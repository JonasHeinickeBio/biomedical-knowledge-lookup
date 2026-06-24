"""
Unit tests for MondoAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.mondo_adapter import MondoAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestMondoAdapter:
    """Tests for MondoAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create MondoAdapter instance."""
        return MondoAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test MondoAdapter initialization."""
        adapter = MondoAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.MONDO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.MONDO

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
        config = LookupConfig(rate_limits={KnowledgeSource.MONDO: 5.0})
        adapter = MondoAdapter(config)
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


class TestMondoSearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return MondoAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_with_docs(self, adapter):
        """Test search with docs in response."""
        docs = [
            {
                "short_form": "MONDO:0005148",
                "label": "diabetes mellitus",
                "iri": "http://purl.obolibrary.org/obo/MONDO_0005148",
                "synonym": ["diabetes", "DM"],
                "description": ["A metabolic disease"],
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


class TestMondoGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return MondoAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_get_details_digit_id(self, adapter):
        """Test get_details with digit-only ID adds MONDO prefix."""
        adapter._make_request = AsyncMock(
            return_value={
                "short_form": "MONDO:0005148",
                "label": "diabetes mellitus",
            }
        )

        result = await adapter.get_concept_details("0005148")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_details_with_prefix(self, adapter):
        """Test get_details with MONDO prefix."""
        adapter._make_request = AsyncMock(
            return_value={
                "short_form": "MONDO:0005148",
                "label": "diabetes mellitus",
            }
        )

        result = await adapter.get_concept_details("MONDO:0005148")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_details_empty_response(self, adapter):
        """Test get_details with empty response."""
        adapter._make_request = AsyncMock(return_value={})
        result = await adapter.get_concept_details("MONDO:0005148")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_exception(self, adapter):
        """Test get_details handles exceptions."""
        adapter._make_request = AsyncMock(side_effect=Exception("Error"))
        result = await adapter.get_concept_details("MONDO:0005148")
        assert result is None


class TestMondoConvertResult:
    """Tests for _convert_mondo_result_to_concept method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return MondoAdapter(lookup_config)

    def test_convert_result_valid(self, adapter):
        """Test conversion with valid result."""
        result = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
            "iri": "http://purl.obolibrary.org/obo/MONDO_0005148",
            "synonym": ["diabetes", "DM"],
            "description": ["A metabolic disease"],
        }
        concept = adapter._convert_mondo_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "diabetes mellitus"
        assert "diabetes" in concept.synonyms
        assert "A metabolic disease" in concept.definitions

    def test_convert_result_no_short_form(self, adapter):
        """Test returns None when no short_form."""
        result = {"label": "Test"}
        concept = adapter._convert_mondo_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_label(self, adapter):
        """Test returns None when no label."""
        result = {"short_form": "MONDO:0005148"}
        concept = adapter._convert_mondo_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_synonyms(self, adapter):
        """Test conversion without synonyms."""
        result = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
        }
        concept = adapter._convert_mondo_result_to_concept(result)
        assert concept is not None
        assert concept.synonyms == []

    def test_convert_result_no_descriptions(self, adapter):
        """Test conversion without descriptions."""
        result = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
        }
        concept = adapter._convert_mondo_result_to_concept(result)
        assert concept is not None
        assert concept.definitions == []

    def test_convert_result_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.mondo_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_mondo_result_to_concept(
                {"short_form": "test", "label": "test"}
            )
            assert result is None


class TestMondoConvertDetails:
    """Tests for _convert_mondo_details_to_concept method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return MondoAdapter(lookup_config)

    def test_convert_details_valid(self, adapter):
        """Test conversion with valid data."""
        data = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
            "iri": "http://purl.obolibrary.org/obo/MONDO_0005148",
            "synonyms": ["DM"],
            "description": ["A disease"],
            "annotation": {
                "database_cross_reference": ["UMLS:C0011849", "MESH:D003924"]
            },
        }
        concept = adapter._convert_mondo_details_to_concept(data)
        assert concept is not None
        assert concept.primary_label == "diabetes mellitus"
        assert "DM" in concept.synonyms
        assert "A disease" in concept.definitions
        assert any("Xref:" in c for c in concept.categories)

    def test_convert_details_no_short_form(self, adapter):
        """Test returns None when no short_form."""
        data = {"label": "Test"}
        concept = adapter._convert_mondo_details_to_concept(data)
        assert concept is None

    def test_convert_details_no_label(self, adapter):
        """Test returns None when no label."""
        data = {"short_form": "MONDO:0005148"}
        concept = adapter._convert_mondo_details_to_concept(data)
        assert concept is None

    def test_convert_details_no_synonyms(self, adapter):
        """Test conversion without synonyms."""
        data = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
        }
        concept = adapter._convert_mondo_details_to_concept(data)
        assert concept is not None
        assert concept.synonyms == []

    def test_convert_details_no_descriptions(self, adapter):
        """Test conversion without descriptions."""
        data = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
        }
        concept = adapter._convert_mondo_details_to_concept(data)
        assert concept is not None
        assert concept.definitions == []

    def test_convert_details_no_annotation(self, adapter):
        """Test conversion without annotation."""
        data = {
            "short_form": "MONDO:0005148",
            "label": "diabetes mellitus",
        }
        concept = adapter._convert_mondo_details_to_concept(data)
        assert concept is not None
        assert not any("Xref:" in c for c in concept.categories)

    def test_convert_details_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.mondo_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_mondo_details_to_concept(
                {"short_form": "test", "label": "test"}
            )
            assert result is None
