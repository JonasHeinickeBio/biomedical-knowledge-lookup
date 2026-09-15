---
description: PubChem compounds by name or CID - title, IUPAC name, formula and InChIKey.
---

# PubChem adapter

Resolves compound names to PubChem CIDs and fetches basic compound records: title, description, IUPAC name, molecular formula and InChIKey. Useful for mapping a drug or chemical name to a CID and a structure key.

| | |
|---|---|
| Source | `KnowledgeSource.PUBCHEM` |
| Class | `knowledge_lookup.adapters.PubChemAdapter` |
| Requires | none |
| Identifiers | CID, e.g. `2244` |
| Upstream API | `https://pubchem.ncbi.nlm.nih.gov/rest/pug` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import PubChemAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with PubChemAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("ibuprofen", limit=3):
            print(concept.primary_id, concept.primary_label)

        aspirin = await adapter.get_concept_details("2244")
        print(aspirin.primary_label, aspirin.synonyms, aspirin.categories)
        print([i.identifier for i in aspirin.identifiers])


asyncio.run(main())
```

Output:

```
3672 Ibuprofen, (+-)-
Aspirin ['2-acetyloxybenzoic acid'] ['Formula: C9H8O4']
['2244', 'BSYNRYMUTXBXSQ-UHFFFAOYSA-N']
```

## Searching

`search_concepts(query, limit)` is a name lookup, not full-text search:

1. `/compound/name/{query}/cids/JSON` resolves the name (or synonym) to CIDs.
2. `get_concept_details` is called for each of the first `limit` CIDs.

Queries without letters or longer than 200 characters are skipped. A name PubChem doesn't know returns `[]` and is logged at `DEBUG` level only. Each search costs `1 + 2 × N` requests for `N` results.

## Concept details

`get_concept_details(cid)` makes two requests: `/compound/cid/{cid}/description/JSON` and `/compound/cid/{cid}/property/IUPACName,MolecularFormula,InChIKey/JSON`.

| Field | Value |
|---|---|
| `primary_id` | CID as given |
| `primary_label` | record title |
| `concept_type` | `CHEMICAL` |
| `definitions` | first description, when PubChem has one |
| `synonyms` | `[IUPAC name]` |
| `categories` | `Formula: <molecular formula>` |
| `identifiers` | `PUBCHEM` CID (URL `https://pubchem.ncbi.nlm.nih.gov/compound/<cid>`) and the InChIKey, also under `PUBCHEM` |
| `confidence_score` | `0.9` |
| `source_data[PUBCHEM]` | the description response |

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). PubChem throttles clients that exceed its usage policy (about 5 requests per second), and a search issues several requests per result, so keep `limit` small. Other errors are logged; search returns `[]` and details return `None`.

## See also

- [UniChem adapter](unichem_adapter.md): cross-reference a CID or InChIKey to ChEMBL, DrugBank, ChEBI, ...
- [ChEMBL adapter](../core/chembl_adapter.md)
- [All adapters](../README.md)
