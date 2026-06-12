# Core Knowledge Sources

This category includes the main biomedical knowledge sources for diseases, phenotypes, and general concept lookup.

## Working Examples (6)

| Adapter | Description | Example |
|---------|-------------|---------|
| OLS | Ontology Lookup Service for diseases, phenotypes, and genes | `core/ols_example.py` |
| UMLS | Unified Medical Language System for comprehensive biomedical concepts | `core/umls_example.py` |
| OpenTargets | Drug targets and disease associations | `core/opentargets_example.py` |
| ChEMBL | Bioactive drug-like molecules | `core/chembl_example.py` |
| DisGeNET | Gene-disease associations | `core/disgenet_example.py` |
| Mondo | Disease ontology | `core/mondo_example.py` |
| UniProt | Protein sequences and functions | `core/uniprot_example.py` |

## API Key Requirements

- **DisGeNET**: Requires `DISGENET_API_KEY` environment variable

## Overview

Core knowledge sources provide foundational biomedical concept lookup capabilities. These adapters cover:
- Disease and phenotype identification
- Drug target discovery
- Protein sequence and function data
- Gene-disease associations

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

# Search across multiple core sources
lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.OLS,
    KnowledgeSource.UMLS,
    KnowledgeSource.OPENTARGETS,
])

# Search for a concept
results = await lookup.search_concepts("cancer")
for concept in results.concepts:
    print(f"{concept.primary_label}: {concept.primary_id}")
```

## Related Categories

- [Phenotypes](../phenotypes/README.md) - More specialized disease and phenotype sources
- [Proteins](../proteins/README.md) - Protein-specific knowledge sources
- [Chemicals](../chemicals/README.md) - Drug and compound information
