# Pathways

This category includes biological pathway databases.

## Working Examples (2)

| Adapter | Description | Example |
|---------|-------------|---------|
| [Reactome](../reactome_example.py) | Biological pathways | `pathways/reactome_example.py` |
| [KEGG](../kegg_example.py) | Pathways and disease maps | `pathways/kegg_example.py` |

## Overview

Pathway sources provide:
- Biological pathway data
- Metabolic pathways
- Signaling pathways
- Disease pathway maps

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.REACTOME,
    KnowledgeSource.KEGG,
])

# Search for a pathway
results = await lookup.search_concepts("apoptosis")
```

## Related Categories

- [Core](../core/README.md) - General pathway information
