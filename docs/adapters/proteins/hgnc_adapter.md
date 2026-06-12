# HGNC Adapter

## Overview

The HGNC Adapter provides access to the HUGO Gene Nomenclature Committee (HGNC) database, which provides official gene symbols and names for human genes. It ensures standardized gene nomenclature and provides comprehensive cross-references to other databases.

### Purpose
- Retrieve official human gene symbols and names
- Access gene cross-references across multiple databases
- Get gene aliases and previous symbols
- Support standardized gene annotation

### Scope
- Official human gene nomenclature
- Gene symbols, names, and descriptions
- Alias symbols and previous symbols
- Gene locations and locus types
- Cross-references to Ensembl, NCBI, UniProt, and other databases
- Gene groups and families

## Key Features

- **Gene Symbol Search**: Search for genes by symbol, name, or alias
- **Official Nomenclature**: Access approved HGNC gene symbols
- **Alias Resolution**: Retrieve all gene aliases and previous symbols
- **Cross-Database References**: Access Ensembl, NCBI Gene, UniProt, and other IDs
- **Gene Location**: Retrieve chromosomal locations and locus information
- **Gene Groups**: Access gene family and group classifications

## API Information

### Endpoint
- **Base URL**: `https://rest.genenames.org`

### Authentication
- **Required**: No
- **API Key**: Not required (public service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search HGNC for genes matching the query (symbol, name, or alias).

**Parameters:**
- `query` (str): Search term (gene symbol, name, or alias)
- `limit` (int): Maximum number of results (default: 20)

**Returns:**
- List of `UnifiedConcept` objects representing gene entries

**Example:**
```python
concepts = await adapter.search_concepts("BRCA1")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific HGNC gene entry.

**Parameters:**
- `concept_id` (str): HGNC ID (e.g., "HGNC:1100") or gene symbol

**Returns:**
- `UnifiedConcept` with full gene details, or `None` if not found

**Example:**
```python
gene = await adapter.get_concept_details("HGNC:1100")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.hgnc_adapter import HGNCAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = HGNCAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.hgnc_adapter import HGNCAdapter

adapter = HGNCAdapter(config)

# Search for BRCA1 gene
results = await adapter.search_concepts("BRCA1", limit=5)

for concept in results:
    print(f"Gene: {concept.primary_label}")
    print(f"Name: {concept.primary_id}")
    print(f"Location: {concept.categories}")
```

### Get Gene Details
```python
# Get detailed information for a specific gene
gene = await adapter.get_concept_details("HGNC:1100")

if gene:
    print(f"Symbol: {gene.primary_label}")
    print(f"Name: {gene.primary_id}")
    print(f"Location: {gene.categories}")
    print(f"Locus Type: {gene.semantic_types}")
    print(f"Synonyms: {gene.synonyms}")
    print(f"Aliases: {gene.synonyms}")
```

### Search by Alias
```python
# Search using an alias
results = await adapter.search_concepts("BRCC1")
```

### Search by Location
```python
# Search for genes on chromosome 17
results = await adapter.search_concepts("17q")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent gene IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("BRCA1")
    if not results:
        logger.info("No HGNC entries found for 'BRCA1'")
except Exception as e:
    logger.error(f"HGNC search failed: {e}")
```

## Rate Limiting

**HGNC API Rate Limits:**
- Free tier: No strict limits published
- Recommended: 3-5 requests per second

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect HGNC's rate limits
- Implement request throttling for bulk operations
- Consider caching for frequently accessed genes

```python
# The adapter automatically handles rate limiting through the base class
```

## Data Model Mapping

| HGNC Field | UnifiedConcept Mapping |
|-----------|----------------------|
| `hgnc_id` | `primary_id` (as `HGNC:{id}`) |
| `name` | `primary_label` |
| `symbol` | `synonyms.append(symbol)` |
| `alias_symbol` | `synonyms.extend(alias_symbol)` |
| `prev_symbol` | `synonyms.extend(prev_symbol)` |
| `location` | `categories.append("locus:{location}")` |
| `gene_group` | `categories.extend(gene_group)` |
| `locus_type` | `semantic_types.append(locus_type)` |
| `entrez_id` | `add_identifier(NCBI, entrez_id)` |
| `ensembl_gene_id` | `add_identifier(ENSEMBL, ensembl_id)` |
| `uniprot_ids` | `add_identifier(UNIPROT, uid)` |

## Related Adapters

- **Ensembl Adapter**: For genome coordinates and gene models
- **NCBI EUtils Adapter**: For Entrez Gene data
- **Uniprot Adapter**: For protein-level data
- **OMIM Adapter**: For disease associations

## References

- [HGNC REST API Documentation](https://www.genenames.org/help/rest/)
- [HGNC Website](https://www.genenames.org/)
- [HGNC Help](https://www.genenames.org/help/)
