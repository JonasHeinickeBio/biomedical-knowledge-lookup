# UniChem Adapter

Cross-reference compound identifiers across databases.

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("CHEMBL25", sources=[KnowledgeSource.UNICHEM])
```

## Features

- Cross-database ID mapping
- Direct links to source databases
- Coverage across ChEMBL, DrugBank, PubChem, etc.