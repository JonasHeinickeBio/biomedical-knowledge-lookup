# Protein Families and Structures

This category includes protein family, domain, and structure databases.

## Working Examples (4)

| Adapter | Description | Example |
|---------|-------------|---------|
| [InterPro](../interpro_example.py) | Protein domain classification | `families/interpro_example.py` |
| [Pfam](../pfam_example.py) | Protein family database | `families/pfam_example.py` |
| [PDB](../pdb_example.py) | Protein 3D structures | `families/pdb_example.py` |
| [STRING](../string_example.py) | Protein-protein interactions | `families/string_example.py` |

## Overview

Protein family and structure sources provide:
- Protein domain classification
- Family groupings
- 3D structure data
- Interaction networks

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.INTERPRO,
    KnowledgeSource.PFAM,
])

# Search for protein domains or families
results = await lookup.search_concepts("kinase")
```

## Related Categories

- [Proteins](../proteins/README.md) - General protein information
