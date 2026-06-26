"""
Unit tests for models.
"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.models import (
    ConceptIdentifier,
    ConceptMapping,
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)


class TestUnifiedConcept:
    def test_unified_concept_creation(self):
        concept = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test Concept", concept_type=ConceptType.DISEASE
        )
        assert concept.primary_id == "TEST:001"
        assert concept.primary_label == "Test Concept"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.confidence_score == 0.0

    def test_add_identifier(self):
        concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test")
        concept.add_identifier(KnowledgeSource.BIOPORTAL, "BP:001", "Test BP")
        assert len(concept.identifiers) == 1
        assert concept.identifiers[0].source == KnowledgeSource.BIOPORTAL

    def test_has_source(self):
        concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test")
        concept.add_identifier(KnowledgeSource.BIOPORTAL, "BP:001", "Test BP")
        assert concept.has_source(KnowledgeSource.BIOPORTAL)
        assert not concept.has_source(KnowledgeSource.OLS)

    def test_merge_with(self):
        concept1 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test", confidence_score=0.8
        )
        concept2 = UnifiedConcept(
            primary_id="TEST:001", primary_label="Test", confidence_score=0.6
        )
        concept2.synonyms.append("Alias")
        merged = concept1.merge_with(concept2)
        assert merged.confidence_score == 0.8
        assert "Alias" in merged.synonyms


class TestLookupResult:
    def test_lookup_result_creation(self):
        result = LookupResult(query="test query")
        assert result.query == "test query"
        assert result.total_found == 0
        assert len(result.concepts) == 0

    def test_add_concepts(self):
        result = LookupResult(query="test")
        concept = UnifiedConcept(primary_id="TEST:001", primary_label="Test")
        result.add_concepts([concept], KnowledgeSource.BIOPORTAL)
        assert result.total_found == 1
        assert KnowledgeSource.BIOPORTAL in result.sources_succeeded

    def test_add_error(self):
        result = LookupResult(query="test")
        result.add_error(KnowledgeSource.BIOPORTAL, "Network error")
        assert KnowledgeSource.BIOPORTAL in result.errors
        assert KnowledgeSource.BIOPORTAL in result.sources_failed

    def test_get_best_matches(self):
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
    def test_lookup_config_creation(self):
        config = LookupConfig()
        assert config.max_results_per_source == 20
        assert config.enable_deduplication is True

    def test_lookup_config_with_all_sources(self):
        config = LookupConfig.with_all_sources()
        assert len(config.enabled_sources) > 0

    def test_is_source_enabled(self):
        config = LookupConfig(enabled_sources=[KnowledgeSource.BIOPORTAL])
        assert config.is_source_enabled(KnowledgeSource.BIOPORTAL)
        assert not config.is_source_enabled(KnowledgeSource.OLS)

    def test_get_api_key(self):
        config = LookupConfig(api_keys={"bioportal": "test_key"})
        assert config.get_api_key("bioportal") == "test_key"


class TestEnums:
    def test_concept_type_values(self):
        assert ConceptType.DISEASE.value == "DISEASE"
        assert ConceptType.GENE.value == "GENE"

    def test_knowledge_source_values(self):
        assert KnowledgeSource.BIOPORTAL.value == "BIOPORTAL"
        assert KnowledgeSource.OLS.value == "OLS"


class TestModelsExtended:
    def test_concept_identifier_str(self):
        cid = ConceptIdentifier(source=KnowledgeSource.CHEMBL, identifier="CHEMBL123")
        assert str(cid) == "chembl:CHEMBL123"

    def test_concept_identifier_str_with_label(self):
        cid = ConceptIdentifier(source=KnowledgeSource.OLS, identifier="DOID:1", label="Disease")
        assert str(cid) == "ols:DOID:1"

    def test_unified_concept_add_mapping(self):
        concept = UnifiedConcept(
            primary_id="C1", primary_label="Test", concept_type=ConceptType.DISEASE
        )
        concept.add_mapping(
            target_source=KnowledgeSource.CHEMBL,
            target_id="CHEMBL123",
            mapping_type="narrow",
            confidence=0.9,
            mapping_source="test_source",
        )
        assert len(concept.mappings) == 1
        m = concept.mappings[0]
        assert m.from_concept.identifier == "C1"
        assert m.to_concept.source == KnowledgeSource.CHEMBL
        assert m.to_concept.identifier == "CHEMBL123"
        assert m.mapping_type == "narrow"
        assert m.confidence == 0.9
        assert m.source == "test_source"

    def test_unified_concept_add_mapping_defaults(self):
        concept = UnifiedConcept(primary_id="C1", primary_label="Test")
        concept.add_mapping(target_source=KnowledgeSource.OLS, target_id="DOID:1")
        m = concept.mappings[0]
        assert m.mapping_type == "exact"
        assert m.confidence == 1.0
        assert m.source is None

    def test_unified_concept_get_identifier(self):
        concept = UnifiedConcept(primary_id="C1", primary_label="Test")
        concept.add_identifier(KnowledgeSource.CHEMBL, "CHEMBL1")
        concept.add_identifier(KnowledgeSource.PUBCHEM, "PUB1")
        result = concept.get_identifier(KnowledgeSource.CHEMBL)
        assert result is not None
        assert result.identifier == "CHEMBL1"

    def test_unified_concept_get_identifier_not_found(self):
        concept = UnifiedConcept(primary_id="C1", primary_label="Test")
        result = concept.get_identifier(KnowledgeSource.CHEMBL)
        assert result is None

    def test_unified_concept_merge_with_duplicate_identifiers(self):
        c1 = UnifiedConcept(primary_id="C1", primary_label="Test", confidence_score=0.9)
        c1.add_identifier(KnowledgeSource.CHEMBL, "CHEMBL1")
        c2 = UnifiedConcept(primary_id="C1", primary_label="Test", confidence_score=0.7)
        c2.add_identifier(KnowledgeSource.CHEMBL, "CHEMBL1")
        c2.add_identifier(KnowledgeSource.PUBCHEM, "PUB1")
        merged = c1.merge_with(c2)
        chembl_ids = [i for i in merged.identifiers if i.source == KnowledgeSource.CHEMBL]
        assert len(chembl_ids) == 1
        assert any(i.source == KnowledgeSource.PUBCHEM for i in merged.identifiers)

    def test_unified_concept_merge_other_is_base(self):
        c1 = UnifiedConcept(primary_id="C1", primary_label="Low", confidence_score=0.3)
        c2 = UnifiedConcept(primary_id="C1", primary_label="High", confidence_score=0.9)
        c2.definitions = ["High def"]
        merged = c1.merge_with(c2)
        assert merged.primary_label == "High"
        assert "High def" in merged.definitions

    def test_lookup_result_group_by_source(self):
        result = LookupResult(query="test")
        c1 = UnifiedConcept(primary_id="C1", primary_label="A")
        c1.sources = {KnowledgeSource.CHEMBL, KnowledgeSource.PUBCHEM}
        c2 = UnifiedConcept(primary_id="C2", primary_label="B")
        c2.sources = {KnowledgeSource.CHEMBL}
        result.concepts = [c1, c2]
        grouped = result.group_by_source()
        assert KnowledgeSource.CHEMBL in grouped
        assert len(grouped[KnowledgeSource.CHEMBL]) == 2
        assert KnowledgeSource.PUBCHEM in grouped
        assert len(grouped[KnowledgeSource.PUBCHEM]) == 1

    def test_lookup_result_group_by_source_empty(self):
        result = LookupResult(query="test")
        grouped = result.group_by_source()
        assert len(grouped) == 0

    def test_lookup_config_get_api_key_from_env(self):
        config = LookupConfig()
        with patch.dict("os.environ", {"CHEMBL_API_KEY": "env_key_123"}):
            result = config.get_api_key("chembl")
            assert result == "env_key_123"

    def test_lookup_config_get_api_key_no_env_no_config(self):
        config = LookupConfig()
        result = config.get_api_key("nonexistent_service_xyz")
        assert result is None

    def test_lookup_config_get_api_key_import_error(self):
        config = LookupConfig()
        with patch.dict("sys.modules", {"dotenv": None}):
            result = config.get_api_key("test_service")
            assert result is None

    def test_concept_identifier_defaults(self):
        cid = ConceptIdentifier(source=KnowledgeSource.OLS, identifier="X")
        assert cid.label is None
        assert cid.url is None

    def test_lookup_result_add_concepts_duplicate_source(self):
        result = LookupResult(query="test")
        c1 = UnifiedConcept(primary_id="C1", primary_label="A")
        c2 = UnifiedConcept(primary_id="C2", primary_label="B")
        result.add_concepts([c1], KnowledgeSource.OLS)
        result.add_concepts([c2], KnowledgeSource.OLS)
        assert result.sources_succeeded.count(KnowledgeSource.OLS) == 1
        assert result.total_found == 2

    def test_lookup_result_add_error_duplicate_source(self):
        result = LookupResult(query="test")
        result.add_error(KnowledgeSource.OLS, "err1")
        result.add_error(KnowledgeSource.OLS, "err2")
        assert result.sources_failed.count(KnowledgeSource.OLS) == 1
        assert result.errors[KnowledgeSource.OLS] == "err2"

    def test_concept_mapping_defaults(self):
        from_c = ConceptIdentifier(source=KnowledgeSource.UMLS, identifier="C1")
        to_c = ConceptIdentifier(source=KnowledgeSource.OLS, identifier="D1")
        cm = ConceptMapping(from_concept=from_c, to_concept=to_c)
        assert cm.mapping_type == "exact"
        assert cm.confidence == 1.0
        assert cm.source is None

    def test_unified_concept_merge_labels(self):
        c1 = UnifiedConcept(primary_id="C1", primary_label="A")
        c1.labels = {"en": "English"}
        c2 = UnifiedConcept(primary_id="C1", primary_label="A")
        c2.labels = {"de": "Deutsch"}
        merged = c1.merge_with(c2)
        assert "en" in merged.labels
        assert "de" in merged.labels

    def test_unified_concept_merge_source_data(self):
        c1 = UnifiedConcept(primary_id="C1", primary_label="A")
        c1.source_data = {KnowledgeSource.OLS: {"k1": "v1"}}
        c2 = UnifiedConcept(primary_id="C1", primary_label="A")
        c2.source_data = {KnowledgeSource.CHEMBL: {"k2": "v2"}}
        merged = c1.merge_with(c2)
        assert KnowledgeSource.OLS in merged.source_data
        assert KnowledgeSource.CHEMBL in merged.source_data
