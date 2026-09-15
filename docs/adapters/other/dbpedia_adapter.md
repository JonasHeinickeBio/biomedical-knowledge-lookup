---
description: DBpedia resources via the public SPARQL endpoint - general knowledge from Wikipedia.
---

# DBpedia adapter

Searches DBpedia, the structured data extracted from Wikipedia, by English label and fetches resource labels, abstracts and types. It also lets you run your own SPARQL queries. Coverage is general-purpose rather than curated biomedical data.

| | |
|---|---|
| Source | `KnowledgeSource.DBPEDIA` |
| Class | `knowledge_lookup.adapters.DBpediaAdapter` |
| Requires | none |
| Identifiers | resource name `Metformin` or `http://dbpedia.org/resource/Metformin` |
| Upstream API | `https://dbpedia.org/sparql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DBpediaAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with DBpediaAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("Metformin", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        entity = await adapter.get_concept_details("Metformin")
        print(entity.primary_id, entity.primary_label, entity.categories[:3])

        raw = await adapter.run_sparql_query(
            "SELECT ?drug WHERE { ?drug a <http://dbpedia.org/ontology/Drug> }", limit=2
        )
        print([b["drug"]["value"] for b in raw["results"]["bindings"]])


asyncio.run(main())
```

Output:

```
Metformin Metformin ['owl#Thing', 'DUL.owl#ChemicalObject', 'Q8386', 'ChemicalSubstance', 'Drug', 'DrugProduct']
metformin Sitagliptin/metformin ['owl#Thing', 'DUL.owl#ChemicalObject', 'Q8386', 'ChemicalSubstance', 'CombinationDrug', 'Drug']
metformin Empagliflozin/metformin ['owl#Thing', 'DUL.owl#ChemicalObject', 'Q8386', 'ChemicalSubstance', 'CombinationDrug', 'Drug']
Metformin Metformin ['owl#Thing', 'DUL.owl#ChemicalObject', 'Q8386']
['http://dbpedia.org/resource/Lipiodol', 'http://dbpedia.org/resource/RAD140']
```

## Searching

`search_concepts(query, limit)` runs a SPARQL query that matches English `rdfs:label` values with Virtuoso's `bif:contains`. A subquery sorts exact label matches first and takes the first `min(limit, 50)` resources; the outer query joins their optional `dbo:abstract` and `rdf:type`.

The type join returns one row per (resource, type) pair. The adapter merges those rows, so each resource is returned once, with all of its types in `categories`.

| Field | Value |
|---|---|
| `primary_id` | last path segment of the resource IRI, so `Sitagliptin/metformin` becomes `metformin` |
| `identifiers` | one `DBPEDIA` identifier; the URL is the resource IRI |
| `definitions` | English abstract, cut to 500 characters, when DBpedia has one |
| `categories` | last segment of each `rdf:type` IRI, each once |
| `concept_type` | `UNKNOWN` |
| `confidence_score` | `0.6` |

User input never reaches the query unescaped. `bif:contains` receives only the words of the query (letters, digits and underscores; quotes and other punctuation are dropped), and the exact-match comparison uses an escaped string literal. A query without any word characters returns `[]` without a request.

## Concept details

`get_concept_details(name_or_iri)` prefixes bare names with `http://dbpedia.org/resource/` (spaces become underscores) and percent-encodes characters that are not allowed in an IRI. It selects `rdfs:label`, `dbo:abstract`, `rdf:type` and `dbo:icd10`, restricted to English or language-less values (up to 100). The result has:

| Field | Value |
|---|---|
| `primary_label` | English `rdfs:label`; falls back to the resource name with underscores replaced by spaces |
| `definitions` | English `dbo:abstract`, cut to 1000 characters |
| `categories` | type names (each once) and `ICD-10: <code>` entries |
| `confidence_score` | `0.65` |

A resource without any values returns `None`. When we checked, the public endpoint returned no `dbo:abstract` values for the resources we tried (for example `Metformin`, `Aspirin`, `Type_2_diabetes`), so `definitions` is often empty.

## Source-specific methods

`run_sparql_query(sparql_query: str, limit: int | None = None)` sends any SPARQL query to the endpoint and returns the JSON result (`head`, `results.bindings`). It appends `LIMIT` if `limit` is given and the query has none. The query is sent as written, so escape any user input yourself.

## Rate limits and errors

`_make_request` is overridden: requests go through the shared retry (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)), but any error is logged and turned into `{}`. Search then returns `[]`, details return `None`, and `run_sparql_query` returns `{}`. Request URLs, parameters and headers are logged at `DEBUG` level.

## See also

- [Wikidata adapter](wikidata_adapter.md)
- [All adapters](../README.md)
