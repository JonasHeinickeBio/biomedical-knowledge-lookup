# PubChem Adapter

Access to PubChem chemical compound data.

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("aspirin", sources=[KnowledgeSource.PUBCHEM])
```

## Features

- Compound search by name, SMILES, InChI
- Property retrieval
- Similarity search
- CID/ SID/ SID conversion