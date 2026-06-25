"""
Unit tests for OMIMAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from knowledge_lookup.adapters.omim_adapter import OMIMAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestOMIMAdapter:
    """Tests for OMIMAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OMIMAdapter instance without API key."""
        return OMIMAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create OMIMAdapter with API key."""
        config = LookupConfig(api_keys={"omim": "test_omim_key"})
        return OMIMAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test OMIMAdapter initialization."""
        adapter = OMIMAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OMIM
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OMIM

    def test_is_available_without_key(self, adapter):
        """Test is_available returns False without API key."""
        assert adapter.is_available() is False

    def test_is_available_with_key(self, adapter_with_api_key):
        """Test is_available returns True with API key."""
        assert adapter_with_api_key.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.OMIM: 2.0})
        adapter = OMIMAdapter(config)
        assert adapter.get_rate_limit() == 2.0

    @pytest.mark.asyncio
    async def test_search_concepts_no_api_key(self, adapter):
        """Test search concepts returns empty list without API key."""
        results = await adapter.search_concepts("diabetes")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter_with_api_key):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "omim": {
                    "searchResponse": {
                        "entryList": [
                            {
                                "entry": {
                                    "mimNumber": 143100,
                                    "titles": {
                                        "preferredTitle": "HUNTINGTON DISEASE; HD",
                                        "alternativeTitles": "HUNTINGTON CHOREA;;HD",
                                        "includedTitles": "",
                                    },
                                    "type": "phenotype",
                                }
                            }
                        ]
                    }
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_api_key.search_concepts("huntington", limit=5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_id == "OMIM:143100"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter_with_api_key):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"omim": {"searchResponse": {"entryList": []}}}
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_api_key.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_http_error(self, mock_get, adapter_with_api_key):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=403, message="Forbidden"
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
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_success(self, mock_get, adapter_with_api_key):
        """Test get_concept_details with valid ID."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "omim": {
                    "entryList": [
                        {
                            "entry": {
                                "mimNumber": 143100,
                                "titles": {
                                    "preferredTitle": "HUNTINGTON DISEASE; HD",
                                    "alternativeTitles": "",
                                    "includedTitles": "",
                                },
                                "type": "phenotype",
                            }
                        }
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.get_concept_details("OMIM:143100")
        assert result is not None
        assert result.primary_id == "OMIM:143100"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_api_key(self, adapter):
        """Test get_concept_details returns None without API key."""
        result = await adapter.get_concept_details("OMIM:143100")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("OMIM:143100")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
