"""
Unit tests for BioOntologyAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.bioontology_adapter import BioOntologyAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestBioOntologyAdapter:
    """Tests for BioOntologyAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create BioOntologyAdapter instance."""
        return BioOntologyAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create BioOntologyAdapter with API key."""
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test BioOntologyAdapter initialization."""
        adapter = BioOntologyAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.BIOONTOLOGY
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.BIOONTOLOGY

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
        config = LookupConfig(rate_limits={KnowledgeSource.BIOONTOLOGY: 5.0})
        adapter = BioOntologyAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})  # Mock response structure
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test query", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
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

    @pytest.mark.asyncio
    async def test_annotate_no_api_key(self, adapter):
        """Test annotate returns empty list without API key."""
        result = await adapter.annotate("Melanoma is a malignant tumor.")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_annotate_success(self, mock_get, adapter_with_api_key):
        """Test successful annotation with BioOntology annotator."""
        annotation_item = {
            "annotatedClass": {
                "@id": "http://purl.bioontology.org/ontology/SNOMEDCT/372244006",
                "prefLabel": "Melanoma",
                "links": {"ontology": "https://data.bioontology.org/ontologies/SNOMEDCT"},
            },
            "annotations": [{"from": 1, "to": 8, "matchType": "PREF"}],
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[annotation_item])
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.annotate(
            "Melanoma is a malignant tumor of melanocytes."
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["annotatedClass"]["prefLabel"] == "Melanoma"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_annotate_with_ontology_filter(self, mock_get, adapter_with_api_key):
        """Test annotation with ontology filter."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[])
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.annotate(
            "diabetes mellitus", ontologies="SNOMEDCT,DOID"
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_annotate_http_error(self, mock_get, adapter_with_api_key):
        """Test annotate handles HTTP errors gracefully."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500, message="Internal Server Error"
            )
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.annotate("test text")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_annotate_network_error(self, mock_get, adapter_with_api_key):
        """Test annotate handles network errors gracefully."""
        mock_get.side_effect = Exception("Network error")

        result = await adapter_with_api_key.annotate("test text")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_annotate_longest_only(self, mock_get, adapter_with_api_key):
        """Test annotation with longest_only=True parameter."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[])
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.annotate("cancer", longest_only=True)
        assert isinstance(result, list)
