# InterPro Adapter

## Overview

The InterPro Adapter provides access to InterPro, a database of protein families, domains, and functional sites that integrates multiple protein signature databases including Pfam, PROSITE, PRINTS, ProDom, SMART, TIGRFAMs, PIRSF, SUPERFAMILY, GenomeProperties, and PANTHER.

### Purpose
- Search for protein families and domains
- Retrieve functional site information
- Access integrated protein signature data
- Support protein annotation and functional prediction

### Scope
- Protein families and domains
- Functional sites and binding regions
- Conserved signature motifs
- Structural domain predictions
- Cross-database protein signature integration

## Key Features

- **Protein Family Search**: Search InterPro for protein families and domains
- **Domain Architecture**: Retrieve domain organization information
- **Functional Annotations**: Access functional site data
- **Database Integration**: Single interface to multiple signature databases
- **Entry Type Classification**: Differentiate between families, domains, repeats
- **Integrated Databases**: Access Pfam, PROSITE, and other database entries

## API Information

### Endpoint
- **Base URL**: `https://www.ebi.ac.uk/interpro/api`

### Authentication
- **Required**: No
- **API Key**: Not required (public EMBL-EBI service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search InterPro for protein families and domains matching the query.

**Parameters:**
- `query` (str): Search term (protein name, domain name, keyword)
- `limit` (int): Maximum number of results (default: 20, max: 20)

**Returns:**
- List of `UnifiedConcept` objects representing protein entries

**Example:**
```python
concepts = await adapter.search_concepts("kinase")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific InterPro entry.

**Parameters:**
- `concept_id` (str): InterPro ID (e.g., "InterPro:IPR000001" or "IPR000001")

**Returns:**
- `UnifiedConcept` with full entry details, or `None` if not found

**Example:**
```python
entry = await adapter.get_concept_details("InterPro:IPR000001")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.interpro_adapter import InterProAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = InterProAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.interpro_adapter import InterProAdapter

adapter = InterProAdapter(config)

# Search for kinase domains
results = await adapter.search_concepts("kinase", limit=10)

for concept in results:
    print(f"Entry: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Type: {concept.semantic_types}")
```

### Get Entry Details
```python
# Get detailed information for a specific InterPro entry
entry = await adapter.get_concept_details("InterPro:IPR000719")

if entry:
    print(f"Name: {entry.primary_label}")
    print(f"Type: {entry.semantic_types}")
    print(f"Description: {entry.definitions}")
    print(f"Categories: {entry.categories}")  # Integrated databases
```

### Search by Protein
```python
# Search for domains in a specific protein
results = await adapter.search_concepts("EGFR")
```

### Search by Function
```python
# Search for DNA-binding domains
results = await adapter.search_concepts("DNA binding")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent entry IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("kinase")
    if not results:
        logger.info("No InterPro entries found for 'kinase'")
except Exception as e:
    logger.error(f"InterPro search failed: {e}")
```

## Rate Limiting

**InterPro API Rate Limits:**
- Free tier: 15 requests per second
- No API key required for public data

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect InterPro's rate limits
- Implement request batching for bulk operations
- Consider caching for frequently accessed entries

```python
# The adapter automatically handles rate limiting through the base class
# Rate limiting is minimal for public EMBL-EBI services
```

## Data Model Mapping

| InterPro Field | UnifiedConcept Mapping |
|---------------|----------------------|
| `metadata.accession` | `primary_id` (as `InterPro:{accession}`) |
| `metadata.name.name` / `metadata.name.short` | `primary_label` |
| `metadata.type` | `semantic_types.append(type)` |
| `metadata.description` | `definitions.extend(descriptions)` |
| `metadata.integrated` | `categories.append(integrated_db_accession)` |

## Related Adapters

- **Pfam Adapter**: For Pfam-specific protein families (via InterPro)
- **Uniprot Adapter**: For protein sequence and functional data
- **GeneOntology Adapter**: For functional annotations
- **PDB Adapter**: For 3D structural data

## References

- [InterPro Documentation](https://www.ebi.ac.uk/interpro/result/download/)
- [InterPro API](https://www.ebi.ac.uk/interpro/api/)
- [InterPro Entry Types](https://interpro-docs.readthedocs.io/en/latest/entrytypes.html)
