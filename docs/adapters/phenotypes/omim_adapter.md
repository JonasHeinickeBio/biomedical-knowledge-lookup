---
description: OMIM Mendelian disorders and genes (API key required).
---

# OMIM adapter

Searches Online Mendelian Inheritance in Man and fetches entries by MIM number: preferred title, alternative titles and gene symbols. Entries are typed as diseases or genes depending on the OMIM entry type.

| | |
|---|---|
| Source | `KnowledgeSource.OMIM` |
| Class | `knowledge_lookup.adapters.OMIMAdapter` |
| Requires | `OMIM_API_KEY` |
| Identifiers | `OMIM:219700` (also `MIM:219700` or `219700`) |
| Upstream API | `https://api.omim.org/api` |

{% hint style="warning" %}
**API key required.** OMIM issues API keys on request. The key comes from `LookupConfig(api_keys={"omim": "..."})` or the `OMIM_API_KEY` environment variable (a `.env` file is loaded). Without it `is_available()` is `False`, search returns `[]` and details return `None`.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OMIMAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OMIMAdapter(LookupConfig()) as adapter:
        if not adapter.is_available():
            raise SystemExit("Set OMIM_API_KEY to use OMIM")

        for concept in await adapter.search_concepts("cystic fibrosis", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        entry = await adapter.get_concept_details("OMIM:219700")
        print(entry.primary_label, entry.synonyms[:2])


asyncio.run(main())
```

{% hint style="info" %}
This example has not been run against the live API because no OMIM key was available. Without a key it exits with `Set OMIM_API_KEY to use OMIM`.
{% endhint %}

## Searching

`search_concepts(query, limit)` calls `/entry/search` with `search=<query>`, `limit=min(limit, 20)` and the key as the `apiKey` query parameter. A search returns at most 20 entries.

| Field | Value |
|---|---|
| `primary_id` | `OMIM:<mimNumber>` |
| `primary_label` | `titles.preferredTitle` |
| `synonyms` | alternative and included titles (split on `;;`) |
| `categories` | `gene_symbols:<symbols>` when the entry has a gene map |
| `concept_type` | entry type `gene` or `gene/phenotype` → `GENE`; everything else (including `phenotype`) → `DISEASE` |
| `identifiers` | one `OMIM` identifier |
| `sources` | `['OMIM']` |
| `confidence_score` | `0.9` |
| `source_data[OMIM]` | raw entry |

## Concept details

`get_concept_details(concept_id)` strips `OMIM:` or `MIM:` and calls `/entry?mimNumber=<n>&include=all`. It returns the same fields, built from the full entry.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`. OMIM enforces per-key request limits.

OMIM takes the key as the `apiKey` query parameter, so request URLs contain it. Error messages are logged with the key redacted, but do not log or share the request URLs yourself.

## See also

- [Mondo adapter](../core/mondo_adapter.md): Mondo terms cross-reference OMIM
- [ClinVar adapter](clinvar_adapter.md), [HPO adapter](hpo_adapter.md)
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): API keys
