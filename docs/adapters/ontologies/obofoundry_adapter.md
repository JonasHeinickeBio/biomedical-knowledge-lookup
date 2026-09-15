---
description: Lightweight term search over the ontologies in OLS4, labelled as OBO Foundry.
---

# OBO Foundry adapter

Runs a free-text search against EMBL-EBI OLS4 and returns a lightweight concept per hit: short-form ID, label and ontology name. Despite the name, results are **not** restricted to OBO Foundry ontologies. MeSH, SNOMED and other non-OBO vocabularies show up too, because the search has no ontology filter.

| | |
|---|---|
| Source | `KnowledgeSource.OBOFOUNDRY` |
| Class | `knowledge_lookup.adapters.OBOFoundryAdapter` |
| Requires | none |
| Identifiers | OLS short form, e.g. `NCIT_C17557` |
| Upstream API | `https://www.ebi.ac.uk/ols4/api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OBOFoundryAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OBOFoundryAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("apoptosis", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)


asyncio.run(main())
```

Output:

```
mesh_D017209 Apoptosis ['Ontology: mesh']
NCIT_C17557 Apoptosis ['Ontology: ncit']
SNOMED_20663007 Apoptosis ['Ontology: snomed']
```

## Searching

`search_concepts(query, limit)` calls `/search?q=...&rows=min(limit, 100)`.

| Field | Value |
|---|---|
| `primary_id` | OLS short form, e.g. `NCIT_C17557` |
| `primary_label` | label |
| `concept_type` | `UNKNOWN` |
| `identifiers` | one `OBOFOUNDRY` identifier; the URL is the term IRI |
| `categories` | `Ontology: <ontology name>` |
| `confidence_score` | `0.8` |

No synonyms or definitions are copied.

## Concept details

Not supported: `get_concept_details` always returns `None`. Fetch the term with the [OLS adapter](../core/ols_adapter.md) using its IRI (the identifier URL).

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged and search returns `[]`.

## See also

- [OLS adapter](../core/ols_adapter.md): richer results from the same search
- [HPO adapter](../phenotypes/hpo_adapter.md), [Gene Ontology adapter](../phenotypes/geneontology_adapter.md), [Mondo adapter](../core/mondo_adapter.md): single OBO ontologies
- [All adapters](../README.md)
