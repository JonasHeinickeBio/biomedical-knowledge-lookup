"""
Re-export models from biomedical_knowledge_models for backward compatibility.
"""

from .biomedical_knowledge_models import (
    ConceptAgreement,
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    MultiSourceAnnotationResult,
    SourceAnnotation,
    UnifiedConcept,
)
from .extensions import ConceptIdentifier, ConceptMapping

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
]
