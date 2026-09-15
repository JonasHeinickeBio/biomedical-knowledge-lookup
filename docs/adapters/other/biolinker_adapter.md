---
description: TIB BioLinker AI - link entities and predicates in free text to UMLS concepts.
---

# BioLinker adapter

Sends free text to the TIB BioLinker AI service, which recognises entities and predicates and links them to UMLS concepts. `search_concepts` expects a sentence or passage rather than a single term, and the adapter adds sentence-level helpers that group the results into entities, predicates and candidate relations.

| | |
|---|---|
| Source | `KnowledgeSource.BIOLINKER` |
| Class | `knowledge_lookup.adapters.BioLinkerAdapter` |
| Requires | none |
| Identifiers | input is text; results use UMLS CUIs, e.g. `C0025598` |
| Upstream API | `https://labs.tib.eu/biolinkerai/process-text` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import BioLinkerAdapter
from knowledge_lookup.models import LookupConfig

TEXT = "Metformin is used to treat type 2 diabetes."


async def main():
    async with BioLinkerAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts(TEXT):
            print(concept.primary_id, concept.primary_label, concept.categories, concept.concept_type)

        annotation = await adapter.annotate_sentence(TEXT)
        print([e["surface_form"] for e in annotation["entities"]], len(annotation["relations"]))


asyncio.run(main())
```

Output (the service is non-deterministic; repeated calls can link different spans):

```
C0025598 metformin ['entities'] DRUG
C0011860 type 2 diabetes ['entities'] UNKNOWN
C1880036 regimen used to treat breast carcinoma ['predicates'] PROCEDURE
['type 2 diabetes'] 0
```

## Searching

`search_concepts(query, limit)` POSTs `{"input_text": query, "k": depth}`. The search depth `k` depends on the length of the text: 25 for fewer than 3 words, 100 for more than 10 words, otherwise 50. Each result's best candidate becomes a concept:

| Field | Value |
|---|---|
| `primary_id` | linked ID (a UMLS CUI) |
| `primary_label` | candidate label |
| `concept_type` | keyword match on the candidate types (disease → `DISEASE`, drug/pharmacologic/substance → `DRUG`, gene, protein, pathway, organism, anatomy, phenotype, chemical, procedure), else `UNKNOWN` |
| `semantic_types` | candidate types as returned (sometimes a single stringified list) |
| `categories` | `['entities']` or `['predicates']` |
| `definitions` | candidate description |
| `synonyms` | the matched surface form, if it differs from the label |
| `identifiers` | one `BIOLINKER` identifier, with a UTS URL for CUIs |
| `confidence_score` | 0.7, plus 0.1 with a description, 0.1 with types, 0.05 for entities, 0.05 if the surface form equals the label |
| `source_data[BIOLINKER]` | `surface_form`, `text_position` (`start`, `end`), `category` |

## Concept details

Not supported: BioLinker has no lookup by ID, so `get_concept_details` logs a warning and returns `None`. Resolve CUIs with the [UMLS adapter](../core/umls_adapter.md).

## Source-specific methods

| Method | Returns |
|---|---|
| `search_concepts_with_depth(query, limit=20, search_depth=50)` | same as `search_concepts` with an explicit `k` |
| `annotate_sentence(sentence, search_depth=50)` | dict with `sentence`, `search_depth`, `total_concepts`, `entities`, `predicates`, `relations`, `concept_map`; on failure a dict with `error` |
| `annotate_multiple_sentences(sentences, search_depth=50)` | list of `annotate_sentence` results, with a 0.5 s pause between sentences |

Entities and predicates are dicts with `surface_form`, `label`, `id`, `type`, `semantic_types`, `position`, `confidence` and `definition`. `relations` is a proximity heuristic: for each predicate, the two nearest entities within 50 characters become subject and object.

## Rate limits and errors

The adapter opens its own HTTP session with a 180-second total timeout, ignoring `timeout_per_source`. Requests go through the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); non-200 responses are raised as `OSError` and retried by category. Errors are logged and search returns `[]`. Calls took 7–15 seconds in testing. Through `CentralKnowledgeLookup` the 30-second `timeout_per_source` still applies.

## See also

- [UMLS adapter](../core/umls_adapter.md)
- [BioOntology adapter](../ontologies/bioontology_adapter.md): BioPortal Annotator
- [All adapters](../README.md)
