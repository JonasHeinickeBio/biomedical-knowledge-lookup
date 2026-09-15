---
description: RCSB Protein Data Bank structure entries - titles, experimental method, resolution.
---

# PDB adapter

Runs full-text searches against the RCSB PDB and fetches entry summaries: title, experimental method, resolution and initial release date. Use it to find experimental structures for a protein.

| | |
|---|---|
| Source | `KnowledgeSource.PDB` |
| Class | `knowledge_lookup.adapters.PDBAdapter` |
| Requires | none |
| Identifiers | `4HHB` (or `PDB:4HHB`) |
| Upstream API | search `https://search.rcsb.org/rcsbsearch/v2`, entries `https://data.rcsb.org/rest/v1/core` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import PDBAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with PDBAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("hemoglobin", limit=3):
            print(concept.primary_id, concept.primary_label[:50])

        entry = await adapter.get_concept_details("4HHB")
        print(entry.primary_id, entry.categories)


asyncio.run(main())
```

Output:

```
PDB:2PGH STRUCTURE DETERMINATION OF AQUOMET PORCINE HEMOGLO
PDB:3PEL Structure of Greyhound Hemoglobin: Origin of High
PDB:3GOU Crystal structure of dog (Canis familiaris) hemogl
PDB:4HHB ['method:X-RAY DIFFRACTION', 'resolution:1.74Å']
```

## Searching

`search_concepts(query, limit)` POSTs a `full_text` query to `/query` with `return_type: entry` and up to `min(limit, 25)` rows, then fetches `/entry/{id}` for every hit (one extra request per result). Hits are ordered by RCSB relevance.

| Field | Value |
|---|---|
| `primary_id` | `PDB:<entry id>` |
| `primary_label` | `struct.title` |
| `concept_type` | `PROTEIN` |
| `semantic_types` | comma-separated parts of `struct.pdbx_descriptor` |
| `categories` | `method:<experimental method>`, `resolution:<Å>` |
| `last_updated` | date of the first revision (initial release) |
| `sources` | `['PDB']` |
| `confidence_score` | `0.85` |
| `source_data[PDB]` | full entry JSON |

## Concept details

`get_concept_details` strips a `PDB:` prefix, upper-cases the ID and returns the same entry conversion.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`. A failed entry fetch during search only drops that hit.

## See also

- [UniProt adapter](../core/uniprot_adapter.md), [InterPro adapter](interpro_adapter.md)
- [All adapters](../README.md)
