"""Unit tests for OFFSIDESAdapter (real OFFSIDES sample rows, no network)."""

import gzip
import math
from pathlib import Path

import pytest

from knowledge_lookup.adapters import offsides_adapter as off_module
from knowledge_lookup.adapters.offsides_adapter import OFFSIDES_URL, OFFSIDESAdapter, _Store
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from knowledge_lookup.utils import dataset_cache
from tests.fixtures.offsides_responses import OFFSIDES_CSV

pytestmark = pytest.mark.unit

NORETHINDRONE = "RXNORM:7514"
ERGOLOID = "RXNORM:4024"
FATIGUE = "MEDDRA:10016256"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """No test may read the user's dataset cache, env overrides or the network."""
    off_module._STORE_CACHE.clear()
    monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("OFFSIDES_PATH", raising=False)
    monkeypatch.delenv("OFFSIDES_DOWNLOAD", raising=False)
    yield
    off_module._STORE_CACHE.clear()


@pytest.fixture
def csv_path(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "OFFSIDES.csv"
    path.write_text(OFFSIDES_CSV)
    monkeypatch.setenv("OFFSIDES_PATH", str(path))
    return path


@pytest.fixture
def adapter(csv_path):
    return OFFSIDESAdapter(LookupConfig())


class TestAvailability:
    def test_source(self):
        assert OFFSIDESAdapter(LookupConfig()).get_source() == KnowledgeSource.OFFSIDES

    def test_unavailable_by_default(self):
        assert OFFSIDESAdapter(LookupConfig()).is_available() is False

    def test_available_with_local_file(self, csv_path):
        assert OFFSIDESAdapter(LookupConfig()).is_available() is True

    def test_unavailable_with_missing_local_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OFFSIDES_PATH", str(tmp_path / "nope.csv"))
        assert OFFSIDESAdapter(LookupConfig()).is_available() is False

    def test_available_with_opt_in(self, monkeypatch):
        monkeypatch.setenv("OFFSIDES_DOWNLOAD", "1")
        assert OFFSIDESAdapter(LookupConfig()).is_available() is True

    def test_available_when_cached(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "OFFSIDES.csv.gz").write_bytes(gzip.compress(OFFSIDES_CSV.encode()))
        assert OFFSIDESAdapter(LookupConfig()).is_available() is True

    @pytest.mark.asyncio
    async def test_nothing_loaded_at_construction(self, csv_path):
        assert OFFSIDESAdapter(LookupConfig())._store is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_adverse_event(self, adapter):
        results = await adapter.search_concepts("fatigue")
        assert results[0].primary_id == FATIGUE
        assert results[0].concept_type == ConceptType.PHENOTYPE
        assert results[0].confidence_score == 1.0
        assert "Chronic fatigue syndrome" in [c.primary_label for c in results]

    @pytest.mark.asyncio
    async def test_search_drug(self, adapter):
        results = await adapter.search_concepts("norethindrone")
        assert [c.primary_id for c in results] == [NORETHINDRONE]
        assert results[0].concept_type == ConceptType.DRUG

    @pytest.mark.asyncio
    async def test_search_name_with_comma(self, adapter):
        results = await adapter.search_concepts("ergoloid")
        assert results[0].primary_label == "ergoloid mesylates, USP"

    @pytest.mark.asyncio
    async def test_search_by_id(self, adapter):
        assert [c.primary_id for c in await adapter.search_concepts("10016256")] == [FATIGUE]
        assert [c.primary_id for c in await adapter.search_concepts("RXNORM:4024")] == [ERGOLOID]

    @pytest.mark.asyncio
    async def test_limit_and_misses(self, adapter):
        assert len(await adapter.search_concepts("anaemia", limit=1)) == 1
        assert await adapter.search_concepts("anaemia", limit=0) == []
        assert await adapter.search_concepts("") == []
        assert await adapter.search_concepts("zzzz") == []

    @pytest.mark.asyncio
    async def test_search_without_dataset_returns_empty(self):
        """No file, no opt-in: logged and empty, never an exception or a download."""
        assert await OFFSIDESAdapter(LookupConfig()).search_concepts("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_drug_details(self, adapter):
        concept = await adapter.get_concept_details(NORETHINDRONE)
        assert concept.primary_label == "Norethindrone"
        data = concept.source_data[KnowledgeSource.OFFSIDES]
        assert data["rxnorm_id"] == 7514
        assert data["n_pairs"] == 6
        # only Jaundice has a PRR whose 95% CI lies above 1 (Fatigue 1.18 [0.99, 1.41])
        assert data["n_prr_signals_ci95_above_1"] == 1
        assert "not causal" in concept.definitions[0]

    @pytest.mark.asyncio
    async def test_event_details(self, adapter):
        concept = await adapter.get_concept_details("MEDDRA:10016256")
        assert concept.primary_label == "Fatigue"
        assert concept.source_data[KnowledgeSource.OFFSIDES]["n_pairs"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "concept_id", ["7514", "rxnorm:7514", "RXCUI:7514", "OFFSIDES:RXNORM:7514"]
    )
    async def test_drug_id_forms(self, adapter, concept_id):
        concept = await adapter.get_concept_details(concept_id)
        assert concept is not None and concept.primary_id == NORETHINDRONE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("concept_id", ["10016256", "meddra:10016256"])
    async def test_event_id_forms(self, adapter, concept_id):
        concept = await adapter.get_concept_details(concept_id)
        assert concept is not None and concept.primary_id == FATIGUE

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "concept_id", ["", "RXNORM:999999", "MEDDRA:10999999", "abc", "RXNORM:x"]
    )
    async def test_unknown_ids(self, adapter, concept_id):
        assert await adapter.get_concept_details(concept_id) is None
        assert await adapter.get_relationships(concept_id) == []
        assert await adapter.get_mappings(concept_id) == []

    @pytest.mark.asyncio
    async def test_details_never_raise(self, adapter, monkeypatch):
        async def boom():
            raise RuntimeError("x")

        monkeypatch.setattr(adapter, "_load_store", boom)
        assert await adapter.get_concept_details(NORETHINDRONE) is None
        assert await adapter.get_relationships(NORETHINDRONE) == []
        assert await adapter.get_mappings(NORETHINDRONE) == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_drug_to_events_with_statistics(self, adapter):
        edges = await adapter.get_relationships(NORETHINDRONE)
        assert len(edges) == 6
        assert {e["relation_label"] for e in edges} == {"has_adverse_event_signal"}
        by_name = {e["related_name"]: e for e in edges}
        fatigue = by_name["Fatigue"]
        assert fatigue["related_id"] == FATIGUE
        assert fatigue["source"] == "OFFSIDES"
        assert fatigue["prr"] == pytest.approx(1.17962)
        assert fatigue["prr_error"] == pytest.approx(0.0900726)
        assert fatigue["reporting_frequency"] == pytest.approx(0.04276)
        assert (fatigue["a"], fatigue["b"], fatigue["c"], fatigue["d"]) == (132, 2955, 1119, 29751)
        assert fatigue["prr_ci95_low"] == pytest.approx(
            1.17962 * math.exp(-1.959964 * 0.0900726), abs=1e-3
        )
        assert fatigue["prr_ci95_low"] < 1.0 < fatigue["prr_ci95_high"]
        assert "not causal" in fatigue["caveat"]

    @pytest.mark.asyncio
    async def test_ordered_by_ci_lower_bound(self, adapter):
        edges = await adapter.get_relationships(NORETHINDRONE)
        lows = [e["prr_ci95_low"] for e in edges]
        assert lows == sorted(lows, reverse=True)
        assert edges[0]["related_name"] == "Jaundice"  # PRR 4.15, tight CI

    @pytest.mark.asyncio
    async def test_one_report_pair_ranks_by_uncertainty_not_prr(self, adapter):
        edges = await adapter.get_relationships("RXNORM:4024")
        names = [e["related_name"] for e in edges]
        # Anaemia/Jaundice both have PRR 2.86 but Jaundice (A=2) is far less certain
        assert names.index("Anaemia") < names.index("Jaundice")

    @pytest.mark.asyncio
    async def test_event_to_drugs(self, adapter):
        edges = await adapter.get_relationships(FATIGUE)
        assert {e["relation_label"] for e in edges} == {"adverse_event_signal_of"}
        assert {e["related_id"] for e in edges} == {NORETHINDRONE, ERGOLOID}
        assert all("prr" in e and "reporting_frequency" in e for e in edges)

    @pytest.mark.asyncio
    async def test_limit(self, adapter):
        assert len(await adapter.get_relationships(NORETHINDRONE, limit=2)) == 2
        assert await adapter.get_relationships(NORETHINDRONE, limit=0) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_drug_mapping(self, adapter):
        assert await adapter.get_mappings(NORETHINDRONE) == [
            {
                "fromId": NORETHINDRONE,
                "toId": "7514",
                "fromSource": "OFFSIDES",
                "toSource": "RXNORM",
                "mappingType": "exact",
                "confidence": 1.0,
            }
        ]

    @pytest.mark.asyncio
    async def test_event_mapping(self, adapter):
        (mapping,) = await adapter.get_mappings("10016256")
        assert (mapping["toSource"], mapping["toId"]) == ("MEDDRA", "10016256")


class TestDataset:
    @pytest.mark.asyncio
    async def test_gzipped_local_file(self, tmp_path, monkeypatch):
        path = tmp_path / "OFFSIDES.csv.gz"
        path.write_bytes(gzip.compress(OFFSIDES_CSV.encode()))
        monkeypatch.setenv("OFFSIDES_PATH", str(path))
        adapter = OFFSIDESAdapter(LookupConfig())
        assert (await adapter.get_concept_details(NORETHINDRONE)) is not None

    @pytest.mark.asyncio
    async def test_store_shared_between_instances(self, csv_path):
        first, second = OFFSIDESAdapter(LookupConfig()), OFFSIDESAdapter(LookupConfig())
        await first.search_concepts("fatigue")
        await second.search_concepts("fatigue")
        assert first._store is second._store

    @pytest.mark.asyncio
    async def test_cached_copy_is_used_without_flag(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "OFFSIDES.csv.gz").write_bytes(gzip.compress(OFFSIDES_CSV.encode()))
        adapter = OFFSIDESAdapter(LookupConfig())
        assert (await adapter.get_concept_details("RXNORM:4024")).primary_label.startswith("ergo")

    @pytest.mark.asyncio
    async def test_opt_in_download_keeps_gz(self, tmp_path, monkeypatch):
        requested: list[str] = []

        async def fake_fetch(url, dest, timeout, headers):
            requested.append(url)
            dest.write_bytes(gzip.compress(OFFSIDES_CSV.encode()))

        monkeypatch.setattr(dataset_cache, "_fetch", fake_fetch)
        monkeypatch.setenv("OFFSIDES_DOWNLOAD", "yes")
        adapter = OFFSIDESAdapter(LookupConfig())
        assert requested == []  # lazy
        concepts = await adapter.search_concepts("fatigue")
        assert concepts and requested == [OFFSIDES_URL]
        cached = tmp_path / "cache" / "OFFSIDES.csv.gz"
        assert cached.read_bytes()[:2] == b"\x1f\x8b"  # still gzipped on disk

    @pytest.mark.asyncio
    async def test_missing_local_path_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OFFSIDES_PATH", str(tmp_path / "missing.csv"))
        adapter = OFFSIDESAdapter(LookupConfig())
        assert await adapter.search_concepts("fatigue") == []


class TestParser:
    def test_header_variants_and_bad_rows(self, tmp_path):
        text = (
            "drug_rxnorm,drug_concept_name,condition_meddra,condition_concept_name,"
            "A,B,C,D,PRR,PRR_error,mean_reporting_frequency\n"
            '1,"drug, one",10000001,Event,3,7,2,98,15.0,0.5,0.3\n'
            "oops,short\n"
            "2,drug two,10000002,Event two,x,7,2,98,15.0,0.5,0.3\n"
            "3,drug three,10000003,Zero PRR,1,9,1,99,0.0,0.5,0.1\n"
        )
        path = tmp_path / "o.csv"
        path.write_text(text)
        store = _Store.from_file(path)
        assert len(store) == 2
        assert store.drug_names == {1: "drug, one", 3: "drug three"}
        assert "prr_ci95_low" not in store.signal(1)  # PRR 0 -> no CI
        assert store.signal(0)["prr"] == 15.0

    def test_missing_column_raises(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("a,b\n1,2\n")
        with pytest.raises(ValueError):
            _Store.from_file(path)

    @pytest.mark.asyncio
    async def test_bad_header_returns_empty(self, tmp_path, monkeypatch):
        path = tmp_path / "bad.csv"
        path.write_text("a,b\n1,2\n")
        monkeypatch.setenv("OFFSIDES_PATH", str(path))
        assert await OFFSIDESAdapter(LookupConfig()).search_concepts("x") == []
