"""
Unit tests for EuropePMCAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from knowledge_lookup.adapters.europepmc_adapter import EuropePMCAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestEuropePMCAdapter:
    """Tests for EuropePMCAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EuropePMCAdapter instance."""
        return EuropePMCAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test EuropePMCAdapter initialization."""
        adapter = EuropePMCAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.EUROPEPMC
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.EUROPEPMC

    def test_is_available(self, adapter):
        """Test is_available returns True (no API key required)."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.EUROPEPMC: 5.0})
        adapter = EuropePMCAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "resultList": {
                    "result": [
                        {
                            "pmid": "12345678",
                            "title": "Test Article on Melanoma",
                            "abstractText": "This study explores melanoma treatment.",
                            "journalTitle": "Cancer Research",
                            "pubYear": "2023",
                        }
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("melanoma", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].primary_label == "Test Article on Melanoma"
        assert results[0].primary_id == "PMID:12345678"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"resultList": {"result": []}})
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
                    "pmid": "12345678",
                    "title": "Test Article",
                    "abstractText": "Abstract text",
                    "journalTitle": "Nature",
                    "pubYear": "2022",
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("MED:12345678")
        assert result is not None
        assert result.primary_id == "PMID:12345678"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when result is empty."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"result": {}})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("MED:99999999")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("concept_id", "expected_path"),
        [
            ("PMID:12345678", "/article/MED/12345678"),
            ("pmid:12345678", "/article/MED/12345678"),
            ("MED:12345678", "/article/MED/12345678"),
            ("12345678", "/article/MED/12345678"),
            ("PMID:PMC7654321", "/article/PMC/PMC7654321"),
            ("PMCID:PMC7654321", "/article/PMC/PMC7654321"),
            ("PMC7654321", "/article/PMC/PMC7654321"),
            ("PMID:PPR1319214", "/article/PPR/PPR1319214"),
        ],
    )
    async def test_get_concept_details_accepts_search_ids(
        self, adapter, concept_id, expected_path
    ):
        """Regression: IDs produced by search (``PMID:...``) are valid details IDs."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {
                "version": "6.9",
                "hitCount": 1,
                "result": {"id": "12345678", "source": "MED", "pmid": "12345678", "title": "T"},
            }
            result = await adapter.get_concept_details(concept_id)
        url, params = mock_req.call_args.args
        assert url.endswith(expected_path)
        assert params == {"format": "json", "resultType": "core"}
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_id_round_trips_to_details(self, adapter):
        """The primary_id of a search result can be passed to get_concept_details."""
        record = {
            "id": "20301425",
            "source": "MED",
            "pmid": "20301425",
            "title": "BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer",
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [
                {"hitCount": 1, "resultList": {"result": [record]}},
                {"hitCount": 1, "result": record},
            ]
            [found] = await adapter.search_concepts("BRCA1", limit=1)
            details = await adapter.get_concept_details(found.primary_id)
        assert found.primary_id == "PMID:20301425"
        assert details is not None
        assert details.primary_id == found.primary_id
        assert mock_req.call_args.args[0].endswith("/article/MED/20301425")

    def test_convert_result_reads_core_journal_info(self, adapter):
        """resultType=core nests the journal title under journalInfo.journal."""
        concept = adapter._convert_result_to_concept(
            {
                "pmid": "12345678",
                "title": "Test",
                "journalInfo": {
                    "volume": "20",
                    "journal": {"title": "Nature", "isoabbreviation": "Nature"},
                },
                "pubYear": "2026",
            }
        )
        assert "journal:Nature" in concept.categories
        assert "year:2026" in concept.categories

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("PMID:12345678")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("PMID:12345678")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
