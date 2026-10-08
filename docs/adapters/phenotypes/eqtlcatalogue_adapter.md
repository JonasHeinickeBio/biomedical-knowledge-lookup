---
description: EBI eQTL Catalogue dataset, study and tissue metadata (the association REST API has been retired; no gene or variant queries).
---

# eQTL Catalogue adapter

!!! warning "Metadata only: the eQTL Catalogue REST API no longer exists"
    Every path under `https://www.ebi.ac.uk/eqtl/api` (`/v1`, `/v2`, `/v3`, `/associations`, `/studies`, `/api-docs`) answers **HTTP 410 Gone** ("This API is no longer available", verified 2026-10-08), and the project's Data access page states that the RESTful API "has now been deprecated and is no longer available". Association data (gene to eQTL variant, variant to gene) are published only as bulk files on the EBI FTP site. This adapter therefore does **not** answer association questions. It serves the catalogue's dataset table, which is what is still reachable over HTTPS.

This adapter lists the uniformly processed QTL **datasets** of the [eQTL Catalogue](https://www.ebi.ac.uk/eqtl/): which study, which tissue or cell type (with its ontology id), which condition (naive or a stimulus), which quantification method (gene expression, exon, transcript, splicing, protein) and how many samples. Use it to find out where a regulatory dataset exists for a tissue or cell type, then query associations elsewhere (see the comparison below).

| | |
|---|---|
| Source | `KnowledgeSource.EQTLCATALOGUE` |
| Class | `knowledge_lookup.adapters.EQTLCatalogueAdapter` |
| Requires | none |
| Identifiers | dataset `QTD000021`, study `QTS000002`, tissue / cell type `CL:0000235`, `UBERON:0000178` (underscore form accepted) |
| Upstream | `https://raw.githubusercontent.com/eQTL-Catalogue/eQTL-Catalogue-resources/master/data_tables/dataset_metadata_r7.tsv` |
| Optional env | `EQTLCATALOGUE_RELEASE=r7` (default) or `r8_beta` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EQTLCatalogueAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with EQTLCatalogueAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("macrophage", limit=4):
            print(concept.primary_id, concept.concept_type, concept.primary_label)

        for rel in await adapter.get_relationships("QTD000006"):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])


asyncio.run(main())
```

Output:

```
CL:0000235 CELL_TYPE macrophage
QTS000001 REFERENCE Alasoo_2018
QTS000021 REFERENCE Nedelec_2016
QTD000001 ASSAY Alasoo_2018 - macrophage (naive, ge)
part_of_study QTS000001 Alasoo_2018
profiled_in_tissue CL:0000235 macrophage
described_in PMID:29379200 PMID 29379200
```

## The dataset table

One 76 KB tab-separated file (release 7: **758 datasets, 42 studies, 99 tissues / cell types**), fetched once per hour at most (plain HTTPS, about 0.8 s). Columns: `study_id` (QTS), `dataset_id` (QTD), `study_label`, `sample_group`, `tissue_id` (`UBERON_`, `CL_`, `EFO_` or `BTO_`, converted to `CL:...`), `tissue_label`, `condition_label`, `sample_size`, `quant_method`, `pmid`, `study_type` (`bulk` 591 datasets, `single-cell` 167).

| `quant_method` | Meaning |
|---|---|
| `ge` | gene expression (eQTL) |
| `exon` | exon expression |
| `tx` / `txrev` | transcript usage / transcript event usage |
| `leafcutter` | splice junction usage (sQTL) |
| `microarray` | microarray gene expression |
| `aptamer` | plasma protein abundance (pQTL, one study: Sun 2018) |

`EQTLCATALOGUE_RELEASE=r8_beta` selects the release 8 pre-release table (GTEx v10, MAGE, IBDverse; the final release 8 is announced for December 2026). Release 7 is the default because it is the stable release.

## Searching and details

- `search_concepts(query)` matches every query word against ids, labels, sample group, condition, quantification method (also by its description: "splice", "protein"), PMID and study type. Order: tissues / cell types, then studies, then datasets. An exact `QTD`, `QTS` or ontology id returns just that concept. **Gene symbols and rsIDs find nothing.**
- Tissue concepts are typed `CELL_TYPE` for `CL:` ids and `TISSUE` otherwise; studies `REFERENCE`; datasets `ASSAY`.
- `get_concept_details`: a dataset's `source_data[EQTLCATALOGUE]` has `study_id`, `study_label`, `sample_group`, `tissue_id`, `tissue_label`, `condition`, `sample_size`, `quant_method`, `pmid`, `study_type` and, for release 7, `sumstats_url`, the FTP address of the summary-statistics file (`ftp://ftp.ebi.ac.uk/pub/databases/spot/eQTL/sumstats/<QTS>/<QTD>/<QTD>.all.tsv.gz`). Only the address is returned; the file is never fetched. A study or tissue concept summarises its datasets, conditions and quantification methods.

## Relationships and mappings

| From | `relation_label` |
|---|---|
| dataset | `part_of_study`, `profiled_in_tissue` (extras `condition`, `sample_group`), `described_in` (`PMID:...`) |
| study | `profiles_tissue`, `has_dataset` |
| tissue / cell type | `profiled_in_study`, `has_dataset` |

`limit` (default 25) caps each repeated type. `get_mappings`: a dataset maps to its tissue term (`UBERON`, `CL`, `EFO` or `BTO`) and `PMID`; a study to its `PMID`; an ontology term to itself, so it can be passed to the Cell Ontology / UBERON adapters. There are no Ensembl or rsID mappings because the catalogue no longer serves genes or variants.

## How this differs from GTEx and Open Targets

| | eQTL Catalogue (this adapter) | [GTEx](../proteins/gtex_adapter.md) | Open Targets |
|---|---|---|---|
| Gene to eQTL variants | no (API retired, bulk files only) | yes, keyless API, 50 tissues | yes, as credible sets / colocalisation |
| What it offers here | which datasets exist per tissue, cell type, condition, method | expression medians and eQTLs of one gene | target / disease evidence incl. QTL credible sets built from this catalogue |
| Coverage | 42 studies, many immune cell types, stimulated conditions, single-cell | one consortium (GTEx v8 / v10) | aggregates several sources |

Cell types and stimuli (for example macrophages exposed to IFN-gamma, T cells with anti-CD3/CD28) are where the catalogue is broader than GTEx, which is why the dataset list is still useful for immunology questions on ME/CFS and Long COVID.

## Licence

Data: Creative Commons Attribution 4.0; code: Apache 2.0 (eQTL Catalogue License page). Cite Kerimov et al., *Nat Genet* 2021 (PMID 34493867) and Kerimov et al., *PLoS Genet* 2023 (PMID 37751440), plus the original study of each dataset (`pmid`).

## Rate limits and errors

Only one small file is downloaded per hour. The shared retry and circuit breaker apply. A response that is not the expected table (for example an HTML error page) is rejected. Errors are logged; every method returns `[]` or `None`.

## Live verification (2026-10-08)

| Call | Result |
|---|---|
| `https://www.ebi.ac.uk/eqtl/api/v1`, `/v2`, `/v3`, `/associations`, `/studies`, `/api-docs` | 410 Gone, 112 to 126 B, 0.2 s |
| `https://www.ebi.ac.uk/eqtl/Data_access/` | "The RESTful API has now been deprecated and is no longer available" |
| `data_tables/dataset_metadata_r7.tsv` | 200, 75,969 B, 758 rows |
| `data_tables/dataset_metadata_r8_beta.tsv` | 200, 64,533 B |
| `http://ftp.ebi.ac.uk/.../QTS000002/QTD000021/QTD000021.all.tsv.gz` (HEAD) | 200, 2,991,536,954 B (3 GB); `https://ftp.ebi.ac.uk` refuses connections |
| `knowledge-lookup check EQTLCATALOGUE -q macrophage` | pass (search 0.8 s, details and relationships from cache) |

`knowledge-lookup check EQTLCATALOGUE` with the default query `BRCA1` finds nothing by design; pass `-q macrophage`.

## Why associations are not implemented

The only remaining access to associations is the FTP tree: files of up to 3 GB per dataset, served over plain HTTP or FTP (HTTPS is refused), tabix-indexed in release 7 and being migrated to parquet in release 8, with an explicit warning that frequent tabix requests are treated as denial-of-service attacks by the EBI firewall. That conflicts with this library's rules (no bulk download by default, no plain-HTTP default, small polite requests). If you need associations for a gene, use the GTEx adapter, or download the relevant `*.all.tsv.gz` yourself using the `sumstats_url` returned here.

## See also

- [GTEx adapter](../proteins/gtex_adapter.md), [Cell Ontology adapter](../ontologies/cellontology_adapter.md), [CZ CELLxGENE adapter](../ontologies/cellxgene_adapter.md)
