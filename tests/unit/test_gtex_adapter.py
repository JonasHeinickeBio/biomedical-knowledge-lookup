"""Unit tests for GTExAdapter (GTEx Portal API v2); no network."""

import copy
import math
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import gtex_adapter
from knowledge_lookup.adapters.gtex_adapter import GTExAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.gtex_responses import (
    EQTL_PAGE0,
    EQTL_PAGE1,
    GENE_SEARCH_BRCA,
    GENE_SEARCH_BRCA1,
    GENE_SEARCH_EMPTY,
    MEDIAN_BRCA1,
)

pytestmark = pytest.mark.unit

ENSG = "ENSG00000012048"


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(gtex_adapter, "_MIN_INTERVAL", 0.0)
    monkeypatch.delenv("GTEX_DATASET_ID", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return GTExAdapter(lookup_config)


def router(genes=GENE_SEARCH_BRCA1, medians=MEDIAN_BRCA1, eqtl_pages=(EQTL_PAGE0, EQTL_PAGE1)):
    """Fake ``_make_request`` answering by endpoint; eQTL pages by the ``page`` param."""

    async def fake(url, params=None, headers=None, json_data=None):
        if url.endswith("reference/geneSearch"):
            return copy.deepcopy(genes)
        if url.endswith("expression/medianGeneExpression"):
            if isinstance(medians, Exception):
                raise medians
            return copy.deepcopy(medians)
        if url.endswith("association/singleTissueEqtl"):
            if isinstance(eqtl_pages, Exception):
                raise eqtl_pages
            return copy.deepcopy(eqtl_pages[min(params["page"], len(eqtl_pages) - 1)])
        raise AssertionError(f"unexpected URL {url}")

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.GTEX
        assert adapter.is_available() is True

    def test_default_dataset_and_override(self, lookup_config, monkeypatch):
        assert GTExAdapter(lookup_config).dataset_id == "gtex_v10"
        assert GTExAdapter(lookup_config).gencode_version == "v39"
        monkeypatch.setenv("GTEX_DATASET_ID", "gtex_v8")
        v8 = GTExAdapter(lookup_config)
        assert (v8.dataset_id, v8.gencode_version) == ("gtex_v8", "v26")
        monkeypatch.setenv("GTEX_DATASET_ID", "gtex_v99")
        assert GTExAdapter(lookup_config).dataset_id == "gtex_v10"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ENSG00000012048", ("ensembl", ENSG)),
            ("ensg00000012048.23", ("ensembl", ENSG)),
            ("ENSEMBL:ENSG00000012048.20", ("ensembl", ENSG)),
            ("GTEx:ENSG00000012048", ("ensembl", ENSG)),
            ("BRCA1", ("symbol", "BRCA1")),
            ("  il6 ", ("symbol", "il6")),
            ("HLA-DRB1", ("symbol", "HLA-DRB1")),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert GTExAdapter._parse_gene_id(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["", "  ", "672", "HGNC:1100", "NCBIGene:672", "GeneID:672", "two words", None]
    )
    def test_unsupported_ids(self, raw):
        assert GTExAdapter._parse_gene_id(raw) is None

    def test_tau_and_labels(self):
        assert GTExAdapter_tau([1.0, 1.0, 1.0]) == pytest.approx(0.0)
        assert GTExAdapter_tau([10.0, 0.0, 0.0]) == pytest.approx(1.0)
        assert GTExAdapter_tau([0.0, 0.0]) is None
        assert GTExAdapter_tau([5.0]) is None
        assert gtex_adapter._specificity_label(0.9) == "tissue-specific"
        assert gtex_adapter._specificity_label(0.6) == "intermediate"
        assert gtex_adapter._specificity_label(0.2) == "broadly expressed"
        assert gtex_adapter._specificity_label(None) is None


def GTExAdapter_tau(values):
    return gtex_adapter._tau(values)


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_ranks_exact_symbol_first(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_BRCA))
        ) as req:
            results = await adapter.search_concepts("brca1", limit=10)
        params = req.call_args.args[1]
        assert params["geneId"] == "brca1" and params["gencodeVersion"] == "v39"
        assert params["genomeBuild"] == "GRCh38/hg38"
        assert results[0].primary_label == "BRCA1" and results[0].confidence_score == 0.95
        assert {c.primary_label for c in results} == {"BRCA1", "BRCA2", "BRCA1P1"}
        assert all(c.concept_type == ConceptType.GENE for c in results)
        # protein-coding genes come before the pseudogene among non-exact hits
        assert [c.primary_label for c in results][-1] == "BRCA1P1"
        assert results[1].confidence_score < results[0].confidence_score

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_BRCA))
        ) as req:
            results = await adapter.search_concepts("BRCA", limit=2)
        assert len(results) == 2
        assert req.call_args.args[1]["itemsPerPage"] == 2

    @pytest.mark.asyncio
    async def test_search_by_ensembl_id(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            results = await adapter.search_concepts("ENSG00000012048.20")
        assert req.call_args.args[1]["geneId"] == ENSG
        assert [c.primary_id for c in results] == [ENSG]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query,limit",
        [("", 5), ("  ", 5), ("BRCA1", 0), (None, 5), ("breast cancer", 5), ("672", 5)],
    )
    async def test_search_unsearchable_inputs(self, adapter, query, limit):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            assert await adapter.search_concepts(query, limit) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_empty_malformed_and_error(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_EMPTY))
        ):
            assert await adapter.search_concepts("zzz") == []
        for payload in ([], {"data": None}, {"data": [{"geneSymbol": "X"}, "junk"]}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("zzz") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("BRCA1") == []

    @pytest.mark.asyncio
    async def test_search_deduplicates(self, adapter):
        gene = GENE_SEARCH_BRCA1["data"][0]
        payload = {"data": [gene, copy.deepcopy(gene)]}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            assert len(await adapter.search_concepts("BRCA1")) == 1


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_content(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            concept = await adapter.get_concept_details("BRCA1")
        assert concept.primary_id == ENSG and concept.primary_label == "BRCA1"
        assert concept.concept_type == ConceptType.GENE
        assert concept.definitions == ["BRCA1 DNA repair associated"]  # [Source:HGNC ...] removed
        assert concept.categories == ["protein coding"]
        identifiers = {i.identifier for i in concept.identifiers}
        assert {ENSG, f"{ENSG}.23", "NCBIGene:672"} <= identifiers
        data = concept.source_data[KnowledgeSource.GTEX]
        assert data["dataset"] == "gtex_v10" and data["gencode_id"] == f"{ENSG}.23"
        assert data["entrez_gene_id"] == 672 and data["chromosome"] == "chr17"
        assert data["top_tissues_tpm"][0] == {
            "tissue": "Cells_EBV-transformed_lymphocytes",
            "tpm": 20.935,
        }
        assert len(data["top_tissues_tpm"]) == 10
        assert data["n_tissues"] == 12 and data["n_tissues_expressed"] >= 5
        assert data["max_tpm"] == 20.935
        assert 0 < data["tau"] <= 1 and data["tissue_specificity"] in {
            "tissue-specific",
            "intermediate",
            "broadly expressed",
        }
        # one gene lookup and one expression request
        assert req.call_count == 2
        assert req.call_args.args[1]["gencodeId"] == f"{ENSG}.23"
        assert req.call_args.args[1]["datasetId"] == "gtex_v10"

    @pytest.mark.asyncio
    async def test_details_by_wrongly_versioned_ensembl_id(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            concept = await adapter.get_concept_details("ENSG00000012048.20")
        assert concept.primary_id == ENSG

    @pytest.mark.asyncio
    async def test_details_symbol_needs_exact_match(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_BRCA))
        ):
            assert (await adapter.get_concept_details("brca2")).primary_label == "BRCA2"
            assert await adapter.get_concept_details("BRC") is None

    @pytest.mark.asyncio
    async def test_details_without_expression_data(self, adapter):
        empty = {"data": [], "paging_info": {}}
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router(medians=empty))):
            concept = await adapter.get_concept_details("BRCA1")
        assert concept is not None
        assert "top_tissues_tpm" not in concept.source_data[KnowledgeSource.GTEX]

    @pytest.mark.asyncio
    async def test_details_ignores_unusable_expression_rows(self, adapter):
        bad = {"data": [{"tissueSiteDetailId": "X", "median": "n/a"}, {"median": 1.0}, "junk"]}
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router(medians=bad))):
            concept = await adapter.get_concept_details("BRCA1")
        assert "n_tissues" not in concept.source_data[KnowledgeSource.GTEX]

    @pytest.mark.asyncio
    async def test_details_all_zero_expression(self, adapter):
        zero = {"data": [{"tissueSiteDetailId": t, "median": 0.0} for t in ("A", "B")]}
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router(medians=zero))):
            concept = await adapter.get_concept_details("BRCA1")
        data = concept.source_data[KnowledgeSource.GTEX]
        assert data["tau"] is None and data["tissue_specificity"] is None
        assert data["n_tissues_expressed"] == 0

    @pytest.mark.asyncio
    async def test_details_missing_invalid_and_error(self, adapter):
        assert await adapter.get_concept_details("") is None
        assert await adapter.get_concept_details("672") is None
        assert await adapter.get_concept_details("HGNC:1100") is None
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_EMPTY))
        ):
            assert await adapter.get_concept_details("ZZZ1") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("BRCA1") is None

    @pytest.mark.asyncio
    async def test_details_gene_record_without_symbol(self, adapter):
        payload = {"data": [{"gencodeId": "ENSG00000000001.1", "geneSymbol": ""}]}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            assert await adapter.get_concept_details("ENSG00000000001") is None

    def test_gene_without_symbol_or_id(self, adapter):
        assert adapter._gene_to_concept({"gencodeId": "ENSG1.1"}) is None
        assert adapter._gene_to_concept({"geneSymbol": "X"}) is None
        bare = adapter._gene_to_concept({"gencodeId": "ENSG00000000001.1", "geneSymbol": "X"})
        assert bare.primary_id == "ENSG00000000001" and bare.definitions == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            mappings = await adapter.get_mappings("ENSG00000012048")
        by_to = {m["toId"]: m for m in mappings}
        assert set(by_to) == {
            "NCBIGene:672",
            "HGNC:1100",
            f"ENSEMBL:{ENSG}.23",
            "HGNC.SYMBOL:BRCA1",
        }
        assert by_to["NCBIGene:672"] == {
            "fromId": ENSG,
            "toId": "NCBIGene:672",
            "fromSource": "ENSEMBL",
            "toSource": "NCBIGene",
            "mappingType": "exact",
            "confidence": 0.95,
        }
        assert by_to[f"ENSEMBL:{ENSG}.23"]["mappingType"] == "version"

    @pytest.mark.asyncio
    async def test_mappings_minimal_gene(self, adapter):
        payload = {"data": [{"gencodeId": "ENSG00000000001.1", "geneSymbol": ""}]}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            mappings = await adapter.get_mappings("ENSG00000000001")
        assert [m["toId"] for m in mappings] == ["ENSEMBL:ENSG00000000001.1"]

    @pytest.mark.asyncio
    async def test_mappings_failures(self, adapter):
        assert await adapter.get_mappings("672") == []
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_EMPTY))
        ):
            assert await adapter.get_mappings("ZZZ1") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("BRCA1") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_tissues_and_eqtls(self, adapter):
        adapter.eqtl_max_pages = 2  # the fixture holds two (trimmed) pages
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            rels = await adapter.get_relationships("BRCA1", limit=3)
        tissues = [r for r in rels if r["relation_label"] == "expressed_in"]
        eqtls = [r for r in rels if r["relation_label"] == "has_eqtl_variant"]
        assert [r["rank"] for r in tissues] == [1, 2, 3]
        assert tissues[0]["related_name"] == "Cells_EBV-transformed_lymphocytes"
        assert tissues[0]["related_id"] == "EFO:0000572"
        assert tissues[0]["unit"] == "TPM" and tissues[0]["median_tpm"] == 20.935
        assert tissues[0]["dataset"] == "gtex_v10" and tissues[0]["source"] == "GTEX"
        assert [r["median_tpm"] for r in tissues] == sorted(
            (r["median_tpm"] for r in tissues), reverse=True
        )
        assert len(eqtls) == 3
        p_values = [r["p_value"] for r in eqtls]
        assert p_values == sorted(p_values)  # most significant first, across both pages
        best = eqtls[0]
        assert best["related_id"].startswith("rs") and best["related_name"].startswith("chr17_")
        assert best["tissue"] and best["slope"] is not None and best["position"]
        assert best["rows_scanned"] == 7 and best["rows_total"] == 1742
        assert best["truncated"] is True  # fixture pages hold fewer rows than the total

    @pytest.mark.asyncio
    async def test_eqtl_scan_stops_at_last_page_and_respects_page_cap(self, adapter):
        single = copy.deepcopy(EQTL_PAGE0)
        single["paging_info"] = {"numberOfPages": 1, "totalNumberOfItems": 3, "page": 0}
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(eqtl_pages=[single]))
        ) as req:
            rels = await adapter.get_relationships("BRCA1", limit=10)
        eqtl_calls = [c for c in req.call_args_list if c.args[0].endswith("singleTissueEqtl")]
        assert len(eqtl_calls) == 1
        assert eqtl_calls[0].args[1]["itemsPerPage"] == 250
        eqtls = [r for r in rels if r["relation_label"] == "has_eqtl_variant"]
        assert len(eqtls) == 3 and eqtls[0]["truncated"] is False

        adapter.eqtl_max_pages = 1
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            await adapter.get_relationships("BRCA1", limit=10)
        eqtl_calls = [c for c in req.call_args_list if c.args[0].endswith("singleTissueEqtl")]
        assert len(eqtl_calls) == 1

    @pytest.mark.asyncio
    async def test_eqtl_dedup_and_variant_fallback(self, adapter):
        row = copy.deepcopy(EQTL_PAGE0["data"][0])
        no_rsid = {**row, "snpId": None, "pValue": 1e-30, "variantId": "chr1_1_A_G_b38"}
        bad_slope = {
            **row,
            "snpId": "rs1",
            "nes": None,
            "pValue": 1e-20,
            "tissueSiteDetailId": "T",
        }
        page = {
            "data": [row, copy.deepcopy(row), no_rsid, bad_slope, {"pValue": "x"}, "junk"],
            "paging_info": {"numberOfPages": 1, "totalNumberOfItems": 4, "page": 0},
        }
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(eqtl_pages=[page]))
        ):
            rels = await adapter.get_relationships("BRCA1", limit=10)
        eqtls = [r for r in rels if r["relation_label"] == "has_eqtl_variant"]
        assert [r["related_id"] for r in eqtls] == ["chr1_1_A_G_b38", "rs1", row["snpId"]]
        assert eqtls[1]["slope"] is None
        # a row without any identifier is skipped
        empty_row = {"pValue": 0.5, "tissueSiteDetailId": "T"}
        page["data"] = [empty_row]
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(eqtl_pages=[page]))
        ):
            rels = await adapter.get_relationships("BRCA1")
        assert not [r for r in rels if r["relation_label"] == "has_eqtl_variant"]

    @pytest.mark.asyncio
    async def test_expression_threshold(self, adapter):
        low = {
            "data": [
                {"tissueSiteDetailId": "Liver", "median": 0.4, "ontologyId": "UBERON:1"},
                {"tissueSiteDetailId": "Lung", "median": 3.0},
            ]
        }
        with patch.object(
            adapter,
            "_make_request",
            AsyncMock(side_effect=router(medians=low, eqtl_pages=[{"data": []}])),
        ):
            rels = await adapter.get_relationships("BRCA1")
        assert [(r["related_name"], r["related_id"]) for r in rels] == [("Lung", "Lung")]

    @pytest.mark.asyncio
    async def test_partial_failures_degrade(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            AsyncMock(side_effect=router(medians=RuntimeError("down"))),
        ):
            rels = await adapter.get_relationships("BRCA1", limit=2)
        assert {r["relation_label"] for r in rels} == {"has_eqtl_variant"}
        with patch.object(
            adapter,
            "_make_request",
            AsyncMock(side_effect=router(eqtl_pages=RuntimeError("down"))),
        ):
            rels = await adapter.get_relationships("BRCA1", limit=2)
        assert {r["relation_label"] for r in rels} == {"expressed_in"}

    @pytest.mark.asyncio
    async def test_relationship_edge_cases(self, adapter):
        assert await adapter.get_relationships("BRCA1", limit=0) == []
        assert await adapter.get_relationships("672") == []
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(genes=GENE_SEARCH_EMPTY))
        ):
            assert await adapter.get_relationships("ZZZ1") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("BRCA1") == []


class TestHttp:
    @pytest.mark.asyncio
    async def test_get_returns_empty_dict_for_non_dict(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[1, 2])):
            assert await adapter._get("reference/gene", {}) == {}

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(gtex_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(gtex_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._get("a", {})
            await adapter._get("b", {})
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6

    def test_tau_is_a_probability(self):
        values = [e["median"] for e in MEDIAN_BRCA1["data"]]
        assert 0 <= gtex_adapter._tau(values) <= 1 and not math.isnan(gtex_adapter._tau(values))
