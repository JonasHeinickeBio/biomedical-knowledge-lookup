---
description: A second registration of the OLS adapter under KnowledgeSource.EBIOLS.
---

# EBI OLS adapter

`EBIOLSAdapter` subclasses the [OLS adapter](../core/ols_adapter.md) and only overrides `get_source()`. The inherited OLS code tags identifiers and `source_data` with `get_source()`, so they are recorded under `EBIOLS` instead of `OLS`. It makes the same HTTP calls to EMBL-EBI OLS4 and returns the same results, but can be enabled, disabled and reported as its own source.

| | |
|---|---|
| Source | `KnowledgeSource.EBIOLS` |
| Class | `knowledge_lookup.adapters.EBIOLSAdapter` |
| Requires | none |
| Identifiers | term IRI, e.g. `http://purl.obolibrary.org/obo/HP_0001250` |
| Upstream API | `https://www.ebi.ac.uk/ols4/api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EBIOLSAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with EBIOLSAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("epilepsy", limit=3):
            print(concept.primary_id, concept.categories, concept.identifiers[0].source)

        seizure = await adapter.get_concept_details("http://purl.obolibrary.org/obo/HP_0001250")
        print(seizure.primary_label, seizure.synonyms)


asyncio.run(main())
```

Output:

```
http://id.nlm.nih.gov/mesh/D004827 ['mesh'] EBIOLS
http://purl.obolibrary.org/obo/DOID_1826 ['doid'] EBIOLS
http://snomed.info/id/84757009 ['snomed'] EBIOLS
Seizure ['Epilepsy', 'Epileptic seizure', 'Seizures']
```

## Searching

Identical to the [OLS adapter](../core/ols_adapter.md#searching): free-text search across all OLS4 ontologies, IRIs as `primary_id`, `concept_type` from the ontology name. Identifiers and `source_data` are recorded under `EBIOLS`, as the output above shows.

## Concept details

Identical to the [OLS adapter](../core/ols_adapter.md#concept-details): only IRIs resolve; CURIEs return `None`. Identifiers and `source_data` are recorded under `EBIOLS`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). If you enable both `OLS` and `EBIOLS` in `CentralKnowledgeLookup`, every search is sent twice to the same service; deduplication merges the duplicate concepts by label.

## See also

- [OLS adapter](../core/ols_adapter.md)
- [All adapters](../README.md)
