"""
Unit tests for STRINGAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from knowledge_lookup.adapters.string_adapter import STRINGAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestSTRINGAdapter:
    """Tests for STRINGAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create STRINGAdapter instance."""
        return STRINGAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test STRINGAdapter initialization."""
        adapter = STRINGAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.STRING
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.STRING

    def test_is_available(self, adapter):
        """Test is_available returns True."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.STRING: 2.0})
        adapter = STRINGAdapter(config)
        assert adapter.get_rate_limit() == 2.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[
                {
                    "stringId": "9606.ENSP00000269305",
                    "preferredName": "TP53",
                    "annotation": "Cellular tumor antigen p53",
                    "taxonId": 9606,
                }
            ]
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("TP53", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_id == "STRING:9606.ENSP00000269305"
        assert results[0].primary_label == "TP53"

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
            return_value=[
                {
                    "stringId": "9606.ENSP00000269305",
                    "preferredName": "TP53",
                    "annotation": "Cellular tumor antigen p53",
                    "taxonId": 9606,
                }
            ]
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("STRING:9606.ENSP00000269305")
        assert result is not None
        assert result.primary_id == "STRING:9606.ENSP00000269305"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when result is empty."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[])
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("STRING:UNKNOWN")
        assert result is None

    @staticmethod
    def _resolve_item():
        """Shape of a current /json/resolve (get_string_ids) row."""
        return {
            "queryIndex": 0,
            "queryItem": "TP53",
            "stringId": "9606.ENSP00000269305",
            "ncbiTaxonId": 9606,
            "taxonName": "Homo sapiens",
            "preferredName": "TP53",
            "annotation": "Cellular tumor antigen p53; Acts as a tumor suppressor.",
        }

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_text_json_content_type(self, mock_get, adapter):
        """Regression: STRING serves ``text/json``; the JSON must still be decoded."""

        async def strict_json(*args, **kwargs):
            # Mimic aiohttp: reject a non-JSON mimetype unless the check is disabled
            if kwargs.get("content_type", "application/json") is not None:
                raise aiohttp.ContentTypeError(
                    MagicMock(),
                    (),
                    message="Attempt to decode JSON with unexpected mimetype: text/json",
                )
            return [self._resolve_item()]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/json; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(side_effect=strict_json)
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("TP53", limit=3)
        assert len(results) == 1
        assert results[0].primary_id == "STRING:9606.ENSP00000269305"
        mock_response.json.assert_awaited_with(content_type=None)

    def test_convert_reads_ncbi_taxon_id(self, adapter):
        """Current responses name the taxon ``ncbiTaxonId``."""
        concept = adapter._convert_resolve_to_concept(self._resolve_item())
        assert concept.categories == ["taxon:9606"]
        assert concept.definitions == ["Cellular tumor antigen p53; Acts as a tumor suppressor."]

    @pytest.mark.asyncio
    async def test_get_concept_details_interaction_partners(self, adapter):
        """Partners come from /json/interaction_partners, once each, excluding the query."""
        partners = [
            {
                "stringId_A": "9606.ENSP00000269305",
                "stringId_B": "9606.ENSP00000340989",
                "preferredName_A": "TP53",
                "preferredName_B": "SFN",
                "ncbiTaxonId": "9606",
                "score": 0.999,
            },
            {
                "stringId_A": "9606.ENSP00000269305",
                "stringId_B": "9606.ENSP00000263253",
                "preferredName_A": "TP53",
                "preferredName_B": "EP300",
                "ncbiTaxonId": "9606",
                "score": 0.998,
            },
            {
                "stringId_A": "9606.ENSP00000269305",
                "stringId_B": "9606.ENSP00000340989",
                "preferredName_A": "TP53",
                "preferredName_B": "SFN",
                "ncbiTaxonId": "9606",
                "score": 0.999,
            },
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [[self._resolve_item()], partners]
            result = await adapter.get_concept_details("TP53")
        assert result.related == ["SFN(score=0.999)", "EP300(score=0.998)"]
        url, params = mock_req.call_args.args
        assert url.endswith("/json/interaction_partners")
        assert params["identifiers"] == "9606.ENSP00000269305"

    @pytest.mark.asyncio
    async def test_get_concept_details_partner_failure_keeps_concept(self, adapter):
        """A failed partner request still returns the resolved protein."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [[self._resolve_item()], Exception("boom")]
            result = await adapter.get_concept_details("STRING:9606.ENSP00000269305")
        assert result is not None
        assert result.related == []

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("STRING:9606.ENSP00000269305")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
