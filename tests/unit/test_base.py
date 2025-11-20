"""
Unit tests for base adapter classes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowledge_lookup.base import KnowledgeSourceAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept


class MockAdapter(KnowledgeSourceAdapter):
    """Mock adapter for testing the base class."""

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OLS

    async def search_concepts(self, query: str, limit: int = 20):
        return [
            UnifiedConcept(
                primary_id="TEST:001",
                primary_label="Test Concept",
                concept_type=ConceptType.DISEASE,
            )
        ]

    async def get_concept_details(self, concept_id: str):
        return UnifiedConcept(
            primary_id=concept_id,
            primary_label="Test Concept Details",
            concept_type=ConceptType.DISEASE,
        )


class TestKnowledgeSourceAdapter:
    """Tests for KnowledgeSourceAdapter base class."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create a mock adapter instance."""
        return MockAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test adapter initialization."""
        adapter = MockAdapter(lookup_config)
        assert adapter.config == lookup_config
        assert adapter.source == KnowledgeSource.OLS

    def test_get_source(self, adapter):
        """Test get_source method."""
        assert adapter.get_source() == KnowledgeSource.OLS

    @pytest.mark.asyncio
    async def test_search_concepts(self, adapter):
        """Test search_concepts method."""
        results = await adapter.search_concepts("test query")
        assert len(results) == 1
        assert results[0].primary_id == "TEST:001"

    @pytest.mark.asyncio
    async def test_get_concept_details(self, adapter):
        """Test get_concept_details method."""
        result = await adapter.get_concept_details("TEST:001")
        assert result is not None
        assert result.primary_id == "TEST:001"

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

    def test_is_available_default(self, adapter):
        """Test is_available default implementation."""
        assert adapter.is_available() is True

    def test_get_rate_limit(self, adapter):
        """Test get_rate_limit method."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, (int, float))
        assert rate_limit >= 0

    @pytest.mark.asyncio
    async def test_context_manager(self, lookup_config):
        """Test adapter as context manager."""
        async with MockAdapter(lookup_config) as adapter:
            assert adapter is not None
            results = await adapter.search_concepts("test")
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_close_method(self, adapter):
        """Test close method."""
        # Should not raise an error
        await adapter.close()


class TestAbstractMethods:
    """Tests for abstract method enforcement."""

    def test_cannot_instantiate_base_class(self):
        """Test that base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            KnowledgeSourceAdapter(LookupConfig())

    def test_must_implement_get_source(self):
        """Test that get_source must be implemented."""

        class IncompleteAdapter(KnowledgeSourceAdapter):
            async def search_concepts(self, query: str, limit: int = 20):
                pass

            async def get_concept_details(self, concept_id: str):
                pass

        # Missing get_source implementation
        with pytest.raises(TypeError):
            IncompleteAdapter(LookupConfig())

    def test_must_implement_search_concepts(self):
        """Test that search_concepts must be implemented."""

        class IncompleteAdapter(KnowledgeSourceAdapter):
            def get_source(self):
                return KnowledgeSource.OLS

            async def get_concept_details(self, concept_id: str):
                pass

        # Missing search_concepts implementation
        with pytest.raises(TypeError):
            IncompleteAdapter(LookupConfig())

    def test_must_implement_get_concept_details(self):
        """Test that get_concept_details must be implemented."""

        class IncompleteAdapter(KnowledgeSourceAdapter):
            def get_source(self):
                return KnowledgeSource.OLS

            async def search_concepts(self, query: str, limit: int = 20):
                pass

        # Missing get_concept_details implementation
        with pytest.raises(TypeError):
            IncompleteAdapter(LookupConfig())
