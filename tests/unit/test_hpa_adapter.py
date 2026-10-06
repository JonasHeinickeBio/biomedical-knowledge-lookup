"""Unit tests for HumanProteinAtlasAdapter (real HPA responses recorded live, no network)."""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.hpa_adapter import HumanProteinAtlasAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures.hpa_responses import (
    DETAIL_ALB,
    DETAIL_BRCA1,
    DETAIL_CD4,
    SEARCH_BRCA1,
    SEARCH_CD4,
    SEARCH_IL6,
    SUMMARY_CD4_BY_ENSG,
)

pytestmark = pytest.mark.unit

CD4 = "ENSG00000010610"
ALB = "ENSG00000163631"
BRCA1 = "ENSG00000012048"

RESPONSES = {
    ("IL6", "summary"): SEARCH_IL6,
    ("BRCA1", "summary"): SEARCH_BRCA1,
    ("CD4", "summary"): SEARCH_CD4,
    (CD4, "summary"): SUMMARY_CD4_BY_ENSG,
    (CD4, "detail"): DETAIL_CD4,
    (ALB, "detail"): DETAIL_ALB,
    (BRCA1, "detail"): DETAIL_BRCA1,
    (BRCA1, "summary"): SEARCH_BRCA1[:1],
}


def fake_request(responses=None):
    table = RESPONSES if responses is None else responses

    async def _request(url, params=None, headers=None, json_data=None):
        kind = "detail" if "t_RNA_liver" in params["columns"] else "summary"
        search = params["search"]
        # the real endpoint matches case-insensitively
        return table.get((search, kind)) or table.get((search.upper(), kind), [])

    return AsyncMock(side_effect=_request)


@pytest.fixture
def adapter():
    instance = HumanProteinAtlasAdapter(LookupConfig())
    instance.clear_cache()
    with patch.object(instance, "_make_request", fake_request()) as mock:
        instance.request_mock = mock
        yield instance
    instance.clear_cache()


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.HUMANPROTEINATLAS
        assert adapter.is_available() is True

    @pytest.mark.asyncio
    async def test_request_shape(self, adapter):
        await adapter.search_concepts("IL6")
        (call,) = adapter.request_mock.call_args_list
        assert call.args[0] == "https://www.proteinatlas.org/api/search_download.php"
        params = call.kwargs["params"]
        assert params["search"] == "IL6" and params["format"] == "json"
        assert params["compress"] == "no"
        assert "rnatsm" in params["columns"] and "t_RNA_liver" not in params["columns"]

    @pytest.mark.asyncio
    async def test_detail_request_uses_tissue_and_blood_columns(self, adapter):
        await adapter.get_concept_details(CD4)
        columns = adapter.request_mock.call_args.kwargs["params"]["columns"].split(",")
        assert "t_RNA_liver" in columns and "blood_RNA_classical_monocyte" in columns
        assert "t_RNA_skin_1" in columns and "blood_RNA_total_PBMC" in columns


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_gene_symbol(self, adapter):
        results = await adapter.search_concepts("IL6")
        assert results[0].primary_id == "ENSG00000136244"
        assert results[0].primary_label == "IL6"
        assert results[0].concept_type == ConceptType.GENE
        assert results[0].confidence_score == 1.0
        assert results[1].confidence_score == 0.6
        assert [c.primary_label for c in results][:3] == ["IL6", "IL6R", "IL6ST"]

    @pytest.mark.asyncio
    async def test_search_summary_fields(self, adapter):
        (il6, *_rest) = await adapter.search_concepts("IL6")
        data = il6.source_data[KnowledgeSource.HUMANPROTEINATLAS]
        assert data["description"] == "Interleukin 6"
        assert data["uniprot"] == ["P05231"]
        assert data["rna_blood_cell_specificity"] == "Group enriched"
        assert "top_tissues_ntpm" not in data  # summary columns carry no per-tissue table
        assert "BSF2" in il6.synonyms and "IL6" in il6.synonyms
        assert il6.definitions == ["Interleukin 6"]

    @pytest.mark.asyncio
    async def test_exact_symbol_is_ranked_first(self, adapter):
        # HPA lists CD40LG-type free-text hits first for some queries; the exact symbol wins
        reordered = list(reversed(SEARCH_CD4))
        with patch.object(adapter, "_make_request", fake_request({("CD4", "summary"): reordered})):
            results = await adapter.search_concepts("CD4")
        assert results[0].primary_label == "CD4"

    @pytest.mark.asyncio
    async def test_synonym_rank(self, adapter):
        record = {**SEARCH_IL6[0], "Gene": "ZZZ1", "Ensembl": "ENSG00000000001"}
        table = {("BSF2", "summary"): [record, SEARCH_IL6[1]]}
        with patch.object(adapter, "_make_request", fake_request(table)):
            results = await adapter.search_concepts("BSF2")
        assert results[0].confidence_score == 0.9  # exact synonym of the ZZZ1 stand-in record

    @pytest.mark.asyncio
    async def test_limit_dedupe_and_empty(self, adapter):
        assert len(await adapter.search_concepts("IL6", limit=2)) == 2
        assert await adapter.search_concepts("IL6", limit=0) == []
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts("nosuchgene") == []
        table = {("dup", "summary"): [SEARCH_IL6[0], SEARCH_IL6[0], {"Gene": "X"}]}
        with patch.object(adapter, "_make_request", fake_request(table)):
            assert len(await adapter.search_concepts("dup")) == 1

    @pytest.mark.asyncio
    async def test_search_never_raises(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("down"))):
            assert await adapter.search_concepts("BRCA1") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_cd4_summary(self, adapter):
        concept = await adapter.get_concept_details(CD4)
        assert concept.primary_id == CD4 and concept.primary_label == "CD4"
        assert concept.concept_type == ConceptType.GENE
        assert concept.confidence_score == 1.0
        assert concept.get_identifier(KnowledgeSource.ENSEMBL).identifier == CD4
        assert concept.get_identifier(KnowledgeSource.UNIPROT).identifier == "P01730"
        data = concept.source_data[KnowledgeSource.HUMANPROTEINATLAS]
        assert data["rna_tissue_specificity"] == "Tissue enhanced"
        assert data["rna_tissue_enriched_ntpm"] == {
            "liver": 143.1,
            "lymphoid tissue": 204.2,
            "parathyroid gland": 163.6,
        }
        assert data["top_tissues_ntpm"][0] == {"name": "thymus", "ntpm": 204.2}
        assert [t["name"] for t in data["top_tissues_ntpm"]][:3] == [
            "thymus",
            "parathyroid gland",
            "spleen",
        ]
        top_cells = data["top_blood_cells_ntpm"]
        assert top_cells[0] == {"name": "plasmacytoid DC", "ntpm": 264.3}
        assert all(c["name"] != "total PBMC" for c in top_cells)
        assert data["rna_blood_cell_specificity"] == "Group enriched"
        assert data["subcellular_location"] == ["Plasma membrane"]
        assert data["plasma_protein"] is False
        assert "CD markers" in concept.categories
        assert "blood_concentration_pg_per_l" not in data

    @pytest.mark.asyncio
    async def test_plasma_protein_and_blood_concentration(self, adapter):
        concept = await adapter.get_concept_details(ALB)
        data = concept.source_data[KnowledgeSource.HUMANPROTEINATLAS]
        assert data["plasma_protein"] is True
        assert data["secretome_location"] == "Secreted to blood"
        assert data["blood_concentration_pg_per_l"] == {"immunoassay": 40000000000000}
        assert data["rna_tissue_enriched_ntpm"] == {"liver": 198523.8}
        assert data["rna_blood_cell_specificity"] == "Not detected in immune cells"
        assert data["rna_blood_cell_enriched_ntpm"] == {}

    @pytest.mark.asyncio
    async def test_tissue_suffix_is_tidied(self, adapter):
        concept = await adapter.get_concept_details(CD4)
        names = {
            t["name"]
            for t in concept.source_data[KnowledgeSource.HUMANPROTEINATLAS]["top_tissues_ntpm"]
        }
        assert not any(n.endswith(" 1") for n in names)
        tissues, _cells = HumanProteinAtlasAdapter._tables(DETAIL_CD4[0])
        assert "skin" in tissues and "stomach" in tissues and "endometrium" in tissues
        assert "skin 1" not in tissues

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "concept_id",
        [CD4, CD4.lower(), f"{CD4}.12", f"HPA:{CD4}", f"ENSEMBL:{CD4}", "CD4", "cd4"],
    )
    async def test_id_forms(self, adapter, concept_id):
        concept = await adapter.get_concept_details(concept_id)
        assert concept is not None and concept.primary_id == CD4

    @pytest.mark.asyncio
    async def test_symbol_resolution_uses_summary_search_then_ensg(self, adapter):
        await adapter.get_concept_details("CD4")
        searches = [c.kwargs["params"]["search"] for c in adapter.request_mock.call_args_list]
        assert searches == ["CD4", CD4]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("concept_id", ["", "  ", "NOSUCHGENE", "ENSG00000999999", "HPA:"])
    async def test_unknown_ids(self, adapter, concept_id):
        assert await adapter.get_concept_details(concept_id) is None
        assert await adapter.get_relationships(concept_id) == []
        assert await adapter.get_mappings(concept_id) == []

    @pytest.mark.asyncio
    async def test_non_matching_symbol_is_not_guessed(self, adapter):
        # free text finds IL6R, IL6ST... for "IL6"; "IL" must not resolve to any of them
        table = {("IL", "summary"): SEARCH_IL6}
        with patch.object(adapter, "_make_request", fake_request(table)):
            assert await adapter.get_concept_details("IL") is None

    @pytest.mark.asyncio
    async def test_details_never_raise(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("down"))):
            assert await adapter.get_concept_details(CD4) is None
            assert await adapter.get_relationships(CD4) == []
            assert await adapter.get_mappings(CD4) == []

    @pytest.mark.asyncio
    async def test_malformed_response_is_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"error": "x"})):
            assert await adapter.get_concept_details(CD4) is None

    @pytest.mark.asyncio
    async def test_record_without_symbol(self, adapter):
        assert adapter._build_concept({"Ensembl": CD4}) is None

    @pytest.mark.asyncio
    async def test_responses_are_cached(self, adapter):
        await adapter.get_concept_details(CD4)
        await adapter.get_relationships(CD4)
        assert adapter.request_mock.await_count == 1


class TestRelationships:
    @pytest.mark.asyncio
    async def test_tissues_enriched_first(self, adapter):
        edges = await adapter.get_relationships(CD4, limit=5)
        tissue_edges = [e for e in edges if e["relation_label"] == "expressed_in"]
        assert len(tissue_edges) == 5
        assert [(e["related_name"], e["enriched"]) for e in tissue_edges[:3]] == [
            ("lymphoid tissue", True),
            ("parathyroid gland", True),
            ("liver", True),
        ]
        lymphoid = tissue_edges[0]
        assert lymphoid["ntpm"] == 204.2
        assert lymphoid["scope"] == "tissue group"  # an HPA tissue group, not a single tissue
        assert tissue_edges[2].get("scope") is None
        # remaining slots: highest-expressed non-enriched tissues
        assert [e["related_name"] for e in tissue_edges[3:]] == ["thymus", "spleen"]
        assert all(e["enriched"] is False for e in tissue_edges[3:])
        for e in tissue_edges:
            assert e["source"] == "HUMANPROTEINATLAS"
            assert e["related_type"] == "tissue"
            assert e["specificity"] == "Tissue enhanced"
            assert e["related_id"] == e["related_name"]

    @pytest.mark.asyncio
    async def test_immune_cell_edges(self, adapter):
        edges = await adapter.get_relationships(CD4, limit=20)
        cells = [e for e in edges if e["relation_label"] == "expressed_in_cell_type"]
        enriched = [e["related_name"] for e in cells if e["enriched"]]
        assert enriched[0] == "plasmacytoid DC"
        assert set(enriched) == {
            "plasmacytoid DC",
            "classical monocyte",
            "intermediate monocyte",
            "non-classical monocyte",
            "myeloid DC",
            "T-reg",
            "memory CD4 T-cell",
            "naive CD4 T-cell",
        }
        assert all(e["related_type"] == "immune cell (blood)" for e in cells)
        assert all(e["specificity"] == "Group enriched" for e in cells)
        names = [e["related_name"] for e in cells]
        assert "total PBMC" not in names
        # non-enriched cells are only listed when they clear the nTPM >= 1 floor
        assert "memory B-cell" not in names  # 0.5 nTPM
        assert "neutrophil" in names  # 11.1 nTPM, not enriched
        assert next(e for e in cells if e["related_name"] == "neutrophil")["enriched"] is False

    @pytest.mark.asyncio
    async def test_limit_is_per_relation_type(self, adapter):
        edges = await adapter.get_relationships(CD4, limit=2)
        assert sorted(e["relation_label"] for e in edges) == [
            "expressed_in",
            "expressed_in",
            "expressed_in_cell_type",
            "expressed_in_cell_type",
        ]
        assert await adapter.get_relationships(CD4, limit=0) == []

    @pytest.mark.asyncio
    async def test_broadly_expressed_gene_has_no_enriched_flags(self, adapter):
        edges = await adapter.get_relationships(BRCA1, limit=3)
        tissue_edges = [e for e in edges if e["relation_label"] == "expressed_in"]
        assert tissue_edges and not any(e["enriched"] for e in tissue_edges)
        assert tissue_edges[0]["specificity"] == "Low tissue specificity"
        ntpms = [e["ntpm"] for e in tissue_edges]
        assert ntpms == sorted(ntpms, reverse=True)

    @pytest.mark.asyncio
    async def test_blood_free_gene_has_no_cell_edges(self, adapter):
        edges = await adapter.get_relationships(ALB)
        assert [e for e in edges if e["relation_label"] == "expressed_in_cell_type"] == []
        liver = next(e for e in edges if e["related_name"] == "liver")
        assert liver["enriched"] is True and liver["ntpm"] == 198523.8


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        mappings = await adapter.get_mappings(CD4)
        by_target = {(m["toSource"], m["toId"]): m for m in mappings}
        assert ("ENSEMBL", CD4) in by_target
        assert by_target[("UNIPROT", "P01730")]["mappingType"] == "xref"
        hgnc = by_target[("HGNC", "CD4")]
        assert hgnc["mappingType"] == "symbol" and hgnc["confidence"] == 0.95
        for m in mappings:
            assert m["fromId"] == CD4 and m["fromSource"] == "HUMANPROTEINATLAS"
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }

    @pytest.mark.asyncio
    async def test_mappings_by_symbol_use_light_columns_only(self, adapter):
        await adapter.get_mappings("BRCA1")
        for call in adapter.request_mock.call_args_list:
            assert "t_RNA_liver" not in call.kwargs["params"]["columns"]

    @pytest.mark.asyncio
    async def test_mapping_for_unknown_record(self, adapter):
        with patch.object(adapter, "_make_request", fake_request({})):
            assert await adapter.get_mappings(CD4) == []
