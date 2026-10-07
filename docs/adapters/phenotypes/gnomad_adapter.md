---
description: gnomAD population allele frequencies and gene constraint (pLI, LOEUF, missense z) via the public GraphQL API.
---

# gnomAD adapter

Queries the Genome Aggregation Database (gnomAD v4.1, GRCh38, 807,162 individuals: 730,947 exomes and 76,215 genomes) through the public GraphQL endpoint behind the gnomAD browser. It answers two questions that matter for variant triage and registry work: how common is a variant in the general population, and how tolerant is a gene of loss-of-function or missense variation.

| | |
|---|---|
| Source | `KnowledgeSource.GNOMAD` |
| Class | `knowledge_lookup.adapters.GnomADAdapter` |
| Requires | none (no key) |
| Identifiers | gene: `ENSG00000012048` (a symbol such as `BRCA1` is accepted as input); variant: `1-11796321-G-A` (GRCh38 `chrom-pos-ref-alt`), or an rsID such as `rs1801133` |
| Upstream API | `POST https://gnomad.broadinstitute.org/api` (GraphQL) |
| Default dataset | `gnomad_r4`, reference genome GRCh38 |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import GnomADAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


async def main():
    async with GnomADAdapter(LookupConfig()) as adapter:
        gene = (await adapter.search_concepts("BRCA1", limit=1))[0]
        print(gene.primary_id, gene.source_data[KnowledgeSource.GNOMAD]["constraint"]["loeuf"])

        variant = await adapter.get_concept_details("rs1801133")
        joint = variant.source_data[KnowledgeSource.GNOMAD]["joint"]
        print(variant.primary_id, joint["ac"], joint["an"], round(joint["af"], 3))

        for edge in await adapter.get_relationships("1-11796321-G-A", limit=3):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

Output (live, October 2026):

```
ENSG00000012048 0.927589724465447
1-11796321-G-A 513548 1613846 0.318
in_gene ENSG00000177000 MTHFR
has_consequence missense_variant missense variant
has_consequence 5_prime_UTR_variant 5 prime UTR variant
```

## Searching

`search_concepts(query, limit)` dispatches on the shape of the query:

| Query | Action |
|---|---|
| gene symbol or Ensembl id (`BRCA1`, `MTHF`, `ENSG...`) | `gene_search` (prefix match), then ONE aliased request that fetches name and constraint for every hit (at most 10) |
| `1-11796321-G-A`, `chr1:11796321:G:A` | variant lookup (separators and `chr` are normalised) |
| `rs1801133` | variant lookup by rsID |
| all digits (`220816`) | ClinVar variation id via `variant_search`, at most 3 variants expanded |
| anything else (phrases, symptoms, diseases) | `[]`: gnomAD indexes genes, variants, regions and transcripts, not phenotypes |

Malformed searches are never sent: the API answers an unparsable `variant_search` with HTTP 500.

## Concept details

`get_concept_details(concept_id)` accepts the same gene and variant forms.

**Genes** (`ConceptType.GENE`, `primary_id` the Ensembl id, label the symbol, `definitions`/`synonyms` hold the gene name). Identifiers: `HGNC`, `NCBI` (Entrez), `OMIM`. `source_data["GNOMAD"]`:

| Field | Content |
|---|---|
| `chrom`, `start`, `stop`, `strand`, `canonical_transcript_id`, `reference_genome` | location (GRCh38) |
| `constraint` | gnomAD v4 constraint: `pLI`, `oe_lof`, `oe_lof_lower`, `oe_lof_upper` (= `loeuf`), `lof_z`, `mis_z`, `syn_z`, `oe_mis`, `oe_syn`, observed/expected counts for LoF, missense, synonymous, `flags` |

BRCA1 as an example: pLI 5.5e-38, LOEUF 0.93, LoF z 2.17, missense z 1.73 (LOEUF near 1 means no strong gene-wide LoF depletion; constraint is a gene-level prior, not a verdict on single variants).

**Variants** (`ConceptType.MOLECULAR_ENTITY`, `primary_id` the variant id, label the rsID when there is one). Identifiers: `DBSNP` per rsID, `CLINVAR` (variation id, with the significance as label). `source_data["GNOMAD"]`:

| Field | Content |
|---|---|
| `chrom`, `pos`, `ref`, `alt`, `caid`, `rsids`, `flags` | basic record (`caid` = ClinGen allele registry id) |
| `exome`, `genome`, `joint` | `ac`, `an`, `af`, `homozygotes`, `hemizygotes`, `filters`, `faf95_popmax`, `faf95_popmax_population` (the `joint` block combines exomes and genomes; v4.1 only) |
| `ancestry_groups` | per ancestry group (`afr`, `amr`, `asj`, `eas`, `fin`, `mid`, `nfe`, `sas`, `ami`, `remaining`) of the joint data: `ac`, `an`, `af`, `homozygotes`. Sex-stratified rows (`nfe_XX`, `XY`) are dropped |
| `transcript_consequences` | up to 8, MANE Select and canonical first: gene, transcript, consequence, `hgvsc`, `hgvsp`, `lof` and flags, PolyPhen/SIFT |
| `clinvar` | `variation_id`, `clinical_significance`, `review_status`, `gold_stars` (only when ClinVar has the variant) |

For an rsID lookup the ClinVar record needs a second request because ClinVar is keyed by variant id.

## Relationships and mappings

| Call | Edges |
|---|---|
| `get_relationships(gene, limit=10)` | `has_variant`: the most frequent protein-altering variants of the gene (missense, frameshift, stop gained, splice donor/acceptor, start/stop lost, inframe indels, or `lof == HC`), ranked by exome+genome allele frequency. Extra keys: `allele_frequency`, `allele_count`, `allele_number`, `consequence`, `hgvsp`, `lof`, `dataset` |
| `get_relationships(variant, limit=10)` | `in_gene` (Ensembl gene id, symbol, consequence, HGVS) and `has_consequence` (Sequence Ontology term), de-duplicated |
| `get_mappings(gene)` | `HGNC`, `NCBI`, `OMIM`, `Ensembl` |
| `get_mappings(variant)` | `dbSNP` (every rsID), `ClinVar` (variation id, with `clinicalSignificance`), `ClinGen` (CAid) |

**Cost warning for gene -> variants.** The API cannot limit a gene's variant list server side. BRCA1 (126 kb) returns 1.7 MB in about 15 s on a cold call (1.5 s when cached); TTN would return tens of MB. The adapter first reads the gene span and refuses genes longer than `MAX_GENE_SPAN_BP = 250,000` (TTN, DMD, ...): `get_relationships` returns `[]` for them and logs a warning. Use the gnomAD website or a region query for those genes.

## Datasets

`GnomADAdapter.dataset` defaults to `gnomad_r4`. Other ids accepted by the API: `gnomad_r4_non_ukb`, `gnomad_r3` (+ `_controls_and_biobanks`, `_non_cancer`, `_non_neuro`, `_non_topmed`, `_non_v2`), `gnomad_r2_1` (+ `_controls`, `_non_neuro`, `_non_cancer`, `_non_topmed`; GRCh37, which this adapter does not query), `exac`. The adapter's queries are GRCh38, so only the r4 and r3 families make sense; `joint` data exist for r4 only.

## Rate limits, licence, errors

gnomAD does not publish a quota for the GraphQL endpoint. Its repository enforces per-IP request and query-cost quotas, and the gnomAD team has quoted about 10 queries per minute; exceeding them yields HTTP 429, which the shared retry layer backs off from. A search costs 1-2 requests, details 1-2, and a gene's variants 2. Keep bulk work to the downloadable VCF/Hail tables instead.

gnomAD states that its data are released under CC0 1.0; check its terms of use before redistributing and cite Karczewski et al. 2020 and Chen et al. 2024.

Errors never raise: unknown genes/variants (HTTP 200 with `errors` and `data: null`), schema errors (HTTP 400) and network failures are logged and give `[]` or `None`. Live latency (October 2026): gene details 0.2-0.4 s, variant details 0.3-1.0 s with ancestry groups, gene search 0.4 s.

## See also

- [HGNC adapter](../proteins/hgnc_adapter.md), [ClinVar adapter](clinvar_adapter.md), [dbSNP adapter](dbsnp_adapter.md)
