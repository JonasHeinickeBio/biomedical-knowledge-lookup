"""
Unit tests for CentralKnowledgeLookup.
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.cache import cache as cache_module
from knowledge_lookup.cache import get_cache, init_cache
from knowledge_lookup.core.central_lookup import CentralKnowledgeLookup
from knowledge_lookup.models import (
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)

pytestmark = pytest.mark.unit


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
        adapter.close = AsyncMock()
        return adapter

    def test_initialization(self, lookup_config):
        """Test CentralKnowledgeLookup initialization."""
        lookup = CentralKnowledgeLookup(config=lookup_config, auto_initialize=False)
        assert lookup.config == lookup_config
        assert lookup.adapters == {}
        assert lookup.executor is not None

    def test_initialization_with_auto_init(self, lookup_config, mock_adapter):
        """Test initialization with auto_initialize=True."""
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

        mock_adapter.search_concepts.side_effect = [
            [UnifiedConcept(primary_id="TEST:001", primary_label="Test Concept 1")],
            [UnifiedConcept(primary_id="TEST:002", primary_label="Test Concept 2")],
        ]

        result = await lookup.search_concepts("test", parallel=True)
        assert result.total_found == 2

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
    async def test_get_concept_details_error_specific_source(self, mock_adapter):
        """Test get_concept_details error in specific source."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.get_concept_details.side_effect = Exception("API error")

        result = await lookup.get_concept_details("TEST:001", KnowledgeSource.BIOPORTAL)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_try_all_sources_error(self, mock_adapter):
        """Test get_concept_details when all sources fail."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.get_concept_details.side_effect = Exception("API error")

        result = await lookup.get_concept_details("TEST:001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_try_all_sources(self, mock_adapter):
        """Test get_concept_details tries all sources and returns first hit."""
        mock_adapter2 = MagicMock()
        mock_adapter2.get_concept_details = AsyncMock(return_value=None)
        mock_adapter2.close = AsyncMock()

        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        lookup.adapters[KnowledgeSource.OLS] = mock_adapter2

        concept = UnifiedConcept(primary_id="ID1", primary_label="Found")
        mock_adapter.get_concept_details.return_value = concept

        result = await lookup.get_concept_details("ID1")
        assert result == concept

    @pytest.mark.asyncio
    async def test_add_source(self):
        """Test add_source method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)

        with patch("knowledge_lookup.core.central_lookup.ADAPTER_CLASSES") as mock_classes:
            mock_adapter_class = MagicMock()
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.is_available.return_value = True
            mock_adapter_class.return_value = mock_adapter_instance

            mock_classes.__contains__ = MagicMock(return_value=True)
            mock_classes.__getitem__ = MagicMock(return_value=mock_adapter_class)

            await lookup.add_source(KnowledgeSource.BIOPORTAL)
            assert KnowledgeSource.BIOPORTAL in lookup.adapters

    @pytest.mark.asyncio
    async def test_add_source_already_exists(self):
        """Test add_source when adapter already exists."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        existing = MagicMock()
        lookup.adapters[KnowledgeSource.BIOPORTAL] = existing

        await lookup.add_source(KnowledgeSource.BIOPORTAL)
        assert lookup.adapters[KnowledgeSource.BIOPORTAL] is existing

    @pytest.mark.asyncio
    async def test_add_source_not_available(self):
        """Test add_source when adapter is not available."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)

        with patch("knowledge_lookup.core.central_lookup.ADAPTER_CLASSES") as mock_classes:
            mock_adapter_class = MagicMock()
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.is_available.return_value = False
            mock_adapter_class.return_value = mock_adapter_instance

            mock_classes.__contains__ = MagicMock(return_value=True)
            mock_classes.__getitem__ = MagicMock(return_value=mock_adapter_class)

            with pytest.raises(RuntimeError, match="adapter is not available"):
                await lookup.add_source(KnowledgeSource.BIOPORTAL)

    @pytest.mark.asyncio
    async def test_add_source_exception(self):
        """Test add_source when adapter init raises."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)

        with patch("knowledge_lookup.core.central_lookup.ADAPTER_CLASSES") as mock_classes:
            mock_adapter_class = MagicMock()
            mock_adapter_class.side_effect = Exception("Init failed")

            mock_classes.__contains__ = MagicMock(return_value=True)
            mock_classes.__getitem__ = MagicMock(return_value=mock_adapter_class)

            with pytest.raises(RuntimeError, match="Failed to initialize"):
                await lookup.add_source(KnowledgeSource.BIOPORTAL)

    def test_remove_source(self, mock_adapter):
        """Test remove_source method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        lookup.remove_source(KnowledgeSource.BIOPORTAL)
        assert KnowledgeSource.BIOPORTAL not in lookup.adapters

    def test_remove_source_not_found(self):
        """Test remove_source when source not in adapters."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.remove_source(KnowledgeSource.BIOPORTAL)

    def test_remove_source_from_config(self, mock_adapter):
        """Test remove_source also removes from enabled_sources."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.config.enabled_sources = [KnowledgeSource.BIOPORTAL]
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        lookup.remove_source(KnowledgeSource.BIOPORTAL)
        assert KnowledgeSource.BIOPORTAL not in lookup.config.enabled_sources

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test get_statistics method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        stats = await lookup.get_statistics()
        assert "available_sources" in stats
        assert "total_sources" in stats
        assert "config" in stats
        assert "max_results_per_source" in stats["config"]

    def test_format_results_table_empty(self):
        """Test format_results_table with empty results."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        result = LookupResult(query="test")
        table = lookup.format_results_table(result)
        assert "No results found" in table

    def test_export_to_json(self):
        """Test export_to_json method."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
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

        concept1 = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept1.sources.append(KnowledgeSource.BIOPORTAL)
        concept2 = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept2.sources.append(KnowledgeSource.OLS)

        mock_adapter.search_concepts.side_effect = [[concept1], [concept2]]
        lookup.config.enable_deduplication = True

        result = await lookup.search_concepts("test")
        assert len(result.concepts) == 1

    @pytest.mark.asyncio
    async def test_search_concepts_error_handling(self, mock_adapter):
        """Test error handling in search_concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.search_concepts.side_effect = Exception("Source error")

        result = await lookup.search_concepts("test")
        assert len(result.concepts) == 0
        assert KnowledgeSource.BIOPORTAL in result.errors

    @pytest.mark.asyncio
    async def test_search_concepts_sequential_error(self, mock_adapter):
        """Test sequential search error handling."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.search_concepts.side_effect = Exception("fail")

        result = await lookup.search_concepts("test", parallel=False)
        assert KnowledgeSource.BIOPORTAL in result.errors

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
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test Concept")
        result = LookupResult(query="test", concepts=[concept])

        table = lookup.format_results_table(result)
        assert "Test Concept" in table
        assert "ID1" in table

    def test_format_results_table_many_concepts(self):
        """Test format_results_table with >20 concepts shows 'more' line."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concepts = [
            UnifiedConcept(primary_id=f"ID{i}", primary_label=f"Concept {i}") for i in range(25)
        ]
        result = LookupResult(query="test", concepts=concepts)
        table = lookup.format_results_table(result)
        assert "more results" in table

    def test_format_results_table_with_errors(self):
        """Test format_results_table with errors."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test")
        result = LookupResult(
            query="test",
            concepts=[concept],
            errors={KnowledgeSource.BIOPORTAL: "timeout"},
        )
        table = lookup.format_results_table(result)
        assert "ERRORS" in table
        assert "timeout" in table

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

    @pytest.mark.asyncio
    async def test_find_mappings_no_concept(self, mock_adapter):
        """Test find_mappings when concept not found returns empty."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        mock_adapter.get_concept_details.return_value = None
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        mappings = await lookup.find_mappings("NONEXISTENT")
        assert mappings == []

    @pytest.mark.asyncio
    async def test_find_mappings_with_target_sources(self, mock_adapter):
        """Test find_mappings filters by target_sources."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        concept = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept.add_identifier(KnowledgeSource.OLS, "ID_OLS", "OLS Label")
        concept.add_identifier(KnowledgeSource.UMLS, "ID_UMLS", "UMLS Label")
        mock_adapter.get_concept_details.return_value = concept

        mappings = await lookup.find_mappings("ID1", target_sources=[KnowledgeSource.OLS])
        assert len(mappings) == 1
        assert mappings[0].source == KnowledgeSource.OLS

    @pytest.mark.asyncio
    async def test_search_concepts_with_concept_type_filter(self, mock_adapter):
        """Test search_concepts with concept_type filtering."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        c1 = UnifiedConcept(
            primary_id="ID1",
            primary_label="Disease",
            concept_type=ConceptType.DISEASE,
        )
        c2 = UnifiedConcept(
            primary_id="ID2",
            primary_label="Gene",
            concept_type=ConceptType.GENE,
        )
        mock_adapter.search_concepts.return_value = [c1, c2]

        result = await lookup.search_concepts("test", concept_types=[ConceptType.DISEASE])
        assert len(result.concepts) == 1
        assert result.concepts[0].concept_type == ConceptType.DISEASE

    @pytest.mark.asyncio
    async def test_search_concepts_specific_sources(self, mock_adapter):
        """Test search_concepts with specific sources param."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        lookup.adapters[KnowledgeSource.OLS] = mock_adapter

        mock_adapter.search_concepts.return_value = [
            UnifiedConcept(primary_id="ID1", primary_label="C1")
        ]

        result = await lookup.search_concepts("test", sources=[KnowledgeSource.BIOPORTAL])
        assert result.total_found == 1

    @pytest.mark.asyncio
    async def test_get_concept_hierarchy(self, mock_adapter):
        """Test get_concept_hierarchy."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        parent = UnifiedConcept(primary_id="P1", primary_label="Parent")
        child = UnifiedConcept(primary_id="C1", primary_label="Child")
        concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Self",
            parents=["P1"],
            children=["C1"],
        )
        mock_adapter.get_concept_details.side_effect = [concept, parent, child]

        hierarchy = await lookup.get_concept_hierarchy("ID1", direction="both")
        assert len(hierarchy["parents"]) == 1
        assert len(hierarchy["children"]) == 1

    @pytest.mark.asyncio
    async def test_get_concept_hierarchy_no_concept(self, mock_adapter):
        """Test get_concept_hierarchy when concept not found."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        mock_adapter.get_concept_details.return_value = None
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        hierarchy = await lookup.get_concept_hierarchy("MISSING")
        assert hierarchy["parents"] == []
        assert hierarchy["children"] == []
        assert hierarchy["siblings"] == []

    @pytest.mark.asyncio
    async def test_suggest_similar_concepts(self, mock_adapter):
        """Test suggest_similar_concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        ref_concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Diabetes",
            synonyms=["diabetes mellitus", "DM"],
            concept_type=ConceptType.DISEASE,
        )
        similar = UnifiedConcept(
            primary_id="ID2",
            primary_label="Diabetes Mellitus",
            confidence_score=0.9,
            concept_type=ConceptType.DISEASE,
        )
        mock_adapter.get_concept_details.return_value = ref_concept
        mock_adapter.search_concepts.return_value = [similar]

        results = await lookup.suggest_similar_concepts("ID1", similarity_threshold=0.5)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_suggest_similar_concepts_not_found(self, mock_adapter):
        """Test suggest_similar_concepts when concept not found."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        mock_adapter.get_concept_details.return_value = None
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter

        results = await lookup.suggest_similar_concepts("MISSING")
        assert results == []

    def test_format_results_detailed_empty(self):
        """Test format_results_detailed with empty results."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        result = LookupResult(query="test")
        output = lookup.format_results_detailed(result)
        assert "No results found" in output

    def test_format_results_detailed_with_concepts(self):
        """Test format_results_detailed with concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Diabetes",
            definitions=["A metabolic disease"],
            synonyms=["DM", "diabetes mellitus"],
            semantic_types=["Disease"],
            categories=["Endocrine"],
        )
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.OLS],
        )
        output = lookup.format_results_detailed(result)
        assert "Diabetes" in output
        assert "A metabolic disease" in output
        assert "DM" in output
        assert "Disease" in output
        assert "Endocrine" in output

    def test_format_results_detailed_many_concepts(self):
        """Test format_results_detailed with >10 concepts."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concepts = [UnifiedConcept(primary_id=f"ID{i}", primary_label=f"C{i}") for i in range(15)]
        result = LookupResult(query="test", concepts=concepts)
        output = lookup.format_results_detailed(result)
        assert "more results" in output

    def test_format_results_detailed_with_errors(self):
        """Test format_results_detailed with errors."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test")
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.OLS],
            errors={KnowledgeSource.BIOPORTAL: "timeout"},
        )
        output = lookup.format_results_detailed(result)
        assert "Sources with errors" in output

    def test_export_to_json_with_file(self):
        """Test export_to_json writes to file."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        result = LookupResult(query="test")
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "out.json"
            returned = lookup.export_to_json(result, filepath=filepath)
            assert filepath.exists()
            assert str(filepath) == returned

    def test_export_to_csv(self):
        """Test export_to_csv."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Test",
            concept_type=ConceptType.DISEASE,
            definitions=["def"],
            synonyms=["syn"],
            semantic_types=["type1"],
            categories=["cat1"],
        )
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
        )
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "out.csv"
            lookup.export_to_csv(result, filepath)
            assert filepath.exists()
            content = filepath.read_text()
            assert "Test" in content

    def test_export_to_ttl(self):
        """Test export_to_ttl."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(
            primary_id="ID:1",
            primary_label="Test Concept",
            concept_type=ConceptType.DISEASE,
            definitions=["A definition"],
            synonyms=["syn1", "syn2"],
            semantic_types=["Disease"],
        )
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            execution_time=1.5,
            total_found=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "out.ttl"
            lookup.export_to_ttl(result, filepath)
            assert filepath.exists()
            content = filepath.read_text()
            assert "@prefix" in content
            assert "Test Concept" in content

    def test_escape_ttl_string(self):
        """Test _escape_ttl_string."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        assert lookup._escape_ttl_string('hello "world"') == 'hello \\"world\\"'
        assert lookup._escape_ttl_string("line\nnew") == "line\\nnew"
        assert lookup._escape_ttl_string("cr\rreturn") == "cr\\rreturn"
        assert lookup._escape_ttl_string("back\\slash") == "back\\\\slash"

    def test_export_to_dataframe(self):
        """Test export_to_dataframe."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Test",
            concept_type=ConceptType.DISEASE,
            confidence_score=0.9,
        )
        concept.sources.append(KnowledgeSource.OLS)
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.OLS],
            execution_time=1.0,
            total_found=1,
        )
        try:
            df = lookup.export_to_dataframe(result)
            assert len(df) == 1
            assert df.attrs["query"] == "test"
        except ImportError:
            pytest.skip("pandas not installed")

    def test_export_to_excel(self):
        """Test export_to_excel."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Test",
            concept_type=ConceptType.DISEASE,
            confidence_score=0.9,
        )
        concept.sources.append(KnowledgeSource.OLS)
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.OLS],
            execution_time=1.0,
            total_found=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "out.xlsx"
            try:
                lookup.export_to_excel(result, filepath)
                assert filepath.exists()
            except ImportError:
                pytest.skip("pandas/openpyxl not installed")

    def test_export_to_excel_with_errors(self):
        """Test export_to_excel includes errors sheet."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test")
        concept.sources.append(KnowledgeSource.OLS)
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.OLS],
            errors={KnowledgeSource.BIOPORTAL: "timeout"},
            total_found=1,
        )
        openpyxl = pytest.importorskip("openpyxl")
        pytest.importorskip("pandas")
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "out.xlsx"
            lookup.export_to_excel(result, filepath)
            workbook = openpyxl.load_workbook(filepath)
            assert workbook.sheetnames == ["Summary", "Results", "Source Stats", "Errors"]
            rows = list(workbook["Errors"].iter_rows(values_only=True))
            assert rows == [("Source", "Error"), ("BIOPORTAL", "timeout")]

    def test_export_summary_report(self):
        """Test export_summary_report."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(
            primary_id="ID1",
            primary_label="Diabetes",
            confidence_score=0.95,
        )
        concept.sources.append(KnowledgeSource.OLS)
        result = LookupResult(
            query="diabetes",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.OLS],
            execution_time=1.2,
            total_found=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "report.txt"
            lookup.export_summary_report(result, filepath)
            assert filepath.exists()
            content = filepath.read_text()
            assert "KNOWLEDGE LOOKUP ANALYSIS REPORT" in content
            assert "Diabetes" in content

    def test_export_summary_report_no_results(self):
        """Test export_summary_report with no results."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        result = LookupResult(
            query="nothing",
            total_found=0,
            sources_queried=[KnowledgeSource.OLS],
            sources_succeeded=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "report.txt"
            lookup.export_summary_report(result, filepath)
            content = filepath.read_text()
            assert "RECOMMENDATIONS" in content

    def test_export_summary_report_with_errors(self):
        """Test export_summary_report with errors."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        concept = UnifiedConcept(primary_id="ID1", primary_label="Test", confidence_score=0.5)
        concept.sources.append(KnowledgeSource.OLS)
        result = LookupResult(
            query="test",
            concepts=[concept],
            sources_queried=[KnowledgeSource.OLS, KnowledgeSource.BIOPORTAL],
            sources_succeeded=[KnowledgeSource.OLS],
            execution_time=1.0,
            total_found=1,
            errors={KnowledgeSource.BIOPORTAL: "timeout"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "report.txt"
            lookup.export_summary_report(result, filepath)
            content = filepath.read_text()
            assert "ERRORS" in content

    def test_deduplicate_concepts_empty(self):
        """Test _deduplicate_concepts with empty list."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        result = lookup._deduplicate_concepts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parallel_error(self, mock_adapter):
        """Test _search_parallel when task raises."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.search_concepts.side_effect = Exception("boom")

        result = await lookup._search_parallel("q", [KnowledgeSource.BIOPORTAL], 10)
        assert isinstance(result[KnowledgeSource.BIOPORTAL], Exception)

    @pytest.mark.asyncio
    async def test_search_sequential_error(self, mock_adapter):
        """Test _search_sequential when source raises."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        mock_adapter.search_concepts.side_effect = Exception("boom")

        result = await lookup._search_sequential("q", [KnowledgeSource.BIOPORTAL], 10)
        assert isinstance(result[KnowledgeSource.BIOPORTAL], Exception)

    @pytest.mark.asyncio
    async def test_search_single_source_not_available(self, mock_adapter):
        """Test _search_single_source when adapter not available."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        with pytest.raises(ValueError, match="not available"):
            await lookup._search_single_source(KnowledgeSource.BIOPORTAL, "q", 10)

    def test_init_adapters_exception_handling(self):
        """Test _initialize_adapters handles exceptions."""
        with patch("knowledge_lookup.core.central_lookup.ADAPTER_CLASSES") as mock_classes:
            config = LookupConfig(enabled_sources=[KnowledgeSource.BIOPORTAL])
            mock_adapter_class = MagicMock(side_effect=Exception("init fail"))

            mock_dict = {KnowledgeSource.BIOPORTAL: mock_adapter_class}
            mock_classes.items.return_value = mock_dict.items()

            lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
            assert KnowledgeSource.BIOPORTAL not in lookup.adapters

    def test_init_adapters_not_available(self):
        """Test _initialize_adapters when adapter not available."""
        with patch("knowledge_lookup.core.central_lookup.ADAPTER_CLASSES") as mock_classes:
            config = LookupConfig(enabled_sources=[KnowledgeSource.BIOPORTAL])
            mock_adapter_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = False
            mock_adapter_class.return_value = mock_instance

            mock_dict = {KnowledgeSource.BIOPORTAL: mock_adapter_class}
            mock_classes.items.return_value = mock_dict.items()

            lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
            assert KnowledgeSource.BIOPORTAL not in lookup.adapters

    def test_initialization_enables_all_sources(self):
        """Test init enables all sources when none specified."""
        config = LookupConfig(enabled_sources=[])
        lookup = CentralKnowledgeLookup(config=config, auto_initialize=False)
        assert len(lookup.config.enabled_sources) > 0

    @pytest.mark.asyncio
    async def test_search_concepts_disabled_dedup(self, mock_adapter):
        """Test search_concepts with dedup disabled."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[KnowledgeSource.BIOPORTAL] = mock_adapter
        lookup.config.enable_deduplication = False

        mock_adapter.search_concepts.return_value = [
            UnifiedConcept(primary_id="ID1", primary_label="A"),
        ]

        result = await lookup.search_concepts("test")
        assert result.total_found == 1


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

HPO = KnowledgeSource.HPO
MONDO = KnowledgeSource.MONDO


def _adapter(delay: float = 0.0, concepts=None, error: Exception | None = None):
    """Mock adapter whose search sleeps *delay* seconds, then returns *concepts* or raises."""
    adapter = MagicMock()
    adapter.get_rate_limit.return_value = 0

    async def _search(query, limit):
        await asyncio.sleep(delay)
        if error is not None:
            raise error
        return list(concepts or [])

    adapter.search_concepts = AsyncMock(side_effect=_search)
    return adapter


def _concept(primary_id: str) -> UnifiedConcept:
    return UnifiedConcept(primary_id=primary_id, primary_label=f"label {primary_id}")


def _tracked_lookup() -> CentralKnowledgeLookup:
    config = LookupConfig(enable_source_health_tracking=True)
    return CentralKnowledgeLookup(config=config, auto_initialize=False)


def _add(lookup: CentralKnowledgeLookup, source: KnowledgeSource, adapter) -> None:
    lookup.health_tracker.wire_adapter(source, adapter)
    lookup.adapters[source] = adapter


def _open_breaker(lookup: CentralKnowledgeLookup, source: KnowledgeSource):
    breaker = lookup.health_tracker.get_or_create(source)
    for _ in range(breaker.threshold):
        breaker.record_failure()
    return breaker


class TestLookupAndConvertToRdf:
    @pytest.mark.asyncio
    async def test_lookup_and_convert_to_rdf_builds_and_saves_graph(self, tmp_path):
        """The converter is imported from knowledge_lookup.services (was ModuleNotFoundError)."""
        lookup = CentralKnowledgeLookup(auto_initialize=False)
        lookup.adapters[HPO] = _adapter(concepts=[_concept("HP:0001250")])
        out = tmp_path / "rdf" / "result.ttl"

        graph = await lookup.lookup_and_convert_to_rdf("seizure", output_path=out)

        assert len(graph) > 0
        assert out.exists()
        assert "label HP:0001250" in out.read_text(encoding="utf-8")


class TestSourceHealthRegressions:
    def test_zero_breaker_settings_are_not_replaced_by_defaults(self):
        config = LookupConfig(circuit_breaker_threshold=1, circuit_breaker_cooldown=0.0)
        lookup = CentralKnowledgeLookup(config=config, auto_initialize=False)

        breaker = lookup.health_tracker.get_or_create(HPO)

        assert breaker.threshold == 1
        assert breaker.cooldown == 0.0

    def test_unset_breaker_settings_use_defaults(self):
        breaker = _tracked_lookup().health_tracker.get_or_create(HPO)

        assert breaker.threshold == 5
        assert breaker.cooldown == 30.0

    def test_get_health_sets_is_open(self):
        lookup = _tracked_lookup()
        lookup.health_tracker.get_or_create(MONDO)
        _open_breaker(lookup, HPO)

        hpo = lookup.health_tracker.get_health(HPO)
        mondo = lookup.health_tracker.get_health(MONDO)

        assert hpo.is_open is True and hpo.circuit_state == "OPEN"
        assert mondo.is_open is False and mondo.circuit_state == "CLOSED"
        assert lookup.health_tracker.open_sources() == {HPO}

    def test_get_health_open_breaker_past_cooldown_is_half_open(self):
        lookup = _tracked_lookup()
        breaker = _open_breaker(lookup, HPO)
        breaker.last_failure_time = breaker._now() - breaker.cooldown - 1

        health = lookup.health_tracker.get_health(HPO)

        assert health.is_open is False and health.circuit_state == "HALF_OPEN"
        assert lookup.health_tracker.open_sources() == set()

    @pytest.mark.asyncio
    async def test_get_statistics_with_tracked_sources(self):
        """circuit_state is a plain string after model regeneration (was AttributeError)."""
        lookup = _tracked_lookup()
        _add(lookup, HPO, _adapter())
        _add(lookup, MONDO, _adapter())
        _open_breaker(lookup, HPO)

        stats = await lookup.get_statistics()

        assert stats["source_health"]["HPO"]["state"] == "OPEN"
        assert stats["source_health"]["MONDO"]["state"] == "CLOSED"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("parallel", [True, False])
    async def test_search_skips_source_with_open_breaker(self, parallel):
        lookup = _tracked_lookup()
        hpo = _adapter(concepts=[_concept("HP:1")])
        mondo = _adapter(concepts=[_concept("MONDO:1")])
        _add(lookup, HPO, hpo)
        _add(lookup, MONDO, mondo)
        _open_breaker(lookup, HPO)

        result = await lookup.search_concepts("q", parallel=parallel)

        hpo.search_concepts.assert_not_awaited()
        assert "Circuit breaker open" in result.errors["HPO"]
        assert [c.primary_id for c in result.concepts] == ["MONDO:1"]

    @pytest.mark.asyncio
    async def test_open_breaker_is_probed_after_cooldown(self):
        lookup = _tracked_lookup()
        hpo = _adapter(concepts=[_concept("HP:1")])
        _add(lookup, HPO, hpo)
        breaker = _open_breaker(lookup, HPO)
        breaker.last_failure_time = breaker._now() - breaker.cooldown - 1

        result = await lookup.search_concepts("q")

        hpo.search_concepts.assert_awaited_once()
        assert result.errors == {}

    def test_format_results_table_lists_open_circuits(self):
        lookup = _tracked_lookup()
        lookup.health_tracker.get_or_create(MONDO)
        _open_breaker(lookup, HPO)
        result = LookupResult(query="q", concepts=[_concept("HP:1")])
        result.source_health = lookup.health_tracker.all_health()

        table = lookup.format_results_table(result)

        assert "CIRCUIT OPEN: HPO" in table


class TestCacheInitialisation:
    def test_init_keeps_preconfigured_cache(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cache_module, "_cache_instance", None)
        configured = init_cache(disk_cache_dir=tmp_path)

        CentralKnowledgeLookup(auto_initialize=False)

        assert get_cache() is configured

    def test_init_creates_default_cache_when_missing(self, monkeypatch):
        monkeypatch.setattr(cache_module, "_cache_instance", None)

        CentralKnowledgeLookup(auto_initialize=False)

        assert cache_module._cache_instance is not None
        assert get_cache()._default_ttl == 3600  # init_cache() defaults


class TestPerSourceTimeout:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("parallel", [True, False])
    async def test_single_source_search_applies_timeout(self, parallel):
        lookup = CentralKnowledgeLookup(
            LookupConfig(timeout_per_source=0.1), auto_initialize=False
        )
        lookup.adapters[HPO] = _adapter(delay=5)

        start = time.monotonic()
        result = await lookup.search_concepts("q", parallel=parallel)

        assert time.monotonic() - start < 2
        assert result.errors == {"HPO": "Timed out after 0.1s"}

    @pytest.mark.asyncio
    async def test_sequential_search_applies_timeout_per_source(self):
        lookup = CentralKnowledgeLookup(
            LookupConfig(timeout_per_source=0.1), auto_initialize=False
        )
        lookup.adapters[HPO] = _adapter(delay=5)
        lookup.adapters[MONDO] = _adapter(concepts=[_concept("MONDO:1")])

        start = time.monotonic()
        result = await lookup.search_concepts("q", parallel=False)

        assert time.monotonic() - start < 2
        assert result.errors == {"HPO": "Timed out after 0.1s"}
        assert [c.primary_id for c in result.concepts] == ["MONDO:1"]

    @pytest.mark.asyncio
    async def test_parallel_timeout_counts_from_start_for_every_source(self):
        """A later source must not inherit the time spent waiting on earlier ones."""
        lookup = CentralKnowledgeLookup(
            LookupConfig(timeout_per_source=0.75), auto_initialize=False
        )
        lookup.adapters[HPO] = _adapter(delay=0.5, concepts=[_concept("HP:1")])
        lookup.adapters[MONDO] = _adapter(delay=1.0, concepts=[_concept("MONDO:1")])

        result = await lookup.search_concepts("q", parallel=True)

        assert result.errors == {"MONDO": "Timed out after 0.75s"}
        assert [c.primary_id for c in result.concepts] == ["HP:1"]

    @pytest.mark.asyncio
    async def test_adapter_timeout_error_keeps_its_message(self):
        lookup = CentralKnowledgeLookup(LookupConfig(timeout_per_source=5), auto_initialize=False)
        lookup.adapters[HPO] = _adapter(error=TimeoutError("upstream read timeout"))

        result = await lookup.search_concepts("q")

        assert result.errors == {"HPO": "upstream read timeout"}


def _tracked_lookup_with_timeout(threshold: int = 2, timeout: float = 0.05):
    config = LookupConfig(
        enable_source_health_tracking=True,
        timeout_per_source=timeout,
        circuit_breaker_threshold=threshold,
        circuit_breaker_cooldown=60,
    )
    return CentralKnowledgeLookup(config=config, auto_initialize=False)


def _details_adapter(delay: float = 0.0, concept=None):
    """Mock adapter whose get_concept_details sleeps *delay* seconds, then returns *concept*."""
    adapter = MagicMock()
    adapter.get_rate_limit.return_value = 0

    async def _details(concept_id):
        await asyncio.sleep(delay)
        return concept

    adapter.get_concept_details = AsyncMock(side_effect=_details)
    return adapter


class TestTimeoutsAndOpenBreakers:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("parallel", [True, False])
    async def test_search_timeouts_open_the_breaker(self, parallel):
        """Regression: a source cut off by timeout_per_source never opened its breaker."""
        lookup = _tracked_lookup_with_timeout(threshold=2)
        hpo = _adapter(delay=5)
        _add(lookup, HPO, hpo)
        _add(lookup, MONDO, _adapter(concepts=[_concept("MONDO:1")]))

        for _ in range(2):
            result = await lookup.search_concepts("q", parallel=parallel)
            assert result.errors["HPO"] == "Timed out after 0.05s"
        assert lookup.health_tracker.get_health(HPO).is_open is True

        result = await lookup.search_concepts("q", parallel=parallel)

        assert hpo.search_concepts.await_count == 2  # the third search skipped HPO
        assert "Circuit breaker open" in result.errors["HPO"]
        assert lookup.health_tracker.get_health(MONDO).failure_count == 0

    @pytest.mark.asyncio
    async def test_timeout_raised_by_the_adapter_is_not_recorded_by_the_lookup(self):
        lookup = _tracked_lookup_with_timeout(threshold=2, timeout=5)
        _add(lookup, HPO, _adapter(error=TimeoutError("upstream read timeout")))

        await lookup.search_concepts("q")

        assert lookup.health_tracker.get_health(HPO).failure_count == 0

    @pytest.mark.asyncio
    async def test_timeouts_are_not_recorded_without_health_tracking(self):
        lookup = CentralKnowledgeLookup(
            LookupConfig(timeout_per_source=0.05), auto_initialize=False
        )
        lookup.adapters[HPO] = _adapter(delay=5)
        breaker = lookup.health_tracker.get_or_create(HPO)

        await lookup.search_concepts("q")

        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("with_source", [True, False])
    async def test_get_concept_details_skips_open_breaker(self, with_source):
        """Regression: get_concept_details still called sources whose breaker was open."""
        lookup = _tracked_lookup_with_timeout()
        hpo = _details_adapter(concept=_concept("HP:1"))
        mondo = _details_adapter(concept=_concept("MONDO:1"))
        _add(lookup, HPO, hpo)
        _add(lookup, MONDO, mondo)
        _open_breaker(lookup, HPO)

        concept = await lookup.get_concept_details("X:1", source=HPO if with_source else None)

        hpo.get_concept_details.assert_not_awaited()
        if with_source:
            assert concept is None
        else:
            assert concept.primary_id == "MONDO:1"

    @pytest.mark.asyncio
    async def test_get_concept_details_timeouts_open_the_breaker(self):
        lookup = _tracked_lookup_with_timeout(threshold=2)
        hpo = _details_adapter(delay=5, concept=_concept("HP:1"))
        _add(lookup, HPO, hpo)

        for _ in range(2):
            assert await lookup.get_concept_details("HP:1", source=HPO) is None
        assert lookup.health_tracker.get_health(HPO).is_open is True

        assert await lookup.get_concept_details("HP:1", source=HPO) is None
        assert hpo.get_concept_details.await_count == 2

    @pytest.mark.asyncio
    async def test_get_concept_details_probes_after_cooldown(self):
        lookup = _tracked_lookup_with_timeout()
        hpo = _details_adapter(concept=_concept("HP:1"))
        _add(lookup, HPO, hpo)
        breaker = _open_breaker(lookup, HPO)
        breaker.last_failure_time = breaker._now() - breaker.cooldown - 1

        concept = await lookup.get_concept_details("HP:1", source=HPO)

        assert concept.primary_id == "HP:1"
