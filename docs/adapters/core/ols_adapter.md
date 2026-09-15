---
description: Free-text search across every ontology in the EMBL-EBI Ontology Lookup Service (OLS4).
---

# OLS adapter

Searches all ontologies loaded in EMBL-EBI OLS4 (DOID, EFO, NCIT, UBERON, ChEBI, HP, MeSH, SNOMED and many more) and fetches terms by IRI. It is the best default when you have a free-text term and don't know which ontology it belongs to.

| | |
|---|---|
| Source | `KnowledgeSource.OLS` |
| Class | `knowledge_lookup.adapters.OLSAdapter` |
| Requires | none |
| Identifiers | term IRI, e.g. `http://purl.obolibrary.org/obo/MONDO_0005148` |
| Upstream API | `https://www.ebi.ac.uk/ols4/api` |

## Quick example

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.adapters import OLSAdapter


async def main():
    # Directly
    async with OLSAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("diabetes mellitus", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories, concept.concept_type)

        term = await adapter.get_concept_details("http://purl.obolibrary.org/obo/MONDO_0005148")
        print(term.primary_label, term.categories[:2])

    # Through CentralKnowledgeLookup
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.OLS]))
    try:
        result = await lookup.search_concepts("asthma", sources=[KnowledgeSource.OLS], max_results=2)
        print([c.primary_label for c in result.concepts])
    finally:
        await lookup.close()


asyncio.run(main())
```

Output:

```
http://purl.obolibrary.org/obo/HP_0000819 Diabetes mellitus ['hp'] PHENOTYPE
http://purl.obolibrary.org/obo/NCIT_C2985 Diabetes Mellitus ['ncit'] UNKNOWN
http://purl.obolibrary.org/obo/DOID_9351 diabetes mellitus ['doid'] DISEASE
type 2 diabetes mellitus ['Xref: DOID:9352', 'Xref: ICD10CM:E11']
['Asthma']
```

## Searching

`search_concepts(query, limit)` calls `/search?q=...&rows=min(limit, 100)` across all ontologies. For each hit:

| Field | Value |
|---|---|
| `primary_id` | term IRI |
| `primary_label` | term label |
| `identifiers` | two `OLS` identifiers: the IRI (also used as URL) and the short form, e.g. `HP_0000819` |
| `definitions` | from `description` |
| `synonyms` | from `synonym`, when the search document has it |
| `categories` | `[ontology_name]`, e.g. `['doid']` |
| `confidence_score` | `0.8` |
| `source_data[OLS]` | raw search document |

Identifiers and `source_data` are keyed by the adapter's `get_source()`, so a subclass such as the [EBI OLS adapter](../ontologies/ebiols_adapter.md) records them under its own source.

`concept_type` is derived from the ontology name:

| Ontology | `concept_type` |
|---|---|
| `doid`, `mondo`, `ordo` | `DISEASE` |
| `drugbank` | `DRUG` |
| `chebi` | `CHEMICAL` |
| `go`, `so`, `pr` | `GENE` |
| `uberon`, `fma`, `ma` | `ANATOMICAL_ENTITY` |
| `hp`, `mp`, `zp` | `PHENOTYPE` |
| `ncbitaxon` | `ORGANISM` |
| anything else | `UNKNOWN` |

## Concept details

`get_concept_details(concept_id)` only resolves IRIs: any string containing `http` is looked up with `/terms?iri=...` and the first match is returned. Anything else, including CURIEs such as `HP:0001250`, returns `None`. Convert OBO CURIEs to their PURL first (`http://purl.obolibrary.org/obo/HP_0001250`).

The detailed concept has `concept_type` `UNKNOWN`, all synonyms and definitions, `categories` entries `Xref: <CURIE>` from `database_cross_reference` annotations and `obo_xref`, and `confidence_score` `0.85`. Parents and children are not fetched.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors left after retries are logged; `search_concepts` then returns `[]` and `get_concept_details` returns `None`.

## See also

- [EBI OLS adapter](../ontologies/ebiols_adapter.md): the same implementation registered as a second source
- [Mondo adapter](mondo_adapter.md), [OBO Foundry adapter](../ontologies/obofoundry_adapter.md), [ZOOMA adapter](../ontologies/zooma_adapter.md)
- [All adapters](../README.md)
- [Searching concepts](../../guides/searching-concepts.md)
