# DBVar Adapter

## Overview

The DBVar Adapter provides access to dbVar (Database of Genomic Structural Variation), NCBI's database of human genomic structural variation. It enables searching for large-scale genomic variants (>50 bp) and retrieving detailed information about specific structural variants including their genomic coordinates, variant types, and clinical significance.

### Purpose
- Search for structural variants (insertions, deletions, duplications, inversions, translocations)
- Retrieve genomic coordinates and variant breakpoints
- Access clinical interpretations and phenotype associations
- Support structural variation research and genomic disorder analysis

### Scope
- Structural variant-level data from dbVar
- Genomic coordinates and breakpoints
- Study and dataset metadata
- Clinical significance and phenotype associations
- Support for NCBI EUtils API integration

## Key Features

- **Structural Variant Search**: Search dbVar by gene name, genomic location, or clinical phenotype
- **Detailed Variant Information**: Get comprehensive variant details including breakpoints and coordinates
- **Variant Type Classification**: Support for various structural variant types (CNV, insertion, deletion, inversion, etc.)
- **Genomic Coordinates**: Access chr, start, end positions and assembly information
- **Clinical Interpretation**: Access pathogenicity classifications and clinical significance
- **Study Metadata**: Retrieve study and dataset information for variants

## API Information

### Endpoint
- **Base URL**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`
- **dbVar Database**: NCBI EUtils database for structural variation data

### Authentication
- **Required**: No
- **API Key**: Not required (public NCBI service)

### Environment Variables
- None required

### Supported Databases
- `dbvar`: Database of genomic structural variation

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search dbVar for structural variants matching the query.

**Parameters:**
- `query` (str): Search term (gene name, genomic location, clinical phenotype)
- `limit` (int): Maximum number of results (default: 20, max: 20)

**Returns:**
- List of `UnifiedConcept` objects representing structural variants

**Example:**
```python
concepts = await adapter.search_concepts("CHR22")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific dbVar structural variant.

**Parameters:**
- `concept_id` (str): dbVar variant ID (e.g., "dbVar:CNV000001" or just "CNV000001")

**Returns:**
- `UnifiedConcept` with full variant details, or `None` if not found

**Example:**
```python
variant = await adapter.get_concept_details("dbVar:CNV000001")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.dbvar_adapter import DBVarAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = DBVarAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.dbvar_adapter import DBVarAdapter

adapter = DBVarAdapter(config)

# Search for structural variants on chromosome 22
results = await adapter.search_concepts("CHR22", limit=10)

for concept in results:
    print(f"Variant: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Type: {concept.semantic_types}")
```

### Get Variant Details
```python
# Get detailed information for a specific variant
variant = await adapter.get_concept_details("dbVar:CNV000001")

if variant:
    print(f"Title: {variant.primary_label}")
    print(f"Genomic Location: {variant.categories}")
    print(f"Variant Type: {variant.semantic_types}")
    print(f"Assembly: {[c for c in variant.categories if 'assembly' in c.lower()]}")
```

### Search by Genomic Location
```python
# Search for variants in a specific genomic region
results = await adapter.search_concepts("6[Chr] AND (1500000:3000000[ChrPos])")
```

### Search by Clinical Phenotype
```python
# Search for pathogenic variants associated with autism
results = await adapter.search_concepts("((Pathogenic[Clinical Interpretation]) OR (Likely pathogenic[Clinical Interpretation])) AND autism[Clinical Phenotype]")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent concept IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("CHR22")
    if not results:
        logger.info("No structural variants found for CHR22")
except Exception as e:
    logger.error(f"DBVar search failed: {e}")
```

## Rate Limiting

**NCBI EUtils Rate Limits:**
- Free tier: 3 requests per second
- With API key: 10 requests per second

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect NCBI's rate limits
- Implement exponential backoff for retry logic
- Consider using EUtils with an API key for higher limits

```python
# The adapter automatically handles rate limiting through the base class
# Additional rate limiting can be configured in LookupConfig
```

## Data Model Mapping

| dbVar Field | UnifiedConcept Mapping |
|-------------|----------------------|
| `uid` | `primary_id` (as `dbVar:{uid}`) |
| `title` | `primary_label` |
| `variant_type` | `semantic_types.append(variant_type)` |
| `chromosome` | `categories.append("chromosome:{chr}")` |
| `start_position` | `categories.append("position:start:{pos}")` |
| `end_position` | `categories.append("position:end:{pos}")` |
| `assembly` | `categories.append("assembly:{assembly_name}")` |
| `variant_size` | `categories.append("size:{size_bp}bp")` |
| `clinical_significance` | `categories.append("clinical_significance:{sig}")` |
| `phenotype` | `categories.append("phenotype:{phenotype}")` |
| `study_id` | `identifiers.append(KnowledgeSource.DBVAR, study_id)` |
| `method` | `source_data['method']` |

## Notes

### Implementation Considerations

1. **NCBI EUtils Integration**: dbVar data is accessed through NCBI's EUtils API, similar to ClinVar. The adapter uses the same patterns for consistency.

2. **Data Structure**: dbVar stores structural variants with complex genomic coordinates including breakpoints, assembly information, and study metadata.

3. **Variant Types**: Supports various structural variant types including:
   - Copy number variations (CNVs)
   - Insertions and deletions (indels)
   - Inversions
   - Translocations
   - Mobile element insertions
   - Complex rearrangements

4. **Clinical Data**: dbVar includes clinical interpretations and phenotype associations for variants, though less comprehensive than ClinVar.

5. **Study Context**: Each variant is linked to specific studies and datasets, providing provenance and methodology information.

6. **Genomic Resolution**: Unlike ClinVar which focuses on SNVs and small variants, dbVar specializes in structural variants >50 bp.

7. **Data Volume**: dbVar contains large volumes of structural variant data from multiple studies including 1000 Genomes, DGV, and clinical studies.

### Planned Enhancements

- [ ] Add support for batch variant lookups
- [ ] Implement study metadata retrieval
- [ ] Add support for genomic range queries
- [ ] Enhance clinical significance parsing
- [ ] Support for variant consequence prediction

### Related Resources

- **ClinVar Adapter**: For SNVs and small variants (complementary to dbVar)
- **dbSNP**: For single nucleotide polymorphisms
- **DGV (Database of Genomic Variants)**: Alternative source for structural variation data
- **NCBI Variation Portal**: Web interface for exploring dbVar and ClinVar data

## References

- [dbVar Overview](https://www.ncbi.nlm.nih.gov/dbvar/)
- [NCBI EUtils API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [NCBI Variation Portal](https://www.ncbi.nlm.nih.gov/variation/)
- [dbVar Documentation](https://www.ncbi.nlm.nih.gov/dbvar/documentation/)
