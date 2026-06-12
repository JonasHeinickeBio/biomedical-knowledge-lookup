# DrugBank Adapter

Access to DrugBank drug and pharmacological data.

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("metformin", sources=[KnowledgeSource.DRUGBANK])
```

## Features

- Drug information lookup
- Pharmacology data
- Drug interactions
- Target information