"""
Unit tests for validation_models module.
"""

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.validation_models import (
    convert_generated_concept_identifier,
    convert_generated_concept_mapping,
    convert_generated_lookup_config,
    convert_generated_lookup_result,
    convert_generated_unified_concept,
)


def _make_gen_identifier(source="CHEMBL", identifier="CHEMBL1", label="Test", url=None):
    from knowledge_lookup.generated_models.biomedical_knowledge_models import (
        ConceptIdentifier as GenCI,
    )
    return GenCI(source=source, identifier=identifier, label=label, url=url)


def _make_gen_mapping(from_id="CHEMBL1", to_id="PUBCHEM2", mapping_type="exact", confidence=1.0, source="test"):
    from knowledge_lookup.generated_models.biomedical_knowledge_models import (
        ConceptMapping as GenCM,
    )
    return GenCM(
        from_concept=_make_gen_identifier("CHEMBL", from_id),
        to_concept=_make_gen_identifier("PUBCHEM", to_id),
        mapping_type=mapping_type,
        confidence=confidence,
        source=source,
    )


def _make_gen_concept(
    primary_id="C1",
    primary_label="Concept1",
    concept_type="DISEASE",
    sources=None,
    identifiers=None,
    mappings=None,
    synonyms=None,
    definitions=None,
    semantic_types=None,
    categories=None,
    parents=None,
    children=None,
    related=None,
    confidence_score=0.9,
):
    from knowledge_lookup.generated_models.biomedical_knowledge_models import (
        UnifiedConcept as GenUC,
    )
    if identifiers is None:
        identifiers = [_make_gen_identifier()]
    if mappings is None:
        mappings = [_make_gen_mapping()]
    kwargs = dict(
        primary_id=primary_id,
        primary_label=primary_label,
        sources=sources,
        identifiers=identifiers,
        mappings=mappings,
        synonyms=synonyms,
        definitions=definitions,
        semantic_types=semantic_types,
        categories=categories,
        parents=parents,
        children=children,
        related=related,
        confidence_score=confidence_score,
    )
    if concept_type is not None:
        kwargs["concept_type"] = concept_type
    return GenUC(**kwargs)


class TestConvertConceptIdentifier:
    def test_basic_conversion(self):
        gen_id = _make_gen_identifier(source="CHEMBL", identifier="CHEMBL25", label="Aspirin")
        result = convert_generated_concept_identifier(gen_id)
        assert result.source == "CHEMBL"
        assert result.identifier == "CHEMBL25"
        assert result.label == "Aspirin"

    def test_with_url(self):
        gen_id = _make_gen_identifier(source="CHEMBL", identifier="C1", label="X", url="http://x.com")
        result = convert_generated_concept_identifier(gen_id)
        assert result.url == "http://x.com"

    def test_enum_source_value(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            KnowledgeSource as GenKS,
        )
        gen_id = _make_gen_identifier(source=GenKS.CHEMBL, identifier="C1")
        result = convert_generated_concept_identifier(gen_id)
        assert result.source == "CHEMBL"

    def test_none_label_and_url(self):
        gen_id = _make_gen_identifier(source="CHEMBL", identifier="C1", label=None, url=None)
        result = convert_generated_concept_identifier(gen_id)
        assert result.label is None
        assert result.url is None


class TestConvertConceptMapping:
    def test_basic_conversion(self):
        gen_map = _make_gen_mapping()
        result = convert_generated_concept_mapping(gen_map)
        assert result.mapping_type == "exact"
        assert result.confidence == 1.0

    def test_none_mapping_type_defaults_to_exact(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            ConceptMapping as GenCM,
        )
        gen_map = GenCM(
            from_concept=_make_gen_identifier(),
            to_concept=_make_gen_identifier("PUBCHEM", "P2"),
            mapping_type=None,
            confidence=None,
            source="src",
        )
        result = convert_generated_concept_mapping(gen_map)
        assert result.mapping_type == "exact"
        assert result.confidence == 1.0

    def test_mapping_source_preserved(self):
        gen_map = _make_gen_mapping(source="test_source")
        result = convert_generated_concept_mapping(gen_map)
        assert result.source == "test_source"


class TestConvertUnifiedConcept:
    def test_basic_conversion(self):
        gen_concept = _make_gen_concept(synonyms=["syn1"], definitions=["def1"], semantic_types=["type1"], categories=["cat1"])
        result = convert_generated_unified_concept(gen_concept)
        assert result.primary_id == "C1"
        assert result.primary_label == "Concept1"
        assert result.concept_type == "DISEASE"
        assert len(result.identifiers) == 1
        assert len(result.mappings) == 1
        assert result.synonyms == ["syn1"]

    def test_concept_type_fallback_to_unknown(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            UnifiedConcept as GenUC,
        )
        gen_concept = GenUC.model_construct(
            primary_id="C1",
            primary_label="X",
            concept_type="NONEXISTENT",
            identifiers=[_make_gen_identifier()],
        )
        result = convert_generated_unified_concept(gen_concept)
        assert result.concept_type == "UNKNOWN"

    def test_concept_type_none(self):
        gen_concept = _make_gen_concept(concept_type=None)
        result = convert_generated_unified_concept(gen_concept)
        assert result.concept_type == "UNKNOWN"

    def test_concept_type_enum_value(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            ConceptType as GenCT,
        )
        gen_concept = _make_gen_concept(concept_type=GenCT.GENE)
        result = convert_generated_unified_concept(gen_concept)
        assert result.concept_type == "GENE"

    def test_sources_from_list(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            KnowledgeSource as GenKS,
        )
        gen_concept = _make_gen_concept(sources=[GenKS.CHEMBL, GenKS.PUBCHEM])
        result = convert_generated_unified_concept(gen_concept)
        source_values = {s for s in result.sources}
        assert "CHEMBL" in source_values
        assert "PUBCHEM" in source_values

    def test_sources_from_identifiers(self):
        gen_concept = _make_gen_concept(sources=None)
        result = convert_generated_unified_concept(gen_concept)
        source_values = {s for s in result.sources}
        assert "CHEMBL" in source_values

    def test_empty_identifiers(self):
        gen_concept = _make_gen_concept(identifiers=[])
        result = convert_generated_unified_concept(gen_concept)
        assert len(result.identifiers) == 0

    def test_empty_optional_fields(self):
        gen_concept = _make_gen_concept(
            synonyms=[], definitions=[], semantic_types=[],
            categories=[], parents=[], children=[], related=[],
        )
        result = convert_generated_unified_concept(gen_concept)
        assert result.synonyms == []
        assert result.definitions == []
        assert result.semantic_types == []
        assert result.categories == []
        assert result.parents == []
        assert result.children == []
        assert result.related == []

    def test_sources_enum_with_value_attr(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            KnowledgeSource as GenKS,
        )
        gen_concept = _make_gen_concept(sources=[GenKS.UNIPROT])
        result = convert_generated_unified_concept(gen_concept)
        source_values = {s for s in result.sources}
        assert "UNIPROT" in source_values

    def test_identifiers_with_enum_source(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            KnowledgeSource as GenKS,
        )
        gen_id = _make_gen_identifier(source=GenKS.PUBCHEM, identifier="P1")
        gen_concept = _make_gen_concept(identifiers=[gen_id])
        result = convert_generated_unified_concept(gen_concept)
        assert result.identifiers[0].source == "PUBCHEM"

    def test_no_identifiers_and_no_sources(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            UnifiedConcept as GenUC,
        )
        gen_concept = GenUC.model_construct(
            primary_id="X1",
            primary_label="X",
            concept_type="DRUG",
            identifiers=None,
            sources=None,
        )
        result = convert_generated_unified_concept(gen_concept)
        assert len(result.sources) == 0

    def test_none_optional_fields(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            UnifiedConcept as GenUC,
        )
        gen_concept = GenUC.model_construct(
            primary_id="X1",
            primary_label="X",
            concept_type="DISEASE",
            identifiers=[_make_gen_identifier()],
            synonyms=None,
            definitions=None,
            semantic_types=None,
            categories=None,
            parents=None,
            children=None,
            related=None,
        )
        result = convert_generated_unified_concept(gen_concept)
        assert result.synonyms == []
        assert result.definitions == []
        assert result.semantic_types == []
        assert result.categories == []
        assert result.parents == []
        assert result.children == []
        assert result.related == []

    def test_confidence_score_none(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            UnifiedConcept as GenUC,
        )
        gen_concept = GenUC.model_construct(
            primary_id="X1",
            primary_label="X",
            confidence_score=None,
        )
        result = convert_generated_unified_concept(gen_concept)
        assert result.confidence_score == 0.0

    def test_last_updated_preserved(self):
        from datetime import datetime
        gen_concept = _make_gen_concept()
        gen_concept.last_updated = datetime(2024, 1, 1)
        result = convert_generated_unified_concept(gen_concept)
        assert result.last_updated == datetime(2024, 1, 1)


class TestConvertLookupResult:
    def test_basic_conversion(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupResult as GenLR,
        )
        gen_result = GenLR(
            query="test",
            concepts=[_make_gen_concept()],
            total_found=1,
            sources_queried=["CHEMBL"],
            sources_succeeded=["CHEMBL"],
            sources_failed=[],
            execution_time=0.5,
        )
        result = convert_generated_lookup_result(gen_result)
        assert result.query == "test"
        assert len(result.concepts) == 1
        assert result.execution_time == 0.5
        assert result.total_found == 1

    def test_empty_sources(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupResult as GenLR,
        )
        gen_result = GenLR(query="test", concepts=None, sources_queried=None)
        result = convert_generated_lookup_result(gen_result)
        assert len(result.concepts) == 0
        assert result.total_found == 0

    def test_sources_with_enum_value(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            KnowledgeSource as GenKS,
        )
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupResult as GenLR,
        )
        gen_result = GenLR(
            query="test",
            sources_queried=[GenKS.OLS],
            sources_succeeded=[GenKS.OLS],
            sources_failed=[],
        )
        result = convert_generated_lookup_result(gen_result)
        queried_values = [s for s in result.sources_queried]
        assert "OLS" in queried_values

    def test_failed_sources(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupResult as GenLR,
        )
        gen_result = GenLR(
            query="test",
            sources_queried=["CHEMBL"],
            sources_succeeded=[],
            sources_failed=["CHEMBL"],
        )
        result = convert_generated_lookup_result(gen_result)
        failed_values = [s for s in result.sources_failed]
        assert "CHEMBL" in failed_values

    def test_execution_time_none(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupResult as GenLR,
        )
        gen_result = GenLR(query="test", execution_time=None)
        result = convert_generated_lookup_result(gen_result)
        assert result.execution_time == 0.0


class TestConvertLookupConfig:
    def test_basic_conversion(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC(
            enabled_sources=["CHEMBL"],
            max_results_per_source=50,
            timeout_per_source=10.0,
        )
        result = convert_generated_lookup_config(gen_config)
        assert result.max_results_per_source == 50
        assert result.timeout_per_source == 10.0

    def test_empty_config(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC()
        result = convert_generated_lookup_config(gen_config)
        assert result.max_results_per_source == 20
        assert result.timeout_per_source == 30.0
        assert result.parallel_queries is True
        assert result.enable_deduplication is True

    def test_concept_types_normalization(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            ConceptType as GenCT,
        )
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC(concept_types=[GenCT.DISEASE])
        result = convert_generated_lookup_config(gen_config)
        assert result.concept_types is not None
        type_values = [t for t in result.concept_types]
        assert "DISEASE" in type_values

    def test_no_concept_types(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC(concept_types=None)
        result = convert_generated_lookup_config(gen_config)
        assert result.concept_types is None

    def test_enabled_sources_enum(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            KnowledgeSource as GenKS,
        )
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC(enabled_sources=[GenKS.UNIPROT])
        result = convert_generated_lookup_config(gen_config)
        source_values = [s for s in result.enabled_sources]
        assert "UNIPROT" in source_values

    def test_concept_types_none_value(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC(concept_types=None)
        result = convert_generated_lookup_config(gen_config)
        assert result.concept_types is None

    def test_similarity_threshold(self):
        from knowledge_lookup.generated_models.biomedical_knowledge_models import (
            LookupConfig as GenLC,
        )
        gen_config = GenLC(similarity_threshold=0.9)
        result = convert_generated_lookup_config(gen_config)
        assert result.similarity_threshold == 0.9
