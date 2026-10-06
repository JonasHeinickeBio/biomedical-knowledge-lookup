---
description: Cell Ontology (CL) cell types with synonyms, definitions, typed relations and cross-references, via EBI OLS4.
---

# Cell Ontology adapter

Looks up cell types in the Cell Ontology (CL) through the EBI OLS4 API, scoped to `ontology=cl`. CL is the identifier space used by CellMarker, CellxGene and most single-cell atlases, so this adapter is the natural bridge from a cell-type name (`T cell`, `natural killer cell`, `B cell`, `monocyte`) to a stable ID, its parents and children, and cross-references (MESH, FMA, BTO, ZFA, UBERON, ...). It is deliberately CL-specific and separate from the generic [OLS adapter](ebiols_adapter.md).

| | |
|---|---|
| Source | `KnowledgeSource.CELLONTOLOGY` |
| Class | `knowledge_lookup.adapters.CellOntologyAdapter` |
| Requires | none |
| Identifiers | `CL:0000084`, `CL_0000084`, bare `0000084` or the full IRI `http://purl.obolibrary.org/obo/CL_0000084` |
| Upstream API | `https://www.ebi.ac.uk/ols4/api` |
| Licence | CL is CC BY 4.0 |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import CellOntologyAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with CellOntologyAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("natural killer cell", limit=3):
            print(c.primary_id, c.primary_label)

        nk = await adapter.get_concept_details("CL:0000623")
        print(nk.primary_label, nk.synonyms, nk.parents)

        for rel in await adapter.get_relationships("CL:0000084", limit=4):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])

        print([m["toId"] for m in await adapter.get_mappings("CL:0000084")])


asyncio.run(main())
```

Output (live, 2026-10-06):

```
CL:0000623 natural killer cell
CL:4047101 liver-resident natural killer cell
CL:0000939 CD16-positive, CD56-dim natural killer cell, human
natural killer cell ['NK cell', 'large granular lymphocyte', 'null cell'] ['group 1 innate lymphoid cell']
is_a CL:0000542 lymphocyte
develops_from CL:0000827 pro-T cell
capable_of GO:0002456 T cell mediated immunity
has_subclass CL:0000789 alpha-beta T cell
['BTO:0000782', 'CALOHA:TS-1001', 'FMA:62870', 'MESH:D013601', 'VHOG:0001479', 'ZFA:0009046']
```

## Searching

`search_concepts(query, limit)` calls `/search?q=...&ontology=cl&type=class&obsoletes=false`. Obsolete terms are excluded and so are imported non-CL classes (UBERON, GO ... can appear under `ontology=cl`); only `CL:` IDs are returned. If `query` is itself a CL identifier (`CL:0000084`, IRI ...) the term is fetched directly. Results carry the label, definition(s), synonyms and `CELL_TYPE` as concept type; `confidence_score` decreases with rank.

## Concept details

`get_concept_details(concept_id)` fetches `/ontologies/cl/terms/{double-URL-encoded IRI}` plus the term's `parents` and `children` pages (at most 25 labels each; failures there degrade to empty lists).

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `CL:0000084` / `T cell` |
| `definitions` | the CL definition, followed by the longer CellGuide extension text when CL carries one |
| `synonyms` | exact, narrow and related synonyms |
| `categories` | `Xref: <DB>:<id>` for every cross-reference; `obsolete` for obsolete terms |
| `parents` / `children` | direct `is_a` neighbours (labels) |
| `identifiers` | the CL IRI as `CELLONTOLOGY` identifier |
| `source_data[CELLONTOLOGY]` | `iri`, `obo_id`, `label`, `in_subset`, `is_obsolete`, `term_replaced_by`, `annotation` |

## Relationships

`get_relationships(concept_id, limit=25)` uses one `/terms/{iri}/graph` request, which returns the term's neighbourhood with typed edges in both directions:

| `relation_label` | Meaning |
|---|---|
| `is_a` | direct parent (outgoing) |
| `develops_from`, `capable_of`, `part_of`, `has_part`, ... | the term's own relations, name from the edge label in snake_case |
| `has_subclass` | direct child (incoming `subClassOf`) |
| `inverse_<relation>` | relations other terms hold towards this one (for example `inverse_occurs_in` for GO processes occurring in the cell) |

Items also carry `direction` (`outgoing`/`incoming`) and `relation_iri`. Order: parents, own relations, children, inverse relations, then cut to `limit`. OLS caps the graph at about 50 nodes for very broad terms (`CL:0000000` "cell").

The per-relation links (`_links.develops_from`, ...) on the term object are not used: they return a mix of several relations' targets.

## Mappings

`get_mappings(concept_id)` converts the term's cross-references (`obo_xref`, falling back to `annotation.database_cross_reference`) into `{fromId, toId, fromSource: "CL", toSource: <DB>, mappingType: "xref", confidence: 0.9}`. Typical databases: MESH, FMA, BTO, CALOHA, VHOG, ZFA, UBERON. Immune cell types (`CL:0000084` T cell, `CL:0000623` NK cell, `CL:0000236` B cell, `CL:0000576` monocyte) were checked live.

## Rate limits and caveats

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); `min_request_timeout` is 30 s because OLS4 answers between 0.3 and 6 s. Errors and unknown IDs are logged; search returns `[]`, details `None`.

- Use the ontology-scoped term URL: `/terms?iri=` returns the same IRI once per ontology that imports it.
- Cell Ontology terms for mouse- or human-specific subtypes carry the species in the label (`... natural killer cell, human`).
- CL labels use CL wording (`natural killer cell`, not `NK cell`); the short names are synonyms and are matched by the search.

## See also

- [CellMarker adapter](cellmarker_adapter.md) (marker genes per CL cell type), [OLS adapter](ebiols_adapter.md)
- [All adapters](../README.md)
