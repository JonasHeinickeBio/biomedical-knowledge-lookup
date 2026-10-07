---
description: GTEx Portal gene expression across 54 tissues (median TPM, tissue specificity) and single-tissue eQTL variants.
---

# GTEx adapter

Looks up human genes in the [GTEx Portal](https://gtexportal.org) (Genotype-Tissue Expression project) and answers three questions: where is the gene expressed (median TPM in 54 post-mortem tissues), how tissue-specific is it, and which common variants regulate it (single-tissue eQTLs, with p-value and effect size). Useful for ME/CFS and Long COVID questions such as "is this immune gene expressed in blood, spleen or brain" or "which GWAS-style variants change its expression".

| | |
|---|---|
| Source | `KnowledgeSource.GTEX` |
| Class | `knowledge_lookup.adapters.GTExAdapter` |
| Requires | none |
| Identifiers | Ensembl gene id `ENSG00000012048` (with or without version) or HGNC symbol `BRCA1`. Entrez ids, HGNC ids and free text are **not** searchable |
| Upstream API | `https://gtexportal.org/api/v2` (keyless, no published rate limit) |
| Dataset | `gtex_v10` (GENCODE v39, GRCh38) by default; `GTEX_DATASET_ID=gtex_v8` (GENCODE v26) selects the older release |
| Licence | open-access summary data; cite the GTEx Consortium and the release used. The API serves no controlled-access individual-level data |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import GTExAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


async def main():
    async with GTExAdapter(LookupConfig()) as adapter:
        il6 = await adapter.get_concept_details("IL6")
        data = il6.source_data[KnowledgeSource.GTEX]
        print(il6.primary_id, data["tissue_specificity"], data["tau"], data["top_tissues_tpm"][:2])

        for edge in await adapter.get_relationships("BRCA1", limit=3):
            print(edge["relation_label"], edge["related_name"], edge.get("median_tpm"), edge.get("p_value"))

        print([m["toId"] for m in await adapter.get_mappings("BRCA1")])


asyncio.run(main())
```

Real output (GTEx v10, fetched 2026-10-07):

```
ENSG00000136244 intermediate 0.721 [{'tissue': 'Adipose_Visceral_Omentum', 'tpm': 53.584}, {'tissue': 'Lung', 'tpm': 29.114}]
expressed_in Cells_EBV-transformed_lymphocytes 20.935 None
expressed_in Testis 10.558 None
expressed_in Cells_Cultured_fibroblasts 7.595 None
has_eqtl_variant chr17_43323919_A_G_b38 None 5.15778944578998e-22
...
['NCBIGene:672', 'HGNC:1100', 'ENSEMBL:ENSG00000012048.23', 'HGNC.SYMBOL:BRCA1']
```

## Requests used and latency

| Call | Request | Latency (measured) |
|---|---|---|
| gene resolution (every call) | `/reference/geneSearch?geneId=...&gencodeVersion=v39&genomeBuild=GRCh38/hg38` | 0.2 - 0.5 s, ~0.5 KB per gene |
| expression summary | `/expression/medianGeneExpression?gencodeId=<versioned id>&datasetId=gtex_v10&itemsPerPage=100` | 0.3 - 0.7 s, 54 rows, ~10 KB |
| eQTLs | `/association/singleTissueEqtl?gencodeId=...&datasetId=...&itemsPerPage=250&page=N` | 0.5 - 1 s per page, ~90 KB per full page |

So `search_concepts` is 1 request (~0.2 - 0.5 s), `get_concept_details` 2 requests (0.8 - 1.5 s), `get_mappings` 1 request, and `get_relationships` 2 to 10 requests (about 1 s for IL6 with 242 eQTL rows, about 3.5 s for BRCA1 with 1742 rows over 7 pages). Requests are spaced 0.3 s apart.

### Quirks (all verified live)

- **Version-qualified GENCODE ids.** `medianGeneExpression` and `singleTissueEqtl` need the exact id of the release (`ENSG00000012048.23` in v10, `.20` in v8). A wrong version returns an empty `data` list with HTTP 200, not an error. The adapter therefore always resolves ids and symbols through `geneSearch` first, which accepts unversioned or wrongly versioned Ensembl ids.
- `geneSearch` does a **prefix match on symbols** (`BRCA` returns BRCA1, BRCA2, BRCA1P1). It accepts neither Entrez ids (`672`) nor HGNC ids nor disease text (`fatigue`): those return an empty list. The adapter returns `None`/`[]` for them instead of guessing.
- eQTL rows come **ordered by tissue, not by significance**, in pages of up to 250, and the API has no sort parameter. To report the most significant variants the adapter scans up to `eqtl_max_pages` (default 8, i.e. 2000 rows) pages and ranks the scanned rows by p-value. Genes with more rows than that get `truncated: True` on every eQTL edge (with `rows_scanned` and `rows_total`); raise `GTExAdapter.eqtl_max_pages` if you need a complete ranking.
- Median expression includes cell-culture "tissues" (`Cells_EBV-transformed_lymphocytes`, `Cells_Cultured_fibroblasts`) which often top the list; judge them separately from primary tissues.

## Searching

`search_concepts(query, limit)` finds genes whose symbol starts with `query` (or the gene with that Ensembl id), at most 50. An exact symbol match comes first (confidence 0.95), then other protein-coding genes, then the rest (pseudogenes, lncRNAs). Search concepts carry no expression data.

## Concept details

`get_concept_details(concept_id)` returns a `GENE` concept.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | unversioned Ensembl id `ENSG00000012048` / HGNC symbol |
| `definitions` | gene name from the GENCODE description (`BRCA1 DNA repair associated`) |
| `categories` | gene type (`protein coding`) |
| `identifiers` | unversioned and versioned Ensembl ids (`GTEX`, with the portal URL), `NCBIGene:672` |
| `source_data[GTEX]` | gene record (`dataset`, `gencode_id`, `gencode_version`, `chromosome`, `start`, `end`, `strand`, `genome_build`, `entrez_gene_id`, `gene_type`) plus the compact expression summary below |

Expression summary keys: `top_tissues_tpm` (top 10 `{tissue, tpm}`), `n_tissues` (54), `n_tissues_expressed` (median TPM >= 1), `max_tpm`, `tau` and `tissue_specificity`. `tau` is the Yanai tissue-specificity index on log2(1 + TPM) (0 housekeeping, 1 one tissue only); `tissue_specificity` is a heuristic label (`tissue-specific` >= 0.8, `intermediate` >= 0.5, otherwise `broadly expressed`), **not a GTEx annotation**. Examples (v10): GAPDH 0.20 broadly expressed, CD4 0.55 intermediate, IL6 0.72 intermediate, TNF 0.92 tissue-specific (lymphoblastoid cell line far above all other tissues).

## Relationships

`get_relationships(concept_id, limit=10)` returns two edge types; `limit` applies to each type, so up to `2 * limit` edges.

| `relation_label` | Content |
|---|---|
| `expressed_in` | the `limit` tissues with the highest median TPM (only tissues with median >= 1 TPM). `related_id` is the tissue's ontology id supplied by GTEx (`UBERON:0000473`, or `EFO:` for cell lines), `related_name` the GTEx tissue id (`Testis`, `Brain_Cortex`); extras `median_tpm`, `unit`, `rank`, `dataset` |
| `has_eqtl_variant` | the `limit` most significant gene-variant-tissue eQTLs among the scanned rows. `related_id` is the rsID (the GTEx `variantId` if there is none), `related_name` the GTEx variant id (`chr17_43323919_A_G_b38`); extras `tissue`, `tissue_ontology_id`, `p_value`, `slope` (normalised effect size, sign gives direction), `chromosome`, `position` (GRCh38), `dataset`, `rows_scanned`, `rows_total`, `truncated` |

If one of the two requests fails, the other type is still returned. The edge `source` is `GTEX`.

## Mappings

`get_mappings(concept_id)` returns `NCBIGene:<entrez>`, `HGNC:<id>` (parsed from the GENCODE description), the version-qualified `ENSEMBL:<id>` as GTEx serves it (`mappingType: "version"`) and `HGNC.SYMBOL:<symbol>`, from the Ensembl id as `fromId`.

## Contrast with the Human Protein Atlas adapter

| | GTEx | [Human Protein Atlas](hpa_adapter.md) |
|---|---|---|
| Expression | bulk RNA-seq medians (TPM), 54 tissues incl. cell lines, ~950 donors | consensus RNA nTPM from HPA and GTEx, 50 tissues plus 18 blood immune cell types |
| Specificity | computed here (tau) | curated HPA categories (tissue enriched, group enriched ...) |
| Protein-level data | none | plasma protein, subcellular location, blood concentration |
| Genetics | **single-tissue eQTLs** (variant, p-value, slope) | none |
| Access | per-gene REST calls, 2 - 10 requests | one keyless download call |
| Immune cells | none (whole blood only, as a tissue) | yes |

Use HPA for "which immune cell type expresses it" and protein location, GTEx for "which variants regulate it, in which tissue".

## Rate limits and caveats

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); `min_request_timeout` is 60 s. Errors, unknown genes and unsupported ids are logged; search returns `[]`, details `None`.

- GTEx is adult post-mortem tissue (mostly older donors, several ischemic times): expression in tissues obtained at autopsy is not equal to expression in living patients' blood or muscle, which matters for ME/CFS and Long COVID.
- eQTL slopes are in normalised units, not fold change.
- Dataset and GENCODE versions change gene ids and coordinates; `dataset` and `gencode_id` are included so results stay interpretable.

## See also

- [Human Protein Atlas adapter](hpa_adapter.md), [Ensembl adapter](ensembl_adapter.md)
- [All adapters](../README.md)
