"""
Knowledge Lookup Package Initialization

Central lookup system for biological concept integration across multiple knowledge sources.
"""

import importlib.metadata as _metadata

from .adapters import (
    ADAPTER_CLASSES,
    BioLinkerAdapter,
    BioOntologyAdapter,
    BioPortalAdapter,
    DBpediaAdapter,
    DisGeNETAdapter,
    DrugBankAdapter,
    EBIOLSAdapter,
    EnsemblAdapter,
    EUtilsAdapter,
    GeneOntologyAdapter,
    HPOAdapter,
    KEGGAdapter,
    MondoAdapter,
    OBOFoundryAdapter,
    OLSAdapter,
    OpenTargetsAdapter,
    OxOAdapter,
    PubChemAdapter,
    QuickGOAdapter,
    ReactomeAdapter,
    TytoAdapter,
    UMLSAdapter,
    UniChemAdapter,
    UniProtAdapter,
    WikidataAdapter,
    ZoomaAdapter,
)
from .cache import KnowledgeLookupCache, get_cache, init_cache
from .core import (
    CentralKnowledgeLookup,
    MultiSourceAnnotator,
    create_knowledge_lookup,
)
from .core.multi_source_annotator import (
    AnnotationConfidence,
    ConceptAgreement,
    MultiSourceAnnotationResult,
    SourceAnnotation,
)
from .models import (
    ConceptIdentifier,
    ConceptMapping,
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)

# Make key classes available at package level
__all__ = [
    # Main classes
    "CentralKnowledgeLookup",
    "create_knowledge_lookup",
    "MultiSourceAnnotator",
    # Caching system
    "KnowledgeLookupCache",
    "get_cache",
    "init_cache",
    # Data models
    "KnowledgeSource",
    "ConceptType",
    "ConceptIdentifier",
    "ConceptMapping",
    "UnifiedConcept",
    "LookupResult",
    "LookupConfig",
    # Multi-source annotation
    "AnnotationConfidence",
    "SourceAnnotation",
    "ConceptAgreement",
    "MultiSourceAnnotationResult",
    # Adapters
    "ADAPTER_CLASSES",
    "UMLSAdapter",
    "UniChemAdapter",
    "BioPortalAdapter",
    "OLSAdapter",
    "WikidataAdapter",
    "BioLinkerAdapter",
    "DBpediaAdapter",
    "OxOAdapter",
    "BioOntologyAdapter",
    "MondoAdapter",
    "UniProtAdapter",
    "DisGeNETAdapter",
    "OpenTargetsAdapter",
    "ReactomeAdapter",
    "PubChemAdapter",
    "DrugBankAdapter",
    "GeneOntologyAdapter",
    "HPOAdapter",
    "OBOFoundryAdapter",
    "EBIOLSAdapter",
    "EnsemblAdapter",
    "KEGGAdapter",
    "QuickGOAdapter",
    "ZoomaAdapter",
    "TytoAdapter",
    "EUtilsAdapter",
]

# Package metadata
# poetry-dynamic-versioning rewrites the next line with the real version at build time
# ([tool.poetry-dynamic-versioning.substitution] in pyproject.toml). Keep it the only line
# that starts with `__version__ = "`, or the substitution would hit more than one line.
__version__ = "0.0.0"
__author__ = "AID-PAIS Knowledge Graph Team"
__description__ = "Unified biological concept lookup across multiple knowledge sources"


def _resolve_version(placeholder: str) -> str:
    """Return the build-substituted version, else the installed distribution's version.

    A source checkout or editable install still carries the "0.0.0" placeholder, so fall
    back to the installed package metadata; keep the placeholder if nothing is installed.
    """
    if placeholder != "0.0.0":
        return placeholder
    try:
        return _metadata.version("biomedical-knowledge-lookup")
    except _metadata.PackageNotFoundError:
        return placeholder


__version__ = _resolve_version(__version__)
