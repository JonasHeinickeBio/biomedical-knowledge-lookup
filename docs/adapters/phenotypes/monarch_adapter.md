---
description: Monarch Initiative gene-disease-phenotype associations (HPO, MONDO, OMIM, Orphanet) with frequency and onset qualifiers.
---

# Monarch Initiative adapter

Searches the Monarch knowledge graph (API v3) for genes, diseases and phenotypic features and walks its typed associations: which phenotypes a disease has (with how often), which genes cause it, which diseases a phenotype occurs in, and which orthologs a gene has. Good for differential-diagnosis style questions ("which diseases list chronic fatigue as a phenotype?") because every edge carries its primary source (OMIM, Orphanet, HPO annotations, ClinGen, ClinVar, PANTHER).

| | |
|---|---|
| Source | `KnowledgeSource.MONARCH` |
| Class | `knowledge_lookup.adapters.MonarchAdapter` |
| Requires | none (keyless) |
| Identifiers | `HGNC:1100`, `MONDO:0005148`, `HP:0012432`; also `OMIM:`, `Orphanet:`/`ORPHA:`, `UMLS:` and non-human `NCBIGene:` ids (see below) |
| Upstream API | `https://api-v3.monarchinitiative.org/v3/api` |
| Latency | 0.6-1.5 s per call |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MonarchAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MonarchAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue", limit=3):
            print(c.primary_id, c.concept_type, c.primary_label)

        for edge in await adapter.get_relationships("MONDO:0007947", limit=3):  # Marfan syndrome
            print(edge["relation_label"], edge["related_id"], edge["related_name"],
                  edge.get("frequency"), edge.get("frequency_label"))


asyncio.run(main())
```

Output (abridged):

```
HP:0012432 PHENOTYPE Chronic fatigue
MONDO:0005404 DISEASE myalgic encephalomeyelitis/chronic fatigue syndrome
MONDO:0015274 DISEASE chronic beryllium disease
has_phenotype HP:0000768 Pectus carinatum 0.9 Very frequent
caused_by HGNC:3603 FBN1 None None
caused_by CLINVAR:12524 NC_000009.12:g.99138006C>T None None
```

## Searching

`search_concepts(query, limit)` issues two `/search` requests and merges the hits by Monarch's search score:

1. diseases and phenotypic features (`category=biolink:Disease&category=biolink:PhenotypicFeature`)
2. genes, restricted to *Homo sapiens* (`in_taxon_label`), because Monarch also indexes every model-organism and livestock gene (a `BRCA1` search matches 107 genes, only 17 human). Set `adapter.human_genes_only = False` to include them.

`confidence_score` is the hit's score relative to the best hit. `concept_type` is `GENE`, `DISEASE` or `PHENOTYPE`.

## Concept details

`get_concept_details(concept_id)` reads `/entity/{id}`:

| Field | Value |
|---|---|
| `primary_label` | node name |
| `synonyms` | symbol, full name, exact/broad/narrow/related synonyms |
| `definitions` | description (diseases, phenotypes) |
| `categories` | Biolink category, `taxon:<species>`, subsets (`rare`, `otar`, ...) |
| `parents` / `children` | `node_hierarchy` super/sub classes (diseases, phenotypes) |
| `identifiers` | the Monarch id plus cross-references with a `KnowledgeSource` (OMIM, MESH, UMLS, ENSEMBL, UNIPROT, NCBI, ...) |
| `source_data[MONARCH]` | the entity without closure lists, plus `association_counts` |

### Identifier handling

Monarch's `/entity` only answers for a node's *primary* id in exact case. The adapter therefore:

- fixes prefix case (`hp:0012432` -> `HP:0012432`, `orpha:558` -> `Orphanet:558`)
- resolves `OMIM:`, `Orphanet:`, `UMLS:`, `MESH:`, `DOID:`, `EFO:`, `NCIT:` ids (and any id that 404s) through `/search?q=<curie>`, which indexes cross-references, and accepts only a hit whose `xref` really contains the id. `OMIM:113705` -> `HGNC:1100`, `OMIM:154700` -> `MONDO:0007947`.
- cannot resolve **human `NCBIGene:` ids** (`NCBIGene:672` is not a Monarch node or xref; human genes are keyed by HGNC). Use the `HGNC:` id. Non-human NCBIGene ids work (`NCBIGene:403437`).

## Relationships

`get_relationships(concept_id, limit=10)` picks associations by the node's category and returns up to `limit` rows **per association category**:

| Node | Associations | `relation_label` |
|---|---|---|
| gene | `GeneToPhenotypicFeature`, `CausalGeneToDisease`, `CorrelatedGeneToDisease`, `GeneToGeneHomology` | `has_phenotype`, `causes`, `gene_associated_with_condition`, `orthologous_to` |
| disease | `DiseaseToPhenotypicFeature`, causal and correlated genes, `VariantToDisease` (capped at 5) | `has_phenotype`, `caused_by`, `condition_associated_with_gene` |
| phenotype | diseases and genes | `phenotype_of` |

The label is the local name of Monarch's predicate; for edges seen from the object side it is inverted (`causes` -> `caused_by`, `has_phenotype` -> `phenotype_of`). A negated association gets a `not_` prefix. Duplicates (one gene-disease pair asserted by OMIM and ClinGen) are merged.

Every edge has `relation_label`, `related_id`, `related_name`, `source` (`"MONARCH"`), `direction` (`outgoing`/`incoming`) and `association_category`. When Monarch has them it adds:

| Key | Meaning |
|---|---|
| `frequency` | numeric fraction. Observed `n/m` (`has_quotient`) wins, then `has_percentage`, then the HP frequency term (midpoint of its range: Obligate 1.0, Very frequent 0.9, Frequent 0.55, Occasional 0.17, Very rare 0.025, Excluded 0.0) |
| `frequency_label`, `frequency_term`, `frequency_raw`, `frequency_count`, `frequency_total` | how the frequency was stated |
| `onset`, `onset_id`, `sex` | onset / sex qualifiers (labels) |
| `evidence`, `publications`, `primary_source` | ECO ids, PMIDs, `infores:omim` / `infores:orphanet` / `infores:hpo-annotations` ... |
| `related_category`, `species` | Biolink category of the other node; species for orthologs |

Qualifier field names were verified live: `frequency_qualifier(_label)`, `has_percentage`, `has_count`, `has_total`, `has_quotient`, `onset_qualifier(_label)`, `sex_qualifier(_label)`, `negated`, `has_evidence`, `publications`. In the checked samples Orphanet rows carry HP frequency terms, OMIM/HPO rows carry counts and percentages; onset qualifiers were not present in the diseases sampled (Marfan, Huntington) so that path is covered by unit tests only.

## Mappings

`get_mappings(concept_id)` returns the node's `xref` plus `mappings`/`external_links`, de-duplicated, as `{fromId, toId, fromSource: "MONARCH", toSource: <prefix>, mappingType: "xref", confidence: 0.9}`. For MONDO:0005404 that is DOID, EFO, ICD9, MEDGEN, MESH, NCIT, NORD, Orphanet, SCTID and UMLS.

## Rate limits, licence and caveats

- Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); no documented rate limit, the adapter makes at most one request per association category (<= 4) per `get_relationships` call.
- Monarch data is CC BY 4.0 in aggregate, but each primary source (OMIM, Orphanet, ClinVar, ...) keeps its own terms: <https://monarchinitiative.org/about/licensing>.
- Association responses are verbose (closure lists); only the fields above are kept.
- The disease-to-phenotype list is not sorted by frequency by Monarch; raise `limit` if you need all of a disease's phenotypes (Marfan has 181).
- Monarch's MONDO label for ME/CFS is spelled "myalgic encephalomeyelitis/chronic fatigue syndrome" (sic).

## See also

- [HPO annotations adapter](hpoa_adapter.md) (the same disease-phenotype frequencies from the source file), [HPO adapter](hpo_adapter.md)
- [All adapters](../README.md)
