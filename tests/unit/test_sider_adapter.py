"""Unit tests for SIDERAdapter (real SIDER 4.1 sample rows, no network)."""

import gzip
from pathlib import Path

import pytest

from knowledge_lookup.adapters import sider_adapter as sider_module
from knowledge_lookup.adapters.sider_adapter import (
    SIDER_FILES,
    SIDERAdapter,
    flat_to_pubchem_cid,
    pubchem_cid_to_flat,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from knowledge_lookup.utils import dataset_cache
from tests.fixtures.sider_responses import (
    DRUG_ATC_TSV,
    DRUG_NAMES_TSV,
    MEDDRA_ALL_SE_TSV,
    MEDDRA_FREQ_TSV,
    MEDDRA_TSV,
)

pytestmark = pytest.mark.unit

LEUCOVORIN = "CID100000143"
BUPROPION = "CID100000444"
CARNITINE = "CID100000085"
ASPIRIN = "CID100002244"
FATIGUE = "C0015672"


@pytest.fixture(autouse=True)
def _fresh_cache():
    sider_module._INDEX_CACHE.clear()
    yield
    sider_module._INDEX_CACHE.clear()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    """A SIDER_DATA_DIR holding the sample files (gz where the server serves gz)."""
    payloads = {
        "names": DRUG_NAMES_TSV,
        "atc": DRUG_ATC_TSV,
        "se": MEDDRA_ALL_SE_TSV,
        "freq": MEDDRA_FREQ_TSV,
        "meddra": MEDDRA_TSV,
    }
    for key, text in payloads.items():
        name = SIDER_FILES[key]
        if name.endswith(".gz"):
            (tmp_path / name).write_bytes(gzip.compress(text.encode()))
        else:
            (tmp_path / name).write_text(text)
    monkeypatch.setenv("SIDER_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def adapter(data_dir):
    return SIDERAdapter(LookupConfig())


class TestIdHelpers:
    def test_flat_to_pubchem(self):
        assert flat_to_pubchem_cid(ASPIRIN) == 2244
        assert flat_to_pubchem_cid("CID000002244") is None
        assert flat_to_pubchem_cid("nonsense") is None

    def test_pubchem_to_flat(self):
        assert pubchem_cid_to_flat(2244) == ASPIRIN
        assert pubchem_cid_to_flat(4091) == "CID100004091"


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.SIDER
        assert adapter.is_available() is True

    @pytest.mark.asyncio
    async def test_nothing_loaded_at_construction(self, data_dir):
        adapter = SIDERAdapter(LookupConfig())
        assert adapter._index is None
        assert adapter._freq_loaded is False


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_side_effect_by_name(self, adapter):
        results = await adapter.search_concepts("fatigue")
        assert results[0].primary_id == FATIGUE
        assert results[0].primary_label == "Fatigue"
        assert results[0].concept_type == ConceptType.PHENOTYPE
        assert results[0].confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_search_drug_by_name(self, adapter):
        results = await adapter.search_concepts("Bupropion")
        assert [c.primary_id for c in results] == [BUPROPION]
        assert results[0].concept_type == ConceptType.DRUG

    @pytest.mark.asyncio
    async def test_search_substring_mixes_drugs_and_side_effects(self, adapter):
        results = await adapter.search_concepts("pain")
        assert [c.primary_label for c in results] == ["Abdominal pain"]

    @pytest.mark.asyncio
    async def test_search_by_atc_code(self, adapter):
        results = await adapter.search_concepts("N06AX")
        assert [c.primary_id for c in results] == [BUPROPION]

    @pytest.mark.asyncio
    async def test_search_by_identifier(self, adapter):
        results = await adapter.search_concepts(LEUCOVORIN)
        assert [c.primary_label for c in results] == ["leucovorin"]

    @pytest.mark.asyncio
    async def test_limit_and_empty_query(self, adapter):
        assert len(await adapter.search_concepts("pain", limit=1)) == 1
        assert await adapter.search_concepts("pain", limit=0) == []
        assert await adapter.search_concepts("   ") == []
        assert await adapter.search_concepts("zzz-no-such-thing") == []

    @pytest.mark.asyncio
    async def test_search_never_raises(self, adapter, monkeypatch):
        async def boom():
            raise RuntimeError("index failed")

        monkeypatch.setattr(adapter, "_load_index", boom)
        assert await adapter.search_concepts("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_drug_details(self, adapter):
        concept = await adapter.get_concept_details(BUPROPION)
        assert concept.primary_label == "bupropion"
        assert concept.concept_type == ConceptType.DRUG
        assert "ATC:N06AX12" in concept.categories
        pubchem = concept.get_identifier(KnowledgeSource.PUBCHEM)
        assert pubchem.identifier == "444"
        data = concept.source_data[KnowledgeSource.SIDER]
        assert data["pubchem_cid"] == 444
        assert data["atc_codes"] == ["N06AX12"]
        assert (
            data["n_side_effects"] == 5
        )  # abdominal/GI pain, amnesia, dyspnoea, fatigue, insomnia
        assert data["stitch_stereo_ids"] == ["CID000000444"]
        assert concept.confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_side_effect_details(self, adapter):
        concept = await adapter.get_concept_details(FATIGUE)
        assert concept.primary_label == "Fatigue"
        assert concept.get_identifier(KnowledgeSource.UMLS).identifier == FATIGUE
        assert concept.source_data[KnowledgeSource.SIDER]["n_drugs"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "concept_id",
        ["SIDER:CID100000444", "cid100000444", "CID000000444", "PUBCHEM:444", "CID:444"],
    )
    async def test_drug_id_normalisation(self, adapter, concept_id):
        concept = await adapter.get_concept_details(concept_id)
        assert concept is not None and concept.primary_id == BUPROPION

    @pytest.mark.asyncio
    @pytest.mark.parametrize("concept_id", ["UMLS:C0015672", "c0015672", "SIDER:C0015672"])
    async def test_cui_normalisation(self, adapter, concept_id):
        concept = await adapter.get_concept_details(concept_id)
        assert concept is not None and concept.primary_id == FATIGUE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("concept_id", ["", "  ", "CID199999999", "C9999999", "banana"])
    async def test_unknown_ids_return_none(self, adapter, concept_id):
        assert await adapter.get_concept_details(concept_id) is None

    @pytest.mark.asyncio
    async def test_drug_without_side_effect_rows(self, adapter):
        concept = await adapter.get_concept_details(ASPIRIN)
        assert concept.primary_label == "aspirin"
        assert concept.source_data[KnowledgeSource.SIDER]["n_side_effects"] == 0
        assert await adapter.get_relationships(ASPIRIN) == []

    @pytest.mark.asyncio
    async def test_details_never_raise(self, adapter, monkeypatch):
        async def boom():
            raise RuntimeError("x")

        monkeypatch.setattr(adapter, "_load_index", boom)
        assert await adapter.get_concept_details(BUPROPION) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_drug_to_side_effects_with_frequency(self, adapter):
        edges = await adapter.get_relationships(BUPROPION)
        by_id = {e["related_id"]: e for e in edges}
        assert set(by_id) == {"C0000737", "C0002622", "C0013404", FATIGUE, "C0917801"}
        for edge in edges:
            assert edge["relation_label"] == "has_side_effect"
            assert edge["source"] == "SIDER"
        fatigue = by_id[FATIGUE]
        assert fatigue["frequency"] == "5%"
        assert fatigue["frequency_min"] == pytest.approx(0.05)
        assert fatigue["frequency_max"] == pytest.approx(0.05)
        assert fatigue["placebo_frequency_max"] == pytest.approx(0.086)
        amnesia = by_id["C0002622"]
        assert amnesia["frequency"] in {"rare", "postmarketing"}
        assert amnesia["frequency_min"] == 0.0
        assert amnesia["frequency_max"] == pytest.approx(0.001)
        assert amnesia["frequency_all"] == ["postmarketing", "rare"]
        dyspnoea = by_id["C0013404"]  # 0%, 1%, 2%, infrequent, rare -> most specific high figure
        assert dyspnoea["frequency"] == "2%"
        assert dyspnoea["frequency_all"] == ["0%", "1%", "2%", "infrequent", "rare"]

    @pytest.mark.asyncio
    async def test_most_frequent_first(self, adapter):
        edges = await adapter.get_relationships(BUPROPION)
        # lower bound of the reported frequency descending, then edges without frequency data (alphabetical)
        lows = [e.get("frequency_min", -1.0) for e in edges]
        assert lows == sorted(lows, reverse=True)
        assert [e["related_name"] for e in edges] == [
            "Fatigue",
            "Dyspnoea",
            "Amnesia",
            "Abdominal pain",
            "Insomnia",
        ]

    @pytest.mark.asyncio
    async def test_edge_without_frequency_data(self, adapter):
        edges = await adapter.get_relationships(BUPROPION)
        insomnia = next(e for e in edges if e["related_id"] == "C0917801")
        assert "frequency" not in insomnia and "placebo_frequency_max" not in insomnia

    @pytest.mark.asyncio
    async def test_limit(self, adapter):
        assert len(await adapter.get_relationships(BUPROPION, limit=2)) == 2
        assert await adapter.get_relationships(BUPROPION, limit=0) == []

    @pytest.mark.asyncio
    async def test_side_effect_to_drugs(self, adapter):
        edges = await adapter.get_relationships("UMLS:C0015672")
        assert [(e["related_id"], e["related_name"]) for e in edges] == [
            (BUPROPION, "bupropion"),
            (LEUCOVORIN, "leucovorin"),
        ]
        assert {e["relation_label"] for e in edges} == {"side_effect_of"}
        assert len(await adapter.get_relationships(FATIGUE, limit=1)) == 1

    @pytest.mark.asyncio
    async def test_unknown_and_error(self, adapter, monkeypatch):
        assert await adapter.get_relationships("nope") == []

        async def boom():
            raise RuntimeError("x")

        monkeypatch.setattr(adapter, "_load_freq", boom)
        assert await adapter.get_relationships(BUPROPION) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_drug_mappings(self, adapter):
        mappings = await adapter.get_mappings(LEUCOVORIN)
        by_target = {(m["toSource"], m["toId"]): m for m in mappings}
        assert by_target[("PUBCHEM", "143")]["mappingType"] == "exact"
        assert by_target[("PUBCHEM", "143")]["confidence"] == 1.0
        assert ("PUBCHEM", "149436") in by_target  # stereo-specific compound id
        assert by_target[("PUBCHEM", "149436")]["mappingType"] == "stereoisomer"
        assert {c for s, c in by_target if s == "ATC"} == {"V03AF03", "V03AF04", "V03AF06"}
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == LEUCOVORIN and m["fromSource"] == "SIDER"

    @pytest.mark.asyncio
    async def test_side_effect_mappings(self, adapter):
        mappings = await adapter.get_mappings(FATIGUE)
        by_target = {(m["toSource"], m["toId"]): m for m in mappings}
        assert ("UMLS", FATIGUE) in by_target
        assert by_target[("MEDDRA", "10016256")]["mappingType"] == "exact"  # PT code
        assert by_target[("MEDDRA", "10043890")]["mappingType"] == "synonym"  # "Tiredness" LLT
        assert len({(m["toSource"], m["toId"]) for m in mappings}) == len(mappings)

    @pytest.mark.asyncio
    async def test_unknown_and_error(self, adapter, monkeypatch):
        assert await adapter.get_mappings("nope") == []

        async def boom():
            raise RuntimeError("x")

        monkeypatch.setattr(adapter, "_load_meddra", boom)
        assert await adapter.get_mappings(FATIGUE) == []


class TestDatasetLoading:
    @pytest.mark.asyncio
    async def test_accepts_decompressed_files(self, tmp_path, monkeypatch):
        """SIDER_DATA_DIR may hold unpacked ``.tsv`` copies of the gz files."""
        (tmp_path / "drug_names.tsv").write_text(DRUG_NAMES_TSV)
        (tmp_path / "drug_atc.tsv").write_text(DRUG_ATC_TSV)
        (tmp_path / "meddra_all_se.tsv").write_text(MEDDRA_ALL_SE_TSV)
        monkeypatch.setenv("SIDER_DATA_DIR", str(tmp_path))
        adapter = SIDERAdapter(LookupConfig())
        assert [c.primary_id for c in await adapter.search_concepts("fatigue")][:1] == [FATIGUE]

    @pytest.mark.asyncio
    async def test_index_shared_between_instances(self, data_dir):
        first = SIDERAdapter(LookupConfig())
        await first.search_concepts("fatigue")
        second = SIDERAdapter(LookupConfig())
        await second.search_concepts("fatigue")
        assert first._index is second._index

    @pytest.mark.asyncio
    async def test_downloads_missing_files_lazily(self, tmp_path, monkeypatch):
        """Without local files the adapter goes through ensure_dataset (patched network)."""
        requested: list[str] = []
        payloads = {
            "drug_names.tsv": DRUG_NAMES_TSV.encode(),
            "drug_atc.tsv": DRUG_ATC_TSV.encode(),
            "meddra_all_se.tsv.gz": gzip.compress(MEDDRA_ALL_SE_TSV.encode()),
        }

        async def fake_fetch(url, dest, timeout, headers):
            requested.append(url)
            dest.write_bytes(payloads[url.rsplit("/", 1)[-1]])

        monkeypatch.setattr(dataset_cache, "_fetch", fake_fetch)
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("SIDER_DATA_DIR", raising=False)

        adapter = SIDERAdapter(LookupConfig())
        assert requested == []  # nothing at construction
        results = await adapter.search_concepts("fatigue")
        assert results and results[0].primary_id == FATIGUE
        assert sorted(url.rsplit("/", 1)[-1] for url in requested) == sorted(payloads)
        assert all(u.startswith("https://sideeffects.embl.de/media/download/") for u in requested)
        assert (tmp_path / "meddra_all_se.tsv").exists()  # gunzipped into the cache

    @pytest.mark.asyncio
    async def test_download_failure_returns_empty(self, tmp_path, monkeypatch):
        async def fail(url, dest, timeout, headers):
            raise OSError("offline")

        monkeypatch.setattr(dataset_cache, "_fetch", fail)
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("SIDER_DATA_DIR", raising=False)
        adapter = SIDERAdapter(LookupConfig())
        assert await adapter.search_concepts("fatigue") == []
        assert await adapter.get_concept_details(FATIGUE) is None
        assert await adapter.get_relationships(FATIGUE) == []
        assert await adapter.get_mappings(FATIGUE) == []


class TestParsers:
    def test_malformed_rows_are_skipped(self, tmp_path):
        names = tmp_path / "n.tsv"
        names.write_text("CID100000001\tfoo\nbroken\n\n")
        atc = tmp_path / "a.tsv"
        atc.write_text("CID100000001\tA01AA01\nCID100000001\tA01AA01\nx\n")
        se = tmp_path / "s.tsv"
        se.write_text(
            "CID100000001\tCID000000001\tC0000001\tPT\tC0000001\tThing\nshort\trow\n"
            "CID100000001\tCID000000001\tC0000002\tLLT\tC0000002\tLLT only\n"
        )
        index = SIDERAdapter._build_index(names, atc, se)
        assert index["names"] == {"CID100000001": "foo"}
        assert index["atc"] == {"CID100000001": ["A01AA01"]}
        assert index["se_by_drug"] == {"CID100000001": {"C0000001": "Thing"}}
        assert "C0000002" not in index["se_names"]

    def test_freq_non_numeric_bounds(self, tmp_path):
        freq = tmp_path / "f.tsv"
        freq.write_text(
            "CID100000001\tCID000000001\tC0000001\t\tfrequent\tNA\t1\tPT\tC0000001\tThing\n"
        )
        result = SIDERAdapter._build_freq(freq)
        assert result[("CID100000001", "C0000001")] == [("frequent", None, 1.0, False)]
