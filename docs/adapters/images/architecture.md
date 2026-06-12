# Biomedical Knowledge Lookup System Architecture

This document describes the architecture of the Biomedical Knowledge Lookup system, a unified interface for querying multiple biological knowledge sources.

## Overview

The system provides a centralized lookup mechanism that abstracts away the complexity of multiple knowledge sources (APIs, ontologies, databases) and presents a unified interface for searching, retrieving, and integrating biomedical concepts.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                              CLIENT APPLICATION                                                      │
│  - CLI tools                                                                                                         │
│  - Web applications                                                                                                  │
│  - Research workflows                                                                                                │
│  - Analysis pipelines                                                                                                │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            CentralKnowledgeLookup (Orchestrator)                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  • Manages adapter lifecycle                                                                                   │  │
│  │  • Coordinates parallel/sequential queries                                                                     │  │
│  │  • Applies rate limiting                                                                                       │  │
│  │  • Merges and deduplicates results                                                                             │  │
│  │  • Handles errors and fallbacks                                                                                │  │
│  │  • Provides unified result format                                                                              │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                        │
                    ┌───────────────────────────────────┼───────────────────────────────────┐
                    ▼                                   ▼                                   ▼
┌────────────────────────────────────────┐  ┌────────────────────────────────────────┐  ┌────────────────────────────────────────┐
│             Cache Layer                │  │           Rate Limiter               │  │            Error Handler             │
│                                        │  │                                        │  │                                        │
│  • Redis/Memcached support             │  │  • Per-source rate limiting          │  │  • Graceful degradation              │
│  • Result caching with TTL             │  │  • Configurable limits               │  │  • Retry logic                     │
│  • Session state management            │  │  • Throttling                        │  │  • Fallback mechanisms               │
└────────────────────────────────────────┘  └────────────────────────────────────────┘  └────────────────────────────────────────┘
                                                        │
                                                        │
                    ┌───────────────────────────────────┼──────────────────────────────────────────────────────────────────────┐
                    ▼                                   ▼                                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            KnowledgeSourceAdapter (Interface/Base Class)                                            │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Abstract methods:                                                                                                             │  │
│  │  • get_source() → KnowledgeSource                                                                                              │  │
│  │  • search_concepts(query, limit) → list[UnifiedConcept]                                                                       │  │
│  │  • get_concept_details(concept_id) → UnifiedConcept                                                                            │  │
│  │  • get_rate_limit() → float                                                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                        │                       │                       │                       │                       │                       │
                        ▼                       ▼                       ▼                       ▼                       ▼                       ▼
        ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
        │   OpenTargetsAdapter  │ │    ChEMBLAdapter    │ │     MONDOAdapter    │ │   UniProtAdapter  │ │  DisGeNETAdapter  │ │     UMLSAdapter     │
        │                       │ │                       │ │                     │ │                   │ │                   │ │                     │
        │  • Target-disease     │ │ • Drug-target       │ │ • Human diseases    │ │ • Protein seq     │ │ • Gene-disease    │ │ • Medical concepts  │
        │  • Drug-target        │ │ • Compound properties│ │ • Ontology terms    │ │ • Gene names      │ │ • Associations    │ │ • UMLS concepts     │
        │  • Pathway data       │ │ • Bioactivity       │ │ • HPO mappings      │ │ • Enzymes         │ │ • Risk factors    │ │ • Semantic types    │
        └───────────────────────┘ └───────────────────────┘ └───────────────────────┘ └───────────────────────┘ └───────────────────────┘ └───────────────────────┘
                        │                       │                       │                       │                       │                       │
                        └───────────────────────┴───────────────────────┴───────────────────────┴───────────────────────┴───────────────────────┘
                                                        │
                                                        ▼
                                      ┌───────────────────────────────────────────────────────┐
                                      │           UnifiedConcept Data Structure               │
                                      │                                                         │
                                      │  • primary_id: str                                    │
                                      │  • primary_label: str                                 │
                                      │  • concept_type: ConceptType                          │
                                      │  • identifiers: list[ConceptIdentifier]              │
                                      │  • sources: set[KnowledgeSource]                     │
                                      │  • confidence_score: float                           │
                                      │  • synonyms, definitions, semantic_types             │
                                      │  • parents, children, related concepts               │
                                      │  • mappings, categories                              │
                                      │  • source_data: dict                                 │
                                      └───────────────────────────────────────────────────────┘
                                                        │
                                                        ▼
                                      ┌───────────────────────────────────────────────────────┐
                                      │              LookupResult                             │
                                      │                                                         │
                                      │  • query: str                                         │
                                      │  • concepts: list[UnifiedConcept]                    │
                                      │  • total_found: int                                   │
                                      │  • sources_queried/succeeded/failed                  │
                                      │  • execution_time: float                             │
                                      │  • errors: dict[KnowledgeSource, str]                │
                                      └───────────────────────────────────────────────────────┘
```

## Component Details

### 1. CentralKnowledgeLookup (Orchestrator)

**Location**: `src/knowledge_lookup/central_lookup.py`

The central orchestrator manages all knowledge sources and provides a unified interface:

**Key Responsibilities**:
- **Adapter Management**: Initialize, store, and manage all knowledge source adapters
- **Query Coordination**: Execute queries either in parallel or sequentially based on configuration
- **Rate Limiting**: Apply rate limits per source to prevent API throttling
- **Result Integration**: Merge duplicate concepts from multiple sources
- **Error Handling**: Collect and report errors from individual sources
- **Caching**: Check cache before querying sources

**Main Methods**:
- `search_concepts(query, concept_types, sources, max_results, parallel)` - Search across sources
- `get_concept_details(concept_id, source)` - Get detailed info for a specific concept
- `find_mappings(concept_id, target_sources)` - Find cross-references
- `get_concept_hierarchy(concept_id, levels, direction)` - Get parent/child relationships
- `suggest_similar_concepts(concept_id, similarity_threshold)` - Find similar concepts

### 2. KnowledgeSourceAdapter (Interface/Base Class)

**Location**: `src/knowledge_lookup/base.py`

Abstract base class defining the contract for all knowledge source adapters:

**Abstract Methods**:
- `get_source()` → KnowledgeSource: Returns the knowledge source enum value
- `search_concepts(query, limit)` → list[UnifiedConcept]: Search for matching concepts
- `get_concept_details(concept_id)` → UnifiedConcept: Get detailed concept information

**Key Features**:
- HTTP session management with aiohttp
- Request error handling and retry logic
- Rate limit configuration
- Default concept type determination from semantic types
- Async context manager support

### 3. Adapters (Source-Specific Implementations)

**Location**: `src/knowledge_lookup/adapters/`

Each adapter implements the interface for a specific knowledge source:

**Core Adapters**:
- **OpenTargetsAdapter**: Target-disease associations, drug-target interactions, pathways
- **ChEMBLAdapter**: Drug compounds, bioactivity data, drug-target interactions
- **MONDOAdapter**: Human diseases, ontological relationships, HPO mappings
- **UniProtAdapter**: Protein sequences, gene names, enzyme information
- **DisGeNETAdapter**: Gene-disease associations, risk factors
- **UMLSAdapter**: Unified Medical Language System concepts, semantic types

**Pattern**:
1. Initialize with config (API keys, rate limits, timeout)
2. Implement `search_concepts()` using source-specific API/endpoint
3. Implement `get_concept_details()` for detailed concept info
4. Parse source-specific response into `UnifiedConcept`
5. Return list of concepts with proper identifiers and metadata

### 4. UnifiedConcept Data Structure

**Location**: `src/knowledge_lookup/models.py`

The unified data structure that represents concepts across all sources:

**Core Fields**:
- `primary_id`: Primary identifier string
- `primary_label`: Human-readable label
- `concept_type`: Enum (DISEASE, DRUG, GENE, PROTEIN, etc.)
- `identifiers`: List of cross-reference identifiers from multiple sources
- `sources`: Set of knowledge sources this concept appears in
- `confidence_score`: Confidence rating for the concept

**Extended Fields**:
- `synonyms`: Alternative names
- `definitions`: Text definitions
- `semantic_types`: UMLS-style semantic types
- `categories`: Ontology categories
- `parents/children/related`: Hierarchical relationships
- `mappings`: Cross-mappings to other concepts
- `source_data`: Raw response data from each source

### 5. Cache Layer

**Implementation Options**:
- **Redis**: For distributed caching
- **Memcached**: Alternative distributed solution
- **In-memory**: Simple caching for single-process scenarios

**Cache Keys**:
- `search:{query}:{source}:{timestamp}` → Cached search results
- `concept:{concept_id}:{source}` → Cached concept details
- `mappings:{concept_id}` → Cached cross-references

**Features**:
- Configurable TTL per source
- Automatic cache hit/miss tracking
- Cache invalidation on updates

### 6. Rate Limiter

**Configuration**: Per-source rate limits in `LookupConfig.rate_limits`

**Implementation**:
- Async sleep between requests
- Token bucket or sliding window algorithms
- Per-source quota management

**Default Rate Limits**:
```python
rate_limits = {
    KnowledgeSource.UMLS: 10.0,      # 10 req/sec
    KnowledgeSource.BIOPORTAL: 5.0,  # 5 req/sec
    KnowledgeSource.CHEMBL: 15.0,    # 15 req/sec
    # ... per source limits
}
```

### 7. Error Handler

**Error Types**:
- **Network errors**: Timeout, connection refused
- **API errors**: Rate limiting, invalid API keys
- **Parsing errors**: Response format changes
- **Resource errors**: Concept not found

**Response Strategies**:
- **Retry**: Automatic retry with exponential backoff
- **Fallback**: Try alternative sources
- **Graceful degradation**: Continue with partial results
- **Error reporting**: Return error details without crashing

## Query Flow

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. CentralKnowledgeLookup.search_concepts(query)             │
│    - Check cache for results                                 │
│    - Determine query sources (enabled or specified)          │
│    - Apply rate limiting                                     │
└──────────────────────────────────────────────────────────────┘
    │
    ├─► Parallel Mode (if parallel=True)
    │     │
    │     ├─► Source 1 (OpenTargets) ──► Adapter.search() ──► Parse ──┐
    │     │                                                              │
    │     ├─► Source 2 (ChEMBL) ──────► Adapter.search() ──► Parse ────┼─► Merge
    │     │                                                              │
    │     └─► Source 3 (MONDO) ───────► Adapter.search() ──► Parse ────┘
    │
    └─► Sequential Mode (if parallel=False)
          │
          ├─► Source 1 ──► Adapter ──► Parse
          │
          ├─► Source 2 ──► Adapter ──► Parse
          │
          └─► Source 3 ──► Adapter ──► Parse

    ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Result Processing                                          │
│    - Merge duplicates (same concept from multiple sources)   │
│    - Filter by concept_type (if specified)                   │
│    - Sort by confidence_score                                │
│    - Apply max_results limit                                 │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. LookupResult                                               │
│    - concepts: List[UnifiedConcept]                          │
│    - total_found: int                                        │
│    - sources_succeeded/failed                                │
│    - errors: dict                                            │
│    - execution_time: float                                   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
User Application (Console, API, Web Interface)
```

## Configuration

```python
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

config = LookupConfig(
    enabled_sources=[
        KnowledgeSource.OPENTARGETS,
        KnowledgeSource.CHEMBL,
        KnowledgeSource.MONDO,
        KnowledgeSource.UNIPROT,
        KnowledgeSource.DISGENET,
        KnowledgeSource.UMLS,
    ],
    max_results_per_source=20,
    timeout_per_source=30.0,
    parallel_queries=True,
    rate_limits={
        KnowledgeSource.UMLS: 10.0,
        KnowledgeSource.BIOPORTAL: 5.0,
    },
    enable_deduplication=True,
)

lookup = CentralKnowledgeLookup(config=config)
result = await lookup.search_concepts("diabetes", max_results=50)
```

## Usage Example

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def main():
    config = LookupConfig.with_all_sources()
    lookup = CentralKnowledgeLookup(config=config)
    
    # Search for concepts
    result = await lookup.search_concepts(
        "type 2 diabetes",
        concept_types=[ConceptType.DISEASE],
        max_results=20
    )
    
    # Process results
    for concept in result.concepts:
        print(f"{concept.primary_label} ({concept.primary_id})")
        print(f"  Sources: {[s.value for s in concept.sources]}")
        print(f"  Confidence: {concept.confidence_score:.3f}")
    
    await lookup.close()

asyncio.run(main())
```

## Extending the System

To add a new knowledge source:

1. **Create adapter**: `src/knowledge_lookup/adapters/new_adapter.py`
2. **Implement required methods** from `KnowledgeSourceAdapter`
3. **Add to models**: Add to `KnowledgeSource` enum in `models.py`
4. **Register adapter**: Add to `ADAPTER_CLASSES` in `adapters/__init__.py`
5. **Test**: Write unit tests in `tests/unit/adapters/test_new_adapter.py`

## Performance Considerations

- **Parallel queries**: Enable for faster queries (default)
- **Caching**: Use Redis for multi-process deployments
- **Rate limiting**: Respect source API limits to avoid throttling
- **Connection pooling**: Reuse aiohttp sessions across requests
- **Result pagination**: Implement for large result sets

## Error Handling Strategy

```python
try:
    result = await lookup.search_concepts("query")
    if result.errors:
        for source, error in result.errors.items():
            logger.warning(f"Source {source} failed: {error}")
    for concept in result.concepts:
        # Process successful results
except Exception as e:
    logger.error(f"Search failed: {e}")
```

---

**Last Updated**: June 2026  
**Version**: 1.0  
**Maintainer**: AID-PAIS Team
