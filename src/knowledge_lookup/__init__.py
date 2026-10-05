"""
Knowledge Lookup Package Initialization

Central lookup system for biological concept integration across multiple knowledge sources.

Public names are resolved lazily (PEP 562): ``import knowledge_lookup`` loads nothing
beyond the version metadata, and ``knowledge_lookup.CentralKnowledgeLookup`` (or
``from knowledge_lookup import OLSAdapter``) imports only the submodule that
defines it. In particular no adapter module, and none of the client libraries they
wrap, is imported until it is used, so an unreachable service cannot break the
package import.
"""

import importlib as _importlib
import importlib.metadata as _metadata
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # real imports for type checkers and IDEs only
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

_ADAPTER_EXPORTS = (
    "BioLinkerAdapter",
    "BioOntologyAdapter",
    "BioPortalAdapter",
    "DBpediaAdapter",
    "DisGeNETAdapter",
    "DrugBankAdapter",
    "EBIOLSAdapter",
    "EnsemblAdapter",
    "EUtilsAdapter",
    "GeneOntologyAdapter",
    "HPOAdapter",
    "KEGGAdapter",
    "MondoAdapter",
    "OBOFoundryAdapter",
    "OLSAdapter",
    "OpenTargetsAdapter",
    "OxOAdapter",
    "PubChemAdapter",
    "QuickGOAdapter",
    "ReactomeAdapter",
    "TytoAdapter",
    "UMLSAdapter",
    "UniChemAdapter",
    "UniProtAdapter",
    "WikidataAdapter",
    "ZoomaAdapter",
)

# public name -> submodule (relative to this package) that defines it
_LAZY_EXPORTS: dict[str, str] = {
    "ADAPTER_CLASSES": "adapters",
    **dict.fromkeys(_ADAPTER_EXPORTS, "adapters"),
    "KnowledgeLookupCache": "cache",
    "get_cache": "cache",
    "init_cache": "cache",
    "CentralKnowledgeLookup": "core",
    "MultiSourceAnnotator": "core",
    "create_knowledge_lookup": "core",
    "AnnotationConfidence": "core.multi_source_annotator",
    "ConceptAgreement": "core.multi_source_annotator",
    "MultiSourceAnnotationResult": "core.multi_source_annotator",
    "SourceAnnotation": "core.multi_source_annotator",
    "ConceptIdentifier": "models",
    "ConceptMapping": "models",
    "ConceptType": "models",
    "KnowledgeSource": "models",
    "LookupConfig": "models",
    "LookupResult": "models",
    "UnifiedConcept": "models",
}


def __getattr__(name: str) -> Any:
    """Import a public name, or a submodule (``knowledge_lookup.adapters``), on first use."""
    if name in _LAZY_EXPORTS:
        value = getattr(_importlib.import_module(f".{_LAZY_EXPORTS[name]}", __name__), name)
        globals()[name] = value  # cache: later lookups skip __getattr__
        return value
    if not name.startswith("_"):
        try:
            return _importlib.import_module(f".{name}", __name__)
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{name}":
                raise  # the submodule exists but one of its own imports is missing
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), *_LAZY_EXPORTS})


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
