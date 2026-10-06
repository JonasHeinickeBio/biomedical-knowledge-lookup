"""
Unit tests for MyGeneInfoAdapter (responses in tests/fixtures/mygeneinfo_responses.py are
trimmed live MyGene.info v3 payloads).
"""

import copy
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from fixtures.mygeneinfo_responses import (
    BRCA1_GENE,
    CRP_GENE,
    IL6_GENE,
    ORTHOLOG_SYMBOLS,
    REACTOME_GENE,
    SEARCH_BRCA1,
    SEARCH_EMPTY,
    TNF_GENE,
)

from knowledge_lookup.adapters.mygeneinfo_adapter import MyGeneInfoAdapter, _as_list
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


def _not_found() -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=None, history=(), status=404)  # type: ignore[arg-type]


@pytest.fixture
def adapter(lookup_config):
    return MyGeneInfoAdapter(lookup_config)


def _hits(*hits):
    return {"took": 1, "total": len(hits), "hits": list(hits)}


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.MYGENEINFO
        assert adapter.source == KnowledgeSource.MYGENEINFO
        assert adapter.is_available() is True

    def test_rate_limit_custom(self):
        config = LookupConfig(rate_limits={KnowledgeSource.MYGENEINFO: 5.0})
        assert MyGeneInfoAdapter(config).get_rate_limit() == 5.0

    def test_as_list(self):
        assert _as_list(None) == []
        assert _as_list("") == []
        assert _as_list("x") == ["x"]
        assert _as_list(["x", "y"]) == ["x", "y"]


class TestSearch:
    @pytest.mark.asyncio
    async def test_symbol_search(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = SEARCH_BRCA1
            concepts = await adapter.search_concepts("BRCA1", limit=3)
        assert [c.primary_id for c in concepts][0] == "NCBIGene:672"
        assert concepts[0].primary_label == "BRCA1"
        assert concepts[0].concept_type == ConceptType.GENE
        assert concepts[0].confidence_score == 0.9
        url, params = req.call_args.args
        assert url.endswith("/query")
        assert params["q"] == "BRCA1" and params["species"] == "human" and params["size"] == 3

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = SEARCH_BRCA1
            concepts = await adapter.search_concepts("BRCA1", limit=1)
        assert len(concepts) == 1

    @pytest.mark.asyncio
    async def test_empty_and_invalid_input(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = SEARCH_EMPTY
            assert await adapter.search_concepts("zzzzqqq") == []
            assert await adapter.search_concepts("   ") == []
            assert await adapter.search_concepts("BRCA1", limit=0) == []
            assert req.await_count == 1

    @pytest.mark.asyncio
    async def test_hit_without_symbol_is_skipped(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = _hits({"_id": "1"}, {"_id": "672", "symbol": "BRCA1"})
            concepts = await adapter.search_concepts("BRCA1")
        assert [c.primary_label for c in concepts] == ["BRCA1"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", ["672", "NCBIGene:672", "ENSG00000012048"])
    async def test_numeric_and_ensembl_queries_use_gene_endpoint(self, adapter, query):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = BRCA1_GENE
            concepts = await adapter.search_concepts(query)
        assert concepts[0].primary_id == "NCBIGene:672"
        assert req.call_args.args[0].rsplit("/", 1)[-1] in {"672", "ENSG00000012048"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("query", "expected"),
        [("HGNC:1100", "HGNC:1100"), ("P38398", "uniprot:P38398")],
    )
    async def test_hgnc_and_uniprot_queries_are_scoped(self, adapter, query, expected):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = _hits(BRCA1_GENE)
            concepts = await adapter.search_concepts(query)
        assert concepts[0].primary_id == "NCBIGene:672"
        assert req.call_args.args[1]["q"] == expected

    @pytest.mark.asyncio
    async def test_unknown_numeric_id_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = _not_found()
            assert await adapter.search_concepts("99999999999") == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = RuntimeError("boom")
            assert await adapter.search_concepts("BRCA1") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_brca1_details(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = BRCA1_GENE
            concept = await adapter.get_concept_details("NCBIGene:672")
        assert concept.primary_id == "NCBIGene:672"
        assert concept.primary_label == "BRCA1"
        assert concept.concept_type == ConceptType.GENE
        assert concept.confidence_score == 1.0
        assert concept.synonyms[0] == "BRCA1 DNA repair associated"
        assert "FANCS" in concept.synonyms
        assert "RING finger protein 53" in concept.synonyms
        assert concept.definitions[0].startswith("This gene encodes")
        assert "locus:17q21.31" in concept.categories
        assert "taxon:9606" in concept.categories
        assert concept.semantic_types == ["protein-coding"]
        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ("NCBI", "672") in ids
        assert ("ENSEMBL", "ENSG00000012048") in ids
        assert ("HGNC", "HGNC:1100") in ids
        assert ("UNIPROT", "P38398") in ids
        assert ("OMIM", "113705") in ids
        assert concept.source_data[KnowledgeSource.MYGENEINFO]["symbol"] == "BRCA1"
        assert req.call_args.args[0].endswith("/gene/672")

    @pytest.mark.asyncio
    async def test_single_value_shapes(self, adapter):
        """CRP: alias is a plain string, pathway entries are dicts."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = CRP_GENE
            concept = await adapter.get_concept_details("1401")
        assert "PTX1" in concept.synonyms

    @pytest.mark.asyncio
    async def test_multi_locus_ensembl_list(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = TNF_GENE
            concept = await adapter.get_concept_details("7124")
        ensembl = [i.identifier for i in concept.identifiers if i.source == "ENSEMBL"]
        assert ensembl[:2] == ["ENSG00000228849", "ENSG00000223952"]
        assert len(ensembl) == 3

    @pytest.mark.asyncio
    async def test_symbol_resolution_prefers_exact_symbol(self, adapter):
        decoy = {"_id": "1", "symbol": "IL6-AS1", "entrezgene": "1"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = _hits(decoy, IL6_GENE | {"symbol": "IL6"})
            concept = await adapter.get_concept_details("il6")
        assert concept.primary_label == "IL6"
        assert req.call_args.args[1]["q"] == 'symbol:"il6" OR alias:"il6"'

    @pytest.mark.asyncio
    async def test_alias_resolution_falls_back_to_first_hit(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = _hits(BRCA1_GENE)
            concept = await adapter.get_concept_details("RNF53")
        assert concept.primary_label == "BRCA1"

    @pytest.mark.asyncio
    async def test_unknown_or_empty_returns_none(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = SEARCH_EMPTY
            assert await adapter.get_concept_details("zzzzqqq") is None
            assert await adapter.get_concept_details("") is None
            req.side_effect = _not_found()
            assert await adapter.get_concept_details("99999999999") is None

    @pytest.mark.asyncio
    async def test_server_error_returns_none(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_concept_details("672") is None

    @pytest.mark.asyncio
    async def test_ensembl_id_mapping_to_several_genes(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = [BRCA1_GENE, CRP_GENE]
            concept = await adapter.get_concept_details("ENSG00000012048.5")
        assert concept.primary_id == "NCBIGene:672"
        assert req.call_args.args[0].endswith("/gene/ENSG00000012048")

    @pytest.mark.asyncio
    async def test_gene_endpoint_without_id_is_not_found(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = {"success": False}
            assert await adapter.get_concept_details("672") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_pathways_and_orthologs(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [BRCA1_GENE, ORTHOLOG_SYMBOLS]
            rels = await adapter.get_relationships("NCBIGene:672")
        pathways = [r for r in rels if r["relation_label"] == "participates_in"]
        orthologs = [r for r in rels if r["relation_label"] == "ortholog"]
        # BRCA1 fixture: 3 WikiPathways + 3 KEGG + 3 PID + 2 NetPath + 3 BioCarta
        assert len(pathways) == 14
        assert [p["pathway_db"] for p in pathways[:4]] == ["WikiPathways"] * 3 + ["KEGG"]
        wp = pathways[0]
        assert wp["related_id"] == "WP138"
        assert wp["related_name"] == "Androgen receptor signaling pathway"
        assert wp["source"] == "MyGeneInfo"
        assert wp["url"] == "https://www.wikipathways.org/pathways/WP138.html"
        assert "url" not in next(p for p in pathways if p["pathway_db"] == "PID")
        # 7 orthologs besides the human gene; 4 symbols came back from the batch query
        assert len(orthologs) == 7
        mouse = next(o for o in orthologs if o["related_id"] == "NCBIGene:12189")
        assert mouse["related_name"] == "Brca1" and mouse["species"] == "Mus musculus"
        assert mouse["taxid"] == 10090
        dog = next(o for o in orthologs if o["species"] == "Canis lupus familiaris")
        assert dog["related_name"] == dog["related_id"] == "NCBIGene:403437"
        assert all(o["related_id"] != "NCBIGene:672" for o in orthologs)

    @pytest.mark.asyncio
    async def test_limit_caps_pathways(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [BRCA1_GENE, ORTHOLOG_SYMBOLS]
            rels = await adapter.get_relationships("672", limit=2)
        assert len([r for r in rels if r["relation_label"] == "participates_in"]) == 2
        assert await adapter.get_relationships("672", limit=0) == []

    @pytest.mark.asyncio
    async def test_single_dict_pathway_entries(self, adapter):
        gene = copy.deepcopy(CRP_GENE)
        gene.pop("homologene", None)
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = gene
            rels = await adapter.get_relationships("1401")
        names = {r["related_name"] for r in rels}
        assert {"Leptin", "IL6-mediated signaling events"} <= names
        assert {r["pathway_db"] for r in rels} >= {"NetPath", "PID", "WikiPathways"}

    @pytest.mark.asyncio
    async def test_reactome_edges_come_first(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = REACTOME_GENE
            rels = await adapter.get_relationships("100131439")
        assert rels[0]["related_id"] == "R-HSA-1280218"
        assert rels[0]["pathway_db"] == "Reactome"
        assert rels[0]["url"] == "https://reactome.org/content/detail/R-HSA-1280218"

    @pytest.mark.asyncio
    async def test_duplicate_and_malformed_pathway_entries(self, adapter):
        gene = {
            "_id": "1",
            "pathway": {
                "kegg": [{"id": "hsa1", "name": "A"}, {"id": "hsa1", "name": "A"}, "oops", {}],
            },
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = gene
            rels = await adapter.get_relationships("1")
        assert [r["related_id"] for r in rels] == ["hsa1"]

    @pytest.mark.asyncio
    async def test_ortholog_symbol_failure_keeps_edges(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [BRCA1_GENE, RuntimeError("boom")]
            rels = await adapter.get_relationships("672")
        orthologs = [r for r in rels if r["relation_label"] == "ortholog"]
        assert len(orthologs) == 7
        assert all(o["related_name"] == o["related_id"] for o in orthologs)

    @pytest.mark.asyncio
    async def test_gene_without_pathways_or_homologs(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = {"_id": "5", "symbol": "X", "pathway": "bad"}
            assert await adapter.get_relationships("5") == []

    @pytest.mark.asyncio
    async def test_errors_and_unknown(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_relationships("672") == []
            req.side_effect = _not_found()
            assert await adapter.get_relationships("99999999999") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_cross_references(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = _hits(BRCA1_GENE)
            mappings = await adapter.get_mappings("BRCA1")
        by_target = {(m["toSource"], m["toId"]): m for m in mappings}
        assert by_target[("Ensembl", "ENSG00000012048")]["mappingType"] == "exact"
        assert ("HGNC", "HGNC:1100") in by_target
        assert ("UniProt", "P38398") in by_target
        assert ("OMIM", "OMIM:113705") in by_target
        assert ("PharmGKB", "PA25411") in by_target
        assert by_target[("PDB", "1JM7")]["mappingType"] == "related"
        # Only the first 10 unreviewed UniProt entries and 10 PDB entries are returned
        trembl = [
            m for m in mappings if m["toSource"] == "UniProt" and m["mappingType"] == "related"
        ]
        assert len(trembl) == 10
        assert len([m for m in mappings if m["toSource"] == "PDB"]) == 10
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "NCBIGene:672" and m["fromSource"] == "MyGeneInfo"

    @pytest.mark.asyncio
    async def test_single_value_swissprot_and_multi_ensembl(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = TNF_GENE
            mappings = await adapter.get_mappings("7124")
        assert len([m for m in mappings if m["toSource"] == "Ensembl"]) == 3

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = SEARCH_EMPTY
            assert await adapter.get_mappings("zzzz") == []
            assert await adapter.get_mappings("") == []
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_mappings("672") == []


class TestConversionEdgeCases:
    def test_incomplete_record_returns_none(self, adapter):
        assert adapter._convert_gene_to_concept({"_id": "1"}) is None
        assert adapter._convert_gene_to_concept({"symbol": "X"}) is None

    def test_converter_swallows_bad_input(self, adapter):
        assert (
            adapter._convert_gene_to_concept({"_id": "1", "symbol": "X", "uniprot": []})
            is not None
        )
        assert (
            adapter._convert_gene_to_concept({"_id": "1", "symbol": "X", "alias": [{}]})
            is not None
        )
        assert adapter._convert_gene_to_concept(None) is None  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_custom_species(self, lookup_config):
        adapter = MyGeneInfoAdapter(lookup_config, species="mouse")
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = SEARCH_EMPTY
            await adapter.search_concepts("Brca1")
        assert req.call_args.args[1]["species"] == "mouse"
