# COSMIC Adapter

## Overview

The COSMIC Adapter provides access to the Catalogue Of Somatic Mutations In Cancer (COSMIC), the world's largest and most comprehensive resource for exploring the impact of somatic mutations in human cancer. It enables searching for cancer genes, mutations, and their clinical implications.

### Purpose
- Search for cancer-associated genes and mutations
- Retrieve somatic mutation data from tumor samples
- Access cancer gene census information
- Support cancer genomics and precision oncology research

### Scope
- Cancer genes and their roles in oncology
- Somatic mutations with clinical significance
- Drug resistance and sensitivity data
- Tumor type associations
- Cancer predisposition genes

## Key Features

- **Cancer Gene Search**: Search COSMIC for genes associated with cancer
- **Mutation Data**: Access somatic mutation information with tissue specificity
- **Role in Cancer**: Retrieve functional role (oncogene, tumor suppressor, etc.)
- **Tier Classification**: Access COSMIC's tier system for cancer genes
- **Hallmark Annotations**: Get cancer hallmark pathway information
- **Synonym Resolution**: Access multiple gene nomenclatures and aliases

## API Information

### Endpoint
- **Base URL**: `https://cancer.sanger.ac.uk/api/rest/cosmic`

### Authentication
- **Required**: Optional (full data access requires authentication)
- **API Key**: Set via `COSMIC_API_KEY` environment variable or config

### Environment Variables
- `COSMIC_API_KEY`: API key for authenticated access (optional but recommended)

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search COSMIC for cancer genes and somatic mutations matching the query.

**Parameters:**
- `query` (str): Search term (gene name, mutation, cancer type)
- `limit` (int): Maximum number of results (default: 20, max: 25)

**Returns:**
- List of `UnifiedConcept` objects representing cancer genes/mutations

**Example:**
```python
concepts = await adapter.search_concepts("BRAF")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific COSMIC gene entry.

**Parameters:**
- `concept_id` (str): COSMIC gene ID (e.g., "COSMIC:719" for BRAF)

**Returns:**
- `UnifiedConcept` with full gene details, or `None` if not found

**Example:**
```python
gene = await adapter.get_concept_details("COSMIC:719")
```

## Configuration

Configure the adapter with optional API key authentication:

```python
from knowledge_lookup.adapters.cosmic_adapter import COSMICAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
# Optional: Set API key via environment variable
# export COSMIC_API_KEY="your_api_key_here"
adapter = COSMICAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.cosmic_adapter import COSMICAdapter

adapter = COSMICAdapter(config)

# Search for BRAF in COSMIC
results = await adapter.search_concepts("BRAF", limit=5)

for concept in results:
    print(f"Gene: {concept.primary_label}")
    print(f"Role in Cancer: {concept.categories}")
    print(f"Tier: {concept.categories}")
```

### Get Gene Details
```python
# Get detailed information for BRAF
gene = await adapter.get_concept_details("COSMIC:719")

if gene:
    print(f"Gene: {gene.primary_label}")
    print(f"Roles: {[c for c in gene.categories if c.startswith('role_in_cancer:')]}")
    print(f"Tier: {[c for c in gene.categories if c.startswith('tier:')}])")
    print(f"Synonyms: {gene.synonyms}")
```

### Search by Mutation
```python
# Search for mutations in a specific gene
results = await adapter.search_concepts("V600E")
```

### Search by Cancer Type
```python
# Search for genes associated with melanoma
results = await adapter.search_concepts("melanoma")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Authentication Errors**: Gracefully handles missing API keys
- **Invalid IDs**: Returns `None` for non-existent gene IDs
- **Network Errors**: Caught and logged, returns empty list
- **Data Parsing Errors**: Graceful handling with error logging

```python
try:
    results = await adapter.search_concepts("BRAF")
    if not results:
        logger.info("No COSMIC entries found for BRAF")
except Exception as e:
    logger.error(f"COSMIC search failed: {e}")
```

## Rate Limiting

**COSMIC API Rate Limits:**
- Rate limits are imposed by the COSMIC service
- Unauthenticated requests have limited access
- Authenticated requests have higher limits

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect COSMIC's rate limits
- Implement request throttling for bulk operations
- Use authenticated access for production workloads

```python
# The adapter automatically handles rate limiting through the base class
# Consider setting API key for higher rate limits
```

## Data Model Mapping

| COSMIC Field | UnifiedConcept Mapping |
|-------------|----------------------|
| `id` / `cosmic_id` | `primary_id` (as `COSMIC:{id}`) |
| `gene_name` / `name` | `primary_label` |
| `role_in_cancer` | `categories.append("role_in_cancer:{role}")` |
| `tier` | `categories.append("tier:{tier}")` |
| `synonyms` | `synonyms.extend(synonyms)` |
| `hallmarks.hallmark` | `semantic_types.append(hallmark)` |

## Related Adapters

- **ClinVar Adapter**: For germline variant data
- **OMIM Adapter**: For Mendelian disease genes
- **Uniprot Adapter**: For protein-level mutation impact
- **DrugBank Adapter**: For targeted therapy drugs

## References

- [COSMIC Documentation](https://cancer.sanger.ac.uk/cosmic/download/api)
- [COSMIC Database](https://cancer.sanger.ac.uk/cosmic)
- [Cancer Gene Census](https://cancer.sanger.ac.uk/census)
