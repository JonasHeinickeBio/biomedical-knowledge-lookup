"""
Unit tests for OxOAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.oxo_adapter import OxOAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestOxOAdapter:
    """Tests for OxOAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OxOAdapter instance."""
        return OxOAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OxOAdapter initialization."""
        adapter = OxOAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OXO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OXO

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
        config = LookupConfig(rate_limits={KnowledgeSource.OXO: 5.0})
        adapter = OxOAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    def _make_mock_session(self, response_json):
        """Helper to create a mock aiohttp session that works with async context managers."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=response_json)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_cm)
        return mock_session

    @pytest.mark.asyncio
    async def test_get_concept_by_id_success(self, adapter):
        """Test get_concept_by_id with successful response."""
        response_data = {
            "_embedded": {
                "searchResults": [
                    {
                        "curie": "DOID:162",
                        "label": "diabetes mellitus",
                        "mappingResponseList": [
                            {
                                "curie": "MONDO:0004992",
                                "label": "diabetes",
                                "targetPrefix": "MONDO",
                                "sourcePrefixes": ["DOID"],
                                "distance": 1,
                            }
                        ],
                    }
                ]
            }
        }
        mock_session = self._make_mock_session(response_data)
        adapter.session = mock_session
        result = await adapter.get_concept_by_id("DOID:162")
        assert result is not None
        assert result.primary_id == "DOID:162"

    @pytest.mark.asyncio
    async def test_get_concept_by_id_with_mapping_target(self, adapter):
        """Test get_concept_by_id with mapping_target and mapping_source."""
        mock_session = self._make_mock_session({"_embedded": {"searchResults": []}})
        adapter.session = mock_session
        result = await adapter.get_concept_by_id(
            "DOID:162", distance=2, mapping_target=["MONDO"], mapping_source=["DOID"]
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_by_id_no_results(self, adapter):
        """Test get_concept_by_id with no embedded results."""
        mock_session = self._make_mock_session({})
        adapter.session = mock_session
        result = await adapter.get_concept_by_id("DOID:162")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_by_id_error(self, adapter):
        """Test get_concept_by_id error handling."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(side_effect=Exception("Network error"))
        adapter.session = mock_session
        result = await adapter.get_concept_by_id("DOID:162")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts with actual results."""
        response_data = {
            "_embedded": {
                "searchResults": [
                    {"curie": "DOID:162", "label": "diabetes mellitus", "mappingResponseList": []},
                    {
                        "curie": "DOID:9351",
                        "label": "diabetes mellitus type 2",
                        "mappingResponseList": [],
                    },
                ]
            }
        }
        mock_session = self._make_mock_session(response_data)
        adapter.session = mock_session
        results = await adapter.search_concepts("diabetes", limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_http_error(self, adapter):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 error")
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_cm)
        adapter.session = mock_session
        results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(side_effect=Exception("Network error"))
        adapter.session = mock_session
        results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_mappings_for_concepts_success(self, adapter):
        """Test get_mappings_for_concepts."""
        response_data = {
            "_embedded": {
                "searchResults": [
                    {
                        "queryId": "DOID:162",
                        "curie": "DOID:162",
                        "mappingResponseList": [
                            {
                                "curie": "MONDO:0004992",
                                "label": "diabetes",
                                "targetPrefix": "MONDO",
                                "sourcePrefixes": ["DOID"],
                                "distance": 1,
                            }
                        ],
                    }
                ]
            }
        }
        mock_session = self._make_mock_session(response_data)
        adapter.session = mock_session
        mappings = await adapter.get_mappings_for_concepts(["DOID:162"])
        assert "DOID:162" in mappings
        assert len(mappings["DOID:162"]) == 1

    @pytest.mark.asyncio
    async def test_get_mappings_for_concepts_with_params(self, adapter):
        """Test get_mappings_for_concepts with mapping_target and mapping_source."""
        mock_session = self._make_mock_session({"_embedded": {"searchResults": []}})
        adapter.session = mock_session
        mappings = await adapter.get_mappings_for_concepts(
            ["DOID:162"], distance=2, mapping_target=["MONDO"], mapping_source=["DOID"]
        )
        assert mappings == {}

    @pytest.mark.asyncio
    async def test_get_mappings_for_concepts_error(self, adapter):
        """Test get_mappings_for_concepts error handling."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.side_effect = Exception("Network error")
        adapter.session = mock_session
        mappings = await adapter.get_mappings_for_concepts(["DOID:162"])
        assert mappings == {}

    @pytest.mark.asyncio
    async def test_get_datasources_success(self, adapter):
        """Test get_datasources."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {
                "_embedded": {
                    "datasources": [
                        {"id": "DOID", "name": "Disease Ontology"},
                        {"id": "MONDO", "name": "MONDO"},
                    ]
                }
            }
            datasources = await adapter.get_datasources()
            assert len(datasources) == 2

    @pytest.mark.asyncio
    async def test_get_datasources_empty(self, adapter):
        """Test get_datasources with no embedded datasources."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            datasources = await adapter.get_datasources()
            assert datasources == []

    @pytest.mark.asyncio
    async def test_get_datasources_error(self, adapter):
        """Test get_datasources error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("API error")
            datasources = await adapter.get_datasources()
            assert datasources == []

    def test_parse_search_result_full(self, adapter):
        """Test _parse_search_result with all fields."""
        result = {
            "curie": "DOID:162",
            "label": "diabetes mellitus",
            "mappingResponseList": [
                {
                    "curie": "MONDO:0004992",
                    "label": "diabetes",
                    "targetPrefix": "MONDO",
                    "sourcePrefixes": ["DOID"],
                    "distance": 1,
                }
            ],
        }
        concept = adapter._parse_search_result(result, "DOID:162")
        assert concept is not None
        assert concept.primary_id == "DOID:162"

    def test_parse_search_result_no_curie(self, adapter):
        """Test _parse_search_result with no curie (returns None)."""
        result = {"label": "diabetes"}
        concept = adapter._parse_search_result(result)
        assert concept is None

    def test_parse_search_result_no_mappings(self, adapter):
        """Test _parse_search_result with no mappings."""
        result = {"curie": "DOID:162", "label": "diabetes mellitus"}
        concept = adapter._parse_search_result(result)
        assert concept is not None

    def test_parse_search_result_query_id_fallback(self, adapter):
        """Test _parse_search_result using queryId as fallback."""
        result = {"queryId": "DOID:162", "label": "diabetes mellitus"}
        concept = adapter._parse_search_result(result)
        assert concept is not None
        assert concept.primary_id == "DOID:162"

    def test_parse_search_result_error(self, adapter):
        """Test _parse_search_result with error-causing data."""
        concept = adapter._parse_search_result(None)
        assert concept is None

    def test_parse_search_result_label_none(self, adapter):
        """Test _parse_search_result when label is None."""
        result = {"curie": "DOID:162", "label": None, "mappingResponseList": []}
        concept = adapter._parse_search_result(result)
        assert concept is not None
        assert concept.primary_label == "DOID:162"

    def test_extract_mappings_with_data(self, adapter):
        """Test _extract_mappings with mappingResponseList."""
        result = {
            "mappingResponseList": [
                {
                    "curie": "MONDO:0004992",
                    "label": "diabetes",
                    "targetPrefix": "MONDO",
                    "sourcePrefixes": ["DOID"],
                    "distance": 1,
                }
            ]
        }
        mappings = adapter._extract_mappings(result)
        assert len(mappings) == 1
        assert mappings[0]["curie"] == "MONDO:0004992"

    def test_extract_mappings_empty(self, adapter):
        """Test _extract_mappings without mappingResponseList."""
        result = {"curie": "DOID:162"}
        mappings = adapter._extract_mappings(result)
        assert mappings == []

    def test_extract_mappings_missing_fields(self, adapter):
        """Test _extract_mappings with missing optional fields in mapping."""
        result = {"mappingResponseList": [{"curie": "MONDO:0004992"}]}
        mappings = adapter._extract_mappings(result)
        assert len(mappings) == 1
        assert mappings[0]["label"] is None
        assert mappings[0]["sourcePrefixes"] == []
        assert mappings[0]["distance"] == 1

    def test_calculate_mapping_confidence_distance_1(self, adapter):
        """Test confidence calculation for direct mapping."""
        mapping = {"distance": 1, "sourcePrefixes": ["DOID"]}
        confidence = adapter._calculate_mapping_confidence(mapping)
        assert confidence == 0.9

    def test_calculate_mapping_confidence_distance_2(self, adapter):
        """Test confidence for distance 2 mapping."""
        mapping = {"distance": 2, "sourcePrefixes": ["DOID"]}
        confidence = adapter._calculate_mapping_confidence(mapping)
        assert confidence == 0.7

    def test_calculate_mapping_confidence_distance_3(self, adapter):
        """Test confidence for distance >= 3 mapping."""
        mapping = {"distance": 3, "sourcePrefixes": ["DOID"]}
        confidence = adapter._calculate_mapping_confidence(mapping)
        assert confidence == 0.5

    def test_calculate_mapping_confidence_multiple_sources(self, adapter):
        """Test confidence boost for multiple source prefixes."""
        mapping = {"distance": 1, "sourcePrefixes": ["DOID", "MONDO"]}
        confidence = adapter._calculate_mapping_confidence(mapping)
        assert confidence == 1.0

    def test_calculate_mapping_confidence_no_distance(self, adapter):
        """Test confidence with default distance (missing distance key -> defaults to 1)."""
        mapping = {"sourcePrefixes": []}
        confidence = adapter._calculate_mapping_confidence(mapping)
        # distance defaults to 1 in the code -> 0.9
        assert confidence == 0.9

    def test_get_knowledge_source_from_prefix_known(self, adapter):
        """Test _get_knowledge_source_from_prefix with known prefixes."""
        assert adapter._get_knowledge_source_from_prefix("UMLS") == KnowledgeSource.UMLS
        assert adapter._get_knowledge_source_from_prefix("NCBI") == KnowledgeSource.NCBI
        assert adapter._get_knowledge_source_from_prefix("UNIPROT") == KnowledgeSource.UNIPROT
        assert adapter._get_knowledge_source_from_prefix("ENSEMBL") == KnowledgeSource.ENSEMBL

    def test_get_knowledge_source_from_prefix_unknown(self, adapter):
        """Test _get_knowledge_source_from_prefix with unknown prefix."""
        result = adapter._get_knowledge_source_from_prefix("UNKNOWN_PREFIX")
        assert result is None

    def test_get_knowledge_source_case_insensitive(self, adapter):
        """Test prefix lookup is case-insensitive."""
        assert adapter._get_knowledge_source_from_prefix("umls") == KnowledgeSource.UMLS
        assert adapter._get_knowledge_source_from_prefix("ncbi") == KnowledgeSource.NCBI

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, adapter):
        """Test validate_connection."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"_embedded": {"datasources": []}}
            result = await adapter.validate_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_connection_error(self, adapter):
        """Test validate_connection error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Connection error")
            result = await adapter.validate_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_concept_details_delegates(self, adapter):
        """Test get_concept_details delegates to get_concept_by_id with distance=3."""
        with patch.object(adapter, "get_concept_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock()
            result = await adapter.get_concept_details("DOID:162")
            mock_get.assert_called_once_with("DOID:162", distance=3)

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
