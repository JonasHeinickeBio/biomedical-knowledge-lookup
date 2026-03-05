"""
Unit tests for BioPortalAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestBioPortalAdapter:
    """Tests for BioPortalAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create BioPortalAdapter instance."""
        return BioPortalAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create BioPortalAdapter with API key."""
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test BioPortalAdapter initialization."""
        adapter = BioPortalAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.BIOPORTAL
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.BIOPORTAL

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
        config = LookupConfig(rate_limits={KnowledgeSource.BIOPORTAL: 5.0})
        adapter = BioPortalAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter_with_api_key):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"collection": []})  # Mock response structure
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_api_key.search_concepts("test query", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter_with_api_key):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"collection": []})
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_api_key.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_http_error(self, mock_get, adapter_with_api_key):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500, message="Internal Server Error"
            )
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_api_key.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_network_error(self, mock_get, adapter_with_api_key):
        """Test search concepts with network error."""
        mock_get.side_effect = Exception("Network error")

        results = await adapter_with_api_key.search_concepts("test")
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
