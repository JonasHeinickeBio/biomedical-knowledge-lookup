---
description: Ensembl gene records by stable ID or human gene symbol.
---

# Ensembl adapter

Fetches gene records from the Ensembl REST API (display name, description, biotype, species) and resolves human gene symbols to Ensembl gene IDs.

| | |
|---|---|
| Source | `KnowledgeSource.ENSEMBL` |
| Class | `knowledge_lookup.adapters.EnsemblAdapter` |
| Requires | none |
| Identifiers | stable ID, e.g. `ENSG00000139618` |
| Upstream API | `https://rest.ensembl.org` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EnsemblAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with EnsemblAdapter(LookupConfig()) as adapter:
        brca2 = await adapter.get_concept_details("ENSG00000139618")
        print(brca2.primary_id, brca2.primary_label, brca2.categories)
        print(brca2.definitions[0])

        for concept in await adapter.search_concepts("TP53", limit=2):
            print(concept.primary_id, concept.primary_label)


asyncio.run(main())
```

Output (this run took about 50 seconds, mostly the symbol lookup):

```
ENSG00000139618 BRCA2 ['Biotype: protein_coding', 'Species: homo_sapiens']
BRCA2 DNA repair associated [Source:HGNC Symbol;Acc:HGNC:1101]
ENSG00000141510 TP53
LRG_321 TP53
```

## Searching

`search_concepts(query, limit)` is a **human gene symbol lookup**, not free-text search:

1. `/xrefs/symbol/homo_sapiens/{query}` returns matching Ensembl and LRG IDs.
2. `get_concept_details` is called for each of the first `limit` IDs.

The query must be a symbol or synonym known to Ensembl; other species are not searched. Each search costs one request plus one per result, and the xrefs endpoint can take ten seconds or more.

## Concept details

`get_concept_details(stable_id)` calls `/lookup/id/{id}?expand=1`.

| Field | Value |
|---|---|
| `primary_id` | stable ID |
| `primary_label` | `display_name` |
| `concept_type` | `GENE` (also for transcript or LRG IDs) |
| `definitions` | `[description]` |
| `categories` | `Biotype: <biotype>`, `Species: <species>` |
| `identifiers` | one `ENSEMBL` identifier, URL `https://www.ensembl.org/id/<id>` |
| `confidence_score` | `1.0` |
| `source_data[ENSEMBL]` | full lookup response (with `expand=1`, including transcripts) |

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`. Through `CentralKnowledgeLookup` the whole search must finish within `timeout_per_source` (default 30 s), which a slow symbol lookup can exceed. Raise the timeout, or call `get_concept_details` when you already have the ID.

## See also

- [HGNC adapter](hgnc_adapter.md): symbol → HGNC record with the Ensembl ID
- [Open Targets adapter](../core/opentargets_adapter.md): uses Ensembl gene IDs for targets
- [All adapters](../README.md)
