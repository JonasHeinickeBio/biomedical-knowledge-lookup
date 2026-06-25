"""
Unit tests for DrugBankAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.drugbank_adapter import DrugBankAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class TestDrugBankAdapter:
    """Tests for DrugBankAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create DrugBankAdapter instance."""
        return DrugBankAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test DrugBankAdapter initialization."""
        adapter = DrugBankAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.DRUGBANK
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.DRUGBANK

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert result is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.DRUGBANK: 5.0})
        adapter = DrugBankAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- search_concepts (lines 32-57) ---

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts returns converted concepts."""
        mock_data = {
            "response": {
                "docs": [
                    {
                        "short_form": "DB00001",
                        "label": "Test Drug",
                        "iri": "http://purl.bioontology.org/ontology/DRUGBANK/DB00001",
                    }
                ]
            }
        }
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=mock_data
        ):
            results = await adapter.search_concepts("test", limit=10)
        assert len(results) == 1
        assert results[0].primary_id == "DB00001"

    @pytest.mark.asyncio
    async def test_search_concepts_no_response_key(self, adapter):
        """Test search_concepts with missing response key."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value={}):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_no_docs_key(self, adapter):
        """Test search_concepts with missing docs key."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={"response": {}}
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search_concepts returns empty on exception."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_empty_docs(self, adapter):
        """Test search_concepts with empty docs list."""
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value={"response": {"docs": []}},
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_none_concept_filtered(self, adapter):
        """Test search_concepts filters None concepts from conversion."""
        mock_data = {
            "response": {
                "docs": [
                    {"short_form": "", "label": ""},  # empty -> None
                    {"short_form": "DB00001", "label": "Valid"},
                ]
            }
        }
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=mock_data
        ):
            results = await adapter.search_concepts("test")
        assert len(results) == 1

    # --- get_concept_details (lines 59-75) ---

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter):
        """Test get_concept_details returns concept."""
        mock_data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "iri": "http://purl.bioontology.org/ontology/DRUGBANK/DB00001",
            "synonyms": ["TestSynonym"],
            "description": ["A test drug"],
        }
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await adapter.get_concept_details("DB00001")
        assert result is not None
        assert result.primary_id == "DB00001"

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_data(self, adapter):
        """Test get_concept_details returns None with empty data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value={}):
            result = await adapter.get_concept_details("DB00001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_none_data(self, adapter):
        """Test get_concept_details returns None with None data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value=None):
            result = await adapter.get_concept_details("DB00001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter):
        """Test get_concept_details returns None on exception."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            result = await adapter.get_concept_details("DB00001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_concept_is_none(self, adapter):
        """Test get_concept_details returns None when conversion fails."""
        mock_data = {"short_form": "", "label": ""}
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await adapter.get_concept_details("DB00001")
        assert result is None

    # --- _convert_drugbank_result_to_concept (lines 77-105) ---

    def test_convert_result_basic(self, adapter):
        """Test _convert_drugbank_result_to_concept with basic data."""
        result_data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "iri": "http://example.com",
        }
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert concept is not None
        assert concept.primary_id == "DB00001"
        assert concept.primary_label == "Test Drug"
        assert concept.concept_type == ConceptType.DRUG

    def test_convert_result_no_short_form(self, adapter):
        """Test _convert_drugbank_result_to_concept returns None without short_form."""
        result_data = {"label": "Test Drug"}
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert concept is None

    def test_convert_result_no_label(self, adapter):
        """Test _convert_drugbank_result_to_concept returns None without label."""
        result_data = {"short_form": "DB00001"}
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert concept is None

    def test_convert_result_with_synonyms(self, adapter):
        """Test _convert_drugbank_result_to_concept includes synonyms."""
        result_data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "synonym": ["Syn1", "Syn2"],
        }
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert "Syn1" in concept.synonyms
        assert "Syn2" in concept.synonyms

    def test_convert_result_with_description(self, adapter):
        """Test _convert_drugbank_result_to_concept includes description."""
        result_data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "description": ["A test drug description"],
        }
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert "A test drug description" in concept.definitions

    def test_convert_result_with_iri(self, adapter):
        """Test _convert_drugbank_result_to_concept adds identifier with IRI."""
        result_data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "iri": "http://example.com/drug",
        }
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert len(concept.identifiers) == 1
        assert concept.identifiers[0].url == "http://example.com/drug"

    def test_convert_result_no_synonyms_no_description(self, adapter):
        """Test _convert_drugbank_result_to_concept handles missing optional fields."""
        result_data = {"short_form": "DB00001", "label": "Test Drug"}
        concept = adapter._convert_drugbank_result_to_concept(result_data)
        assert concept.synonyms == []
        assert concept.definitions == []

    def test_convert_result_exception(self, adapter):
        """Test _convert_drugbank_result_to_concept returns None on exception."""
        concept = adapter._convert_drugbank_result_to_concept(None)
        assert concept is None

    # --- _convert_drugbank_details_to_concept (lines 107-135) ---

    def test_convert_details_basic(self, adapter):
        """Test _convert_drugbank_details_to_concept with basic data."""
        data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "iri": "http://example.com",
        }
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert concept is not None
        assert concept.primary_id == "DB00001"
        assert concept.primary_label == "Test Drug"
        assert concept.confidence_score == 0.95
        assert concept.concept_type == ConceptType.DRUG

    def test_convert_details_no_short_form(self, adapter):
        """Test _convert_drugbank_details_to_concept returns None without short_form."""
        data = {"label": "Test Drug"}
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert concept is None

    def test_convert_details_no_label(self, adapter):
        """Test _convert_drugbank_details_to_concept returns None without label."""
        data = {"short_form": "DB00001"}
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert concept is None

    def test_convert_details_with_synonyms(self, adapter):
        """Test _convert_drugbank_details_to_concept includes synonyms."""
        data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "synonyms": ["Syn1", "Syn2"],
        }
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert "Syn1" in concept.synonyms
        assert "Syn2" in concept.synonyms

    def test_convert_details_with_description(self, adapter):
        """Test _convert_drugbank_details_to_concept includes description."""
        data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "description": ["A test drug description"],
        }
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert "A test drug description" in concept.definitions

    def test_convert_details_with_iri(self, adapter):
        """Test _convert_drugbank_details_to_concept adds identifier with IRI."""
        data = {
            "short_form": "DB00001",
            "label": "Test Drug",
            "iri": "http://example.com/drug",
        }
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert len(concept.identifiers) == 1
        assert concept.identifiers[0].url == "http://example.com/drug"

    def test_convert_details_no_synonyms_no_description(self, adapter):
        """Test _convert_drugbank_details_to_concept handles missing optional fields."""
        data = {"short_form": "DB00001", "label": "Test Drug"}
        concept = adapter._convert_drugbank_details_to_concept(data)
        assert concept.synonyms == []
        assert concept.definitions == []

    def test_convert_details_exception(self, adapter):
        """Test _convert_drugbank_details_to_concept returns None on exception."""
        concept = adapter._convert_drugbank_details_to_concept(None)
        assert concept is None
