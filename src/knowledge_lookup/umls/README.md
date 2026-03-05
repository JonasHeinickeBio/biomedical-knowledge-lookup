# Unified UMLS Client Documentation

## Overview

The **OptimizedUMLSClient** is a unified, fully optimized Python client for interacting with the Unified Medical Language System (UMLS) API. This client combines both low-level API communication and high-level service coordination into a single, efficient interface for medical concept search, retrieval, and analysis.

## Architecture

### 🏗️ **Unified Design**

- **Single Client Interface**: All functionality accessible through one `OptimizedUMLSClient` class
- **Integrated API Communication**: Built-in authenticated request handling with retry logic
- **Service Coordination**: Harmonized search, concept, and metadata services
- **Legacy Compatibility**: Maintains backward compatibility with `UMLSApiClient` and `UMLSAPIClient` aliases

### 🔧 **Key Components**

- **OptimizedUMLSClient**: Main unified client with all functionality
- **UMLSAuthenticator**: Token management and authentication
- **Service Modules**: Specialized services for search, concepts, and metadata
- **Protocol-Based Design**: Duck-typed interfaces for maximum flexibility

## Features

### 🚀 **Core Features**

- **Cached Authentication**: Automatic TGT (Ticket Granting Ticket) caching with configurable expiration
- **Rate Limiting**: Configurable request rate limiting to respect API limits
- **Retry Logic**: Automatic retry with exponential backoff for failed requests
- **Comprehensive Search**: Multiple search types (exact, approximate, words, truncation)
- **Batch Operations**: Efficient batch processing for multiple queries
- **Error Handling**: Robust error handling with detailed logging

### 🔍 **Search Capabilities**

- **Concept Search**: Search for medical concepts by name/description
- **Semantic Type Filtering**: Filter results by semantic types (e.g., Disease, Symptom)
- **Source Vocabulary Filtering**: Search within specific vocabularies (SNOMED CT, ICD, etc.)
- **Flexible Search Types**: Words, exact, approximate, left/right truncation

### 📊 **Data Retrieval**

- **Concept Details**: Complete concept information including definitions, synonyms
- **Relationship Mapping**: Parent-child relationships and semantic relationships
- **Atom Retrieval**: All terms/atoms for a concept across vocabularies
- **Hierarchy Navigation**: Explore concept hierarchies
- **Similar Concept Discovery**: Find related concepts

### 🛠 **Advanced Features**

- **Code Lookup**: Convert source-specific codes to CUIs
- **Metadata Access**: Retrieve available semantic types and source vocabularies
- **Performance Monitoring**: Built-in statistics and performance tracking
- **Factory Pattern**: Convenient client creation with `create_umls_client()`

## Installation and Setup

### Prerequisites

```bash
pip install requests python-dotenv tenacity
```

### Environment Configuration

Create a `.env` file in your project root:

```env
UMLS_API_KEY_TU=your_umls_api_key_here
```

### Basic Usage

```python
from aid_pais_knowledgegraph.umls import create_umls_client

# Create client (all functionality in one interface)
client = create_umls_client()

# Search for concepts
results = client.search_concepts("diabetes")

# Get detailed information
concept = client.get_concept_details(results[0].cui)

# Make direct API calls
api_data = client.make_request("/content/current/CUI/C0011849")

# Access statistics
stats = client.get_statistics()
```

## Unified Client Benefits

### 🎯 **Simplified Interface**

- **Single Import**: All functionality from one `OptimizedUMLSClient` class
- **Unified API**: Both high-level methods and low-level `make_request()` available
- **Legacy Support**: Existing code using `UMLSApiClient` or `UMLSAPIClient` continues to work
- **Duck Typing**: Services accept any object with `make_request()` method

### ⚡ **Performance Optimizations**

- **Eliminated Redundancy**: Removed duplicate API client implementations
- **Direct Communication**: No intermediate API client layer
- **Optimized Memory**: Single client instance handles all operations
- **Faster Initialization**: Streamlined component initialization
from aid_pais_knowledgegraph.umls.client import create_umls_client

# Initialize client

client = create_umls_client()

# Search for concepts

results = client.search_concepts("diabetes", page_size=10)
for result in results:
    print(f"{result.cui}: {result.name}")

```

## API Reference

### Client Initialization

#### `OptimizedUMLSClient(api_key, version, timeout, max_retries, rate_limit, cache_duration)`
```python
client = OptimizedUMLSClient(
    api_key="your_api_key",          # UMLS API key
    version="current",               # UMLS version
    timeout=30.0,                    # Request timeout in seconds
    max_retries=3,                   # Number of retry attempts
    rate_limit=0.1,                  # Seconds between requests
    cache_duration=3600              # TGT cache duration in seconds
)
```

#### `create_umls_client(**kwargs)`

Factory function for convenient client creation:

```python
client = create_umls_client(rate_limit=0.2, timeout=45.0)
```

### Search Operations

#### `search_concepts(query, search_type, source, semantic_types, page_size, page_number, return_id_type)`

```python
# Basic search
results = client.search_concepts("fatigue")

# Advanced search with filters
results = client.search_concepts(
    query="diabetes",
    search_type="exact",               # "words", "exact", "approximate", etc.
    source="SNOMEDCT_US",             # Specific vocabulary
    semantic_types=["T047"],          # Disease or Syndrome
    page_size=25,                     # Results per page
    page_number=1,                    # Page number
    return_id_type="concept"          # Type of ID to return
)
```

**Search Types:**

- `"words"`: Word-based search (default)
- `"exact"`: Exact string match
- `"approximate"`: Fuzzy matching
- `"leftTruncation"`: Left truncation matching
- `"rightTruncation"`: Right truncation matching

#### `batch_search(queries, **kwargs)`

```python
# Batch search for multiple terms
queries = ["diabetes", "hypertension", "asthma"]
results = client.batch_search(queries, page_size=5)

for query, search_results in results.items():
    print(f"{query}: {len(search_results)} results")
```

### Concept Information

#### `get_concept_details(cui)`

```python
concept = client.get_concept_details("C0011849")  # Diabetes CUI

if concept:
    print(f"Name: {concept.name}")
    print(f"Semantic Types: {concept.semantic_types}")
    print(f"Definitions: {concept.definitions}")
    print(f"Synonyms: {concept.synonyms}")
    print(f"Sources: {concept.sources}")
```

#### `get_concept_atoms(cui, source)`

```python
# Get all terms/atoms for a concept
atoms = client.get_concept_atoms("C0011849")

# Get atoms from specific source
snomed_atoms = client.get_concept_atoms("C0011849", source="SNOMEDCT_US")
```

#### `get_concept_relationships(cui, include_related)`

```python
# Get all relationships
relationships = client.get_concept_relationships("C0011849")

# Get relationships including related concepts
detailed_rels = client.get_concept_relationships("C0011849", include_related=True)
```

### Hierarchy and Relationships

#### `get_concept_hierarchy(cui, levels)`

```python
hierarchy = client.get_concept_hierarchy("C0011849")

print(f"Parents: {len(hierarchy['parents'])}")
print(f"Children: {len(hierarchy['children'])}")

for parent in hierarchy['parents']:
    print(f"  Parent: {parent['name']} ({parent['cui']})")
```

#### `find_similar_concepts(cui, similarity_threshold)`

```python
similar = client.find_similar_concepts("C0011849", similarity_threshold=0.8)

for concept in similar:
    print(f"Similar: {concept['name']} ({concept['cui']})")
```

### Metadata Operations

#### `get_semantic_types()`

```python
semantic_types = client.get_semantic_types()
for st in semantic_types[:5]:  # First 5
    print(f"{st.get('ui', '')}: {st.get('name', '')}")
```

#### `get_sources()`

```python
sources = client.get_sources()
for source in sources[:5]:  # First 5
    print(f"{source.get('rootSource', '')}: {source.get('name', '')}")
```

### Code Conversion

#### `get_cui_from_code(code, source)`

```python
# Convert SNOMED CT code to CUI
cui = client.get_cui_from_code("73211009", "SNOMEDCT_US")
if cui:
    print(f"CUI for SNOMED code: {cui}")
```

### Performance and Monitoring

#### `get_statistics()`

```python
stats = client.get_statistics()
print(f"Total requests: {stats['total_requests']}")
print(f"Cache hit ratio: {stats['cache_hit_ratio']:.2f}")
print(f"TGT expires: {stats['tgt_expires']}")
```

#### `reset_statistics()` and `clear_cache()`

```python
# Reset performance counters
client.reset_statistics()

# Clear authentication cache (forces re-authentication)
client.clear_cache()
```

## Data Classes

### UMLSConcept

Represents a complete UMLS concept with all its properties:

```python
@dataclass
class UMLSConcept:
    cui: str                          # Concept Unique Identifier
    name: str                         # Preferred name
    semantic_types: List[str]         # Semantic type names
    definitions: List[str]            # Concept definitions
    synonyms: List[str]               # Alternative terms
    sources: List[str]                # Source vocabularies
    atoms: List[Dict[str, Any]]       # Raw atom data
    relationships: List[Dict[str, Any]] # Relationship data
```

### UMLSSearchResult

Represents a search result:

```python
@dataclass
class UMLSSearchResult:
    cui: str                          # Concept Unique Identifier
    name: str                         # Concept name
    ui: str                           # Unique identifier
    source: str                       # Source vocabulary
    source_concept_id: str            # Source-specific ID
    root_source: str                  # Root source vocabulary
```

## Example Workflows

### 1. Basic Concept Exploration

```python
# Search for a condition
results = client.search_concepts("chronic fatigue syndrome")

if results:
    # Get detailed information
    concept = client.get_concept_details(results[0].cui)

    # Explore hierarchy
    hierarchy = client.get_concept_hierarchy(results[0].cui)

    # Find similar concepts
    similar = client.find_similar_concepts(results[0].cui)
```

### 2. Multi-Source Analysis

```python
# Search across multiple vocabularies
sources = ["SNOMEDCT_US", "ICD10CM", "MSH"]

for source in sources:
    results = client.search_concepts("diabetes", source=source, page_size=3)
    print(f"\n{source}: {len(results)} results")
    for result in results:
        print(f"  {result.cui}: {result.name}")
```

### 3. Semantic Type Analysis

```python
# Get all semantic types
semantic_types = client.get_semantic_types()

# Filter for disease-related types
disease_types = [st for st in semantic_types
                if 'disease' in st.get('name', '').lower()]

# Search using disease semantic types
disease_cuis = [st.get('ui', '') for st in disease_types]
results = client.search_concepts("diabetes", semantic_types=disease_cuis)
```

### 4. Batch Processing Pipeline

```python
# Define conditions to analyze
conditions = [
    "diabetes mellitus",
    "hypertension",
    "chronic fatigue syndrome",
    "fibromyalgia",
    "multiple sclerosis"
]

# Batch search
batch_results = client.batch_search(conditions, page_size=3)

# Process results
for condition, results in batch_results.items():
    print(f"\n=== {condition.upper()} ===")

    if results:
        # Get details for best match
        concept = client.get_concept_details(results[0].cui)

        if concept:
            print(f"Name: {concept.name}")
            print(f"Semantic Types: {', '.join(concept.semantic_types)}")
            print(f"Sources: {', '.join(concept.sources[:3])}")  # First 3 sources
```

## Performance Optimization

### 1. Configure Rate Limiting

```python
# For high-volume applications
client = create_umls_client(rate_limit=0.05)  # 20 requests/second max

# For batch processing
client = create_umls_client(rate_limit=0.2)   # 5 requests/second
```

### 2. Monitor Performance

```python
# Track performance over time
initial_stats = client.get_statistics()

# ... perform operations ...

final_stats = client.get_statistics()
print(f"Requests made: {final_stats['total_requests'] - initial_stats['total_requests']}")
print(f"Cache efficiency: {final_stats['cache_hit_ratio']:.2%}")
```

### 3. Optimize for Large Datasets

```python
# Use batch operations
queries = ["term1", "term2", "term3", ...]
results = client.batch_search(queries, page_size=10)

# Use pagination for large result sets
all_results = []
page = 1
while True:
    page_results = client.search_concepts("diabetes", page_number=page, page_size=100)
    if not page_results:
        break
    all_results.extend(page_results)
    page += 1
```

## Error Handling

The client includes comprehensive error handling:

```python
try:
    results = client.search_concepts("diabetes")
except ValueError as e:
    print(f"Configuration error: {e}")
except RuntimeError as e:
    print(f"API error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

Common error scenarios:

- **Authentication failures**: Invalid API key or expired tokens
- **Rate limiting**: Too many requests too quickly
- **Network issues**: Timeouts or connection errors
- **API errors**: Invalid parameters or service unavailable

## Integration Examples

### With Neo4j Knowledge Graph

```python
from neo4j import GraphDatabase

# Initialize both clients
umls_client = create_umls_client()
neo4j_driver = GraphDatabase.driver("bolt://localhost:7687")

def enrich_symptom_with_umls(symptom_name):
    # Search UMLS
    results = umls_client.search_concepts(symptom_name, page_size=1)

    if results:
        concept = umls_client.get_concept_details(results[0].cui)

        # Store in Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MERGE (s:Symptom {name: $name})
                SET s.cui = $cui,
                    s.semantic_types = $semantic_types,
                    s.umls_sources = $sources
            """,
            name=symptom_name,
            cui=concept.cui,
            semantic_types=concept.semantic_types,
            sources=concept.sources
            )
```

### With DataFrame Processing

```python
import pandas as pd

# Process symptoms DataFrame
df = pd.DataFrame({"symptoms": ["fatigue", "headache", "joint pain"]})

def get_umls_info(symptom):
    results = umls_client.search_concepts(symptom, page_size=1)
    if results:
        return {
            "cui": results[0].cui,
            "umls_name": results[0].name,
            "source": results[0].source
        }
    return {"cui": None, "umls_name": None, "source": None}

# Apply UMLS enrichment
umls_data = df["symptoms"].apply(get_umls_info)
df = pd.concat([df, pd.json_normalize(umls_data)], axis=1)
```

## Testing

The client includes comprehensive test suites:

### Simple Test

```bash
python tests/simple_umls_test.py
```

### Comprehensive Test Suite

```bash
python tests/test_umls_client.py
```

### Direct Module Test

```bash
python -m aid_pais_knowledgegraph.umls.client
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | None | UMLS API key (required) |
| `version` | "current" | UMLS version to use |
| `timeout` | 30.0 | Request timeout in seconds |
| `max_retries` | 3 | Number of retry attempts |
| `rate_limit` | 0.1 | Minimum seconds between requests |
| `cache_duration` | 3600 | TGT cache duration in seconds |

## Semantic Types Reference

Common semantic type abbreviations:

- **T047**: Disease or Syndrome
- **T184**: Sign or Symptom
- **T033**: Finding
- **T046**: Pathologic Function
- **T048**: Mental or Behavioral Dysfunction
- **T191**: Neoplastic Process
- **T037**: Injury or Poisoning

## Source Vocabularies

Common source abbreviations:

- **SNOMEDCT_US**: SNOMED Clinical Terms US Edition
- **ICD10CM**: International Classification of Diseases, 10th Revision, Clinical Modification
- **MSH**: Medical Subject Headings (MeSH)
- **RXNORM**: RxNorm
- **CPT**: Current Procedural Terminology
- **HCPCS**: Healthcare Common Procedure Coding System
- **HPO**: Human Phenotype Ontology
- **NCIT**: NCI Thesaurus

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API key is set in environment
   - Check API key validity at UMLS UTS
   - Ensure network connectivity

2. **Rate Limiting**
   - Increase `rate_limit` parameter
   - Use batch operations for multiple queries
   - Monitor statistics for cache efficiency

3. **Empty Results**
   - Try different search types
   - Check spelling and terminology
   - Use broader semantic type filters

4. **Performance Issues**
   - Enable caching with longer `cache_duration`
   - Use appropriate `page_size` values
   - Monitor request statistics

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

client = create_umls_client()
# Debug information will be printed
```

## License and Attribution

This client is part of the AID-PAIS Knowledge Graph project. When using this client, please cite:

```
AID-PAIS Knowledge Graph Project
Optimized UMLS Client
https://github.com/your-repo/AID-PAIS-KnowledgeGraph
```

The UMLS data used by this client is provided by the National Library of Medicine and requires appropriate licensing for use.

---

For more information, visit the [UMLS Documentation](https://documentation.uts.nlm.nih.gov/rest/home.html) or contact the development team.
