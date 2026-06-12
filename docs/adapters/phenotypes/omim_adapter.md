# OMIM Adapter

## Overview

The OMIM Adapter provides access to OMIM (Online Mendelian Inheritance in Man), a comprehensive and authoritative compendium of human genes and genetic phenotypes. It contains detailed information about the relationship between genes and inherited conditions.

### Purpose
- Search for human genes and genetic disorders
- Retrieve Mendelian inheritance patterns
- Access gene-phenotype relationships
- Support clinical genetics and rare disease research

### Scope
- Human genes and their phenotypic associations
- Mendelian disorders and inheritance patterns
- Gene symbols and MIM numbers
- Clinical synopses and diagnostic criteria
- Allelic variants and mutations
- Cross-references to other databases

## Key Features

- **Gene and Disorder Search**: Search OMIM for genes and genetic disorders
- **MIM Number Resolution**: Access entries by MIM number
- **Phenotype Data**: Retrieve detailed clinical phenotypes
- **Inheritance Patterns**: Access mode of inheritance information
- **Gene Symbols**: Get official gene symbols and aliases
- **Alternative Titles**: Access multiple names and synonyms
- **Cross-Database References**: Link to NCBI, UniProt, and other databases

## API Information

### Endpoint
- **Base URL**: `https://api.omim.org/api`

### Authentication
- **Required**: Yes
- **API Key**: Set via `OMIM_API_KEY` environment variable or config

### Environment Variables
- `OMIM_API_KEY`: OMIM API key (required for access)

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search OMIM for genes and genetic disorders matching the query.

**Parameters:**
- `query` (str): Search term (gene name, disorder, keyword)
- `limit` (int): Maximum number of results (default: 20, max: 20)

**Returns:**
- List of `UnifiedConcept` objects representing genes or disorders

**Example:**
```python
concepts = await adapter.search_concepts("cystic fibrosis")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific OMIM entry.

**Parameters:**
- `concept_id` (str): OMIM ID (e.g., "OMIM:143100" or "143100" or "MIM:143100")

**Returns:**
- `UnifiedConcept` with full entry details, or `None` if not found

**Example:**
```python
entry = await adapter.get_concept_details("OMIM:143100")
```

## Configuration

Configure the adapter with the required API key:

```python
from knowledge_lookup.adapters.omim_adapter import OMIMAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
# Set API key via environment variable
# export OMIM_API_KEY="your_api_key_here"
adapter = OMIMAdapter(config)

# Check availability before use
if adapter.is_available():
    # Proceed with queries
    pass
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.omim_adapter import OMIMAdapter

adapter = OMIMAdapter(config)

# Search for cystic fibrosis
results = await adapter.search_concepts("cystic fibrosis", limit=5)

for concept in results:
    print(f"Entry: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Type: {concept.concept_type}")
```

### Get Entry Details
```python
# Get detailed information for a specific OMIM entry
entry = await adapter.get_concept_details("OMIM:219700")

if entry:
    print(f"Title: {entry.primary_label}")
    print(f"Type: {entry.concept_type}")
    print(f"Gene Symbols: {[c for c in entry.categories if c.startswith('gene_symbols:')}])")
    print(f"Synonyms: {entry.synonyms}")
```

### Search by MIM Number
```python
# Direct lookup by MIM number
entry = await adapter.get_concept_details("143100")
```

### Search by Gene
```python
# Search for CFTR gene
results = await adapter.search_concepts("CFTR")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Authentication Errors**: Logs warning when API key is missing, returns empty list
- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent entry IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("cystic fibrosis")
    if not results:
        logger.info("No OMIM entries found for 'cystic fibrosis'")
except Exception as e:
    logger.error(f"OMIM search failed: {e}")
```

## Rate Limiting

**OMIM API Rate Limits:**
- Free tier: Limited requests per day
- Authenticated access: Higher limits with API key

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect OMIM's rate limits
- Implement request throttling for bulk operations
- Cache results for frequently accessed entries
- Use API key for production workloads

```python
# The adapter automatically handles rate limiting through the base class
# Ensure API key is set for production use
```

## Data Model Mapping

| OMIM Field | UnifiedConcept Mapping |
|-----------|----------------------|
| `mimNumber` | `primary_id` (as `OMIM:{number}`) |
| `titles.preferredTitle` | `primary_label` |
| `type` | `concept_type` (determined by `_determine_omim_type()`) |
| `titles.alternativeTitles` | `synonyms.extend(titles)` |
| `titles.includedTitles` | `synonyms.extend(titles)` |
| `geneMap.geneSymbols` | `categories.append("gene_symbols:{symbols}")` |

## Related Adapters

- **ClinVar Adapter**: For variant-level data
- **HGNC Adapter**: For gene nomenclature
- **Uniprot Adapter**: For protein-level data
- **GeneOntology Adapter**: For functional annotations

## References

- [OMIM API Documentation](https://www.omim.org/help/api)
- [OMIM Website](https://www.omim.org/)
- [OMIM Help](https://www.omim.org/help/)
