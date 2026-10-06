"""Unit tests for PubTatorAdapter (all HTTP mocked with trimmed real responses)."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fixtures import pubtator_responses as fx

from knowledge_lookup.adapters.pubtator_adapter import PubTatorAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource

pytestmark = pytest.mark.unit


def _router(table: dict[tuple[str, str], Any]):
    """Return a fake ``_make_request`` keyed on (endpoint suffix, distinguishing param)."""

    async def fake(url, params=None, headers=None, json_data=None):
        params = params or {}
        for (suffix, key), value in table.items():
            if url.endswith(suffix) and key in {
                str(params.get("query")),
                str(params.get("text")),
                str(params.get("e1")),
                str(params.get("pmids")),
                str(params.get("concept")),
                "*",
            }:
                if isinstance(value, Exception):
                    raise value
                return value
        return []

    return fake


@pytest.fixture
def adapter(lookup_config):
    a = PubTatorAdapter(lookup_config)
    a._min_interval = 0.0
    return a


def _patch(adapter, table):
    return patch.object(adapter, "_make_request", new=AsyncMock(side_effect=_router(table)))


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.PUBTATOR
        assert adapter.is_available() is True

    def test_label_from_accession(self):
        f = PubTatorAdapter._label_from_accession
        assert f("@DISEASE_Fatigue_Syndrome_Chronic") == "Fatigue Syndrome Chronic"
        assert f("@VARIANT_c.68_69del_BRCA1_human") == "c.68_69del BRCA1"
        assert f("not-an-accession") == "not-an-accession"

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, lookup_config):
        a = PubTatorAdapter(lookup_config)
        a._min_interval = 0.05
        with patch.object(a, "_make_request", new=AsyncMock(return_value=[])) as mock:
            with patch("asyncio.sleep", new=AsyncMock()) as sleep:
                await a._get("/entity/autocomplete/", {"query": "a"})
                await a._get("/entity/autocomplete/", {"query": "b"})
        assert mock.await_count == 2
        sleep.assert_awaited()  # second call had to wait


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_mixed_types(self, adapter):
        with _patch(adapter, {("/entity/autocomplete/", "BRCA1"): fx.AUTOCOMPLETE_BRCA1}) as m:
            concepts = await adapter.search_concepts("BRCA1", limit=10)
        assert [c.primary_id for c in concepts] == [
            "@GENE_BRCA1",
            "@GENE_BRCA1.L",
            "@VARIANT_c.5382insC_BRCA1_human",
        ]
        assert concepts[0].concept_type == ConceptType.GENE
        assert concepts[2].concept_type == ConceptType.MOLECULAR_ENTITY
        assert concepts[0].confidence_score == 0.9
        assert concepts[2].confidence_score == 0.7
        assert [i.identifier for i in concepts[0].identifiers if i.source == "NCBI"] == ["672"]
        assert concepts[0].sources == [KnowledgeSource.PUBTATOR]
        assert concepts[0].source_data[KnowledgeSource.PUBTATOR]["db_id"] == "672"
        # no ``concept`` param without entity_types
        assert "concept" not in m.await_args.args[1]

    @pytest.mark.asyncio
    async def test_search_limit_and_synonym_and_mesh(self, adapter):
        with _patch(
            adapter, {("/entity/autocomplete/", "fatigue"): fx.AUTOCOMPLETE_FATIGUE_DISEASE}
        ):
            concepts = await adapter.search_concepts("fatigue", limit=2)
        assert len(concepts) == 2
        assert concepts[1].primary_label == "Fatigue Syndrome Chronic"
        assert any(
            i.source == KnowledgeSource.MESH and i.identifier == "D015673"
            for i in concepts[1].identifiers
        )
        with _patch(
            adapter, {("/entity/autocomplete/", "fatigue"): fx.AUTOCOMPLETE_FATIGUE_DISEASE}
        ):
            all_three = await adapter.search_concepts("fatigue", limit=5)
        assert all_three[2].synonyms == ["Fatigue, Voice"]

    @pytest.mark.asyncio
    async def test_search_entity_types_one_call_each_and_dedup(self, adapter):
        with _patch(adapter, {("/entity/autocomplete/", "*"): fx.AUTOCOMPLETE_BRCA1}) as m:
            concepts = await adapter.search_concepts(
                "BRCA1", limit=20, entity_types=["gene", "VARIANT", "bogus"]
            )
        assert m.await_count == 2
        assert [c.args[1]["concept"] for c in m.await_args_list] == ["GENE", "VARIANT"]
        assert len(concepts) == 3  # same hits twice -> de-duplicated

    @pytest.mark.asyncio
    async def test_search_only_invalid_types_returns_empty(self, adapter):
        assert await adapter.search_concepts("BRCA1", entity_types=["bogus"]) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("BRCA1", 0)])
    async def test_search_invalid_input(self, adapter, query, limit):
        assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_search_empty_and_malformed_and_error(self, adapter):
        with _patch(adapter, {("/entity/autocomplete/", "*"): []}):
            assert await adapter.search_concepts("zzzz") == []
        with _patch(adapter, {("/entity/autocomplete/", "*"): {"detail": "bad"}}):
            assert await adapter.search_concepts("zzzz") == []
        with _patch(adapter, {("/entity/autocomplete/", "*"): RuntimeError("boom")}):
            assert await adapter.search_concepts("zzzz") == []

    @pytest.mark.asyncio
    async def test_search_skips_unusable_hits(self, adapter):
        hits = ["junk", {"_id": "bad", "name": "x"}, {"_id": "@GENE_X"}, fx.AUTOCOMPLETE_BRCA1[0]]
        with _patch(adapter, {("/entity/autocomplete/", "*"): hits}):
            concepts = await adapter.search_concepts("BRCA1")
        assert [c.primary_id for c in concepts] == ["@GENE_BRCA1"]


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_by_accession(self, adapter):
        table = {("/entity/autocomplete/", "Fatigue Syndrome Chronic"): fx.AUTOCOMPLETE_CFS_EXACT}
        with _patch(adapter, table) as m:
            concept = await adapter.get_concept_details("@DISEASE_Fatigue_Syndrome_Chronic")
        assert concept.primary_label == "Fatigue Syndrome Chronic"
        assert concept.concept_type == ConceptType.DISEASE
        assert m.await_args.args[1]["concept"] == "DISEASE"

    @pytest.mark.asyncio
    async def test_details_with_prefix_and_case(self, adapter):
        table = {("/entity/autocomplete/", "Fatigue Syndrome Chronic"): fx.AUTOCOMPLETE_CFS_EXACT}
        with _patch(adapter, table):
            concept = await adapter.get_concept_details(
                "pubtator:@disease_Fatigue_Syndrome_Chronic"
            )
        assert concept is not None
        assert concept.primary_id == "@DISEASE_Fatigue_Syndrome_Chronic"

    @pytest.mark.asyncio
    async def test_details_by_mesh_id_tries_disease_then_chemical(self, adapter):
        table = {
            ("/search/", "@DISEASE_MESH:D001241"): {"results": [], "total_pages": 0},
            ("/search/", "@CHEMICAL_MESH:D001241"): {
                "results": [
                    {"text_hl": "@CHEMICAL_Aspirin @<m>CHEMICAL_MESH:D001241</m> @@@aspirin@@@"}
                ]
            },
            ("/entity/autocomplete/", "Aspirin"): fx.AUTOCOMPLETE_ASPIRIN_CHEMICAL,
        }
        with _patch(adapter, table) as m:
            concept = await adapter.get_concept_details("MESH:D001241")
        assert concept.primary_id == "@CHEMICAL_Aspirin"
        searched = [c.args[1].get("text") for c in m.await_args_list if "text" in c.args[1]]
        assert searched == ["@DISEASE_MESH:D001241", "@CHEMICAL_MESH:D001241"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cid", ["672", "NCBIGene:672", "ncbi_gene:672"])
    async def test_details_by_ncbi_gene_id(self, adapter, cid):
        table = {
            ("/search/", "@GENE_672"): fx.SEARCH_BY_GENE_ID,
            ("/entity/autocomplete/", "BRCA1"): fx.AUTOCOMPLETE_BRCA1,
        }
        with _patch(adapter, table):
            concept = await adapter.get_concept_details(cid)
        assert concept.primary_id == "@GENE_BRCA1"

    @pytest.mark.asyncio
    async def test_details_taxon_id_resolution(self, adapter):
        table = {
            ("/search/", "@SPECIES_9606"): {
                "results": [{"text_hl": "in @SPECIES_human @<m>SPECIES_9606</m> @@@patients@@@"}]
            },
            ("/entity/autocomplete/", "human"): [
                {
                    "_id": "@SPECIES_human",
                    "biotype": "species",
                    "db_id": "9606",
                    "db": "ncbi_taxonomy",
                    "name": "human",
                    "match": "Matched on name <m>human</m>",
                }
            ],
        }
        with _patch(adapter, table):
            concept = await adapter.get_concept_details("NCBITaxon:9606")
        assert concept.concept_type == ConceptType.ORGANISM

    @pytest.mark.asyncio
    async def test_details_variant(self, adapter):
        table = {("/entity/autocomplete/", "c.68_69del"): fx.AUTOCOMPLETE_VARIANT}
        with _patch(adapter, table) as m:
            concept = await adapter.get_concept_details("@VARIANT_c.68_69del_BRCA1_human")
        assert concept.primary_label == "c.68_69del"
        assert m.await_args.args[1]["query"] == "c.68_69del"

    @pytest.mark.asyncio
    async def test_details_not_found_and_bad_ids(self, adapter):
        table = {("/entity/autocomplete/", "*"): fx.AUTOCOMPLETE_BRCA1}
        with _patch(adapter, table):
            assert await adapter.get_concept_details("@GENE_NOSUCHGENE") is None
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("not an id") is None
            assert await adapter.get_concept_details("PUBTATOR:") is None
        with _patch(adapter, {("/entity/autocomplete/", "*"): {"x": 1}}):
            assert await adapter.get_concept_details("@GENE_BRCA1") is None

    @pytest.mark.asyncio
    async def test_details_id_resolution_failure_and_no_match(self, adapter):
        with _patch(adapter, {("/search/", "*"): RuntimeError("down")}):
            assert await adapter.get_concept_details("D015673") is None
        with _patch(adapter, {("/search/", "*"): {"results": [{"text_hl": "nothing"}]}}):
            assert await adapter.get_concept_details("D015673") is None
        with _patch(adapter, {("/search/", "*"): ["unexpected"]}):
            assert await adapter.get_concept_details("672") is None

    @pytest.mark.asyncio
    async def test_details_error_returns_none(self, adapter):
        with _patch(adapter, {("/entity/autocomplete/", "*"): RuntimeError("x")}):
            assert await adapter.get_concept_details("@GENE_BRCA1") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships_directions_and_shape(self, adapter):
        table = {("/relations", "@DISEASE_Fatigue_Syndrome_Chronic"): fx.RELATIONS_CFS}
        with _patch(adapter, table) as m:
            rels = await adapter.get_relationships("@DISEASE_Fatigue_Syndrome_Chronic")
        assert len(rels) == 5
        first = rels[0]
        assert first == {
            "relation_label": "treat",
            "related_id": "@CHEMICAL_Hydrocortisone",
            "related_name": "Hydrocortisone",
            "source": "PubTator",
            "direction": "incoming",
            "related_type": "CHEMICAL",
            "publication_count": 47,
        }
        by_id = {r["related_id"]: r for r in rels}
        assert by_id["@GENE_RNASEL"]["direction"] == "outgoing"
        assert by_id["@GENE_TNF"]["relation_label"] == "stimulate"
        assert by_id["@VARIANT_p.A1156T_SCN4A_human"]["related_name"] == "p.A1156T SCN4A"
        assert m.await_args.args[1] == {"e1": "@DISEASE_Fatigue_Syndrome_Chronic"}
        # strongest first
        counts = [r["publication_count"] for r in rels]
        assert counts == sorted(counts, reverse=True)

    @pytest.mark.asyncio
    async def test_relationships_filters_limit_and_dedup(self, adapter):
        rows = fx.RELATIONS_CFS + [fx.RELATIONS_CFS[0]]  # duplicate row
        table = {("/relations", "@DISEASE_Fatigue_Syndrome_Chronic"): rows}
        with _patch(adapter, table) as m:
            rels = await adapter.get_relationships(
                "@DISEASE_Fatigue_Syndrome_Chronic",
                limit=2,
                relation_type="TREAT",
                target_type="chemical",
            )
        assert m.await_args.args[1] == {
            "e1": "@DISEASE_Fatigue_Syndrome_Chronic",
            "type": "treat",
            "e2": "CHEMICAL",
        }
        assert len(rels) == 2

    @pytest.mark.asyncio
    async def test_relationships_by_mesh_id(self, adapter):
        table = {
            ("/search/", "@DISEASE_MESH:D015673"): fx.SEARCH_BY_MESH,
            ("/relations", "@DISEASE_Fatigue_Syndrome_Chronic"): fx.RELATIONS_CFS,
        }
        with _patch(adapter, table):
            rels = await adapter.get_relationships("D015673", limit=3)
        assert len(rels) == 3

    @pytest.mark.asyncio
    async def test_relationships_edge_cases(self, adapter):
        assert await adapter.get_relationships("@GENE_BRCA1", limit=0) == []
        assert await adapter.get_relationships("garbage") == []
        junk = [{"type": "", "source": "@A_B", "target": "@C_D"}, {"source": "", "type": "t"}]
        with _patch(adapter, {("/relations", "*"): junk}):
            assert await adapter.get_relationships("@GENE_BRCA1") == []
        with _patch(adapter, {("/relations", "*"): {"detail": "x"}}):
            assert await adapter.get_relationships("@GENE_BRCA1") == []
        with _patch(adapter, {("/relations", "*"): RuntimeError("down")}):
            assert await adapter.get_relationships("@GENE_BRCA1") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_mesh_gene_variants(self, adapter):
        with _patch(adapter, {("/entity/autocomplete/", "*"): fx.AUTOCOMPLETE_CFS_EXACT}):
            m = await adapter.get_mappings("@DISEASE_Fatigue_Syndrome_Chronic")
        assert m == [
            {
                "fromId": "@DISEASE_Fatigue_Syndrome_Chronic",
                "toId": "MESH:D015673",
                "fromSource": "PubTator",
                "toSource": "MeSH",
                "mappingType": "exact",
                "confidence": 0.95,
            }
        ]
        with _patch(adapter, {("/entity/autocomplete/", "*"): fx.AUTOCOMPLETE_BRCA1}):
            m = await adapter.get_mappings("@GENE_BRCA1")
        assert m[0]["toId"] == "NCBIGene:672" and m[0]["toSource"] == "NCBI Gene"

    @pytest.mark.asyncio
    async def test_mappings_variant_litvar(self, adapter):
        with _patch(adapter, {("/entity/autocomplete/", "*"): fx.AUTOCOMPLETE_VARIANT}):
            parent = await adapter.get_mappings("@VARIANT_c.68_69del_BRCA1_human")
            rs = await adapter.get_mappings("@VARIANT_c.68_69delAG_BRCA1_human")
        assert parent == [
            {
                "fromId": "@VARIANT_c.68_69del_BRCA1_human",
                "toId": "NCBIGene:672",
                "fromSource": "PubTator",
                "toSource": "NCBI Gene",
                "mappingType": "parent_gene",
                "confidence": 0.95,
            }
        ]
        assert [(x["toId"], x["toSource"]) for x in rs] == [("rs386833395", "dbSNP")]

    @pytest.mark.asyncio
    async def test_mappings_other_db_missing_and_error(self, adapter):
        hit = [
            {
                "_id": "@SPECIES_human",
                "biotype": "species",
                "db_id": "9606",
                "db": "ncbi_taxonomy",
                "name": "human",
                "match": "Matched on name <m>x</m>",
            }
        ]
        with _patch(adapter, {("/entity/autocomplete/", "*"): hit}):
            m = await adapter.get_mappings("@SPECIES_human")
        assert m[0]["toSource"] == "ncbi_taxonomy" and m[0]["toId"] == "9606"
        nodb = [{"_id": "@GENE_X", "biotype": "gene", "name": "X"}]
        with _patch(adapter, {("/entity/autocomplete/", "*"): nodb}):
            assert await adapter.get_mappings("@GENE_X") == []
            assert await adapter.get_mappings("@GENE_NOPE") == []
        with _patch(adapter, {("/entity/autocomplete/", "*"): RuntimeError("x")}):
            assert await adapter.get_mappings("@GENE_X") == []
        with patch.object(adapter, "get_concept_details", new=AsyncMock(side_effect=ValueError)):
            assert await adapter.get_mappings("@GENE_X") == []


class TestPublications:
    @pytest.mark.asyncio
    async def test_publications_single_page(self, adapter):
        table = {("/search/", "@DISEASE_Fatigue_Syndrome_Chronic"): fx.SEARCH_CFS}
        with _patch(adapter, table) as m:
            pubs = await adapter.get_publications("@DISEASE_Fatigue_Syndrome_Chronic", limit=2)
        assert [p["pmid"] for p in pubs] == ["35046929", "35432363"]
        assert pubs[0]["title"].startswith("The Gut Microbiome")
        assert pubs[0]["doi"] == "10.3389/fimmu.2021.628741"
        assert pubs[0]["pmcid"] == "PMC8761622"
        assert m.await_count == 1

    @pytest.mark.asyncio
    async def test_publications_multiple_pages_dedup_and_cap(self, adapter):
        def page_of(n):
            return {
                "results": [{"pmid": 1000 * n + i, "title": f"t{n}-{i}"} for i in range(10)]
                + [{"pmid": 1}],  # repeated pmid across pages must be de-duplicated
                "total_pages": 100,
            }

        calls = []

        async def fake(url, params=None, headers=None, json_data=None):
            calls.append(params["page"])
            return page_of(params["page"])

        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=fake)):
            pubs = await adapter.get_publications("@GENE_BRCA1", limit=25)
            assert len(pubs) == 25 and calls == [1, 2, 3]
            calls.clear()
            await adapter.get_publications("@GENE_BRCA1", limit=500)
            assert calls == [1, 2, 3, 4, 5]  # capped at 5 pages

    @pytest.mark.asyncio
    async def test_publications_stops_at_last_page_and_edge_cases(self, adapter):
        one_page = {"results": [{"pmid": 5, "title": "x"}], "total_pages": 1}
        with _patch(adapter, {("/search/", "*"): one_page}) as m:
            pubs = await adapter.get_publications("@GENE_BRCA1", limit=30)
        assert len(pubs) == 1 and m.await_count == 1
        assert await adapter.get_publications("@GENE_BRCA1", limit=0) == []
        assert await adapter.get_publications("nonsense") == []
        with _patch(adapter, {("/search/", "*"): ["bad"]}):
            assert await adapter.get_publications("@GENE_BRCA1") == []
        with _patch(adapter, {("/search/", "*"): {"results": [{"title": "no pmid"}]}}):
            assert await adapter.get_publications("@GENE_BRCA1") == []
        with _patch(adapter, {("/search/", "*"): RuntimeError("x")}):
            assert await adapter.get_publications("@GENE_BRCA1") == []

    @pytest.mark.asyncio
    async def test_annotations(self, adapter):
        with _patch(adapter, {("/publications/export/biocjson", "35046929"): fx.BIOC_35046929}):
            ann = await adapter.get_publication_annotations(["35046929", "abc"])
        assert list(ann) == ["35046929"]
        texts = [a["text"] for a in ann["35046929"]]
        assert texts == ["Myalgic Encephalomyelitis", "ME"]  # duplicate mention collapsed
        assert ann["35046929"][0]["identifier"] == "MESH:D015673"

    @pytest.mark.asyncio
    async def test_annotations_edge_cases(self, adapter):
        assert await adapter.get_publication_annotations([]) == {}
        assert await adapter.get_publication_annotations(["abc"]) == {}
        with _patch(adapter, {("/publications/export/biocjson", "*"): ["bad"]}):
            assert await adapter.get_publication_annotations(["1"]) == {}
        with _patch(adapter, {("/publications/export/biocjson", "*"): RuntimeError("x")}):
            assert await adapter.get_publication_annotations(["1"]) == {}
