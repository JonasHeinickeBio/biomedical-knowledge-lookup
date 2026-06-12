# OpenTargets Adapter Documentation

## Overview

The OpenTargets adapter provides access to the Open Targets Platform through its GraphQL API. Open Targets is a public-private partnership that combines genetic, genomic, and chemical data to systematically identify and prioritize drug targets and their relationships to diseases.

The adapter enables searching for and retrieving information about:
- **Targets** (genes/proteins): Drug targets and their biological properties
- **Diseases**: Clinical conditions and their characteristics
- **Target-Disease Associations**: Evidence-based links between targets and diseases

## Key Features

### Core Capabilities
- **Search multiple entity types**: Simultaneously search for targets and diseases
- **Target-focused queries**: Retrieve gene/protein information with biotype classification
- **Disease-focused queries**: Get disease definitions and clinical characteristics
- **Unified concept representation**: Standardized data structure across knowledge sources
- **GraphQL-based API**: Efficient querying with structured responses

### Data Sources
The Open Targets Platform integrates data from:
- **Genetic associations**: GWAS, experimental validations
- **Expert curation**: Manually curated target-disease relationships
- **RNA expression**: Tissue-specific expression profiles
- **Known drugs**: Drug-target interactions from ChEMBL
- **Somatic mutations**: Cancer mutation data from COSMIC
- **Animal models**: Phenotypic data from mouse models

## API Information

### Endpoint
- **Base URL**: `https://api.platform.opentargets.org/api/v4/graphql`
- **Authentication**: None (public API)
- **Rate Limiting**: Applied by Open Targets (see [Rate Limiting](#rate-limiting))
- **Protocol**: GraphQL over HTTPS POST

### API Access Notes
- No API key required for basic access
- Rate limits are enforced per IP address
- GraphQL queries allow precise data specification
- Supports pagination and filtering

## Key Functions

### Core Search Methods

#### `search_concepts(query: str, limit: int = 20) -> List[UnifiedConcept]`

Searches Open Targets for targets and diseases matching the query string.

**Parameters:**
- `query`: Search term (gene symbol, disease name, keyword, etc.)
- `limit`: Maximum number of results to return (default: 20)

**Returns:** `List[UnifiedConcept]` - Concepts matching the query

**Example Data Structure:**
```json
[
  {
    "primary_id": "ENSG00000141510",
    "primary_label": "TNF",
    "concept_type": "GENE",
    "definitions": ["Biotype: protein-coding"],
    "synonyms": ["TNF", "TNFA", "TNF-alpha"],
    "identifiers": [
      {
        "source": "OPENTARGETS",
        "identifier": "ENSG00000141510",
        "label": "TNF",
        "url": "https://platform.opentargets.org/target/ENSG00000141510"
      }
    ],
    "confidence_score": 0.9,
    "source_data": {
      "OPENTARGETS": {
        "id": "ENSG00000141510",
        "name": "TNF",
        "entity": "target",
        "description": "Tumor necrosis factor"
      }
    }
  },
  {
    "primary_id": "EFO_0003928",
    "primary_label": "rheumatoid arthritis",
    "concept_type": "DISEASE",
    "definitions": ["Autoimmune disorder primarily affecting the joints."],
    "identifiers": [
      {
        "source": "OPENTARGETS",
        "identifier": "EFO_0003928",
        "label": "rheumatoid arthritis",
        "url": "https://platform.opentargets.org/disease/EFO_0003928"
      }
    ],
    "confidence_score": 0.9,
    "source_data": {
      "OPENTARGETS": {
        "id": "EFO_0003928",
        "name": "rheumatoid arthritis",
        "entity": "disease",
        "description": "A chronic, systemic autoimmune disease..."
      }
    }
  }
]
```

**Search Examples:**
```python
# Search for a gene
results = await adapter.search_concepts("BRCA1")

# Search for a disease
results = await adapter.search_concepts("diabetes mellitus")

# Search with keyword
results = await adapter.search_concepts("cancer")

# Limit results
results = await adapter.search_concepts("interleukin", limit=10)
```

#### `get_concept_details(concept_id: str) -> UnifiedConcept | None`

Retrieves detailed information about a specific target or disease by its Open Targets ID.

**Parameters:**
- `concept_id`: Open Targets identifier (Ensembl ID for targets, EFO/MONDO/ORPHA for diseases)

**Returns:** `UnifiedConcept` with detailed information, or `None` if not found

**Entity Type Detection:**
The adapter automatically detects entity type based on ID prefix:
- **Targets**: `ENSG*` (Ensembl gene IDs)
- **Diseases**: `EFO_*`, `MONDO_*`, `ORPHA*` (EBI Functional Ontology, Mondo, Orphanet)

**Target Response Example:**
```json
{
  "primary_id": "ENSG00000141510",
  "primary_label": "TNF",
  "concept_type": "GENE",
  "definitions": ["Biotype: protein-coding"],
  "synonyms": ["TNF", "TNFA"],
  "identifiers": [
    {
      "source": "OPENTARGETS",
      "identifier": "ENSG00000141510",
      "label": "TNF",
      "url": "https://platform.opentargets.org/target/ENSG00000141510"
    }
  ],
  "confidence_score": 0.9,
  "source_data": {
    "OPENTARGETS": {
      "id": "ENSG00000141510",
      "approvedSymbol": "TNF",
      "biotype": "protein-coding"
    }
  }
}
```

**Disease Response Example:**
```json
{
  "primary_id": "EFO_0003928",
  "primary_label": "rheumatoid arthritis",
  "concept_type": "DISEASE",
  "definitions": ["Autoimmune disorder primarily affecting the joints."],
  "identifiers": [
    {
      "source": "OPENTARGETS",
      "identifier": "EFO_0003928",
      "label": "rheumatoid arthritis",
      "url": "https://platform.opentargets.org/disease/EFO_0003928"
    }
  ],
  "confidence_score": 0.9,
  "source_data": {
    "OPENTARGETS": {
      "id": "EFO_0003928",
      "name": "rheumatoid arthritis",
      "definition": "A chronic, systemic autoimmune disease..."
    }
  }
}
```

### Helper Methods

#### `is_available() -> bool`

Check if the Open Targets API is accessible.

**Returns:** `bool` - True if the API endpoint is reachable

**Example:**
```python
if adapter.is_available():
    results = await adapter.search_concepts("interleukin")
else:
    print("Open Targets API is currently unavailable")
```

**Note:** Currently always returns `True` as Open Targets is a public API. Consider implementing health check if API availability needs to be verified.

#### `get_rate_limit() -> float`

Get the rate limit for this source in requests per second.

**Returns:** `float` - Rate limit (default: 1.0 from config)

**Note:** Rate limiting is configured via `LookupConfig.rate_limits[KnowledgeSource.OPENTARGETS]`.

## Data Structures

### UnifiedConcept Fields

The OpenTargetsAdapter populates the following `UnifiedConcept` fields:

#### Core Identification
- `primary_id`: Open Targets identifier (Ensembl gene ID or EFO/MONDO/ORPHA disease ID)
- `primary_label`: Human-readable name (gene symbol for targets, disease name for diseases)
- `concept_type`: `GENE` for targets, `DISEASE` for diseases

#### Definitions and Descriptions
- `definitions`: 
  - Targets: List containing biotype information (e.g., `["Biotype: protein-coding"]`)
  - Diseases: List containing disease definitions from source
- `synonyms`: Approved symbols/synonyms for the concept

#### Cross-references
- `identifiers`: List of `ConceptIdentifier` objects with:
  - Source: `OPENTARGETS`
  - Identifier: The primary ID
  - Label: The primary label
  - URL: Direct link to Open Targets platform page

#### Metadata
- `confidence_score`: Fixed at 0.9 for all concepts
- `source_data`: Complete raw response from Open Targets API

### Open Targets Response Fields

The adapter extracts data from the following Open Targets GraphQL response fields:

#### For Targets
| Field | Description | Mapped to |
|-------|-------------|-----------|
| `id` | Ensembl gene ID | `primary_id` |
| `approvedSymbol` | HGNC approved symbol | `primary_label`, `synonyms` |
| `biotype` | Gene biotype (protein-coding, lncRNA, etc.) | `definitions` |

#### For Diseases
| Field | Description | Mapped to |
|-------|-------------|-----------|
| `id` | EFO/MONDO/ORPHA ID | `primary_id` |
| `name` | Disease name | `primary_label` |
| `definition` | Disease definition/description | `definitions` |

#### Search Results (search.hits)
| Field | Description |
|-------|-------------|
| `id` | Entity identifier |
| `name` | Entity name/label |
| `entity` | Entity type ("target" or "disease") |
| `description` | Brief description (if available) |

## Configuration

### Basic Configuration

```python
from knowledge_lookup import LookupConfig, KnowledgeSource
from knowledge_lookup.adapters.opentargets_adapter import OpenTargetsAdapter

# Create configuration
config = LookupConfig()

# Optional: Set rate limit for Open Targets (requests per second)
config.rate_limits[KnowledgeSource.OPENTARGETS] = 2.0

# Initialize adapter
adapter = OpenTargetsAdapter(config)
```

### Rate Limiting

Open Targets enforces rate limits on their GraphQL API. Configure appropriate limits:

```python
# Configure rate limiting (requests per second)
config = LookupConfig()
config.rate_limits[KnowledgeSource.OPENTARGETS] = 1.0  # Default: 1 req/s

# For higher throughput (check Open Targets rate limits)
config.rate_limits[KnowledgeSource.OPENTARGETS] = 5.0
```

**Recommended Settings:**
- **Default**: 1.0 requests/second (conservative)
- **Moderate**: 2.0-3.0 requests/second
- **High**: 5.0 requests/second (use with caution)

### Timeout Configuration

```python
# Set per-source timeout (seconds)
config.timeout_per_source = 30.0  # Default
```

## Usage Examples

### Basic Search

```python
import asyncio
from knowledge_lookup import LookupConfig, KnowledgeSource
from knowledge_lookup.adapters.opentargets_adapter import OpenTargetsAdapter

async def main():
    config = LookupConfig()
    adapter = OpenTargetsAdapter(config)
    
    # Search for targets and diseases
    results = await adapter.search_concepts("interleukin", limit=10)
    
    for concept in results:
        print(f"{concept.primary_label} ({concept.primary_id})")
        print(f"  Type: {concept.concept_type.value}")
        print(f"  URL: {concept.get_identifier(KnowledgeSource.OPENTARGETS).url}")

asyncio.run(main())
```

### Get Detailed Target Information

```python
async def get_target_details():
    config = LookupConfig()
    adapter = OpenTargetsAdapter(config)
    
    # Get detailed information for a specific target
    target_id = "ENSG00000141510"  # TNF gene
    target = await adapter.get_concept_details(target_id)
    
    if target:
        print(f"Target: {target.primary_label}")
        print(f"Biotype: {target.definitions[0]}")
        print(f"Synonyms: {target.synonyms}")

asyncio.run(get_target_details())
```

### Disease Information Lookup

```python
async def get_disease_details():
    config = LookupConfig()
    adapter = OpenTargetsAdapter(config)
    
    # Get detailed information for a specific disease
    disease_id = "EFO_0003928"  # Rheumatoid arthritis
    disease = await adapter.get_concept_details(disease_id)
    
    if disease:
        print(f"Disease: {disease.primary_label}")
        print(f"Definition: {disease.definitions[0]}")

asyncio.run(get_disease_details())
```

### Combined Search and Filter

```python
async def search_and_filter():
    config = LookupConfig()
    adapter = OpenTargetsAdapter(config)
    
    # Search for cancer-related concepts
    results = await adapter.search_concepts("cancer", limit=20)
    
    # Filter by concept type
    genes = [c for c in results if c.concept_type == ConceptType.GENE]
    diseases = [c for c in results if c.concept_type == ConceptType.DISEASE]
    
    print(f"Found {len(genes)} genes and {len(diseases)} diseases")

asyncio.run(search_and_filter())
```

### Check API Availability

```python
async def check_availability():
    config = LookupConfig()
    adapter = OpenTargetsAdapter(config)
    
    if adapter.is_available():
        print("Open Targets API is available")
        results = await adapter.search_concepts("diabetes")
    else:
        print("Open Targets API is currently unavailable")

asyncio.run(check_availability())
```

## Error Handling

### Common Error Scenarios

#### 1. Network/Connection Errors
```python
from knowledge_lookup.base import KnowledgeSourceAdapter

try:
    results = await adapter.search_concepts("invalid query")
except aiohttp.ClientError as e:
    print(f"Network error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

#### 2. Invalid Concept IDs
```python
concept = await adapter.get_concept_details("INVALID_ID")
if concept is None:
    print("Concept not found or invalid ID format")
```

#### 3. GraphQL API Errors
```python
try:
    results = await adapter.search_concepts("query")
except Exception as e:
    logger.error(f"Open Targets search failed: {e}")
    results = []  # Return empty list on error
```

### Error Handling Patterns

The adapter implements:
- **Graceful degradation**: Returns empty list on search errors
- **None returns**: Returns `None` for `get_concept_details` on failure
- **Logging**: Comprehensive error logging with context
- **Exception wrapping**: Logs original exceptions with context

### Logging

Enable logging to capture adapter operations:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('knowledge_lookup.adapters.opentargets_adapter')

# Now adapter operations will log:
# - Search queries and result counts
# - Errors with concept IDs
# - Conversion failures
```

## Rate Limiting Considerations

### Open Targets Rate Limits

The Open Targets Platform GraphQL API enforces rate limits. Best practices:

#### 1. Respect Default Limits
- Default rate: ~1 request per second
- Burst limits may allow short bursts of requests
- Monitor for 429 (Too Many Requests) responses

#### 2. Implement Retry Logic
```python
import asyncio
from functools import wraps

def with_rate_limiting(max_retries=3, base_delay=1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except aiohttp.ClientResponseError as e:
                    if e.status == 429:
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limited, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        raise
            raise Exception("Max retries exceeded due to rate limiting")
        return wrapper
    return decorator
```

#### 3. Use Asyncio Semaphores
```python
import asyncio

class RateLimitedAdapter:
    def __init__(self, adapter, max_concurrent=2):
        self.adapter = adapter
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def search_concepts(self, *args, **kwargs):
        async with self.semaphore:
            return await self.adapter.search_concepts(*args, **kwargs)
```

### Monitoring Rate Limits

Track rate limit usage:
```python
import time

class RateLimitedAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
        self.request_times = []
    
    async def search_concepts(self, *args, **kwargs):
        # Clean old requests (older than 1 second)
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 1.0]
        
        if len(self.request_times) >= 2:  # 2 requests per second
            await asyncio.sleep(1.0 - (now - self.request_times[0]))
        
        self.request_times.append(now)
        return await self.adapter.search_concepts(*args, **kwargs)
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTargetsAdapter                       │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ search_concepts│  │get_concept_details│  │is_available  │ │
│  └────────┬───────┘  └────────┬─────────┘  └──────────────┘ │
│           │                   │                               │
│           ▼                   ▼                               ▼
│    ┌──────────────┐    ┌──────────────┐              ┌────────┐ │
│    │ GraphQL      │    │ GraphQL      │              │ HTTP   │ │
│    │ Query        │    │ Query        │              │ GET    │ │
│    │ Construction │    │ Construction │              │ /health│ │
│    └───────┬──────┘    └───────┬──────┘              └────────┘ │
│            │                   │                               │
│            ▼                   ▼                               ▼
│    ┌──────────────┐    ┌──────────────┐              ┌────────┐ │
│    │ HTTP Request │    │ HTTP Request │              │ Status │ │
│    │ (POST)       │    │ (POST)       │              │ Check  │ │
│    └───────┬──────┘    └───────┬──────┘              └────────┘ │
│            │                   │                               │
│            ▼                   ▼                               ▼
│    ┌──────────────┐    ┌──────────────┐              ┌────────┐ │
│    │ Open Targets │    │ Open Targets │              │ API    │ │
│    │ GraphQL API  │    │ GraphQL API  │              │ URL:   │ │
│    │              │    │              │              │ https://│ │
│    └──────────────┘    └──────────────┘              │api.opent │ │
│                                                      │argets.or │ │
│                                                      │g/api/v4/ │ │
│                                                      │graphql   │ │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │Data         │
                    │Conversion   │
                    │to           │
                    │UnifiedConcep│
                    │t           │
                    └──────────────┘
```

### Data Flow

1. **Input**: Query string or concept ID
2. **GraphQL Construction**: Build appropriate query
3. **API Request**: POST to Open Targets GraphQL endpoint
4. **Response Parsing**: Extract data from GraphQL response
5. **Conversion**: Map to `UnifiedConcept` structure
6. **Output**: Return concepts with standardized format

## Integration with CentralKnowledgeLookup

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

# Initialize central lookup
lookup = CentralKnowledgeLookup()

# Query Open Targets via central lookup
result = await lookup.search_concepts(
    query="diabetes",
    sources=[KnowledgeSource.OPENTARGETS]
)

for concept in result.concepts:
    print(f"{concept.primary_label}: {concept.concept_type.value}")
```

## Comparison with Other Adapters

| Feature | OpenTargets | UMLS | MONDO | DisGeNET |
|---------|-------------|------|-------|----------|
| **Authentication** | None | UMLS API key | None | DisGeNET API key |
| **Search Scope** | Targets + Diseases | All UMLS vocabularies | Diseases only | Gene-disease associations |
| **Entity Types** | GENE, DISEASE | All UMLS semantic types | DISEASE | DISEASE |
| **API Type** | GraphQL | REST | REST | REST |
| **Primary Use** | Target-disease evidence | Concept normalization | Disease standardization | Gene-disease links |
| **Rate Limiting** | Applied | Variable | Applied | Applied |

## Limitations

### Current Implementation
- **No pagination support**: Limited to first N results from search
- **Basic entity details**: Target/disease detail queries are minimal
- **No association queries**: Cannot retrieve target-disease associations directly
- **Fixed confidence score**: All concepts get 0.9 confidence
- **No filtering**: Search returns all matching entities without filtering

### Future Enhancements
- Add pagination for search results
- Support target-disease association queries
- Implement more detailed entity queries (pathways, drugs, etc.)
- Add filtering by entity type in search
- Support additional Open Targets endpoints

## References

- **Open Targets Platform**: https://platform.opentargets.org/
- **Open Targets API Docs**: https://docs.opentargets.org/
- **GraphQL Specification**: https://graphql.org/
- **Source Code**: `src/knowledge_lookup/adapters/opentargets_adapter.py`

## See Also

- [ChEMBL Adapter](chembl_adapter.md) - For drug and compound data
- [DisGeNET Adapter](disgenet_adapter.md) - For gene-disease associations
- [MONDO Adapter](mondo_adapter.md) - For disease ontology data
- [UniProt Adapter](uniprot_adapter.md) - For protein sequence data
