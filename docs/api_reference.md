# API Reference

Complete reference for the Biomedical Knowledge Lookup library.

## Core Classes

### CentralKnowledgeLookup

Main entry point for querying multiple knowledge sources.

```python
from knowledge_lookup import CentralKnowledgeLookup

lookup = CentralKnowledgeLookup(config=None)
```

#### Methods

##### `search_concepts(query, sources=None, max_results=50, parallel=True)`

Search for concepts across knowledge sources.

| Parameter | Type | Description |
|-----------|------|-------------|
| query | str | Search term or phrase |
| sources | list[KnowledgeSource] | Specific sources to query (default: all) |
| max_results | int | Maximum total results (default: 50) |
| parallel | bool | Query sources in parallel (default: True) |

Returns: `LookupResult`

##### `get_concept_details(concept_id, source=None)`

Get detailed information about a concept.

| Parameter | Type | Description |
|-----------|------|-------------|
| concept_id | str | Concept identifier |
| source | KnowledgeSource | Specific source (default: try all) |

Returns: `UnifiedConcept | None`

##### `get_concept_hierarchy(concept_id, levels=1, direction="both")`

Get hierarchical relationships.

| Parameter | Type | Description |
|-----------|------|-------------|
| concept_id | str | Concept identifier |
| levels | int | Hierarchy levels to traverse |
| direction | str | "up", "down", or "both" |

Returns: `dict[str, list[UnifiedConcept]]`

##### `suggest_similar_concepts(concept_id, similarity_threshold=0.8)`

Find similar concepts.

Returns: `list[UnifiedConcept]`

#### Export Methods

| Method | Description |
|--------|-------------|
| `export_to_json(result, filepath)` | Export to JSON format |
| `export_to_csv(result, filepath)` | Export to CSV format |
| `export_to_ttl(result, filepath)` | Export to Turtle RDF |
| `export_to_dataframe(result)` | Export to pandas DataFrame |
| `export_to_excel(result, filepath)` | Export to Excel workbook |
| `export_summary_report(result, filepath)` | Generate text report |

---

### MultiSourceAnnotator

Advanced annotation using multiple sources with consensus analysis.

```python
from knowledge_lookup import MultiSourceAnnotator

annotator = MultiSourceAnnotator(config=None)
```

#### Methods

##### `annotate_sentence(sentence, sources=None)`

Annotate a sentence using multiple sources.

Returns: `MultiSourceAnnotationResult`

##### `annotate_multiple_sentences(sentences, sources=None)`

Annotate multiple sentences with batch processing.

Returns: `list[MultiSourceAnnotationResult]`

---

## Data Models

### UnifiedConcept

Standardized concept representation.

| Attribute | Type | Description |
|-----------|------|-------------|
| primary_id | str | Unique identifier |
| primary_label | str | Preferred label |
| concept_type | ConceptType | Type enum |
| synonyms | list[str] | Alternative labels |
| definitions | list[str] | Concept definitions |
| semantic_types | list[str] | UMLS semantic types |
| categories | list[str] | Category labels |
| sources | set[KnowledgeSource] | Contributing sources |
| confidence_score | float | Confidence (0-1) |
| parents | list[str] | Parent concept IDs |
| children | list[str] | Child concept IDs |

#### Methods

- `add_identifier(source, identifier, label=None)` - Add cross-reference
- `add_mapping(target_source, target_id, ...)` - Add mapping
- `get_identifier(source)` - Get identifier for source
- `has_source(source)` - Check if source contributed
- `merge_with(other)` - Merge with another concept

### LookupResult

Container for search results.

| Attribute | Type | Description |
|-----------|------|-------------|
| query | str | Original search query |
| concepts | list[UnifiedConcept] | Found concepts |
| total_found | int | Total count |
| sources_queried | list[KnowledgeSource] | Sources attempted |
| sources_succeeded | list[KnowledgeSource] | Sources with results |
| sources_failed | list[KnowledgeSource] | Sources with errors |
| execution_time | float | Seconds taken |
| errors | dict | Error messages by source |

#### Methods

- `add_concepts(concepts, source)` - Add concepts from source
- `get_best_matches(limit=10)` - Get top concepts by confidence
- `group_by_source()` - Group concepts by source

### LookupConfig

Configuration for lookup operations.

| Attribute | Type | Description |
|-----------|------|-------------|
| enabled_sources | list[KnowledgeSource] | Sources to enable |
| max_results_per_source | int | Per-source limit (default: 20) |
| timeout_per_source | float | Timeout in seconds (default: 30) |
| min_confidence_threshold | float | Minimum confidence (default: 0) |
| rate_limits | dict | Requests per second per source |
| enable_deduplication | bool | Deduplicate results (default: True) |
| similarity_threshold | float | Deduplication threshold (default: 0.8) |

---

## Enums

### KnowledgeSource

All 27 supported knowledge sources:

```
UMLS, OLS, BIOPORTAL, BIOONTOLOGY, CHEMBL, UNICHEM,
BIOLINKER, DISGENET, MONDO, PUBCHEM, UNIPROT,
WIKIDATA, DBPEDIA, OXO, TYTO, ZOOMA,
OPENTARGETS, REACTOME, DRUGBANK, GENEONTOLOGY,
HPO, OBOFOUNDRY, EBIOLS, ENSEMBL, KEGG,
QUICKGO, EUTILS
```

### ConceptType

Concept type classification:

```
DISEASE, SYMPTOM, PHENOTYPE, TREATMENT, PROGNOSIS,
GENE, PROTEIN, CYTOKINE, BIOMARKER,
CHEMICAL, DRUG,
ORGAN, TISSUE, CELL_TYPE,
PATHWAY, BIOLOGICAL_PROCESS, MOLECULAR_FUNCTION,
PROCEDURE, OBSERVATION, ASSAY,
CLINICAL_STUDY, EVIDENCE, REFERENCE
```

### AnnotationConfidence

Confidence levels for multi-source annotation:

```
HIGH     - 80%+ sources agree
MEDIUM   - 60-79% sources agree
LOW      - 40-59% sources agree
DISPUTED - <40% sources agree
```

---

## Factory Function

### `create_knowledge_lookup`

Convenience factory for quick setup:

```python
from knowledge_lookup import create_knowledge_lookup

lookup = create_knowledge_lookup(
    api_keys={"bioportal": "key"},
    fast_mode=True
)
```

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
```

---

## Usage Example

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

async def main():
    lookup = CentralKnowledgeLookup()

    # Search
    result = await lookup.search_concepts(
        "insulin",
        sources=[KnowledgeSource.BIOPORTAL, KnowledgeSource.CHEMBL],
        max_results=20
    )

    # Access results
    print(f"Found {result.total_found} concepts")
    for concept in result.concepts[:5]:
        print(f"  {concept.primary_label}")

    # Export
    lookup.export_to_json(result, "results.json")

    await lookup.close()

asyncio.run(main())
```