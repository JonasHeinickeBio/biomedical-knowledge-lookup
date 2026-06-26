"""Unit tests for examples.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import knowledge_lookup.examples as examples
import pytest

pytestmark = pytest.mark.unit


class MockConcept:
    """Mock concept for testing."""

    def __init__(self, label="Test Concept", id_="TEST:001", concept_type="GENE"):
        self.primary_label = label
        self.primary_id = id_
        self.concept_type = MagicMock(value=concept_type)
        self.sources = [MagicMock(value="TEST")]
        self.confidence_score = 0.9
        self.definitions = ["A test definition"]
        self.synonyms = ["Test Synonym"]
        self.semantic_types = ["T123"]
        self.categories = ["Test"]


class MockSearchResult:
    """Mock search result for testing."""

    def __init__(self, concepts=None, total=1):
        self.concepts = concepts or [MockConcept()]
        self.total_found = total
        self.execution_time = 0.1
        self.sources_queried = [MagicMock(value="TEST")]
        self.sources_succeeded = [MagicMock(value="TEST")]
        self.errors = {}
        self.group_by_source = MagicMock(return_value={})


class MockLookup:
    """Mock lookup instance."""

    def __init__(self):
        self.search_concepts = AsyncMock(return_value=MockSearchResult())
        self.get_concept_details = AsyncMock(return_value=MockConcept())
        self.find_mappings = AsyncMock(return_value=[])
        self.get_concept_hierarchy = AsyncMock(return_value={"parents": [], "children": []})
        self.suggest_similar_concepts = AsyncMock(return_value=[])
        self.close = AsyncMock()


class TestExamples:
    """Tests for example functions."""

    @pytest.mark.asyncio
    async def test_example_basic_search(self):
        """Test example_basic_search runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_basic_search()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_example_specific_sources(self):
        """Test example_specific_sources runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_specific_sources()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_example_concept_types(self):
        """Test example_concept_types runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_concept_types()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_example_concept_details(self):
        """Test example_concept_details runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_concept_details()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_example_umls_integration_no_key(self):
        """Test example_umls_integration skips when no key."""
        with patch("os.getenv", return_value=None), patch("builtins.print") as mock_print:
            await examples.example_umls_integration()
            assert any("UMLS" in str(c) for c in mock_print.call_args_list)

    @pytest.mark.asyncio
    async def test_example_cross_reference_mapping(self):
        """Test example_cross_reference_mapping runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_cross_reference_mapping()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_example_concept_hierarchy(self):
        """Test example_concept_hierarchy runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_concept_hierarchy()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_example_similar_concepts(self):
        """Test example_similar_concepts runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.example_similar_concepts()
            mock_lookup.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_main(self):
        """Test main runs without error."""
        mock_lookup = MockLookup()

        with patch(
            "knowledge_lookup.examples.create_knowledge_lookup", return_value=mock_lookup
        ), patch("builtins.print"):
            await examples.main()
