---
description: Pfam protein families and domains, served through the InterPro API.
---

# Pfam adapter

Searches Pfam entries and fetches them by accession. Pfam is now distributed through InterPro, so this adapter uses the InterPro API's `pfam` member database.

| | |
|---|---|
| Source | `KnowledgeSource.PFAM` |
| Class | `knowledge_lookup.adapters.PfamAdapter` |
| Requires | none |
| Identifiers | `PF00069` |
| Upstream API | `https://www.ebi.ac.uk/interpro/api` (`/entry/pfam`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import PfamAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with PfamAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("kinase", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        family = await adapter.get_concept_details("PF00069")
        print(family.primary_id, family.primary_label, family.semantic_types)


asyncio.run(main())
```

Output:

```
Pfam:PF00069 Protein kinase domain MOLECULAR_ENTITY
Pfam:PF00162 Phosphoglycerate kinase MOLECULAR_ENTITY
Pfam:PF00224 Pyruvate kinase, barrel domain MOLECULAR_ENTITY
Pfam:PF00069 Protein kinase domain ['domain']
```

## Searching

`search_concepts(query, limit)` calls `/entry/pfam/?search=...&page_size=min(limit, 20)` and returns at most 20 entries.

| Field | Value |
|---|---|
| `primary_id` | `Pfam:<accession>` |
| `primary_label` | entry name |
| `concept_type` | `PROTEIN` for type `family`, `MOLECULAR_ENTITY` for everything else |
| `semantic_types` | `[entry type]`, e.g. `['domain']` |
| `categories` | `clan:<clan>` when the entry has a clan |
| `definitions` | the description (cut to 500 characters) when the API returns one, which is often not the case for Pfam entries |
| `sources` | `['PFAM']` |
| `confidence_score` | `0.85` |

## Concept details

`get_concept_details` accepts `PF00069`, `Pfam:PF00069` or bare digits (prefixed with `PF`) and calls `/entry/pfam/{accession}`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [InterPro adapter](interpro_adapter.md)
- [All adapters](../README.md)
