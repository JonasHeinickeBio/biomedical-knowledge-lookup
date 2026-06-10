# Getting Started with Biomedical Knowledge Lookup

Welcome to Biomedical Knowledge Lookup! This guide will help you get started with the project and show you how to use it for your research.

## Prerequisites

- Python 3.10+
- Poetry (recommended) or pip

## Installation

```bash
pip install biomedical-knowledge-lookup
# or
poetry add biomedical-knowledge-lookup
```

## Basic Search

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

# Initialize the lookup system
lookup = CentralKnowledgeLookup()

# Search for concepts across multiple sources
results = await lookup.search_concepts(
    "diabetes mellitus",
    sources=[KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS, KnowledgeSource.UMLS]
)

# Access the results
for concept in results.concepts:
    print(f"{concept.primary_label} ({concept.primary_id})")
    print(f"  Source: {list(concept.sources)[0].value}")
    print(f"  Type: {concept.concept_type.value}")
```

## Detailed Concept Information

```python
# Get detailed information about a specific concept
concept_details = await lookup.get_concept_details("DOID:9351")

# Access the details
print(f"Label: {concept_details.primary_label}")
print(f"Definitions: {concept_details.definitions}")
print(f"Synonyms: {concept_details.synonyms}")
```

## Multi-source Annotation

```python
from knowledge_lookup import MultiSourceAnnotator

# Annotate text with concepts from multiple sources
annotator = MultiSourceAnnotator()
annotations = await annotator.annotate_sentence(
    "Type 2 diabetes is associated with insulin resistance"
)

# Access the consensus annotations
for consensus in annotations.consensus_concepts:
    print(f"Consensus: {consensus.primary_concept.primary_label}")
    print(f"  Sources: {[s.value for s in consensus.agreeing_sources]}")
    print(f"  Confidence: {consensus.confidence_level.value}")
```

## Configuration

### API Keys

Some sources require API keys. Set them as environment variables or in a `.env` file:

```bash
export BIOPORTAL_API_KEY="your_key_here"
export UMLS_API_KEY="your_key_here"
```

### Advanced Configuration

```python
from knowledge_lookup import LookupConfig, KnowledgeSource

config = LookupConfig(
    rate_limits={
        KnowledgeSource.BIOPORTAL: 10,
        KnowledgeSource.OLS: 20,
    },
    cache_enabled=True,
    cache_dir="./cache"
)

lookup = CentralKnowledgeLookup(config)
```

## Next Steps

- Explore the [API Reference](api_reference.md)
- Check out the [Adapter Documentation](adapters/)
- Read through the [Example Notebooks](../examples/)
