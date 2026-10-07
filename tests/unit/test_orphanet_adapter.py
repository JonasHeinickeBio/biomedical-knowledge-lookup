"""Unit tests for OrphanetAdapter (Orphadata API) using trimmed real responses."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.orphanet_adapter import (
    OrphanetAdapter,
    _results,
    normalize_orphacode,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import orphanet_responses as fx

pytestmark = pytest.mark.unit


class _NotFound(Exception):
    status = 404


def _router(overrides: dict | None = None):
    """Fake ``_make_request`` answering by URL path like the Orphadata API."""
    table = {
        "/rd-cross-referencing/orphacodes/558": fx.XREF_558,
        "/rd-cross-referencing/orphacodes/names/marfan": fx.NAME_MARFAN,
        "/rd-cross-referencing/orphacodes/names/chronic fatigue": fx.NAME_CFS,
        "/rd-cross-referencing/orphacodes": fx.XREF_LIST,
        "/rd-associated-genes/orphacodes/166024": fx.GENES_166024,
        "/rd-phenotypes/orphacodes/558": fx.PHENO_558,
        "/rd-classification/orphacodes/558/hchids": fx.CLASS_558,
        "/rd-classification/orphacodes": fx.CLASS_LIST,
        "/rd-epidemiology/orphacodes/558": fx.EPI_558,
        "/rd-natural_history/orphacodes/558": fx.HISTORY_558,
    }
    table.update(overrides or {})

    async def fake(url, params=None, headers=None, json_data=None):
        path = url.removeprefix("https://api.orphadata.com")
        if path not in table:
            raise _NotFound(path)
        value = table[path]
        if isinstance(value, Exception):
            raise value
        return value

    return fake


@pytest.fixture
def adapter(lookup_config):
    return OrphanetAdapter(lookup_config)


def patched(adapter, overrides=None):
    return patch.object(adapter, "_make_request", AsyncMock(side_effect=_router(overrides)))


class TestIds:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ORPHA:558", "558"),
            ("orpha:558", "558"),
            ("Orphanet_558", "558"),
            ("Orphanet:558", "558"),
            ("ORPHAcode 558", "558"),
            ("558", "558"),
            ("ORPHA:0558", "558"),
            ("http://www.orpha.net/ORDO/Orphanet_558", "558"),
            ("marfan", None),
            ("OMIM:154700", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_orphacode(raw) == expected

    def test_results_shapes(self):
        assert _results(None) == []
        assert _results({"data": {"results": {"a": 1}}}) == [{"a": 1}]
        assert _results({"data": {"results": [{"a": 1}, "x"]}}) == [{"a": 1}]
        assert _results({"error": {"code": 404}}) == []


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ORPHANET
        assert adapter.is_available() is True


class TestSearch:
    @pytest.mark.asyncio
    async def test_name_search_ranks_exact_and_prefix_first(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("marfan syndrome", limit=10)
        ids = [c.primary_id for c in results]
        assert ids[0] == "ORPHA:558"
        assert "ORPHA:284963" in ids
        assert results[0].concept_type == ConceptType.DISEASE
        assert results[0].confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_words_any_order_and_api_best_match_added(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("chronic fatigue", limit=5)
        by_id = {c.primary_id: c for c in results}
        assert results[0].primary_id == "ORPHA:1983"  # found by the list scan
        assert "NON RARE IN EUROPE" in results[0].primary_label
        assert by_id["ORPHA:206610"].confidence_score == 0.85  # Orphadata's own best match
        assert "OBSOLETE" in by_id["ORPHA:206610"].primary_label

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, adapter):
        with patched(adapter):
            assert len(await adapter.search_concepts("marfan", limit=2)) == 2
            assert await adapter.search_concepts("marfan", limit=0) == []

    @pytest.mark.asyncio
    async def test_id_query_returns_details(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("Orphanet_558")
        assert [c.primary_id for c in results] == ["ORPHA:558"]
        assert results[0].definitions

    @pytest.mark.asyncio
    async def test_empty_unknown_and_errors(self, adapter):
        assert await adapter.search_concepts("   ") == []
        with patched(adapter):
            assert await adapter.search_concepts("zzzz nothing") == []
            assert await adapter.search_concepts("ORPHA:999999") == []
        # list endpoint down: Orphadata's own best match still answers
        fresh = OrphanetAdapter(adapter.config)
        with patched(fresh, {"/rd-cross-referencing/orphacodes": RuntimeError("down")}):
            assert [c.primary_id for c in await fresh.search_concepts("marfan")] == ["ORPHA:558"]
        # everything down
        broken = OrphanetAdapter(adapter.config)
        with patch.object(broken, "_make_request", AsyncMock(side_effect=RuntimeError("down"))):
            assert await broken.search_concepts("marfan") == []
        with patch.object(broken, "_ensure_names", AsyncMock(side_effect=ValueError("x"))):
            assert await broken.search_concepts("marfan") == []

    @pytest.mark.asyncio
    async def test_failed_name_list_is_not_cached(self, adapter):
        with patched(adapter, {"/rd-cross-referencing/orphacodes": RuntimeError("down")}):
            assert await adapter._ensure_names() == {}
        assert adapter._names is None
        with patched(adapter):
            assert "558" in await adapter._ensure_names()


class TestDetails:
    @pytest.mark.asyncio
    async def test_marfan_details(self, adapter):
        with patched(adapter):
            concept = await adapter.get_concept_details("ORPHA:558")
        assert concept.primary_id == "ORPHA:558"
        assert concept.primary_label == "Marfan syndrome"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.synonyms == ["MFS"]
        assert concept.definitions[0].startswith("Marfan syndrome is a systemic disease")
        assert "Disease" in concept.categories and "Disorder" in concept.categories
        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert (KnowledgeSource.MONDO, "MONDO:0007947") in ids
        assert (KnowledgeSource.UMLS, "C0024796") in ids
        assert (KnowledgeSource.OMIM, "OMIM:154700") in ids
        assert (KnowledgeSource.MESH, "D008382") in ids
        assert "ORPHA:519292" in concept.parents and "ORPHA:284963" in concept.children
        data = concept.source_data[KnowledgeSource.ORPHANET]
        assert data["url"].endswith("/558")
        assert data["type_of_inheritance"] == ["Autosomal dominant"]
        assert data["average_age_of_onset"] == ["All ages"]
        assert len(data["prevalence"]) == 2

    @pytest.mark.asyncio
    async def test_flags_become_categories(self, adapter):
        record = copy.deepcopy(fx.XREF_558)
        record["data"]["results"]["DisorderFlag"] = [{"Label": "Obsolete entity", "Value": 16}]
        with patched(adapter, {"/rd-cross-referencing/orphacodes/558": record}):
            concept = await adapter.get_concept_details("558")
        assert "obsolete entity" in concept.categories

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        with patched(adapter):
            assert await adapter.get_concept_details("ORPHA:999999") is None
            assert await adapter.get_concept_details("not an id") is None
        with patched(adapter, {"/rd-cross-referencing/orphacodes/558": RuntimeError("x")}):
            assert await adapter.get_concept_details("558") is None

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_none(self, adapter):
        with patch.object(adapter, "_get", AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.get_concept_details("558") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_phenotypes_with_frequency(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("ORPHA:558")
        pheno = [r for r in rels if r["relation_label"] == "has_phenotype"]
        assert [r["related_id"] for r in pheno][:3] == ["HP:0000768", "HP:0001065", "HP:0001166"]
        assert pheno[0]["related_name"] == "Pectus carinatum"
        assert pheno[0]["frequency_term"] == "HP:0040281"
        assert pheno[0]["frequency_label"] == "Very frequent"
        assert pheno[0]["frequency_raw"] == "Very frequent (99-80%)"
        assert pheno[0]["frequency"] == 0.9
        assert pheno[0]["diagnostic_criteria"] == "Diagnostic criterion"
        assert pheno[0]["references"][0] == "30726024"
        assert pheno[-1]["related_id"] == "HP:0000023"  # Occasional comes last
        assert all(r["source"] == "ORPHANET" for r in rels)

    @pytest.mark.asyncio
    async def test_excluded_phenotype_is_negated(self, adapter):
        pheno = copy.deepcopy(fx.PHENO_558)
        pheno["data"]["results"]["Disorder"]["HPODisorderAssociation"][0]["HPOFrequency"] = (
            "Excluded (0%)"
        )
        with patched(adapter, {"/rd-phenotypes/orphacodes/558": pheno}):
            rels = await adapter.get_relationships("558")
        pheno_edges = [r for r in rels if r["relation_label"].endswith("has_phenotype")]
        assert pheno_edges[-1]["relation_label"] == "not_has_phenotype"
        assert pheno_edges[-1]["frequency"] == 0.0

    @pytest.mark.asyncio
    async def test_classification_parents_and_children_with_labels(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("558")
        parents = {r["related_id"]: r for r in rels if r["relation_label"] == "subclass_of"}
        children = {r["related_id"]: r for r in rels if r["relation_label"] == "has_subclass"}
        assert parents["ORPHA:519292"]["related_name"] == "Syndromic ectopia lentis"
        assert any("rare developmental" in t for t in parents["ORPHA:519292"]["classifications"])
        assert children["ORPHA:284963"]["related_name"] == "Marfan syndrome type 1"
        assert set(children) == {"ORPHA:284963", "ORPHA:284973"}

    @pytest.mark.asyncio
    async def test_genes(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("ORPHA:166024")
        genes = [r for r in rels if r["relation_label"] == "associated_with"]
        assert len(genes) == 1
        gene = genes[0]
        assert gene["related_id"] == "HGNC:30497" and gene["related_name"] == "KIF7"
        assert gene["association_type"] == "Disease-causing germline mutation(s) in"
        assert gene["association_status"] == "Assessed"
        assert gene["references"] == ["22587682"]
        assert gene["ensembl"] == "ENSG00000166813" and gene["locus"] == "15q26.1"
        assert gene["omim_gene"] == "611254" and gene["uniprot"] == "Q2M1P5"

    @pytest.mark.asyncio
    async def test_gene_without_hgnc_falls_back_to_symbol_and_dedupes(self, adapter):
        genes = copy.deepcopy(fx.GENES_166024)
        assoc = genes["data"]["results"]["DisorderGeneAssociation"]
        assoc[0]["Gene"]["ExternalReference"] = []
        assoc.append(copy.deepcopy(assoc[0]))
        with patched(adapter, {"/rd-associated-genes/orphacodes/166024": genes}):
            rels = await adapter.get_relationships("166024")
        genes_only = [r for r in rels if r["relation_label"] == "associated_with"]
        assert [r["related_id"] for r in genes_only] == ["KIF7"]

    @pytest.mark.asyncio
    async def test_limit_per_kind_and_invalid(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("558", limit=2)
            assert len([r for r in rels if r["relation_label"] == "has_phenotype"]) == 2
            assert len([r for r in rels if r["relation_label"] == "subclass_of"]) == 2
            assert await adapter.get_relationships("558", limit=0) == []
            assert await adapter.get_relationships("nope") == []
            assert await adapter.get_relationships("ORPHA:999999") == []

    @pytest.mark.asyncio
    async def test_unlabelled_class_node_has_no_name(self, adapter):
        classes = copy.deepcopy(fx.CLASS_558)
        classes["data"]["results"][0]["parents"] = [424242]
        with patched(adapter, {"/rd-classification/orphacodes/558/hchids": classes}):
            rels = await adapter.get_relationships("558")
        assert next(r for r in rels if r["related_id"] == "ORPHA:424242")["related_name"] is None

    @pytest.mark.asyncio
    async def test_errors_return_empty(self, adapter):
        with patch.object(adapter, "_get", AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.get_relationships("558") == []

    @pytest.mark.asyncio
    async def test_failed_class_list_is_retried(self, adapter):
        with patched(adapter, {"/rd-classification/orphacodes": RuntimeError("x")}):
            labels = await adapter._label_for({"519292"})
        assert labels == {"519292": ""}
        assert adapter._class_names is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        with patched(adapter):
            maps = await adapter.get_mappings("ORPHA:558")
        by_to = {m["toId"]: m for m in maps}
        assert by_to["ICD10:Q87.4"]["mappingType"] == "exactMatch"
        assert by_to["ICD11:LD28.01"]["toSource"] == "ICD11"
        assert by_to["MONDO:0007947"]["confidence"] == 1.0
        assert by_to["MESH:D008382"]["fromSource"] == "ORPHANET"
        assert by_to["MEDDRA:10026829"]["fromId"] == "ORPHA:558"
        assert by_to["UMLS:C0024796"]["relation"].startswith("E (")
        assert by_to["OMIM:154700"]["mappingType"] == "narrowMatch"  # ORPHA broader than OMIM
        assert by_to["OMIM:610168"]["mappingType"] == "broadMatch"
        assert {m["fromId"] for m in maps} == {"ORPHA:558"}

    @pytest.mark.asyncio
    async def test_unvalidated_unknown_gets_lower_confidence(self, adapter):
        record = copy.deepcopy(fx.XREF_558)
        refs = record["data"]["results"]["ExternalReference"]
        refs[0]["DisorderMappingValidationStatus"] = "Not yet validated"
        refs[1]["DisorderMappingRelation"] = "WEIRD (?)"
        refs.append({**refs[0]})  # duplicate is dropped
        refs.append({"Source": "Unknown", "Reference": "1"})  # unsupported source is skipped
        with patched(adapter, {"/rd-cross-referencing/orphacodes/558": record}):
            maps = await adapter.get_mappings("558")
        by_to = {m["toId"]: m for m in maps}
        assert by_to["ICD10:Q87.4"]["confidence"] == 0.6
        assert by_to["ICD11:LD28.01"]["mappingType"] == "relatedMatch"
        assert len(maps) == len(refs) - 2

    @pytest.mark.asyncio
    async def test_empty_invalid_and_errors(self, adapter):
        with patched(adapter):
            assert await adapter.get_mappings("ORPHA:999999") == []
            assert await adapter.get_mappings("zzz") == []
        with patch.object(adapter, "_get", AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.get_mappings("558") == []


class TestHttp:
    @pytest.mark.asyncio
    async def test_get_swallows_404_and_errors(self, adapter):
        with patched(adapter, {"/x": _NotFound("x")}):
            assert await adapter._get("/x") is None
        with patched(adapter, {"/x": RuntimeError("down")}):
            assert await adapter._get("/x") is None
