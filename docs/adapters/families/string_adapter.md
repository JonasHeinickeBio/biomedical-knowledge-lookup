# STRING Adapter

## Overview

The STRING Adapter provides access to STRING (Search Tool for the Retrieval of Interacting Genes/Proteins), a database of known and predicted protein-protein interactions. It includes direct (physical) and indirect (functional) associations derived from experiments, databases, and text mining.

### Purpose
- Search for protein-protein interactions
- Retrieve interaction partners and confidence scores
- Access functional association data
- Support pathway analysis and network biology

### Scope
- Protein-protein interactions (physical and functional)
- Interaction confidence scores
- Functional enrichment and pathway associations
- Protein complexes and modules
- Cross-species interaction predictions
- Text-mining derived interactions

## Key Features

- **Protein Search**: Search for proteins by identifier or name
- **Interaction Partners**: Retrieve interaction network for a protein
- **Confidence Scores**: Access interaction confidence metrics
- **Functional Associations**: Get functional enrichment data
- **Taxon Information**: Retrieve species information
- **Network Visualization**: Support for interaction network analysis

## API Information

### Endpoint
- **Base URL**: `https://string-db.org/api`

### Authentication
- **Required**: No
- **API Key**: Not required (public service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search STRING for proteins and protein-protein interactions matching the query.

**Parameters:**
- `query` (str): Search term (protein name, gene name, identifier)
- `limit` (int): Maximum number of results (default: 20, max: 5)

**Returns:**
- List of `UnifiedConcept` objects representing proteins

**Example:**
```python
concepts = await adapter.search_concepts("TP53")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get protein details and interaction partners from STRING.

**Parameters:**
- `concept_id` (str): STRING protein ID (e.g., "STRING:9606.ENSP00000269305")

**Returns:**
- `UnifiedConcept` with protein details and interaction partners, or `None` if not found

**Example:**
```python
protein = await adapter.get_concept_details("STRING:9606.ENSP00000269305")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.string_adapter import STRINGAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = STRINGAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.string_adapter import STRINGAdapter

adapter = STRINGAdapter(config)

# Search for TP53 protein
results = await adapter.search_concepts("TP53", limit=5)

for concept in results:
    print(f"Protein: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Taxon: {concept.categories}")
```

### Get Protein Details
```python
# Get protein details and interaction partners
protein = await adapter.get_concept_details("STRING:9606.ENSP00000269305")

if protein:
    print(f"Protein: {protein.primary_label}")
    print(f"Annotation: {protein.definitions}")
    print(f"Interactions: {protein.related}")
    print(f"Taxon: {[c for c in protein.categories if c.startswith('taxon:')}])")
```

### Search by Identifier
```python
# Search using Ensembl protein ID
results = await adapter.search_concepts("ENSP00000269305")
```

### Network Analysis
```python
# Get interaction partners for a protein
protein = await adapter.get_concept_details("STRING:9606.ENSP00000269305")

if protein and protein.related:
    for interaction in protein.related:
        print(f"Interaction: {interaction}")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent protein IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging
- **Interaction Fetch Failures**: Non-critical, logged as warning

```python
try:
    results = await adapter.search_concepts("TP53")
    if not results:
        logger.info("No STRING entries found for 'TP53'")
except Exception as e:
    logger.error(f"STRING search failed: {e}")
```

## Rate Limiting

**STRING API Rate Limits:**
- Free tier: No strict limits published
- Recommended: 10 requests per second

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect STRING's rate limits
- Implement request throttling for bulk operations
- Cache interaction networks for frequently accessed proteins

```python
# The adapter automatically handles rate limiting through the base class
```

## Data Model Mapping

| STRING Field | UnifiedConcept Mapping |
|-------------|----------------------|
| `stringId` | `primary_id` (as `STRING:{id}`) |
| `preferredName` | `primary_label` |
| `annotation` | `definitions.append(annotation[:500])` |
| `taxonId` | `categories.append("taxon:{id}")` |
| `interaction伙伴` | `related.append("{partner}(score={score})")` |

## Related Adapters

- **Uniprot Adapter**: For protein sequence and functional data
- **GeneOntology Adapter**: For functional annotations
- **KEGG Adapter**: For pathway data
- **Reactome Adapter**: For detailed pathway information

## References

- [STRING API Documentation](https://string-db.org/cgi/help?sessionId=)
- [STRING Website](https://string-db.org/)
- [STRING Help](https://string-db.org/help/)
