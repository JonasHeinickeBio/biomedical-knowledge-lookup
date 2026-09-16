---
description: DrugBank IDs, names and synonyms, looked up without an API key through MyChem.info.
---

# DrugBank adapter

Looks up DrugBank drugs (`DB` identifiers) by name, synonym or ID without an API key. DrugBank's own API is licensed, so the adapter queries MyChem.info (BioThings), which serves DrugBank's open fields: ID, name, synonyms, CAS number, UNII and InChIKey.

| | |
|---|---|
| Source | `KnowledgeSource.DRUGBANK` |
| Class | `knowledge_lookup.adapters.DrugBankAdapter` |
| Requires | none |
| Identifiers | `DB00945` (also `DRUGBANK:DB00945`) |
| Upstream API | `https://mychem.info/v1` (`drugbank` fields) |

{% hint style="info" %}
**Open fields only, non-commercial licence.** MyChem.info serves the open DrugBank fields listed above, not descriptions, indications, targets or interactions. DrugBank data is licensed CC BY-NC 4.0; check the licence before commercial use.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DrugBankAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with DrugBankAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("aspirin", limit=3):
            print(concept.primary_id, concept.primary_label)

        drug = await adapter.get_concept_details("DB00945")
        print(drug.primary_label, drug.synonyms[:3], drug.categories)


asyncio.run(main())
```

Output:

```
DB00945 Acetylsalicylic acid
DB00388 Phenylephrine
DB00201 Caffeine
Acetylsalicylic acid ['2-Acetoxybenzenecarboxylic acid', '2-Acetoxybenzoic acid', 'acetyl salicylic acid'] ['cas:50-78-2', 'unii:R16CO5Y76E', 'inchi_key:BSYNRYMUTXBXSQ-UHFFFAOYSA-N']
```

## Searching

`search_concepts(query, limit)` calls `/query` with `q=(<query>) AND _exists_:drugbank`, the DrugBank fields and `size=min(limit, 100)`. Lucene special characters in the query are escaped, so it is searched literally. Results come in MyChem.info's relevance order, which ranks on all MyChem.info fields: drugs that share products with the query can appear (aspirin also finds phenylephrine and caffeine). Records are de-duplicated by DrugBank ID.

| Field | Value |
|---|---|
| `primary_id` | DrugBank ID, e.g. `DB00945` |
| `primary_label` | DrugBank name, e.g. `Acetylsalicylic acid` |
| `concept_type` | `DRUG` |
| `synonyms` | DrugBank synonyms (without the label) |
| `categories` | `cas:<CAS>`, `unii:<UNII>`, `inchi_key:<InChIKey>` (when present) |
| `identifiers` | one `DRUGBANK` identifier, URL `https://go.drugbank.com/drugs/<id>` |
| `sources` | `['DRUGBANK']` |
| `confidence_score` | `0.9` |
| `source_data[DRUGBANK]` | MyChem.info `drugbank` record |

## Concept details

`get_concept_details("DB00945")` strips a `DRUGBANK:` prefix, queries `drugbank.id:"DB00945"` and returns the record whose ID matches, with the same fields as search and `confidence_score` `0.95`. Unknown IDs return `None`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [UniChem adapter](unichem_adapter.md), [ChEMBL adapter](../core/chembl_adapter.md), [PubChem adapter](pubchem_adapter.md)
- [All adapters](../README.md)
