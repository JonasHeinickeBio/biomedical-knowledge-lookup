---
description: DBpedia resources via the public SPARQL endpoint - general knowledge from Wikipedia.
---

# DBpedia adapter

Searches DBpedia, the structured data extracted from Wikipedia, by English label and fetches resource labels, abstracts, types and external identifiers (Wikidata, MeSH, OMIM, ...). It also lets you run your own SPARQL queries. Coverage is general-purpose rather than curated biomedical data.

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

`get_concept_details(name_or_iri)` prefixes bare names with `http://dbpedia.org/resource/` (spaces become underscores) and percent-encodes characters that are not allowed in an IRI. It selects `rdfs:label`, `dbo:abstract`, `rdf:type`, the identifier properties below and the `owl:sameAs` links to Wikidata and Freebase, restricted to English or language-less values (up to 200 rows; at most 12 `owl:sameAs` rows). The result has:

| Field | Value |
|---|---|
| `primary_label` | English `rdfs:label`; falls back to the resource name with underscores replaced by spaces |
| `definitions` | English `dbo:abstract`, cut to 1000 characters |
| `identifiers` | `DBPEDIA`, plus the external identifiers below |
| `categories` | type names (each once) and `<label>: <value>` entries for identifiers without a `KnowledgeSource` |
| `confidence_score` | `0.65` |

External identifiers (values as stored by DBpedia; junk such as `,` is skipped):

| DBpedia property | Exposed as |
|---|---|
| `owl:sameAs` to `wikidata.org/entity/Q...` | `WIKIDATA` identifier with the entity IRI as URL; the other ~70 interlanguage `sameAs` links are not fetched |
| `dbo:meshId`, `dbo:omim`, `dbo:medlinePlus` | `MESH` (also the `MeSH: <id>` category), `OMIM`, `MEDLINEPLUS` |
| `dbo:nciId`, `dbo:orpha` | `NCIEVS` (C-numbers only), `ORPHANET` (`ORPHA:` prefix added to the bare number) |
| `dbo:kegg`, `dbo:pubchem`, `dbo:chEBI`, `dbo:chEMBL` | `KEGG`, `PUBCHEM`, `CHEBI` (`CHEBI:` prefix added), `CHEMBL` (`CHEMBL` prefix added) |
| `dbo:icd10`, `dbo:icd9`, `dbo:diseasesDB`, `dbo:eMedicineSubject`, `dbo:eMedicineTopic` | categories `ICD-10: ...`, `ICD-9: ...`, `DiseasesDB: ...`, `eMedicine subject: ...`, `eMedicine topic: ...` |
| `dbo:casNumber`, `dbo:atcCode` | categories `CAS: ...`, `ATC: ...` |
| `owl:sameAs` to `rdf.freebase.com/ns/m.xxx` | category `Freebase: /m/xxx` |

For `Crohn's_disease` this yields `WIKIDATA Q1472`, `MESH D003424`, `OMIM 266600`, `MEDLINEPLUS 000249` and the categories `ICD-10: K50`, `ICD-9: 555`, `DiseasesDB: 3178`, `Freebase: /m/0h1n9`. DBpedia coverage varies by article, so many resources have only some of these.

Three behaviours were added after running the adapter against a dozen resources:

- **Redirects are followed.** Wikipedia redirect pages (for example `Severe_acute_respiratory_syndrome_coronavirus_2`) have no data of their own; the adapter follows `dbo:wikiPageRedirects` for up to two hops and returns the target (`SARS-CoV-2`).
- **Ambiguous `sameAs` clusters are ignored.** A few resources (`P53`, `Interleukin_6`) are linked by DBpedia to about 15,000 unrelated Wikidata items. More than five Wikidata links on one resource are discarded as unreliable; the resource's other identifiers are unaffected. Resources that merge two articles (such as `Fatigue` with `Q9690` and `Q15729017`) keep both.
- **Junk values are dropped.** An ATC value must look like an ATC code (`N02BA01`), so DBpedia's `Combinations:` and `,` are skipped. Trailing dots are stripped (`E11.` becomes `ICD-10: E11`).

A resource without any values returns `None`. When we checked, the public endpoint returned no `dbo:abstract` values for the resources we tried (for example `Metformin`, `Aspirin`, `Type_2_diabetes`), so `definitions` is often empty.

## Mappings, relationships and lookups

| Method | Returns |
|---|---|
| `get_mappings(name_or_iri)` | the identifiers from [Concept details](#concept-details) as `{fromId, toId, fromSource, toSource, mappingType, confidence}` dicts, the shape the Ensembl and KEGG adapters use. The link to Wikidata has `mappingType` `sameAs`, the others `xref`. Redirects are followed and the same validation applies. |
| `get_relationships(name_or_iri, limit=10)` | typed edges `{relation_label, related_id, related_name, source, property}` to other resources. `limit` caps the edges per relation label. |
| `get_synonyms(name_or_iri, limit=50)` | alternative names: the titles of Wikipedia pages that redirect to the resource (`Crohn disease`, `Morbus Crohn`, common misspellings). |
| `find_by_identifier(source, identifier, limit=5)` | reverse lookup: the resources that carry an identifier, with `confidence_score` `0.9`. `source` is a `KnowledgeSource` (`MESH`, `OMIM`, `CHEMBL`, ...), a label (`"ICD-10"`, `"CAS"`) or `WIKIDATA` with a Q-ID, resolved through `owl:sameAs`. |

`get_relationships` follows these object-valued properties; only targets that are DBpedia resources are returned.

| Edge label | DBpedia property |
|---|---|
| `has_category` | `dct:subject` (a Wikipedia category, `Category:...`) |
| `is_a` | `dbo:class` (for example the drug class of Aspirin) |
| `route_of_administration` | `dbo:routesOfAdministration` |
| `has_symptom`, `treated_by`, `has_cause` | `dbo:symptom`, `dbo:treatment` and `dbo:medication`, `dbo:medicalCause` |
| `differential_diagnosis`, `diagnosed_by`, `medical_specialty`, `vaccine` | `dbo:differentialDiagnosis`, `dbo:medicalDiagnosis`, `dbo:medicalSpecialty`, `dbo:vaccination` |

`dbo:class`, `dct:subject` and `dbo:routesOfAdministration` were seen on live resources; the disease properties are the ones the DBpedia ontology declares on `dbo:Disease`, and many articles do not carry them, or carry them as text rather than links, in which case they are skipped.

Live output for `Crohn's_disease` and `Aspirin`:

```
mappings   [('DiseasesDB', '3178'), ('Freebase', '/m/0h1n9'), ('ICD-10', 'K50'), ('ICD-9', '555'), ('MEDLINEPLUS', '000249'), ('MESH', 'D003424'), ('OMIM', '266600'), ('WIKIDATA', 'Q1472'), ('eMedicine subject', 'med'), ('eMedicine topic', '477')]
aspirin    [('has_category', 'Category:German_inventions'), ('is_a', 'Nonsteroidal_anti-inflammatory_drug'), ('has_category', 'Category:Aspirin')]
crohn      [('has_symptom', 'Abdominal_pain'), ('differential_diagnosis', "Behçet's_disease"), ('treated_by', 'Corticosteroid'), ('diagnosed_by', 'Biopsy'), ...]
synonyms   ['Chrons disease', 'Krohn's disease', 'Morbus Crohn', 'Granulomatous Colitis', 'Ileocolitis', ...]
find MESH D003424 / WIKIDATA Q1472  ->  Crohn's_disease
```

Values for `dbo:nciId` and `dbo:orpha` are only accepted when they look like the identifier: live `nciId` values include stray URL fragments.

## Source-specific methods

`run_sparql_query(sparql_query: str, limit: int | None = None)` sends any SPARQL query to the endpoint and returns the JSON result (`head`, `results.bindings`). It appends `LIMIT` if `limit` is given and the query has none. The query is sent as written, so escape any user input yourself.

## Rate limits and errors

`_make_request` is overridden: requests go through the shared retry (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)), but any error is logged and turned into `{}`. Search then returns `[]`, details return `None`, and `run_sparql_query` returns `{}`. Request URLs, parameters and headers are logged at `DEBUG` level.

The policy follows the documented limits of the public Virtuoso endpoint ([DBpedia SPARQL docs](https://www.dbpedia.org/resources/sparql/)):

| Documented rule | What the adapter does |
|---|---|
| queries run for at most 120 s (`MaxQueryExecutionTime`) | `min_request_timeout = 125`, so the server stops the query (with partial results) instead of the client (with nothing) |
| a query that times out returns **partial results with HTTP 200**, no error; `X-SQL-State`/`X-SQL-Message` say so | the response hook logs a warning with those headers |
| result sets are capped at 10,000 rows, flagged by `X-SPARQL-MaxRows` | queries ask for at most 300 rows; the same warning is logged if the cap is hit |
| 50 connections per IP | `max_concurrent_requests = 5` |
| on 503 or 429, pause and retry | shared retry with `Retry-After` honoured; network errors are retried once after 2 s |

A partial result is logged, not raised: the identifiers or relations in it are correct but may be incomplete, and the adapter cannot tell which rows are missing.

## See also

- [Wikidata adapter](wikidata_adapter.md)
- [All adapters](../README.md)
