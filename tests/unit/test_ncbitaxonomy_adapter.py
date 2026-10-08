"""Unit tests for NCBITaxonomyAdapter (NCBI Datasets taxonomy v2); no network."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import ncbitaxonomy_adapter
from knowledge_lookup.adapters.ncbitaxonomy_adapter import NCBITaxonomyAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.ncbitaxonomy_responses import (
    LINKS_EBV,
    LINKS_SARS2,
    NAME_REPORT_EBV,
    REPORT_EBV,
    REPORT_EBV_RELATED,
    REPORT_EMPTY,
    REPORT_SARS2,
    SUGGEST_EMPTY,
    SUGGEST_SARS,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setattr(ncbitaxonomy_adapter, "_MIN_INTERVAL_KEYLESS", 0.0)
    monkeypatch.setattr(ncbitaxonomy_adapter, "_MIN_INTERVAL_KEYED", 0.0)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return NCBITaxonomyAdapter(lookup_config)


def router(calls=None, links=None, name_report=None, reports=None):
    """Fake ``_make_request`` answering by URL path."""
    reports = reports or {}

    async def fake(url, params=None, headers=None, json_data=None):
        if calls is not None:
            calls.append((url, params, headers))
        path = url.split("/taxonomy/", 1)[1]
        if path.startswith("taxon_suggest/"):
            return copy.deepcopy(SUGGEST_SARS)
        if path.endswith("/name_report"):
            if isinstance(name_report, Exception):
                raise name_report
            return copy.deepcopy(name_report if name_report is not None else NAME_REPORT_EBV)
        if path.endswith("/links"):
            if isinstance(links, Exception):
                raise links
            return copy.deepcopy(links if links is not None else {})
        if path.endswith("/dataset_report"):
            key = path.split("/")[1]
            if key in reports:
                return copy.deepcopy(reports[key])
            raise AssertionError(f"unexpected dataset_report {key}")
        raise AssertionError(f"unexpected URL {url}")

    return fake


EBV_REPORTS = {
    "10376": REPORT_EBV,
    "1,10239,3044472,10375,12509,31525,777777": REPORT_EBV_RELATED,
}


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.NCBITAXONOMY
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2697049", "2697049"),
            ("NCBITaxon:2697049", "2697049"),
            ("ncbitaxon_2697049", "2697049"),
            ("taxid:2697049", "2697049"),
            ("txid2697049", None),
            ("TaxID: 10376", "10376"),
            ("0009606", "9606"),
            ("0", None),
            ("", None),
            (None, None),
            ("SARS-CoV-2", None),
            ("12345678901", None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert NCBITaxonomyAdapter._parse_id(raw) == expected

    def test_rank_helper(self):
        assert NCBITaxonomyAdapter._rank({"rank": "SPECIES"}) == "species"
        assert NCBITaxonomyAdapter._rank({"rank": "ACELLULAR_ROOT"}) == "acellular root"
        assert NCBITaxonomyAdapter._rank({}) == "no rank"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search(self, adapter):
        calls = []
        with patch.object(adapter, "_make_request", router(calls)):
            concepts = await adapter.search_concepts("SARS-CoV-2", limit=10)
        assert [c.primary_id for c in concepts] == ["2901879", "2697049", "9606"]
        sars2 = concepts[1]
        assert sars2.concept_type == ConceptType.ORGANISM
        assert sars2.primary_label == "Severe acute respiratory syndrome coronavirus 2"
        assert sars2.synonyms == ["SARS-CoV-2"]
        assert sars2.semantic_types == ["no rank"]
        assert sars2.categories == ["viruses"]
        assert sars2.sources == [KnowledgeSource.NCBITAXONOMY]
        assert sars2.identifiers[1].identifier == "NCBITaxon:2697049"
        assert concepts[2].synonyms == ["human"]
        assert concepts[2].semantic_types == ["species"]
        assert concepts[0].confidence_score > concepts[2].confidence_score
        url, params, headers = calls[0]
        assert url.endswith("/taxonomy/taxon_suggest/SARS-CoV-2")
        assert params == {"tax_rank_filter": "higher_taxon"}
        assert "api-key" not in headers

    @pytest.mark.asyncio
    async def test_limit(self, adapter):
        with patch.object(adapter, "_make_request", router()):
            assert len(await adapter.search_concepts("sars", limit=1)) == 1
            assert await adapter.search_concepts("sars", limit=0) == []

    @pytest.mark.asyncio
    async def test_slash_in_query_is_not_a_path_separator(self, adapter):
        calls = []
        with patch.object(adapter, "_make_request", router(calls)):
            await adapter.search_concepts("ME/CFS virus", limit=1)
        assert calls[0][0].endswith("/taxon_suggest/ME CFS virus")

    @pytest.mark.asyncio
    async def test_search_by_id_goes_to_details(self, adapter):
        with patch.object(adapter, "_make_request", router(reports={"2697049": REPORT_SARS2})):
            concepts = await adapter.search_concepts("NCBITaxon:2697049")
        assert [c.primary_id for c in concepts] == ["2697049"]

    @pytest.mark.asyncio
    async def test_search_by_unknown_id_is_empty(self, adapter):
        with patch.object(adapter, "_make_request", router(reports={"99": REPORT_EMPTY})):
            assert await adapter.search_concepts("99") == []

    @pytest.mark.asyncio
    async def test_empty_and_error(self, adapter):
        assert await adapter.search_concepts("   ") == []
        assert await adapter.search_concepts(None) == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value=SUGGEST_EMPTY)):
            assert await adapter.search_concepts("zzzqqq") == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value=["not a dict"])):
            assert await adapter.search_concepts("x") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details(self, adapter):
        with patch.object(adapter, "_make_request", router(reports=EBV_REPORTS)):
            concept = await adapter.get_concept_details("NCBITaxon:10376")
        assert concept is not None
        assert concept.primary_id == "10376"
        assert concept.primary_label == "human gammaherpesvirus 4"
        assert concept.concept_type == ConceptType.ORGANISM
        assert concept.synonyms[0] == "Epstein-Barr virus"
        assert {"EBV", "HHV-4", "Human herpesvirus 4"} <= set(concept.synonyms)
        assert len(concept.synonyms) == len({s.casefold() for s in concept.synonyms})
        assert concept.semantic_types == ["no rank"]
        assert concept.categories == ["viruses", "moltype:dsDNA"]
        assert "Orthoherpesviridae > Lymphocryptovirus" in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.NCBITAXONOMY]
        assert data["secondary_tax_ids"] == [47902]
        assert data["parents"][-1] == 10375
        assert data["counts"] == {"assembly": 586}
        assert data["classification"]["genus"] == "Lymphocryptovirus"
        assert concept.confidence_score == 0.95
        assert concept.identifiers[1].url.endswith("/taxonomy/10376")

    @pytest.mark.asyncio
    async def test_details_survive_name_report_failure(self, adapter):
        fake = router(reports=EBV_REPORTS, name_report=RuntimeError("down"))
        with patch.object(adapter, "_make_request", fake):
            concept = await adapter.get_concept_details("10376")
        assert concept is not None
        assert concept.synonyms == ["Epstein-Barr virus"]

    @pytest.mark.asyncio
    async def test_rank_and_authority(self, adapter):
        report = copy.deepcopy(REPORT_SARS2)
        tax = report["reports"][0]["taxonomy"]
        tax["rank"] = "SPECIES"
        tax["current_scientific_name"]["authority"] = "Linnaeus, 1758"
        tax.pop("classification")
        fake = router(reports={"2697049": report}, name_report={"reports": []})
        with patch.object(adapter, "_make_request", fake):
            concept = await adapter.get_concept_details("2697049")
        assert concept.semantic_types == ["species"]
        assert concept.definitions == ["NCBI Taxonomy species (taxid 2697049)"]
        assert concept.source_data[KnowledgeSource.NCBITAXONOMY]["authority"] == "Linnaeus, 1758"

    @pytest.mark.asyncio
    async def test_unknown_and_invalid(self, adapter):
        with patch.object(adapter, "_make_request", router(reports={"99": REPORT_EMPTY})):
            assert await adapter.get_concept_details("99") is None
        assert await adapter.get_concept_details("not-an-id") is None
        assert await adapter.get_concept_details("") is None

    @pytest.mark.asyncio
    async def test_nameless_report_is_none(self, adapter):
        nameless = {"reports": [{"taxonomy": {"tax_id": 7}}]}
        with patch.object(adapter, "_make_request", router(reports={"7": nameless})):
            assert await adapter.get_concept_details("7") is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_concept_details("10376") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships(self, adapter):
        calls = []
        with patch.object(adapter, "_make_request", router(calls, reports=EBV_REPORTS)):
            rels = await adapter.get_relationships("10376")
        by_label = {}
        for rel in rels:
            by_label.setdefault(rel["relation_label"], []).append(rel)
        # parent is the last lineage entry; the rest are ancestors, root first
        assert [r["related_id"] for r in by_label["is_a"]] == ["NCBITaxon:10375"]
        assert by_label["is_a"][0]["related_name"] == "Lymphocryptovirus"
        assert by_label["is_a"][0]["rank"] == "genus"
        ancestors = by_label["descendant_of"]
        assert [r["related_id"] for r in ancestors] == [
            "NCBITaxon:1",
            "NCBITaxon:10239",
            "NCBITaxon:3044472",
        ]
        assert [r["depth"] for r in ancestors] == [0, 1, 2]
        assert [r["rank"] for r in ancestors] == ["no rank", "acellular root", "family"]
        # child 777777 is not in the report and is skipped
        assert [r["related_id"] for r in by_label["has_subclass"]] == [
            "NCBITaxon:12509",
            "NCBITaxon:31525",
        ]
        assert all(r["source"] == "NCBITAXONOMY" for r in rels)
        assert calls[1][1] == {"page_size": 7}

    @pytest.mark.asyncio
    async def test_children_are_capped(self, adapter):
        reports = {
            "10376": REPORT_EBV,
            "1,10239,3044472,10375,12509": REPORT_EBV_RELATED,
        }
        with patch.object(adapter, "_make_request", router(reports=reports)):
            rels = await adapter.get_relationships("10376", limit=1)
        assert [r["related_id"] for r in rels if r["relation_label"] == "has_subclass"] == [
            "NCBITaxon:12509"
        ]

    @pytest.mark.asyncio
    async def test_root_has_no_parent(self, adapter):
        root = {
            "reports": [{"taxonomy": {"tax_id": 1, "current_scientific_name": {"name": "root"}}}]
        }
        with patch.object(adapter, "_make_request", router(reports={"1": root})):
            assert await adapter.get_relationships("1") == []

    @pytest.mark.asyncio
    async def test_unknown_invalid_zero_limit_and_error(self, adapter):
        with patch.object(adapter, "_make_request", router(reports={"99": REPORT_EMPTY})):
            assert await adapter.get_relationships("99") == []
        assert await adapter.get_relationships("junk") == []
        assert await adapter.get_relationships("10376", limit=0) == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_relationships("10376") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_with_merged_id_and_eol(self, adapter):
        fake = router(reports=EBV_REPORTS, links=LINKS_EBV)
        with patch.object(adapter, "_make_request", fake):
            mappings = await adapter.get_mappings("10376")
        assert [(m["toId"], m["toSource"], m["mappingType"]) for m in mappings] == [
            ("NCBITaxon:10376", "NCBITAXON", "exactMatch"),
            ("NCBITaxon:47902", "NCBITAXON", "merged_id"),
            ("https://eol.org/pages/46699929", "EOL", "xref"),
        ]
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "10376"
            assert m["fromSource"] == "NCBITAXONOMY"

    @pytest.mark.asyncio
    async def test_wikipedia_link(self, adapter):
        fake = router(reports={"2697049": REPORT_SARS2}, links=LINKS_SARS2)
        with patch.object(adapter, "_make_request", fake):
            mappings = await adapter.get_mappings("taxid:2697049")
        assert [m["toSource"] for m in mappings] == ["NCBITAXON", "WIKIPEDIA", "EOL"]

    @pytest.mark.asyncio
    async def test_links_failure_keeps_other_mappings(self, adapter):
        fake = router(reports={"2697049": REPORT_SARS2}, links=RuntimeError("down"))
        with patch.object(adapter, "_make_request", fake):
            mappings = await adapter.get_mappings("2697049")
        assert [m["toId"] for m in mappings] == ["NCBITaxon:2697049"]

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        with patch.object(adapter, "_make_request", router(reports={"99": REPORT_EMPTY})):
            assert await adapter.get_mappings("99") == []
        assert await adapter.get_mappings("junk") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_mappings("10376") == []


class TestThrottlingAndKey:
    @pytest.mark.asyncio
    async def test_calls_are_spaced(self, adapter, monkeypatch):
        monkeypatch.setattr(ncbitaxonomy_adapter, "_MIN_INTERVAL_KEYLESS", 0.34)
        now = [100.0]
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)
            now[0] += delay

        monkeypatch.setattr(ncbitaxonomy_adapter.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(
            ncbitaxonomy_adapter, "time", SimpleNamespace(monotonic=lambda: now[0])
        )
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            for _ in range(3):
                await adapter._get("taxon/1/links")
        # the first call is not delayed; each later one waits out the interval
        assert len(sleeps) == 2
        assert all(abs(d - 0.34) < 1e-6 for d in sleeps)

    @pytest.mark.asyncio
    async def test_api_key_sent_as_header_and_not_logged_in_url(self, adapter, monkeypatch):
        monkeypatch.setenv("NCBI_API_KEY", "test-key")
        calls = []
        with patch.object(adapter, "_make_request", router(calls)):
            await adapter.search_concepts("sars")
        url, params, headers = calls[0]
        assert headers["api-key"] == "test-key"
        assert "test-key" not in url
        assert "test-key" not in str(params)

    @pytest.mark.asyncio
    async def test_api_key_from_config(self):
        from knowledge_lookup.models import LookupConfig

        adapter = NCBITaxonomyAdapter(LookupConfig(api_keys={"ncbi": "cfg-key"}))
        assert adapter._api_key() == "cfg-key"
