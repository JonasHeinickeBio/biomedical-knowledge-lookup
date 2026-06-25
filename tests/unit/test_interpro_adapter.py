"""
Unit tests for InterProAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from knowledge_lookup.adapters.interpro_adapter import InterProAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestInterProAdapter:
    """Tests for InterProAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create InterProAdapter instance."""
        return InterProAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test InterProAdapter initialization."""
        adapter = InterProAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.INTERPRO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.INTERPRO

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
        config = LookupConfig(rate_limits={KnowledgeSource.INTERPRO: 4.0})
        adapter = InterProAdapter(config)
        assert adapter.get_rate_limit() == 4.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "metadata": {
                            "accession": "IPR000001",
                            "name": {"name": "Kringle", "short": "Kringle"},
                            "type": "Domain",
                            "description": [{"text": "The kringle domain."}],
                        }
                    }
                ]
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("kringle", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_id == "InterPro:IPR000001"
        assert results[0].primary_label == "Kringle"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
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
            return_value={
                "metadata": {
                    "accession": "IPR000001",
                    "name": {"name": "Kringle"},
                    "type": "Domain",
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("IPR000001")
        assert result is not None
        assert result.primary_id == "InterPro:IPR000001"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("IPR999999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("IPR000001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_exception(self, mock_get, adapter):
        """Test get_concept_details with exception."""
        mock_get.side_effect = Exception("Network error")
        result = await adapter.get_concept_details("IPR000001")
        assert result is None

    def test_convert_result_string_name(self, adapter):
        """Test _convert_result_to_concept with string name instead of dict."""
        item = {
            "metadata": {
                "accession": "IPR000002",
                "name": "TestDomain",
                "type": "domain",
                "description": ["A test domain"],
                "integrated": [{"accession": "PF00001"}],
            }
        }
        concept = adapter._convert_result_to_concept(item)
        assert concept is not None
        assert concept.primary_label == "TestDomain"
        assert concept.concept_type == "MOLECULAR_ENTITY"

    def test_convert_result_empty_accession(self, adapter):
        """Test _convert_result_to_concept returns None for empty accession."""
        item = {"metadata": {"accession": "", "name": {"name": "Test"}}}
        concept = adapter._convert_result_to_concept(item)
        assert concept is None

    def test_convert_result_empty_name_fallback(self, adapter):
        """Test _convert_result_to_concept falls back to ipr_id when name dict is empty."""
        item = {"metadata": {"accession": "IPR000003", "name": {}}}
        concept = adapter._convert_result_to_concept(item)
        # Falls back to ipr_id as label
        assert concept is not None
        assert concept.primary_label == "IPR000003"

    def test_convert_result_family_type(self, adapter):
        """Test _convert_result_to_concept with family entry type."""
        item = {
            "metadata": {
                "accession": "IPR000004",
                "name": {"name": "Kringle"},
                "type": "family",
            }
        }
        concept = adapter._convert_result_to_concept(item)
        assert concept is not None
        assert concept.concept_type == "PROTEIN"

    def test_convert_result_description_as_string(self, adapter):
        """Test _convert_result_to_concept with description as string."""
        item = {
            "metadata": {
                "accession": "IPR000005",
                "name": {"name": "Test"},
                "type": "domain",
                "description": "A string description",
            }
        }
        concept = adapter._convert_result_to_concept(item)
        assert concept is not None
        assert "A string description" in concept.definitions

    def test_convert_result_integrated_non_dict(self, adapter):
        """Test _convert_result_to_concept with non-dict integrated entries."""
        item = {
            "metadata": {
                "accession": "IPR000006",
                "name": {"name": "Test"},
                "type": "domain",
                "integrated": ["PF00001", "PS00001"],
            }
        }
        concept = adapter._convert_result_to_concept(item)
        assert concept is not None
        # Non-dict entries should be skipped
        assert concept.categories == []

    def test_convert_result_no_metadata_key(self, adapter):
        """Test _convert_result_to_concept when no metadata key."""
        item = {
            "accession": "IPR000007",
            "name": {"name": "TopLevel"},
            "type": "homologous_superfamily",
        }
        concept = adapter._convert_result_to_concept(item)
        assert concept is not None
        assert concept.concept_type == "MOLECULAR_ENTITY"

    def test_convert_result_error(self, adapter):
        """Test _convert_result_to_concept with malformed data raises no error."""
        item = {"invalid": "data"}
        concept = adapter._convert_result_to_concept(item)
        assert concept is None

    @pytest.mark.asyncio
    async def test_get_concept_details_with_prefix(self, adapter):
        """Test get_concept_details adds IPR prefix when missing."""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json = AsyncMock(
                return_value={
                    "metadata": {
                        "accession": "IPR000001",
                        "name": {"name": "Kringle"},
                        "type": "domain",
                    }
                }
            )
            mock_get.return_value.__aenter__.return_value = mock_response
            result = await adapter.get_concept_details("000001")
            assert result is not None
