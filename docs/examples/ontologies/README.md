# Ontologies

This category includes ontology services and knowledge representation systems.

## Working Examples (3)

| Adapter | Description | Example |
|---------|-------------|---------|
| [Bioontology](../bioontology_example.py) | BioOntology API | `ontologies/bioontology_example.py` |
| [BioPortal](../bioportal_example.py) | NCBI BioPortal ontologies | `ontologies/bioportal_example.py` |
| [EBIOLS](../ebiols_example.py) | EBI Ontology Lookup Service | `ontologies/ebiols_example.py` |
| [OBOFoundry](../obofoundry_example.py) | Interoperable ontologies | `ontologies/obofoundry_example.py` |
| [Zooma](../zooma_example.py) | Ontology annotation mapping | `ontologies/zooma_example.py` |

## API Key Requirements

- **Bioontology**: Requires `BIOPORTAL_API_KEY` environment variable
- **BioPortal**: Requires `BIOPORTAL_API_KEY` environment variable

## Overview

Ontology sources provide:
- Standardized biomedical ontologies
- Ontology search and browsing
- Ontology cross-references
- Annotation mapping

## Quick Start

```python
from knowledge_lookup import create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[
    KnowledgeSource.BIOONTOLOGY,
    KnowledgeSource.OBOFOUNDRY,
])

# Search for ontology terms
results = await lookup.search_concepts("cell")
```

## Related Categories

- [Core](../core/README.md) - General ontology services
- [Phenotypes](../phenotypes/README.md) - Phenotype ontologies
