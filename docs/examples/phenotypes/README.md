# Phenotypes and Diseases

This category includes sources focused on phenotypes, diseases, and clinical concepts.

## Working Examples (4)

| Adapter | Description | Example |
|---------|-------------|---------|
| [HPO](../hpo_example.py) | Human phenotype ontology | `phenotypes/hpo_example.py` |
| [GeneOntology](../geneontology_example.py) | Gene function annotations | `phenotypes/geneontology_example.py` |
| [OMIM](../omim_example.py) | Online Mendelian Inheritance in Man | `phenotypes/omim_example.py` |
| [ClinVar](../clinvar_example.py) | Genomic variations and clinical significance | `phenotypes/clinvar_example.py` |
| [QuickGO](../quickgo_example.py) | Gene Ontology browser | `phenotypes/quickgo_example.py` |

## API Key Requirements

- **OMIM**: Requires `OMIM_API_KEY` environment variable

## Overview

Phenotype and disease sources provide:
- Phenotype identification and classification
- Disease definitions and classifications
- Gene-disease associations
- Clinical variant data

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.HPO,
    KnowledgeSource.OMIM,
])

# Search for a phenotype or disease
results = await lookup.search_concepts("diabetes")
```

## Related Categories

- [Core](../core/README.md) - General disease sources
- [Proteins](../proteins/README.md) - Disease-related proteins
