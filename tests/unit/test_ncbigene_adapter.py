"""Unit tests for NCBIGeneAdapter (HTTP mocked with trimmed real Datasets API responses)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest
from fixtures import ncbigene_responses as fx

from knowledge_lookup.adapters.ncbigene_adapter import NCBIGeneAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2/gene/"


@pytest.fixture(autouse=True)
def no_ncbi_key(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("ncbi_api_key", raising=False)


@pytest.fixture
def adapter(lookup_config):
    a = NCBIGeneAdapter(lookup_config)
    a._min_interval = 0.0
    return a


class Router:
    """Fake ``_make_request``: answers by URL path (relative to the gene API base)."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, params=None, headers=None, json_data=None):
        assert url.startswith(BASE)
        path = url[len(BASE) :]
        self.calls.append((path, params, headers))
        answer = self.routes.get(path, {})
        if isinstance(answer, Exception):
            raise answer
        return answer

    def patch(self):
        return patch.object(NCBIGeneAdapter, "_make_request", new=AsyncMock(side_effect=self))

    @property
    def paths(self):
        return [c[0] for c in self.calls]


def _data(concept):
    return concept.source_data[KnowledgeSource.NCBIGENE]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.NCBIGENE
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("672", "672"),
            ("0672", "672"),
            ("NCBIGene:672", "672"),
            ("ncbigene:672", "672"),
            ("GeneID:672", "672"),
            ("Entrez:672", "672"),
            ("entrezgene_672", "672"),
            (" NCBI : 672 ", "672"),
            ("0", None),
            ("-5", None),
            ("BRCA1", None),
            ("NCBIGene:BRCA1", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert NCBIGeneAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize(
        "taxon,expected",
        [
            (None, "9606"),
            (10090, "10090"),
            ("human", "human"),
            ("Mus musculus", "Mus%20musculus"),
            ("../../etc", "9606"),
            ("a/b", "9606"),
            ("", "9606"),
        ],
    )
    def test_taxon_segment(self, taxon, expected):
        assert NCBIGeneAdapter._taxon_segment(taxon) == expected

    def test_api_key_sources(self, adapter, monkeypatch):
        assert adapter._api_key() is None
        monkeypatch.setenv("NCBI_API_KEY", "envkey")
        assert adapter._api_key() == "envkey"
        assert NCBIGeneAdapter(LookupConfig(api_keys={"ncbi": "cfgkey"}))._api_key() == "cfgkey"

    @pytest.mark.asyncio
    async def test_headers_and_key(self, adapter, monkeypatch):
        router = Router({"id/672": fx.GENE_BRCA1})
        with router.patch():
            await adapter.get_concept_details("672")
            monkeypatch.setenv("NCBI_API_KEY", "k3y")
            await adapter.get_concept_details("672")
        assert router.calls[0][2] == {"Accept": "application/json"}
        assert router.calls[1][2] == {"Accept": "application/json", "api-key": "k3y"}

    @pytest.mark.asyncio
    async def test_throttle_is_faster_with_a_key(self, lookup_config, monkeypatch):
        a = NCBIGeneAdapter(lookup_config)
        router = Router({})
        with router.patch(), patch("asyncio.sleep", new=AsyncMock()) as sleep:
            await a._get("id/1")
            await a._get("id/1")
            keyless = sleep.await_args.args[0]
            monkeypatch.setenv("NCBI_API_KEY", "k")
            a._last_request = 0.0
            sleep.reset_mock()
            await a._get("id/1")
            await a._get("id/1")
            keyed = sleep.await_args.args[0]
        assert 0.3 < keyless <= 0.34 + 1e-6
        assert 0.0 < keyed <= 0.11 + 1e-6

    @pytest.mark.asyncio
    async def test_non_dict_answer_is_empty(self, adapter):
        with patch.object(NCBIGeneAdapter, "_make_request", new=AsyncMock(return_value=[1])):
            assert await adapter._get("id/1") == {}


class TestSearch:
    @pytest.mark.asyncio
    async def test_symbol_then_text_fill(self, adapter):
        router = Router(
            {
                "symbol/BRCA1/taxon/9606": {"reports": fx.GENE_BRCA1["reports"]},
                "taxon/9606/dataset_report": fx.TEXT_SEARCH_BREAST_CANCER,
            }
        )
        with router.patch():
            concepts = await adapter.search_concepts("BRCA1", limit=5)
        assert router.paths == ["symbol/BRCA1/taxon/9606", "taxon/9606/dataset_report"]
        assert router.calls[1][1] == {"query": "BRCA1", "page_size": 5}
        # the symbol hit comes first and the text search does not repeat it
        assert [c.primary_id for c in concepts] == ["672", "675", "1485"]
        brca1 = concepts[0]
        assert brca1.primary_label == "BRCA1" and brca1.concept_type == "GENE"
        assert brca1.sources == [KnowledgeSource.NCBIGENE]

    @pytest.mark.asyncio
    async def test_limit_one_skips_the_text_search(self, adapter):
        router = Router({"symbol/brca1/taxon/9606": fx.GENE_BRCA1})
        with router.patch():
            concepts = await adapter.search_concepts("brca1", limit=1)
        assert router.paths == ["symbol/brca1/taxon/9606"]
        assert [c.primary_id for c in concepts] == ["672"]

    @pytest.mark.asyncio
    async def test_free_text_goes_to_the_text_search_only(self, adapter):
        router = Router({"taxon/9606/dataset_report": fx.TEXT_SEARCH_BREAST_CANCER})
        with router.patch():
            concepts = await adapter.search_concepts(" breast cancer ", limit=2)
        assert router.paths == ["taxon/9606/dataset_report"]
        assert router.calls[0][1] == {"query": "breast cancer", "page_size": 2}
        assert [c.primary_id for c in concepts] == ["672", "675"]

    @pytest.mark.asyncio
    async def test_id_queries(self, adapter):
        router = Router({"id/672,3105": fx.GENES_BY_ID})
        with router.patch():
            concepts = await adapter.search_concepts("NCBIGene:672, 3105")
        assert router.paths == ["id/672,3105"]
        assert {c.primary_id for c in concepts} == {"672", "3105", "7157"}  # the fixture's answer

    @pytest.mark.asyncio
    async def test_zero_ids_make_no_request(self, adapter):
        router = Router({})
        with router.patch():
            assert await adapter.search_concepts("0") == []
        assert router.calls == []

    @pytest.mark.asyncio
    async def test_symbol_list_and_taxon(self, adapter):
        router = Router({"symbol/Brca1,Tp53/taxon/Mus%20musculus": fx.GENE_MOUSE_BRCA1})
        with router.patch():
            concepts = await adapter.search_concepts("Brca1, Tp53", limit=1, taxon="Mus musculus")
        assert router.paths == ["symbol/Brca1,Tp53/taxon/Mus%20musculus"]
        assert concepts[0].primary_id == "12189"

    @pytest.mark.asyncio
    async def test_alias_returns_every_gene_using_it(self, adapter):
        router = Router({"symbol/BRCC1/taxon/9606": fx.GENES_ALIAS_BRCC1})
        with router.patch():
            concepts = await adapter.search_concepts("BRCC1", limit=2)
        assert [c.primary_label for c in concepts] == ["BRCA1", "ICE2"]

    @pytest.mark.asyncio
    async def test_limit_is_capped_and_applied(self, adapter):
        router = Router({"taxon/9606/dataset_report": fx.TEXT_SEARCH_BREAST_CANCER})
        with router.patch():
            await adapter.search_concepts("breast cancer", limit=5000)
        assert router.calls[0][1]["page_size"] == 100

    @pytest.mark.asyncio
    async def test_duplicates_removed(self, adapter):
        doubled = {"reports": fx.GENE_BRCA1["reports"] * 2}
        router = Router({"symbol/BRCA1/taxon/9606": doubled})
        with router.patch():
            assert len(await adapter.search_concepts("BRCA1", limit=1)) == 1
        router = Router({"id/672": doubled})
        with router.patch():
            assert len(await adapter.search_concepts("672", limit=5)) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), (None, 5), ("BRCA1", 0)])
    async def test_empty_input(self, adapter, query, limit):
        router = Router({})
        with router.patch():
            assert await adapter.search_concepts(query, limit=limit) == []
        assert router.calls == []

    @pytest.mark.asyncio
    async def test_no_match_and_errors(self, adapter):
        router = Router({})  # every route answers {}
        with router.patch():
            assert await adapter.search_concepts("NOTAGENE123") == []
        router = Router({"symbol/BRCA1/taxon/9606": RuntimeError("down")})
        with router.patch():
            assert await adapter.search_concepts("BRCA1") == []

    @pytest.mark.asyncio
    async def test_records_without_id_or_name_are_skipped(self, adapter):
        reports = {"reports": [{"gene": {"symbol": "X"}}, {"gene": {"gene_id": "5"}}, {"x": 1}]}
        router = Router({"symbol/X/taxon/9606": reports, "taxon/9606/dataset_report": {}})
        with router.patch():
            assert await adapter.search_concepts("X") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_concept(self, adapter):
        router = Router({"id/672": fx.GENE_BRCA1})
        with router.patch():
            concept = await adapter.get_concept_details("NCBIGene:672")
        assert router.paths == ["id/672"]
        assert (concept.primary_id, concept.primary_label) == ("672", "BRCA1")
        assert concept.concept_type == "GENE" and concept.confidence_score == 0.95
        assert concept.synonyms[0] == "BRCA1 DNA repair associated"
        assert "RNF53" in concept.synonyms and "BRCA1" not in concept.synonyms
        assert len({s.casefold() for s in concept.synonyms}) == len(concept.synonyms)
        assert concept.definitions[0].startswith(
            "This gene encodes a 190 kD nuclear phosphoprotein"
        )
        assert concept.categories == ["taxon:9606", "chromosome:17", "locus:17q21.31"]
        assert concept.semantic_types == ["PROTEIN_CODING"]
        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ids >= {
            ("NCBIGENE", "672"),
            ("HGNC", "HGNC:1100"),
            ("ENSEMBL", "ENSG00000012048"),
            ("OMIM", "113705"),
            ("UNIPROT", "P38398"),
        }
        data = _data(concept)
        assert data["url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
        assert data["taxname"] == "Homo sapiens" and data["transcript_count"] == 368
        assert data["annotations"][0]["assembly_name"] == "GRCh38.p14"
        assert data["gene_ontology"]["molecular_functions"][0]["go_id"] == "GO:0003677"

    @pytest.mark.asyncio
    async def test_non_human_authority_is_kept_in_source_data_only(self, adapter):
        router = Router({"symbol/Brca1/taxon/10090": fx.GENE_MOUSE_BRCA1})
        with router.patch():
            concept = await adapter.get_concept_details("Brca1", taxon=10090)
        assert concept.primary_id == "12189"
        assert not any(i.source == "HGNC" for i in concept.identifiers)
        assert _data(concept)["nomenclature_authority"]["authority"] == "MGI"

    @pytest.mark.asyncio
    async def test_symbol_lookup_prefers_exact_symbol(self, adapter):
        router = Router({"symbol/brca1/taxon/9606": fx.GENES_ALIAS_BRCC1})
        with router.patch():
            concept = await adapter.get_concept_details("brca1")
        assert concept.primary_id == "672"

    @pytest.mark.asyncio
    async def test_ambiguous_alias_gives_none(self, adapter):
        router = Router({"symbol/BRCC1/taxon/9606": fx.GENES_ALIAS_BRCC1})
        with router.patch():
            assert await adapter.get_concept_details("BRCC1") is None
        router = Router(
            {"symbol/BRCC1/taxon/9606": {"reports": fx.GENES_ALIAS_BRCC1["reports"][:1]}}
        )
        with router.patch():  # a unique alias resolves
            assert (await adapter.get_concept_details("BRCC1")).primary_id == "672"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", "abc def", "BRCA1,TP53", "0", "../x", None])
    async def test_invalid_ids_make_no_request(self, adapter, bad):
        router = Router({})
        with router.patch():
            assert await adapter.get_concept_details(bad) is None
            assert await adapter.get_mappings(bad) == []
            assert await adapter.get_relationships(bad) == []
        assert router.calls == []

    @pytest.mark.asyncio
    async def test_unknown_gene_and_errors(self, adapter):
        router = Router({"id/99999999": {}})
        with router.patch():
            assert await adapter.get_concept_details("99999999") is None
            assert await adapter.get_mappings("99999999") == []
            assert await adapter.get_relationships("99999999") == []
        router = Router({"id/672": RuntimeError("400 Bad Request")})
        with router.patch():
            assert await adapter.get_concept_details("672") is None
            assert await adapter.get_mappings("672") == []
            assert await adapter.get_relationships("672") == []

    def test_conversion_error_gives_none(self, adapter):
        assert adapter._convert_gene_to_concept({"symbol": "X"}) is None  # no gene_id

    def test_label_falls_back_to_description(self, adapter):
        concept = adapter._convert_gene_to_concept({"gene_id": "7", "description": "some gene"})
        assert concept.primary_label == "some gene" and concept.synonyms == []

    def test_go_terms_are_deduplicated_and_capped(self, adapter):
        gene = {
            "gene_ontology": {
                "molecular_functions": [{"go_id": "GO:1", "name": "a"}] * 3
                + [{"go_id": f"GO:{i}"} for i in range(2, 100)]
                + [{"name": "no id"}],
            }
        }
        terms = adapter._go_terms(gene)["molecular_functions"]
        assert len(terms) == 50 and terms[0] == {"go_id": "GO:1", "name": "a", "qualifier": ""}
        assert adapter._go_terms({}) == {}


class TestMappings:
    @pytest.mark.asyncio
    async def test_human_gene_mappings(self, adapter):
        router = Router({"id/672": fx.GENE_BRCA1})
        with router.patch():
            mappings = await adapter.get_mappings("672")
        got = {(m["toSource"], m["toId"]): m for m in mappings}
        assert got[("NCBIGENE", "NCBIGene:672")]["mappingType"] == "exactMatch"
        assert got[("HGNC", "HGNC:1100")]["confidence"] == 1.0
        assert got[("ENSEMBL", "ENSG00000012048")]["mappingType"] == "exactMatch"
        assert got[("OMIM", "OMIM:113705")]["mappingType"] == "xref"
        assert got[("UNIPROT", "P38398")]["mappingType"] == "encodes_product"
        assert len(mappings) == 5
        for m in mappings:
            assert m["fromId"] == "672" and m["fromSource"] == "NCBIGENE"
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }

    @pytest.mark.asyncio
    async def test_mouse_gene_uses_its_own_authority(self, adapter):
        router = Router({"symbol/Brca1/taxon/10090": fx.GENE_MOUSE_BRCA1})
        with router.patch():
            mappings = await adapter.get_mappings("Brca1", taxon=10090)
        assert ("MGI", "MGI:104537") in {(m["toSource"], m["toId"]) for m in mappings}

    @pytest.mark.asyncio
    async def test_sparse_record_and_conversion_error(self, adapter):
        sparse = {
            "reports": [
                {"gene": {"gene_id": "7", "nomenclature_authority": {"identifier": "X:1"}}}
            ]
        }
        router = Router({"id/7": sparse})
        with router.patch():
            mappings = await adapter.get_mappings("7")
        assert [(m["toSource"], m["toId"]) for m in mappings] == [
            ("NCBIGENE", "NCBIGene:7"),
            ("NOMENCLATURE", "X:1"),
        ]
        bad = {"reports": [{"gene": {"gene_id": "7", "ensembl_gene_ids": 5}}]}
        router = Router({"id/7": bad})
        with router.patch():
            assert await adapter.get_mappings("7") == []


class TestRelationships:
    ROUTES = {
        "id/672": fx.GENE_BRCA1,
        "id/672/product_report": fx.PRODUCT_REPORT_BRCA1,
        "id/672/orthologs": fx.ORTHOLOGS_BRCA1_MOUSE,
    }

    @pytest.mark.asyncio
    async def test_annotation_products_and_orthologs(self, adapter):
        router = Router(self.ROUTES)
        with router.patch():
            edges = await adapter.get_relationships("NCBIGene:672")
        assert router.paths == ["id/672", "id/672/product_report", "id/672/orthologs"]
        assert router.calls[2][1] == {"taxon_filter": "10090"}
        labels = [e["relation_label"] for e in edges]
        assert labels.count("located_on") == 2 and labels.count("has_ortholog") == 1
        located = edges[0]
        assert located["related_id"] == "NC_000017.11"
        assert (located["begin"], located["end"], located["orientation"]) == (
            "43044295",
            "43170327",
            "minus",
        )
        assert located["assembly_name"] == "GRCh38.p14" and located["chromosome"] == "17"
        transcripts = [e for e in edges if e["relation_label"] == "has_transcript"]
        # MANE Select first, then accession order
        assert [t["related_id"] for t in transcripts] == [
            "NM_007294.4",
            "NM_001407571.1",
            "NM_001407581.1",
            "NM_001407582.1",
        ]
        assert transcripts[0]["select_category"] == "MANE_SELECT"
        assert transcripts[0]["ensembl_transcript"] == "ENST00000357654.9"
        proteins = [e for e in edges if e["relation_label"] == "encodes"]
        assert proteins[0]["related_id"] == "NP_009225.1"
        assert proteins[0]["transcript"] == "NM_007294.4"
        assert proteins[0]["related_name"].endswith("(isoform 1)")
        ortholog = next(e for e in edges if e["relation_label"] == "has_ortholog")
        assert ortholog["related_id"] == "NCBIGene:12189"
        assert ortholog["related_name"] == "Brca1" and ortholog["taxname"] == "Mus musculus"
        for e in edges:
            assert {"relation_label", "related_id", "related_name", "source"} <= set(e)

    @pytest.mark.asyncio
    async def test_max_transcripts_caps_products(self, adapter):
        router = Router(self.ROUTES)
        with router.patch():
            edges = await adapter.get_relationships("672", max_transcripts=1, ortholog_taxa=())
        assert [e["related_id"] for e in edges if e["relation_label"] == "has_transcript"] == [
            "NM_007294.4"
        ]
        assert "id/672/orthologs" not in router.paths

    @pytest.mark.asyncio
    async def test_zero_transcripts_skips_the_big_request(self, adapter):
        router = Router(self.ROUTES)
        with router.patch():
            edges = await adapter.get_relationships("672", max_transcripts=0)
        assert "id/672/product_report" not in router.paths
        assert {e["relation_label"] for e in edges} == {"located_on", "has_ortholog"}

    @pytest.mark.asyncio
    async def test_own_taxon_is_not_an_ortholog_query(self, adapter):
        router = Router(self.ROUTES)
        with router.patch():
            await adapter.get_relationships("672", max_transcripts=0, ortholog_taxa=[9606, "7955"])
        assert [c[1] for c in router.calls if c[0].endswith("orthologs")] == [
            {"taxon_filter": "7955"}
        ]

    @pytest.mark.asyncio
    async def test_failed_optional_requests_keep_the_rest(self, adapter):
        routes = {**self.ROUTES, "id/672/product_report": RuntimeError("x")}
        routes["id/672/orthologs"] = RuntimeError("y")
        router = Router(routes)
        with router.patch():
            edges = await adapter.get_relationships("672")
        assert {e["relation_label"] for e in edges} == {"located_on"}

    @pytest.mark.asyncio
    async def test_report_without_products_and_self_ortholog(self, adapter):
        routes = {
            "id/672": fx.GENE_BRCA1,
            "id/672/product_report": {"reports": [{"not": "a product"}, "x"]},
            "id/672/orthologs": {"reports": fx.GENE_BRCA1["reports"]},  # the gene itself
        }
        router = Router(routes)
        with router.patch():
            edges = await adapter.get_relationships("672")
        assert {e["relation_label"] for e in edges} == {"located_on"}

    @pytest.mark.asyncio
    async def test_transcript_without_protein_and_odd_annotations(self, adapter):
        gene = copy.deepcopy(fx.GENE_BRCA1)
        gene["reports"][0]["gene"]["annotations"] = [
            {
                "genomic_locations": [
                    {"sequence_name": "1"},
                    {"genomic_accession_version": "NC_1.1"},
                ]
            }
        ]
        routes = {
            "id/672": gene,
            "id/672/product_report": {
                "reports": [
                    {"product": {"transcripts": [{"accession_version": "NR_1.1"}, {"name": "x"}]}}
                ]
            },
        }
        router = Router(routes)
        with router.patch():
            edges = await adapter.get_relationships("672", ortholog_taxa=())
        assert [(e["relation_label"], e["related_id"]) for e in edges] == [
            ("located_on", "NC_1.1"),
            ("has_transcript", "NR_1.1"),
        ]
        assert edges[0]["related_name"] == "chromosome"
        assert edges[1]["related_name"] == "NR_1.1"

    @pytest.mark.asyncio
    async def test_broken_annotation_does_not_raise(self, adapter):
        gene = copy.deepcopy(fx.GENE_BRCA1)
        gene["reports"][0]["gene"]["annotations"] = "oops"
        router = Router({"id/672": gene})
        with router.patch():
            assert (
                await adapter.get_relationships("672", max_transcripts=0, ortholog_taxa=()) == []
            )
