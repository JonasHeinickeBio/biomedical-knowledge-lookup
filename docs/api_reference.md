# API Reference

Complete reference for the Biomedical Knowledge Lookup library.

---

## Table of Contents

- [Core Classes](#core-classes)
  - [CentralKnowledgeLookup](#centralknowledgelookup)
  - [MultiSourceAnnotator](#multisourceannotator)
- [Data Models](#data-models)
  - [UnifiedConcept](#unifiedconcept)
  - [LookupResult](#lookupresult)
  - [LookupConfig](#lookupconfig)
  - [Identifier](#identifier)
  - [SourceResult](#sourceresult)
- [Enums](#enums)
- [Factory Functions](#factory-functions)
- [Cache System](#cache-system)
- [Error Handling](#error-handling)
- [Complete Usage Examples](#complete-usage-examples)

---

## Core Classes

### CentralKnowledgeLookup

Main entry point for querying multiple knowledge sources.

```python
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

lookup = CentralKnowledgeLookup(config=None)
```

#### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `LookupConfig | None` | `None` | Configuration object |

#### Methods

##### `search_concepts(query, sources=None, limit=20, offset=0, concept_types=None) -> LookupResult`

Search for concepts across knowledge sources.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | *Required* | Search term or phrase |
| `sources` | `List[KnowledgeSource] | None` | `None` | Specific sources to query (default: all) |
| `limit` | `int` | `20` | Maximum results per source |
| `offset` | `int` | `0` | Pagination offset |
| `concept_types` | `List[str] | None` | `None` | Filter by concept types |

**Returns:** `LookupResult`

**Example:**
```python
result = await lookup.search_concepts(
    query="diabetes",
    sources=[KnowledgeSource.MONDO, KnowledgeSource.OPENTARGETS],
    limit=10
)
```

---

##### `get_concept_details(concept_id, sources=None) -> Optional[UnifiedConcept]`

Get detailed information about a specific concept.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `concept_id` | `str` | *Required* | Concept identifier |
| `sources` | `List[KnowledgeSource] | None` | `None` | Specific sources to query |

**Returns:** `UnifiedConcept | None`

**Example:**
```python
concept = await lookup.get_concept_details(
    concept_id="DOID:9351",
    sources=[KnowledgeSource.MONDO]
)
```

---

##### `get_concept_hierarchy(concept_id, source, levels=2, direction="both") -> dict`

Get hierarchical relationships for a concept.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `concept_id` | `str` | *Required* | Concept identifier |
| `source` | `KnowledgeSource` | *Required* | Source to query |
| `levels` | `int` | `2` | Hierarchy levels to traverse |
| `direction` | `str` | `"both"` | `"up"`, `"down"`, or `"both"` |

**Returns:** `dict` - Hierarchical relationships

**Example:**
```python
hierarchy = await lookup.get_concept_hierarchy(
    concept_id="DOID:9351",
    source=KnowledgeSource.MONDO,
    levels=3,
    direction="up"
)
```

---

##### `get_similar_concepts(concept_id, source, threshold=0.8) -> List[UnifiedConcept]`

Find similar concepts based on semantic similarity.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `concept_id` | `str` | *Required* | Concept identifier |
| `source` | `KnowledgeSource` | *Required* | Source to query |
| `threshold` | `float` | `0.8` | Similarity threshold (0-1) |

**Returns:** `List[UnifiedConcept]`

**Example:**
```python
similar = await lookup.get_similar_concepts(
    concept_id="CHEMBL123",
    source=KnowledgeSource.CHEMBL,
    threshold=0.7
)
```

---

##### `is_source_available(source) -> bool`

Check if a knowledge source is accessible.

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | `KnowledgeSource` | Source to check |

**Returns:** `bool`

**Example:**
```python
if await lookup.is_source_available(KnowledgeSource.OPENTARGETS):
    # Source is available
```

---

##### `export_to_json(result, filepath) -> None`

Export lookup results to JSON file.

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `result` | `LookupResult` | Results to export |
| `filepath` | `str` | Output file path |

**Example:**
```python
lookup.export_to_json(result, "results.json")
```

---

##### `export_to_csv(result, filepath) -> None`

Export lookup results to CSV file.

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `result` | `LookupResult` | Results to export |
| `filepath` | `str` | Output file path |

**Example:**
```python
lookup.export_to_csv(result, "results.csv")
```

---

##### `export_to_dataframe(result) -> DataFrame`

Export lookup results to pandas DataFrame.

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `result` | `LookupResult` | Results to export |

**Returns:** `DataFrame`

**Example:**
```python
df = lookup.export_to_dataframe(result)
print(df.head())
```

---

##### `export_to_rdf(result, filepath, format="turtle") -> None`

Export lookup results to RDF format.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `result` | `LookupResult` | Results to export |
| `filepath` | `str` | Output file path |
| `format` | `str` | `"turtle"` | RDF format: "turtle", "xml", "json-ld" |

**Example:**
```python
lookup.export_to_rdf(result, "results.ttl", format="turtle")
```

---

##### `export_summary_report(result, filepath) -> None`

Generate a human-readable summary report.

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `result` | `LookupResult` | Results to report |
| `filepath` | `str` | Output file path |

**Example:**
```python
lookup.export_summary_report(result, "summary.txt")
```

---

##### `close() -> None`

Clean up resources and close HTTP sessions.

**Example:**
```python
await lookup.close()
```

---

### MultiSourceAnnotator

Advanced annotation using multiple sources with consensus analysis.

```python
from knowledge_lookup import MultiSourceAnnotator

annotator = MultiSourceAnnotator(config=None)
```

#### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `LookupConfig | None` | `None` | Configuration object |

#### Methods

##### `annotate_sentence(sentence, sources=None) -> MultiSourceAnnotationResult`

Annotate a sentence using multiple knowledge sources.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sentence` | `str` | *Required* | Text to annotate |
| `sources` | `List[KnowledgeSource] | None` | `None` | Sources to use (default: all) |

**Returns:** `MultiSourceAnnotationResult`

**Example:**
```python
result = await annotator.annotate_sentence(
    "Type 2 diabetes is associated with insulin resistance",
    sources=[KnowledgeSource.OPENTARGETS, KnowledgeSource.MONDO]
)
```

---

##### `annotate_multiple_sentences(sentences, sources=None) -> List[MultiSourceAnnotationResult]`

Annotate multiple sentences with batch processing.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sentences` | `List[str]` | *Required* | Texts to annotate |
| `sources` | `List[KnowledgeSource] | None` | `None` | Sources to use |

**Returns:** `List[MultiSourceAnnotationResult]`

**Example:**
```python
results = await annotator.annotate_multiple_sentences(
    sentences=[
        "TP53 is a tumor suppressor gene",
        "BRCA1 mutations increase cancer risk"
    ],
    sources=[KnowledgeSource.OPENTARGETS]
)
```

---

##### `get_consensus_concepts(annotation_result, min_sources=2) -> List[ConsensusConcept]`

Extract consensus concepts from annotation results.

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `annotation_result` | `MultiSourceAnnotationResult` | Annotation result |
| `min_sources` | `int` | `2` | Minimum sources for consensus |

**Returns:** `List[ConsensusConcept]`

**Example:**
```python
consensus = annotator.get_consensus_concepts(result, min_sources=2)
for c in consensus:
    print(f"Consensus: {c.primary_concept.primary_label}")
```

---

##### `get_annotation_confidence(annotation_result) -> float`

Calculate overall annotation confidence.

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `annotation_result` | `MultiSourceAnnotationResult` | Annotation result |

**Returns:** `float` - Confidence score (0-1)

**Example:**
```python
confidence = annotator.get_annotation_confidence(result)
print(f"Annotation confidence: {confidence:.2f}")
```

---

## Data Models

### UnifiedConcept

Standardized concept representation across knowledge sources.

| Attribute | Type | Description |
|-----------|------|-------------|
| `primary_id` | `str` | Primary identifier (source-specific) |
| `primary_label` | `str` | Preferred label/name |
| `concept_type` | `ConceptType` | Type classification |
| `synonyms` | `List[str]` | Alternative names |
| `definitions` | `List[str]` | Concept definitions |
| `semantic_types` | `List[str]` | UMLS semantic types |
| `categories` | `List[str]` | Category labels |
| `sources` | `Set[KnowledgeSource]` | Contributing sources |
| `confidence_score` | `float` | Confidence score (0-1) |
| `parents` | `List[str]` | Parent concept IDs |
| `children` | `List[str]` | Child concept IDs |
| `identifiers` | `List[Identifier]` | All identifiers |
| `data_sources` | `Dict` | Source-specific data |
| `url` | `str` | Main URL for concept |

#### Methods

| Method | Description |
|--------|-------------|
| `add_identifier(source, identifier, label=None)` | Add cross-reference identifier |
| `add_mapping(target_source, target_id, ...)` | Add mapping to another concept |
| `get_identifier(source)` | Get identifier for a specific source |
| `has_source(source)` | Check if source contributed |
| `merge_with(other)` | Merge with another concept |
| `get_identifier(source)` | Get identifier for a source |

---

### LookupResult

Container for search results.

| Attribute | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Original search query |
| `concepts` | `List[UnifiedConcept]` | Found concepts (deduplicated) |
| `total_found` | `int` | Total count across all sources |
| `results` | `List[SourceResult]` | Per-source results |
| `sources_queried` | `List[KnowledgeSource]` | Sources attempted |
| `sources_succeeded` | `List[KnowledgeSource]` | Sources with results |
| `sources_failed` | `List[KnowledgeSource]` | Sources with errors |
| `execution_time` | `float` | Seconds taken |
| `errors` | `Dict[KnowledgeSource, str]` | Error messages |

#### Methods

| Method | Description |
|--------|-------------|
| `add_concepts(concepts, source)` | Add concepts from a source |
| `get_best_matches(limit=10)` | Get top concepts by confidence |
| `group_by_source()` | Group concepts by source |
| `filter_by_confidence(min_score)` | Filter by minimum confidence |
| `filter_by_source(source)` | Filter by source |

---

### LookupConfig

Configuration for lookup operations.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled_sources` | `List[KnowledgeSource]` | All | Sources to enable |
| `max_results_per_source` | `int` | `20` | Per-source result limit |
| `timeout_per_source` | `float` | `30.0` | Timeout in seconds |
| `min_confidence_threshold` | `float` | `0.0` | Minimum confidence |
| `rate_limits` | `Dict[KnowledgeSource, float]` | `{}` | Requests/second |
| `enable_deduplication` | `bool` | `True` | Enable deduplication |
| `similarity_threshold` | `float` | `0.8` | Deduplication threshold |
| `retry_on_failure` | `bool` | `True` | Retry failed requests |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `retry_delay` | `float` | `1.0` | Base retry delay |
| `cache_enabled` | `bool` | `False` | Enable caching |
| `cache_ttl` | `int` | `3600` | Cache TTL in seconds |

---

### Identifier

Cross-reference identifier for a concept.

| Attribute | Type | Description |
|-----------|------|-------------|
| `source` | `KnowledgeSource` | Source of this identifier |
| `id` | `str` | Identifier value |
| `label` | `str | None` | Optional label |
| `url` | `str | None` | URL to concept |

---

### SourceResult

Results from a single knowledge source.

| Attribute | Type | Description |
|-----------|------|-------------|
| `source` | `KnowledgeSource` | Knowledge source |
| `concepts` | `List[UnifiedConcept]` | Found concepts |
| `total_found` | `int` | Total count from source |
| `execution_time` | `float` | Seconds taken |
| `error` | `str | None` | Error message if failed |

---

## Enums

### KnowledgeSource

All 27 supported knowledge sources:

```python
# Core sources
OPENTARGETS, CHEMBL, MONDO, UNIPROT, DISGENET
OLS, BIOPORTAL, ENSEMBL, REACTOME, PUBCHEM

# Additional sources
BIOPORTAL, UMLS, UNICHEM, WIKIDATA, DBPEDIA
OXO, TYTO, ZOOMA, DRUGBANK, GENEONTOLOGY
HPO, OBOFOUNDRY, EBIOLS, KEGG, QUICKGO, EUTILS
```

---

### ConceptType

Concept type classification:

```python
DISEASE, SYMPTOM, PHENOTYPE
TREATMENT, PROGNOSIS
GENE, PROTEIN, CYTOKINE, BIOMARKER
CHEMICAL, DRUG
ORGAN, TISSUE, CELL_TYPE
PATHWAY, BIOLOGICAL_PROCESS, MOLECULAR_FUNCTION
PROCEDURE, OBSERVATION, ASSAY
CLINICAL_STUDY, EVIDENCE, REFERENCE
```

---

### AnnotationConfidence

Confidence levels for multi-source annotation:

| Level | Description | Threshold |
|-------|-------------|-----------|
| `HIGH` | Strong consensus | 80%+ sources agree |
| `MEDIUM` | Moderate consensus | 60-79% sources agree |
| `LOW` | Limited consensus | 40-59% sources agree |
| `DISPUTED` | Low agreement | <40% sources agree |

---

## Factory Functions

### `create_knowledge_lookup`

Convenience factory for quick setup.

```python
from knowledge_lookup import create_knowledge_lookup

lookup = create_knowledge_lookup(
    api_keys={"bioportal": "your-key"},
    fast_mode=True
)
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_keys` | `Dict[str, str] | None` | `None` | API keys for sources |
| `fast_mode` | `bool` | `False` | Optimize for speed |

**Returns:** `CentralKnowledgeLookup`

---

### `create_annotator`

Create an annotator with default configuration.

```python
from knowledge_lookup import create_annotator

annotator = create_annotator()
```

**Returns:** `MultiSourceAnnotator`

---

## Cache System

```python
from knowledge_lookup import KnowledgeLookupCache, get_cache, init_cache

# Initialize cache
cache = init_cache("./cache_dir")

# Get default cache
cache = get_cache()

# Use in operations
cache.get("key")  # Get value
cache.set("key", value)  # Set value
cache.delete("key")  # Delete value
cache.clear()  # Clear all
```

---

## Error Handling

### Exception Hierarchy

```
Exception
├── KnowledgeLookupError
│   ├── SourceUnavailableError
│   ├── RateLimitError
│   ├── APIError
│   ├── ConfigurationError
│   └── ValidationError
```

### RateLimitError

Raised when a source rate limit is exceeded.

| Attribute | Type | Description |
|-----------|------|-------------|
| `source` | `KnowledgeSource` | Source that rate limited |
| `retry_after` | `float` | Seconds to wait before retry |
| `message` | `str` | Error message |

### SourceUnavailableError

Raised when a source is unreachable.

| Attribute | Type | Description |
|-----------|------|-------------|
| `source` | `KnowledgeSource` | Unavailable source |
| `message` | `str` | Error message |

### APIError

Raised for API response errors.

| Attribute | Type | Description |
|-----------|------|-------------|
| `source` | `KnowledgeSource` | Source that errored |
| `status_code` | `int` | HTTP status code |
| `message` | `str` | Error message |

---

## Complete Usage Examples

### Basic Search

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

async def basic_search():
    lookup = CentralKnowledgeLookup()
    
    # Search across all sources
    result = await lookup.search_concepts(
        query="diabetes",
        sources=list(KnowledgeSource)
    )
    
    print(f"Found {result.total_found} concepts")
    
    # Display results
    for concept in result.get_best_matches(10):
        print(f"  {concept.primary_label} ({concept.concept_type.value})")
    
    await lookup.close()

asyncio.run(basic_search())
```

### Multi-Source Annotation

```python
import asyncio
from knowledge_lookup import MultiSourceAnnotator, KnowledgeSource

async def annotate_text():
    annotator = MultiSourceAnnotator()
    
    # Annotate a medical text
    sentence = "TP53 mutations are associated with increased risk of breast cancer"
    
    result = await annotator.annotate_sentence(
        sentence=sentence,
        sources=[
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.DISGENET,
            KnowledgeSource.CHEMBL
        ]
    )
    
    # Get consensus concepts
    for consensus in result.consensus_concepts:
        print(f"Consensus: {consensus.primary_concept.primary_label}")
        print(f"  Confidence: {consensus.confidence_level.value}")
        print(f"  Sources: {len(consensus.agreeing_sources)}")
    
    await annotator.close()

asyncio.run(annotate_text())
```

### Advanced Configuration

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig, KnowledgeSource

async def advanced_usage():
    # Custom configuration
    config = LookupConfig(
        enabled_sources=[
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.CHEMBL,
            KnowledgeSource.MONDO,
        ],
        rate_limits={
            KnowledgeSource.OPENTARGETS: 5.0,
            KnowledgeSource.CHEMBL: 10.0,
        },
        timeout_per_source=60.0,
        max_results_per_source=30,
        enable_deduplication=True,
        similarity_threshold=0.85,
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    # Perform search
    result = await lookup.search_concepts(
        query="insulin resistance",
        sources=[KnowledgeSource.OPENTARGETS]
    )
    
    # Export results
    lookup.export_to_json(result, "results.json")
    df = lookup.export_to_dataframe(result)
    df.to_csv("results.csv", index=False)
    
    await lookup.close()

asyncio.run(advanced_usage())
```

### Error Handling

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource
from knowledge_lookup.exceptions import RateLimitError, SourceUnavailableError, APIError

async def error_handling():
    lookup = CentralKnowledgeLookup()
    
    try:
        result = await lookup.search_concepts(
            query="test",
            sources=[KnowledgeSource.OPENTARGETS]
        )
        print(f"Success: {len(result.concepts)} concepts")
        
    except RateLimitError as e:
        print(f"Rate limited by {e.source}")
        print(f"Retry after: {e.retry_after:.1f} seconds")
        # Implement exponential backoff
        import asyncio
        await asyncio.sleep(e.retry_after * 2)
        
    except SourceUnavailableError as e:
        print(f"Source {e.source} unavailable")
        # Try alternative source
        result = await lookup.search_concepts("test", [KnowledgeSource.MONDO])
        
    except APIError as e:
        print(f"API error from {e.source}: {e.status_code}")
        
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}")
        
    finally:
        await lookup.close()

asyncio.run(error_handling())
```

---

*For more examples, see the [Getting Started](getting_started.md) guide and [example notebooks](../examples/).*