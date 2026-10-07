---
description: DGIdb aggregated drug-gene interactions (v5 GraphQL API, no key).
---

# DGIdb adapter

Queries the Drug-Gene Interaction database (DGIdb v5), which aggregates drug-gene interactions from 45 sources (PharmGKB, CIViC, OncoKB, ChEMBL, Guide to Pharmacology, DTC, TTD, DrugBank and others). A gene links to the drugs that act on it and a drug to its gene targets, with an interaction score, interaction types and the supporting sources and PMIDs.

**Licensing:** every source keeps its own licence (see `sources { sourceDbName license licenseLink }` in the API). As of 2026-10, OncoKB, COSMIC, DrugBank, CancerCommons and MyCancerGenome are marked restrictive / non-commercial and one source is "Unknown". Each relationship lists its `sources`, so you can filter before commercial use or redistribution. Cite DGIdb when you use it.

| | |
|---|---|
| Source | `KnowledgeSource.DGIDB` |
| Class | `knowledge_lookup.adapters.DGIdbAdapter` |
| Requires | none |
| Identifiers | genes `hgnc:1100`; drugs `rxcui:1191`, `chembl:CHEMBL1703` (DGIdb's own primary concept ids); bare symbols or exact drug names also work |
| Upstream API | `POST https://dgidb.org/api/graphql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DGIdbAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with DGIdbAdapter(LookupConfig()) as adapter:
        (drug,) = await adapter.search_concepts("modafinil")
        print(drug.primary_id, drug.primary_label, drug.concept_type)

        for edge in await adapter.get_relationships(drug.primary_id, limit=3):
            print(edge["relation_label"], edge["related_name"], edge["score"], edge["sources"])

        print([m["toId"] for m in await adapter.get_mappings("rxcui:1191")][:4])


asyncio.run(main())
```

Output (live, 2026-10):

```
rxcui:30125 MODAFINIL CHEMICAL
inhibitor SLC6A3 0.2512594437972281 ['TdgClinicalTrial', 'TTD', 'ChEMBL']
interacts_with ADRA1D 0.1236728726478568 ['TTD']
interacts_with ABCB1 0.06331577690584059 ['PharmGKB']
['RXCUI:1191', 'CHEMBL:CHEMBL25', 'NCIT:C287', 'PUBCHEM.SUBSTANCE:178100961']
```

## How the API behaves (verified live)

All requests are `POST /api/graphql` with `{"query": ..., "variables": {...}}`; values are passed as variables, never interpolated. The schema can be browsed by introspection (`__schema`, `__type`). Observed behaviour:

- `genes(names: [...])` matches gene symbols exactly (case-insensitive); `drugs(names: [...])` matches by substring, so `aspirin` also returns `ASPIRIN-TRIGGERED RESOLVIN D1`. Results are ranked exact-name first.
- `genes(conceptIds: [...])` and `drugs(conceptIds: [...])` only resolve a record's *primary* concept id. A drug's other identifiers (aspirin's `chembl:CHEMBL25`) are aliases and return nothing; query by name or the primary id (`rxcui:1191`) instead.
- The top-level `interactions(geneConceptIds: ...)` filter returned no rows in testing, so interactions are read nested under the gene or drug node (a gene such as BRCA1 has 92, aspirin 88) and capped client-side. Interactions arrive in no meaningful order and are ranked by `interactionScore`.
- GraphQL errors are returned with HTTP 200 and an `errors` array; the adapter treats them as failures.
- Latency 0.3-1.0 s per request; no rate limit was hit at about 1 request/s.

## Searching

`search_concepts(query, limit)` asks for genes first (exact symbol) and only falls back to drugs when no gene matches, so `BRCA1` returns the gene and `aspirin` or `modafinil` the drugs. A query with a prefix (`hgnc:1100`, `rxcui:1191`) resolves directly.

| Concept | `concept_type` | `primary_id` | Notes |
|---|---|---|---|
| gene | `GENE` | `hgnc:1100` | `synonyms` from aliases, `definitions` the long name, `categories` DGIdb gene categories (`DRUGGABLE GENOME`, `CLINICALLY ACTIONABLE`, ...) |
| drug | `CHEMICAL` | `rxcui:1191`, `chembl:...`, `ncit:...` | `categories` includes `approved` and drug classes, `definitions` the indication, ChEMBL and DrugBank ids as identifiers |

Drug names are upper case as DGIdb stores them. `get_concept_details` adds the number of known interactions.

## Relationships

`get_relationships(concept_id, limit=25)` returns gene <-> drug interactions, strongest `interactionScore` first. `relation_label` is the DGIdb interaction type lower-cased (`inhibitor`, `agonist`, `antagonist`, `binder`, `partial_agonist`, ...) and `interacts_with` when the sources record no type (the majority). One edge per (partner, type). Extra keys: `score`, `evidence_score`, `directionality` (`INHIBITORY`, `ACTIVATING`, ...), `interaction_types`, `sources` (source database names), `pmids` (at most 25), `approved` (drug partners), `related_type`.

## Mappings

`get_mappings` returns the primary concept id and the aliases that are real cross-references: `HGNC`, `ENSEMBL`, `NCBI` (`NCBIGENE:`), `UNIPROT`, `OMIM`, `ORPHANET`, `PHARMGKB` and `COSMIC` for genes; `RXNORM`, `CHEMBL`, `DRUGBANK`, `PUBCHEM`, `NCIT`, `GUIDETOPHARMACOLOGY`, `TTD` and `PHARMGKB` for drugs. PubMed, CCDS, RefSeq and similar technical aliases are dropped.

## Caveats

- Interaction scores combine evidence counts and drug/gene specificity; DGIdb discourages treating them as probabilities.
- Many low-evidence DTC/ChEMBL rows have the same score; the clinically important edges (for example OLAPARIB-BRCA1, evidence score 19) are not necessarily first.
- Uses the shared HTTP retry and circuit breaker. Errors are logged; search and relationships return `[]`, details return `None`.

## See also

- [ChEMBL adapter](../core/chembl_adapter.md), [DrugBank adapter](drugbank_adapter.md), [Open Targets adapter](../core/opentargets_adapter.md)
- [All adapters](../README.md)
