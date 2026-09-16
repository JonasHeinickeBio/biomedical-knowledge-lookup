"""
Unit tests for COSMICAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from knowledge_lookup.adapters.cosmic_adapter import COSMICAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

API_KEY = "dGVzdEBleGFtcGxlLm9yZzpzZWNyZXQ="  # base64("test@example.org:secret")
LOGGER = "knowledge_lookup.adapters.cosmic_adapter.logger"


class TestCOSMICAdapter:
    """Tests for COSMICAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create COSMICAdapter instance without credentials."""
        with patch("os.getenv", return_value=None):
            return COSMICAdapter(LookupConfig())

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create COSMICAdapter with credentials."""
        config = LookupConfig(api_keys={"cosmic": API_KEY})
        return COSMICAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test COSMICAdapter initialization."""
        adapter = COSMICAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.COSMIC
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.COSMIC

    def test_is_available_without_credentials(self, adapter):
        """Regression: COSMIC needs a registered account, so no credentials -> unavailable."""
        assert adapter.api_key is None
        assert adapter.is_available() is False

    def test_is_available_with_credentials(self, adapter_with_api_key):
        """Configured credentials make the adapter available."""
        assert adapter_with_api_key.is_available() is True

    def test_is_available_with_env_credentials(self):
        """COSMIC_API_KEY from the environment is picked up."""
        with patch.dict("os.environ", {"COSMIC_API_KEY": API_KEY}):
            adapter = COSMICAdapter(LookupConfig())
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.COSMIC: 2.0})
        adapter = COSMICAdapter(config)
        assert adapter.get_rate_limit() == 2.0

    @pytest.mark.asyncio
    async def test_search_without_credentials_skips_request(self, adapter):
        """Without credentials search logs why and makes no request."""
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req,
            patch(LOGGER) as mock_logger,
        ):
            results = await adapter.search_concepts("BRAF")
        assert results == []
        mock_req.assert_not_awaited()
        assert "registered account" in mock_logger.warning.call_args.args[0]

    @pytest.mark.asyncio
    async def test_details_without_credentials_skips_request(self, adapter):
        """Without credentials details logs why and makes no request."""
        with (
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req,
            patch(LOGGER) as mock_logger,
        ):
            result = await adapter.get_concept_details("COSMIC:BRAF")
        assert result is None
        mock_req.assert_not_awaited()
        assert "COSMIC_API_KEY" in mock_logger.warning.call_args.args[0]

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success_list(self, mock_get, adapter_with_api_key):
        """Test successful search returning a list, sending Basic credentials."""
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

        results = await adapter_with_api_key.search_concepts("TP53", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_id == "COSMIC:TP53"
        assert mock_get.call_args.kwargs["headers"]["Authorization"] == f"Basic {API_KEY}"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_dict_response(self, mock_get, adapter_with_api_key):
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

        results = await adapter_with_api_key.search_concepts("BRCA1", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter_with_api_key):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[])
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_api_key.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_404_explains_retired_endpoint(self, adapter_with_api_key):
        """The legacy REST endpoint answers 404; the log says why."""
        error = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=404, message="Not Found"
        )
        with (
            patch.object(
                adapter_with_api_key, "_make_request", new_callable=AsyncMock, side_effect=error
            ),
            patch(LOGGER) as mock_logger,
        ):
            results = await adapter_with_api_key.search_concepts("BRAF")
        assert results == []
        assert "authenticated file downloads" in mock_logger.error.call_args.args[0]

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
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_success(self, mock_get, adapter_with_api_key):
        """Test get_concept_details with valid ID."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"id": "TP53", "gene_name": "TP53", "tier": "1"}
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.get_concept_details("COSMIC:TP53")
        assert result is not None
        assert result.primary_id == "COSMIC:TP53"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter_with_api_key):
        """Test get_concept_details when result is empty."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.get_concept_details("COSMIC:UNKNOWN")
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
