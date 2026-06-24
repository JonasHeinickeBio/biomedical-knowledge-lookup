"""
Unit tests for HPOAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.hpo_adapter import HPOAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestHPOAdapter:
    """Tests for HPOAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create HPOAdapter instance."""
        return HPOAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test HPOAdapter initialization."""
        adapter = HPOAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.HPO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.HPO

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.HPO: 5.0})
        adapter = HPOAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_with_terms(self, adapter):
        """Test search_concepts when API returns terms (lines 39-42)."""
        hpo_data = {
            "terms": [
                {"id": "HP:0000118", "name": "Phenotypic abnormality", "synonyms": ["abnormal phenotype"]},
                {"id": "HP:0000819", "name": "Diabetes mellitus", "synonyms": ["diabetes"]},
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = hpo_data
            results = await adapter.search_concepts("diabetes", limit=10)
            assert len(results) == 2
            assert results[0].primary_id == "HP:0000118"

    @pytest.mark.asyncio
    async def test_search_concepts_term_conversion_returns_none(self, adapter):
        """Test search when _convert_hpo_result_to_concept returns None."""
        hpo_data = {"terms": [{"invalid": "data"}]}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = hpo_data
            with patch.object(adapter, "_convert_hpo_result_to_concept", return_value=None):
                results = await adapter.search_concepts("test")
                assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_no_terms_key(self, adapter):
        """Test search when response has no 'terms' key."""
        data = {"error": "not found"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            results = await adapter.search_concepts("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            results = await adapter.search_concepts("test")
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter):
        """Test successful get_concept_details (lines 59-60)."""
        data = {
            "details": {
                "id": "HP:0000118",
                "name": "Phenotypic abnormality",
                "synonyms": ["abnormal phenotype"],
                "definition": "A phenotypic abnormality.",
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("HP:0000118")
            assert result is not None
            assert result.primary_id == "HP:0000118"

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling (lines 64-66)."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("HP:0000118")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_details_key(self, adapter):
        """Test get_concept_details with no 'details' key."""
        data = {"error": "not found"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("HP:0000118")
            assert result is None

    def test_convert_hpo_result_full(self, adapter):
        """Test _convert_hpo_result_to_concept with all fields (lines 70-95)."""
        result = {
            "id": "HP:0000118",
            "name": "Phenotypic abnormality",
            "synonyms": ["abnormal phenotype", "phenotype abnormality"],
        }
        concept = adapter._convert_hpo_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "HP:0000118"
        assert concept.primary_label == "Phenotypic abnormality"
        assert "abnormal phenotype" in concept.synonyms
        assert concept.confidence_score == 0.95

    def test_convert_hpo_result_no_id(self, adapter):
        """Test _convert_hpo_result_to_concept with missing id (returns None)."""
        result = {"name": "Some term"}
        concept = adapter._convert_hpo_result_to_concept(result)
        assert concept is None

    def test_convert_hpo_result_no_name(self, adapter):
        """Test _convert_hpo_result_to_concept with missing name (returns None)."""
        result = {"id": "HP:0000118"}
        concept = adapter._convert_hpo_result_to_concept(result)
        assert concept is None

    def test_convert_hpo_result_no_synonyms(self, adapter):
        """Test _convert_hpo_result_to_concept without synonyms."""
        result = {"id": "HP:0000118", "name": "Phenotypic abnormality"}
        concept = adapter._convert_hpo_result_to_concept(result)
        assert concept is not None
        assert len(concept.synonyms) == 0

    def test_convert_hpo_result_error(self, adapter):
        """Test _convert_hpo_result_to_concept with error-causing data."""
        concept = adapter._convert_hpo_result_to_concept(None)
        assert concept is None

    def test_convert_hpo_details_full(self, adapter):
        """Test _convert_hpo_details_to_concept with all fields (lines 99-127)."""
        details = {
            "id": "HP:0000118",
            "name": "Phenotypic abnormality",
            "synonyms": ["abnormal phenotype"],
            "definition": "A phenotypic abnormality.",
        }
        concept = adapter._convert_hpo_details_to_concept(details)
        assert concept is not None
        assert concept.primary_id == "HP:0000118"
        assert concept.primary_label == "Phenotypic abnormality"
        assert "abnormal phenotype" in concept.synonyms
        assert "A phenotypic abnormality." in concept.definitions
        assert concept.confidence_score == 1.0

    def test_convert_hpo_details_no_id(self, adapter):
        """Test _convert_hpo_details_to_concept with missing id."""
        details = {"name": "Some term"}
        concept = adapter._convert_hpo_details_to_concept(details)
        assert concept is None

    def test_convert_hpo_details_no_name(self, adapter):
        """Test _convert_hpo_details_to_concept with missing name."""
        details = {"id": "HP:0000118"}
        concept = adapter._convert_hpo_details_to_concept(details)
        assert concept is None

    def test_convert_hpo_details_no_synonyms_no_definition(self, adapter):
        """Test _convert_hpo_details_to_concept without optional fields."""
        details = {"id": "HP:0000118", "name": "Phenotypic abnormality"}
        concept = adapter._convert_hpo_details_to_concept(details)
        assert concept is not None
        assert len(concept.synonyms) == 0
        assert len(concept.definitions) == 0

    def test_convert_hpo_details_error(self, adapter):
        """Test _convert_hpo_details_to_concept with error-causing data."""
        concept = adapter._convert_hpo_details_to_concept(None)
        assert concept is None

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
