"""
Models package — data models and type definitions.
"""

from .biomedical_knowledge_models import (
    ConceptIdentifier as GeneratedConceptIdentifier,
)
from .biomedical_knowledge_models import (
    ConceptMapping as GeneratedConceptMapping,
)
from .biomedical_knowledge_models import (
    LookupConfig as GeneratedLookupConfig,
)
from .biomedical_knowledge_models import (
    LookupResult as GeneratedLookupResult,
)
from .biomedical_knowledge_models import (
    UnifiedConcept as GeneratedUnifiedConcept,
)

# Backward-compatible wrappers — imported last to avoid circular imports
from .extensions import (
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)
from .models import (
    ConceptAgreement,
    ConceptIdentifier,
    ConceptMapping,
    ConceptType,
    KnowledgeSource,
    MultiSourceAnnotationResult,
    SourceAnnotation,
)
from .validation_models import (
    convert_generated_concept_identifier,
    convert_generated_concept_mapping,
    convert_generated_lookup_config,
    convert_generated_lookup_result,
    convert_generated_unified_concept,
)

__all__ = [
    "ConceptIdentifier",
    "ConceptMapping",
    "ConceptType",
    "KnowledgeSource",
    "LookupConfig",
    "LookupResult",
    "UnifiedConcept",
    "SourceAnnotation",
    "ConceptAgreement",
    "MultiSourceAnnotationResult",
    # Legacy alias exports
    "convert_generated_concept_identifier",
    "convert_generated_concept_mapping",
    "convert_generated_lookup_config",
    "convert_generated_lookup_result",
    "convert_generated_unified_concept",
    "GeneratedConceptIdentifier",
    "GeneratedConceptMapping",
    "GeneratedLookupConfig",
    "GeneratedLookupResult",
    "GeneratedUnifiedConcept",
]
