---
description: InterPro protein families, domains and repeats.
---

# InterPro adapter

Searches InterPro entries (families, domains, repeats, homologous superfamilies) and fetches entry descriptions. Use it to find the InterPro accession for a protein family or domain name.

| | |
|---|---|
| Source | `KnowledgeSource.INTERPRO` |
| Class | `knowledge_lookup.adapters.InterProAdapter` |
| Requires | none |
| Identifiers | `IPR000719` |
| Upstream API | `https://www.ebi.ac.uk/interpro/api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import InterProAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with InterProAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("protein kinase", limit=3):
            print(concept.primary_id, concept.primary_label, concept.semantic_types)

        entry = await adapter.get_concept_details("IPR000719")
        print(entry.primary_label, entry.concept_type, entry.definitions[0][:60])


asyncio.run(main())
```

Output:

```
InterPro:IPR000333 Ser/Thr protein kinase, TGFB receptor ['family']
InterPro:IPR000719 Protein kinase domain ['domain']
InterPro:IPR001245 Serine-threonine/tyrosine-protein kinase, catalytic domain ['domain']
Protein kinase domain MOLECULAR_ENTITY <p>This entry represents the protein kinase domain containin
```

## Searching

`search_concepts(query, limit)` calls `/entry/interpro/?search=...&page_size=min(limit, 20)`, so a search returns at most 20 entries.

| Field | Value |
|---|---|
| `primary_id` | `InterPro:<accession>` |
| `primary_label` | entry name |
| `semantic_types` | `[entry type]`, e.g. `['domain']` |
| `concept_type` | `family` → `PROTEIN`; `domain`, `repeat`, `homologous_superfamily` → `MOLECULAR_ENTITY`; other types → `PROTEIN` |
| `categories` | accessions listed under `metadata.integrated`, if any |
| `sources` | `['INTERPRO']` |
| `confidence_score` | `0.85` |

Search results carry no description.

## Concept details

`get_concept_details` accepts `IPR000719`, `InterPro:IPR000719` or bare digits (`000719` gets the `IPR` prefix) and calls `/entry/interpro/{accession}`. `definitions` holds the description paragraphs, each cut to 500 characters, with the HTML markup InterPro uses (`<p>`, citations) left in place.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [Pfam adapter](pfam_adapter.md): Pfam families from the same API
- [UniProt adapter](../core/uniprot_adapter.md)
- [All adapters](../README.md)
