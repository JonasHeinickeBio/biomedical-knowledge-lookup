---
description: SNOMED CT concepts, synonyms, is-a hierarchy and attribute relationships through a Snowstorm server (SNOMED International licence applies; not live-verified).
---

# SNOMED CT (Snowstorm) adapter

Searches SNOMED CT and reads concepts, synonyms, is-a parents/children and attribute relationships (finding site, morphology, causative agent, ...) from a [Snowstorm](https://github.com/IHTSDO/snowstorm) terminology server.

> **Status: not live-verified.** The default public server refused every connection from the development network (`Connection refused` on port 443 for `browser.ihtsdotools.org` and `snowstorm.ihtsdotools.org`, repeated over several minutes, while other hosts were reachable). Parsing follows Snowstorm's documented JSON layout and is tested against *synthetic* fixtures that mirror it (`tests/fixtures/snomedct_responses.py`). Run `knowledge-lookup check SNOMEDCT` from a network that can reach your server before relying on this adapter, and expect small fixes (field names, the `groupByConcept` and `members` parameters) if the first live run shows differences.

| | |
|---|---|
| Source | `KnowledgeSource.SNOMEDCT` |
| Class | `knowledge_lookup.adapters.SnomedCTAdapter` |
| Requires | none for the code; **a SNOMED CT licence for the content** (see below) |
| Identifiers | SCTID: `84229001` (fatigue), `52448006` (dementia); also `SNOMEDCT:84229001`, `SNOMED:84229001`, `SCTID:84229001` |
| Upstream API | Snowstorm REST API, default `https://browser.ihtsdotools.org/snowstorm/snomed-ct` |

## Licence (read this first)

SNOMED CT is **not open data**. It is owned by SNOMED International and licensed under the SNOMED CT Affiliate Licence:

- In SNOMED International **member countries** the content is free to use under the national licence. **Germany is a member**; the German release and licensing are handled nationally (BfArM). Check the current terms of your own country.
- Elsewhere an **Affiliate Licence** is required (registration, acceptance of the terms; research use is generally free of charge).
- The default endpoint is SNOMED International's **public browser instance**: it is a demonstration server with rate limits and no service guarantee and is **not for bulk or production use**. The adapter spaces requests about 1 s apart on it, caches concept views per adapter instance and caps result sizes. For anything beyond occasional lookups use a national or self-hosted Snowstorm via `SNOMED_SNOWSTORM_URL`.
- Do not redistribute SNOMED CT content (labels, hierarchies) together with your data unless your licence allows it.

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `SNOMED_SNOWSTORM_URL` | `https://browser.ihtsdotools.org/snowstorm/snomed-ct` | Snowstorm base URL (trailing slash ignored). A non-default URL is treated as private and throttled at 10 requests/s instead of 1/s. |
| `SNOMED_SNOWSTORM_BRANCH` | `MAIN` | Code-system branch. `MAIN` is the latest International Edition; national extensions have their own branch (e.g. `MAIN/SNOMEDCT-DE`) and dated releases live under `MAIN/<yyyy-mm-dd>`. `GET {base}/codesystems` lists the branch paths of a server. |

Both are re-read on every request. Every request sends `Accept: application/json`, `Accept-Language: en` and a descriptive `User-Agent`.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import SnomedCTAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with SnomedCTAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("fatigue", limit=3):
            print(concept.primary_id, concept.primary_label, concept.semantic_types)

        fatigue = await adapter.get_concept_details("SNOMEDCT:84229001")
        print(fatigue.primary_label, fatigue.synonyms[:3])
        print(fatigue.source_data["SNOMEDCT"]["fsn"])

        for edge in await adapter.get_relationships("52448006", limit=10):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

No captured output is shown because the service could not be reached (see the status note).

## Endpoints used

| Method | Request |
|---|---|
| `search_concepts` | `GET /{branch}/descriptions?term=&active=true&conceptActive=true&groupByConcept=true&limit=` |
| `get_concept_details`, `get_relationships` | `GET /browser/{branch}/concepts/{id}` (one request, cached on the adapter) |
| `get_relationships` (children) | `GET /{branch}/concepts/{id}/children?form=inferred` |
| `get_mappings` | `GET /{branch}/members?referenceSet=447562003&referencedComponentId={id}&active=true` |

## Searching

Active descriptions of active concepts are searched with Snowstorm's relevance ranking; hits are collapsed to one concept each. A bare SCTID query returns that concept. Each hit becomes a concept with the preferred term (PT) as label, the FSN and its semantic tag in `source_data`, and the matched synonym in `synonyms`.

`concept_type` from the FSN semantic tag:

| Tag | Type |
|---|---|
| `disorder` | `DISEASE` |
| `finding`, `morphologic abnormality` | `PHENOTYPE` (SNOMED findings cover symptoms and signs) |
| `procedure` | `PROCEDURE` |
| `regime/therapy` | `TREATMENT` |
| `body structure` | `ANATOMICAL_ENTITY` |
| `cell`, `cell structure` | `CELL_TYPE`, `CELLULAR_COMPONENT` |
| `organism` | `ORGANISM` |
| `substance` | `CHEMICAL` |
| `medicinal product`, `medicinal product form`, `clinical drug`, `product` | `DRUG` |
| `observable entity` | `OBSERVATION` |
| anything else | `UNKNOWN` |

## Concept details

| Field | Value |
|---|---|
| `primary_label` | preferred term |
| `synonyms` | active English synonym descriptions (PT and FSN stem excluded) |
| `definitions` | active `TEXT_DEFINITION` descriptions (few concepts have one in the International Edition) |
| `semantic_types` | `[semantic tag]` |
| `source_data[SNOMEDCT]` | `sctid`, `fsn`, `semantic_tag`, `active`, `branch`, `definition_status`, `module_id`, `effective_time` |

## Relationships

`get_relationships(concept_id, limit=50)`, inferred form only (stated duplicates and inactive rows are skipped):

- `is_a`: the related concept is a parent
- attribute edges named after the attribute: `finding_site`, `associated_morphology`, `causative_agent`, ... (extras `group` = role group, `attribute_id` = attribute SCTID); an attribute without a name becomes `attribute_<SCTID>`
- `has_subtype`: the related concept is a child (one extra request)

The order is parents, attributes, then children, so `limit` trims children first (broad concepts have thousands of children).

## Mappings

`get_mappings` reads the International Edition's ICD-10 complex map reference set (`447562003`) and returns `mappingType` `icd10_complex_map` with `mapGroup`, `mapPriority`, `mapRule` and `mapAdvice` extras. Both the endpoint and the field names are from the Snowstorm documentation and **not live-verified**; national editions usually carry their own maps (for Germany, ICD-10-GM maps come from the national release) and then this returns `[]`. For coding work against ICD-10-GM use the [ICD-10-GM adapter](icd10gm_adapter.md).

## Rate limits and errors

Requests are spaced at least 1 s apart on the public server and use a 30 s timeout floor (the public instance can be slow). Shared retry/circuit-breaker applies (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Interface methods never raise: search returns `[]`, details `None`, and an unreachable server only logs an error.

## Not implemented

ECL queries, reference-set membership beyond the ICD-10 map, history/replacements of inactive concepts and language-specific preferred terms (the adapter asks for English only).

## See also

- [ICD-10-GM adapter](icd10gm_adapter.md), [UMLS adapter](../core/umls_adapter.md) (SNOMED CT crosswalks through the Metathesaurus)
- [All adapters](../README.md)
