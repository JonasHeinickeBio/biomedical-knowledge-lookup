# KEGG Adapter

## Overview

The KEGG Adapter provides access to the Kyoto Encyclopedia of Genes and Genomes (KEGG), a database resource for understanding high-level functions and utilities of biological systems. It covers pathways, diseases, drugs, and orthology classifications.

### Purpose
- Search for biological pathways
- Retrieve disease and drug information
- Access KEGG orthology (KO) classifications
- Support pathway analysis and systems biology

### Scope
- Biological pathways (metabolism, signaling, cellular processes)
- Human diseases and drug information
- KEGG Orthology (KO) groups
- BRITE functional hierarchies
- KEGG GENES, GENOME, and COMPOUND databases
- Pathway maps and reaction information

## Key Features

- **Pathway Search**: Search KEGG for biological pathways
- **Disease and Drug Search**: Retrieve disease and drug information
- **Pathway Maps**: Access pathway diagram information
- **Orthology Classification**: Get KO classifications
- **Reaction Data**: Retrieve biochemical reactions
- **Species-Specific Paths**: Access organism-specific pathway versions

## API Information

### Endpoint
- **Base URL**: `https://rest.kegg.jp`

### Authentication
- **Required**: No
- **API Key**: Not required (public service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search KEGG for diseases or drugs matching the query.

**Parameters:**
- `query` (str): Search term (disease name, drug name, pathway)
- `limit` (int): Maximum number of results (default: 20)

**Returns:**
- List of `UnifiedConcept` objects representing diseases or drugs

**Example:**
```python
concepts = await adapter.search_concepts("diabetes")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific KEGG entry.

**Parameters:**
- `concept_id` (str): KEGG ID (e.g., "H00001" for disease, "D00001" for drug)

**Returns:**
- `UnifiedConcept` with full entry details, or `None` if not found

**Example:**
```python
entry = await adapter.get_concept_details("H00001")
```

## Configuration

Configure the adapter with required `LookupConfig`:

```python
from knowledge_lookup.adapters.kegg_adapter import KEGGAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = KEGGAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.kegg_adapter import KEGGAdapter

adapter = KEGGAdapter(config)

# Search for diabetes-related entries
results = await adapter.search_concepts("diabetes", limit=10)

for concept in results:
    print(f"Entry: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Type: {concept.concept_type}")
```

### Get Entry Details
```python
# Get detailed information for a specific disease
entry = await adapter.get_concept_details("H00001")

if entry:
    print(f"Name: {entry.primary_label}")
    print(f"Type: {entry.concept_type}")
    print(f"Description: {entry.definitions}")
```

### Search for Drugs
```python
# Search for drug entries
results = await adapter.search_concepts("aspirin")
```

### Search for Pathways
```python
# Search for metabolic pathways
results = await adapter.search_concepts("metabolism")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent entry IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("diabetes")
    if not results:
        logger.info("No KEGG entries found for 'diabetes'")
except Exception as e:
    logger.error(f"KEGG search failed: {e}")
```

## Rate Limiting

**KEGG API Rate Limits:**
- Free tier: No strict limits published
- Recommended: 3-5 requests per second

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect KEGG's rate limits
- Implement request throttling for bulk operations
- Consider caching for frequently accessed entries

```python
# The adapter automatically handles rate limiting through the base class
```

## Data Model Mapping

| KEGG Field | UnifiedConcept Mapping |
|-----------|----------------------|
| `kegg_id` | `primary_id` |
| `label` (from NAME line) | `primary_label` |
| `text` (raw KEGG format) | `definitions.append(description)` |
| `kegg_id.startswith('H')` | `concept_type = DISEASE` |
| `kegg_id.startswith('D')` | `concept_type = DRUG` |

## Related Adapters

- **Reactome Adapter**: For detailed pathway data
- **GeneOntology Adapter**: For functional annotations
- **Uniprot Adapter**: For protein-pathway mappings
- **DrugBank Adapter**: For detailed drug information

## References

- [KEGG API Documentation](https://www.kegg.jp/kegg/docs/api.html)
- [KEGG Website](https://www.kegg.jp/)
- [KEGG Help](https://www.kegg.jp/kegg/help.html)
