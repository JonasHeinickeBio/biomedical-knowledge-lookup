---
description: Mondo Disease Ontology terms, served from the EBI Ontology Lookup Service.
---

# Mondo adapter

Looks up diseases in the Mondo Disease Ontology through EMBL-EBI OLS4. Every result is a `DISEASE` concept with a Mondo ID. Use it to normalise disease names to Mondo; term details carry cross-references to DOID, ICD-10, OMIM, UMLS and others.

| | |
|---|---|
| Source | `KnowledgeSource.MONDO` |
| Class | `knowledge_lookup.adapters.MondoAdapter` |
| Requires | none |
| Identifiers | `MONDO:0005148` |
| Upstream API | `https://www.ebi.ac.uk/ols4/api` (ontology `mondo`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MondoAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MondoAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("type 2 diabetes", limit=3):
            print(concept.primary_id, concept.primary_label)

        t2d = await adapter.get_concept_details("MONDO:0005148")
        print(t2d.primary_label, len(t2d.synonyms), t2d.categories[:3])


asyncio.run(main())
```

Output:

```
MONDO_0005148 type 2 diabetes mellitus
MONDO_0007453 maturity-onset diabetes of the young type 2
MONDO_1011605 type 2 diabetes mellitus, pig
type 2 diabetes mellitus 25 ['Xref: DOID:9352', 'Xref: ICD10CM:E11', 'Xref: ICD10WHO:E11']
```

## Searching

`search_concepts(query, limit)` calls `/search` with `ontology=mondo` and `rows=min(limit, 100)`. For each hit:

| Field | Value |
|---|---|
| `primary_id` | OLS short form with an underscore, e.g. `MONDO_0005148` |
| `primary_label` | term label |
| `concept_type` | always `DISEASE` |
| `identifiers` | one `MONDO` identifier; the URL is the term IRI |
| `synonyms`, `definitions` | from the search document when present (search hits usually carry a definition but no synonyms) |
| `confidence_score` | `0.95` |
| `source_data[MONDO]` | raw OLS search document |

## Concept details

`get_concept_details(concept_id)` accepts `MONDO:0005148`, `MONDO_0005148` or bare digits (`5148` is zero-padded to `MONDO:0005148`). It fetches the term from `/ontologies/mondo/terms/{encoded IRI}` and returns:

- all synonyms and definitions
- `categories` entries `Xref: <CURIE>` for every `database_cross_reference` annotation (DOID, ICD-10-CM, MeSH, OMIM, UMLS, ...)
- `confidence_score` `1.0`

`primary_id` uses the underscore form (`MONDO_0005148`) whichever form you pass in. Parents and children are not populated.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors left after retries are logged; `search_concepts` then returns `[]` and `get_concept_details` returns `None`.

## See also

- [OLS adapter](ols_adapter.md): the same service across all ontologies
- [HPO adapter](../phenotypes/hpo_adapter.md), [OMIM adapter](../phenotypes/omim_adapter.md)
- [OxO adapter](../other/oxo_adapter.md): mappings from Mondo IDs to other vocabularies
- [All adapters](../README.md)
