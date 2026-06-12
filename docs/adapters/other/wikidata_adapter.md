# Wikidata Adapter

Access to Wikidata structured knowledge base.

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("cancer", sources=[KnowledgeSource.WIKIDATA])
```

## Features

- Search entities by label or description
- Cross-references to other databases
- Property data retrieval
- SPARQL endpoint access