"""
Unit tests for base adapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.base import KnowledgeSourceAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestKnowledgeSourceAdapter:
    """Tests for KnowledgeSourceAdapter."""

    @pytest.fixture
    def config(self):
        """Create LookupConfig instance."""
        return LookupConfig()

    @pytest.fixture
    def adapter(self, config):
        """Create a test adapter."""

        class TestAdapter(KnowledgeSourceAdapter):
            def get_source(self):
                return KnowledgeSource.BIOPORTAL

            async def search_concepts(self, query: str, limit: int = 20):
                return []

            async def get_concept_details(self, concept_id: str):
                return None

        return TestAdapter(config)

    def test_adapter_initialization(self, config):
        """Test adapter initialization."""

        class TestAdapter(KnowledgeSourceAdapter):
            def get_source(self):
                return KnowledgeSource.BIOPORTAL

            async def search_concepts(self, query: str, limit: int = 20):
                return []

            async def get_concept_details(self, concept_id: str):
                return None

        adapter = TestAdapter(config)
        assert adapter.config == config
        assert adapter.session is None

    def test_get_source_abstract(self, config):
        """Test get_source is abstract."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            KnowledgeSourceAdapter(config)

    def test_is_available_default(self, adapter):
        """Test is_available default implementation."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit default."""
        rate = adapter.get_rate_limit()
        assert isinstance(rate, int | float)
        assert rate >= 0

    @pytest.mark.asyncio
    async def test_search_concepts_implemented(self, adapter):
        """Test search_concepts is implemented in test adapter."""
        result = await adapter.search_concepts("test")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_concept_details_implemented(self, adapter):
        """Test get_concept_details is implemented in test adapter."""
        result = await adapter.get_concept_details("TEST:001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings default implementation."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships default implementation."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            # Session should still be None until _get_session is called
            assert adapter.session is None
        # Session should still be None after context exit since it was never created
        assert adapter.session is None

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_make_request_success(self, mock_session_class, adapter):
        """Test _make_request success."""
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"result": "data"})
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session

        result = await adapter._make_request("http://test.com")
        assert result == {"result": "data"}

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_make_request_http_error(self, mock_session_class, adapter):
        """Test _make_request with HTTP error."""
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session

        with pytest.raises(Exception, match="HTTP 500"):
            await adapter._make_request("http://test.com")

    def test_create_concept(self, adapter):
        """Test _create_concept helper."""
        concept = adapter._create_concept("TEST:001", "Test Concept")
        assert concept.primary_id == "TEST:001"
        assert concept.primary_label == "Test Concept"
        assert concept.sources == ["BIOPORTAL"]

    def test_determine_concept_type_disease(self, adapter):
        """Test _determine_concept_type for disease."""
        concept_type = adapter._determine_concept_type(["disease"])
        assert concept_type.name == "DISEASE"

    def test_determine_concept_type_gene(self, adapter):
        """Test _determine_concept_type for gene."""
        concept_type = adapter._determine_concept_type(["gene"])
        assert concept_type.name == "GENE"

    def test_determine_concept_type_unknown(self, adapter):
        """Test _determine_concept_type for unknown."""
        concept_type = adapter._determine_concept_type(["unknown"])
        assert concept_type.name == "UNKNOWN"


class TestNotFoundIsNotABreakerFailure:
    """Regression: HTTP 404 ("no match" for several APIs) opened the circuit breaker."""

    @staticmethod
    def _adapter(threshold: int):
        from knowledge_lookup.utils.retry_utils import CircuitBreaker

        class Adapter(KnowledgeSourceAdapter):
            def get_source(self):
                return KnowledgeSource.REACTOME

            async def search_concepts(self, query: str, limit: int = 20):
                return []

            async def get_concept_details(self, concept_id: str):
                return None

        adapter = Adapter(LookupConfig())
        breaker = CircuitBreaker(threshold=threshold, cooldown=60)
        adapter.set_circuit_breaker(breaker)
        return adapter, breaker

    @staticmethod
    def _http_error(status: int):
        import aiohttp

        return aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=status, message="HTTP error"
        )

    @pytest.mark.asyncio
    async def test_repeated_404s_keep_the_breaker_closed(self):
        adapter, breaker = self._adapter(threshold=2)
        operation = AsyncMock(side_effect=self._http_error(404))

        for _ in range(5):
            with pytest.raises(Exception, match="HTTP error"):
                await adapter._call_with_retry("search", operation)

        assert operation.await_count == 5  # raised to the adapter every time, never retried
        assert breaker.state.value == "closed"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_404_probe_closes_a_half_open_breaker(self):
        adapter, breaker = self._adapter(threshold=1)
        breaker.record_failure()
        breaker.last_failure_time -= breaker.cooldown + 1  # cooldown elapsed

        with pytest.raises(Exception, match="HTTP error"):
            await adapter._call_with_retry("search", AsyncMock(side_effect=self._http_error(404)))

        assert breaker.state.value == "closed"

    @pytest.mark.asyncio
    async def test_other_client_errors_still_count(self):
        adapter, breaker = self._adapter(threshold=2)
        operation = AsyncMock(side_effect=self._http_error(403))

        for _ in range(2):
            with pytest.raises(Exception, match="HTTP error"):
                await adapter._call_with_retry("search", operation)

        assert breaker.state.value == "open"

    def test_is_not_found_reads_the_status_code_not_the_message(self):
        from knowledge_lookup.base import _is_not_found

        class RequestsStyleError(Exception):
            response = MagicMock(status_code=404)

        assert _is_not_found(self._http_error(404))
        assert _is_not_found(RequestsStyleError())
        assert not _is_not_found(self._http_error(500))
        assert not _is_not_found(Exception("lookup of R-HSA-404 failed"))
