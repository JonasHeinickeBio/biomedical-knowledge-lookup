# Chemicals and Drugs

This category includes sources for drug and compound information.

## Working Examples (3)

| Adapter | Description | Example |
|---------|-------------|---------|
| [DrugBank](../drugbank_example.py) | Drug information and targets | `chemicals/drugbank_example.py` |
| [PubChem](../pubchem_example.py) | Chemical compounds and structures | `chemicals/pubchem_example.py` |
| [UniChem](../unichem_example.py) | Drug cross-references | `chemicals/unichem_example.py` |

## Overview

Chemical knowledge sources provide:
- Drug information and mechanisms
- Chemical compound data
- Drug-target interactions
- Structure-activity relationships

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.DRUGBANK,
    KnowledgeSource.PUBCHEM,
])

# Search for a drug or compound
results = await lookup.search_concepts("aspirin")
```

## Related Categories

- [Core](../core/README.md) - General drug target information
- [Proteins](../proteins/README.md) - Drug targets
