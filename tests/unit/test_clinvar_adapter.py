"""
Unit tests for ClinVarAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from knowledge_lookup.adapters.clinvar_adapter import ClinVarAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestClinVarAdapter:
    """Tests for ClinVarAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create ClinVarAdapter instance."""
        return ClinVarAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test ClinVarAdapter initialization."""
        adapter = ClinVarAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.CLINVAR
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.CLINVAR

    def test_is_available(self, adapter):
        """Test is_available returns True (public API)."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.CLINVAR: 3.0})
        adapter = ClinVarAdapter(config)
        assert adapter.get_rate_limit() == 3.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        # First call: esearch
        esearch_response = AsyncMock()
        esearch_response.status = 200
        esearch_response.raise_for_status = MagicMock()
        esearch_response.json = AsyncMock(return_value={"esearchresult": {"idlist": ["12345"]}})

        # Second call: esummary
        esummary_response = AsyncMock()
        esummary_response.status = 200
        esummary_response.raise_for_status = MagicMock()
        esummary_response.json = AsyncMock(
            return_value={
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "uid": "12345",
                        "title": "NM_000492.4(CFTR):c.1521_1523delCTT (p.Phe508del)",
                        "clinical_significance": {"description": "Pathogenic"},
                        "obj_type": "single nucleotide variant",
                    },
                }
            }
        )

        mock_get.return_value.__aenter__.side_effect = [esearch_response, esummary_response]

        results = await adapter.search_concepts("CFTR", limit=5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert "ClinVar:12345" == results[0].primary_id

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty ID list."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"esearchresult": {"idlist": []}})
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
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "uid": "12345",
                        "title": "CFTR variant",
                        "clinical_significance": {"description": "Pathogenic"},
                    },
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("ClinVar:12345")
        assert result is not None
        assert result.primary_id == "ClinVar:12345"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when result is not found."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"result": {"uids": []}})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("ClinVar:99999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("ClinVar:12345")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
