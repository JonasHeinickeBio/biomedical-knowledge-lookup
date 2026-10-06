"""Unit tests for DGIdbAdapter (fixtures are real, trimmed DGIdb v5 GraphQL responses)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.dgidb_adapter import DGIdbAdapter, _normalize_concept_id
from knowledge_lookup.models import KnowledgeSource
from tests.fixtures import dgidb_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter(lookup_config):
    return DGIdbAdapter(lookup_config)


def mock_gql(*responses):
    return patch.object(DGIdbAdapter, "_make_request", AsyncMock(side_effect=list(responses)))


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.DGIDB
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("HGNC:1100", "hgnc:1100"),
            ("hgnc:1100", "hgnc:1100"),
            ("RXCUI:1191", "rxcui:1191"),
            ("chembl:CHEMBL1703", "chembl:CHEMBL1703"),
            ("DGIDB:hgnc:1100", "hgnc:1100"),
            ("BRCA1", None),
            ("aspirin", None),
            ("hgnc:", None),
            ("", None),
        ],
    )
    def test_normalize_concept_id(self, raw, expected):
        assert _normalize_concept_id(raw) == expected

    @pytest.mark.asyncio
    async def test_gql_posts_json_with_variables(self, adapter):
        with mock_gql(fx.SEARCH_GENE_BRCA1) as mock:
            await adapter.search_concepts("BRCA1")
        kwargs = mock.call_args.kwargs
        assert mock.call_args.args[0] == "https://dgidb.org/api/graphql"
        assert kwargs["json_data"]["variables"] == {"v": ["BRCA1"]}
        assert "genes(names: $v)" in kwargs["json_data"]["query"]

    @pytest.mark.asyncio
    async def test_graphql_error_is_failure(self, adapter):
        with mock_gql(fx.GRAPHQL_ERROR):
            assert await adapter.search_concepts("BRCA1") == []
        with mock_gql({"errors": ["plain string error"]}):
            assert await adapter.search_concepts("BRCA1") == []
        with mock_gql(["not a dict"]):
            assert await adapter.search_concepts("BRCA1") == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_gene_hit_stops_before_drugs(self, adapter):
        with mock_gql(fx.SEARCH_GENE_BRCA1) as mock:
            concepts = await adapter.search_concepts("BRCA1")
        assert mock.await_count == 1
        (gene,) = concepts
        assert gene.primary_id == "hgnc:1100" and gene.primary_label == "BRCA1"
        assert gene.concept_type == "GENE"
        assert "FANCS" in gene.synonyms and "BRCA1" not in gene.synonyms
        # CURIE-looking aliases are cross references, not synonyms
        assert not any(":" in s for s in gene.synonyms)
        assert gene.definitions == ["BRCA1 DNA repair associated"]

    @pytest.mark.asyncio
    async def test_falls_back_to_drugs(self, adapter):
        with mock_gql(fx.EMPTY_NODES, fx.SEARCH_DRUG_MODAFINIL) as mock:
            concepts = await adapter.search_concepts("modafinil")
        assert mock.await_count == 2
        (drug,) = concepts
        assert drug.primary_id == "rxcui:30125"
        assert drug.concept_type == "CHEMICAL"
        assert "approved" in drug.categories
        assert "ARMODAFINIL" in drug.synonyms

    @pytest.mark.asyncio
    async def test_drug_substring_matches_ranked_exact_first_and_limited(self, adapter):
        payload = {
            "data": {
                "drugs": {
                    "nodes": [
                        {
                            "name": "ASPIRIN-TRIGGERED RESOLVIN D1",
                            "conceptId": "iuphar.ligand:6239",
                        },
                        {"name": "ASPIRIN", "conceptId": "rxcui:1191", "approved": True},
                        {"name": "ASPIRIN TRELAMINE", "conceptId": "chembl:CHEMBL5314595"},
                        {"name": "ASPIRIN", "conceptId": "rxcui:1191"},  # duplicate
                        {"name": "", "conceptId": "x:1"},  # unusable
                    ]
                }
            }
        }
        with mock_gql(fx.EMPTY_NODES, payload):
            concepts = await adapter.search_concepts("aspirin", limit=10)
        assert [c.primary_id for c in concepts] == [
            "rxcui:1191",
            "chembl:CHEMBL5314595",
            "iuphar.ligand:6239",
        ]
        with mock_gql(fx.EMPTY_NODES, payload):
            assert len(await adapter.search_concepts("aspirin", limit=2)) == 2

    @pytest.mark.asyncio
    async def test_search_no_hits_blank_and_errors(self, adapter):
        with mock_gql(fx.EMPTY_NODES, {"data": {"drugs": {"nodes": []}}}):
            assert await adapter.search_concepts("xyzzy") == []
        assert await adapter.search_concepts("   ") == []
        assert await adapter.search_concepts("BRCA1", limit=0) == []
        with patch.object(DGIdbAdapter, "_make_request", AsyncMock(side_effect=OSError("down"))):
            assert await adapter.search_concepts("BRCA1") == []

    @pytest.mark.asyncio
    async def test_search_by_concept_id_uses_details(self, adapter):
        with mock_gql(fx.DETAILS_GENE_BRCA1) as mock:
            concepts = await adapter.search_concepts("HGNC:1100")
        assert [c.primary_id for c in concepts] == ["hgnc:1100"]
        assert mock.call_args.kwargs["json_data"]["variables"] == {"v": ["hgnc:1100"]}
        with mock_gql(fx.EMPTY_NODES):
            assert await adapter.search_concepts("hgnc:99999999") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_details(self, adapter):
        with mock_gql(fx.DETAILS_GENE_BRCA1):
            gene = await adapter.get_concept_details("hgnc:1100")
        assert "TUMOR SUPPRESSOR" in gene.categories
        assert any("5 DGIdb interactions with drugs" in d for d in gene.definitions)

    @pytest.mark.asyncio
    async def test_drug_details(self, adapter):
        with mock_gql(fx.DETAILS_DRUG_MODAFINIL) as mock:
            drug = await adapter.get_concept_details("RXCUI:30125")
        assert mock.call_args.kwargs["json_data"]["variables"] == {"v": ["rxcui:30125"]}
        assert "Indication: central nervous system stimulant" in drug.definitions
        assert "Small molecule" in drug.categories
        sources = {i.source for i in drug.identifiers}
        assert KnowledgeSource.CHEMBL in sources and KnowledgeSource.DRUGBANK in sources
        assert any("8 DGIdb interactions with genes" in d for d in drug.definitions)

    @pytest.mark.asyncio
    async def test_details_by_exact_name_gene_then_drug(self, adapter):
        with mock_gql(fx.DETAILS_GENE_BRCA1) as mock:
            assert (await adapter.get_concept_details("brca1")).primary_id == "hgnc:1100"
        assert mock.await_count == 1
        with mock_gql(fx.EMPTY_NODES, fx.DETAILS_DRUG_MODAFINIL):
            assert (await adapter.get_concept_details("Modafinil")).primary_id == "rxcui:30125"

    @pytest.mark.asyncio
    async def test_details_name_requires_exact_match(self, adapter):
        substring_only = {
            "data": {"drugs": {"nodes": [{"name": "MODAFINIL ACID", "conceptId": "x:1"}]}}
        }
        with mock_gql(fx.EMPTY_NODES, substring_only):
            assert await adapter.get_concept_details("modafinil") is None

    @pytest.mark.asyncio
    async def test_details_missing_blank_and_error(self, adapter):
        with mock_gql(fx.EMPTY_NODES):
            assert await adapter.get_concept_details("hgnc:99999999") is None
        assert await adapter.get_concept_details("") is None
        with patch.object(DGIdbAdapter, "_make_request", AsyncMock(side_effect=OSError("down"))):
            assert await adapter.get_concept_details("hgnc:1100") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_drug_to_genes_with_interaction_type(self, adapter):
        with mock_gql(fx.RELATIONSHIPS_DRUG_MODAFINIL):
            edges = await adapter.get_relationships("rxcui:30125", limit=50)
        assert len(edges) == 8
        # strongest first: the SLC6A3 inhibitor edge
        top = edges[0]
        assert top["related_id"] == "hgnc:11049" and top["related_name"] == "SLC6A3"
        assert top["relation_label"] == "inhibitor"
        assert top["directionality"] == "INHIBITORY"
        assert top["sources"] == ["TdgClinicalTrial", "TTD", "ChEMBL"]
        assert top["related_type"] == "gene" and top["source"] == "DGIDB"
        assert top["score"] == pytest.approx(0.2512594, rel=1e-4)
        assert "approved" not in top
        scores = [e["score"] for e in edges]
        assert scores == sorted(scores, reverse=True)
        untyped = next(e for e in edges if e["related_name"] == "CYP2D6")
        assert untyped["relation_label"] == "interacts_with"
        assert untyped["pmids"] == [22931300, 10820139]
        assert untyped["interaction_types"] == []

    @pytest.mark.asyncio
    async def test_gene_to_drugs_and_limit(self, adapter):
        with mock_gql(fx.RELATIONSHIPS_GENE_BRCA1):
            edges = await adapter.get_relationships("hgnc:1100", limit=2)
        assert len(edges) == 2
        assert all(e["related_type"] == "drug" and "approved" in e for e in edges)
        assert edges[0]["score"] >= edges[1]["score"]

    @pytest.mark.asyncio
    async def test_multiple_types_make_one_edge_each_and_pmids_capped(self, adapter):
        payload = copy.deepcopy(fx.RELATIONSHIPS_DRUG_MODAFINIL)
        node = payload["data"]["drugs"]["nodes"][0]
        node["interactions"] = [
            {
                "gene": {"name": "G1", "conceptId": "hgnc:1"},
                "interactionScore": 1.0,
                "evidenceScore": 9,
                "interactionTypes": [
                    {"type": "Partial Agonist", "directionality": "ACTIVATING"},
                    {"type": "partial agonist", "directionality": "ACTIVATING"},  # duplicate
                    {"type": "allosteric-modulator", "directionality": None},
                ],
                "sources": [],
                "publications": [{"pmid": n} for n in range(1, 60)],
            },
            {"gene": {"name": "", "conceptId": "hgnc:2"}, "interactionScore": 0.5},  # unusable
        ]
        with mock_gql(payload):
            edges = await adapter.get_relationships("rxcui:30125")
        assert [e["relation_label"] for e in edges] == ["partial_agonist", "allosteric_modulator"]
        assert len(edges[0]["pmids"]) == 25
        with mock_gql(payload):
            assert len(await adapter.get_relationships("rxcui:30125", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_relationship_failures(self, adapter):
        assert await adapter.get_relationships("hgnc:1100", limit=0) == []
        assert await adapter.get_relationships("") == []
        with mock_gql(fx.EMPTY_NODES):
            assert await adapter.get_relationships("hgnc:99999999") == []
        with patch.object(DGIdbAdapter, "_make_request", AsyncMock(side_effect=OSError("down"))):
            assert await adapter.get_relationships("hgnc:1100") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_gene_mappings(self, adapter):
        with mock_gql(fx.SEARCH_GENE_BRCA1):
            maps = await adapter.get_mappings("hgnc:1100")
        by_source = {m["toSource"]: m["toId"] for m in maps}
        assert by_source["HGNC"] == "HGNC:1100"
        assert by_source["ENSEMBL"] == "ENSEMBL:ENSG00000012048"
        assert by_source["NCBI"] == "NCBIGENE:672"
        assert by_source["UNIPROT"] == "UNIPROT:P38398"
        assert by_source["OMIM"] == "OMIM:113705"
        assert "PUBMED" not in by_source and "CCDS" not in by_source
        assert all(m["fromId"] == "hgnc:1100" and m["fromSource"] == "DGIDB" for m in maps)
        assert all(m["mappingType"] == "xref" and m["confidence"] == 0.9 for m in maps)

    @pytest.mark.asyncio
    async def test_drug_mappings_dedupe(self, adapter):
        payload = copy.deepcopy(fx.DETAILS_DRUG_MODAFINIL)
        node = payload["data"]["drugs"]["nodes"][0]
        node["drugAliases"].append({"alias": "CHEMBL:CHEMBL1373"})  # duplicate xref
        with mock_gql(payload):
            maps = await adapter.get_mappings("rxcui:30125")
        ids = [m["toId"] for m in maps]
        assert ids.count("CHEMBL:CHEMBL1373") == 1
        assert {"RXCUI:30125", "DRUGBANK:DB06413", "NCIT:C26661"} <= set(ids)
        assert any(m["toSource"] == "RXNORM" for m in maps)

    @pytest.mark.asyncio
    async def test_mapping_failures(self, adapter):
        with mock_gql(fx.EMPTY_NODES):
            assert await adapter.get_mappings("hgnc:99999999") == []
        with patch.object(DGIdbAdapter, "_make_request", AsyncMock(side_effect=OSError("down"))):
            assert await adapter.get_mappings("hgnc:1100") == []

    @pytest.mark.asyncio
    async def test_unknown_prefix_gets_no_mapping(self, adapter):
        payload = {"data": {"drugs": {"nodes": [{"name": "X", "conceptId": "foo:1"}]}}}
        with mock_gql(payload):
            assert await adapter.get_mappings("foo:1") == []
