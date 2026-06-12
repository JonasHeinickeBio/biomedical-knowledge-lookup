"""
Unit tests for UMLSAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.umls_adapter import UMLSAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestUMLSAdapter:
    """Tests for UMLSAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create UMLSAdapter instance."""
        return UMLSAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create UMLSAdapter with API key."""
        config = LookupConfig(api_keys={"umls": "test_api_key"})
        return UMLSAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test UMLSAdapter initialization."""
        adapter = UMLSAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.UMLS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.UMLS

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
        config = LookupConfig(rate_limits={KnowledgeSource.UMLS: 5.0})
        adapter = UMLSAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, adapter):
        """Test successful search concepts."""
        # Mock the UMLS client to return results
        mock_client = MagicMock()
        mock_client.search_concepts.return_value = []
        adapter.client = mock_client

        results = await adapter.search_concepts("test query", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_empty_response(self, adapter):
        """Test search concepts with empty response."""
        # Mock the UMLS client to return empty results
        mock_client = MagicMock()
        mock_client.search_concepts.return_value = []
        adapter.client = mock_client

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_http_error(self, adapter):
        """Test search concepts with HTTP error."""
        mock_client = MagicMock()
        mock_client.search_concepts.side_effect = Exception("HTTP Error")
        adapter.client = mock_client

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        mock_client = MagicMock()
        mock_client.search_concepts.side_effect = Exception("Network error")
        adapter.client = mock_client

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

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
            pass  # Should not raise any exceptions
