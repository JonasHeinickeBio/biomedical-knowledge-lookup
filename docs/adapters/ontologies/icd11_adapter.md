---
description: WHO ICD-11 (MMS) entities and codes via the ICD-API, with parents and children as typed relationships.
---

# WHO ICD-11 adapter

Searches the ICD-11 Mortality and Morbidity Statistics (MMS) linearization and fetches entities by code, for example `8E49` Postviral fatigue syndrome (the ME/CFS context) or `RA02` Post COVID-19 condition. Titles, definitions, index terms and inclusion terms come from the WHO ICD-API, which also serves German and other translations through `Accept-Language`.

> **Not live-verified.** The WHO API needs free credentials and none were used while writing this adapter. It follows the public ICD-API documentation and the OpenAPI description at `https://id.who.int/swagger/v2/swagger.json` (checked keylessly), and is tested with mocked token and API responses only.

| | |
|---|---|
| Source | `KnowledgeSource.ICD11` |
| Class | `knowledge_lookup.adapters.ICD11Adapter` |
| Requires | `ICD11_CLIENT_ID` and `ICD11_CLIENT_SECRET` (free registration at <https://icd.who.int/icdapi>), **or** `ICD11_API_BASE` pointing at a self-hosted ICD-API container |
| Identifiers | MMS code `8E49`, `ICD11:8E49`, numeric MMS entity id (the number at the end of a WHO URI), or a WHO URI |
| Upstream API | `https://id.who.int/icd/release/11/{release}/mms/...` |

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `ICD11_CLIENT_ID`, `ICD11_CLIENT_SECRET` | OAuth2 client credentials (also read from `config.get_api_key("icd11_client_id")` / `("icd11_client_secret")`) | none |
| `ICD11_API_BASE` | API root; set for WHO's Docker container (`docker run -p 80:80 -e acceptLicense=true whoicd/icd-api`), which needs no token | `https://id.who.int` |
| `ICD11_RELEASE` | MMS release id (see the [supported releases](https://icd.who.int/docs/icd-api/SupportedClassifications/)) | `2025-01` |
| `ICD11_LANGUAGE` | `Accept-Language`, for example `de` (German is published for release `2026-01`) | `en` |

`is_available()` is true when both credentials are present or `ICD11_API_BASE` is set.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ICD11Adapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ICD11Adapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("postviral fatigue", limit=3):
            print(concept.primary_id, concept.primary_label)

        mecfs = await adapter.get_concept_details("8E49")
        print(mecfs.primary_label, mecfs.synonyms, mecfs.parents)
        for edge in await adapter.get_relationships("8E49"):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

## Authentication and token handling

The adapter posts `grant_type=client_credentials`, `client_id`, `client_secret` and `scope=icdapi_access` to `https://icdaccessmanagement.who.int/connect/token`. WHO tokens live about one hour; the adapter keeps the token, refreshes it 60 seconds before expiry, and serialises refreshes with an async lock so parallel searches share one token request. When the API answers `401`, the cached token is dropped and the request is retried once with a new one; a second `401` (or a failing token request) makes the call return `[]` / `None`. With `ICD11_API_BASE` set no token is requested and no `Authorization` header is sent. Every request carries `API-Version: v2`, `Accept: application/json` and `Accept-Language`.

## What each method returns

- **`search_concepts(query, limit)`** calls `mms/search?q=...&useFlexisearch=true&flatResults=true&highlightingEnabled=false`. Concepts use the code as `primary_id` (blocks and chapters without a code fall back to the numeric entity id), the title as label, and WHO's relative `score` (capped at 1) as `confidence_score`. `<em class="found">` highlighting is stripped. Chapter 21 symptom codes (`MA`-`MH`) are typed `SYMPTOM`, extension codes (`X...`) `UNKNOWN`, everything else `DISEASE`.
- **`get_concept_details(id)`** resolves a code through `mms/codeinfo/{code}` to the entity id and reads `mms/{id}`. `definitions` hold the definition and long definition; `synonyms` combine index terms and inclusion terms (deprecated ones dropped); `semantic_types` hold the class kind (`category`, `block`, `chapter`); `parents` and `children` hold numeric entity ids; `source_data["ICD11"]` is the raw entity.
- **`get_relationships(id, limit=25)`** returns `is_a` (parents) and `has_subtype` (children, capped at `limit`). The entity page lists neighbours only as URIs, so each one is fetched (4 at a time) to obtain its code and title.
- **`get_mappings(id)`** returns a single `foundation_uri` mapping from the MMS code to the ICD-11 Foundation entity URI (`source` field). The API offers no ICD-10 crosswalk.

Post-coordination (`stem/extension` and `&` combinations) is ignored: only the stem code is resolved.

## Licence and caveats

ICD-11 is a WHO work licensed under CC BY-ND 3.0 IGO (no derivatives, attribution required); read the [licence](https://icd.who.int/en/docs/icd11-license.pdf) and the API terms before redistributing content. The API enforces fair-use request limits; the adapter uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Interface methods never raise: failures are logged and give `[]` / `None`.

## See also

- [ICD-10-GM adapter](icd10gm_adapter.md) for the German ICD-10 coding of the same conditions (`G93.3`)
- [All adapters](../README.md)
