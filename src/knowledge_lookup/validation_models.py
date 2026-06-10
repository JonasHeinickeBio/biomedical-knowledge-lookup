"""
Adapter Response Validation Models

Validation models for API responses from knowledge sources.
Uses generated Pydantic models for strict validation with
conversion methods to existing dataclass models.
"""

from typing import Any

from src.knowledge_lookup.generated_models.biomedical_knowledge_models import (
    UnifiedConcept as GeneratedUnifiedConcept,
    ConceptIdentifier as GeneratedConceptIdentifier,
    ConceptMapping as GeneratedConceptMapping,
    LookupResult as GeneratedLookupResult,
    LookupConfig as GeneratedLookupConfig,
    SourceAnnotation as GeneratedSourceAnnotation,
    ConceptAgreement as GeneratedConceptAgreement,
    MultiSourceAnnotationResult as GeneratedMultiSourceAnnotationResult,
)
from src.knowledge_lookup.models import (
    UnifiedConcept,
    ConceptIdentifier,
    ConceptMapping,
    LookupResult,
    LookupConfig,
    ConceptType,
    KnowledgeSource,
)


def _convert_generated_concept_identifier(
    gen_id: GeneratedConceptIdentifier,
) -> ConceptIdentifier:
    """Convert a generated ConceptIdentifier to the existing model."""
    # Handle both enum and string formats
    source_value = gen_id.source.value if hasattr(gen_id.source, 'value') else gen_id.source
    # Convert to lowercase to match existing KnowledgeSource enum values
    if isinstance(source_value, str):
        source_value = source_value.lower()
    return ConceptIdentifier(
        source=KnowledgeSource(source_value),
        identifier=gen_id.identifier,
        label=gen_id.label,
        url=gen_id.url,
    )


def _convert_generated_concept_mapping(
    gen_mapping: GeneratedConceptMapping,
) -> ConceptMapping:
    """Convert a generated ConceptMapping to the existing model."""
    return ConceptMapping(
        from_concept=_convert_generated_concept_identifier(gen_mapping.from_concept),
        to_concept=_convert_generated_concept_identifier(gen_mapping.to_concept),
        mapping_type=gen_mapping.mapping_type or "exact",
        confidence=gen_mapping.confidence or 1.0,
        source=gen_mapping.source,
    )


def _convert_generated_unified_concept(
    gen_concept: GeneratedUnifiedConcept,
) -> UnifiedConcept:
    """Convert a generated UnifiedConcept to the existing model."""
    # Map concept type - generated uses string values (uppercase), existing uses lowercase
    concept_type_value = gen_concept.concept_type
    if concept_type_value:
        # Handle both enum and string formats
        if hasattr(concept_type_value, 'value'):
            concept_type_str = concept_type_value.value
        else:
            concept_type_str = concept_type_value
        # Convert to lowercase to match existing ConceptType enum values
        if isinstance(concept_type_str, str):
            concept_type_str = concept_type_str.lower()
        try:
            concept_type = ConceptType(concept_type_str)
        except ValueError:
            concept_type = ConceptType.UNKNOWN
    else:
        concept_type = ConceptType.UNKNOWN

    # Collect sources from identifiers if sources list is empty
    converted_sources = set()
    if gen_concept.sources:
        converted_sources = set(KnowledgeSource(s.value.lower() if hasattr(s, 'value') else s.lower()) for s in gen_concept.sources)
    else:
        # Extract sources from identifiers
        for id in gen_concept.identifiers or []:
            source_value = id.source.value if hasattr(id.source, 'value') else id.source
            if isinstance(source_value, str):
                source_value = source_value.lower()
            converted_sources.add(KnowledgeSource(source_value))
    
    return UnifiedConcept(
        primary_id=gen_concept.primary_id,
        primary_label=gen_concept.primary_label,
        concept_type=concept_type,
        identifiers=[_convert_generated_concept_identifier(id) for id in gen_concept.identifiers or []],
        mappings=[_convert_generated_concept_mapping(m) for m in gen_concept.mappings or []],
        labels={},
        synonyms=gen_concept.synonyms or [],
        definitions=gen_concept.definitions or [],
        semantic_types=gen_concept.semantic_types or [],
        categories=gen_concept.categories or [],
        parents=gen_concept.parents or [],
        children=gen_concept.children or [],
        related=gen_concept.related or [],
        sources=converted_sources,
        confidence_score=gen_concept.confidence_score or 0.0,
        last_updated=gen_concept.last_updated,
    )


def _convert_generated_lookup_result(
    gen_result: GeneratedLookupResult,
) -> LookupResult:
    """Convert a generated LookupResult to the existing model."""
    # Handle both enum and string formats for sources
    def _normalize_source(s):
        source_value = s.value if hasattr(s, 'value') else s
        if isinstance(source_value, str):
            source_value = source_value.lower()
        return KnowledgeSource(source_value)
    
    return LookupResult(
        query=gen_result.query,
        concepts=[_convert_generated_unified_concept(c) for c in gen_result.concepts or []],
        total_found=gen_result.total_found or 0,
        sources_queried=[_normalize_source(s) for s in (gen_result.sources_queried or [])],
        sources_succeeded=[_normalize_source(s) for s in (gen_result.sources_succeeded or [])],
        sources_failed=[_normalize_source(s) for s in (gen_result.sources_failed or [])],
        execution_time=gen_result.execution_time or 0.0,
        errors={},
    )


def _convert_generated_lookup_config(
    gen_config: GeneratedLookupConfig,
) -> LookupConfig:
    """Convert a generated LookupConfig to the existing model."""
    def _normalize_source(s):
        source_value = s.value if hasattr(s, 'value') else s
        if isinstance(source_value, str):
            source_value = source_value.lower()
        return KnowledgeSource(source_value)
    
    def _normalize_concept_type(t):
        type_value = t.value if hasattr(t, 'value') else t
        if isinstance(type_value, str):
            type_value = type_value.lower()
        return ConceptType(type_value)
    
    return LookupConfig(
        enabled_sources=[_normalize_source(s) for s in (gen_config.enabled_sources or [])],
        max_results_per_source=gen_config.max_results_per_source or 20,
        timeout_per_source=gen_config.timeout_per_source or 30.0,
        parallel_queries=gen_config.parallel_queries or True,
        min_confidence_threshold=gen_config.min_confidence_threshold or 0.0,
        preferred_languages=gen_config.preferred_languages or ["en"],
        concept_types=[_normalize_concept_type(t) for t in (gen_config.concept_types or [])] if gen_config.concept_types else None,
        rate_limits={},
        enable_deduplication=gen_config.enable_deduplication or True,
        similarity_threshold=gen_config.similarity_threshold or 0.8,
        merge_similar_concepts=gen_config.merge_similar_concepts or True,
        enable_ontology_mapping=gen_config.enable_ontology_mapping or True,
        api_keys={},
    )


# Re-export the generated models for convenience
__all__ = [
    # Generated Pydantic models
    "GeneratedUnifiedConcept",
    "GeneratedConceptIdentifier",
    "GeneratedConceptMapping",
    "GeneratedLookupResult",
    "GeneratedLookupConfig",
    "GeneratedSourceAnnotation",
    "GeneratedConceptAgreement",
    "GeneratedMultiSourceAnnotationResult",
    # Conversion functions
    "convert_generated_concept_identifier",
    "convert_generated_concept_mapping",
    "convert_generated_unified_concept",
    "convert_generated_lookup_result",
    "convert_generated_lookup_config",
]

# Export with proper function names
convert_generated_concept_identifier = _convert_generated_concept_identifier
convert_generated_concept_mapping = _convert_generated_concept_mapping
convert_generated_unified_concept = _convert_generated_unified_concept
convert_generated_lookup_result = _convert_generated_lookup_result
convert_generated_lookup_config = _convert_generated_lookup_config
