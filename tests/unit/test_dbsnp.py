"""Unit tests for DbSNPAdapter (mocked NCBI Variation Services responses captured live)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import dbsnp_adapter as mod
from knowledge_lookup.adapters.dbsnp_adapter import DbSNPAdapter, parse_rsid
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import dbsnp_responses as fx

pytestmark = pytest.mark.unit

DBSNP = KnowledgeSource.DBSNP


def route(table):
    """AsyncMock side effect answering by the tail of the URL; missing paths raise (HTTP 404)."""

    async def fake(url, params=None, headers=None, json_data=None):
        for suffix, value in table.items():
            if url.endswith(suffix):
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
        raise RuntimeError(f"404 {url}")

    return AsyncMock(side_effect=fake)


FULL = {
    "refsnp/1801133": fx.REFSNP_1801133,
    "refsnp/80357906": fx.REFSNP_80357906,
    "refsnp/4134713": fx.REFSNP_4134713_MERGED,
    "/rsids": fx.SPDI_RSIDS,
    "/contextuals": fx.HGVS_CONTEXTUALS,
}


@pytest.fixture
def adapter(lookup_config, monkeypatch):
    monkeypatch.setattr(mod, "MIN_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(mod, "MIN_INTERVAL_WITH_KEY_SECONDS", 0.0)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    return DbSNPAdapter(lookup_config)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.DBSNP
        assert adapter.is_available() is True
        assert adapter.min_request_timeout >= 60

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("rs1801133", "1801133"),
            ("RS1801133", "1801133"),
            ("1801133", "1801133"),
            ("dbSNP:rs1801133", "1801133"),
            (" rs0001 ", "1"),
            ("rs0", "0"),
            ("abc", None),
            ("rs", None),
            ("", None),
            ("NC_000001.11:11796320:G:A", None),
        ],
    )
    def test_parse_rsid(self, raw, expected):
        assert parse_rsid(raw) == expected

    @pytest.mark.parametrize(
        ("seq_id", "chrom"),
        [
            ("NC_000001.11", "1"),
            ("NC_000017.11", "17"),
            ("NC_000023.11", "X"),
            ("NC_000024.10", "Y"),
            ("NC_012920.1", "MT"),
            ("NG_013351.1", None),
        ],
    )
    def test_chrom_from_accession(self, seq_id, chrom):
        assert mod._chrom_from_accession(seq_id) == chrom

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, lookup_config, monkeypatch):
        monkeypatch.delenv("NCBI_API_KEY", raising=False)
        adapter = DbSNPAdapter(lookup_config)
        sleeps: list[float] = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        with (
            patch.object(adapter, "_make_request", AsyncMock(return_value={})),
            patch.object(mod.asyncio, "sleep", fake_sleep),
        ):
            await adapter._get("refsnp/1")
            await adapter._get("refsnp/2")
        assert len(sleeps) == 1 and 0 < sleeps[0] <= mod.MIN_INTERVAL_SECONDS + 1e-6

    @pytest.mark.asyncio
    async def test_api_key_sent_only_when_configured(self, lookup_config, monkeypatch):
        monkeypatch.setattr(mod, "MIN_INTERVAL_WITH_KEY_SECONDS", 0.0)
        monkeypatch.setenv("NCBI_API_KEY", "test-key")
        adapter = DbSNPAdapter(lookup_config)
        mock = AsyncMock(return_value={})
        with patch.object(adapter, "_make_request", mock):
            await adapter._get("refsnp/1")
        assert mock.await_args.kwargs["params"] == {"api_key": "test-key"}
        monkeypatch.delenv("NCBI_API_KEY")
        with patch.object(adapter, "_make_request", mock):
            await adapter._get("refsnp/1")
        assert mock.await_args.kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_non_dict_response_is_none(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=["x"])):
            assert await adapter._get("refsnp/1") is None


class TestDetails:
    @pytest.mark.asyncio
    async def test_snv_details(self, adapter):
        mock = route(FULL)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("rs1801133")
        assert concept.primary_id == "rs1801133"
        assert concept.primary_label == "rs1801133"
        assert concept.concept_type == ConceptType.MOLECULAR_ENTITY
        assert [i.source for i in concept.identifiers].count(DBSNP) == 1
        assert concept.identifiers[0].url.endswith("/snp/rs1801133")
        assert any(
            i.source == KnowledgeSource.NCBI and i.label == "MTHFR" for i in concept.identifiers
        )
        assert "rs4134713" in concept.synonyms  # merged rsID
        assert "NC_000001.11:g.11796321G>A" in concept.synonyms
        assert "MTHFR" in concept.definitions[0]
        data = concept.source_data[DBSNP]
        assert data["variant_type"] == "snv"
        assert data["status"] == "current"
        grch38 = data["placements"][0]
        assert grch38["assembly"].startswith("GRCh38") and grch38["chrom"] == "1"
        assert grch38["alleles"][1]["spdi"] == "NC_000001.11:11796320:G:A"
        assert data["genes"][0]["symbol"] == "MTHFR"
        assert "missense_variant" in data["consequences"]
        assert data["mane_select_ids"] == ["NM_005957.5"]
        studies = {s["study"]: s for s in data["allele_frequencies"]}
        assert studies["GnomAD_exomes"]["alleles"]["A"] == pytest.approx(0.3233, abs=1e-3)
        assert len(data["allele_frequencies"]) <= mod.MAX_STUDIES
        assert "drug-response" in data["clinvar_significances"]
        assert mock.await_count == 1

    @pytest.mark.asyncio
    async def test_input_forms_hit_the_same_endpoint(self, adapter):
        for raw in ("1801133", "RS1801133", "dbSNP:rs1801133"):
            mock = route(FULL)
            with patch.object(adapter, "_make_request", mock):
                concept = await adapter.get_concept_details(raw)
            assert concept.primary_id == "rs1801133"
            assert mock.await_args.args[0].endswith("/refsnp/1801133")

    @pytest.mark.asyncio
    async def test_merged_rsid_resolves_to_survivor(self, adapter):
        mock = route(FULL)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("rs4134713")
        assert concept.primary_id == "rs1801133"
        data = concept.source_data[DBSNP]
        assert data["requested_id"] == "rs4134713"
        assert data["merged_from"] == ["4134713"]
        assert mock.await_count == 2

    @pytest.mark.asyncio
    async def test_merge_chain_is_bounded(self, adapter):
        loop = {"refsnp/1": {"refsnp_id": "1", "merged_snapshot_data": {"merged_into": ["1"]}}}
        with patch.object(adapter, "_make_request", route(loop)) as mock:
            assert await adapter.get_concept_details("rs1") is None
        assert mock.await_count == mod.MAX_MERGE_HOPS + 1

    @pytest.mark.asyncio
    async def test_spdi_and_hgvs_inputs(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)) as mock:
            by_spdi = await adapter.get_concept_details("NC_000001.11:11796320:G:A")
            by_hgvs = await adapter.get_concept_details("NC_000001.11:g.11796321G>A")
        assert by_spdi.primary_id == by_hgvs.primary_id == "rs1801133"
        urls = [call.args[0] for call in mock.await_args_list]
        assert any("/spdi/NC_000001.11:11796320:G:A/rsids" in u for u in urls)
        assert any("/hgvs/NC_000001.11:g.11796321G>A/contextuals" in u for u in urls)

    @pytest.mark.asyncio
    async def test_spdi_without_rsid_and_bad_hgvs(self, adapter):
        table = {"/rsids": {"data": {"rsids": []}}, "/contextuals": {"data": {"spdis": []}}}
        with patch.object(adapter, "_make_request", route(table)):
            assert await adapter.get_concept_details("NC_000001.11:5:A:T") is None
            assert await adapter.get_concept_details("NC_000001.11:g.5A>T") is None

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        mock = route(FULL)
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.get_concept_details("rs999999999999") is None
            assert await adapter.get_concept_details("abc") is None
            assert await adapter.get_concept_details("") is None
        assert mock.await_count == 1  # invalid input never reaches the network
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=OSError("down"))):
            assert await adapter.get_concept_details("rs1801133") is None
        with patch.object(adapter, "_load", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_concept_details("rs1801133") is None

    @pytest.mark.asyncio
    async def test_withdrawn_and_empty_documents(self, adapter):
        withdrawn = {
            "refsnp_id": "5",
            "withdrawn_snapshot_data": {"withdrawn_time": "2010-01-01T00:00Z"},
        }
        with patch.object(adapter, "_make_request", route({"refsnp/5": withdrawn})):
            concept = await adapter.get_concept_details("rs5")
        assert concept.source_data[DBSNP]["status"] == "withdrawn"
        assert concept.definitions == ["VARIANT rs5"]
        unsupported = {"refsnp_id": "6", "unsupported_snapshot_data": {}}
        with patch.object(adapter, "_make_request", route({"refsnp/6": unsupported})):
            concept = await adapter.get_concept_details("rs6")
        assert concept.source_data[DBSNP]["status"] == "unsupported"
        with patch.object(adapter, "_make_request", route({"refsnp/7": {"create_date": "x"}})):
            assert await adapter.get_concept_details("rs7") is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_resolves_identifiers(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)):
            found = await adapter.search_concepts("rs1801133", limit=5)
        assert [c.primary_id for c in found] == ["rs1801133"]

    @pytest.mark.asyncio
    async def test_search_free_text_and_limit(self, adapter):
        mock = route(FULL)
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.search_concepts("chronic fatigue", 5) == []
            assert await adapter.search_concepts("rs1801133", 0) == []
        mock.assert_not_awaited()


class TestRelationships:
    @pytest.mark.asyncio
    async def test_genes_and_conditions(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)):
            rels = await adapter.get_relationships("rs1801133", limit=50)
        located = [r for r in rels if r["relation_label"] == "located_in"]
        assert [(r["related_id"], r["related_name"]) for r in located] == [("4524", "MTHFR")]
        assert located[0]["id_namespace"] == "NCBI Gene"
        conditions = [r for r in rels if r["relation_label"] == "has_clinical_association"]
        assert conditions
        homocystinuria = next(r for r in conditions if "Homocystinuria" in r["related_name"])
        assert homocystinuria["related_id"] == "C1856061"
        assert homocystinuria["id_namespace"] == "MedGen"
        assert (
            homocystinuria["clinical_significance"]
            == "conflicting-interpretations-of-pathogenicity"
        )
        assert homocystinuria["rcv"].startswith("RCV")
        # "not provided" / "not specified" conditions carry no information
        assert not any(
            r["related_name"].lower() in mod._UNINFORMATIVE_CONDITIONS for r in conditions
        )
        pairs = [(r["related_id"], r["clinical_significance"]) for r in conditions]
        assert len(pairs) == len(set(pairs))

    @pytest.mark.asyncio
    async def test_limit_and_empty(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)):
            assert len(await adapter.get_relationships("rs1801133", limit=2)) == 2
            assert await adapter.get_relationships("rs1801133", limit=0) == []
            assert await adapter.get_relationships("rs999999999999") == []
        with patch.object(adapter, "get_concept_details", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_relationships("rs1801133") == []

    @pytest.mark.asyncio
    async def test_condition_without_ids_falls_back_to_name(self, adapter):
        doc = copy.deepcopy(fx.REFSNP_80357906)
        for ann in doc["primary_snapshot_data"]["allele_annotations"]:
            for rec in ann["clinical"]:
                rec["disease_ids"] = []
                rec["disease_names"] = ["Some condition"]
        with patch.object(adapter, "_make_request", route({"refsnp/80357906": doc})):
            rels = await adapter.get_relationships("rs80357906", limit=50)
        conditions = [r for r in rels if r["relation_label"] == "has_clinical_association"]
        assert conditions[0]["related_id"] == "Some condition"
        assert conditions[0]["id_namespace"] is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_clinvar_hgvs_and_merged_mappings(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)):
            maps = await adapter.get_mappings("rs80357906")
        assert all(m["fromId"] == "rs80357906" and m["fromSource"] == "dbSNP" for m in maps)
        assert all(
            {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"} <= m.keys()
            for m in maps
        )
        by_kind = {(m["toSource"], m.get("kind")): m for m in maps}
        assert by_kind[("ClinVar", "variation")]["toId"] == "17677"
        assert by_kind[("ClinVar", "VCV")]["toId"] == "VCV000017677"
        assert by_kind[("ClinVar", "RCV")]["toId"].startswith("RCV")
        merged = {m["toId"] for m in maps if m["mappingType"] == "merged_from"}
        assert {"rs76171189", "rs397507246"} <= merged
        assert any(m["toSource"] == "HGVS" and m["toId"].startswith("NC_000017") for m in maps)
        assert any(m["toSource"] == "NCBI" and m["toId"] == "672" for m in maps)
        keys = [(m["toId"], m["toSource"]) for m in maps]
        assert len(keys) == len(set(keys))

    @pytest.mark.asyncio
    async def test_merged_input_is_mapped_from_survivor(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)):
            maps = await adapter.get_mappings("rs4134713")
        assert all(m["fromId"] == "rs1801133" for m in maps)
        assert any(m["toId"] == "rs4134713" and m["mappingType"] == "merged_from" for m in maps)

    @pytest.mark.asyncio
    async def test_mapping_failures(self, adapter):
        with patch.object(adapter, "_make_request", route(FULL)):
            assert await adapter.get_mappings("rs999999999999") == []
            assert await adapter.get_mappings("abc") == []
        with patch.object(adapter, "get_concept_details", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_mappings("rs1801133") == []
