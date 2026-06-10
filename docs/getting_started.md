# Getting Started with Biomedical Knowledge Lookup

A unified framework for accessing multiple biomedical knowledge sources through a consistent API. This guide will help you get up and running quickly.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Searching Concepts](#searching-concepts)
- [Retrieving Concept Details](#retrieving-concept-details)
- [Multi-Source Annotation](#multi-source-annotation)
- [Configuration](#configuration)
- [Working with Results](#working-with-results)
- [Error Handling](#error-handling)
- [Performance Tips](#performance-tips)
- [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements

- **Python Version**: 3.10 or higher
- **Memory**: Minimum 2GB RAM
- **Disk Space**: ~50MB for core library

### Optional Dependencies

- **Jupyter Notebook**: For interactive examples
- **HTTP/2 Support**: For improved performance with some APIs

```bash
# Verify Python version
python --version
# Should show Python 3.10.x or higher

# Check pip availability
pip --version
```

---

## Installation

### Using pip

```bash
pip install biomedical-knowledge-lookup
```

### Using Poetry (Recommended)

```bash
poetry add biomedical-knowledge-lookup
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/your-org/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup

# Install with Poetry
poetry install

# Install development dependencies
poetry install --with dev
```

### Verifying Installation

```python
# Create a test file: test_install.py
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

async def test():
    lookup = CentralKnowledgeLookup()
    print(f"Available sources: {len(KnowledgeSource)}")
    print(f"Lookup initialized: {lookup is not None}")
    await lookup.close()

import asyncio
asyncio.run(test())
```

Run the test:
```bash
python test_install.py
```

---

## Basic Usage

### Initializing the Lookup Engine

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

async def main():
    # Initialize with default configuration
    lookup = CentralKnowledgeLookup()
    
    # Or with custom configuration
    # config = LookupConfig()
    # lookup = CentralKnowledgeLookup(config)
    
    await lookup.close()

asyncio.run(main())
```

### First Search: Diabetes Example

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

async def search_diabetes():
    lookup = CentralKnowledgeLookup()
    
    # Search for diabetes across all sources
    result = await lookup.search_concepts(
        query="diabetes mellitus",
        sources=list(KnowledgeSource)  # Search all sources
    )
    
    print(f"Query: 'diabetes mellitus'")
    print(f"Results found: {result.total_found}")
    print(f"Execution time: {result.execution_time:.2f}s")
    print(f"Sources queried: {len(result.results)}")
    
    # Display top results
    for i, concept in enumerate(result.concepts[:5], 1):
        print(f"\n{i}. {concept.primary_label}")
        print(f"   ID: {concept.primary_id}")
        print(f"   Type: {concept.concept_type.value}")
    
    await lookup.close()

asyncio.run(search_diabetes())
```

---

## Searching Concepts

### Search by Query String

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Basic search
result = await lookup.search_concepts(
    query="BRCA1",
    sources=[KnowledgeSource.OPENTARGETS]
)

# Search with limit
result = await lookup.search_concepts(
    query="insulin",
    sources=[KnowledgeSource.CHEMBL],
    limit=10
)

# Search with offset (pagination)
result = await lookup.search_concepts(
    query="cancer",
    sources=[KnowledgeSource.DISGENET],
    limit=20,
    offset=20  # Get next page
)
```

### Search by Concept ID

```python
# Direct concept lookup by ID
concept = await lookup.get_concept_details(
    concept_id="ENSG00000012048",
    sources=[KnowledgeSource.OPENTARGETS]
)

if concept:
    print(f"Found: {concept.primary_label}")
```

### Search by Entity Type

```python
# Filter by concept type during search
result = await lookup.search_concepts(
    query="diabetes",
    sources=[KnowledgeSource.MONDO],
    concept_types=["disease", "phenotype"]
)
```

### Search Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | *Required* | Search query string |
| `sources` | `List[KnowledgeSource]` | All sources | List of sources to search |
| `limit` | `int` | 20 | Maximum results per source |
| `offset` | `int` | 0 | Pagination offset |
| `concept_types` | `List[str]` | None | Filter by concept types |

---

## Retrieving Concept Details

### Get Detailed Information

```python
from knowledge_lookup import CentralKnowledgeLookup

lookup = CentralKnowledgeLookup()

# Get full concept details
concept = await lookup.get_concept_details(
    concept_id="DOID:9351",  # Type 2 diabetes
    sources=[KnowledgeSource.MONDO]
)

if concept:
    print(f"Label: {concept.primary_label}")
    print(f"Type: {concept.concept_type.value}")
    print(f"Definitions: {len(concept.definitions)}")
    print(f"Synonyms: {len(concept.synonyms)}")
    
    # Access source-specific data
    for identifier in concept.identifiers:
        print(f"{identifier.source.value}: {identifier.id}")
```

### Available Concept Properties

| Property | Type | Description |
|----------|------|-------------|
| `primary_id` | `str` | Primary identifier (source-specific) |
| `primary_label` | `str` | Primary name/label |
| `concept_type` | `ConceptType` | Type (disease, drug, gene, etc.) |
| `definitions` | `List[str]` | Concept definitions |
| `synonyms` | `List[str]` | Alternative names |
| `identifiers` | `List[Identifier]` | All identifiers from all sources |
| `sources` | `List[KnowledgeSource]` | Sources where found |
| `data_sources` | `Dict` | Source-specific data |
| `url` | `str` | Main URL for the concept |

---

## Multi-Source Annotation

### Annotating Text

```python
from knowledge_lookup import MultiSourceAnnotator

# Initialize annotator
annotator = MultiSourceAnnotator()

# Annotate a sentence
sentence = "Type 2 diabetes is associated with insulin resistance"

result = await annotator.annotate_sentence(sentence)

# Process annotations
for concept in result.concepts:
    print(f"Found: {concept.primary_label}")
    print(f"  Span: {concept.span}")
    print(f"  Confidence: {concept.confidence}")
```

### Consensus Annotation

```python
# Get consensus across multiple sources
result = await annotator.annotate_sentence(
    "TP53 mutation in lung cancer",
    sources=[
        KnowledgeSource.OPENTARGETS,
        KnowledgeSource.DISGENET,
        KnowledgeSource.CHEMBL
    ]
)

for consensus in result.consensus_concepts:
    print(f"Consensus Concept: {consensus.primary_concept.primary_label}")
    print(f"  Confidence: {consensus.confidence_level.value}")
    print(f"  Sources: {[s.value for s in consensus.agreeing_sources]}")
    print(f"  Support: {len(consensus.agreeing_sources)}/{len(result.sources)} sources")
```

### Batch Annotation

```python
# Annotate multiple sentences
sentences = [
    "SARS-CoV-2 causes COVID-19",
    "ACE2 is the receptor for SARS-CoV-2",
    "Remdesivir is an antiviral drug"
]

results = await annotator.annotate_sentences(sentences)

for i, result in enumerate(results):
    print(f"Sentence {i+1}: {sentences[i]}")
    print(f"  Concepts found: {len(result.concepts)}")
```

---

## Configuration

### API Keys

Many knowledge sources require API keys. Set them as environment variables:

```bash
# Create .env file
cat > .env << EOF
# Open Targets Platform (free, no auth)
# No API key required

# BioPortal (requires free registration)
BIOPORTAL_API_KEY="your-bioportal-api-key"

# UMLS (requires license)
UMLS_API_KEY="your-umls-api-key"

# DisGeNET (requires registration)
DISGENET_API_KEY="your-disgenet-api-key"

# ChEMBL (optional, for increased rate limits)
CHEMBL_API_KEY="your-chembl-api-key"
EOF

# Load environment variables
export $(grep -v '^#' .env | xargs)
```

### Custom Configuration

```python
from knowledge_lookup import LookupConfig, KnowledgeSource

# Create configuration
config = LookupConfig(
    # Enable/disable sources
    enabled_sources=[
        KnowledgeSource.OPENTARGETS,
        KnowledgeSource.CHEMBL,
        KnowledgeSource.MONDO,
    ],
    
    # Rate limiting (requests per second)
    rate_limits={
        KnowledgeSource.OPENTARGETS: 5.0,
        KnowledgeSource.CHEMBL: 10.0,
        KnowledgeSource.MONDO: 20.0,
    },
    
    # Timeouts
    timeout_per_source=30.0,  # seconds
    global_timeout=120.0,     # total request timeout
    
    # Result limits
    max_results_per_source=50,
    max_total_results=200,
    
    # Error handling
    retry_on_failure=True,
    max_retries=3,
    retry_delay=1.0,  # seconds
    
    # Caching
    cache_enabled=True,
    cache_ttl=3600,  # seconds
)

# Use configuration
lookup = CentralKnowledgeLookup(config)
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BIOPORTAL_API_KEY` | Optional | API key for BioPortal |
| `UMLS_API_KEY` | Optional | API key for UMLS |
| `DISGENET_API_KEY` | Optional | API key for DisGeNET |
| `CHEMBL_API_KEY` | Optional | API key for ChEMBL |

---

## Working with Results

### Result Objects

```python
from knowledge_lookup import CentralKnowledgeLookup

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts(
    query="diabetes",
    sources=[KnowledgeSource.OPENTARGETS, KnowledgeSource.MONDO]
)

# Result metadata
print(f"Total results: {result.total_found}")
print(f"Execution time: {result.execution_time:.2f}s")
print(f"Errors: {result.errors}")

# Source results
for source_result in result.results:
    print(f"{source_result.source.value}: {len(source_result.concepts)} concepts")

# All concepts (deduplicated)
for concept in result.concepts:
    print(f"{concept.primary_label}: {concept.primary_id}")
```

### Exporting Results

```python
# Export to JSON
lookup.export_to_json(result, "results.json")
print("Results saved to results.json")

# Export to CSV
lookup.export_to_csv(result, "results.csv")
print("Results saved to results.csv")

# Export to pandas DataFrame
df = lookup.export_to_dataframe(result)
print(f"DataFrame shape: {df.shape}")
print(df.head())
```

### Result to JSON Structure

```json
{
  "total_found": 42,
  "execution_time": 2.35,
  "results": [
    {
      "source": "OPENTARGETS",
      "concepts": [
        {
          "primary_id": "ENSG00000141510",
          "primary_label": "TCF7L2",
          "concept_type": "gene",
          "identifiers": [...]
        }
      ]
    }
  ],
  "concepts": [...],
  "errors": []
}
```

---

## Error Handling

### Catching Errors

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource
from knowledge_lookup.exceptions import (
    SourceUnavailableError,
    RateLimitError,
    APIError
)

lookup = CentralKnowledgeLookup()

try:
    result = await lookup.search_concepts(
        query="test",
        sources=[KnowledgeSource.OPENTARGETS]
    )
    print(f"Success: {len(result.concepts)} concepts")
    
except RateLimitError as e:
    print(f"Rate limited by {e.source}: Wait {e.retry_after:.1f}s")
    # Implement retry with exponential backoff
    import asyncio
    await asyncio.sleep(e.retry_after * 2)
    
except SourceUnavailableError as e:
    print(f"Source {e.source} is unavailable")
    # Try alternative sources
    
except APIError as e:
    print(f"API error from {e.source}: {e.message}")
    # Log and handle appropriately

except Exception as e:
    print(f"Unexpected error: {type(e).__name__}: {e}")

finally:
    await lookup.close()
```

### Error Types

| Exception | Description | Resolution |
|-----------|-------------|------------|
| `RateLimitError` | Source rate limit exceeded | Wait and retry with backoff |
| `SourceUnavailableError` | Source endpoint unreachable | Check network, try later |
| `APIError` | Invalid API response | Check API key, parameters |
| `ConfigurationError` | Invalid configuration | Review config settings |

---

## Performance Tips

### Optimize Query Performance

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup

async def parallel_queries():
    lookup = CentralKnowledgeLookup()
    
    # Run multiple searches in parallel
    tasks = [
        lookup.search_concepts("diabetes", [KnowledgeSource.MONDO]),
        lookup.search_concepts("insulin", [KnowledgeSource.CHEMBL]),
        lookup.search_concepts("TP53", [KnowledgeSource.OPENTARGETS]),
    ]
    
    # Execute all concurrently
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        print(f"Query {i+1}: {result.total_found} results")
    
    await lookup.close()

asyncio.run(parallel_queries())
```

### Efficient Result Processing

```python
def process_results(result):
    """Process results efficiently"""
    # Use generators for large result sets
    for concept in result.concepts:
        # Process one concept at a time
        yield {
            'id': concept.primary_id,
            'label': concept.primary_label,
            'type': concept.concept_type.value
        }

# Use with large result sets
for concept_data in process_results(result):
    print(concept_data)
```

### Caching Strategy

```python
import asyncio
from functools import lru_cache
from knowledge_lookup import CentralKnowledgeLookup

async def search_cached(query, sources, lookup, cache={}):
    """Simple caching wrapper"""
    cache_key = (query, tuple(sources))
    
    if cache_key not in cache:
        cache[cache_key] = await lookup.search_concepts(query, sources)
    
    return cache[cache_key]

async def main():
    lookup = CentralKnowledgeLookup()
    
    # First call - fetches from API
    result1 = await search_cached("diabetes", [KnowledgeSource.MONDO], lookup)
    
    # Second call - returns cached
    result2 = await search_cached("diabetes", [KnowledgeSource.MONDO], lookup)
    
    print(f"Cache hit: {result1 is result2}")
    await lookup.close()

asyncio.run(main())
```

---

## Next Steps

### Documentation

- **[API Reference](api_reference.md)** - Complete API specifications
- **[Adapter Documentation](adapters/index.md)** - Detailed adapter information
- **[Architecture](architecture.md)** - System design and patterns

### Examples

- **[Basic Usage Notebook](examples/basic_usage.ipynb)** - Interactive examples
- **[Advanced Patterns](examples/advanced_usage.ipynb)** - Complex integrations
- **[Real-World Examples](examples/real_world/)** - Production examples

### Community

- **[GitHub Issues](https://github.com/your-org/biomedical-knowledge-lookup/issues)** - Report bugs
- **[Discussions](https://github.com/your-org/biomedical-knowledge-lookup/discussions)** - Ask questions
- **[Contributing Guide](CONTRIBUTING.md)** - Contribute code

### Additional Resources

- **[Open Targets Platform](https://www.opentargets.org/)** - Main data source
- **[ChEMBL](https://www.ebi.ac.uk/chembl/)** - Drug data
- **[MONDO](https://mondo.monarchinitiative.org/)** - Disease ontology

---

*For support, please open an issue on GitHub or contact the maintainers.*