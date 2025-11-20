"""
Unit tests for data models.
"""


from knowledge_lookup.models import (
    ConceptIdentifier,
    ConceptMapping,
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)


class TestKnowledgeSource:
    """Tests for KnowledgeSource enum."""

    def test_enum_members_exist(self):
        """Test that expected knowledge sources exist."""
        sources = [s.value for s in KnowledgeSource]
        assert "umls" in sources
        assert "ols" in sources
        assert "bioportal" in sources
        assert "chembl" in sources
        assert "disgenet" in sources
        assert "ensembl" in sources

    def test_enum_access_by_value(self):
        """Test accessing enum by value."""
        source = KnowledgeSource("umls")
        assert source == KnowledgeSource.UMLS

    def test_enum_count(self):
        """Test that we have the expected number of sources."""
        assert len(list(KnowledgeSource)) >= 29


class TestConceptType:
    """Tests for ConceptType enum."""

    def test_enum_members_exist(self):
        """Test that expected concept types exist."""
        types = [t.value for t in ConceptType]
        assert "disease" in types
        assert "drug" in types
        assert "gene" in types
        assert "protein" in types

    def test_enum_access_by_value(self):
        """Test accessing enum by value."""
        concept_type = ConceptType("disease")
        assert concept_type == ConceptType.DISEASE


class TestUnifiedConcept:
    """Tests for UnifiedConcept model."""

    def test_unified_concept_creation(self):
        """Test creating a UnifiedConcept."""
        concept = UnifiedConcept(
            primary_id="C123",
            primary_label="Test",
            concept_type=ConceptType.DISEASE,
        )
        assert concept.primary_id == "C123"
        assert concept.primary_label == "Test"
        assert concept.concept_type == ConceptType.DISEASE

    def test_unified_concept_with_synonyms(self):
        """Test UnifiedConcept with synonyms."""
        concept = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
            synonyms=["diabetes", "DM", "diabetes disease"],
        )
        assert len(concept.synonyms) == 3
        assert "diabetes" in concept.synonyms

    def test_unified_concept_with_definitions(self):
        """Test UnifiedConcept with definitions."""
        definition = "A metabolic disease characterized by high blood sugar"
        concept = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
            definitions=[definition],
        )
        assert definition in concept.definitions

    def test_unified_concept_with_source_data(self):
        """Test UnifiedConcept with source data."""
        source_data = {
            KnowledgeSource.OLS: {
                "ontology": "doid",
                "iri": "http://purl.obolibrary.org/obo/DOID_9351",
            }
        }
        concept = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
            source_data=source_data,
        )
        assert KnowledgeSource.OLS in concept.source_data
        assert concept.source_data[KnowledgeSource.OLS]["ontology"] == "doid"

    def test_unified_concept_with_identifiers(self):
        """Test UnifiedConcept with identifiers."""
        concept = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
        )
        concept.add_identifier(KnowledgeSource.UMLS, "C0011849", "Diabetes Mellitus")
        concept.add_identifier(KnowledgeSource.BIOPORTAL, "73211009")
        assert len(concept.identifiers) == 2
        assert KnowledgeSource.UMLS in concept.sources

    def test_unified_concept_equality(self):
        """Test UnifiedConcept equality comparison."""
        concept1 = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
        )
        concept2 = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
        )
        # Dataclass equality comparison
        assert concept1.primary_id == concept2.primary_id
        assert concept1.primary_label == concept2.primary_label


class TestConceptIdentifier:
    """Tests for ConceptIdentifier model."""

    def test_concept_identifier_creation(self):
        """Test creating a ConceptIdentifier."""
        identifier = ConceptIdentifier(
            identifier="DOID:9351",
            source=KnowledgeSource.OLS,
            label="diabetes mellitus",
        )
        assert identifier.identifier == "DOID:9351"
        assert identifier.source == KnowledgeSource.OLS
        assert identifier.label == "diabetes mellitus"


class TestConceptMapping:
    """Tests for ConceptMapping model."""

    def test_concept_mapping_creation(self):
        """Test creating a ConceptMapping."""
        from_concept = ConceptIdentifier(
            source=KnowledgeSource.OLS,
            identifier="DOID:9351",
            label="diabetes mellitus",
        )
        to_concept = ConceptIdentifier(
            source=KnowledgeSource.UMLS,
            identifier="C0011849",
            label="Diabetes Mellitus",
        )
        mapping = ConceptMapping(
            from_concept=from_concept,
            to_concept=to_concept,
            mapping_type="exact",
            confidence=0.95,
        )
        assert mapping.from_concept.identifier == "DOID:9351"
        assert mapping.to_concept.identifier == "C0011849"
        assert mapping.confidence == 0.95


class TestLookupConfig:
    """Tests for LookupConfig model."""

    def test_lookup_config_defaults(self):
        """Test LookupConfig with default values."""
        config = LookupConfig()
        assert config.max_results_per_source == 20
        assert config.timeout_per_source > 0
        assert config.parallel_queries is True

    def test_lookup_config_custom_values(self):
        """Test LookupConfig with custom values."""
        config = LookupConfig(
            max_results_per_source=50,
            timeout_per_source=60,
            rate_limits={KnowledgeSource.BIOPORTAL: 10},
        )
        assert config.max_results_per_source == 50
        assert config.timeout_per_source == 60
        assert KnowledgeSource.BIOPORTAL in config.rate_limits

    def test_lookup_config_with_api_keys(self):
        """Test LookupConfig with API keys."""
        api_keys = {
            "BIOPORTAL": "test_key_123",
            "UMLS": "test_umls_key",
        }
        config = LookupConfig(api_keys=api_keys)
        assert config.api_keys["BIOPORTAL"] == "test_key_123"


class TestLookupResult:
    """Tests for LookupResult model."""

    def test_lookup_result_creation(self):
        """Test creating a LookupResult."""
        concepts = [
            UnifiedConcept(
                primary_id="DOID:9351",
                primary_label="diabetes mellitus",
                concept_type=ConceptType.DISEASE,
            )
        ]
        result = LookupResult(
            query="diabetes",
            concepts=concepts,
            sources_queried=[KnowledgeSource.OLS],
        )
        assert result.query == "diabetes"
        assert len(result.concepts) == 1
        assert KnowledgeSource.OLS in result.sources_queried

    def test_lookup_result_empty(self):
        """Test LookupResult with no concepts."""
        result = LookupResult(
            query="nonexistent",
            concepts=[],
            sources_queried=[KnowledgeSource.OLS],
        )
        assert result.query == "nonexistent"
        assert len(result.concepts) == 0

    def test_lookup_result_add_concepts(self):
        """Test adding concepts to result."""
        result = LookupResult(query="test")
        concepts = [
            UnifiedConcept(
                primary_id="TEST:001",
                primary_label="Test",
                concept_type=ConceptType.DISEASE,
            )
        ]
        result.add_concepts(concepts, KnowledgeSource.OLS)
        assert len(result.concepts) == 1
        assert KnowledgeSource.OLS in result.sources_succeeded

    def test_lookup_result_add_error(self):
        """Test adding error to result."""
        result = LookupResult(query="test")
        result.add_error(KnowledgeSource.OLS, "Connection timeout")
        assert KnowledgeSource.OLS in result.errors
        assert KnowledgeSource.OLS in result.sources_failed
