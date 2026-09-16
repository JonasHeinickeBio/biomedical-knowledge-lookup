---
description: Wikidata items via the Wikidata Query Service - labels, descriptions, UMLS and MeSH cross-references.
---

# Wikidata adapter

Searches Wikidata items by label and fetches item details, including UMLS CUI, MeSH, ICD-10 and NCBI Taxonomy cross-references, through the Wikidata Query Service. Useful as a bridge between biomedical IDs and general knowledge.

| | |
|---|---|
| Source | `KnowledgeSource.WIKIDATA` |
| Class | `knowledge_lookup.adapters.WikidataAdapter` |
| Requires | none |
| Identifiers | `Q18216` |
| Upstream API | `https://query.wikidata.org/sparql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import WikidataAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with WikidataAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("metformin", limit=3):
            print(concept.primary_id, concept.primary_label, concept.definitions)

        aspirin = await adapter.get_concept_details("Q18216")
        print(aspirin.primary_label, aspirin.concept_type)
        print([(i.source, i.identifier) for i in aspirin.identifiers], aspirin.categories)


asyncio.run(main())
```

Output:

```
Q19484 metformin ['chemical compound']
Q22250907 Q22250907 []
Q27089363 metformin hydrochloride ['chemical compound']
aspirin CHEMICAL
[('WIKIDATA', 'Q18216'), ('UMLS', 'C0004057')] ['MeSH: D001241', 'type of chemical entity']
```

## Searching

`search_concepts(query, limit)` runs a SPARQL query that calls the MediaWiki `EntitySearch` API (English) through `wikibase:mwapi`. A subquery takes the first `limit` items by search rank (`wikibase:apiOrdinal`), and the outer query joins their optional "instance of" (P31) labels.

The best match therefore comes first, and each item is returned once: the rows of an item with several P31 values are merged, so `categories` lists all of its instance-of labels. Items without an English label get their Q-ID as label, like `Q22250907` in the output. The query text is passed as an escaped SPARQL string literal, so quotes and backslashes in the query are safe.

| Field | Value |
|---|---|
| `primary_id` | Q-ID |
| `primary_label` | English label |
| `definitions` | item description |
| `categories` | all instance-of labels, each once |
| `concept_type` | from the first instance-of label that maps to a type: disease/disorder/syndrome → `DISEASE`, drug/pharmaceutical/medication → `DRUG`, gene → `GENE`, protein → `PROTEIN`, chemical/compound → `CHEMICAL`, taxon/species/organism → `ORGANISM`, else `UNKNOWN` |
| `identifiers` | one `WIKIDATA` identifier; the URL is the entity IRI |
| `confidence_score` | `0.7` |

## Concept details

`get_concept_details(qid)` only accepts IDs of the form `Q` followed by digits; anything else returns `None` without a request. It collects:

- label, description and all instance-of labels as `categories`
- the UMLS CUI (P2892) as a `UMLS` identifier
- the MeSH descriptor ID (P486) as a `MeSH: <id>` category (there is no MeSH `KnowledgeSource`)
- ICD-10 (P494) as `ICD-10: <code>` and NCBI Taxonomy (P685) as `NCBI Taxon: <id>` categories
- `confidence_score` `0.8`, with all SPARQL bindings in `source_data[WIKIDATA]`

The query returns one row per combination of optional values; identifiers and categories are de-duplicated across rows.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). The Wikidata Query Service throttles heavy clients with HTTP 429, which is retried with backoff. Other errors are logged; search returns `[]` and details return `None`.

## See also

- [DBpedia adapter](dbpedia_adapter.md), [UMLS adapter](../core/umls_adapter.md)
- [All adapters](../README.md)
