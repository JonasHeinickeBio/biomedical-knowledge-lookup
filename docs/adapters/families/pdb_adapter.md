# PDB Adapter

## Overview

The PDB Adapter provides access to the Protein Data Bank (PDB), the world's largest repository of 3D structural data of biological macromolecules. Managed by the RCSB PDB, it enables searching for protein structures and retrieving detailed structural information.

### Purpose
- Search for protein structures by name, function, or keyword
- Retrieve 3D structural data and metadata
- Access experimental method and resolution information
- Support structural biology and drug design applications

### Scope
- Macromolecular structures (proteins, nucleic acids, complexes)
- Experimental structure determination methods
- Resolution and quality metrics
- Ligand and bound molecule information
- Structure citations and publications

## Key Features

- **Structure Search**: Search PDB by protein name, function, or keyword
- **Experimental Method**: Access X-ray, NMR, Cryo-EM, and other method data
- **Resolution Information**: Retrieve structural resolution metrics
- **Release Dates**: Access structure release and revision history
- **Citation Data**: Get related publications and authors
- **Structure Summary**: Retrieve comprehensive structure metadata

## API Information

### Endpoint
- **Search URL**: `https://search.rcsb.org/rcsbsearch/v2/query`
- **Data URL**: `https://data.rcsb.org/rest/v1/core`

### Authentication
- **Required**: No
- **API Key**: Not required (public RCSB service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search PDB for protein structures matching the query.

**Parameters:**
- `query` (str): Search term (protein name, function, keyword)
- `limit` (int): Maximum number of results (default: 20, max: 25)

**Returns:**
- List of `UnifiedConcept` objects representing structure entries

**Example:**
```python
concepts = await adapter.search_concepts("hemoglobin")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific PDB entry.

**Parameters:**
- `concept_id` (str): PDB ID (e.g., "PDB:1HBB" or just "1HBB")

**Returns:**
- `UnifiedConcept` with full structure details, or `None` if not found

**Example:**
```python
structure = await adapter.get_concept_details("PDB:1HBB")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.pdb_adapter import PDBAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = PDBAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.pdb_adapter import PDBAdapter

adapter = PDBAdapter(config)

# Search for hemoglobin structures
results = await adapter.search_concepts("hemoglobin", limit=10)

for concept in results:
    print(f"Structure: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Method: {concept.categories}")
```

### Get Structure Details
```python
# Get detailed information for a specific structure
structure = await adapter.get_concept_details("PDB:1HBB")

if structure:
    print(f"Title: {structure.primary_label}")
    print(f"Method: {[c for c in structure.categories if c.startswith('method:')}])")
    print(f"Resolution: {[c for c in structure.categories if c.startswith('resolution:')}])")
    print(f"Release Date: {structure.last_updated}")
```

### Search by Protein
```python
# Search for structures of a specific protein
results = await adapter.search_concepts("insulin")
```

### Search by Method
```python
# Search for Cryo-EM structures
results = await adapter.search_concepts("Cryo-EM")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent structure IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("hemoglobin")
    if not results:
        logger.info("No PDB entries found for 'hemoglobin'")
except Exception as e:
    logger.error(f"PDB search failed: {e}")
```

## Rate Limiting

**RCSB PDB API Rate Limits:**
- Free tier: 10 requests per second
- No API key required for public data

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect RCSB's rate limits
- Implement request batching for bulk operations
- Consider caching for frequently accessed structures

```python
# The adapter automatically handles rate limiting through the base class
```

## Data Model Mapping

| PDB Field | UnifiedConcept Mapping |
|-----------|----------------------|
| `entry.id` | `primary_id` (as `PDB:{id}`) |
| `struct.title` | `primary_label` |
| `exptl.method` | `categories.append("method:{method}")` |
| `refine.ls_d_res_high` | `categories.append("resolution:{resolution}Å")` |
| `pdbx_audit_revision_history.revision_date` | `last_updated` |
| `struct.pdbx_descriptor` | `semantic_types.extend(keywords)` |

## Related Adapters

- **Uniprot Adapter**: For protein sequence data
- **HGNC Adapter**: For gene nomenclature
- **EuropePMC Adapter**: For related publications
- **InterPro Adapter**: For protein domain information

## References

- [RCSB PDB API Documentation](https://data.rcsb.org/)
- [RCSB PDB Website](https://www.rcsb.org/)
- [PDB Format Documentation](https://www.wwpdb.org/documentation/file-format)
