---
description: Gene Ontology terms (processes, functions, components) from the QuickGO ontology API.
---

# Gene Ontology adapter

Searches Gene Ontology terms and fetches them by GO ID using EBI's QuickGO REST API. Results carry the term name, definition, synonyms and GO aspect (biological process, molecular function or cellular component).

| | |
|---|---|
| Source | `KnowledgeSource.GENEONTOLOGY` |
| Class | `knowledge_lookup.adapters.GeneOntologyAdapter` |
| Requires | none |
| Identifiers | `GO:0006915` |
| Upstream API | `https://www.ebi.ac.uk/QuickGO/services/ontology/go` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import GeneOntologyAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with GeneOntologyAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("apoptosis", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        term = await adapter.get_concept_details("GO:0006915")
        print(term.primary_label, len(term.synonyms), term.definitions[0][:60])


asyncio.run(main())
```

Output:

```
GO:0097194 execution phase of apoptosis ['Aspect: biological_process']
GO:0070227 lymphocyte apoptotic process ['Aspect: biological_process']
GO:1902489 hepatoblast apoptotic process ['Aspect: biological_process']
apoptotic process 16 A programmed cell death process which begins when a cell rec
```

## Searching

`search_concepts(query, limit)` calls `/search?query=...&limit=min(limit, 100)`. QuickGO's ranking does not put the exact term first: `apoptotic process` itself is not in the top three above.

| Field | Value |
|---|---|
| `primary_id` | GO ID |
| `primary_label` | term name |
| `concept_type` | always `GENE` (the [QuickGO adapter](quickgo_adapter.md) uses `BIOLOGICAL_PROCESS` etc. instead) |
| `categories` | `Aspect: <biological_process \| molecular_function \| cellular_component>` |
| `definitions` | definition text |
| `synonyms` | synonym names (search results usually have none) |
| `identifiers` | one `GENEONTOLOGY` identifier, URL `https://www.ebi.ac.uk/QuickGO/term/<id>` |
| `confidence_score` | `0.95` |

## Concept details

`get_concept_details("GO:0006915")` calls `/terms/{id}` and converts the first result the same way, with synonyms filled in.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [QuickGO adapter](quickgo_adapter.md): GO terms through `bioservices`
- [Reactome adapter](../pathways/reactome_adapter.md)
- [All adapters](../README.md)
