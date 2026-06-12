# EuropePMC Adapter

## Overview

The EuropePMC Adapter provides access to Europe PubMed Central (EuropePMC), a comprehensive literature and citation database covering life sciences and biomedical research. It enables searching for scientific publications and retrieving detailed article information including abstracts, authors, and citations.

### Purpose
- Search for biomedical literature and publications
- Retrieve article metadata and abstracts
- Access author and citation information
- Support literature review and evidence-based research

### Scope
- Life sciences and biomedical research articles
- Journal articles, conference proceedings, patents
- Article abstracts and full-text availability
- Author lists and affiliations
- Publication years and journal information
- DOI and PMID identifiers
- Cross-references to other databases

## Key Features

- **Literature Search**: Search EuropePMC for publications by keyword
- **Article Metadata**: Retrieve comprehensive article information
- **Abstract Access**: Get article abstracts (up to 1000 chars)
- **Author Information**: Retrieve author lists and details
- **Journal Data**: Access journal names and publication years
- **DOI and PMID**: Get publication identifiers
- **Citation Support**: Access cited references and citing articles

## API Information

### Endpoint
- **Base URL**: `https://www.ebi.ac.uk/europepmc/webservices/rest`

### Authentication
- **Required**: No
- **API Key**: Not required (public EMBL-EBI service)

### Environment Variables
- None required

## Key Methods

### `search_concepts(query, limit=20) -> list[UnifiedConcept]`

Search EuropePMC for literature matching the query.

**Parameters:**
- `query` (str): Search term (keyword, author, journal, etc.)
- `limit` (int): Maximum number of results (default: 20, max: 25)

**Returns:**
- List of `UnifiedConcept` objects representing publications

**Example:**
```python
concepts = await adapter.search_concepts("cancer immunotherapy")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Get detailed information about a specific EuropePMC article.

**Parameters:**
- `concept_id` (str): Article ID (e.g., "PMID:12345678" or "12345678" or "MED:12345678")

**Returns:**
- `UnifiedConcept` with full article details, or `None` if not found

**Example:**
```python
article = await adapter.get_concept_details("PMID:12345678")
```

## Configuration

The adapter requires no special configuration beyond the base `LookupConfig`.

```python
from knowledge_lookup.adapters.europepmc_adapter import EuropePMCAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
adapter = EuropePMCAdapter(config)
```

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.europepmc_adapter import EuropePMCAdapter

adapter = EuropePMCAdapter(config)

# Search for cancer immunotherapy articles
results = await adapter.search_concepts("cancer immunotherapy", limit=10)

for concept in results:
    print(f"Title: {concept.primary_label}")
    print(f"ID: {concept.primary_id}")
    print(f"Year: {concept.categories}")
```

### Get Article Details
```python
# Get detailed information for a specific article
article = await adapter.get_concept_details("PMID:31537800")

if article:
    print(f"Title: {article.primary_label}")
    print(f"Authors: {[c for c in article.categories if c.startswith('authors:')}])")
    print(f"Abstract: {article.definitions}")
    print(f"Journal: {[c for c in article.categories if c.startswith('journal:')}])")
    print(f"Year: {[c for c in article.categories if c.startswith('year:')}])")
```

### Search by Author
```python
# Search for publications by a specific author
results = await adapter.search_concepts("Smith J[Author]")
```

### Search by Journal
```python
# Search for articles in a specific journal
results = await adapter.search_concepts("NEJM[journal]")
```

## Error Handling

The adapter implements comprehensive error handling:

- **Search Failures**: Returns empty list on error with logging
- **Invalid IDs**: Returns `None` for non-existent article IDs
- **Network Errors**: Caught and logged, returns appropriate fallback
- **Data Parsing Errors**: Graceful handling with `logger.error` logging

```python
try:
    results = await adapter.search_concepts("cancer")
    if not results:
        logger.info("No EuropePMC entries found for 'cancer'")
except Exception as e:
    logger.error(f"EuropePMC search failed: {e}")
```

## Rate Limiting

**EuropePMC API Rate Limits:**
- Free tier: No strict limits published
- Recommended: 3-5 requests per second

The adapter includes built-in rate limiting via the base class `KnowledgeSourceAdapter`. Implementations should:
- Respect EuropePMC's rate limits
- Implement request throttling for bulk operations
- Consider caching for frequently accessed articles

```python
# The adapter automatically handles rate limiting through the base class
```

## Data Model Mapping

| EuropePMC Field | UnifiedConcept Mapping |
|----------------|----------------------|
| `pmid` / `id` | `primary_id` (as `PMID:{pmid}`) |
| `title` | `primary_label` |
| `authorList.author` | `categories.append("authors:{list}")` |
| `abstractText` | `definitions.append(abstract[:1000])` |
| `journalTitle` | `categories.append("journal:{title}")` |
| `pubYear` | `categories.append("year:{year}")` |
| `doi` | `add_identifier(EUROPEPMC, "DOI:{doi}")` |

## Related Adapters

- **PubMed EUtils Adapter**: For NCBI PubMed access
- **Uniprot Adapter**: For protein-specific literature
- **OMIM Adapter**: For disease-related literature
- **GeneOntology Adapter**: For functional annotation literature

## References

- [EuropePMC RESTful Web Service](https://europepmc.org/RestfulWebService)
- [EuropePMC Website](https://europepmc.org/)
- [EuropePMC Help](https://europepmc.org/help)
