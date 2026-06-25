"""
Unit tests for HGNCAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from knowledge_lookup.adapters.hgnc_adapter import HGNCAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestHGNCAdapter:
    """Tests for HGNCAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create HGNCAdapter instance."""
        return HGNCAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test HGNCAdapter initialization."""
        adapter = HGNCAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.HGNC
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.HGNC

    def test_is_available(self, adapter):
        """Test is_available returns True (public API)."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, (int, float))
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.HGNC: 3.0})
        adapter = HGNCAdapter(config)
        assert adapter.get_rate_limit() == 3.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "response": {
                    "docs": [
                        {
                            "hgnc_id": "HGNC:1100",
                            "symbol": "BRCA1",
                            "name": "BRCA1 DNA repair associated",
                            "location": "17q21.31",
                            "entrez_id": "672",
                            "ensembl_gene_id": "ENSG00000012048",
                        }
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("BRCA1", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_id == "HGNC:1100"
        assert results[0].primary_label == "BRCA1 DNA repair associated"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {"docs": []}})
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
    async def test_get_concept_details_by_hgnc_id(self, mock_get, adapter):
        """Test get_concept_details using HGNC ID."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "response": {
                    "docs": [
                        {
                            "hgnc_id": "HGNC:1100",
                            "symbol": "BRCA1",
                            "name": "BRCA1 DNA repair associated",
                        }
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("HGNC:1100")
        assert result is not None
        assert result.primary_id == "HGNC:1100"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when no result is found."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {"docs": []}})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("UNKNOWN_GENE")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("HGNC:1100")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("HGNC:1100")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
