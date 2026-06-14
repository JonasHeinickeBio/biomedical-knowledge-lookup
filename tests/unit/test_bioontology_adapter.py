"""
Unit tests for BioOntologyAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.bioontology_adapter import BioOntologyAdapter
from knowledge_lookup.models import (
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    UnifiedConcept,
)


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
        mock_response.json = AsyncMock(return_value={"results": []})
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
            pass

    @pytest.mark.asyncio
    async def test_annotate_no_api_key(self, adapter):
        """Test annotate returns empty list without API key."""
        adapter.api_key = None
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
            },
            "annotations": [{"from": 1, "to": 8, "matchType": "PREF"}],
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=[annotation_item])
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter_with_api_key.annotate("Melanoma is a malignant tumor.")
        assert isinstance(result, list)
        assert len(result) == 1

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


class TestBioOntologyEndpoints:
    """Tests for endpoints property and fetch_api_endpoints."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_endpoints_initially_empty(self, adapter_with_api_key):
        """Test endpoints returns empty dict initially."""
        assert adapter_with_api_key.endpoints == {}

    def test_endpoints_returns_cached(self, adapter_with_api_key):
        """Test endpoints returns cached dict when set."""
        adapter_with_api_key._api_endpoints = {"search": "http://example.com/search"}
        assert adapter_with_api_key.endpoints == {"search": "http://example.com/search"}

    def test_endpoints_non_dict_returns_empty(self, adapter_with_api_key):
        """Test endpoints returns empty dict when _api_endpoints is not a dict."""
        adapter_with_api_key._api_endpoints = "not a dict"
        assert adapter_with_api_key.endpoints == {}

    @pytest.mark.asyncio
    async def test_fetch_api_endpoints_success(self, adapter_with_api_key):
        """Test fetch_api_endpoints with successful response."""
        endpoints_data = {"links": {"search": "http://example.com/search"}}
        adapter_with_api_key._make_request = AsyncMock(return_value=endpoints_data)

        result = await adapter_with_api_key.fetch_api_endpoints()
        assert result == {"search": "http://example.com/search"}
        assert adapter_with_api_key._api_endpoints == {"search": "http://example.com/search"}

    @pytest.mark.asyncio
    async def test_fetch_api_endpoints_no_links(self, adapter_with_api_key):
        """Test fetch_api_endpoints when response has no 'links' key."""
        adapter_with_api_key._make_request = AsyncMock(return_value={"no_links": True})

        result = await adapter_with_api_key.fetch_api_endpoints()
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_api_endpoints_empty_response(self, adapter_with_api_key):
        """Test fetch_api_endpoints when response is empty/None."""
        adapter_with_api_key._make_request = AsyncMock(return_value={})

        result = await adapter_with_api_key.fetch_api_endpoints()
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_api_endpoints_exception(self, adapter_with_api_key):
        """Test fetch_api_endpoints handles exceptions."""
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("API Error"))

        result = await adapter_with_api_key.fetch_api_endpoints()
        assert result == {}


class TestBioOntologyBuildParams:
    """Tests for _build_params method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_build_params_with_query_kwarg(self, adapter_with_api_key):
        """Test _build_params maps 'query' to 'q'."""
        params = adapter_with_api_key._build_params(query="diabetes")
        assert params["q"] == "diabetes"
        assert params["apikey"] == "test_api_key"

    def test_build_params_with_q_kwarg(self, adapter_with_api_key):
        """Test _build_params maps 'q' to 'q'."""
        params = adapter_with_api_key._build_params(q="cancer")
        assert params["q"] == "cancer"

    def test_build_params_with_extra_params(self, adapter_with_api_key):
        """Test _build_params merges extra_params."""
        params = adapter_with_api_key._build_params(
            extra_params={"custom": "value"}, query="test"
        )
        assert params["custom"] == "value"
        assert params["q"] == "test"

    def test_build_params_removes_none_values(self, adapter_with_api_key):
        """Test _build_params removes None values."""
        params = adapter_with_api_key._build_params(
            include=None, page=None, query="test"
        )
        assert "include" not in params
        assert "page" not in params


class TestBioOntologyBuildHeaders:
    """Tests for _build_headers method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_build_headers_no_auth(self, adapter_with_api_key):
        """Test _build_headers returns empty dict when no auth."""
        headers = adapter_with_api_key._build_headers(use_auth_header=False)
        assert headers == {}

    def test_build_headers_with_auth(self, adapter_with_api_key):
        """Test _build_headers returns Authorization header when auth enabled."""
        headers = adapter_with_api_key._build_headers(use_auth_header=True)
        assert "Authorization" in headers
        assert "apikey token=test_api_key" in headers["Authorization"]


class TestBioOntologyMakeRequest:
    """Tests for _make_request method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_make_request_exception(self, adapter_with_api_key):
        """Test _make_request returns empty dict on exception."""
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        adapter_with_api_key.session = mock_session

        result = await adapter_with_api_key._make_request("http://example.com")
        assert result == {}


class TestBioOntologyCallEndpoint:
    """Tests for call_endpoint method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_call_endpoint_fetches_endpoints_if_not_cached(self, adapter_with_api_key):
        """Test call_endpoint fetches endpoints if not cached."""
        adapter_with_api_key._api_endpoints = None
        adapter_with_api_key.fetch_api_endpoints = AsyncMock(
            return_value={"search": "http://example.com/search"}
        )
        adapter_with_api_key._make_request = AsyncMock(return_value={"results": []})

        result = await adapter_with_api_key.call_endpoint("search")
        adapter_with_api_key.fetch_api_endpoints.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_endpoint_not_found(self, adapter_with_api_key):
        """Test call_endpoint returns None for unknown endpoint."""
        adapter_with_api_key._api_endpoints = {"search": "http://example.com/search"}

        result = await adapter_with_api_key.call_endpoint("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_endpoint_success(self, adapter_with_api_key):
        """Test call_endpoint with valid endpoint."""
        adapter_with_api_key._api_endpoints = {"search": "http://example.com/search"}
        adapter_with_api_key._make_request = AsyncMock(return_value={"results": ["test"]})

        result = await adapter_with_api_key.call_endpoint("search", params={"q": "test"})
        assert result == {"results": ["test"]}

    @pytest.mark.asyncio
    async def test_call_endpoint_exception(self, adapter_with_api_key):
        """Test call_endpoint handles exceptions."""
        adapter_with_api_key._api_endpoints = {"search": "http://example.com/search"}
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))

        result = await adapter_with_api_key.call_endpoint("search")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_endpoint_default_params(self, adapter_with_api_key):
        """Test call_endpoint uses default params when None."""
        adapter_with_api_key._api_endpoints = {"search": "http://example.com/search"}
        adapter_with_api_key._make_request = AsyncMock(return_value={"results": []})

        result = await adapter_with_api_key.call_endpoint("search", params=None)
        assert result is not None


class TestBioOntologySearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_search_no_api_key(self, adapter_with_api_key):
        """Test search_concepts returns empty when no API key."""
        adapter_with_api_key.api_key = None
        result = await adapter_with_api_key.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_raw_mode(self, adapter_with_api_key):
        """Test search_concepts returns raw collection in raw mode."""
        collection = [{"@id": "test", "prefLabel": "Test"}]
        adapter_with_api_key._make_request = AsyncMock(
            return_value={"collection": collection}
        )

        result = await adapter_with_api_key.search_concepts("test", raw=True, limit=10)
        assert result == collection

    @pytest.mark.asyncio
    async def test_search_raw_mode_no_collection(self, adapter_with_api_key):
        """Test search_concepts raw mode returns empty when no collection key."""
        adapter_with_api_key._make_request = AsyncMock(return_value={})

        result = await adapter_with_api_key.search_concepts("test", raw=True, limit=10)
        assert result == []

    @pytest.mark.asyncio
    async def test_search_exception(self, adapter_with_api_key):
        """Test search_concepts handles exceptions."""
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))

        result = await adapter_with_api_key.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_with_collection_items(self, adapter_with_api_key):
        """Test search_concepts parses collection items."""
        collection = [
            {
                "@id": "http://example.com/1",
                "prefLabel": "Test1",
                "synonym": ["syn1"],
                "definition": ["def1"],
            },
            {
                "@id": "http://example.com/2",
                "prefLabel": "Test2",
            },
        ]
        adapter_with_api_key._make_request = AsyncMock(
            return_value={"collection": collection}
        )

        result = await adapter_with_api_key.search_concepts("test", limit=10)
        assert len(result) == 2
        assert all(isinstance(c, UnifiedConcept) for c in result)


class TestBioOntologyBuildSearchRequest:
    """Tests for _build_search_request method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_build_search_request(self, adapter_with_api_key):
        """Test _build_search_request returns correct url and params."""
        url, params = adapter_with_api_key._build_search_request("diabetes", 10)
        assert url == "https://data.bioontology.org/search"
        assert params["q"] == "diabetes"
        assert params["pagesize"] == 10
        assert params["apikey"] == "test_api_key"

    def test_build_search_request_max_limit(self, adapter_with_api_key):
        """Test _build_search_request caps pagesize at 50."""
        url, params = adapter_with_api_key._build_search_request("test", 100)
        assert params["pagesize"] == 50


class TestBioOntologyParseSearchResponse:
    """Tests for _parse_search_response method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_parse_search_response_empty(self, adapter_with_api_key):
        """Test _parse_search_response with no collection."""
        result = adapter_with_api_key._parse_search_response({}, 10)
        assert result == []

    def test_parse_search_response_with_items(self, adapter_with_api_key):
        """Test _parse_search_response with collection items."""
        data = {
            "collection": [
                {"@id": "http://example.com/1", "prefLabel": "Test1"},
                {"@id": "http://example.com/2", "prefLabel": "Test2"},
            ]
        }
        result = adapter_with_api_key._parse_search_response(data, 10)
        assert len(result) == 2

    def test_parse_search_response_respects_limit(self, adapter_with_api_key):
        """Test _parse_search_response respects limit."""
        data = {
            "collection": [
                {"@id": f"http://example.com/{i}", "prefLabel": f"Test{i}"}
                for i in range(5)
            ]
        }
        result = adapter_with_api_key._parse_search_response(data, 2)
        assert len(result) == 2


class TestBioOntologyGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_get_concept_details_no_api_key(self, adapter_with_api_key):
        """Test get_concept_details returns None without API key."""
        adapter_with_api_key.api_key = None
        result = await adapter_with_api_key.get_concept_details(
            "http://example.com/1", ontology="DOID"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_raw_mode(self, adapter_with_api_key):
        """Test get_concept_details returns raw data in raw mode."""
        raw_data = {"@id": "test", "prefLabel": "Test"}
        adapter_with_api_key._build_details_request = MagicMock(
            return_value=("http://example.com", {"apikey": "test"})
        )
        adapter_with_api_key._make_request = AsyncMock(return_value=raw_data)

        result = await adapter_with_api_key.get_concept_details(
            "http://example.com/1", ontology="DOID", raw=True
        )
        assert result == raw_data

    @pytest.mark.asyncio
    async def test_get_concept_details_minimal_mode(self, adapter_with_api_key):
        """Test get_concept_details returns minimal metadata in minimal mode."""
        data = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "synonym": ["syn1"],
            "definition": ["def1"],
            "obsolete": False,
        }
        adapter_with_api_key._build_details_request = MagicMock(
            return_value=("http://example.com", {"apikey": "test"})
        )
        adapter_with_api_key._make_request = AsyncMock(return_value=data)

        result = await adapter_with_api_key.get_concept_details(
            "http://example.com/1", ontology="DOID", minimal=True
        )
        assert isinstance(result, dict)
        assert result["id"] == "http://example.com/1"
        assert result["label"] == "Test"

    @pytest.mark.asyncio
    async def test_get_concept_details_with_related(self, adapter_with_api_key):
        """Test get_concept_details fetches related resources."""
        data = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "links": {"children": "http://example.com/children"},
        }
        adapter_with_api_key._build_details_request = MagicMock(
            return_value=("http://example.com", {"apikey": "test"})
        )
        adapter_with_api_key._make_request = AsyncMock(return_value=data)
        adapter_with_api_key._fetch_related_resources = AsyncMock()

        result = await adapter_with_api_key.get_concept_details(
            "http://example.com/1",
            ontology="DOID",
            fetch_related=True,
        )
        assert result is not None
        adapter_with_api_key._fetch_related_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter_with_api_key):
        """Test get_concept_details handles exceptions."""
        adapter_with_api_key._build_details_request = MagicMock(
            return_value=("http://example.com", {"apikey": "test"})
        )
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))

        result = await adapter_with_api_key.get_concept_details(
            "http://example.com/1", ontology="DOID"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_result(self, adapter_with_api_key):
        """Test get_concept_details logs when no result found."""
        adapter_with_api_key._build_details_request = MagicMock(
            return_value=("http://example.com", {"apikey": "test"})
        )
        adapter_with_api_key._make_request = AsyncMock(return_value={})
        adapter_with_api_key._parse_details_response = MagicMock(return_value=None)

        result = await adapter_with_api_key.get_concept_details(
            "http://example.com/1", ontology="DOID"
        )
        assert result is None


class TestBioOntologyParseMinimalMetadata:
    """Tests for parse_minimal_metadata static method."""

    def test_parse_minimal_metadata_non_dict(self):
        """Test parse_minimal_metadata with non-dict returns empty dict."""
        result = BioOntologyAdapter.parse_minimal_metadata("not a dict")
        assert result == {}

    def test_parse_minimal_metadata_none(self):
        """Test parse_minimal_metadata with None returns empty dict."""
        result = BioOntologyAdapter.parse_minimal_metadata(None)
        assert result == {}

    def test_parse_minimal_metadata_valid(self):
        """Test parse_minimal_metadata with valid dict."""
        data = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "synonym": ["syn1"],
            "definition": ["def1"],
            "obsolete": False,
        }
        result = BioOntologyAdapter.parse_minimal_metadata(data)
        assert result["id"] == "http://example.com/1"
        assert result["label"] == "Test"


class TestBioOntologyAnnotateDictResponse:
    """Tests for annotate returning dict responses."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_annotate_dict_with_annotations_key(self, adapter_with_api_key):
        """Test annotate returns annotations from dict response."""
        adapter_with_api_key._make_request = AsyncMock(
            return_value={"annotations": [{"id": "test"}]}
        )
        result = await adapter_with_api_key.annotate("test text")
        assert result == [{"id": "test"}]

    @pytest.mark.asyncio
    async def test_annotate_dict_with_results_key(self, adapter_with_api_key):
        """Test annotate returns results from dict response."""
        adapter_with_api_key._make_request = AsyncMock(return_value={"results": [{"id": "test"}]})
        result = await adapter_with_api_key.annotate("test text")
        assert result == [{"id": "test"}]

    @pytest.mark.asyncio
    async def test_annotate_dict_no_known_key(self, adapter_with_api_key):
        """Test annotate returns empty list for unknown dict keys."""
        adapter_with_api_key._make_request = AsyncMock(return_value={"unknown_key": "value"})
        result = await adapter_with_api_key.annotate("test text")
        assert result == []

    @pytest.mark.asyncio
    async def test_annotate_extra_params(self, adapter_with_api_key):
        """Test annotate passes extra_params."""
        adapter_with_api_key._make_request = AsyncMock(return_value=[])
        result = await adapter_with_api_key.annotate("test text", extra_params={"custom": "val"})
        assert result == []


class TestBioOntologyBatchAnnotate:
    """Tests for batch_annotate method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_batch_annotate_success(self, adapter_with_api_key):
        """Test batch_annotate returns data."""
        adapter_with_api_key._make_request = AsyncMock(return_value={"results": []})

        result = await adapter_with_api_key.batch_annotate(
            ["text1", "text2"], ontologies="DOID"
        )
        assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_batch_annotate_exception(self, adapter_with_api_key):
        """Test batch_annotate handles exceptions."""
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))

        result = await adapter_with_api_key.batch_annotate(["text1"])
        assert result is None

    @pytest.mark.asyncio
    async def test_batch_annotate_with_extra_params(self, adapter_with_api_key):
        """Test batch_annotate with extra_params."""
        adapter_with_api_key._make_request = AsyncMock(return_value=[])

        result = await adapter_with_api_key.batch_annotate(
            ["text1"], extra_params={"custom": "val"}
        )
        assert result is not None


class TestBioOntologyGetAnalytics:
    """Tests for get_analytics method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_get_analytics_success(self, adapter_with_api_key):
        """Test get_analytics returns data."""
        adapter_with_api_key._make_request = AsyncMock(return_value={"data": "analytics"})

        result = await adapter_with_api_key.get_analytics(
            ontology="DOID", month=1, year=2024
        )
        assert result == {"data": "analytics"}

    @pytest.mark.asyncio
    async def test_get_analytics_exception(self, adapter_with_api_key):
        """Test get_analytics handles exceptions."""
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))

        result = await adapter_with_api_key.get_analytics()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_analytics_no_params(self, adapter_with_api_key):
        """Test get_analytics with no params."""
        adapter_with_api_key._make_request = AsyncMock(return_value=[])

        result = await adapter_with_api_key.get_analytics()
        assert result is not None


class TestBioOntologyFetchRelatedResources:
    """Tests for _fetch_related_resources method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_fetch_related_resources_all_keys(self, adapter_with_api_key):
        """Test _fetch_related_resources fetches all related keys."""
        concept = UnifiedConcept(
            primary_id="test", primary_label="Test", concept_type=ConceptType.DISEASE
        )
        links = {
            "children": "http://example.com/children",
            "parents": "http://example.com/parents",
            "ancestors": "http://example.com/ancestors",
            "descendants": "http://example.com/descendants",
            "tree": "http://example.com/tree",
            "notes": "http://example.com/notes",
            "mappings": "http://example.com/mappings",
            "instances": "http://example.com/instances",
        }
        adapter_with_api_key._make_request = AsyncMock(return_value={"data": "test"})

        await adapter_with_api_key._fetch_related_resources(concept, links, "test_id")
        assert adapter_with_api_key._make_request.call_count == 8

    @pytest.mark.asyncio
    async def test_fetch_related_resources_exception(self, adapter_with_api_key):
        """Test _fetch_related_resources handles exceptions per key."""
        concept = UnifiedConcept(
            primary_id="test", primary_label="Test", concept_type=ConceptType.DISEASE
        )
        links = {"children": "http://example.com/children"}
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))

        # Should not raise, just log warning
        await adapter_with_api_key._fetch_related_resources(concept, links, "test_id")

    @pytest.mark.asyncio
    async def test_fetch_related_resources_with_extra_params(self, adapter_with_api_key):
        """Test _fetch_related_resources uses extra_params."""
        concept = UnifiedConcept(
            primary_id="test", primary_label="Test", concept_type=ConceptType.DISEASE
        )
        links = {"children": "http://example.com/children"}
        adapter_with_api_key._make_request = AsyncMock(return_value={"data": "test"})

        await adapter_with_api_key._fetch_related_resources(
            concept, links, "test_id", extra_params={"custom": "val"}
        )
        adapter_with_api_key._make_request.assert_called_once()


class TestBioOntologyBuildDetailsRequest:
    """Tests for _build_details_request method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_build_details_request_with_ontology(self, adapter_with_api_key):
        """Test _build_details_request with ontology."""
        url, params = adapter_with_api_key._build_details_request(
            "MONDO:0005148", ontology="mondo"
        )
        assert "mondo" in url

    def test_build_details_request_full_url(self, adapter_with_api_key):
        """Test _build_details_request with full URL concept_id."""
        url, params = adapter_with_api_key._build_details_request(
            "http://purl.obolibrary.org/obo/DOID_9351", ontology="doid"
        )
        assert "doid" in url
        assert params["apikey"] == "test_api_key"

    def test_build_details_request_no_ontology_raises(self, adapter_with_api_key):
        """Test _build_details_request raises ValueError without ontology."""
        with pytest.raises(ValueError, match="Ontology must be provided"):
            adapter_with_api_key._build_details_request("test:001", ontology=None)


class TestBioOntologyParseDetailsResponse:
    """Tests for _parse_details_response method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_parse_details_response_valid(self, adapter_with_api_key):
        """Test _parse_details_response with valid data."""
        data = {"@id": "http://example.com/1", "prefLabel": "Test"}
        result = adapter_with_api_key._parse_details_response(data)
        assert isinstance(result, UnifiedConcept)
        assert result.primary_label == "Test"

    def test_parse_details_response_empty(self, adapter_with_api_key):
        """Test _parse_details_response with empty data."""
        result = adapter_with_api_key._parse_details_response({})
        assert result is None


class TestBioOntologyConvertResult:
    """Tests for _convert_bioontology_result_to_concept method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioontology": "test_api_key"})
        return BioOntologyAdapter(config)

    def test_convert_result_valid(self, adapter_with_api_key):
        """Test conversion with valid result."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "synonym": ["syn1", "syn2"],
            "definition": ["A test definition"],
            "cui": ["C0001"],
            "semanticType": "Disease",
            "obsolete": True,
        }
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "Test"
        assert "syn1" in concept.synonyms
        assert "A test definition" in concept.definitions
        assert "obsolete" in concept.categories

    def test_convert_result_no_id(self, adapter_with_api_key):
        """Test conversion with no @id returns None."""
        result = {"prefLabel": "Test"}
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_label(self, adapter_with_api_key):
        """Test conversion with no prefLabel returns None."""
        result = {"@id": "http://example.com/1"}
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert concept is None

    def test_convert_result_synonyms_as_string(self, adapter_with_api_key):
        """Test conversion handles synonyms as string."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "synonym": "single_synonym",
        }
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert "single_synonym" in concept.synonyms

    def test_convert_result_definitions_as_string(self, adapter_with_api_key):
        """Test conversion handles definitions as string."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "definition": "single definition",
        }
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert "single definition" in concept.definitions

    def test_convert_result_cui_as_string(self, adapter_with_api_key):
        """Test conversion handles CUI as string."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "cui": "C0001",
        }
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert "C0001" in concept.categories

    def test_convert_result_semantic_type_as_string(self, adapter_with_api_key):
        """Test conversion handles semanticType as string."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "semanticType": "Disease",
        }
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert "Disease" in concept.semantic_types

    def test_convert_result_synonyms_key(self, adapter_with_api_key):
        """Test conversion uses 'synonyms' key if 'synonym' absent."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "synonyms": ["alt_syn1"],
        }
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert "alt_syn1" in concept.synonyms

    def test_convert_result_no_synonyms(self, adapter_with_api_key):
        """Test conversion handles missing synonyms."""
        result = {"@id": "http://example.com/1", "prefLabel": "Test"}
        concept = adapter_with_api_key._convert_bioontology_result_to_concept(result)
        assert concept.synonyms == []

    def test_convert_result_exception(self, adapter_with_api_key):
        """Test conversion handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.bioontology_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter_with_api_key._convert_bioontology_result_to_concept(
                {"@id": "http://example.com/1", "prefLabel": "Test"}
            )
            assert result is None
