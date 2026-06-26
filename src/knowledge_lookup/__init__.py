"""
Knowledge Lookup Package Initialization

Central lookup system for biological concept integration across multiple knowledge sources.
"""

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
__version__ = "1.0.0"
__author__ = "AID-PAIS Knowledge Graph Team"
__description__ = "Unified biological concept lookup across multiple knowledge sources"
