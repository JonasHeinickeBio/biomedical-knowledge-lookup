---
description: KEGG DISEASE and DRUG entries through the KEGG REST API.
---

# KEGG adapter

Searches the KEGG DISEASE and DRUG databases by keyword and fetches entries by KEGG ID. Pathway, gene and compound entries are not covered despite the "pathways" category.

| | |
|---|---|
| Source | `KnowledgeSource.KEGG` |
| Class | `knowledge_lookup.adapters.KEGGAdapter` |
| Requires | none |
| Identifiers | disease `H00409`, drug `D00944` |
| Upstream API | `https://rest.kegg.jp` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import KEGGAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with KEGGAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("metformin", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        for kegg_id in ("H00409", "D00944"):
            entry = await adapter.get_concept_details(kegg_id)
            print(entry.primary_id, entry.primary_label, entry.concept_type)


asyncio.run(main())
```

Output:

```
D00944 Metformin hydrochloride (JP19/USP) DRUG
D04966 Metformin (USAN/INN) DRUG
D09744 Pioglitazone hydrochloride and metformin hydrochloride (JP19) DRUG
H00409 Type 2 diabetes mellitus DISEASE
D00944 Metformin hydrochloride (JP19/USP) DRUG
```

## Searching

`search_concepts(query, limit)` calls `/find/disease/{query}` and, if that yields fewer than `limit` entries, `/find/drug/{query}` for the rest. Diseases therefore come first.

| Field | Value |
|---|---|
| `primary_id` | KEGG ID without the `ds:`/`dr:` prefix |
| `primary_label` | first name (text before the first `;`) |
| `concept_type` | `DISEASE` or `DRUG` |
| `identifiers` | one `KEGG` identifier (no URL) |
| `confidence_score` | `0.8` |

## Concept details

`get_concept_details(kegg_id)` treats IDs starting with `H` as diseases (`/get/ds:<id>`) and everything else as drugs (`/get/dr:<id>`). Pathway IDs such as `hsa04210` therefore return `None`. The flat file is parsed for:

- `primary_label`: first `NAME`
- `definitions`: the first `DESCRIPTION` line
- `concept_type`: `DISEASE` for `H…`, `DRUG` for `D…`
- identifier URL `https://www.kegg.jp/dbget-bin/www_bget?<id>`
- `confidence_score` `1.0`, and the full text in `source_data[KEGG]["raw_text"]`

## Rate limits and errors

Text requests use `_make_request_text` with the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). A search makes up to two requests. Errors are logged; search returns `[]` and details return `None`. KEGG's REST API is provided for academic use.

## See also

- [Reactome adapter](reactome_adapter.md): pathways
- [ChEMBL adapter](../core/chembl_adapter.md), [Mondo adapter](../core/mondo_adapter.md)
- [All adapters](../README.md)
