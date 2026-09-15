---
description: Reactome pathways and reactions through the Reactome ContentService.
---

# Reactome adapter

Searches Reactome pathways and reactions by keyword and fetches them by stable ID, with their summaries.

| | |
|---|---|
| Source | `KnowledgeSource.REACTOME` |
| Class | `knowledge_lookup.adapters.ReactomeAdapter` |
| Requires | none |
| Identifiers | stable ID, e.g. `R-HSA-109581` |
| Upstream API | `https://reactome.org/ContentService` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ReactomeAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ReactomeAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("apoptosis", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        pathway = await adapter.get_concept_details("R-HSA-109581")
        print(pathway.primary_id, pathway.primary_label, pathway.definitions[0][:60])


asyncio.run(main())
```

Output:

```
R-HSA-109581 Apoptosis ['Homo sapiens']
R-DRE-109581 Apoptosis ['Danio rerio']
R-MMU-109581 Apoptosis ['Mus musculus']
R-HSA-109581 Apoptosis Apoptosis is a distinct form of cell death that is functiona
```

Search is not limited to human: inferred orthologous events (`R-DRE-...`, `R-MMU-...`) share the human label, so `CentralKnowledgeLookup` may merge them into one concept.

## Searching

`search_concepts(query, limit)` calls `/search/query?query=...&rows=min(limit, 100)`. The ContentService groups hits by type (`results[].entries[]`, with the type on each entry); the adapter keeps the `Pathway` and `Reaction` entries in the order Reactome returns them and stops after `limit` concepts (`rows` applies per group).

| Field | Value |
|---|---|
| `primary_id` | stable ID (`stId`) |
| `primary_label` | name, with Reactome's `<span class="highlighting">` markup removed |
| `definitions` | summation, markup removed |
| `categories` | species |
| `concept_type` | `PATHWAY` for pathways, `BIOLOGICAL_PROCESS` for reactions |
| `identifiers` | one `REACTOME` identifier, URL `https://reactome.org/content/detail/<id>` |
| `confidence_score` | `0.9` |
| `source_data[REACTOME]` | raw search entry |

Reactome answers HTTP 404 when nothing matches; search then returns `[]`. The 404 counts as an answer, not as a failure, so repeated searches without matches do not open the source's circuit breaker.

## Concept details

`get_concept_details(stable_id)` calls `/data/query/{id}`.

| Field | Value |
|---|---|
| `primary_id` | stable ID (`stId`) |
| `primary_label` | `displayName` |
| `definitions` | text of the first summation |
| `concept_type` | from `schemaClass`: `PATHWAY` for pathways, `BIOLOGICAL_PROCESS` for reactions and other events, otherwise `UNKNOWN` |
| `identifiers` | one `REACTOME` identifier, URL `https://reactome.org/content/detail/<id>` |
| `confidence_score` | `1.0` |
| `source_data[REACTOME]` | full database object |

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [KEGG adapter](kegg_adapter.md), [Gene Ontology adapter](../phenotypes/geneontology_adapter.md)
- [All adapters](../README.md)
