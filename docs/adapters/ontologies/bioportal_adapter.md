---
description: Search across 1000+ ontologies in NCBO BioPortal - SNOMED CT, MeSH, LOINC, ICD and more (API key required).
---

# BioPortal adapter

Runs term searches across all ontologies in NCBO BioPortal and returns one concept per matching class, and fetches class details. It is a small wrapper; for the Annotator, related resources (parents, children, mappings) and other endpoints use the [BioOntology adapter](bioontology_adapter.md), which talks to the same API.

| | |
|---|---|
| Source | `KnowledgeSource.BIOPORTAL` |
| Class | `knowledge_lookup.adapters.BioPortalAdapter` |
| Requires | `BIOPORTAL_API_KEY` |
| Identifiers | class IRI, e.g. `http://purl.bioontology.org/ontology/MESH/D003920` |
| Upstream API | `https://data.bioontology.org` |

{% hint style="warning" %}
**API key required.** The key comes from `LookupConfig(api_keys={"bioportal": "..."})` or the `BIOPORTAL_API_KEY` environment variable (a `.env` file is loaded). Without it `is_available()` is `False` and `CentralKnowledgeLookup` skips the source. You get a key with a free BioPortal account.

The key is sent in the `Authorization` header, never in the request URL, so it does not show up in logged errors.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import BioPortalAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with BioPortalAdapter(LookupConfig()) as adapter:
        if not adapter.is_available():
            raise SystemExit("Set BIOPORTAL_API_KEY to use BioPortal")

        for concept in await adapter.search_concepts("diabetes mellitus", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)


asyncio.run(main())
```

Output:

```
http://purl.bioontology.org/ontology/MESH/D003920 Diabetes Mellitus ['https://data.bioontology.org/ontologies/MESH']
http://purl.bioontology.org/ontology/SNOMEDCT/73211009 Diabetes mellitus ['https://data.bioontology.org/ontologies/SNOMEDCT']
http://purl.bioontology.org/ontology/LNC/LA14291-1 Diabetes mellitus ['https://data.bioontology.org/ontologies/LOINC']
```

## Searching

`search_concepts(query, limit)` calls `/search` with `q` and `pagesize=min(limit, 50)`; the key goes in an `Authorization: apikey token=…` header.

| Field | Value |
|---|---|
| `primary_id` | class IRI (`@id`) |
| `primary_label` | `prefLabel` |
| `synonyms`, `definitions` | from `synonym` and `definition` |
| `categories` | `[ontology link]`, e.g. `https://data.bioontology.org/ontologies/MESH` |
| `identifiers` | one `BIOPORTAL` identifier |
| `confidence_score` | `0.8` |
| `source_data[BIOPORTAL]` | raw search item |

`concept_type` is guessed from the ontology link by substring: `doid`/`mondo`/`ordo` → `DISEASE`, `drugbank` → `DRUG`, `chebi` → `CHEMICAL`, `go`/`so` → `GENE`, `uberon`/`fma` → `ANATOMICAL_ENTITY`, `hp`/`mp` → `PHENOTYPE`, otherwise `UNKNOWN`. Large vocabularies such as MeSH, SNOMED CT and LOINC come back as `UNKNOWN`.

## Concept details

`get_concept_details(concept_id, ontology=None)` fetches `/ontologies/{acronym}/classes/{URL-encoded IRI}` and returns the class with `synonyms` and `definitions` (`confidence_score` `0.85`).

- `concept_id` is a class IRI as returned by `search_concepts`, or the class's `links.self` URL.
- `ontology` is the BioPortal acronym, e.g. `"MESH"`. When omitted it is inferred from BioPortal PURLs (`http://purl.bioontology.org/ontology/MESH/D003920` → `MESH`, `…/ontology/LNC/…` → `LOINC`) and OBO PURLs (`http://purl.obolibrary.org/obo/DOID_9351` → `DOID`). For any other IRI pass `ontology=`; without it the method returns `None` without making a request.
- BioPortal's default class response has no `parents` / `children`, so those stay empty. Use the BioOntology adapter with `fetch_related=True` for the hierarchy.

```python
dm = await adapter.get_concept_details("http://purl.bioontology.org/ontology/MESH/D003924")
print(dm.primary_label)  # Diabetes Mellitus, Type 2
```

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged with the API key redacted; search returns `[]` and details return `None`.

## See also

- [BioOntology adapter](bioontology_adapter.md)
- [OLS adapter](../core/ols_adapter.md): keyless alternative for many of the same ontologies
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): API keys
