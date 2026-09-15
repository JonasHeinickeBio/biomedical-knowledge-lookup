"""
Unit tests for EUtilsAdapter.

The mocked responses are shaped like what ``bioservices.EUtils`` returns today:
NCBI's JSON ``esearchresult`` (``idlist``) for ``ESearch`` and the ``result``
object (``uids`` plus one record per UID) for ``ESummary``.
"""

import logging
import sys
from unittest.mock import MagicMock, patch

mock_bioservices = MagicMock()
sys.modules["bioservices"] = mock_bioservices

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.eutils_adapter import (
    EUtilsAdapter,
    _extract_gene_field,
    _extract_protein_field,
    _extract_pubmed_field,
    _extract_taxonomy_field,
    _id_list,
    _summary_records,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

PUBMED_SUMMARY = {
    "uids": ["42728754"],
    "42728754": {
        "uid": "42728754",
        "pubdate": "2026 Sep",
        "source": "J Obstet Gynaecol Res",
        "authors": [
            {"name": "Rouf T", "authtype": "Author", "clusterid": ""},
            {"name": "Ahmad I", "authtype": "Author", "clusterid": ""},
        ],
        "title": "Unani Herbal Vaginal Douche: A Case Series.",
        "fulljournalname": "The journal of obstetrics and gynaecology research",
        "articleids": [{"idtype": "pubmed", "idtypen": 1, "value": "42728754"}],
    },
}
GENE_SUMMARY = {
    "uids": ["1956"],
    "1956": {
        "uid": "1956",
        "name": "EGFR",
        "description": "epidermal growth factor receptor",
        "organism": {"scientificname": "Homo sapiens", "commonname": "human", "taxid": 9606},
        "otheraliases": "ERBB, ERBB1, HER1",
    },
}
PROTEIN_SUMMARY = {
    "uids": ["2992366234"],
    "2992366234": {
        "uid": "2992366234",
        "caption": "NP_001428163",
        "title": "histone deacetylase 8 isoform 12 [Homo sapiens]",
        "accessionversion": "NP_001428163.1",
        "taxid": 9606,
    },
}
TAXONOMY_SUMMARY = {
    "uids": ["9606"],
    "9606": {
        "uid": "9606",
        "rank": "species",
        "scientificname": "Homo sapiens",
        "commonname": "human",
        "taxid": 9606,
    },
}
SUMMARIES = {
    "pubmed": PUBMED_SUMMARY,
    "gene": GENE_SUMMARY,
    "protein": PROTEIN_SUMMARY,
    "taxonomy": TAXONOMY_SUMMARY,
}


def _esearch(ids):
    return {"count": str(len(ids)), "retmax": str(len(ids)), "retstart": "0", "idlist": ids}


def _mock_eutils(hits=None, summaries=None):
    """EUtils mock whose ESearch returns *hits[db]* and ESummary *summaries[db]*."""
    hits = hits or {}
    summaries = summaries or SUMMARIES
    eu = MagicMock()
    eu.ESearch.side_effect = lambda db, term, retmax=20: _esearch(hits.get(db, []))
    eu.ESummary.side_effect = lambda db, ids: summaries[db]
    return eu


def _patch_bioservices(eu):
    return patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=eu))})


class TestEUtilsAdapter:
    """Tests for EUtilsAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EUtilsAdapter instance."""
        return EUtilsAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test EUtilsAdapter initialization."""
        adapter = EUtilsAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.EUTILS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.EUTILS

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.EUTILS: 5.0})
        adapter = EUtilsAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- is_available ---

    def test_is_available_with_bioservices(self, adapter):
        """is_available is True when bioservices can be imported."""
        with patch.dict("sys.modules", {"bioservices": MagicMock()}):
            assert adapter.is_available() is True

    def test_is_available_without_bioservices(self, adapter):
        """Regression: is_available is False when bioservices is not installed."""
        with patch.dict("sys.modules", {"bioservices": None}):
            assert adapter.is_available() is False

    def test_is_available_not_imported_uses_find_spec(self, adapter):
        """Without an imported module, availability comes from importlib's find_spec."""
        saved = sys.modules.pop("bioservices")
        try:
            with patch("importlib.util.find_spec", return_value=None):
                assert adapter.is_available() is False
            with patch("importlib.util.find_spec", return_value=object()):
                assert adapter.is_available() is True
        finally:
            sys.modules["bioservices"] = saved

    # --- search_concepts ---

    @pytest.mark.asyncio
    async def test_search_concepts_bioservices_import_error(self, adapter):
        """Search returns [] when bioservices is not installed."""
        with patch.dict("sys.modules", {"bioservices": None}):
            assert await adapter.search_concepts("test") == []

    @pytest.mark.asyncio
    async def test_search_concepts_pubmed_json(self, adapter):
        """Regression: PubMed hits are read from the JSON idlist/uids response."""
        eu = _mock_eutils(hits={"pubmed": ["42728754"]})
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("case series", limit=4)

        assert len(results) == 1
        concept = results[0]
        assert concept.primary_id == "PMID:42728754"
        assert concept.primary_label == "Unani Herbal Vaginal Douche: A Case Series."
        assert concept.concept_type == ConceptType.CITATION
        data = concept.source_data[KnowledgeSource.EUTILS]
        assert data["authors"] == ["Rouf T", "Ahmad I"]
        assert data["journal"] == "The journal of obstetrics and gynaecology research"
        assert KnowledgeSource.EUTILS in concept.sources

    @pytest.mark.asyncio
    async def test_search_concepts_gene_json(self, adapter):
        """Gene hits use name and description from the JSON summary."""
        eu = _mock_eutils(hits={"gene": ["1956"]})
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("EGFR", limit=4)

        assert [c.primary_id for c in results] == ["GeneID:1956"]
        assert results[0].primary_label == "EGFR"
        assert results[0].concept_type == ConceptType.GENE
        data = results[0].source_data[KnowledgeSource.EUTILS]
        assert data["description"] == "epidermal growth factor receptor"
        assert data["organism"] == "Homo sapiens"

    @pytest.mark.asyncio
    async def test_search_concepts_protein_json(self, adapter):
        """Protein hits use title and accessionversion from the JSON summary."""
        eu = _mock_eutils(hits={"protein": ["2992366234"]})
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("HDAC8", limit=4)

        assert [c.primary_id for c in results] == ["Protein:2992366234"]
        assert results[0].concept_type == ConceptType.PROTEIN
        assert results[0].source_data[KnowledgeSource.EUTILS]["accession"] == "NP_001428163.1"

    @pytest.mark.asyncio
    async def test_search_concepts_taxonomy_json(self, adapter):
        """Taxonomy hits use scientificname and commonname from the JSON summary."""
        eu = _mock_eutils(hits={"taxonomy": ["9606"]})
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("human", limit=4)

        assert [c.primary_id for c in results] == ["TaxID:9606"]
        assert results[0].primary_label == "Homo sapiens"
        assert results[0].concept_type == ConceptType.ORGANISM
        assert results[0].source_data[KnowledgeSource.EUTILS]["common_name"] == "human"

    @pytest.mark.asyncio
    async def test_search_concepts_all_databases_in_order(self, adapter):
        """Results come from pubmed, gene, protein and taxonomy, in that order."""
        eu = _mock_eutils(
            hits={
                "pubmed": ["42728754"],
                "gene": ["1956"],
                "protein": ["2992366234"],
                "taxonomy": ["9606"],
            }
        )
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("anything", limit=8)
        assert [c.primary_id for c in results] == [
            "PMID:42728754",
            "GeneID:1956",
            "Protein:2992366234",
            "TaxID:9606",
        ]

    @pytest.mark.asyncio
    async def test_search_concepts_small_limit_still_searches(self, adapter):
        """Regression: a limit below 4 no longer searches nothing (limit // 4 == 0)."""
        eu = _mock_eutils(hits={"pubmed": ["42728754"], "gene": ["1956"]})
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("x", limit=1)

        assert [c.primary_id for c in results] == ["PMID:42728754"]
        assert [call.kwargs["retmax"] for call in eu.ESearch.call_args_list] == [1, 1, 1, 1]

    @pytest.mark.asyncio
    async def test_search_concepts_batches_esummary(self, adapter):
        """One ESummary request per database with comma-separated IDs."""
        summaries = dict(SUMMARIES)
        summaries["pubmed"] = {
            "uids": ["1", "2"],
            "1": {"uid": "1", "title": "First"},
            "2": {"uid": "2", "title": "Second"},
        }
        eu = _mock_eutils(hits={"pubmed": ["1", "2"]}, summaries=summaries)
        with _patch_bioservices(eu):
            results = await adapter.search_concepts("x", limit=8)

        assert [c.primary_label for c in results] == ["First", "Second"]
        eu.ESummary.assert_called_once_with("pubmed", "1,2")

    @pytest.mark.asyncio
    async def test_search_concepts_record_without_label_skipped(self, adapter):
        """Summary records without a title/name are skipped."""
        summaries = dict(SUMMARIES)
        summaries["pubmed"] = {"uids": ["1"], "1": {"uid": "1", "title": ""}}
        eu = _mock_eutils(hits={"pubmed": ["1"]}, summaries=summaries)
        with _patch_bioservices(eu):
            assert await adapter.search_concepts("x", limit=4) == []

    @pytest.mark.asyncio
    async def test_search_concepts_one_database_fails(self, adapter, caplog):
        """Regression: a failing database is logged, the others still return results."""
        eu = _mock_eutils(hits={"gene": ["1956"]})

        def esearch(db, term, retmax=20):
            if db == "pubmed":
                raise RuntimeError("HTTP 500")
            return _esearch(["1956"] if db == "gene" else [])

        eu.ESearch.side_effect = esearch
        with _patch_bioservices(eu), caplog.at_level(logging.WARNING):
            results = await adapter.search_concepts("EGFR", limit=4)

        assert [c.primary_id for c in results] == ["GeneID:1956"]
        assert "EUtils pubmed search failed" in caplog.text

    @pytest.mark.asyncio
    async def test_search_concepts_unexpected_response_logged(self, adapter, caplog):
        """Regression: an error status instead of JSON is logged, not silently empty."""
        eu = _mock_eutils()
        eu.ESearch.side_effect = lambda db, term, retmax=20: 400
        with _patch_bioservices(eu), caplog.at_level(logging.WARNING):
            results = await adapter.search_concepts("x", limit=4)

        assert results == []
        assert "unexpected ESearch response: 400" in caplog.text
        assert "Error searching EUtils" in caplog.text

    @pytest.mark.asyncio
    async def test_search_concepts_all_fail_notifies_circuit_breaker(self, adapter, caplog):
        """When every database fails, the error reaches the circuit breaker and the log."""
        eu = _mock_eutils()
        eu.ESearch.side_effect = Exception("Search error")
        breaker = MagicMock()
        breaker.allow_request.return_value = True
        adapter.set_circuit_breaker(breaker)
        with _patch_bioservices(eu), caplog.at_level(logging.ERROR):
            results = await adapter.search_concepts("test")

        assert results == []
        breaker.record_failure.assert_called()
        assert "Error searching EUtils: Search error" in caplog.text

    @pytest.mark.asyncio
    async def test_search_concepts_no_hits(self, adapter):
        """Empty idlists return [] without ESummary calls."""
        eu = _mock_eutils()
        with _patch_bioservices(eu):
            assert await adapter.search_concepts("nonexistent", limit=20) == []
        eu.ESummary.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_concepts_zero_limit(self, adapter):
        """limit <= 0 returns [] without requests."""
        eu = _mock_eutils()
        with _patch_bioservices(eu):
            assert await adapter.search_concepts("x", limit=0) == []
        eu.ESearch.assert_not_called()

    # --- get_concept_details ---

    @pytest.mark.asyncio
    async def test_get_concept_details_import_error(self, adapter):
        """get_concept_details returns None when bioservices is not installed."""
        with patch.dict("sys.modules", {"bioservices": None}):
            assert await adapter.get_concept_details("PMID:12345") is None

    @pytest.mark.asyncio
    async def test_get_concept_details_pubmed(self, adapter):
        """Regression: PubMed uses rettype=abstract ("full" returns an empty body)."""
        eu = MagicMock()
        eu.EFetch.return_value = b"1. Nucleic Acids Res. 2013 Jan;41:D36-42.\n\nGenBank.\n"
        eu.ESummary.return_value = {
            "uids": ["23193287"],
            "23193287": {"uid": "23193287", "title": "GenBank."},
        }
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("PMID:23193287")

        assert result is not None
        assert result.primary_id == "PMID:23193287"
        assert result.primary_label == "GenBank."
        assert result.concept_type == ConceptType.CITATION
        eu.EFetch.assert_called_once_with("pubmed", "23193287", rettype="abstract", retmode="text")
        data = result.source_data[KnowledgeSource.EUTILS]
        assert data["full_record"].startswith("1. Nucleic Acids Res.")

    @pytest.mark.asyncio
    async def test_get_concept_details_geneid(self, adapter):
        """Gene details use rettype=full and the gene name as label."""
        eu = MagicMock()
        eu.EFetch.return_value = b"\n1. BRCA1\nOfficial Symbol: BRCA1\n"
        eu.ESummary.return_value = {"uids": ["672"], "672": {"uid": "672", "name": "BRCA1"}}
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("GeneID:672")

        assert result.primary_label == "BRCA1"
        assert result.concept_type == ConceptType.GENE
        eu.EFetch.assert_called_once_with("gene", "672", rettype="full", retmode="text")

    @pytest.mark.asyncio
    async def test_get_concept_details_taxid(self, adapter):
        """Taxonomy details are typed ORGANISM, like search results."""
        eu = MagicMock()
        eu.EFetch.return_value = b"1. Homo sapiens\n    (human), species, primates\n"
        eu.ESummary.return_value = TAXONOMY_SUMMARY
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("TaxID:9606")

        assert result.primary_label == "Homo sapiens"
        assert result.concept_type == ConceptType.ORGANISM

    @pytest.mark.asyncio
    async def test_get_concept_details_protein_prefix(self, adapter):
        """IDs returned by search (Protein:<uid>) resolve against the protein database."""
        eu = MagicMock()
        eu.EFetch.return_value = "LOCUS       NP_001428163"
        eu.ESummary.return_value = PROTEIN_SUMMARY
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("Protein:2992366234")

        assert result.concept_type == ConceptType.PROTEIN
        assert result.primary_label == "histone deacetylase 8 isoform 12 [Homo sapiens]"
        eu.EFetch.assert_called_once_with("protein", "2992366234", rettype="gp", retmode="text")

    @pytest.mark.asyncio
    async def test_get_concept_details_protein_accession(self, adapter):
        """NP_ accessions resolve against the protein database."""
        eu = MagicMock()
        eu.EFetch.return_value = "LOCUS       NP_000537"
        eu.ESummary.return_value = {"error": "Invalid uid"}
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("NP_000537")

        assert result is not None
        assert result.primary_label == "Protein NP_000537"
        eu.EFetch.assert_called_once_with("protein", "NP_000537", rettype="gp", retmode="text")

    @pytest.mark.asyncio
    async def test_get_concept_details_nuccore_accession(self, adapter):
        """NM_ accessions resolve against nuccore with rettype=gb."""
        eu = MagicMock()
        eu.EFetch.return_value = "LOCUS       NM_000537"
        eu.ESummary.side_effect = Exception("summary failed")
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("NM_000537")

        assert result.primary_label == "NUCCORE NM_000537"
        assert result.concept_type == ConceptType.MOLECULAR_ENTITY
        eu.EFetch.assert_called_once_with("nuccore", "NM_000537", rettype="gb", retmode="text")

    @pytest.mark.asyncio
    async def test_get_concept_details_unknown_format(self, adapter):
        """Unprefixed IDs default to PubMed."""
        eu = MagicMock()
        eu.EFetch.return_value = "Some record"
        eu.ESummary.return_value = {"uids": []}
        with _patch_bioservices(eu):
            result = await adapter.get_concept_details("12345")

        assert result.primary_label == "PubMed Article 12345"
        assert eu.EFetch.call_args.args[0] == "pubmed"

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_record(self, adapter):
        """An empty EFetch body means not found."""
        eu = MagicMock()
        eu.EFetch.return_value = b""
        with _patch_bioservices(eu):
            assert await adapter.get_concept_details("PMID:12345") is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error_status(self, adapter):
        """An HTTP status code instead of a body means not found."""
        eu = MagicMock()
        eu.EFetch.return_value = 400
        with _patch_bioservices(eu):
            assert await adapter.get_concept_details("PMID:12345") is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_record(self, adapter):
        """EFetch returning None means not found."""
        eu = MagicMock()
        eu.EFetch.return_value = None
        with _patch_bioservices(eu):
            assert await adapter.get_concept_details("PMID:12345") is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """EFetch exceptions are logged and return None."""
        eu = MagicMock()
        eu.EFetch.side_effect = Exception("Fetch error")
        with _patch_bioservices(eu):
            assert await adapter.get_concept_details("PMID:12345") is None

    # --- helpers ---

    def test_extract_fields_from_json_records(self):
        """Current JSON records use flat lower-case keys."""
        assert _extract_pubmed_field(PUBMED_SUMMARY["42728754"], "Title").startswith("Unani")
        assert _extract_gene_field(GENE_SUMMARY["1956"], "Name") == "EGFR"
        assert (
            _extract_protein_field(PROTEIN_SUMMARY["2992366234"], "AccessionVersion")
            == "NP_001428163.1"
        )
        assert _extract_taxonomy_field(TAXONOMY_SUMMARY["9606"], "CommonName") == "human"

    def test_extract_field_legacy_docsum(self):
        """Legacy DocSum dicts with an Item list are still accepted."""
        docsum = {"Item": [{"Name": "Title", "ItemContent": "Test Article"}]}
        assert _extract_pubmed_field(docsum, "Title") == "Test Article"
        assert _extract_pubmed_field(docsum, "Author") == ""

    def test_extract_field_invalid_input(self):
        """Non-dict input returns an empty string."""
        assert _extract_pubmed_field(None, "Title") == ""
        assert _extract_gene_field({}, "Name") == ""
        assert _extract_protein_field({"Item": None}, "Title") == ""
        assert _extract_taxonomy_field("text", "ScientificName") == ""

    def test_id_list_shapes(self):
        """_id_list accepts the bioservices shape, the raw NCBI wrapper and legacy IdList."""
        assert _id_list(_esearch(["1", "2"])) == ["1", "2"]
        assert _id_list({"esearchresult": {"idlist": [3]}}) == ["3"]
        assert _id_list({"IdList": ["4"]}) == ["4"]

    @pytest.mark.parametrize("response", [400, None, {"error": "API rate limit exceeded"}])
    def test_id_list_unexpected_raises(self, response):
        """Anything else is an error, not an empty result."""
        with pytest.raises(RuntimeError, match="unexpected ESearch response"):
            _id_list(response)

    def test_summary_records_shapes(self):
        """_summary_records reads uids from the result object or the raw wrapper."""
        assert _summary_records(GENE_SUMMARY, ["1956"])[0][0] == "1956"
        assert _summary_records({"result": GENE_SUMMARY}, [])[0][1]["name"] == "EGFR"
        assert _summary_records({"1956": GENE_SUMMARY["1956"]}, ["1956"])[0][0] == "1956"

    @pytest.mark.parametrize("summary", [500, {"error": "Invalid uid"}])
    def test_summary_records_errors_raise(self, summary):
        with pytest.raises(RuntimeError):
            _summary_records(summary, ["1"])

    # --- defaults ---

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass
