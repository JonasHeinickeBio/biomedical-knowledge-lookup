---
description: EBI OxO cross-references between ontology and vocabulary identifiers (CURIEs).
---

# OxO adapter

Looks up cross-references for an ontology identifier in EBI OxO. For example, it maps `MONDO:0005148` to DOID, ICD-10-CM, MedGen, MeSH, UMLS and others, following mappings up to a configurable distance. The input is a CURIE, not free text.

| | |
|---|---|
| Source | `KnowledgeSource.OXO` |
| Class | `knowledge_lookup.adapters.OxOAdapter` |
| Requires | none |
| Identifiers | CURIE, e.g. `MONDO:0005148`, `DOID:162` |
| Upstream API | `https://www.ebi.ac.uk/spot/oxo/api` |

## Quick example

```python
import asyncio

from knowledge_lookup import KnowledgeSource
from knowledge_lookup.adapters import OxOAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OxOAdapter(LookupConfig()) as adapter:
        concept = await adapter.get_concept_by_id("MONDO:0005148", distance=1)
        print(concept.primary_id, concept.primary_label)

        raw = concept.source_data[KnowledgeSource.OXO]["mappingResponseList"]
        print(len(raw), [m["curie"] for m in raw[:4]])


asyncio.run(main())
```

Output:

```
MONDO:0005148 type 2 diabetes mellitus
11 ['DOID:9352', 'ICD10CM:E11', 'ICD10WHO:E11', 'MEDGEN:41523']
```

## Searching

`search_concepts(query, limit=10)` (note the default of 10) POSTs `{"ids": [query], "distance": 2}` to `/search`. The query must be a CURIE; free text returns nothing.

| Field | Value |
|---|---|
| `primary_id` | the CURIE |
| `primary_label` | OxO label (falls back to the CURIE) |
| `concept_type` | `UNKNOWN` |
| `identifiers` | the CURIE, once, under `OXO` |
| `sources` | `['OXO']` |
| `mappings` | `ConceptMapping` entries only for targets whose prefix matches a `KnowledgeSource` name (`UMLS`, `OLS`, `BIOPORTAL`, `BIOONTOLOGY`, `WIKIDATA`, `DBPEDIA`, `NCBI`, `UNIPROT`, `ENSEMBL`, `PUBCHEM`, `CHEMBL`) |
| `confidence_score` | `0.8` |
| `source_data[OXO]` | raw OxO result, including `mappingResponseList` |

Most real targets (DOID, ICD10CM, MeSH, MedGen, ...) do not match those names, so they are missing from `mappings`. Read them from `source_data[KnowledgeSource.OXO]["mappingResponseList"]`: each entry has `curie`, `label`, `sourcePrefixes`, `targetPrefix` and `distance`.

## Concept details

`get_concept_details(curie)` is `get_concept_by_id(curie, distance=3)`, so it follows mappings up to three hops.

## Source-specific methods

| Method | Returns |
|---|---|
| `get_concept_by_id(concept_id, **kwargs)` | concept as above; kwargs `distance` (default 1), `mapping_target` and `mapping_source` (lists of prefixes to restrict mappings) |
| `get_mappings_for_concepts(concept_ids, **kwargs)` | `dict[str, list[dict]]` keyed by query ID; each dict has `curie`, `label`, `targetPrefix`, `sourcePrefixes`, `distance`; same kwargs |
| `get_datasources()` | always `[]` and logs a warning: the current OxO service no longer has a datasources endpoint (it answers HTTP 400). Kept for backward compatibility |
| `validate_connection()` | `bool` from `GET /api/search`, which answers with an empty result page |

The base-class `get_mappings()` is not overridden and returns `[]`.

## Rate limits and errors

Requests go through the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); searches are JSON POSTs. Errors are logged; search returns `[]`, details return `None` and `get_mappings_for_concepts` returns `{}`.

## See also

- [Mondo adapter](../core/mondo_adapter.md), [OLS adapter](../core/ols_adapter.md)
- [All adapters](../README.md)
