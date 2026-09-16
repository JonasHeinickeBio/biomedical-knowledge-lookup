"""
Unit tests for QuickGOAdapter.

The mocked responses are shaped like what ``bioservices.QuickGO`` returns today:
``go_search``/``get_go_terms`` return the ``results`` list, ``Annotation``
returns the whole result page, and HTTP errors come back as an
``HTTPResponseError`` object instead of an exception.
"""

import logging
import sys
from unittest.mock import MagicMock, patch

mock_bioservices = MagicMock()
sys.modules["bioservices"] = mock_bioservices

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.quickgo_adapter import (
    QuickGOAdapter,
    _is_gene_product_id,
    _results_list,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class HTTPResponseError:
    """Stand-in for bioservices.services.HTTPResponseError (returned, not raised)."""

    status_code = 400

    def __repr__(self):
        return "HTTPResponseError(400: )"


GO_SEARCH_RESULTS = [
    {
        "id": "GO:0097194",
        "isObsolete": False,
        "name": "execution phase of apoptosis",
        "definition": {"text": "A stage of the apoptotic process."},
        "aspect": "biological_process",
    },
    {
        "id": "GO:0070227",
        "isObsolete": False,
        "name": "lymphocyte apoptotic process",
        "definition": {"text": "Any apoptotic process in a lymphocyte."},
        "aspect": "biological_process",
    },
]
GO_TERM_DETAILS = [
    {
        "id": "GO:0006915",
        "isObsolete": False,
        "name": "apoptotic process",
        "definition": {
            "text": "A programmed cell death process.",
            "xrefs": [{"dbCode": "PMID", "dbId": "18846107"}],
        },
        "synonyms": [
            {"name": "apoptosis", "type": "narrow"},
            {"name": "programmed cell death by apoptosis", "type": "exact"},
        ],
        "children": [{"id": "GO:0097194", "relation": "part_of"}],
        "aspect": "biological_process",
        "usage": "Unrestricted",
    }
]
ANNOTATION_PAGE = {
    "numberOfHits": 1043,
    "results": [
        {
            "id": "UniProtKB:P04637!58679183",
            "geneProductId": "UniProtKB:P04637",
            "qualifier": "acts_upstream_of",
            "goId": "GO:0008285",
            "goName": None,
            "goEvidence": "ISS",
            "goAspect": "biological_process",
            "evidenceCode": "ECO:0000250",
            "reference": "PMID:30514107",
            "withFrom": [{"connectedXrefs": [{"db": "UniProtKB", "id": "P10361"}]}],
            "taxonId": 9606,
            "assignedBy": "ARUK-UCL",
            "extensions": [],
            "symbol": "TP53",
            "date": "20210810",
        }
    ],
    "pageInfo": {"resultsPerPage": 1, "current": 1, "total": 1043},
}


def _patch_quickgo(qgo):
    return patch.dict(
        "sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=qgo))}
    )


class TestQuickGOAdapter:
    """Tests for QuickGOAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create QuickGOAdapter instance."""
        return QuickGOAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test QuickGOAdapter initialization."""
        adapter = QuickGOAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.QUICKGO

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.QUICKGO

    def test_is_available_with_bioservices(self, adapter):
        """is_available is True when bioservices can be imported."""
        with patch.dict("sys.modules", {"bioservices": MagicMock()}):
            assert adapter.is_available() is True

    def test_is_available_without_bioservices(self, adapter):
        """Regression: is_available is False when bioservices is not installed."""
        with patch.dict("sys.modules", {"bioservices": None}):
            assert adapter.is_available() is False

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.QUICKGO: 5.0})
        adapter = QuickGOAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass


class TestQuickGOHelpers:
    """Tests for module-level helpers."""

    @pytest.mark.parametrize(
        "value",
        ["P04637", "UniProtKB:P04637", "A0A024R161", "Q9Y6K9-2", "ComplexPortal:CPX-1"],
    )
    def test_gene_product_ids(self, value):
        assert _is_gene_product_id(value)

    @pytest.mark.parametrize("value", ["apoptosis", "GO:0006915", "TP53", "cell death", ""])
    def test_not_gene_product_ids(self, value):
        assert not _is_gene_product_id(value)

    def test_results_list_shapes(self):
        assert _results_list([1], "x") == [1]
        assert _results_list(ANNOTATION_PAGE, "x") == ANNOTATION_PAGE["results"]

    @pytest.mark.parametrize("response", [HTTPResponseError(), 400, None, {"messages": ["bad"]}])
    def test_results_list_errors_raise(self, response):
        with pytest.raises(RuntimeError, match="QuickGO x failed"):
            _results_list(response, "x")


class TestQuickGOSearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return QuickGOAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_import_error(self, adapter):
        """Test search returns empty when bioservices not available."""
        with patch.dict("sys.modules", {"bioservices": None}):
            result = await adapter.search_concepts("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_search_free_text_uses_go_search(self, adapter):
        """Regression: free text goes to the search endpoint, not get_go_terms/Annotation."""
        qgo = MagicMock()
        qgo.go_search.return_value = GO_SEARCH_RESULTS
        with _patch_quickgo(qgo):
            result = await adapter.search_concepts("apoptosis", limit=10)

        assert [c.primary_id for c in result] == ["GO:0097194", "GO:0070227"]
        qgo.go_search.assert_called_once_with("apoptosis", limit=10)
        qgo.get_go_terms.assert_not_called()
        qgo.Annotation.assert_not_called()

        concept = result[0]
        assert concept.primary_label == "execution phase of apoptosis"
        assert concept.concept_type == ConceptType.BIOLOGICAL_PROCESS
        assert concept.definitions == ["A stage of the apoptotic process."]
        assert [(i.source, i.identifier) for i in concept.identifiers] == [
            (KnowledgeSource.QUICKGO, "GO:0097194")
        ]
        data = concept.source_data[KnowledgeSource.QUICKGO]
        assert data["go_aspect"] == "biological_process"
        assert data["description"] == "GO Term: execution phase of apoptosis (biological_process)"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "aspect, expected",
        [
            ("molecular_function", ConceptType.MOLECULAR_FUNCTION),
            ("cellular_component", ConceptType.CELLULAR_COMPONENT),
            ("unknown", ConceptType.BIOLOGICAL_PROCESS),
        ],
    )
    async def test_search_aspects(self, adapter, aspect, expected):
        qgo = MagicMock()
        qgo.go_search.return_value = [{"id": "GO:0003674", "name": "term", "aspect": aspect}]
        with _patch_quickgo(qgo):
            result = await adapter.search_concepts("term", limit=10)
        assert result[0].concept_type == expected

    @pytest.mark.asyncio
    async def test_search_gene_product_annotations(self, adapter):
        """Regression: Annotation returns a dict page; its results become concepts."""
        qgo = MagicMock()
        qgo.go_search.return_value = []
        qgo.Annotation.return_value = ANNOTATION_PAGE
        with _patch_quickgo(qgo):
            result = await adapter.search_concepts("UniProtKB:P04637", limit=10)

        qgo.Annotation.assert_called_once_with(geneProductId="UniProtKB:P04637", limit=10)
        assert len(result) == 1
        concept = result[0]
        assert concept.primary_id == "UniProtKB:P04637_GO:0008285"
        assert concept.concept_type == ConceptType.GENE_DISEASE_ASSOCIATION
        data = concept.source_data[KnowledgeSource.QUICKGO]
        assert data["aspect"] == "biological_process"
        assert data["evidence_code"] == "ECO:0000250"
        assert data["go_evidence"] == "ISS"
        assert data["symbol"] == "TP53"

    @pytest.mark.asyncio
    async def test_search_error_object_is_logged(self, adapter, caplog):
        """Regression: an HTTPResponseError return value is logged, not swallowed."""
        qgo = MagicMock()
        qgo.go_search.return_value = HTTPResponseError()
        with _patch_quickgo(qgo), caplog.at_level(logging.WARNING):
            result = await adapter.search_concepts("apoptosis", limit=10)

        assert result == []
        assert "QuickGO term search failed for 'apoptosis'" in caplog.text
        assert "Error searching QuickGO" in caplog.text

    @pytest.mark.asyncio
    async def test_search_partial_failure_keeps_results(self, adapter, caplog):
        """If only the term search fails, annotation results are still returned."""
        qgo = MagicMock()
        qgo.go_search.side_effect = Exception("HTTP 503")
        qgo.Annotation.return_value = ANNOTATION_PAGE
        with _patch_quickgo(qgo), caplog.at_level(logging.WARNING):
            result = await adapter.search_concepts("P04637", limit=10)

        assert len(result) == 1
        assert "QuickGO term search failed" in caplog.text

    @pytest.mark.asyncio
    async def test_search_exception_notifies_circuit_breaker(self, adapter):
        """Test search handles exceptions and reports them to the circuit breaker."""
        qgo = MagicMock()
        qgo.go_search.side_effect = Exception("API Error")
        breaker = MagicMock()
        breaker.allow_request.return_value = True
        adapter.set_circuit_breaker(breaker)
        with _patch_quickgo(qgo):
            result = await adapter.search_concepts("test", limit=10)
        assert result == []
        breaker.record_failure.assert_called()

    @pytest.mark.asyncio
    async def test_search_skips_invalid_terms(self, adapter):
        """Test search skips non-dict terms and terms without id or name."""
        qgo = MagicMock()
        qgo.go_search.return_value = ["not_a_dict", 123, {"id": "", "name": ""}]
        with _patch_quickgo(qgo):
            assert await adapter.search_concepts("test", limit=10) == []

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, adapter):
        qgo = MagicMock()
        qgo.go_search.return_value = GO_SEARCH_RESULTS
        qgo.Annotation.return_value = ANNOTATION_PAGE
        with _patch_quickgo(qgo):
            result = await adapter.search_concepts("P04637", limit=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_zero_limit(self, adapter):
        qgo = MagicMock()
        with _patch_quickgo(qgo):
            assert await adapter.search_concepts("apoptosis", limit=0) == []
        qgo.go_search.assert_not_called()


class TestQuickGOGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return QuickGOAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_get_details_import_error(self, adapter):
        """Test get_details returns None when bioservices not available."""
        with patch.dict("sys.modules", {"bioservices": None}):
            result = await adapter.get_concept_details("GO:0008150")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_details_go_term(self, adapter):
        """GO term details include definition text, synonym names and raw details."""
        qgo = MagicMock()
        qgo.get_go_terms.return_value = GO_TERM_DETAILS
        with _patch_quickgo(qgo):
            result = await adapter.get_concept_details("GO:0006915")

        qgo.get_go_terms.assert_called_once_with("GO:0006915")
        assert result.primary_id == "GO:0006915"
        assert result.primary_label == "apoptotic process"
        assert result.concept_type == ConceptType.BIOLOGICAL_PROCESS
        assert result.definitions == ["A programmed cell death process."]
        assert result.synonyms == ["apoptosis", "programmed cell death by apoptosis"]
        data = result.source_data[KnowledgeSource.QUICKGO]
        assert data["definition"]["text"] == "A programmed cell death process."
        assert data["usage"] == "Unrestricted"
        assert data["full_details"] == GO_TERM_DETAILS[0]

    @pytest.mark.asyncio
    async def test_get_details_go_term_without_id_uses_concept_id(self, adapter):
        """The requested ID is used when the record has no id; string synonyms are kept."""
        qgo = MagicMock()
        qgo.get_go_terms.return_value = [
            {"name": "molecular_function", "aspect": "molecular_function", "synonyms": ["MF"]}
        ]
        with _patch_quickgo(qgo):
            result = await adapter.get_concept_details("GO:0003674")
        assert result.primary_id == "GO:0003674"
        assert result.concept_type == ConceptType.MOLECULAR_FUNCTION
        assert result.synonyms == ["MF"]

    @pytest.mark.asyncio
    async def test_get_details_go_term_empty_name(self, adapter):
        """Test get_details skips term with empty name."""
        qgo = MagicMock()
        qgo.get_go_terms.return_value = [{"name": "", "aspect": "biological_process"}]
        with _patch_quickgo(qgo):
            assert await adapter.get_concept_details("GO:0008150") is None

    @pytest.mark.asyncio
    async def test_get_details_go_term_no_results(self, adapter):
        """Test get_details returns None when no results."""
        qgo = MagicMock()
        qgo.get_go_terms.return_value = []
        with _patch_quickgo(qgo):
            assert await adapter.get_concept_details("GO:0008150") is None

    @pytest.mark.asyncio
    async def test_get_details_go_term_error_object(self, adapter, caplog):
        """An HTTPResponseError return value is logged and returns None."""
        qgo = MagicMock()
        qgo.get_go_terms.return_value = HTTPResponseError()
        with _patch_quickgo(qgo), caplog.at_level(logging.ERROR):
            assert await adapter.get_concept_details("GO:0008150") is None
        assert "QuickGO term lookup failed" in caplog.text

    @pytest.mark.asyncio
    async def test_get_details_annotation(self, adapter):
        """Regression: gene product details read the dict page returned by Annotation."""
        qgo = MagicMock()
        qgo.Annotation.return_value = ANNOTATION_PAGE
        with _patch_quickgo(qgo):
            result = await adapter.get_concept_details("UniProtKB:P04637")

        assert result.primary_id == "UniProtKB:P04637_GO:0008285"
        assert result.concept_type == ConceptType.GENE_DISEASE_ASSOCIATION
        data = result.source_data[KnowledgeSource.QUICKGO]
        assert data["reference"] == "PMID:30514107"
        assert data["taxonId"] == 9606
        assert data["full_annotation"] == ANNOTATION_PAGE["results"][0]

    @pytest.mark.asyncio
    async def test_get_details_annotation_no_results(self, adapter):
        """Test get_details returns None for annotation with no results."""
        qgo = MagicMock()
        qgo.Annotation.return_value = {"numberOfHits": 0, "results": []}
        with _patch_quickgo(qgo):
            assert await adapter.get_concept_details("P12345") is None

    @pytest.mark.asyncio
    async def test_get_details_annotation_empty_gene_or_go(self, adapter):
        """Test get_details skips annotation with empty gene or go id."""
        qgo = MagicMock()
        qgo.Annotation.return_value = [{"geneProductId": "", "goId": ""}]
        with _patch_quickgo(qgo):
            assert await adapter.get_concept_details("P12345") is None

    @pytest.mark.asyncio
    async def test_get_details_free_text_makes_no_request(self, adapter):
        """IDs that are neither GO IDs nor gene products are not sent to QuickGO."""
        qgo = MagicMock()
        with _patch_quickgo(qgo):
            assert await adapter.get_concept_details("apoptosis") is None
        qgo.Annotation.assert_not_called()
        qgo.get_go_terms.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_details_exception(self, adapter):
        """Test get_details handles exceptions."""
        qgo = MagicMock()
        qgo.get_go_terms.side_effect = Exception("API Error")
        with _patch_quickgo(qgo):
            assert await adapter.get_concept_details("GO:0008150") is None
