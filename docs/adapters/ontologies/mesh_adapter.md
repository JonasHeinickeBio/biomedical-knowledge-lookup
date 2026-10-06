---
description: NLM Medical Subject Headings descriptors, supplementary concepts and qualifiers with entry terms, scope notes, tree numbers and hierarchy, e.g. D015673.
---

# MeSH adapter

Looks up NLM Medical Subject Headings (MeSH) through the keyless `id.nlm.nih.gov/mesh` service. MeSH is the vocabulary behind PubMed indexing, so it is the natural join key for literature-mined records. Concepts carry the heading's entry terms as synonyms, the scope note as definition, and tree numbers in `source_data`.

| | |
|---|---|
| Source | `KnowledgeSource.MESH` |
| Class | `knowledge_lookup.adapters.MeSHAdapter` |
| Requires | none |
| Identifiers | `D015673` (descriptor), `C000657245` (supplementary concept), `Q000175` (qualifier); also `MESH:D015673`, `MeSH:D015673` and the full `http://id.nlm.nih.gov/mesh/D015673` URI |
| Upstream API | REST look-up `https://id.nlm.nih.gov/mesh/lookup/{descriptor,term}` and SPARQL `https://id.nlm.nih.gov/mesh/sparql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MeSHAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MeSHAdapter(LookupConfig()) as adapter:
        # Entry terms resolve to their heading: "long covid" -> Post-Acute COVID-19 Syndrome
        for concept in await adapter.search_concepts("long covid", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        mecfs = await adapter.get_concept_details("MESH:D015673")
        print(mecfs.primary_label, mecfs.synonyms[:3])
        print(mecfs.source_data["MESH"]["tree_numbers"])

        for edge in await adapter.get_relationships("D015673"):
            if edge["relation_label"] == "broader_than":
                print(edge["related_id"], edge["related_name"])

        # Fast exact-label helper for annotating MeSH heading strings (one REST call)
        print((await adapter.lookup_descriptor("Fatigue Syndrome, Chronic")).primary_id)


asyncio.run(main())
```

Output (captured live):

```
D000094024 Post-Acute COVID-19 Syndrome DISEASE
Fatigue Syndrome, Chronic ['Systemic Exertion Intolerance Disease', 'Myalgic Encephalomyelitis', 'Encephalomyelitis, Myalgic']
['C23.550.291.500.392', 'C05.651.310', 'C10.668.364', 'C10.586.500.600']
MESH:D002908 Chronic Disease
MESH:D004679 Encephalomyelitis
MESH:D009135 Muscular Diseases
MESH:D009468 Neuromuscular Diseases
D015673
```

(`source_data` is keyed by the `KnowledgeSource` enum, which compares equal to the string `"MESH"`.)

## How it talks to MeSH

| Need | Endpoint | Typical latency |
|---|---|---|
| Exact preferred label | `lookup/descriptor?label=...&match=exact` | 0.7 s |
| Heading label contains text | `lookup/descriptor?...&match=contains&limit=N` | 0.7 s |
| Entry term contains text | `lookup/term?...&match=contains&limit=N` | 0.7 s |
| Everything about a record | one SPARQL `SELECT` (label, type, scope note, tree numbers, entry terms, active flag) | 0.9 s |
| Relationships | one SPARQL `SELECT` (broader, narrower, qualifiers, see-also, mapped headings) | 0.8 s |

The adapter uses SPARQL for details because the per-record JSON (`https://id.nlm.nih.gov/mesh/D015673.json`) only holds URIs, so labels of related headings and the scope note (stored on the *concept* `M...`, not the descriptor) would need many more requests.

## Searching

`search_concepts(query, limit)` runs three REST look-ups in parallel (exact heading label, heading label contains, entry term contains), ranks the candidates locally and enriches the survivors with **one** batched SPARQL query that also resolves entry-term IDs (`T...`) to their heading:

1. exact heading label match
2. exact entry-term match
3. heading starts with the query
4. heading label contains the query
5. entry term contains the query

The look-up endpoints return alphabetical, not relevance-ordered, results, which is why the adapter over-fetches (`max(3*limit, 20)`) before ranking. A query that is already a MeSH UI (`D015673`, `MESH:D015673`) goes straight to `get_concept_details`.

Notes:

- The heading look-ups match the *preferred* label only: `"chronic fatigue"` finds nothing there (the heading is *Fatigue Syndrome, Chronic*) but finds the heading through its entry term *Chronic Fatigue Syndrome*.
- Supplementary concept records (`C...`, e.g. `BRCA1 protein, human`) are reached through entry terms only; obsolete ones are labelled `[OBSOLETE] ...` by NLM and have `source_data["MESH"]["active"] == False`.
- If one of the three REST calls fails the others still contribute; if all fail the search returns `[]`.

## `lookup_descriptor(label)`

Cheap, exact, case-insensitive heading-label lookup for annotating corpora where records already carry MeSH heading strings. One REST request, returns a minimal concept (id + label, `concept_type` `UNKNOWN`), or `None` when no heading has that exact label. It does not try entry terms (use `search_concepts` for that) and does not fetch scope notes or tree numbers (use `get_concept_details`).

## Concept details

`get_concept_details(concept_id)` accepts the identifier forms above.

| Field | Value |
|---|---|
| `primary_label` | preferred heading label |
| `synonyms` | entry terms (the heading label is not repeated) |
| `definitions` | scope note (descriptors/qualifiers) or the `note` of a supplementary concept |
| `concept_type` | from the first matching tree: `C23.888` (signs and symptoms) `SYMPTOM`, `C` `DISEASE`, `D12.776` `PROTEIN`, `D` `CHEMICAL`, `A` `ANATOMICAL_ENTITY`, `B` `ORGANISM`, `E` `PROCEDURE`, `G` `BIOLOGICAL_PROCESS`; supplementary concepts by record type (`SCR_Disease`, `SCR_Chemical`, ...); otherwise `UNKNOWN` |
| `semantic_types` | MeSH record type, e.g. `TopicalDescriptor`, `SCR_Disease`, `Qualifier` |
| `categories` | tree category letters, e.g. `['C']` or `['C', 'F']` |
| `identifiers` | one `MESH` identifier with a `meshb.nlm.nih.gov` URL |
| `source_data[MESH]` | `ui`, `record_type`, `tree_numbers`, `active` |

## Relationships

`get_relationships(concept_id, limit=50)` returns `{relation_label, related_id, related_name, source}` edges with `related_id` as `MESH:<UI>`; `limit` caps each kind separately.

| `relation_label` | Meaning |
|---|---|
| `broader_than` | the related heading is a broader (parent) heading of the queried one; one level only |
| `narrower_than` | the related heading is a narrower (child) heading |
| `allowed_qualifier` | permitted subheading (`Q...`), descriptors only (35 for *Fatigue Syndrome, Chronic*) |
| `see_also` | related heading suggested by MeSH |
| `mapped_to` | supplementary concept -> the headings it is indexed under |

The label names the *related* heading (`broader_than` = "the related heading is broader than this one").

## Mappings

`get_mappings(concept_id)` only reports what MeSH itself states: supplementary concept -> heading (`preferred_mapped_to`, confidence 1.0; `mapped_to`, 0.8), e.g. `C000657245` ([OBSOLETE] COVID-19) -> `D018352` Coronavirus Infections, `D011024`, `D058873`. **MeSH RDF contains no UMLS CUIs or ICD/SNOMED codes**; use the [UMLS](../core/umls_adapter.md) adapter for MeSH <-> CUI links.

## Rate limits, licence and errors

No key. NLM asks API users to be considerate; the adapter issues 1 to 4 requests per call and relies on the shared retry/circuit-breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). MeSH is a US government work, free to use; NLM requests attribution. Free-text SPARQL scans (`FILTER(CONTAINS(...))` over all terms) took about 17 s in testing, so the adapter never uses them. `bif:contains` is not available on the endpoint. Interface methods never raise: search returns `[]`, details `None`.

## See also

- [UMLS adapter](../core/umls_adapter.md) for CUI mappings, [BioPortal adapter](bioportal_adapter.md) for MeSH via BioPortal
- [All adapters](../README.md)
