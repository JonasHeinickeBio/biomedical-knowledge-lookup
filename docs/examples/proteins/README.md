# Proteins and Genes

This category includes sources focused on protein and gene information.

## Working Examples (3)

| Adapter | Description | Example |
|---------|-------------|---------|
| [UniProt](../uniprot_example.py) | Protein sequences and functions | `proteins/uniprot_example.py` |
| [Ensembl](../ensembl_example.py) | Genome annotation | `proteins/ensembl_example.py` |
| [HGNC](../hgnc_example.py) | Human gene nomenclature | `proteins/hgnc_example.py` |

## Overview

Protein and gene sources provide:
- Protein sequences and structures
- Gene annotations and nomenclature
- Genomic location data
- Protein function information

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.UNIPROT,
    KnowledgeSource.ENSEMBL,
])

# Search for a protein or gene
results = await lookup.search_concepts("TP53")
```

## Related Categories

- [Core](../core/README.md) - General protein information
- [Phenotypes](../phenotypes/README.md) - Gene-disease associations
