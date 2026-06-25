"""
Unit tests for PDBAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from knowledge_lookup.adapters.pdb_adapter import PDBAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestPDBAdapter:
    """Tests for PDBAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create PDBAdapter instance."""
        return PDBAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test PDBAdapter initialization."""
        adapter = PDBAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.PDB
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.PDB

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
        config = LookupConfig(rate_limits={KnowledgeSource.PDB: 5.0})
        adapter = PDBAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, mock_post, adapter):
        """Test successful search concepts."""
        # Mock the POST search response
        post_response = AsyncMock()
        post_response.status = 200
        post_response.raise_for_status = MagicMock()
        post_response.json = AsyncMock(return_value={"result_set": [{"identifier": "1ABC"}]})
        mock_post.return_value.__aenter__.return_value = post_response

        # Mock the GET entry summary response
        get_response = AsyncMock()
        get_response.status = 200
        get_response.raise_for_status = MagicMock()
        get_response.json = AsyncMock(
            return_value={
                "entry": {"id": "1ABC"},
                "struct": {
                    "title": "CRYSTAL STRUCTURE OF HUMAN HEMOGLOBIN",
                    "pdbx_descriptor": "Hemoglobin",
                },
            }
        )
        mock_get.return_value.__aenter__.return_value = get_response

        results = await adapter.search_concepts("hemoglobin", limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_search_concepts_empty_response(self, mock_post, adapter):
        """Test search concepts with empty result."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"result_set": []})
        mock_post.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_search_concepts_http_error(self, mock_post, adapter):
        """Test search concepts with HTTP error."""
        mock_post.side_effect = Exception("HTTP 500 Internal Server Error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_search_concepts_network_error(self, mock_post, adapter):
        """Test search concepts with network error."""
        mock_post.side_effect = Exception("Network error")

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
            return_value={
                "entry": {"id": "1ABC"},
                "struct": {
                    "title": "CRYSTAL STRUCTURE OF HUMAN HEMOGLOBIN",
                    "pdbx_descriptor": "Hemoglobin",
                },
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("PDB:1ABC")
        assert result is not None
        assert result.primary_id == "PDB:1ABC"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when result is empty."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("PDB:XXXX")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("PDB:1ABC")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
