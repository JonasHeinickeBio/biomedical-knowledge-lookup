---
description: STRING human protein identifiers and their top interaction partners.
---

# STRING adapter

Resolves human protein names to STRING identifiers and lists their top interaction partners from the STRING database.

| | |
|---|---|
| Source | `KnowledgeSource.STRING` |
| Class | `knowledge_lookup.adapters.STRINGAdapter` |
| Requires | none |
| Identifiers | protein name `TP53` or STRING ID `9606.ENSP00000269305` |
| Upstream API | `https://string-db.org/api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import STRINGAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with STRINGAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("TP53", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        tp53 = await adapter.get_concept_details("TP53")
        print(tp53.primary_id, tp53.related)


asyncio.run(main())
```

Output:

```
STRING:9606.ENSP00000269305 TP53 ['taxon:9606']
STRING:9606.ENSP00000269305 ['SFN(score=0.999)', 'EP300(score=0.999)', 'HIF1A(score=0.999)', 'HDAC1(score=0.999)', 'HSP90AA1(score=0.999)']
```

## Searching

`search_concepts(query, limit)` calls `/json/resolve` with `species=9606` (human only) and `limit=min(limit, 5)`, so it returns at most five results. Each match becomes a `PROTEIN` concept:

- `primary_id`: `STRING:<stringId>`
- `primary_label`: preferred name
- `definitions`: STRING annotation, cut to 500 characters
- `categories`: `taxon:<ncbiTaxonId>`
- `confidence_score`: `0.8`

## Concept details

`get_concept_details(concept_id)` strips a `STRING:` prefix and resolves the identifier (limit 1). It then calls `/json/interaction_partners` (human, limit 5) and appends each partner once to `related` as `NAME(score=0.999)`.

## Rate limits and errors

STRING serves JSON with the content type `text/json`, so the adapter overrides `_make_request` to decode the body regardless of content type (GET only). Requests still use the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`. A failed partner request is logged as a warning and leaves `related` empty.

## See also

- [UniProt adapter](../core/uniprot_adapter.md), [HGNC adapter](../proteins/hgnc_adapter.md)
- [All adapters](../README.md)
