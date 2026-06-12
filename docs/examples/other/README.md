# Other and Specialized Sources

This category includes specialized and general knowledge sources that don't fit into other categories.

## Working Examples (5)

| Adapter | Description | Example |
|---------|-------------|---------|
| [Biolinker](../biolinker_example.py) | Biomedical concept linking | `other/biolinker_example.py` |
| [DBpedia](../dbpedia_example.py) | Wikipedia structured data | `other/dbpedia_example.py` |
| [OxO](../oxo_example.py) | Ontology cross-references | `other/oxo_example.py` |
| [Tyto](../tyto_example.py) | Ontology terms lookup | `other/tyto_example.py` |
| [Wikidata](../wikidata_example.py) | General knowledge from Wikidata | `other/wikidata_example.py` |

## API Key Requirements

- **COSMIC**: Requires `COSMIC_API_KEY` environment variable

## Overview

Other sources provide:
- General knowledge graph data
- Ontology cross-referencing
- Structured wiki data
- Specialized biomedical services

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.WIKIDATA,
    KnowledgeSource.DBPEDIA,
])

# Search for general knowledge
results = await lookup.search_concepts("heart disease")
```

## Related Categories

- [Core](../core/README.md) - General sources
- [Ontologies](../ontologies/README.md) - Ontology-specific sources
