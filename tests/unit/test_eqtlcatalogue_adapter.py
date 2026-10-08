"""Unit tests for EQTLCatalogueAdapter (dataset table of the eQTL Catalogue); no network."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import eqtlcatalogue_adapter
from knowledge_lookup.adapters.eqtlcatalogue_adapter import EQTLCatalogueAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.eqtlcatalogue_responses import DATASET_METADATA_TSV

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("EQTLCATALOGUE_RELEASE", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return EQTLCatalogueAdapter(lookup_config)


def table(text=DATASET_METADATA_TSV):
    return patch.object(EQTLCatalogueAdapter, "_make_request_text", AsyncMock(return_value=text))


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.EQTLCATALOGUE
        assert adapter.is_available() is True

    def test_release_selection(self, lookup_config, monkeypatch):
        default = EQTLCatalogueAdapter(lookup_config)
        assert default.release == "r7" and default.metadata_url.endswith("dataset_metadata_r7.tsv")
        monkeypatch.setenv("EQTLCATALOGUE_RELEASE", "R8_beta")
        beta = EQTLCatalogueAdapter(lookup_config)
        assert beta.release == "r8_beta" and beta.metadata_url.endswith("_r8_beta.tsv")
        monkeypatch.setenv("EQTLCATALOGUE_RELEASE", "r99")
        assert EQTLCatalogueAdapter(lookup_config).release == "r7"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("QTD000021", ("dataset", "QTD000021")),
            ("qtd000021", ("dataset", "QTD000021")),
            ("eqtlcatalogue:QTD000021", ("dataset", "QTD000021")),
            ("QTS000002", ("study", "QTS000002")),
            ("CL:0000235", ("term", "CL:0000235")),
            ("CL_0000235", ("term", "CL:0000235")),
            ("uberon_0000178", ("term", "UBERON:0000178")),
            ("EFO:0004905", ("term", "EFO:0004905")),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert EQTLCatalogueAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", "BRCA1", "ENSG00000012048", "rs123", "QTD1", None])
    def test_unsupported_ids(self, raw):
        assert EQTLCatalogueAdapter._parse_id(raw) is None

    def test_ontology_id_normalisation(self):
        assert eqtlcatalogue_adapter._ontology_id("UBERON_0000178") == "UBERON:0000178"
        assert eqtlcatalogue_adapter._ontology_id(" FOO_1 ") == "FOO_1"
        assert eqtlcatalogue_adapter._ontology_id("") == ""


class TestTable:
    @pytest.mark.asyncio
    async def test_table_is_cached(self, adapter):
        with table() as req:
            await adapter.search_concepts("blood")
            await adapter.get_concept_details("QTD000021")
        assert req.call_count == 1
        assert req.call_args.args[0] == adapter.metadata_url

    @pytest.mark.asyncio
    async def test_table_expires(self, adapter, monkeypatch):
        clock = {"now": 10.0}
        monkeypatch.setattr(
            eqtlcatalogue_adapter, "time", SimpleNamespace(monotonic=lambda: clock["now"])
        )
        with table() as req:
            await adapter._datasets()
            clock["now"] += eqtlcatalogue_adapter._CACHE_TTL + 1
            await adapter._datasets()
        assert req.call_count == 2

    @pytest.mark.asyncio
    async def test_unexpected_header_is_rejected(self, adapter):
        with table("<html>rate limited</html>"):
            assert await adapter.search_concepts("blood") == []
            assert await adapter.get_concept_details("QTD000021") is None
            assert await adapter.get_mappings("QTD000021") == []
            assert await adapter.get_relationships("QTD000021") == []

    @pytest.mark.asyncio
    async def test_download_failure_is_tolerated(self, adapter):
        failing = patch.object(
            EQTLCatalogueAdapter, "_make_request_text", AsyncMock(side_effect=RuntimeError("x"))
        )
        with failing:
            assert await adapter.search_concepts("blood") == []
            assert await adapter.get_concept_details("CL:0000235") is None
            assert await adapter.get_mappings("CL:0000235") == []
            assert await adapter.get_relationships("CL:0000235") == []

    @pytest.mark.asyncio
    async def test_rows_without_dataset_id_are_skipped(self, adapter):
        text = DATASET_METADATA_TSV + "QTS000099\t\tX\tx\tCL_1\tx\tnaive\t1\tge\t\tbulk\n"
        with table(text):
            rows = await adapter._datasets()
        assert len(rows) == 9


class TestSearch:
    @pytest.mark.asyncio
    async def test_tissue_study_then_datasets(self, adapter):
        with table():
            results = await adapter.search_concepts("macrophage", limit=20)
        ids = [c.primary_id for c in results]
        assert ids[0] == "CL:0000235" and results[0].concept_type == ConceptType.CELL_TYPE
        assert results[0].confidence_score == 0.9  # exact label
        assert ids[1] == "QTS000001" and results[1].concept_type == ConceptType.REFERENCE
        assert ids[2:] == ["QTD000001", "QTD000002", "QTD000003", "QTD000006"]
        assert results[2].concept_type == ConceptType.ASSAY
        assert len(set(ids)) == len(ids)

    @pytest.mark.asyncio
    async def test_all_tokens_must_match_including_condition_and_method(self, adapter):
        with table():
            results = await adapter.search_concepts("macrophage ifng", limit=20)
        assert {c.primary_id for c in results} == {"CL:0000235", "QTS000001", "QTD000006"}
        with table():
            results = await adapter.search_concepts("splice junction", limit=20)
        assert results == []  # no leafcutter dataset in the trimmed fixture
        with table():
            results = await adapter.search_concepts("protein aptamer", limit=20)
        assert [c.primary_id for c in results if c.concept_type == ConceptType.ASSAY] == [
            "QTD000584"
        ]

    @pytest.mark.asyncio
    async def test_search_by_pmid_and_ids(self, adapter):
        with table():
            by_pmid = await adapter.search_concepts("27863251")
            by_id = await adapter.search_concepts("QTD000356")
            by_term = await adapter.search_concepts("CL_0000235")
            missing = await adapter.search_concepts("QTD999999")
        assert "QTD000021" in {c.primary_id for c in by_pmid}
        assert [c.primary_id for c in by_id] == ["QTD000356"]
        assert [c.primary_id for c in by_term] == ["CL:0000235"]
        assert missing == []

    @pytest.mark.asyncio
    async def test_ontology_class_selects_type(self, adapter):
        with table():
            blood = (await adapter.search_concepts("blood", limit=1))[0]
        assert blood.primary_id == "UBERON:0000178"
        assert blood.concept_type == ConceptType.TISSUE
        summary = blood.source_data[KnowledgeSource.EQTLCATALOGUE]
        assert summary["n_datasets"] == 2 and summary["studies"] == ["QTS000015"]
        assert summary["quant_methods"] == ["exon", "ge"]

    @pytest.mark.asyncio
    async def test_limit_blank_and_gene_queries(self, adapter):
        with table():
            assert len(await adapter.search_concepts("macrophage", limit=2)) == 2
            assert await adapter.search_concepts("macrophage", limit=0) == []
            assert await adapter.search_concepts("   ") == []
            # genes / variants are not served any more: nothing matches
            assert await adapter.search_concepts("BRCA1") == []
            assert await adapter.search_concepts("rs4239702") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_dataset_details(self, adapter):
        with table():
            concept = await adapter.get_concept_details("qtd000021")
        assert concept.primary_id == "QTD000021"
        assert concept.primary_label == "BLUEPRINT - monocyte (naive, ge)"
        assert concept.confidence_score == 0.95
        assert "gene expression" in concept.definitions[0] and "n=191" in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.EQTLCATALOGUE]
        assert data["study_id"] == "QTS000002" and data["tissue_id"] == "CL:0002057"
        assert data["pmid"] == "27863251" and data["quant_method"] == "ge"
        assert data["sumstats_url"] == (
            "ftp://ftp.ebi.ac.uk/pub/databases/spot/eQTL/sumstats/QTS000002/"
            "QTD000021/QTD000021.all.tsv.gz"
        )

    @pytest.mark.asyncio
    async def test_no_sumstats_url_for_unverified_release_layout(self, lookup_config, monkeypatch):
        monkeypatch.setenv("EQTLCATALOGUE_RELEASE", "r8_beta")
        beta = EQTLCatalogueAdapter(lookup_config)
        with table():
            concept = await beta.get_concept_details("QTD000021")
        assert "sumstats_url" not in concept.source_data[KnowledgeSource.EQTLCATALOGUE]

    @pytest.mark.asyncio
    async def test_study_details(self, adapter):
        with table():
            concept = await adapter.get_concept_details("QTS000001")
        assert concept.primary_label == "Alasoo_2018" and concept.concept_type == "REFERENCE"
        data = concept.source_data[KnowledgeSource.EQTLCATALOGUE]
        assert data["n_datasets"] == 4 and data["tissues"] == ["macrophage"]
        assert data["conditions"] == ["IFNg_18h", "naive"] and data["study_type"] == "bulk"
        assert "4 datasets" in concept.definitions[0]

    @pytest.mark.asyncio
    async def test_single_cell_study_type(self, adapter):
        with table():
            concept = await adapter.get_concept_details("QTS000036")
        assert concept.source_data[KnowledgeSource.EQTLCATALOGUE]["study_type"] == "single-cell"

    @pytest.mark.asyncio
    async def test_tissue_details_accept_both_curie_forms(self, adapter):
        with table():
            a = await adapter.get_concept_details("CL:0000235")
            b = await adapter.get_concept_details("CL_0000235")
        assert a.primary_id == b.primary_id == "CL:0000235" and a.primary_label == "macrophage"

    @pytest.mark.asyncio
    async def test_unknown_ids(self, adapter):
        with table():
            assert await adapter.get_concept_details("QTD999999") is None
            assert await adapter.get_concept_details("QTS999999") is None
            assert await adapter.get_concept_details("UBERON:9999999") is None
            assert await adapter.get_concept_details("ENSG00000012048") is None
            assert await adapter.get_concept_details("") is None


class TestMappingsAndRelationships:
    @pytest.mark.asyncio
    async def test_dataset_mappings(self, adapter):
        with table():
            mappings = await adapter.get_mappings("QTD000021")
        assert [(m["toSource"], m["toId"]) for m in mappings] == [
            ("CL", "CL:0002057"),
            ("PMID", "PMID:27863251"),
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
            assert m["fromId"] == "QTD000021" and m["fromSource"] == "EQTLCATALOGUE"
            assert m["mappingType"] == "annotation"

    @pytest.mark.asyncio
    async def test_study_and_term_mappings(self, adapter):
        with table():
            study = await adapter.get_mappings("QTS000002")
            term = await adapter.get_mappings("UBERON_0000178")
        assert [m["toId"] for m in study] == ["PMID:27863251"]
        assert term[0]["toId"] == "UBERON:0000178" and term[0]["mappingType"] == "exact"
        assert term[0]["toSource"] == "UBERON"

    @pytest.mark.asyncio
    async def test_mappings_unknown(self, adapter):
        with table():
            assert await adapter.get_mappings("QTD999999") == []
            assert await adapter.get_mappings("QTS999999") == []
            assert await adapter.get_mappings("CL:9999999") == []
            assert await adapter.get_mappings("BRCA1") == []

    @pytest.mark.asyncio
    async def test_dataset_relationships(self, adapter):
        with table():
            rels = await adapter.get_relationships("QTD000006")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [
            ("part_of_study", "QTS000001"),
            ("profiled_in_tissue", "CL:0000235"),
            ("described_in", "PMID:29379200"),
        ]
        assert rels[1]["condition"] == "IFNg_18h" and rels[1]["source"] == "EQTLCATALOGUE"

    @pytest.mark.asyncio
    async def test_dataset_without_pmid_has_no_publication_edge(self, adapter):
        text = DATASET_METADATA_TSV.replace("29379200", "")
        with table(text):
            rels = await adapter.get_relationships("QTD000001")
        assert [r["relation_label"] for r in rels] == ["part_of_study", "profiled_in_tissue"]

    @pytest.mark.asyncio
    async def test_study_relationships(self, adapter):
        with table():
            rels = await adapter.get_relationships("QTS000001", limit=3)
        labels = [r["relation_label"] for r in rels]
        assert labels == ["profiles_tissue", "has_dataset", "has_dataset", "has_dataset"]
        assert rels[1]["related_id"] == "QTD000001"
        assert rels[1]["related_name"] == "Alasoo_2018 macrophage (ge)"

    @pytest.mark.asyncio
    async def test_tissue_relationships(self, adapter):
        with table():
            rels = await adapter.get_relationships("CL:0000235", limit=2)
        assert [r["relation_label"] for r in rels] == [
            "profiled_in_study",
            "has_dataset",
            "has_dataset",
        ]
        assert rels[0]["related_id"] == "QTS000001"

    @pytest.mark.asyncio
    async def test_relationship_limits_dedupe_and_unknowns(self, adapter):
        with table():
            tissue_rels = await adapter.get_relationships("UBERON:0000178", limit=1)
            assert [r["related_id"] for r in tissue_rels] == ["QTS000015", "QTD000356"]
            assert await adapter.get_relationships("QTD000021", limit=0) == []
            assert await adapter.get_relationships("QTD999999") == []
            assert await adapter.get_relationships("QTS999999") == []
            assert await adapter.get_relationships("CL:9999999") == []
            assert await adapter.get_relationships("BRCA1") == []

    @pytest.mark.asyncio
    async def test_study_with_two_tissues_lists_each_once(self, adapter):
        text = DATASET_METADATA_TSV + (
            "QTS000001\tQTD000900\tAlasoo_2018\tx\tUBERON_0000178\tblood\tnaive\t5\tge\t1\tbulk\n"
        )
        with table(text):
            rels = await adapter.get_relationships("QTS000001", limit=10)
        tissues = [r["related_id"] for r in rels if r["relation_label"] == "profiles_tissue"]
        assert tissues == ["CL:0000235", "UBERON:0000178"]
