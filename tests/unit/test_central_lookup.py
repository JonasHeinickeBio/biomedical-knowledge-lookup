"""
Unit tests for CentralKnowledgeLookup.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from knowledge_lookup.central_lookup import CentralKnowledgeLookup
from knowledge_lookup.models import KnowledgeSource, LookupConfig, UnifiedConcept


class TestCentralKnowledgeLookup:
    """Tests for CentralKnowledgeLookup."""

    @pytest.fixture
    def lookup_config(self):
        """Create LookupConfig instance."""
        return LookupConfig()

    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter."""
        adapter = MagicMock()
        adapter.get_source.return_value = KnowledgeSource.BIOPORTAL
        adapter.is_available.return_value = True
        adapter.get_rate_limit.return_value = 1.0
        adapter.search_concepts = AsyncMock(return_value=[])
        adapter.get_concept_details = AsyncMock(return_value=None)
        adapter.get_mappings = AsyncMock(return_value=[])
        adapter.get_relationships = AsyncMock(return_value=[])
        return adapter

    def test_initialization(self, lookup_config):
        """Test CentralKnowledgeLookup initialization."""
        lookup = CentralKnowledgeLookup(config=lookup_config, auto_initialize=False)
        assert lookup.config == lookup_config
        assert lookup.adapters == {}
        assert lookup.executor is not None

    def test_initialization_with_auto_init(self, lookup_config, mock_adapter):
        """Test initialization with auto_initialize=True."""
        # Since lookup_config has no enabled_sources, init sets to all, so adapters are initialized
        # But since adapters are not available, adapters dict will have some that are available
        # For this test, just check that init doesn't crash
        lookup = CentralKnowledgeLookup(config=lookup_config, auto_initialize=True)
        assert isinstance(lookup.adapters, dict)

    def test_get_available_sources_empty(self):
        """Test get_available_sources with no adapters."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        assert lookup.get_available_sources() == []

    @pytest.mark.asyncio
    async def test_search_concepts_no_sources(self):
        """Test search_concepts with no available sources."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        result = await lookup.search_concepts("test")
        assert result.query == "test"
        assert result.total_found == 0
        assert result.sources_queried == []

    @pytest.mark.asyncio
    async def test_search_concepts_with_mock_adapter(self, mock_adapter):
        """Test search_concepts with a mock adapter."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        mock_adapter.search_concepts.return_value = [
            UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept")
        ]

        result = await lookup.search_concepts("test")
        assert result.query == "test"
        assert result.total_found == 1
        assert len(result.concepts) == 1
        assert result.concepts[0].primary_label == "Test Concept"

    @pytest.mark.asyncio
    async def test_search_concepts_parallel(self, mock_adapter):
        """Test parallel search execution."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        lookup.adapters[KnowledgeSource.OLS] = mock_adapter

        # Create different concepts to avoid deduplication
        mock_adapter.search_concepts.side_effect = [
            [UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept 1")],
            [UnifiedConcept(primary_id="TEST:002", primary_label="Test Concept 2")],
        ]

        result = await lookup.search_concepts("test", parallel=True)
        assert result.total_found == 2  # One from each adapter

    @pytest.mark.asyncio
    async def test_search_concepts_sequential(self, mock_adapter):
        """Test sequential search execution."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        mock_adapter.search_concepts.return_value = [
            UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept")
        ]

        result = await lookup.search_concepts("test", parallel=False)
        assert result.total_found == 1

    @pytest.mark.asyncio
    async def test_get_concept_details(self, mock_adapter):
        """Test get_concept_details."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        mock_concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept")
        mock_adapter.get_concept_details.return_value = mock_concept

        result = await lookup.get_concept_details("TEST:001")
        assert result == mock_concept

    @pytest.mark.asyncio
    async def test_get_concept_details_specific_source(self, mock_adapter):
        """Test get_concept_details from specific source."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        mock_concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept")
        mock_adapter.get_concept_details.return_value = mock_concept

        result = await lookup.get_concept_details("TEST:001", KnowledgeSource.BIOPORTAL)
        assert result == mock_concept
        mock_adapter.get_concept_details.assert_called_once_with("TEST:001")

    @pytest.mark.asyncio
    async def test_add_source(self):
        """Test add_source method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)

        with patch("knowledge_lookup.central_lookup.ADAPTER_CLASSES") as mock_classes:
            mock_adapter_class = MagicMock()
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.is_available.return_value = True
            mock_adapter_class.return_value = mock_adapter_instance

            # Make the mock behave like a dict containing BIOPORTAL
            mock_classes.__contains__ = MagicMock(return_value=True)
            mock_classes.__getitem__ = MagicMock(return_value=mock_adapter_class)

            await lookup.add_source(KnowledgeSource.BIOPORTAL)
            assert KnowledgeSource.BIOPORTAL in lookup.adapters

    def test_remove_source(self, mock_adapter):
        """Test remove_source method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        lookup.remove_source(KnowledgeSource.BIOPORTAL)
        assert KnowledgeSource.BIOPORTAL not in lookup.adapters

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test get_statistics method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        stats = await lookup.get_statistics()
        assert "available_sources" in stats
        assert "total_sources" in stats
        assert "config" in stats

    def test_format_results_table_empty(self):
        """Test format_results_table with empty results."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        from knowledge_lookup.models import LookupResult

        result = LookupResult(query="test")
        table = lookup.format_results_table(result)
        assert "No results found" in table

    def test_export_to_json(self):
        """Test export_to_json method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        from knowledge_lookup.models import LookupResult

        result = LookupResult(query="test")
        json_data = lookup.export_to_json(result)
        assert json_data["query"] == "test"
        assert "concepts" in json_data

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        """Test close method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        await lookup.close()
        # Should not raise exceptions

    def test_lookup_config_initialization(self):
        """Test initialization with explicit config."""
        config = LookupConfig(max_results_per_source=50)
        lookup = CentralKnowledgeLookup(config=config, auto_initialize=False)
        assert lookup.config.max_results_per_source == 50

    @pytest.mark.asyncio
    async def test_search_concepts_deduplication(self, mock_adapter):
        """Test results deduplication in search_concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        lookup.adapters[KnowledgeSource.OLS] = mock_adapter

        # Identical concepts from different sources
        concept1 = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept1.sources.add(KnowledgeSource.BIOPORTAL)
        concept2 = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept2.sources.add(KnowledgeSource.OLS)
        
        mock_adapter.search_concepts.side_effect = [[concept1], [concept2]]

        # Enable deduplication in config
        lookup.config.enable_deduplication = True
        
        result = await lookup.search_concepts("test")
        # Should be deduplicated to 1 concept
        assert len(result.concepts) == 1
        assert KnowledgeSource.BIOPORTAL in result.concepts[0].sources
        assert KnowledgeSource.OLS in result.concepts[0].sources

    @pytest.mark.asyncio
    async def test_search_concepts_error_handling(self, mock_adapter):
        """Test error handling in search_concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        
        mock_adapter.search_concepts.side_effect = Exception("Source error")
        
        result = await lookup.search_concepts("test")
        assert len(result.concepts) == 0
        assert KnowledgeSource.BIOPORTAL in result.errors
        assert KnowledgeSource.BIOPORTAL in result.sources_failed

    @pytest.mark.asyncio
    async def test_get_concept_details_not_found(self, mock_adapter):
        """Test get_concept_details when concept not found."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.get_concept_details.return_value = None
        
        result = await lookup.get_concept_details("NONEXISTENT")
        assert result is None

    def test_format_results_table_with_concepts(self):
        """Test format_results_table with actual concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        from knowledge_lookup.models import LookupResult
        
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test Concept")
        result = LookupResult(query="test", concepts=[concept])
        
        table = lookup.format_results_table(result)
        assert "Test Concept" in table
        assert "ID1" in table

    @pytest.mark.asyncio
    async def test_add_source_invalid(self):
        """Test add_source with invalid source."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        with pytest.raises(ValueError, match="Unsupported knowledge source"):
            await lookup.add_source(MagicMock())

    @pytest.mark.asyncio
    async def test_find_mappings_from_central(self, mock_adapter):
        """Test find_mappings through central lookup."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept.add_identifier(KnowledgeSource.OLS, "MAPPED_ID", "Mapped Label")
        mock_adapter.get_concept_details.return_value = concept
        
        mappings = await lookup.find_mappings("ID1")
        assert len(mappings) == 1
        assert mappings[0].identifier == "MAPPED_ID"
