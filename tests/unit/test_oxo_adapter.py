"""
Unit tests for OxOAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.oxo_adapter import OxOAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestOxOAdapter:
    """Tests for OxOAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OxOAdapter instance."""
        return OxOAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OxOAdapter initialization."""
        adapter = OxOAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OXO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OXO

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
        config = LookupConfig(rate_limits={KnowledgeSource.OXO: 5.0})
        adapter = OxOAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, adapter):
        """Test successful search concepts."""
        # Mock the session post response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"_embedded": {"searchResults": []}}
        )
        mock_post_context = AsyncMock()
        mock_post_context.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value = mock_post_context

            results = await adapter.search_concepts("test query", limit=10)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_empty_response(self, adapter):
        """Test search concepts with empty response."""
        # Mock the session post response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"_embedded": {"searchResults": []}}
        )
        mock_post_context = AsyncMock()
        mock_post_context.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value = mock_post_context

            results = await adapter.search_concepts("nonexistent", limit=10)
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_http_error(self, adapter):
        """Test search concepts with HTTP error."""
        # Mock the session post response to raise an error
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 error")
        mock_post_context = AsyncMock()
        mock_post_context.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value = mock_post_context

            results = await adapter.search_concepts("test")
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        # Mock the session post response to raise an error
        mock_post_context = AsyncMock()
        mock_post_context.__aenter__.side_effect = Exception("Network error")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value = mock_post_context

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
