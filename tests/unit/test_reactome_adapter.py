"""
Unit tests for ReactomeAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.reactome_adapter import ReactomeAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestReactomeAdapter:
    """Tests for ReactomeAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create ReactomeAdapter instance."""
        return ReactomeAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test ReactomeAdapter initialization."""
        adapter = ReactomeAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.REACTOME
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.REACTOME

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
        config = LookupConfig(rate_limits={KnowledgeSource.REACTOME: 5.0})
        adapter = ReactomeAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_with_pathway_results(self, adapter):
        """Test search_concepts with pathway results."""
        reactome_data = {
            "results": [
                {"stId": "R-HSA-1640170", "name": "Cell Cycle", "type": "Pathway", "summation": "The cell cycle.", "species": ["Homo sapiens"]},
                {"stId": "R-HSA-109581", "name": "Apoptosis", "type": "Pathway", "summation": "Programmed cell death.", "species": ["Homo sapiens"]},
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            results = await adapter.search_concepts("cell cycle", limit=10)
            assert len(results) == 2
            assert results[0].primary_id == "R-HSA-1640170"

    @pytest.mark.asyncio
    async def test_search_concepts_filters_non_pathway(self, adapter):
        """Test search filters out non-Pathway/Reaction types."""
        reactome_data = {
            "results": [
                {"stId": "R-HSA-1640170", "name": "Cell Cycle", "type": "Pathway"},
                {"stId": "R-HSA-123456", "name": "Some other type", "type": "Other"},
                {"stId": "R-HSA-109581", "name": "Apoptosis", "type": "Reaction"},
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            results = await adapter.search_concepts("test", limit=10)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_result_conversion_returns_none(self, adapter):
        """Test search when _convert_reactome_result returns None."""
        reactome_data = {"results": [{"type": "Pathway"}]}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            with patch.object(adapter, "_convert_reactome_result_to_concept", return_value=None):
                results = await adapter.search_concepts("test")
                assert len(results) == 0

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
        """Test successful get_concept_details."""
        data = {"stId": "R-HSA-1640170", "displayName": "Cell Cycle", "dbId": 1640170, "summation": [{"text": "The cell cycle."}]}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is not None
            assert result.primary_id == "R-HSA-1640170"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_dbid(self, adapter):
        """Test get_concept_details when no 'dbId' in response."""
        data = {"name": "something"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_data(self, adapter):
        """Test get_concept_details with empty data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is None

    def test_convert_reactome_result_full(self, adapter):
        """Test _convert_reactome_result_to_concept with all fields."""
        result = {
            "stId": "R-HSA-1640170", "name": "Cell Cycle",
            "summation": "The cell cycle describes the series of events.",
            "species": ["Homo sapiens", "Mus musculus"],
        }
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "R-HSA-1640170"
        assert concept.primary_label == "Cell Cycle"
        assert "The cell cycle describes the series of events." in concept.definitions
        assert "Homo sapiens" in concept.categories
        assert concept.confidence_score == 0.9

    def test_convert_reactome_result_no_stid(self, adapter):
        """Test _convert_reactome_result_to_concept with missing stId."""
        result = {"name": "Cell Cycle"}
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is None

    def test_convert_reactome_result_no_name(self, adapter):
        """Test _convert_reactome_result_to_concept with missing name."""
        result = {"stId": "R-HSA-1640170"}
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is None

    def test_convert_reactome_result_no_summation_no_species(self, adapter):
        """Test _convert_reactome_result without optional fields."""
        result = {"stId": "R-HSA-1640170", "name": "Cell Cycle"}
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_reactome_result_error(self, adapter):
        """Test _convert_reactome_result error handling."""
        concept = adapter._convert_reactome_result_to_concept(None)
        assert concept is None

    def test_convert_reactome_details_full(self, adapter):
        """Test _convert_reactome_details_to_concept with all fields."""
        data = {
            "stId": "R-HSA-1640170", "displayName": "Cell Cycle",
            "summation": [{"text": "The cell cycle describes the series of events."}],
        }
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is not None
        assert concept.primary_id == "R-HSA-1640170"
        assert concept.primary_label == "Cell Cycle"
        assert "The cell cycle describes the series of events." in concept.definitions
        assert concept.confidence_score == 1.0

    def test_convert_reactome_details_no_stid(self, adapter):
        """Test _convert_reactome_details_to_concept with missing stId."""
        data = {"displayName": "Cell Cycle"}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is None

    def test_convert_reactome_details_no_display_name(self, adapter):
        """Test _convert_reactome_details_to_concept with missing displayName."""
        data = {"stId": "R-HSA-1640170"}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is None

    def test_convert_reactome_details_no_summation(self, adapter):
        """Test _convert_reactome_details_to_concept without summation."""
        data = {"stId": "R-HSA-1640170", "displayName": "Cell Cycle"}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is not None
        assert len(concept.definitions) == 0

    def test_convert_reactome_details_empty_summation(self, adapter):
        """Test _convert_reactome_details_to_concept with empty summation list."""
        data = {"stId": "R-HSA-1640170", "displayName": "Cell Cycle", "summation": []}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is not None

    def test_convert_reactome_details_error(self, adapter):
        """Test _convert_reactome_details error handling."""
        concept = adapter._convert_reactome_details_to_concept(None)
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
