---
description: COSMIC cancer genes and somatic mutations (requires COSMIC account credentials; no query API is currently available).
---

# COSMIC adapter

Meant to look up cancer genes in COSMIC, the Catalogue of Somatic Mutations in Cancer: role in cancer, tier, synonyms and hallmarks.

| | |
|---|---|
| Source | `KnowledgeSource.COSMIC` |
| Class | `knowledge_lookup.adapters.COSMICAdapter` |
| Requires | COSMIC account credentials (`COSMIC_API_KEY`) |
| Identifiers | `COSMIC:TP53` |
| Upstream API | `https://cancer.sanger.ac.uk/api/rest/cosmic` |

{% hint style="warning" %}
**Credentials required, and no query API is currently available.** COSMIC has no public, keyless API: programmatic access needs a registered COSMIC account, and COSMIC currently offers authenticated file downloads rather than a gene or mutation query endpoint. The legacy REST endpoint the adapter calls (`/genes`) answers HTTP 404 with or without credentials.

- Without credentials `is_available()` is `False`, so `CentralKnowledgeLookup` skips COSMIC. Direct calls log a warning and return `[]` / `None` without sending a request.
- With credentials the request is sent; the 404 is logged at `ERROR` level with this explanation, and the calls return `[]` / `None`.

For clinically interpreted variants, use the [ClinVar adapter](../phenotypes/clinvar_adapter.md).
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import COSMICAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with COSMICAdapter(LookupConfig()) as adapter:
        print(adapter.is_available())
        print(await adapter.search_concepts("TP53", limit=3))


asyncio.run(main())
```

Output (without credentials; the warning is logged):

```
False
[]
```

## Searching

Credentials are the base64 encoding of `email:password` for a COSMIC account, passed as `api_keys={"cosmic": ...}` or `COSMIC_API_KEY`. With credentials, `search_concepts(query, limit)` requests `/genes?gene_name=<query>&limit=min(limit, 25)` with `Authorization: Basic <key>`. Any gene record would become a `GENE` concept:

- `primary_id`: `COSMIC:<id>`
- `categories`: `role_in_cancer:...` and `tier:...`
- `synonyms`: gene synonyms
- `semantic_types`: hallmarks
- `confidence_score`: `0.85`

## Concept details

`get_concept_details(concept_id)` strips a `COSMIC:` prefix and requests `/genes/{id}` (credentials required, as above).

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). 404 responses are not retried.

## See also

- [ClinVar adapter](../phenotypes/clinvar_adapter.md): clinical variants from NCBI
- [All adapters](../README.md)
