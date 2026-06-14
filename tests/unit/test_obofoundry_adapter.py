"""
Unit tests for OBOFoundryAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.obofoundry_adapter import OBOFoundryAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept


class TestOBOFoundryAdapter:
    """Tests for OBOFoundryAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OBOFoundryAdapter instance."""
        return OBOFoundryAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OBOFoundryAdapter initialization."""
        adapter = OBOFoundryAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OBOFOUNDRY
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OBOFOUNDRY

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
        config = LookupConfig(rate_limits={KnowledgeSource.OBOFOUNDRY: 5.0})
        adapter = OBOFoundryAdapter(config)
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


class TestOBOFoundrySearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OBOFoundryAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_with_docs(self, adapter):
        """Test search with docs in response."""
        docs = [
            {
                "short_form": "DOID:9351",
                "label": "diabetes mellitus",
                "iri": "http://purl.obolibrary.org/obo/DOID_9351",
                "ontology_name": "doid",
            }
        ]
        adapter._make_request = AsyncMock(
            return_value={"response": {"docs": docs}}
        )

        result = await adapter.search_concepts("diabetes", limit=10)
        assert len(result) == 1
        assert result[0].primary_label == "diabetes mellitus"

    @pytest.mark.asyncio
    async def test_search_no_response_key(self, adapter):
        """Test search with no response key."""
        adapter._make_request = AsyncMock(return_value={})
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_no_docs_key(self, adapter):
        """Test search with no docs key."""
        adapter._make_request = AsyncMock(return_value={"response": {}})
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_exception(self, adapter):
        """Test search handles exceptions."""
        adapter._make_request = AsyncMock(side_effect=Exception("Error"))
        result = await adapter.search_concepts("test")
        assert result == []


class TestOBOFoundryConvertResult:
    """Tests for _convert_obo_result_to_concept method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OBOFoundryAdapter(lookup_config)

    def test_convert_result_valid(self, adapter):
        """Test conversion with valid result."""
        result = {
            "short_form": "DOID:9351",
            "label": "diabetes mellitus",
            "iri": "http://purl.obolibrary.org/obo/DOID_9351",
            "ontology_name": "doid",
        }
        concept = adapter._convert_obo_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "diabetes mellitus"
        assert any("Ontology: doid" in c for c in concept.categories)

    def test_convert_result_no_short_form(self, adapter):
        """Test returns None when no short_form."""
        result = {"label": "Test"}
        concept = adapter._convert_obo_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_label(self, adapter):
        """Test returns None when no label."""
        result = {"short_form": "DOID:9351"}
        concept = adapter._convert_obo_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_ontology_name(self, adapter):
        """Test conversion without ontology_name."""
        result = {
            "short_form": "DOID:9351",
            "label": "diabetes mellitus",
        }
        concept = adapter._convert_obo_result_to_concept(result)
        assert concept is not None
        assert not any("Ontology:" in c for c in concept.categories)

    def test_convert_result_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.obofoundry_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_obo_result_to_concept(
                {"short_form": "test", "label": "test"}
            )
            assert result is None
