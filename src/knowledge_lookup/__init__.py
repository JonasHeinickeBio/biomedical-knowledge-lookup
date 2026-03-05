"""
Knowledge Lookup Package Initialization

Central lookup system for biological concept integration across multiple knowledge sources.
"""

from .adapters.eutils_adapter import EUtilsAdapter
from .adapters.kegg_adapter import KEGGAdapter
from .adapters.quickgo_adapter import QuickGOAdapter
from .benchmarks import (
    Benchmarker,
    BenchmarkRegistry,
    BenchmarkResult,
    BenchmarkSuite,
    benchmark,
    generate_report,
)
from .cache import (
    CacheBackendType,
    KnowledgeLookupCache,
    RedisCacheBackend,
    create_cache_backend,
    get_cache,
    init_cache,
)
from .central_lookup import CentralKnowledgeLookup
from .models import (
    ConceptIdentifier,
    ConceptMapping,
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    UnifiedConcept,
)
from .multi_source_annotator import (
    AnnotationConfidence,
    ConceptAgreement,
    MultiSourceAnnotationResult,
    MultiSourceAnnotator,
    SourceAnnotation,
)
from .oxo_adapter import OxOAdapter

# Make key classes available at package level
__all__ = [
    # Main classes
    "CentralKnowledgeLookup",
    "MultiSourceAnnotator",
    # Caching system
    "KnowledgeLookupCache",
    "CacheBackendType",
    "RedisCacheBackend",
    "create_cache_backend",
    "get_cache",
    "init_cache",
    # Benchmarking
    "Benchmarker",
    "BenchmarkRegistry",
    "BenchmarkResult",
    "BenchmarkSuite",
    "benchmark",
    "generate_report",
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
    "OxOAdapter",
    "KEGGAdapter",
    "QuickGOAdapter",
    "EUtilsAdapter",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "AID-PAIS Knowledge Graph Team"
__description__ = "Unified biological concept lookup across multiple knowledge sources"
