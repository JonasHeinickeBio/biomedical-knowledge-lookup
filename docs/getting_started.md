# Getting Started with Biomedical Knowledge Lookup

A unified tool for querying biological concepts across multiple knowledge sources.

## Prerequisites

- Python 3.10+
- Poetry (recommended) or pip

## Installation

```bash
pip install biomedical-knowledge-lookup
# or
poetry add biomedical-knowledge-lookup
```

## Quick Start

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

async def main():
    lookup = CentralKnowledgeLookup()

    # Search across all sources
    result = await lookup.search_concepts("diabetes mellitus")

    print(f"Found {result.total_found} concepts in {result.execution_time:.2f}s")
    for concept in result.concepts[:5]:
        print(f"  {concept.primary_label} ({concept.primary_id})")

    await lookup.close()

asyncio.run(main())
```

## Searching Specific Sources

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search specific sources
result = await lookup.search_concepts(
    "BRCA1",
    sources=[KnowledgeSource.BIOPORTAL, KnowledgeSource.UMLS]
)

for concept in result.concepts:
    print(f"{concept.primary_label}")
    print(f"  Type: {concept.concept_type.value}")
    print(f"  Sources: {[s.value for s in concept.sources]}")
```

## Concept Details

```python
# Get detailed information about a specific concept
concept = await lookup.get_concept_details("DOID:9351")

if concept:
    print(f"Label: {concept.primary_label}")
    print(f"Definitions: {concept.definitions[:2]}")
    print(f"Synonyms: {concept.synonyms[:5]}")
```

## Multi-Source Annotation

```python
from knowledge_lookup import MultiSourceAnnotator

annotator = MultiSourceAnnotator()

result = await annotator.annotate_sentence(
    "Type 2 diabetes is associated with insulin resistance"
)

for consensus in result.consensus_concepts:
    print(f"Concept: {consensus.primary_concept.primary_label}")
    print(f"  Confidence: {consensus.confidence_level.value}")
    print(f"  Agreeing sources: {[s.value for s in consensus.agreeing_sources]}")
```

## Configuration

### API Keys

Set as environment variables:

```bash
export BIOPORTAL_API_KEY="your_key_here"
export UMLS_API_KEY="your_key_here"
export DISGENET_API_KEY="your_key_here"
```

### LookupConfig

```python
from knowledge_lookup import LookupConfig, KnowledgeSource

config = LookupConfig(
    enabled_sources=[KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS],
    rate_limits={
        KnowledgeSource.BIOPORTAL: 10,
        KnowledgeSource.OLS: 20,
    },
    max_results_per_source=20,
)

lookup = CentralKnowledgeLookup(config)
```

## Exporting Results

```python
# Export to JSON
lookup.export_to_json(result, "results.json")

# Export to CSV
lookup.export_to_csv(result, "results.csv")

# Export to pandas DataFrame
df = lookup.export_to_dataframe(result)
```

## Available Knowledge Sources

See [README.md](README.md) for complete list of 27 supported sources.

## Next Steps

- Explore the [API Reference](api_reference.md)
- Check out [Adapter Documentation](adapters/)
- See example notebooks in the repository