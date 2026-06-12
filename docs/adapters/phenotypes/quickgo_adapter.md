# QuickGO Adapter

## Overview

The QuickGO Adapter provides access to QuickGO, the Gene Ontology annotation service. QuickGO provides comprehensive Gene Ontology (GO) annotations for genes and gene products, including evidence codes, annotation sources, and cross-references.

### Purpose
- Search for GO terms and annotations
- Retrieve gene-GO term associations
- Access evidence codes and annotation sources
- Support functional annotation analysis

### Scope
- GO terms and their annotations
- Gene and protein annotations to GO terms
- Evidence codes (IDA, IEA, IMP, etc.)
- Annotation sources and references
- Taxon information for annotations
- Annotation extensions

## Key Features

- **GO Term Search**: Search QuickGO for GO terms by name
- **Annotation Search**: Find annotations for specific genes/proteins
- **Evidence Code Access**: Retrieve evidence codes for annotations
- **Reference Information**: Get publication references
- **Annotation Extensions**: Access annotation extension data
- **Taxon Support**: Get species information for annotations

## API Information

### Endpoint
- **Base URL**: Uses `bioservices.QuickGO` client (not REST API)

### Authentication
- **Required**: No
- **API Key**: Not required

### Environment Variables
- None required

## Prerequisites

The QuickGO adapter requires the `bioservices` package:

```bash
pip install bioservices
```

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search QuickGO for GO terms and annotations matching the query.

**Parameters:**
- `query` (str): Search term (gene ID, protein ID, GO term keyword)
- `limit` (int): Maximum number of results (default: 20)

**Returns:**
- List of `UnifiedConcept` objects representing GO terms or annotations

**Example:**
```python
concepts = await adapter.search_concepts("TP53")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a GO term or annotation.

**Parameters:**
- `concept_id` (str): GO ID (e.g., "GO:0008150") or gene-GO association

**Returns:**
- `UnifiedConcept` with term details or annotation details, or `None` if not found

**Example:**
```python
term = await adapter.get_concept_details("GO:0008150")
```

## Configuration

Configure the adapter with required `LookupConfig`:

```python
from knowledge_lookup.adapters.quickgo_adapter import QuickGOAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = QuickGOAdapter(config)

# Ensure bioservices is installed
# pip install bioservices
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.quickgo_adapter import QuickGOAdapter

adapter = QuickGOAdapter(config)

# Search for TP53 annotations
results = await adapter.search_concepts("TP53", limit=20)

for concept in results:
    print(f"Primary Label: {concept.primary_label}")
    print(f"Type: {concept.concept_type}")
    print(f"Source: {concept.sources}")
```

### Get Term Details
```python
# Get detailed information for a specific GO term
term = await adapter.get_concept_details("GO:0008150")

if term:
    print(f"Name: {term.primary_label}")
    print(f"Aspect: {term.source_data[QUICKGO]['go_aspect']}")
    print(f"Definition: {term.source_data[QUICKGO]['definition']}")
```

### Search by Protein
```python
# Search for annotations of a specific protein
results = await adapter.search_concepts("P04637")
```

### Search by GO Term
```python
# Search for specific GO term
results = await adapter.search_concepts("apoptosis")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Missing Dependency**: Logs error and returns empty list if `bioservices` not available
- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent terms
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("TP53")
    if not results:
        logger.info("No QuickGO entries found for 'TP53'")
except Exception as e:
    logger.error(f"QuickGO search failed: {e}")
```

## Rate Limiting

**QuickGO API Rate Limits:**
- Free tier: 15 requests per second
- No API key required for public data

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect QuickGO's rate limits
- Implement request batching for bulk operations
- Consider caching for frequently accessed terms

```python
# The adapter automatically handles rate limiting through the base class
```

## Data Model Mapping

| QuickGO Field | UnifiedConcept Mapping |
|--------------|----------------------|
| `id` | `primary_id` |
| `name` | `primary_label` |
| `aspect` | `categories.append("Aspect: {aspect}")` |
| `definition.text` | `definitions.append(definition)` |
| `synonyms.name` | `synonyms.extend(synonyms)` |
| `geneProductId` + `goId` | `primary_id` (association format) |

## Related Adapters

- **GeneOntology Adapter**: For GO term definitions
- **Uniprot Adapter**: For protein annotations
- **HGNC Adapter**: For gene annotations
- **InterPro Adapter**: For domain annotations

## References

- [QuickGO Website](https://www.ebi.ac.uk/QuickGO/)
- [QuickGO API](https://www.ebi.ac.uk/QuickGO/api/index.html)
- [QuickGO Documentation](https://www.ebi.ac.uk/QuickGO/docs/)
