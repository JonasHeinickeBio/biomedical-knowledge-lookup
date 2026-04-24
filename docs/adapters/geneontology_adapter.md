# Gene Ontology (GO) Adapter

Access to Gene Ontology and related annotations via QuickGO.

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("apoptosis", sources=[KnowledgeSource.GENEONTOLOGY])
```

## Features

- GO term search
- Gene product annotations
- GO slim mappings
- Hierarchy traversal