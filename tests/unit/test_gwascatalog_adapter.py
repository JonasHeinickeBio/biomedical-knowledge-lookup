"""Unit tests for GWASCatalogAdapter (fixtures are real, trimmed REST API v2 responses)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.gwascatalog_adapter import (
    GWASCatalogAdapter,
    _curie,
    _normalize_id,
)
from knowledge_lookup.models import KnowledgeSource
from tests.fixtures import gwascatalog_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter(lookup_config):
    return GWASCatalogAdapter(lookup_config)


def route(mapping):
    """AsyncMock side effect answering by URL suffix (and the filter params)."""

    async def _request(url, params=None, headers=None, json_data=None):
        for key, value in mapping.items():
            if url.endswith(key[0]) and all((params or {}).get(k) == v for k, v in key[1]):
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"unexpected request {url} {params}")

    return _request


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.GWASCATALOG
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("rs1801270", ("variant", "rs1801270")),
            ("RS1801270", ("variant", "rs1801270")),
            ("MONDO_0005404", ("trait", "MONDO_0005404")),
            ("mondo:0005404", ("trait", "MONDO_0005404")),
            ("EFO:0004540", ("trait", "EFO_0004540")),
            ("hp_0012378", ("trait", "HP_0012378")),
            ("orphanet_5304", ("trait", "Orphanet_5304")),
            ("GWASCATALOG:rs1801270", ("variant", "rs1801270")),
            ("fatigue", None),
            ("", None),
            ("rs", None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert _normalize_id(raw) == expected

    def test_curie(self):
        assert _curie("MONDO_0005404") == "MONDO:0005404"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_traits_ranks_exact_first(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=fx.SEARCH_FATIGUE)
        ) as mock:
            concepts = await adapter.search_concepts("fatigue", limit=5)
        assert [c.primary_id for c in concepts] == ["HP:0012378", "MONDO:0005404"]
        assert concepts[0].concept_type == "PHENOTYPE"
        assert concepts[1].concept_type == "DISEASE"
        assert concepts[1].primary_label.endswith("chronic fatigue syndrome")
        params = mock.call_args.args[1]
        assert params["efo_trait"] == "fatigue"

    @pytest.mark.asyncio
    async def test_search_respects_limit_and_dedupes(self, adapter):
        page = copy.deepcopy(fx.SEARCH_FATIGUE)
        items = page["_embedded"]["efo_traits"]
        items.append(dict(items[0]))  # duplicate id
        with patch.object(adapter, "_make_request", AsyncMock(return_value=page)):
            assert len(await adapter.search_concepts("fatigue", limit=1)) == 1
            assert len(await adapter.search_concepts("fatigue", limit=10)) == 2

    @pytest.mark.asyncio
    async def test_search_skips_unusable_items(self, adapter):
        page = {
            "_embedded": {
                "efo_traits": [{"efo_id": "bad id", "efo_trait": "x"}, {"efo_id": "EFO_1"}]
            }
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=page)):
            assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_search_empty_and_invalid(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.EMPTY_PAGE)):
            assert await adapter.search_concepts("zzzzqq") == []
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts("fatigue", limit=0) == []

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("fatigue") == []

    @pytest.mark.asyncio
    async def test_search_by_identifier_delegates_to_details(self, adapter):
        mapping = {
            ("/single-nucleotide-polymorphisms/rs1801270", ()): fx.SNP_RS1801270,
        }
        with patch.object(adapter, "_make_request", route(mapping)):
            concepts = await adapter.search_concepts("rs1801270")
        assert [c.primary_id for c in concepts] == ["rs1801270"]
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.search_concepts("EFO_0004540") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_trait_details_with_counts(self, adapter):
        mapping = {
            ("/efo-traits/MONDO_0005404", ()): fx.TRAIT_MECFS,
            ("/studies", (("efo_id", "MONDO_0005404"),)): fx.STUDIES_MECFS_COUNT,
            ("/associations", (("efo_id", "MONDO_0005404"),)): fx.ASSOCIATIONS_MECFS_COUNT,
        }
        with patch.object(adapter, "_make_request", route(mapping)):
            concept = await adapter.get_concept_details("MONDO:0005404")
        assert concept.primary_id == "MONDO:0005404"
        assert concept.concept_type == "DISEASE"
        assert any("19 GWAS Catalog studies and 9 associations" in d for d in concept.definitions)
        raw = concept.source_data[KnowledgeSource.GWASCATALOG]
        assert raw["gwas_counts"] == {"studies": 19, "associations": 9}
        assert "gwas_trait" in concept.categories

    @pytest.mark.asyncio
    async def test_trait_details_survive_count_failure(self, adapter):
        mapping = {
            ("/efo-traits/MONDO_0005404", ()): fx.TRAIT_MECFS,
            ("/studies", (("efo_id", "MONDO_0005404"),)): RuntimeError("down"),
            ("/associations", (("efo_id", "MONDO_0005404"),)): fx.ASSOCIATIONS_MECFS_COUNT,
        }
        with patch.object(adapter, "_make_request", route(mapping)):
            concept = await adapter.get_concept_details("MONDO_0005404")
        assert concept is not None
        assert "gwas_counts" not in concept.source_data[KnowledgeSource.GWASCATALOG]

    @pytest.mark.asyncio
    async def test_variant_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.SNP_RS1801270)):
            concept = await adapter.get_concept_details("rs1801270")
        assert concept.primary_id == "rs1801270"
        assert concept.concept_type == "MOLECULAR_ENTITY"
        text = concept.definitions[0]
        assert "missense_variant" in text and "chr6:36684194" in text and "CDKN1A" in text
        assert "missense_variant" in concept.semantic_types

    @pytest.mark.asyncio
    async def test_variant_without_location_fields(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"rs_id": "rs5"})):
            concept = await adapter.get_concept_details("rs5")
        assert concept.primary_id == "rs5" and concept.definitions == []

    @pytest.mark.asyncio
    async def test_details_bad_input_and_errors(self, adapter):
        assert await adapter.get_concept_details("not an id") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.get_concept_details("MONDO_0005404") is None
            assert await adapter.get_concept_details("rs1801270") is None
        with patch.object(adapter, "_make_request", AsyncMock(return_value=["not", "a", "dict"])):
            assert await adapter.get_concept_details("MONDO_0005404") is None
            assert await adapter.get_concept_details("rs1801270") is None
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"efo_id": "X"})):
            assert await adapter.get_concept_details("MONDO_0005404") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_trait_to_variants(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=fx.ASSOCIATIONS_MECFS)
        ) as mock:
            edges = await adapter.get_relationships("MONDO:0005404", limit=3)
        assert [e["related_id"] for e in edges] == ["rs141691232", "rs190241717", "rs189511601"]
        first = edges[0]
        assert first["relation_label"] == "associated_variant"
        assert first["source"] == "GWASCATALOG"
        assert first["p_value"] == pytest.approx(6e-13)
        assert first["risk_allele"] == "rs141691232-G"
        assert first["mapped_genes"] == ["LINC01419", "TPM3P3"]
        assert first["study_accession"] == "GCST90480593"
        assert first["pmid"] == "39024449"
        params = mock.call_args.args[1]
        assert params["efo_id"] == "MONDO_0005404"
        assert params["sort"] == "p_value" and params["direction"] == "asc"

    @pytest.mark.asyncio
    async def test_trait_edges_capped_by_limit(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.ASSOCIATIONS_MECFS)):
            edges = await adapter.get_relationships("MONDO_0005404", limit=2)
        assert len(edges) == 2

    @pytest.mark.asyncio
    async def test_trait_pagination_and_dedup(self, adapter):
        page0 = copy.deepcopy(fx.ASSOCIATIONS_MECFS)
        page0["page"] = {"size": 3, "totalElements": 6, "totalPages": 2, "number": 0}
        page1 = copy.deepcopy(fx.ASSOCIATIONS_MECFS)  # same SNPs again -> deduplicated
        page1["page"] = {"size": 3, "totalElements": 6, "totalPages": 2, "number": 1}
        extra = copy.deepcopy(page1["_embedded"]["associations"][0])
        extra["snp_allele"] = [{"rs_id": "rs999", "effect_allele": "?"}]
        page1["_embedded"]["associations"].append(extra)
        mock = AsyncMock(side_effect=[page0, page1])
        with patch.object(adapter, "_make_request", mock):
            edges = await adapter.get_relationships("MONDO_0005404", limit=4)
        assert [e["related_id"] for e in edges][-1] == "rs999"
        assert edges[-1]["effect_allele"] is None and edges[-1]["risk_allele"] is None
        assert len(edges) == 4 and mock.await_count == 2

    @pytest.mark.asyncio
    async def test_variant_to_traits_and_genes(self, adapter):
        mapping = {
            ("/single-nucleotide-polymorphisms/rs1801270", ()): fx.SNP_RS1801270,
            ("/associations", (("rs_id", "rs1801270"),)): fx.ASSOCIATIONS_RS1801270,
        }
        with patch.object(adapter, "_make_request", route(mapping)):
            edges = await adapter.get_relationships("rs1801270")
        traits = [e for e in edges if e["relation_label"] == "associated_trait"]
        genes = [e for e in edges if e["relation_label"] == "mapped_gene"]
        # two studies report the same trait: one edge, best p-value
        assert len(traits) == 1
        assert traits[0]["related_id"] == "EFO:0005763"
        assert traits[0]["related_name"] == "pulse pressure measurement"
        assert traits[0]["p_value"] == pytest.approx(2e-8)
        assert traits[0]["risk_allele"] == "rs1801270-A"
        assert [g["related_id"] for g in genes] == ["CDKN1A"]
        assert genes[0]["functional_class"] == "missense_variant"

    @pytest.mark.asyncio
    async def test_variant_traits_survive_snp_failure(self, adapter):
        mapping = {
            ("/single-nucleotide-polymorphisms/rs1801270", ()): RuntimeError("500"),
            ("/associations", (("rs_id", "rs1801270"),)): fx.ASSOCIATIONS_RS1801270,
        }
        with patch.object(adapter, "_make_request", route(mapping)):
            edges = await adapter.get_relationships("rs1801270")
        assert [e["relation_label"] for e in edges] == ["associated_trait"]

    @pytest.mark.asyncio
    async def test_variant_association_failure_returns_empty(self, adapter):
        mapping = {
            ("/single-nucleotide-polymorphisms/rs1801270", ()): fx.SNP_RS1801270,
            ("/associations", (("rs_id", "rs1801270"),)): RuntimeError("500"),
        }
        with patch.object(adapter, "_make_request", route(mapping)):
            assert await adapter.get_relationships("rs1801270") == []

    @pytest.mark.asyncio
    async def test_relationship_edge_cases(self, adapter):
        assert await adapter.get_relationships("nonsense") == []
        assert await adapter.get_relationships("MONDO_0005404", limit=0) == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.EMPTY_PAGE)):
            assert await adapter.get_relationships("MONDO_0100233") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("MONDO_0005404") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_trait_mapping(self, adapter):
        (m,) = await adapter.get_mappings("MONDO_0005404")
        assert m == {
            "fromId": "MONDO:0005404",
            "toId": "MONDO:0005404",
            "fromSource": "GWASCATALOG",
            "toSource": "MONDO",
            "mappingType": "sameAs",
            "confidence": 1.0,
        }
        assert (await adapter.get_mappings("HP:0012378"))[0]["toSource"] == "HPO"
        assert (await adapter.get_mappings("EFO_0004540"))[0]["toSource"] == "EFO"
        assert (await adapter.get_mappings("FOO_1"))[0]["toSource"] == "FOO"

    @pytest.mark.asyncio
    async def test_variant_mapping_and_invalid(self, adapter):
        (m,) = await adapter.get_mappings("rs1801270")
        assert m["toSource"] == "dbSNP" and m["toId"] == "rs1801270"
        assert await adapter.get_mappings("junk") == []
