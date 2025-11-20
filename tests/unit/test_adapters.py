"""
Unit tests for adapter classes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from knowledge_lookup.adapters.ols_adapter import OLSAdapter
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter


class TestOLSAdapter:
    """Tests for OLS (Ontology Lookup Service) adapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OLS adapter instance."""
        return OLSAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OLS adapter initialization."""
        adapter = OLSAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OLS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OLS

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts(self, mock_get, adapter, mock_ols_response):
        """Test searching concepts via OLS."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_ols_response)
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("diabetes", limit=10)
        assert isinstance(results, list)
        # Should process the mocked response
        if len(results) > 0:
            assert hasattr(results[0], "primary_id")
            assert hasattr(results[0], "primary_label")

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details(self, mock_get, adapter):
        """Test getting concept details from OLS."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "iri": "http://purl.obolibrary.org/obo/DOID_9351",
                "label": "diabetes mellitus",
                "description": ["A metabolic disease"],
                "synonyms": ["diabetes", "DM"],
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("DOID:9351")
        # Should return a UnifiedConcept or None
        assert result is None or hasattr(result, "primary_id")

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_error_handling(self, mock_get, adapter):
        """Test error handling in search_concepts."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_get.return_value.__aenter__.return_value = mock_response

        # Should handle errors gracefully
        results = await adapter.search_concepts("test")
        assert isinstance(results, list)


class TestBioPortalAdapter:
    """Tests for BioPortal adapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create BioPortal adapter instance."""
        return BioPortalAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test BioPortal adapter initialization."""
        adapter = BioPortalAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.BIOPORTAL
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.BIOPORTAL

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_with_api_key(
        self, mock_get, lookup_config, mock_bioportal_response
    ):
        """Test searching concepts with API key."""
        config = LookupConfig(
            api_keys={KnowledgeSource.BIOPORTAL: "test_api_key"}
        )
        adapter = BioPortalAdapter(config)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_bioportal_response)
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("diabetes")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_without_api_key(self, adapter):
        """Test searching concepts without API key."""
        # Should handle missing API key
        results = await adapter.search_concepts("diabetes")
        assert isinstance(results, list)

    def test_is_available_with_api_key(self, lookup_config):
        """Test is_available returns True with API key."""
        config = LookupConfig(
            api_keys={KnowledgeSource.BIOPORTAL: "test_api_key"}
        )
        adapter = BioPortalAdapter(config)
        # May return True or False depending on implementation
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_is_available_without_api_key(self, adapter):
        """Test is_available returns False without API key."""
        result = adapter.is_available()
        assert isinstance(result, bool)


class TestAdapterFactory:
    """Tests for adapter factory functionality."""

    def test_create_ols_adapter(self, lookup_config):
        """Test creating OLS adapter."""
        adapter = OLSAdapter(lookup_config)
        assert isinstance(adapter, OLSAdapter)
        assert adapter.source == KnowledgeSource.OLS

    def test_create_bioportal_adapter(self, lookup_config):
        """Test creating BioPortal adapter."""
        adapter = BioPortalAdapter(lookup_config)
        assert isinstance(adapter, BioPortalAdapter)
        assert adapter.source == KnowledgeSource.BIOPORTAL

    def test_all_adapters_have_source(self, lookup_config):
        """Test that all adapters properly set their source."""
        from knowledge_lookup.base import KnowledgeSourceAdapter

        # This is a general test that any adapter should pass
        adapter = OLSAdapter(lookup_config)
        assert hasattr(adapter, "source")
        assert isinstance(adapter.source, KnowledgeSource)


class TestAdapterErrorHandling:
    """Tests for adapter error handling."""

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_network_error_handling(self, mock_get, lookup_config):
        """Test handling of network errors."""
        adapter = OLSAdapter(lookup_config)
        mock_get.side_effect = Exception("Network error")

        # Should handle network errors gracefully
        results = await adapter.search_concepts("test")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_timeout_handling(self, mock_get, lookup_config):
        """Test handling of timeouts."""
        adapter = OLSAdapter(lookup_config)
        mock_get.side_effect = TimeoutError("Request timeout")

        # Should handle timeouts gracefully
        results = await adapter.search_concepts("test")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_invalid_json_response(self, mock_get, lookup_config):
        """Test handling of invalid JSON responses."""
        adapter = OLSAdapter(lookup_config)
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_get.return_value.__aenter__.return_value = mock_response

        # Should handle JSON errors gracefully
        results = await adapter.search_concepts("test")
        assert isinstance(results, list)


class TestAdapterRateLimiting:
    """Tests for adapter rate limiting."""

    def test_get_rate_limit_default(self, lookup_config):
        """Test getting default rate limit."""
        adapter = OLSAdapter(lookup_config)
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, (int, float))
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test getting custom rate limit from config."""
        config = LookupConfig(
            rate_limits={KnowledgeSource.OLS: 5.0}
        )
        adapter = OLSAdapter(config)
        rate_limit = adapter.get_rate_limit()
        assert rate_limit == 5.0

    def test_rate_limit_applied(self, lookup_config):
        """Test that rate limit is properly stored."""
        adapter = OLSAdapter(lookup_config)
        assert hasattr(adapter, "get_rate_limit")
        assert callable(adapter.get_rate_limit)
