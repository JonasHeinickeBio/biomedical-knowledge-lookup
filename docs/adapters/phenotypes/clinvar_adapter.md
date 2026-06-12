# ClinVar Adapter

## Overview

The ClinVar Adapter provides access to ClinVar, NCBI's database of genomic variation and its relationship to human health. It enables searching for clinical variants and retrieving detailed information about specific variants including their clinical significance, associated genes, and conditions.

### Purpose
- Search for clinical variants (SNPs, insertions, deletions, CNVs)
- Retrieve clinical significance classifications
- Access gene-variant-disease relationships
- Support precision medicine and genetic research applications

### Scope
- Variant-level data from ClinVar
- Clinical interpretations and assertions
- Gene and condition associations
- Support for NCBI EUtils API integration

## Key Features

- **Variant Search**: Search ClinVar by gene name, condition, or variant description
- **Detailed Variant Information**: Get comprehensive variant details including clinical significance
- **Clinical Significance Classification**: Access ACMG-classified pathogenicity assessments
- **Gene-Condition Links**: Retrieve associated genes and medical conditions
- **Variant Type Classification**: Support for various variant types (SNV, insertion, deletion, etc.)

## API Information

### Endpoint
- **Base URL**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`
- **ClinVar REST API**: `https://clinvar.ncbi.nlm.nih.gov/api/rest`

### Authentication
- **Required**: No
- **API Key**: Not required (public NCBI service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search ClinVar for clinical variants matching the query.

**Parameters:**
- `query` (str): Search term (gene name, condition, variant description)
- `limit` (int): Maximum number of results (default: 20, max: 20)

**Returns:**
- List of `UnifiedConcept` objects representing variants

**Example:**
```python
concepts = await adapter.search_concepts("BRCA1")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific ClinVar variant.

**Parameters:**
- `concept_id` (str): ClinVar variant ID (e.g., "ClinVar:143100" or just "143100")

**Returns:**
- `UnifiedConcept` with full variant details, or `None` if not found

**Example:**
```python
variant = await adapter.get_concept_details("ClinVar:143100")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.clinvar_adapter import ClinVarAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = ClinVarAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.clinvar_adapter import ClinVarAdapter

adapter = ClinVarAdapter(config)

# Search for BRCA1 variants
results = await adapter.search_concepts("BRCA1", limit=10)

for concept in results:
    print(f"Variant: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Categories: {concept.categories}")
```

### Get Variant Details
```python
# Get detailed information for a specific variant
variant = await adapter.get_concept_details("ClinVar:VCV000143100")

if variant:
    print(f"Title: {variant.primary_label}")
    print(f"Clinical Significance: {variant.categories}")
    print(f"Genes: {[c for c in variant.categories if c.startswith('gene:')]}")
    print(f"Conditions: {[c for c in variant.categories if c.startswith('condition:')]}")
```

### Search by Condition
```python
# Search for variants associated with breast cancer
results = await adapter.search_concepts("breast cancer")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent concept IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("BRCA1")
    if not results:
        logger.info("No variants found for BRCA1")
except Exception as e:
    logger.error(f"ClinVar search failed: {e}")
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

| ClinVar Field | UnifiedConcept Mapping |
|--------------|----------------------|
| `uid` | `primary_id` (as `ClinVar:{uid}`) |
| `title` | `primary_label` |
| `clinical_significance.description` | `categories.append("clinical_significance:{sig}")` |
| `gene_sort` | `categories.append("gene:{gene}")` |
| `obj_type` | `semantic_types.append(variation_type)` |
| `trait_set.trait_name` | `categories.append("condition:{condition}")` |
| `variation_name` | Included in `primary_label` |

## Related Adapters

- **HGNC Adapter**: For gene nomenclature and identifiers
- **OMIM Adapter**: For Mendelian disease associations
- **GeneOntology Adapter**: For functional annotations
- **Uniprot Adapter**: For protein-level variant impact

## References

- [ClinVar Documentation](https://www.ncbi.nlm.nih.gov/clinvar/docs/api_http/)
- [NCBI EUtils API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [ClinVar REST API](https://clinvar.ncbi.nlm.nih.gov/api/)
