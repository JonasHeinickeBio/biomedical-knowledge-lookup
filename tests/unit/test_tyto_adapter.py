"""
Unit tests for TytoAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.tyto_adapter import TytoAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestTytoAdapter:
    """Tests for TytoAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create TytoAdapter instance."""
        return TytoAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test TytoAdapter initialization."""
        adapter = TytoAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.TYTO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.TYTO

    def test_is_available_with_tyto(self, adapter):
        """Test is_available when tyto is available."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_is_available_without_tyto(self):
        """Test is_available when tyto is not available."""
        import knowledge_lookup.adapters.tyto_adapter as mod
        original_tyto = mod.tyto
        try:
            mod.tyto = None
            adapter2 = TytoAdapter(LookupConfig())
            assert adapter2.is_available() is False
        finally:
            mod.tyto = original_tyto

    @pytest.mark.asyncio
    async def test_get_concept_details_no_tyto(self):
        """Test get_concept_details when tyto is None."""
        import knowledge_lookup.adapters.tyto_adapter as mod
        original_tyto = mod.tyto
        try:
            mod.tyto = None
            adapter2 = TytoAdapter(LookupConfig())
            result = await adapter2.get_concept_details("http://purl.obolibrary.org/obo/DOID_162")
            assert result is None
        finally:
            mod.tyto = original_tyto

    @pytest.mark.asyncio
    async def test_get_concept_details_non_uri(self, adapter):
        """Test get_concept_details with non-URI concept_id (returns None)."""
        result = await adapter.get_concept_details("DOID:162")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_with_tyto_success(self):
        """Test get_concept_details with successful tyto lookup."""
        import knowledge_lookup.adapters.tyto_adapter as mod
        mock_tyto = MagicMock()
        mock_tyto.get_label.return_value = "Diabetes mellitus"

        original_tyto = mod.tyto
        try:
            mod.tyto = mock_tyto
            adapter2 = TytoAdapter(LookupConfig())
            result = await adapter2.get_concept_details("http://purl.obolibrary.org/obo/DOID_162")
            assert result is not None
            assert result.primary_id == "http://purl.obolibrary.org/obo/DOID_162"
            assert result.primary_label == "Diabetes mellitus"
        finally:
            mod.tyto = original_tyto

    @pytest.mark.asyncio
    async def test_get_concept_details_with_tyto_no_label(self):
        """Test get_concept_details when tyto returns None label."""
        import knowledge_lookup.adapters.tyto_adapter as mod
        mock_tyto = MagicMock()
        mock_tyto.get_label.return_value = None

        original_tyto = mod.tyto
        try:
            mod.tyto = mock_tyto
            adapter2 = TytoAdapter(LookupConfig())
            result = await adapter2.get_concept_details("http://purl.obolibrary.org/obo/DOID_162")
            assert result is None
        finally:
            mod.tyto = original_tyto

    @pytest.mark.asyncio
    async def test_get_concept_details_with_tyto_empty_label(self):
        """Test get_concept_details when tyto returns empty string label."""
        import knowledge_lookup.adapters.tyto_adapter as mod
        mock_tyto = MagicMock()
        mock_tyto.get_label.return_value = ""

        original_tyto = mod.tyto
        try:
            mod.tyto = mock_tyto
            adapter2 = TytoAdapter(LookupConfig())
            result = await adapter2.get_concept_details("http://purl.obolibrary.org/obo/DOID_162")
            assert result is None
        finally:
            mod.tyto = original_tyto

    @pytest.mark.asyncio
    async def test_get_concept_details_with_tyto_exception(self):
        """Test get_concept_details when tyto raises exception."""
        import knowledge_lookup.adapters.tyto_adapter as mod
        mock_tyto = MagicMock()
        mock_tyto.get_label.side_effect = Exception("Ontology error")

        original_tyto = mod.tyto
        try:
            mod.tyto = mock_tyto
            adapter2 = TytoAdapter(LookupConfig())
            result = await adapter2.get_concept_details("http://purl.obolibrary.org/obo/DOID_162")
            assert result is None
        finally:
            mod.tyto = original_tyto

    @pytest.mark.asyncio
    async def test_search_concepts_always_empty(self, adapter):
        """Test search_concepts always returns empty list."""
        results = await adapter.search_concepts("test query")
        assert results == []

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.TYTO: 5.0})
        adapter = TytoAdapter(config)
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
