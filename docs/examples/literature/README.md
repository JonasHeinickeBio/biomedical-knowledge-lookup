# Literature

This category includes literature and publication databases.

## Working Examples (2)

| Adapter | Description | Example |
|---------|-------------|---------|
| [EuropePMC](../europepmc_example.py) | Europe PMC literature search | `literature/europepmc_example.py` |
| [EUtils](../eutils_example.py) | NCBI E-utilities | `literature/eutils_example.py` |

## Overview

Literature sources provide:
- Scientific literature search
- Publication data
- Citation information
- Abstracts and full-text access

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.EUROPEPMC,
    KnowledgeSource.EUTILS,
])

# Search for literature
results = await lookup.search_concepts("cancer treatment")
```

## Related Categories

- [Core](../core/README.md) - General information sources
