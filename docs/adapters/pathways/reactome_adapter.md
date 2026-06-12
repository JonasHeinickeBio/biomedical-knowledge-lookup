# Reactome Adapter

Access to Reactome biological pathways.

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("apoptosis", sources=[KnowledgeSource.REACTOME])
```

## Features

- Pathway search
- Reaction data
- Pathway components
- Cross-references to other databases