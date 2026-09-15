---
description: Human Phenotype Ontology terms from the JAX ontology API.
---

# HPO adapter

Searches the Human Phenotype Ontology and fetches terms by HPO ID. Results carry the term name, definition, synonyms and UMLS cross-references. Use it to normalise clinical signs and symptoms to HPO terms.

| | |
|---|---|
| Source | `KnowledgeSource.HPO` |
| Class | `knowledge_lookup.adapters.HPOAdapter` |
| Requires | none |
| Identifiers | `HP:0001250` |
| Upstream API | `https://ontology.jax.org/api/hp` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import HPOAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with HPOAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("seizure", limit=3):
            print(concept.primary_id, concept.primary_label)

        seizure = await adapter.get_concept_details("HP:0001250")
        print(seizure.primary_label, seizure.synonyms)
        print([(i.source, i.identifier) for i in seizure.identifiers])


asyncio.run(main())
```

Output:

```
HP:0001250 Seizure
HP:0033349 Seizure cluster
HP:0002373 Febrile seizure (within the age range of 3 months to 6 years)
Seizure ['Epileptic seizure', 'Seizures', 'Epilepsy']
[('HPO', 'HP:0001250'), ('UMLS', 'UMLS:C0014544'), ('UMLS', 'UMLS:C0036572')]
```

## Searching

`search_concepts(query, limit)` calls `/search?q=...&limit=min(limit, 100)`.

| Field | Value |
|---|---|
| `primary_id` | HPO ID, e.g. `HP:0001250` |
| `primary_label` | term name |
| `concept_type` | `PHENOTYPE` |
| `synonyms`, `definitions` | synonyms and definition |
| `identifiers` | `HPO` (URL `https://hpo.jax.org/browse/term/<id>`), plus one `UMLS` identifier per `UMLS:` cross-reference, with the prefix kept |
| `confidence_score` | `0.95` |
| `source_data[HPO]` | raw term |

## Concept details

`get_concept_details` takes the full CURIE (`HP:0001250`) and calls `/terms/{id}`. It returns the same fields with `confidence_score` `1.0`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [Mondo adapter](../core/mondo_adapter.md), [OMIM adapter](omim_adapter.md)
- [All adapters](../README.md)
- [Searching concepts](../../guides/searching-concepts.md)
