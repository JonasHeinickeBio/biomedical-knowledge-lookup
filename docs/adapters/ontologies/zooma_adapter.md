---
description: EBI ZOOMA - map free-text annotation values to ontology terms using curated annotations.
---

# ZOOMA adapter

Sends a text value, for example a sample attribute such as "heart attack", to EBI ZOOMA and returns the ontology terms that curated annotations map it to, each with ZOOMA's confidence level. Use it to annotate metadata values with ontology IRIs.

| | |
|---|---|
| Source | `KnowledgeSource.ZOOMA` |
| Class | `knowledge_lookup.adapters.ZoomaAdapter` |
| Requires | none |
| Identifiers | ontology term IRIs, e.g. `http://purl.obolibrary.org/obo/HP_0001658` |
| Upstream API | `https://www.ebi.ac.uk/spot/zooma/v2/api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ZoomaAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ZoomaAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("heart attack", limit=3):
            print(concept.primary_id, concept.confidence_score, concept.categories)


asyncio.run(main())
```

Output:

```
http://purl.obolibrary.org/obo/HP_0001658 0.9 ['Source: hp']
http://purl.obolibrary.org/obo/DOID_5844 0.9 ['Source: doid']
http://purl.obolibrary.org/obo/MONDO_0005068 0.9 ['Source: mondo']
```

## Searching

`search_concepts(query, limit)` calls `/services/annotate?propertyValue=<query>` and keeps the first `limit` annotations.

| Field | Value |
|---|---|
| `primary_id` | first semantic tag (term IRI); additional tags are ignored |
| `primary_label` | the annotated property value (the matched text), **not** the term label |
| `concept_type` | `UNKNOWN` |
| `confidence_score` | ZOOMA confidence: `HIGH` 0.9, `GOOD` 0.7, `MEDIUM` 0.5, `LOW` 0.3 |
| `categories` | `Source: <provenance source name>` |
| `source_data[ZOOMA]` | raw annotation |

To get the term label, pass the IRI to `OLSAdapter.get_concept_details`.

## Concept details

Not supported: `get_concept_details` always returns `None`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged and search returns `[]`.

## See also

- [OLS adapter](../core/ols_adapter.md): resolve the returned IRIs
- [BioOntology adapter](bioontology_adapter.md): BioPortal Annotator for longer text
- [All adapters](../README.md)
