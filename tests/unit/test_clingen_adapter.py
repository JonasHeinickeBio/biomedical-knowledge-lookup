"""Unit tests for ClinGenAdapter, run on rows of the real ClinGen CSV exports.

Nothing is downloaded: the CSVs come from tests/fixtures/clingen_responses.py (trimmed real
rows) and are written to tmp_path; the download path is tested with a patched ensure_dataset.
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import clingen_adapter
from knowledge_lookup.adapters.clingen_adapter import (
    ClinGenAdapter,
    parse_dosage_csv,
    parse_validity_csv,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import clingen_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture
def files(tmp_path):
    validity = tmp_path / "validity.csv"
    dosage = tmp_path / "dosage.csv"
    validity.write_text(fx.VALIDITY_CSV, encoding="utf-8")
    dosage.write_text(fx.DOSAGE_CSV, encoding="utf-8")
    return validity, dosage


@pytest.fixture
def adapter(lookup_config, files, monkeypatch):
    monkeypatch.setenv("CLINGEN_PATH", str(files[0]))
    monkeypatch.setenv("CLINGEN_DOSAGE_PATH", str(files[1]))
    return ClinGenAdapter(lookup_config)


class TestParser:
    def test_validity_rows(self, files):
        index = parse_validity_csv(files[0])
        assert len(index.curations) == 16
        row = next(c for c in index.by_gene["HGNC:1100"] if c.moi == "AD")
        assert row.disease_label == "BRCA1-related cancer predisposition"
        assert row.mondo_id == "MONDO:0700268" and row.classification == "Definitive"
        assert row.date == "2024-08-29" and row.sop == "SOP10"
        assert row.expert_panel == "Hereditary Cancer Gene Curation Expert Panel"
        assert row.report_url.startswith("https://search.clinicalgenome.org/kb/gene-validity/")
        assert index.symbol_ids["BRCA1"] == "HGNC:1100"
        assert index.disease_labels["MONDO:0010543"] == "Barth syndrome"

    def test_dosage_rows_and_dosage_only_genes(self, files):
        index = parse_validity_csv(files[0])
        parse_dosage_csv(files[1], index)
        assert index.dosage["HGNC:1100"].haploinsufficiency.startswith("Sufficient Evidence")
        assert index.dosage["HGNC:1100"].date == "2021-09-23"
        assert "HGNC:18149" in index.gene_symbols and "HGNC:18149" not in index.by_gene

    def test_garbage_and_short_rows(self, tmp_path):
        path = tmp_path / "x.csv"
        path.write_text(
            '"title"\n"GENE SYMBOL","a"\n"+++","+"\n"X","HGNC:1"\n"Y","nope","a","b"\n'
        )
        assert parse_validity_csv(path).curations == []
        index = parse_validity_csv(path)
        parse_dosage_csv(path, index)
        assert index.dosage == {}
        no_header = tmp_path / "y.csv"
        no_header.write_text('"a","b"\n')
        assert parse_validity_csv(no_header).curations == []


class TestAvailability:
    def test_source(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CLINGEN

    def test_path_cache_and_download_switches(self, lookup_config, tmp_path, monkeypatch):
        for name in ("CLINGEN_PATH", "CLINGEN_DOWNLOAD", "KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path))
        adapter = ClinGenAdapter(lookup_config)
        assert adapter.is_available() is False
        monkeypatch.setenv("CLINGEN_DOWNLOAD", "1")
        assert adapter.is_available() is True
        monkeypatch.delenv("CLINGEN_DOWNLOAD")
        (tmp_path / clingen_adapter.VALIDITY_FILENAME).write_text("x")
        assert adapter.is_available() is True
        monkeypatch.setenv("CLINGEN_PATH", str(tmp_path / "missing.csv"))
        assert adapter.is_available() is False
        monkeypatch.setenv("CLINGEN_PATH", str(tmp_path / clingen_adapter.VALIDITY_FILENAME))
        assert adapter.is_available() is True


class TestLoading:
    @pytest.mark.asyncio
    async def test_download_path_uses_dataset_cache_once(self, lookup_config, files, monkeypatch):
        monkeypatch.delenv("CLINGEN_PATH", raising=False)
        monkeypatch.delenv("CLINGEN_DOSAGE_PATH", raising=False)
        adapter = ClinGenAdapter(lookup_config)
        by_url = {clingen_adapter.VALIDITY_URL: files[0], clingen_adapter.DOSAGE_URL: files[1]}
        fake = AsyncMock(side_effect=lambda url, **kw: by_url[url])
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", fake):
            await adapter.search_concepts("BRCA1")
            await adapter.search_concepts("FBN1")
        assert fake.await_count == 2  # validity + dosage, only on the first call
        assert fake.await_args_list[0].kwargs["filename"] == clingen_adapter.VALIDITY_FILENAME
        assert adapter._index.dosage

    @pytest.mark.asyncio
    async def test_local_validity_path_never_downloads_dosage(
        self, lookup_config, files, monkeypatch
    ):
        monkeypatch.setenv("CLINGEN_PATH", str(files[0]))
        monkeypatch.delenv("CLINGEN_DOSAGE_PATH", raising=False)
        adapter = ClinGenAdapter(lookup_config)
        fake = AsyncMock()
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", fake):
            assert await adapter.search_concepts("BRCA1")
        fake.assert_not_awaited()
        assert adapter._index.dosage == {}

    @pytest.mark.asyncio
    async def test_dosage_failure_is_not_fatal(self, lookup_config, files, monkeypatch):
        monkeypatch.setenv("CLINGEN_PATH", str(files[0]))
        monkeypatch.setenv("CLINGEN_DOSAGE_PATH", str(files[0].parent / "nope.csv"))
        adapter = ClinGenAdapter(lookup_config)
        assert await adapter.get_concept_details("HGNC:1100")
        assert adapter._index.dosage == {}
        monkeypatch.delenv("CLINGEN_DOSAGE_PATH")
        monkeypatch.setenv("CLINGEN_DOSAGE_PATH", str(files[1]))
        with patch.object(clingen_adapter, "parse_dosage_csv", side_effect=ValueError("bad")):
            other = ClinGenAdapter(lookup_config)
            assert await other.get_concept_details("HGNC:1100")

    @pytest.mark.asyncio
    async def test_load_failure_degrades_and_retries(self, lookup_config, monkeypatch, tmp_path):
        monkeypatch.setenv("CLINGEN_PATH", str(tmp_path / "missing.csv"))
        adapter = ClinGenAdapter(lookup_config)
        assert await adapter.search_concepts("BRCA1") == []
        assert await adapter.get_concept_details("BRCA1") is None
        assert await adapter.get_relationships("BRCA1") == []
        assert adapter._index is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_gene_symbol_ranks_gene_first_then_diseases(self, adapter):
        results = await adapter.search_concepts("BRCA1")
        assert [c.primary_id for c in results] == ["HGNC:1100", "MONDO:0700268"]
        assert results[0].concept_type == ConceptType.GENE and results[0].confidence_score == 1.0
        assert results[1].concept_type == ConceptType.DISEASE
        assert results[1].confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_disease_label_and_word_match(self, adapter):
        results = await adapter.search_concepts("mitochondrial disease")
        assert [c.primary_id for c in results] == ["MONDO:0044970"]
        words = await adapter.search_concepts("syndrome")
        assert "MONDO:0010543" in {c.primary_id for c in words}
        assert all(c.confidence_score in (0.7, 0.8) for c in words)

    @pytest.mark.asyncio
    async def test_substring_inside_word_scores_lowest(self, adapter):
        results = await adapter.search_concepts("rca1")
        assert results[0].primary_id == "HGNC:1100" and results[0].confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_identifier_queries(self, adapter):
        assert [c.primary_id for c in await adapter.search_concepts("HGNC:1100")] == ["HGNC:1100"]
        assert [c.primary_id for c in await adapter.search_concepts("hgnc:3603")] == ["HGNC:3603"]
        assert [c.primary_id for c in await adapter.search_concepts("mondo:10543")] == [
            "MONDO:0010543"
        ]
        assert await adapter.search_concepts("HGNC:99999999") == []
        assert await adapter.search_concepts("MONDO:9999999") == []

    @pytest.mark.asyncio
    async def test_limit_empty_and_unknown(self, adapter):
        assert await adapter.search_concepts("") == []
        assert await adapter.search_concepts("BRCA1", limit=0) == []
        assert len(await adapter.search_concepts("syndrome", limit=1)) == 1
        assert await adapter.search_concepts("zzzzzz") == []

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("BRCA1") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_details_with_dosage(self, adapter):
        concept = await adapter.get_concept_details("BRCA1")
        assert concept.primary_id == "HGNC:1100" and concept.primary_label == "BRCA1"
        assert concept.concept_type == ConceptType.GENE
        assert (
            "2 ClinGen gene-disease validity curation(s) (2 Definitive)" in concept.definitions[0]
        )
        assert any("Haploinsufficiency" in d for d in concept.definitions)
        assert "ClinGen dosage sensitivity" in concept.categories
        assert KnowledgeSource.HGNC in {i.source for i in concept.identifiers}
        data = concept.source_data[KnowledgeSource.CLINGEN]
        assert data["validity_summary"]["best_classification"] == "Definitive"
        assert len(data["validity"]) == 2 and data["validity"][0]["gene"] == "BRCA1"
        assert data["dosage"]["triplosensitivity"] == "No Evidence for Triplosensitivity"
        assert data["url"].endswith("HGNC:1100")

    @pytest.mark.asyncio
    async def test_dosage_only_gene(self, adapter):
        concept = await adapter.get_concept_details("HGNC:18149")
        assert concept.primary_label == "A4GALT"
        assert concept.definitions == [
            "Dosage sensitivity: Gene Associated with Autosomal Recessive Phenotype; "
            "No Evidence for Triplosensitivity."
        ]
        assert "validity" not in concept.source_data[KnowledgeSource.CLINGEN]

    @pytest.mark.asyncio
    async def test_disease_details(self, adapter):
        concept = await adapter.get_concept_details("MONDO:0044970")
        assert concept.primary_label == "mitochondrial disease"
        assert concept.concept_type == ConceptType.DISEASE
        assert "ABCB7" in concept.definitions[0] and "ACO2" in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.CLINGEN]
        assert data["validity_summary"]["n_submitters"] == 1
        assert {c["gene"] for c in data["validity"]} == {"ABCB7", "ACO2", "MT-ATP6"}
        assert KnowledgeSource.MONDO in {i.source for i in concept.identifiers}

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        assert await adapter.get_concept_details("HGNC:99999999") is None
        assert await adapter.get_concept_details("NOTAGENE") is None
        assert await adapter.get_concept_details("") is None
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("BRCA1") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_gene_to_diseases_with_curation_and_dosage_keys(self, adapter):
        rels = await adapter.get_relationships("HGNC:1100")
        assert [r["related_id"] for r in rels] == [
            "MONDO:0700268",
            "MONDO:0054748",
        ]  # newest first
        first = rels[0]
        assert first["relation_label"] == "associated_with" and first["source"] == "CLINGEN"
        assert first["related_name"] == "BRCA1-related cancer predisposition"
        assert first["classification"] == "Definitive" and first["classification_strength"] == 1.0
        assert first["mode_of_inheritance"] == "Autosomal dominant" and first["moi_code"] == "AD"
        assert first["curation_date"] == "2024-08-29" and first["sop"] == "SOP10"
        assert first["expert_panel"].startswith("Hereditary Cancer")
        assert first["report_url"].startswith("https://search.clinicalgenome.org")
        assert first["dosage_haploinsufficiency"] == "Sufficient Evidence for Haploinsufficiency"
        assert first["dosage_triplosensitivity"].startswith("No Evidence")
        assert first["dosage_date"] == "2021-09-23"

    @pytest.mark.asyncio
    async def test_disease_to_genes_and_symbol_input(self, adapter):
        rels = await adapter.get_relationships("mondo:44970")
        assert [r["related_name"] for r in rels] == ["MT-ATP6", "ACO2", "ABCB7"]  # by strength
        assert (
            rels[0]["related_id"] == "HGNC:7414"
            and rels[0]["mode_of_inheritance"] == "Mitochondrial"
        )
        by_symbol = await adapter.get_relationships("brca1")
        assert len(by_symbol) == 2

    @pytest.mark.asyncio
    async def test_negative_predicates_sort_last(self, adapter):
        rels = await adapter.get_relationships("FBN1")
        assert [r["relation_label"] for r in rels] == [
            "associated_with",
            "disputed_association_with",
        ]
        refuted = (await adapter.get_relationships("ADRA2B"))[0]
        assert refuted["relation_label"] == "refuted_association_with"
        assert refuted["classification_strength"] == 0.0
        nkdr = (await adapter.get_relationships("ACAT2"))[0]
        assert nkdr["relation_label"] == "no_known_relationship_with"
        assert nkdr["mode_of_inheritance"] == "Undetermined"

    @pytest.mark.asyncio
    async def test_limit_unknown_and_errors(self, adapter):
        assert len(await adapter.get_relationships("AARS1", limit=2)) == 2
        assert await adapter.get_relationships("AARS1", limit=0) == []
        assert await adapter.get_relationships("MONDO:9999999") == []
        assert await adapter.get_relationships("NOTAGENE") == []
        assert await adapter.get_relationships("HGNC:18149") == []  # dosage-only gene
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("BRCA1") == []

    @pytest.mark.asyncio
    async def test_mappings_default_empty(self, adapter):
        assert await adapter.get_mappings("HGNC:1100") == []
