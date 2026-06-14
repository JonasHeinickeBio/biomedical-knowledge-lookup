"""
Unit tests for ZoomaAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.zooma_adapter import ZoomaAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept


class TestZoomaAdapter:
    """Tests for ZoomaAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create ZoomaAdapter instance."""
        return ZoomaAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test ZoomaAdapter initialization."""
        adapter = ZoomaAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.ZOOMA
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.ZOOMA

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
        config = LookupConfig(rate_limits={KnowledgeSource.ZOOMA: 5.0})
        adapter = ZoomaAdapter(config)
        assert adapter.get_rate_limit() == 5.0

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
    async def test_get_concept_details(self, adapter):
        """Test get_concept_details returns None."""
        result = await adapter.get_concept_details("test:001")
        assert result is None


class TestZoomaSearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return ZoomaAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_with_list_data(self, adapter):
        """Test search with list response."""
        data = [
            {
                "semanticTags": ["http://purl.obolibrary.org/obo/DOID_9351"],
                "annotatedProperty": {"propertyValue": "diabetes"},
                "confidence": "HIGH",
                "derivedFrom": {
                    "provenance": {"source": {"name": "test_source"}}
                },
            }
        ]
        adapter._make_request = AsyncMock(return_value=data)

        result = await adapter.search_concepts("diabetes", limit=10)
        assert len(result) == 1
        assert result[0].primary_label == "diabetes"

    @pytest.mark.asyncio
    async def test_search_not_list(self, adapter):
        """Test search with non-list response."""
        adapter._make_request = AsyncMock(return_value={"not": "a list"})
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_empty_list(self, adapter):
        """Test search with empty list."""
        adapter._make_request = AsyncMock(return_value=[])
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_exception(self, adapter):
        """Test search handles exceptions."""
        adapter._make_request = AsyncMock(side_effect=Exception("Error"))
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, adapter):
        """Test search respects limit parameter."""
        data = [
            {
                "semanticTags": [f"http://example.com/{i}"],
                "annotatedProperty": {"propertyValue": f"term{i}"},
                "confidence": "HIGH",
            }
            for i in range(5)
        ]
        adapter._make_request = AsyncMock(return_value=data)

        result = await adapter.search_concepts("test", limit=2)
        assert len(result) == 2


class TestZoomaConvertResult:
    """Tests for _convert_zooma_result_to_concept method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return ZoomaAdapter(lookup_config)

    def test_convert_result_valid(self, adapter):
        """Test conversion with valid result."""
        result = {
            "semanticTags": ["http://purl.obolibrary.org/obo/DOID_9351"],
            "annotatedProperty": {"propertyValue": "diabetes"},
            "confidence": "HIGH",
            "derivedFrom": {
                "provenance": {"source": {"name": "test_source"}}
            },
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "diabetes"
        assert concept.confidence_score == 0.9
        assert any("Source: test_source" in c for c in concept.categories)

    def test_convert_result_no_semantic_tags(self, adapter):
        """Test returns None when no semantic tags."""
        result = {
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "HIGH",
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept is None

    def test_convert_result_empty_semantic_tags(self, adapter):
        """Test returns None when semantic tags is empty."""
        result = {
            "semanticTags": [],
            "annotatedProperty": {"propertyValue": "test"},
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept is None

    def test_convert_result_confidence_good(self, adapter):
        """Test conversion with GOOD confidence."""
        result = {
            "semanticTags": ["http://example.com/1"],
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "GOOD",
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept.confidence_score == 0.7

    def test_convert_result_confidence_medium(self, adapter):
        """Test conversion with MEDIUM confidence."""
        result = {
            "semanticTags": ["http://example.com/1"],
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "MEDIUM",
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept.confidence_score == 0.5

    def test_convert_result_confidence_low(self, adapter):
        """Test conversion with LOW confidence."""
        result = {
            "semanticTags": ["http://example.com/1"],
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "LOW",
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept.confidence_score == 0.3

    def test_convert_result_unknown_confidence(self, adapter):
        """Test conversion with unknown confidence defaults to 0.3."""
        result = {
            "semanticTags": ["http://example.com/1"],
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "UNKNOWN",
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept.confidence_score == 0.3

    def test_convert_result_no_derived_from(self, adapter):
        """Test conversion without derivedFrom."""
        result = {
            "semanticTags": ["http://example.com/1"],
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "HIGH",
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept is not None
        assert not any("Source:" in c for c in concept.categories)

    def test_convert_result_derived_from_empty_source(self, adapter):
        """Test conversion with empty source name."""
        result = {
            "semanticTags": ["http://example.com/1"],
            "annotatedProperty": {"propertyValue": "test"},
            "confidence": "HIGH",
            "derivedFrom": {
                "provenance": {"source": {"name": ""}}
            },
        }
        concept = adapter._convert_zooma_result_to_concept(result)
        assert concept is not None
        assert not any("Source:" in c for c in concept.categories)

    def test_convert_result_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.zooma_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_zooma_result_to_concept(
                {"semanticTags": ["test"], "annotatedProperty": {"propertyValue": "test"}}
            )
            assert result is None
