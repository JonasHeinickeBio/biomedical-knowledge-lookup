"""
Unit tests for COSMICAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from knowledge_lookup.adapters.cosmic_adapter import COSMICAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit
class TestCOSMICAdapter:
    """Tests for COSMICAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create COSMICAdapter instance without API key."""
        return COSMICAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create COSMICAdapter with API key."""
        config = LookupConfig(api_keys={"cosmic": "dGVzdF9rZXk="})  # base64 encoded
        return COSMICAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test COSMICAdapter initialization."""
        adapter = COSMICAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.COSMIC
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.COSMIC

    def test_is_available(self, adapter):
        """Test is_available returns True."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, (int, float))
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.COSMIC: 2.0})
        adapter = COSMICAdapter(config)
        assert adapter.get_rate_limit() == 2.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success_list(self, mock_get, adapter):
        """Test successful search returning a list."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[
                {
                    "id": "TP53",
                    "gene_name": "TP53",
                    "role_in_cancer": "TSG",
                    "tier": "1",
                }
            ]
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("TP53", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_id == "COSMIC:TP53"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_dict_response(self, mock_get, adapter):
        """Test search with dict response containing 'genes' key."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "genes": [
                    {"id": "BRCA1", "gene_name": "BRCA1", "role_in_cancer": "TSG", "tier": "1"}
                ]
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("BRCA1", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[])
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_http_error(self, mock_get, adapter):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500, message="Internal Server Error"
            )
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_network_error(self, mock_get, adapter):
        """Test search concepts with network error."""
        mock_get.side_effect = Exception("Network error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_success(self, mock_get, adapter):
        """Test get_concept_details with valid ID."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"id": "TP53", "gene_name": "TP53", "tier": "1"}
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("COSMIC:TP53")
        assert result is not None
        assert result.primary_id == "COSMIC:TP53"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when result is empty."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("COSMIC:UNKNOWN")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("COSMIC:TP53")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
