"""
Unit tests for GeneOntologyAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.geneontology_adapter import GeneOntologyAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept


class TestGeneOntologyAdapter:
    """Tests for GeneOntologyAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create GeneOntologyAdapter instance."""
        return GeneOntologyAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test GeneOntologyAdapter initialization."""
        adapter = GeneOntologyAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.GENEONTOLOGY
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.GENEONTOLOGY

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
        config = LookupConfig(rate_limits={KnowledgeSource.GENEONTOLOGY: 5.0})
        adapter = GeneOntologyAdapter(config)
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


class TestGeneOntologySearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return GeneOntologyAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_with_results(self, adapter):
        """Test search with results."""
        results_data = [
            {
                "id": "GO:0008150",
                "name": "biological_process",
                "aspect": "Biological Process",
                "definition": {"text": "A biological process"},
                "synonyms": [{"name": "BP"}],
            }
        ]
        adapter._make_request = AsyncMock(return_value={"results": results_data})

        result = await adapter.search_concepts("biological process", limit=10)
        assert len(result) == 1
        assert result[0].primary_label == "biological_process"

    @pytest.mark.asyncio
    async def test_search_no_results_key(self, adapter):
        """Test search with no results key."""
        adapter._make_request = AsyncMock(return_value={})
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_exception(self, adapter):
        """Test search handles exceptions."""
        adapter._make_request = AsyncMock(side_effect=Exception("Error"))
        result = await adapter.search_concepts("test")
        assert result == []


class TestGeneOntologyGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return GeneOntologyAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_get_details_success(self, adapter):
        """Test get_details with results."""
        adapter._make_request = AsyncMock(
            return_value={
                "results": [
                    {
                        "id": "GO:0008150",
                        "name": "biological_process",
                        "aspect": "Biological Process",
                    }
                ]
            }
        )

        result = await adapter.get_concept_details("GO:0008150")
        assert result is not None
        assert result.primary_label == "biological_process"

    @pytest.mark.asyncio
    async def test_get_details_no_results(self, adapter):
        """Test get_details with no results."""
        adapter._make_request = AsyncMock(return_value={"results": []})
        result = await adapter.get_concept_details("GO:0008150")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_no_results_key(self, adapter):
        """Test get_details with no results key."""
        adapter._make_request = AsyncMock(return_value={})
        result = await adapter.get_concept_details("GO:0008150")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_exception(self, adapter):
        """Test get_details handles exceptions."""
        adapter._make_request = AsyncMock(side_effect=Exception("Error"))
        result = await adapter.get_concept_details("GO:0008150")
        assert result is None


class TestGeneOntologyConvertResult:
    """Tests for _convert_go_result_to_concept method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return GeneOntologyAdapter(lookup_config)

    def test_convert_result_valid(self, adapter):
        """Test conversion with valid result."""
        result = {
            "id": "GO:0008150",
            "name": "biological_process",
            "aspect": "Biological Process",
            "definition": {"text": "A biological process"},
            "synonyms": [{"name": "BP"}],
        }
        concept = adapter._convert_go_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "biological_process"
        assert "BP" in concept.synonyms
        assert "A biological process" in concept.definitions
        assert any("Aspect:" in c for c in concept.categories)

    def test_convert_result_no_id(self, adapter):
        """Test returns None when no id."""
        result = {"name": "test"}
        concept = adapter._convert_go_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_name(self, adapter):
        """Test returns None when no name."""
        result = {"id": "GO:0008150"}
        concept = adapter._convert_go_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_synonyms(self, adapter):
        """Test conversion without synonyms."""
        result = {
            "id": "GO:0008150",
            "name": "biological_process",
        }
        concept = adapter._convert_go_result_to_concept(result)
        assert concept is not None
        assert concept.synonyms == []

    def test_convert_result_no_definition(self, adapter):
        """Test conversion without definition."""
        result = {
            "id": "GO:0008150",
            "name": "biological_process",
        }
        concept = adapter._convert_go_result_to_concept(result)
        assert concept is not None
        assert concept.definitions == []

    def test_convert_result_empty_aspect(self, adapter):
        """Test conversion with empty aspect."""
        result = {
            "id": "GO:0008150",
            "name": "biological_process",
            "aspect": "",
        }
        concept = adapter._convert_go_result_to_concept(result)
        assert concept is not None
        assert not any("Aspect:" in c for c in concept.categories)

    def test_convert_result_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.geneontology_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_go_result_to_concept(
                {"id": "test", "name": "test"}
            )
            assert result is None
