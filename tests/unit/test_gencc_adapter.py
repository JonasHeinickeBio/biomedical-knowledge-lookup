"""Unit tests for GenCCAdapter on rows of the real GenCC submissions export.

Nothing is downloaded (the full export is ~28 MB): tests/fixtures/gencc_responses.py holds
real rows from 64 KiB Range samples plus a few clearly marked composed rows that add
submitters the samples lacked.
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import gencc_adapter
from knowledge_lookup.adapters.gencc_adapter import GenCCAdapter, parse_submissions
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import gencc_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "gencc-submissions.csv"
    path.write_text(fx.GENCC_CSV, encoding="utf-8")
    return path


@pytest.fixture
def adapter(lookup_config, csv_file, monkeypatch):
    monkeypatch.setenv("GENCC_PATH", str(csv_file))
    return GenCCAdapter(lookup_config)


class TestParser:
    def test_rows_and_indexes(self, csv_file):
        index = parse_submissions(csv_file)
        assert index.submissions == 17  # malformed trailing rows are skipped
        ski = index.by_gene["HGNC:10896"][0]
        assert ski.gene_symbol == "SKI" and ski.disease_id == "MONDO:0008426"
        assert ski.original_id == "OMIM:182212" and ski.classification == "Definitive"
        assert ski.moi == "Autosomal dominant" and ski.submitter == "Ambry Genetics"
        assert ski.date == "2018-03-30" and ski.pmids == ""
        # Ambry puts its PMID text in the assertion-criteria column (real data quirk)
        assert ski.criteria_url == "PMID: 28106320"
        assert index.symbol_ids["SKI"] == "HGNC:10896"
        assert index.disease_labels["MONDO:0010543"] == "Barth syndrome"
        assert "OMIM:182212" in index.by_original and "ORPHA:99999" in index.by_original
        # ClinGen rows submit the MONDO id itself: no alias entry
        assert "MONDO:0010543" not in index.by_original
        # notes (long, multi-line, quoted) are discarded but the row still parses
        assert len(index.by_gene["HGNC:11577"]) == 1

    def test_row_without_mondo_uses_submitted_id(self, csv_file):
        index = parse_submissions(csv_file)
        assert index.disease_labels["OMIM:424242"] == "XYZ DISEASE"

    def test_empty_and_wrong_files(self, tmp_path):
        empty = tmp_path / "e.csv"
        empty.write_text("")
        assert parse_submissions(empty).submissions == 0
        wrong = tmp_path / "w.csv"
        wrong.write_text('"a","b"\n"1","2"\n')
        with pytest.raises(ValueError, match="missing columns"):
            parse_submissions(wrong)

    def test_reordered_columns_and_nbsp(self, tmp_path):
        path = tmp_path / "r.csv"
        path.write_text(
            "submitter_title,classification_title,gene_symbol,gene_curie,disease_title,"
            "disease_curie,submitted_as_pmids\n"
            'X lab,Strong,ABC1,HGNC:5,some disease,MONDO:0000005,"PMID:\xa0123"\n'
        )
        index = parse_submissions(path)
        sub = index.by_gene["HGNC:5"][0]
        assert sub.submitter == "X lab" and sub.pmids == "PMID: 123" and sub.moi == ""


class TestAvailability:
    def test_source(self, adapter):
        assert adapter.get_source() == KnowledgeSource.GENCC

    def test_opt_in_switches(self, lookup_config, tmp_path, monkeypatch):
        for name in ("GENCC_PATH", "GENCC_DOWNLOAD", "KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path))
        adapter = GenCCAdapter(lookup_config)
        assert adapter.is_available() is False  # never downloads 28 MB by default
        monkeypatch.setenv("GENCC_DOWNLOAD", "1")
        assert adapter.is_available() is True
        monkeypatch.delenv("GENCC_DOWNLOAD")
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS", "true")
        assert adapter.is_available() is True
        monkeypatch.delenv("KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS")
        (tmp_path / gencc_adapter.GENCC_FILENAME).write_text("x")
        assert adapter.is_available() is True
        monkeypatch.setenv("GENCC_PATH", str(tmp_path / "missing.csv"))
        assert adapter.is_available() is False
        monkeypatch.setenv("GENCC_PATH", str(tmp_path / gencc_adapter.GENCC_FILENAME))
        assert adapter.is_available() is True

    def test_construction_never_touches_the_network_or_disk(self, lookup_config, monkeypatch):
        monkeypatch.delenv("GENCC_PATH", raising=False)
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset") as fake:
            GenCCAdapter(lookup_config)
        fake.assert_not_called()


class TestLoading:
    @pytest.mark.asyncio
    async def test_lazy_download_once_via_dataset_cache(
        self, lookup_config, csv_file, monkeypatch
    ):
        monkeypatch.delenv("GENCC_PATH", raising=False)
        adapter = GenCCAdapter(lookup_config)
        fake = AsyncMock(return_value=csv_file)
        with patch("knowledge_lookup.utils.dataset_cache.ensure_dataset", fake):
            assert await adapter.search_concepts("SKI")
            assert await adapter.search_concepts("KIF1B")
        fake.assert_awaited_once()
        assert fake.await_args.args[0] == gencc_adapter.GENCC_URL
        assert fake.await_args.kwargs["filename"] == gencc_adapter.GENCC_FILENAME

    @pytest.mark.asyncio
    async def test_load_failure_degrades_and_retries(self, lookup_config, monkeypatch, tmp_path):
        monkeypatch.setenv("GENCC_PATH", str(tmp_path / "missing.csv"))
        adapter = GenCCAdapter(lookup_config)
        assert await adapter.search_concepts("SKI") == []
        assert await adapter.get_concept_details("SKI") is None
        assert await adapter.get_relationships("SKI") == []
        assert await adapter.get_mappings("MONDO:0008426") == []
        assert adapter._index is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_gene_symbol_and_disease_label(self, adapter):
        genes = await adapter.search_concepts("SKI")
        assert genes[0].primary_id == "HGNC:10896" and genes[0].concept_type == ConceptType.GENE
        assert genes[0].confidence_score == 1.0
        diseases = await adapter.search_concepts("barth syndrome")
        assert diseases[0].primary_id == "MONDO:0010543"
        assert diseases[0].concept_type == ConceptType.DISEASE

    @pytest.mark.asyncio
    async def test_ranking_prefix_word_substring(self, adapter):
        results = await adapter.search_concepts("syndrome")
        scores = {c.primary_id: c.confidence_score for c in results}
        assert scores["MONDO:0010543"] == 0.8 and scores["MONDO:0008426"] == 0.8
        sub = await adapter.search_concepts("nsertion")  # inside a word -> nothing
        assert sub == []
        inner = await adapter.search_concepts("IF1")
        assert inner[0].primary_id == "HGNC:16636" and inner[0].confidence_score == 0.7
        prefix = await adapter.search_concepts("KIF")
        assert prefix[0].confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_identifier_queries(self, adapter):
        assert [c.primary_id for c in await adapter.search_concepts("hgnc:10896")] == [
            "HGNC:10896"
        ]
        assert [c.primary_id for c in await adapter.search_concepts("MONDO:8426")] == [
            "MONDO:0008426"
        ]
        omim = await adapter.search_concepts("omim:182212")
        assert omim[0].primary_id == "OMIM:182212"
        assert omim[0].primary_label == "SHPRINTZEN-GOLDBERG CRANIOSYNOSTOSIS SYNDROME; SGS"
        orpha = await adapter.search_concepts("Orphanet_99999")
        assert orpha[0].primary_id == "ORPHA:99999"
        assert await adapter.search_concepts("HGNC:9999999") == []
        assert await adapter.search_concepts("MONDO:9999999") == []

    @pytest.mark.asyncio
    async def test_limit_empty_and_errors(self, adapter):
        assert await adapter.search_concepts("") == []
        assert await adapter.search_concepts("SKI", limit=0) == []
        assert len(await adapter.search_concepts("syndrome", limit=1)) == 1
        assert await adapter.search_concepts("hgnc:10896 mondo", limit=1) == []
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("SKI") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_details(self, adapter):
        concept = await adapter.get_concept_details("KIF1B")
        assert concept.primary_id == "HGNC:16636"
        assert (
            "5 GenCC submission(s) from 4 submitter(s) on 2 disease(s)" in concept.definitions[0]
        )
        assert "strongest classification: Definitive" in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.GENCC]
        assert data["n_submissions"] == 5 and data["n_diseases"] == 2
        assert "Orphanet" in data["submitters"] and "G2P" in data["submitters"]
        cmt = data["diseases"]["MONDO:0007308"]
        assert cmt["best_classification"] == "Definitive" and cmt["conflicting"] is True
        assert KnowledgeSource.HGNC in {i.source for i in concept.identifiers}

    @pytest.mark.asyncio
    async def test_disease_details_by_mondo_and_by_submitted_id(self, adapter):
        by_mondo = await adapter.get_concept_details("MONDO:0007308")
        assert by_mondo.primary_label.startswith("Charcot-Marie-Tooth disease type 2A1")
        data = by_mondo.source_data[KnowledgeSource.GENCC]
        assert data["n_genes"] == 1 and data["genes"]["HGNC:16636"]["symbol"] == "KIF1B"
        by_omim = await adapter.get_concept_details("OMIM:118210")
        assert by_omim.primary_id == "OMIM:118210"
        assert KnowledgeSource.MONDO in {i.source for i in by_omim.identifiers}
        assert by_omim.source_data[KnowledgeSource.GENCC]["n_submissions"] == 3

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        assert await adapter.get_concept_details("NOTAGENE") is None
        assert await adapter.get_concept_details("MONDO:9999999") is None
        assert await adapter.get_concept_details("") is None
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("SKI") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_gene_to_diseases_every_submitter_and_consensus(self, adapter):
        rels = await adapter.get_relationships("HGNC:16636")
        assert [r["related_id"] for r in rels] == ["MONDO:0007308", "MONDO:0008233"]
        cmt = rels[0]
        assert cmt["relation_label"] == "associated_with" and cmt["source"] == "GENCC"
        assert cmt["related_name"].startswith("Charcot-Marie-Tooth")
        assert cmt["best_classification"] == "Definitive"
        assert cmt["consensus_classification"] == "Disputed Evidence"  # 4-way tie -> weakest
        assert cmt["n_submitters"] == 4 and cmt["conflicting"] is True
        assert cmt["classification_strength"] == 1.0
        assert cmt["classification_counts"] == {
            "Limited": 1,
            "Strong": 1,
            "Disputed Evidence": 1,
            "Definitive": 1,
        }
        assert cmt["modes_of_inheritance"] == ["Autosomal dominant", "Monoallelic"]
        assert cmt["latest_date"] == "2024-10-15"
        by_submitter = {s["submitter"]: s for s in cmt["submissions"]}
        assert set(by_submitter) == {
            "Ambry Genetics",
            "Genomics England PanelApp",
            "G2P",
            "Orphanet",
        }
        assert by_submitter["Orphanet"]["original_disease_id"] == "Orphanet:99999"
        assert by_submitter["Genomics England PanelApp"]["classification"] == "Strong"
        assert by_submitter["Genomics England PanelApp"]["pmids"] == "PMID: 111"

    @pytest.mark.asyncio
    async def test_negative_and_weak_pairs_get_typed_predicates(self, adapter):
        slc = (await adapter.get_relationships("SLC9A1"))[0]
        assert slc["best_classification"] == "Supportive"
        assert slc["relation_label"] == "associated_with" and slc["conflicting"] is False
        afp = (await adapter.get_relationships("AFP"))[0]
        assert afp["relation_label"] == "no_known_relationship_with"
        anxa = (await adapter.get_relationships("ANXA5"))[0]
        assert anxa["relation_label"] == "disputed_association_with"
        assert anxa["classification_strength"] == 0.05

    @pytest.mark.asyncio
    async def test_disease_to_genes_by_mondo_and_submitted_id(self, adapter):
        rels = await adapter.get_relationships("MONDO:0007308")
        assert [(r["related_id"], r["related_name"]) for r in rels] == [("HGNC:16636", "KIF1B")]
        via_omim = await adapter.get_relationships("OMIM:118210")
        assert via_omim[0]["n_submitters"] == 3  # Orphanet used its own id
        via_orpha = await adapter.get_relationships("orphanet:99999")
        assert via_orpha[0]["n_submitters"] == 1

    @pytest.mark.asyncio
    async def test_ordering_limit_and_unknown(self, adapter):
        rels = await adapter.get_relationships("mondo:5021")
        assert rels[0]["related_name"] == "ANKRD1"
        gene_rels = await adapter.get_relationships("KIF1B", limit=1)
        assert len(gene_rels) == 1
        assert await adapter.get_relationships("KIF1B", limit=0) == []
        assert await adapter.get_relationships("NOTAGENE") == []
        assert await adapter.get_relationships("MONDO:9999999") == []
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("SKI") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mondo_to_submitted_ids(self, adapter):
        maps = await adapter.get_mappings("MONDO:0007308")
        assert {m["toId"] for m in maps} == {"OMIM:118210", "ORPHA:99999"}
        first = maps[0]
        assert first["fromId"] == "MONDO:0007308" and first["fromSource"] == "GENCC"
        assert first["mappingType"] == "submitted_as" and first["confidence"] == 0.9
        assert {m["toSource"] for m in maps} == {"OMIM", "ORPHA"}

    @pytest.mark.asyncio
    async def test_submitted_id_to_mondo(self, adapter):
        maps = await adapter.get_mappings("OMIM:182212")
        assert [(m["fromId"], m["toId"], m["toSource"]) for m in maps] == [
            ("OMIM:182212", "MONDO:0008426", "MONDO")
        ]

    @pytest.mark.asyncio
    async def test_no_mapping_unknown_and_errors(self, adapter):
        assert await adapter.get_mappings("MONDO:0010543") == []  # ClinGen id == MONDO id
        assert await adapter.get_mappings("MONDO:9999999") == []
        assert await adapter.get_mappings("SKI") == []
        with patch.object(adapter, "_ensure_index", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("MONDO:0007308") == []
