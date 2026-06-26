"""
Unit tests for helper functions.
"""

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.helpers import (
    _deduplicate_concepts,
    format_results_detailed,
    format_results_table,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupResult, UnifiedConcept


class TestHelpers:
    """Tests for helper functions."""

    @pytest.fixture
    def sample_concepts(self):
        """Create sample concepts for testing."""
        concept1 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test Concept 1", concept_type=ConceptType.DISEASE
        )
        concept1.add_identifier(KnowledgeSource.BIOPORTAL, "TEST:001", "Test Concept 1")

        concept2 = UnifiedConcept(
            primary_id="TEST:002", primary_label="Test Concept 2", concept_type=ConceptType.GENE
        )
        concept2.add_identifier(KnowledgeSource.OLS, "TEST:002", "Test Concept 2")

        # Duplicate concept
        concept3 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test Concept 1", concept_type=ConceptType.DISEASE
        )
        concept3.add_identifier(KnowledgeSource.UNIPROT, "TEST:001", "Test Concept 1")

        return [concept1, concept2, concept3]

    @pytest.fixture
    def sample_result(self, sample_concepts):
        """Create sample lookup result."""
        return LookupResult(
            query="test query",
            concepts=sample_concepts,
            execution_time=1.5,
            sources_queried=[KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS],
            sources_succeeded=[KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS],
        )

    def test_deduplicate_concepts_no_duplicates(self, sample_concepts):
        """Test deduplication with no duplicates."""
        concepts = sample_concepts[:2]  # Remove the duplicate
        deduped = _deduplicate_concepts(concepts)
        assert len(deduped) == 2
        assert deduped == concepts

    def test_deduplicate_concepts_with_duplicates(self, sample_concepts):
        """Test deduplication with duplicates."""
        deduped = _deduplicate_concepts(sample_concepts)
        assert len(deduped) == 2  # Should remove one duplicate
        # Should keep the first occurrence
        assert deduped[0].primary_id == "TEST:001"
        assert deduped[1].primary_id == "TEST:002"

    def test_deduplicate_concepts_empty_list(self):
        """Test deduplication with empty list."""
        deduped = _deduplicate_concepts([])
        assert deduped == []

    def test_deduplicate_concepts_similarity_threshold(self, sample_concepts):
        """Test deduplication respects similarity threshold parameter."""
        deduped = _deduplicate_concepts(sample_concepts, similarity_threshold=0.9)
        assert len(deduped) == 2  # Same result since we're using exact matching

    def test_format_results_table_with_concepts(self, sample_result):
        """Test table formatting with concepts."""
        table = format_results_table(sample_result)
        lines = table.split("\n")

        # Should have header + 3 concept rows (no deduplication in format function)
        assert len(lines) == 4
        assert (
            lines[0]
            == "Primary Label\tPrimary ID\tType\tConfidence\tSources\tSynonyms\tDefinitions"
        )
        assert "Test Concept 1" in lines[1]
        assert "Test Concept 2" in lines[2]

    def test_format_results_table_empty_results(self):
        """Test table formatting with no concepts."""
        result = LookupResult(query="empty", concepts=[])
        table = format_results_table(result)
        assert table == "No concepts found."

    def test_format_results_detailed_with_concepts(self, sample_result):
        """Test detailed formatting with concepts."""
        detailed = format_results_detailed(sample_result)
        lines = detailed.split("\n")

        assert "Concept 1:" in lines[0]
        assert "Label: Test Concept 1" in detailed
        assert "ID: TEST:001" in detailed
        assert "Type: DISEASE" in detailed
        assert "Concept 2:" in lines[7]  # After blank line

    def test_format_results_detailed_empty_results(self):
        """Test detailed formatting with no concepts."""
        result = LookupResult(query="empty", concepts=[])
        detailed = format_results_detailed(result)
        assert detailed == "No concepts found."

    def test_format_results_detailed_with_synonyms_and_definitions(self):
        """Test detailed formatting with synonyms and definitions."""
        concept = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test Concept", concept_type=ConceptType.DISEASE
        )
        concept.synonyms = ["synonym1", "synonym2"]
        concept.definitions = ["definition1", "definition2"]
        concept.semantic_types = ["Disease"]
        concept.categories = ["Category1"]
        concept.parents = ["parent1"]
        concept.children = ["child1"]

        result = LookupResult(query="test", concepts=[concept])
        detailed = format_results_detailed(result)

        assert "Synonyms: synonym1, synonym2" in detailed
        assert "Definitions: definition1, definition2" in detailed
        assert "Semantic Types: Disease" in detailed
        assert "Categories: Category1" in detailed
        assert "Parents: parent1" in detailed
        assert "Children: child1" in detailed
