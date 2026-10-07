---
description: NCATS Translator Node Normalizer / Name Resolver: equivalent identifiers across MONDO, HP, UMLS, MeSH, NCBIGene.
---

# NCATS Node Normalizer and Name Resolver adapter

Two companion NCATS Translator services in one adapter. The **Name Resolver** turns free text into CURIEs; the **Node Normalizer** maps any CURIE to its clique of equivalent identifiers across vocabularies (MONDO, DOID, UMLS, MeSH, SNOMED CT, ICD, MedDRA, NCBIGene, UniProt, CHEBI, ...), with a preferred id and label, Biolink types and an information-content score. It is the cheap way to raise identifier-linking rates: `normalize_curies()` resolves hundreds of mixed-style ids in a few requests.

| | |
|---|---|
| Source | `KnowledgeSource.NODENORM` |
| Class | `knowledge_lookup.adapters.NodeNormAdapter` |
| Requires | none (keyless) |
| Identifiers | any CURIE, prefix case does not matter: `MONDO:0005404`, `mesh:D015673`, `ncbigene:672` |
| Upstream APIs | Node Normalizer `https://nodenormalization-sri.renci.org`, Name Resolver `https://name-resolution-sri.renci.org` |
| Latency | 0.5-0.9 s (batch POSTs of ~100 ids take ~0.2-0.6 s) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import NodeNormAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with NodeNormAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue syndrome", limit=3):
            print(c.primary_id, c.primary_label, c.confidence_score)

        # link a mixed bag of identifiers in one request
        linked = await adapter.normalize_curies(["mesh:D015673", "hp:0012432", "ncbigene:672", "BAD:1"])
        for original, record in linked.items():
            print(original, "->", record and (record["id"], record["label"], record["type"]))

        print(len(await adapter.get_mappings("MONDO:0005404")), "equivalent identifiers")


asyncio.run(main())
```

Output:

```
MONDO:0005404 myalgic encephalomeyelitis/chronic fatigue syndrome 1.0
UMLS:C3824694 Chronic fatigue syndrome in adolescence 0.25
UMLS:C3824890 Chronic fatigue syndrome in children 0.25
mesh:D015673 -> ('MONDO:0005404', 'myalgic encephalomeyelitis/chronic fatigue syndrome', 'biolink:Disease')
hp:0012432 -> ('HP:0012432', 'Chronic fatigue', 'biolink:PhenotypicFeature')
ncbigene:672 -> ('NCBIGene:672', 'BRCA1', 'biolink:Gene')
BAD:1 -> None
14 equivalent identifiers
```

## Endpoints used (verified live, current versions)

| Service | Call |
|---|---|
| Node Normalizer 2.5.1 | `GET /get_normalized_nodes?curie=...&conflate=true&description=true` (single id) and `POST /get_normalized_nodes` with `{"curies": [...], "conflate": true, "description": false}` (batches) |
| Name Resolver | `GET /lookup?string=...&limit=...`; `POST /bulk-lookup` with `{"strings": [...], "limit": n}` |

The paths are unversioned (`/get_normalized_nodes`, `/lookup`); their OpenAPI documents are at `/openapi.json` on each host. Node Normalizer accepted `mesh:D015673`, `hgnc:1100`, `ncbigene:672`, `NCBIGENE:672` and `Medgen:5130` alike, so prefix case does not break linking. The adapter additionally canonicalises prefixes it knows (`hgnc:` -> `HGNC:`), and passes unknown ones through unchanged.

## Methods

- `search_concepts(query, limit)` calls the Name Resolver `/lookup`. Each hit is one equivalence clique: `primary_id` is its preferred CURIE, `synonyms` the clique's names (capped at 30), `semantic_types` the Biolink types, `confidence_score` the Solr score relative to the best hit (raw scores are unbounded, 1731 for a perfect ME/CFS match). Hits are not filtered by type.
- `get_concept_details(curie)` reads the normalized node: `primary_id` is the **preferred** identifier (may differ in prefix from the query), `primary_label` its label, `semantic_types` the Biolink types, `definitions` up to 3 descriptions, `synonyms` the labels of the equivalent identifiers, `identifiers` the equivalents that have a `KnowledgeSource` (MONDO, HPO, OMIM, UMLS, MESH, NCBI, UNIPROT, ...), and `source_data[NODENORM]` the full flattened record including `information_content` (0-100). Non-CURIE input and unknown ids return `None`; there is no name fallback (use `search_concepts`).
- `get_mappings(curie)` returns the other equivalent identifiers as `{fromId, toId, fromSource: "NODENORM", toSource: <prefix>, mappingType: "equivalent", confidence: 1.0, toLabel}`; `toLabel` is omitted when the clique has no label for that id (SNOMEDCT, MedDRA, ICD often have none).
- `normalize_curies(curies, description=False) -> dict` batch helper (POST, 100 ids per request). Returns `{input as given: record or None}` where a record has `id`, `label`, `type` (most specific Biolink type), `types`, `equivalent_identifiers` (`[{"identifier", "label"}]`), `information_content` and optionally `descriptions` and `taxa`. `None` means unknown to Node Normalizer, not a CURIE, or its batch failed (logged).
- `bulk_lookup(names, limit=5) -> dict` resolves many names in one `/bulk-lookup` POST: `{name: [{"curie", "label", "types", "score"}]}`, e.g. `long covid` -> `MONDO:0100233 long COVID-19`.
- `get_relationships` is not provided.

## Quirks

- **Conflation:** with `conflate=true` (the default, `adapter.conflate`) genes and proteins are merged and drugs/chemicals are merged, so `HGNC:1100` normalizes to `NCBIGene:672`. Set `adapter.conflate = False` to keep them apart.
- Unknown CURIEs come back as `null` for that key, not as an HTTP error.
- Preferred labels come from the preferred id and can be unexpected (MONDO's "encephalomeyelitis" spelling; `EFO:0004540` is labelled "obsolete_chronic fatigue syndrome").
- Name Resolver matches are lexical: `diabetes` returns diabetes mellitus, but also unrelated cliques that carry the word.

## Rate limits and licence

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). No documented rate limit or key; the services are run by the Translator project (RENCI) on a best-effort basis, so batch with `normalize_curies` instead of looping over single ids. The data aggregates many vocabularies with their own terms (UMLS/SNOMED CT/MedDRA identifiers are only identifiers here, no licensed content); see <https://github.com/TranslatorSRI/NodeNormalization> and <https://github.com/TranslatorSRI/NameResolution>.

## See also

- [OXO adapter](../other/oxo_adapter.md) and [UniChem adapter](../chemicals/unichem_adapter.md) for other cross-reference services
- [All adapters](../README.md)
