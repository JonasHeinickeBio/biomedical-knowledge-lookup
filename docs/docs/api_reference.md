# API Reference

This document provides detailed information about the classes and methods available in the Biomedical Knowledge Lookup library.

## Core Classes

### `CentralKnowledgeLookup`

The main entry point for searching concepts and getting details across all available knowledge sources.

- `__init__(config: Optional[LookupConfig] = None)`: Initialize the lookup system.
- `async search_concepts(query: str, sources: Optional[List[KnowledgeSource]] = None, limit: int = 10) -> LookupResult`: Search for concepts.
- `async get_concept_details(concept_id: str, sources: Optional[List[KnowledgeSource]] = None) -> Optional[UnifiedConcept]`: Get detailed information for a specific concept.
- `async get_mappings(concept_id: str, sources: Optional[List[KnowledgeSource]] = None) -> List[ConceptMapping]`: Get cross-reference mappings for a concept.
- `export_to_rdf(result: LookupResult) -> rdflib.Graph`: Export lookup results to an RDF graph.

### `MultiSourceAnnotator`

Advanced annotation platform that uses multiple knowledge sources with consensus analysis.

- `__init__(config: Optional[LookupConfig] = None)`: Initialize the annotator.
- `async annotate_sentence(sentence: str, sources: Optional[List[KnowledgeSource]] = None) -> MultiSourceAnnotationResult`: Annotate a sentence using multiple sources.
- `async annotate_multiple_sentences(sentences: List[str], sources: Optional[List[KnowledgeSource]] = None) -> List[MultiSourceAnnotationResult]`: Annotate multiple sentences.

## Data Models

### `UnifiedConcept`

Standardized concept representation used across all adapters.

- `primary_id: str`: Unique identifier for the concept.
- `primary_label: str`: Preferred label for the concept.
- `concept_type: ConceptType`: Type of the concept (DISEASE, PROTEIN, etc.).
- `synonyms: List[str]`: List of alternative labels.
- `definitions: List[str]`: List of concept definitions.
- `confidence_score: float`: Confidence score for the concept identification.
- `sources: Set[KnowledgeSource]`: Set of sources that identified the concept.

### `LookupResult`

Container for concept lookup results.

- `query: str`: Original search query.
- `concepts: List[UnifiedConcept]`: List of concepts found.
- `execution_time: float`: Time taken for the lookup.
- `sources_queried: List[KnowledgeSource]`: Sources attempted during the lookup.
- `sources_succeeded: List[KnowledgeSource]`: Sources that returned results.

## Enums

### `KnowledgeSource`

Enum representing all supported biomedical knowledge sources (BioPortal, OLS, UMLS, ChEMBL, etc.).

### `ConceptType`

Enum representing different types of biological concepts (DISEASE, PROTEIN, CHEMICAL, GENE, PATHWAY, etc.).

## Utilities

### `KnowledgeLookupCache`

Intelligent caching system for optimizing API performance.

- `get_cache() -> KnowledgeLookupCache`: Get the default cache instance.
- `init_cache(cache_dir: str)`: Initialize the cache with a specific directory.
