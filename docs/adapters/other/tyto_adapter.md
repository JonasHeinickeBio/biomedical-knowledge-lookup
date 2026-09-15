---
description: Ontology term lookup (SO, SBO, NCIT) through the tyto library.
---

# Tyto adapter

Resolves ontology term URIs to labels and exact labels to term URIs with the `tyto` library, which is used in synthetic-biology tooling. The adapter supports the Sequence Ontology (SO), the Systems Biology Ontology (SBO) and the NCI Thesaurus (NCIT).

| | |
|---|---|
| Source | `KnowledgeSource.TYTO` |
| Class | `knowledge_lookup.adapters.TytoAdapter` |
| Requires | `[tyto]` extra |
| Identifiers | term URI, e.g. `http://purl.obolibrary.org/obo/SO_0000167`, `http://identifiers.org/SBO:0000241` |
| Upstream API | Ontobee SPARQL endpoint, through `tyto`; `tyto` also ships SO and SBO as local OWL files |

{% hint style="info" %}
**Exact labels only.** `tyto` has no free-text search: `search_concepts` finds a term only when the query is its whole label (case-insensitive), and returns at most one term per ontology.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import TytoAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with TytoAdapter(LookupConfig()) as adapter:
        print("available:", adapter.is_available())
        for concept in await adapter.search_concepts("promoter"):
            print(concept.primary_id, concept.primary_label, concept.categories)

        term = await adapter.get_concept_details("http://identifiers.org/SBO:0000241")
        print(term.primary_label, term.categories)


asyncio.run(main())
```

Output:

```
available: True
https://identifiers.org/SO:0000167 promoter ['SO']
https://identifiers.org/ncit:C13297 Promoter ['NCIT']
functional entity ['SBO']
```

## Searching

`search_concepts(query, limit)` asks SO, SBO and NCIT, in that order, for a term whose label equals the query, using each ontology's `get_uri_by_term`. Spaces in the query also match `-` and `_`. Labels that match several terms in one ontology are skipped; `promoter` is ambiguous in SBO, which is why SBO is missing from the output.

| Field | Value |
|---|---|
| `primary_id` | term URI as `tyto` returns it (identifiers.org form, e.g. `https://identifiers.org/SO:0000167`) |
| `primary_label` | the term's label from `get_term_by_uri`; falls back to the query |
| `categories` | the ontology name (`SO`, `SBO` or `NCIT`) |
| `identifiers` | one `TYTO` identifier; the URL is the term URI |
| `concept_type` | `UNKNOWN` |
| `confidence_score` | `1.0` |
| `source_data[TYTO]` | `ontology`, `uri`, `label` |

`tyto` puts the label into a SPARQL regular expression without escaping, so the adapter only accepts queries made of letters, digits, spaces and hyphens. Anything else (quotes, dots, `5' UTR`) logs a warning and returns `[]`.

## Concept details

`get_concept_details(uri)` accepts SO, SBO and NCIT term URIs in PURL form (`http://purl.obolibrary.org/obo/SO_...`, `http://biomodels.net/SBO/SBO_...`, `http://purl.obolibrary.org/obo/NCIT_...`) or identifiers.org form (`http://` or `https://`). It calls the ontology's `get_term_by_uri` and returns a concept like a search result, with the URI exactly as given as `primary_id`.

IDs that do not start with `http` return `None`. URIs of other ontologies log a warning and return `None`, as do unknown terms and URIs containing characters that are not allowed in an IRI.

## Rate limits and errors

The `tyto` calls run in a worker thread through `_thread_with_retry`, which applies the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). A term that is not found is not an error. If one ontology fails, a warning is logged and the others are still searched; only when all three fail is the error retried and reported to the circuit breaker, and search returns `[]`.

Each lookup is a SPARQL request to Ontobee, and a search makes up to six. When a label is not found online, `tyto` loads its bundled SO or SBO OWL file, which takes a few seconds the first time. `tyto` logs through its own logger, for example `Ambiguous term promoter--found multiple URIs ...` at `ERROR` level. If `tyto` is not installed, importing the module logs a warning and `is_available()` is `False`.

## See also

- [OLS adapter](../core/ols_adapter.md): search and resolve terms of most OBO ontologies
- [All adapters](../README.md)
