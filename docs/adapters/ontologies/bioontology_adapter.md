---
description: Full NCBO BioPortal REST client - search, class details, Annotator and generic endpoints (API key required).
---

# BioOntology adapter

A feature-rich client for the NCBO BioPortal REST API (`data.bioontology.org`). It supports search with any BioPortal parameter, class details with related resources, the Annotator for free text, and calls to any endpoint listed at the API root. It uses the same service and key as the [BioPortal adapter](bioportal_adapter.md), which only offers basic search.

| | |
|---|---|
| Source | `KnowledgeSource.BIOONTOLOGY` |
| Class | `knowledge_lookup.adapters.BioOntologyAdapter` |
| Requires | `BIOPORTAL_API_KEY` |
| Identifiers | class IRI plus ontology acronym, e.g. `http://purl.bioontology.org/ontology/MESH/D003920` in `MESH` |
| Upstream API | `https://data.bioontology.org` |

{% hint style="warning" %}
**API key required.** The key is looked up as `get_api_key("bioontology")` and then `get_api_key("bioportal")`: `LookupConfig(api_keys={"bioportal": "..."})`, or the `BIOONTOLOGY_API_KEY` / `BIOPORTAL_API_KEY` environment variables. Without it `is_available()` is `False`.

Every request sends the key in an `Authorization: apikey token=…` header, and an `apikey` parameter passed by a caller is dropped, so the key never appears in request URLs or logs.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import BioOntologyAdapter
from knowledge_lookup.models import LookupConfig

MESH_DM = "http://purl.bioontology.org/ontology/MESH/D003920"


async def main():
    async with BioOntologyAdapter(LookupConfig()) as adapter:
        if not adapter.is_available():
            raise SystemExit("Set BIOPORTAL_API_KEY to use BioOntology")

        hits = await adapter.search_concepts("diabetes", limit=3, extra_params={"ontologies": "MESH"})
        for concept in hits:
            print(concept.primary_id, concept.primary_label, concept.semantic_types)

        dm = await adapter.get_concept_details(MESH_DM, ontology="MESH", fetch_related=False)
        print(dm.primary_label, dm.definitions[0][:50])

        for ann in await adapter.annotate("insulin resistance in obesity", ontologies="MESH"):
            print(ann["annotatedClass"]["@id"])


asyncio.run(main())
```

Output:

```
http://purl.bioontology.org/ontology/MESH/D003920 Diabetes Mellitus ['T047']
http://purl.bioontology.org/ontology/MESH/D048909 Diabetes Complications ['T047']
http://purl.bioontology.org/ontology/MESH/D016640 Diabetes, Gestational ['T047']
Diabetes Mellitus A heterogeneous group of disorders characterized b
http://purl.bioontology.org/ontology/MESH/D007333
http://purl.bioontology.org/ontology/MESH/D009765
```

## Searching

```python
async def search_concepts(
    query: str,
    limit: int = 20,
    raw: bool = False,
    extra_params: dict[str, Any] | None = None,
    **kwargs,  # include, page, pagesize, include_views, display_context, display_links, format
) -> list
```

Calls `/search` with `q` and `pagesize=min(limit, 50)`. Pass other BioPortal search parameters through `extra_params`, for example `{"ontologies": "MESH,SNOMEDCT"}` or `{"require_exact_match": "true"}`. With `raw=True` you get the raw `collection` items instead of concepts.

| Field | Value |
|---|---|
| `primary_id` | class IRI (`@id`) |
| `primary_label` | `prefLabel` |
| `concept_type` | `UNKNOWN` |
| `synonyms`, `definitions` | from `synonym` and `definition` |
| `categories` | UMLS CUIs (`cui`), plus `obsolete` for obsolete classes |
| `semantic_types` | UMLS TUIs (`semanticType`), e.g. `['T047']` |
| `confidence_score` | `0.8` |

## Concept details

```python
async def get_concept_details(
    concept_id: str,
    ontology: str | None = None,   # e.g. "MESH"; inferred from BioPortal/OBO PURLs if omitted
    fetch_related: bool = True,
    extra_params: dict[str, Any] | None = None,
    use_auth_header: bool = False,
    minimal: bool = False,
    raw: bool = False,
    **kwargs,
)
```

- `ontology` is the BioPortal acronym. When omitted it is inferred from BioPortal PURLs (`http://purl.bioontology.org/ontology/MESH/D003920` → `MESH`, `…/ontology/LNC/…` → `LOINC`) and OBO PURLs (`http://purl.obolibrary.org/obo/DOID_9351` → `DOID`), so `CentralKnowledgeLookup.get_concept_details(iri)` works for those IRIs. For any other IRI pass `ontology=`; without it the call logs a `ValueError` and returns `None`.
- IRIs are URL-encoded into `/ontologies/{ontology}/classes/{iri}`.
- With `fetch_related=True` (the default) the adapter follows the class links `children`, `parents`, `ancestors`, `descendants`, `tree`, `notes`, `mappings` and `instances`, one request each. It stores the responses in `source_data["bioontology_<name>"]`, not in `parents` / `children`.
- `minimal=True` returns a dict with `id`, `label`, `synonyms`, `definition` and `obsolete`. `raw=True` returns the JSON.
- `use_auth_header` is accepted for backward compatibility only: the key is always sent as a header.

## Source-specific methods

| Method | Purpose |
|---|---|
| `annotate(text, ontologies=None, longest_only=True, extra_params=None)` | BioPortal Annotator: returns the raw annotation list (`annotatedClass`, `annotations` with text positions) |
| `batch_annotate(texts, ontologies=None, longest_only=True, extra_params=None)` | runs `annotate` for every text concurrently; returns one annotation list per text, in input order (`[]` for a text whose request failed) |
| `get_analytics(ontology=None, month=None, year=None, extra_params=None)` | `/analytics` with the given `ontology`, `month` and `year` filters |
| `fetch_api_endpoints()` | reads the link map at the API root and caches it; also available as the `endpoints` property |
| `call_endpoint(endpoint_name, params=None)` | GET any endpoint from that map by name, e.g. `"ontologies"` |
| `parse_minimal_metadata(concept_details)` | static helper behind `minimal=True` |

## Rate limits and errors

`_make_request` is overridden: it goes through the shared retry (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)) but returns `{}` on any error. Methods therefore return empty results instead of raising. Failed requests are logged at `ERROR` with the API key redacted; request URLs are logged only at `DEBUG`.

## See also

- [BioPortal adapter](bioportal_adapter.md)
- [UMLS adapter](../core/umls_adapter.md)
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): API keys
