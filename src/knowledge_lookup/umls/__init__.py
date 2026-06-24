"""
UMLS Ecosystem Modules

Subpackage for UMLS-specific functionality beyond the basic adapter.
Provides local caching, RDF/SPARQL export, batch processing, LLM-augmented
normalization, and concept embedding similarity.

Modules
-------
cache       — SQLite + FTS5 local concept cache (1–5ms lookups)
rdf         — RDF/Turtle/JSON-LD export + async SPARQL query client
batch       — CSV/JSON/txt batch concept extraction pipeline
llm         — LLM-augmented concept normalization (OpenAI/Anthropic/HuggingFace)
embeddings  — Semantic similarity via sentence-transformers/fastText/OpenAI
"""

from .batch import BatchProcessor, BatchResult
from .cache import PartialMatcher, UMLSCache
from .embeddings import ConceptEmbedder
from .llm import LLMNormalizer
from .rdf import (
    SPARQL_ENDPOINTS,
    SparqlEndpoint,
    concept_to_graph,
    concepts_to_graph,
    concepts_to_jsonld,
    concepts_to_turtle,
    save_concepts_to_file,
)

__all__ = [
    "BatchProcessor",
    "BatchResult",
    "UMLSCache",
    "PartialMatcher",
    "ConceptEmbedder",
    "LLMNormalizer",
    "SparqlEndpoint",
    "concept_to_graph",
    "concepts_to_graph",
    "concepts_to_jsonld",
    "concepts_to_turtle",
    "save_concepts_to_file",
    "SPARQL_ENDPOINTS",
]
