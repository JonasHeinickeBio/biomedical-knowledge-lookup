# Pfam Adapter

## Overview

The Pfam Adapter provides access to Pfam, a large collection of protein families, each represented by multiple sequence alignments and hidden Markov models (HMMs). Pfam is now served via the InterPro API and provides comprehensive protein family coverage.

### Purpose
- Search for protein families and domains
- Retrieve HMM-based family classifications
- Access protein domain architecture information
- Support protein annotation and functional prediction

### Scope
- Protein families (PF00001 format)
- Protein domains and repeats
- Homologous superfamily classifications
- Clan groupings (related families)
- Sequence motif definitions

## Key Features

- **Protein Family Search**: Search Pfam for protein families by name or description
- **HMM-Based Classification**: Access hidden Markov model family definitions
- **Clan Information**: Retrieve clan groupings for related families
- **Domain Architecture**: Access domain organization in proteins
- **Integrated with InterPro**: Single interface for Pfam data via InterPro API
- **Sequence Alignment Data**: Access multiple sequence alignments

## API Information

### Endpoint
- **Base URL**: `https://www.ebi.ac.uk/interpro/api` (Pfam data via InterPro)

### Authentication
- **Required**: No
- **API Key**: Not required (public EMBL-EBI service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search Pfam for protein families matching the query.

**Parameters:**
- `query` (str): Search term (family name, domain name, keyword)
- `limit` (int): Maximum number of results (default: 20, max: 20)

**Returns:**
- List of `UnifiedConcept` objects representing protein family entries

**Example:**
```python
concepts = await adapter.search_concepts("SH2")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific Pfam entry.

**Parameters:**
- `concept_id` (str): Pfam ID (e.g., "Pfam:PF00001" or "PF00001")

**Returns:**
- `UnifiedConcept` with full family details, or `None` if not found

**Example:**
```python
family = await adapter.get_concept_details("Pfam:PF00001")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.pfam_adapter import PfamAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = PfamAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.pfam_adapter import PfamAdapter

adapter = PfamAdapter(config)

# Search for SH2 domain family
results = await adapter.search_concepts("SH2", limit=5)

for concept in results:
    print(f"Family: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Type: {concept.semantic_types}")
```

### Get Family Details
```python
# Get detailed information for a specific Pfam family
family = await adapter.get_concept_details("Pfam:PF07714")

if family:
    print(f"Name: {family.primary_label}")
    print(f"Type: {family.semantic_types}")
    print(f"Description: {family.definitions}")
    print(f"Clan: {[c for c in family.categories if c.startswith('clan:')]}")
```

### Search by Protein
```python
# Search for families in a specific protein
results = await adapter.search_concepts("p53")
```

### Search by Function
```python
# Search for ATP-binding domains
results = await adapter.search_concepts("ATP binding")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent family IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("SH2")
    if not results:
        logger.info("No Pfam entries found for 'SH2'")
except Exception as e:
    logger.error(f"Pfam search failed: {e}")
```

## Rate Limiting

**InterPro API Rate Limits (includes Pfam):**
- Free tier: 15 requests per second
- No API key required for public data

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect InterPro's rate limits
- Implement request batching for bulk operations
- Consider caching for frequently accessed families

```python
# The adapter automatically handles rate limiting through the base class
# Rate limiting is minimal for public EMBL-EBI services
```

## Data Model Mapping

| Pfam Field | UnifiedConcept Mapping |
|-----------|----------------------|
| `metadata.accession` | `primary_id` (as `Pfam:{accession}`) |
| `metadata.name.name` / `metadata.name.short` | `primary_label` |
| `metadata.type` | `semantic_types.append(type)` |
| `metadata.description` | `definitions.extend(description)` |
| `metadata.clan` | `categories.append("clan:{clan}")` |

## Related Adapters

- **InterPro Adapter**: For unified access to all protein signature databases
- **Uniprot Adapter**: For protein sequence and functional data
- **GeneOntology Adapter**: For functional annotations
- **PDB Adapter**: For 3D structural data

## References

- [Pfam Documentation](https://pfam.xfam.org/)
- [InterPro API](https://www.ebi.ac.uk/interpro/api/)
- [Pfam Help](https://pfam.xfam.org/help)
