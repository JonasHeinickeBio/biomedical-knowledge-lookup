"""
Unit tests for models.
"""

from knowledge_lookup.models import (
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)


class TestUnifiedConcept:
    """Tests for UnifiedConcept."""

    def test_unified_concept_creation(self):
        """Test UnifiedConcept creation."""
        concept = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test Concept", concept_type=ConceptType.DISEASE
        )
        assert concept.primary_id == "TEST:001"
        assert concept.primary_label == "Test Concept"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.confidence_score == 0.0

    def test_add_identifier(self):
        """Test add_identifier method."""
        concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test")
        concept.add_identifier(KnowledgeSource.BIOPORTAL, "BP:001", "Test BP")
        assert len(concept.identifiers) == 1
        assert concept.identifiers[0].source == KnowledgeSource.BIOPORTAL

    def test_has_source(self):
        """Test has_source method."""
        concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test")
        concept.add_identifier(KnowledgeSource.BIOPORTAL, "BP:001", "Test BP")
        assert concept.has_source(KnowledgeSource.BIOPORTAL)
        assert not concept.has_source(KnowledgeSource.OLS)

    def test_merge_with(self):
        """Test merge_with method."""
        concept1 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test", confidence_score=0.8
        )
        concept2 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test", confidence_score=0.6
        )
        concept2.synonyms.append("Alias")

        merged = concept1.merge_with(concept2)
        assert merged.confidence_score == 0.8  # Higher confidence
        assert "Alias" in merged.synonyms


class TestLookupResult:
    """Tests for LookupResult."""

    def test_lookup_result_creation(self):
        """Test LookupResult creation."""
        result = LookupResult(query="test query")
        assert result.query == "test query"
        assert result.total_found == 0
        assert len(result.concepts) == 0

    def test_add_concepts(self):
        """Test add_concepts method."""
        result = LookupResult(query="test")
        concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test")
        result.add_concepts([concept], KnowledgeSource.BIOPORTAL)
        assert result.total_found == 1
        assert KnowledgeSource.BIOPORTAL in result.sources_succeeded

    def test_add_error(self):
        """Test add_error method."""
        result = LookupResult(query="test")
        result.add_error(KnowledgeSource.BIOPORTAL, "Network error")
        assert KnowledgeSource.BIOPORTAL in result.errors
        assert KnowledgeSource.BIOPORTAL in result.sources_failed

    def test_get_best_matches(self):
        """Test get_best_matches method."""
        result = LookupResult(query="test")
        concept1 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test1", confidence_score=0.5
        )
        concept2 = UnifiedConcept(
            primary_id="TEST:002", primary_label="Test2", confidence_score=0.8
        )
        result.concepts = [concept1, concept2]
        best = result.get_best_matches(1)
        assert len(best) == 1
        assert best[0].confidence_score == 0.8


class TestLookupConfig:
    """Tests for LookupConfig."""

    def test_lookup_config_creation(self):
        """Test LookupConfig creation."""
        config = LookupConfig()
        assert config.max_results_per_source == 20
        assert config.enable_deduplication == True

    def test_lookup_config_with_all_sources(self):
        """Test with_all_sources class method."""
        config = LookupConfig.with_all_sources()
        assert len(config.enabled_sources) > 0

    def test_is_source_enabled(self):
        """Test is_source_enabled method."""
        config = LookupConfig(enabled_sources=[KnowledgeSource.BIOPORTAL])
        assert config.is_source_enabled(KnowledgeSource.BIOPORTAL)
        assert not config.is_source_enabled(KnowledgeSource.OLS)

    def test_get_api_key(self):
        """Test get_api_key method."""
        config = LookupConfig(api_keys={"bioportal": "test_key"})
        assert config.get_api_key("bioportal") == "test_key"


class TestEnums:
    """Tests for enums."""

    def test_concept_type_values(self):
        """Test ConceptType enum values."""
        assert ConceptType.DISEASE.value == "disease"
        assert ConceptType.GENE.value == "gene"

    def test_knowledge_source_values(self):
        """Test KnowledgeSource enum values."""
        assert KnowledgeSource.BIOPORTAL.value == "bioportal"
        assert KnowledgeSource.OLS.value == "ols"
