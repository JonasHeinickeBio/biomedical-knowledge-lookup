"""Unit tests for GnomADAdapter (mocked GraphQL responses captured from the live API)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.gnomad_adapter import (
    MAX_GENE_SPAN_BP,
    GnomADAdapter,
    normalize_variant_id,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import gnomad_responses as fx

pytestmark = pytest.mark.unit

GNOMAD = KnowledgeSource.GNOMAD


def router(**responses):
    """AsyncMock side effect answering by GraphQL operation name (``Gnomad...``)."""

    async def fake(url, params=None, headers=None, json_data=None):
        name = json_data["query"].split("(")[0].split("{")[0].replace("query", "").strip()
        value = responses.get(name)
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value) if value is not None else {"data": None}

    return AsyncMock(side_effect=fake)


@pytest.fixture
def adapter(lookup_config):
    return GnomADAdapter(lookup_config)


NOT_FOUND = {"errors": [{"message": "Gene not found"}], "data": {"gene": None}}


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.GNOMAD
        assert adapter.is_available() is True
        assert adapter.min_request_timeout >= 60

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1-55516888-G-GA", "1-55516888-G-GA"),
            ("chr1:55516888:g:ga", "1-55516888-G-GA"),
            ("X_1000_A_T", "X-1000-A-T"),
            ("chrMT-100-A-G", "M-100-A-G"),
            ("rs1801133", None),
            ("1-abc-G-A", None),
            ("", None),
        ],
    )
    def test_normalize_variant_id(self, raw, expected):
        assert normalize_variant_id(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ENSG00000012048", ("gene_id", "ENSG00000012048")),
            ("ensg00000012048.23", ("gene_id", "ENSG00000012048")),
            ("gnomad:rs1801133", ("rsid", "rs1801133")),
            ("RS1801133", ("rsid", "rs1801133")),
            ("chr1-5-A-T", ("variant", "1-5-A-T")),
            ("brca1", ("symbol", "BRCA1")),
            ("", None),
            ("not a thing!", None),
        ],
    )
    def test_classify(self, adapter, raw, expected):
        assert adapter._classify(raw) == expected


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_details_with_constraint(self, adapter):
        mock = router(GnomadGene=fx.GENE_BRCA1)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("BRCA1")
        assert concept is not None
        assert concept.primary_id == "ENSG00000012048"
        assert concept.primary_label == "BRCA1"
        assert concept.concept_type == ConceptType.GENE
        assert {i.source for i in concept.identifiers} >= {
            KnowledgeSource.HGNC,
            KnowledgeSource.NCBI,
            KnowledgeSource.OMIM,
        }
        data = concept.source_data[GNOMAD]
        assert data["constraint"]["loeuf"] == pytest.approx(0.9276, abs=1e-3)
        assert data["constraint"]["lof_z"] == pytest.approx(2.1667, abs=1e-3)
        assert data["chrom"] == "17"
        # symbol lookups use the symbol variable, Ensembl ids the gene_id variable
        assert mock.await_args.kwargs["json_data"]["variables"] == {"symbol": "BRCA1"}
        with patch.object(adapter, "_make_request", mock):
            await adapter.get_concept_details("ENSG00000012048.23")
        assert mock.await_args.kwargs["json_data"]["variables"] == {"geneId": "ENSG00000012048"}

    @pytest.mark.asyncio
    async def test_variant_details(self, adapter):
        mock = router(GnomadVariant=fx.VARIANT_MTHFR_RESPONSE)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("chr1:11796321:G:A")
        assert concept.primary_id == "1-11796321-G-A"
        assert concept.primary_label == "rs1801133"
        assert concept.concept_type == ConceptType.MOLECULAR_ENTITY
        assert "1-11796321-G-A" in concept.synonyms
        assert {i.source for i in concept.identifiers} >= {
            KnowledgeSource.DBSNP,
            KnowledgeSource.CLINVAR,
        }
        data = concept.source_data[GNOMAD]
        assert data["kind"] == "variant"
        assert data["joint"]["af"] == pytest.approx(0.32, abs=0.02)
        assert data["exome"]["ac"] > 0 and data["genome"]["an"] > 0
        assert data["clinvar"]["variation_id"] == "3520"
        ids = {g["id"] for g in data["ancestry_groups"]}
        assert "nfe" in ids and "afr" in ids
        # sex-stratified rows are dropped
        assert not any(i.endswith(("_XX", "_XY")) or i in ("XX", "XY") for i in ids)
        assert data["transcript_consequences"][0]["consequence"] == "missense_variant"
        assert "MTHFR" in concept.definitions[0]
        assert concept.categories == ["missense_variant"]

    @pytest.mark.asyncio
    async def test_rsid_details_fetches_clinvar_second(self, adapter):
        mock = router(
            GnomadVariantByRsid=fx.VARIANT_BY_RSID_RESPONSE,
            GnomadClinvar=fx.CLINVAR_VARIANT_RESPONSE,
        )
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("rs1801133")
        assert concept.primary_id == "1-11796321-G-A"
        assert concept.source_data[GNOMAD]["clinvar"]["clinical_significance"]
        assert mock.await_count == 2

    @pytest.mark.asyncio
    async def test_rsid_without_clinvar(self, adapter):
        mock = router(GnomadVariantByRsid=fx.VARIANT_BY_RSID_RESPONSE)
        with patch.object(adapter, "_make_request", mock):
            concept = await adapter.get_concept_details("rs1801133")
        assert concept is not None
        assert concept.source_data[GNOMAD]["clinvar"] is None

    @pytest.mark.asyncio
    async def test_variant_without_consequences_or_frequency(self, adapter):
        payload = {"data": {"variant": {"variant_id": "1-1-A-T", "rsids": []}, "clinvar": None}}
        with patch.object(adapter, "_make_request", router(GnomadVariant=payload)):
            concept = await adapter.get_concept_details("1-1-A-T")
        assert concept.primary_label == "1-1-A-T"
        assert concept.definitions == ["gnomAD variant 1-1-A-T"]
        assert concept.source_data[GNOMAD]["joint"] is None

    @pytest.mark.asyncio
    async def test_not_found_and_invalid(self, adapter):
        mock = router(GnomadGene=NOT_FOUND, GnomadVariant={"data": {"variant": None}})
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.get_concept_details("NOPE") is None
            assert await adapter.get_concept_details("1-1-A-T") is None
            assert await adapter.get_concept_details("not a thing!") is None
        assert mock.await_count == 2  # the invalid id never reaches the network

    @pytest.mark.asyncio
    async def test_gene_without_symbol_is_dropped(self, adapter):
        payload = {"data": {"gene": {"gene_id": "ENSG00000000001"}}}
        with patch.object(adapter, "_make_request", router(GnomadGene=payload)):
            assert await adapter.get_concept_details("ENSG00000000001") is None

    @pytest.mark.asyncio
    async def test_errors_never_raise(self, adapter):
        mock = router(GnomadGene=RuntimeError("boom"))
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.get_concept_details("BRCA1") is None
        with patch.object(adapter, "_make_request", AsyncMock(return_value=["not", "a", "dict"])):
            assert await adapter.get_concept_details("BRCA1") is None
        with patch.object(adapter, "_fetch_gene", AsyncMock(side_effect=ValueError("x"))):
            assert await adapter.get_concept_details("BRCA1") is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_gene_search_batches_details(self, adapter):
        mock = router(GnomadGeneSearch=fx.GENE_SEARCH_BRCA1, GnomadGenes=fx.GENES_BATCH_BRCA1)
        with patch.object(adapter, "_make_request", mock):
            concepts = await adapter.search_concepts("brca1", limit=5)
        assert [c.primary_id for c in concepts] == [
            g["gene_id"] for g in fx.GENES_BATCH_BRCA1["data"].values()
        ]
        assert concepts[0].primary_label == "BRCA1"
        assert mock.await_count == 2  # search + ONE batched detail request

    @pytest.mark.asyncio
    async def test_gene_search_limit(self, adapter):
        mock = router(GnomadGeneSearch=fx.GENE_SEARCH_BRCA1, GnomadGenes=fx.GENES_BATCH_BRCA1)
        with patch.object(adapter, "_make_request", mock):
            concepts = await adapter.search_concepts("brca1", limit=1)
        assert len(concepts) == 1
        batch_query = mock.await_args.kwargs["json_data"]["query"]
        assert "ENSG00000267595" not in batch_query  # only `limit` ids are expanded

    @pytest.mark.asyncio
    async def test_empty_results(self, adapter):
        mock = router(GnomadGeneSearch={"data": {"gene_search": []}})
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.search_concepts("fatigue") == []

    @pytest.mark.asyncio
    async def test_blank_zero_limit_and_unsearchable(self, adapter):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("BRCA1", 0) == []
            assert await adapter.search_concepts("chronic fatigue syndrome", 5) == []
        mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_variant_and_rsid_queries(self, adapter):
        mock = router(
            GnomadVariant=fx.VARIANT_MTHFR_RESPONSE,
            GnomadVariantByRsid=fx.VARIANT_BY_RSID_RESPONSE,
            GnomadClinvar=fx.CLINVAR_VARIANT_RESPONSE,
        )
        with patch.object(adapter, "_make_request", mock):
            by_id = await adapter.search_concepts("1-11796321-G-A")
            by_rsid = await adapter.search_concepts("rs1801133")
        assert by_id[0].primary_id == by_rsid[0].primary_id == "1-11796321-G-A"

    @pytest.mark.asyncio
    async def test_variant_miss(self, adapter):
        with patch.object(adapter, "_make_request", router(GnomadVariant={"data": {}})):
            assert await adapter.search_concepts("1-1-A-T") == []

    @pytest.mark.asyncio
    async def test_clinvar_variation_id_search(self, adapter):
        mock = router(
            GnomadVariantSearch=fx.VARIANT_SEARCH_CLINVAR,
            GnomadVariant=fx.VARIANT_MTHFR_RESPONSE,
        )
        with patch.object(adapter, "_make_request", mock):
            concepts = await adapter.search_concepts("220816", limit=5)
        assert len(concepts) == 1

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", router(GnomadGeneSearch=OSError("down"))):
            assert await adapter.search_concepts("BRCA1") == []
        with patch.object(adapter, "_classify", side_effect=RuntimeError("x")):
            assert await adapter.search_concepts("BRCA1") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_gene_to_variants_ranked_and_capped(self, adapter):
        mock = router(
            GnomadGeneSpan=fx.GENE_SPAN_BRCA1,
            GnomadGeneVariants=fx.GENE_VARIANTS_BRCA1,
        )
        with patch.object(adapter, "_make_request", mock):
            rels = await adapter.get_relationships("ENSG00000012048", limit=3)
        assert len(rels) == 3
        assert all(r["relation_label"] == "has_variant" and r["source"] == "gnomAD" for r in rels)
        freqs = [r["allele_frequency"] for r in rels]
        assert freqs == sorted(freqs, reverse=True)
        assert rels[0]["consequence"] == "missense_variant"
        assert rels[0]["related_name"].startswith("rs")

    @pytest.mark.asyncio
    async def test_gene_relationships_skip_intronic_and_include_lof(self, adapter):
        mock = router(GnomadGeneSpan=fx.GENE_SPAN_BRCA1, GnomadGeneVariants=fx.GENE_VARIANTS_BRCA1)
        with patch.object(adapter, "_make_request", mock):
            rels = await adapter.get_relationships("ENSG00000012048", limit=50)
        consequences = {r["consequence"] for r in rels}
        assert "intron_variant" not in consequences
        assert "frameshift_variant" in consequences

    @pytest.mark.asyncio
    async def test_gene_by_symbol_and_huge_gene_guard(self, adapter):
        huge = {
            "data": {
                "gene": {
                    "gene_id": "ENSG00000155657",
                    "symbol": "TTN",
                    "start": 1,
                    "stop": MAX_GENE_SPAN_BP + 2,
                }
            }
        }
        mock = router(GnomadGeneSpan=huge)
        with patch.object(adapter, "_make_request", mock):
            assert await adapter.get_relationships("TTN") == []
        assert mock.await_args.kwargs["json_data"]["variables"] == {"symbol": "TTN"}
        assert mock.await_count == 1  # the all-variants query is never sent

    @pytest.mark.asyncio
    async def test_gene_relationships_dedupe_and_unknown_gene(self, adapter):
        variants = copy.deepcopy(fx.GENE_VARIANTS_BRCA1)
        variants["data"]["gene"]["variants"].append(
            copy.deepcopy(variants["data"]["gene"]["variants"][0])
        )
        variants["data"]["gene"]["variants"].append(
            {"variant_id": "17-1-A-T", "consequence": "missense_variant", "exome": None}
        )
        mock = router(GnomadGeneSpan=fx.GENE_SPAN_BRCA1, GnomadGeneVariants=variants)
        with patch.object(adapter, "_make_request", mock):
            rels = await adapter.get_relationships("ENSG00000012048", limit=50)
        ids = [r["related_id"] for r in rels]
        assert len(ids) == len(set(ids))
        assert "17-1-A-T" not in ids  # no counts, no frequency
        with patch.object(adapter, "_make_request", router(GnomadGeneSpan=NOT_FOUND)):
            assert await adapter.get_relationships("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_variant_gene_and_consequences(self, adapter):
        mock = router(GnomadVariant=fx.VARIANT_MTHFR_RESPONSE)
        with patch.object(adapter, "_make_request", mock):
            rels = await adapter.get_relationships("1-11796321-G-A", limit=20)
        gene_edges = [r for r in rels if r["relation_label"] == "in_gene"]
        assert [(r["related_id"], r["related_name"]) for r in gene_edges] == [
            ("ENSG00000177000", "MTHFR")
        ]
        assert gene_edges[0]["hgvsp"] == "p.Ala222Val"
        terms = [r["related_id"] for r in rels if r["relation_label"] == "has_consequence"]
        assert "missense_variant" in terms and len(terms) == len(set(terms))
        with patch.object(adapter, "_make_request", mock):
            capped = await adapter.get_relationships("1-11796321-G-A", limit=1)
        assert len(capped) == 1

    @pytest.mark.asyncio
    async def test_relationship_edge_cases(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock()) as mock:
            assert await adapter.get_relationships("BRCA1", limit=0) == []
            assert await adapter.get_relationships("not a thing!") == []
        mock.assert_not_awaited()
        with patch.object(adapter, "_make_request", router(GnomadVariant={"data": {}})):
            assert await adapter.get_relationships("1-1-A-T") == []
        with patch.object(adapter, "_make_request", router(GnomadGeneSpan=OSError("x"))):
            assert await adapter.get_relationships("BRCA1") == []
        with patch.object(adapter, "_classify", side_effect=RuntimeError("x")):
            assert await adapter.get_relationships("BRCA1") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_variant_mappings(self, adapter):
        mock = router(GnomadVariant=fx.VARIANT_MTHFR_RESPONSE)
        with patch.object(adapter, "_make_request", mock):
            maps = await adapter.get_mappings("1-11796321-G-A")
        by_source = {m["toSource"]: m for m in maps}
        assert by_source["dbSNP"]["toId"] == "rs1801133"
        assert by_source["ClinVar"]["toId"] == "3520"
        assert by_source["ClinVar"]["clinicalSignificance"] == "drug response"
        assert by_source["ClinGen"]["toId"].startswith("CA")
        assert all(
            {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"} <= m.keys()
            for m in maps
        )

    @pytest.mark.asyncio
    async def test_gene_mappings(self, adapter):
        with patch.object(adapter, "_make_request", router(GnomadGene=fx.GENE_BRCA1)):
            maps = await adapter.get_mappings("BRCA1")
        assert {(m["toSource"], m["toId"]) for m in maps} == {
            ("HGNC", "HGNC:1100"),
            ("NCBI", "672"),
            ("OMIM", "113705"),
            ("Ensembl", "ENSG00000012048"),
        }

    @pytest.mark.asyncio
    async def test_mapping_failures(self, adapter):
        with patch.object(adapter, "_make_request", router(GnomadGene=NOT_FOUND)):
            assert await adapter.get_mappings("NOPE") == []
        with patch.object(adapter, "_make_request", router(GnomadVariant={"data": {}})):
            assert await adapter.get_mappings("1-1-A-T") == []
        with patch.object(adapter, "_make_request", AsyncMock()) as mock:
            assert await adapter.get_mappings("not a thing!") == []
        mock.assert_not_awaited()
        with patch.object(adapter, "_make_request", router(GnomadVariant=OSError("x"))):
            assert await adapter.get_mappings("1-1-A-T") == []
        with patch.object(adapter, "_classify", side_effect=RuntimeError("x")):
            assert await adapter.get_mappings("BRCA1") == []
