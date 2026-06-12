# Gene Ontology (GO) Adapter

## Overview

The Gene Ontology Adapter provides access to the Gene Ontology (GO) database through QuickGO API. GO provides a controlled vocabulary of terms for describing gene product characteristics across species, covering biological process, molecular function, and cellular component.

### Purpose
- Search for Gene Ontology terms
- Retrieve GO term definitions and relationships
- Access gene-to-GO term annotations
- Support functional enrichment analysis

### Scope
- GO terms (Biological Process, Molecular Function, Cellular Component)
- GO term definitions and synonyms
- Term relationships (is_a, part_of, regulates)
- Gene and protein annotations to GO terms
- Evidence codes and annotation sources

## Key Features

- **GO Term Search**: Search GO for terms by name or description
- **Term Details**: Retrieve comprehensive term information
- **Annotation Search**: Find genes annotated to specific GO terms
- **Evidence Codes**: Access evidence codes for annotations
- **Term Relationships**: Access hierarchical relationships between terms
- **Cross-References**: Link to external databases

## API Information

### Endpoint
- **Base URL**: `https://www.ebi.ac.uk/QuickGO/services/ontology/go`

### Authentication
- **Required**: No
- **API Key**: Not required (public EMBL-EBI service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search GO for terms matching the query.

**Parameters:**
- `query` (str): Search term (GO term name, keyword)
- `limit` (int): Maximum number of results (default: 20)

**Returns:**
- List of `UnifiedConcept` objects representing GO terms

**Example:**
```python
concepts = await adapter.search_concepts("cell cycle")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific GO term.

**Parameters:**
- `concept_id` (str): GO ID (e.g., "GO:0008150")

**Returns:**
- `UnifiedConcept` with full term details, or `None` if not found

**Example:**
```python
term = await adapter.get_concept_details("GO:0008150")
```

## Configuration

Configure the adapter with required `LookupConfig`:

```python
from knowledge_lookup.adapters.geneontology_adapter import GeneOntologyAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = GeneOntologyAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.geneontology_adapter import GeneOntologyAdapter

adapter = GeneOntologyAdapter(config)

# Search for cell cycle terms
results = await adapter.search_concepts("cell cycle", limit=10)

for concept in results:
    print(f"GO Term: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Aspect: {concept.categories}")
```

### Get Term Details
```python
# Get detailed information for a specific GO term
term = await adapter.get_concept_details("GO:0008150")

if term:
    print(f"Name: {term.primary_label}")
    print(f"ID: {term.primary_id}")
    print(f"Definition: {term.definitions}")
    print(f"Aspect: {term.categories}")
    print(f"Synonyms: {term.synonyms}")
```

### Search by Function
```python
# Search for ATP binding terms
results = await adapter.search_concepts("ATP binding")
```

### Search by Process
```python
# Search for metabolic process terms
results = await adapter.search_concepts("metabolic process")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent term IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("cell cycle")
    if not results:
        logger.info("No GO terms found for 'cell cycle'")
except Exception as e:
    logger.error(f"GO search failed: {e}")
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

| GO Field | UnifiedConcept Mapping |
|---------|----------------------|
| `id` | `primary_id` (as `GO:{id}`) |
| `name` | `primary_label` |
| `definition.text` | `definitions.append(definition)` |
| `synonyms.name` | `synonyms.extend(synonyms)` |
| `aspect` | `categories.append("Aspect: {aspect}")` |

## Related Adapters

- **QuickGO Adapter**: For GO annotations
- **Uniprot Adapter**: For protein-GO annotations
- **HGNC Adapter**: For gene-GO annotations
- **InterPro Adapter**: For domain-GO mappings

## References

- [QuickGO Documentation](https://www.ebi.ac.uk/QuickGO/)
- [Gene Ontology Website](http://geneontology.org/)
- [GO Help](http://geneontology.org/docs/go-citation-policy/)
