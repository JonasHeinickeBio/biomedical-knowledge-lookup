---
description: CZ CELLxGENE Discover single-cell collections, datasets, cell types (CL), tissues (UBERON), diseases (MONDO) and marker genes.
---

# CZ CELLxGENE adapter

Searches [CZ CELLxGENE Discover](https://cellxgene.cziscience.com/), the Chan Zuckerberg Initiative's curated catalogue of single-cell RNA-seq data. Every dataset is annotated with ontology terms: Cell Ontology cell types (`CL`), tissues (`UBERON`), diseases (`MONDO`, `PATO:0000461` for normal), assays (`EFO`) and organism (`NCBITaxon`). The adapter answers "which single-cell datasets cover disease X, tissue Y or cell type Z" and "what are the marker genes of cell type Z". It never downloads the `.h5ad` data files: it only returns their URLs and sizes.

| | |
|---|---|
| Source | `KnowledgeSource.CELLXGENE` |
| Class | `knowledge_lookup.adapters.CellxGeneAdapter` |
| Requires | none (keyless) |
| Identifiers | collection / dataset UUID, cell type `CL:0000623`, tissue `UBERON:0000178`, disease `MONDO:0100233` (underscore form accepted) |
| Upstream API | `https://api.cellxgene.cziscience.com` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import CellxGeneAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with CellxGeneAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("long covid", limit=4):
            print(concept.primary_id, concept.concept_type, concept.primary_label[:60])

        rels = await adapter.get_relationships("MONDO:0100233")
        collection = next(r for r in rels if r["relation_label"] == "studied_in_collection")
        print(collection["related_name"], collection["cells"])

        for rel in await adapter.get_relationships("CL:0000623", limit=4):
            if rel["relation_label"] == "has_marker_gene":
                print(rel["related_name"], round(rel["marker_score"], 2), rel["tissue"])


asyncio.run(main())
```

Output:

```
MONDO:0100233 DISEASE long COVID-19
35d0b748-3eed-43a5-a1c4-1dade5ec5ca0 REFERENCE Impaired local intrinsic immunity to SARS-CoV-2 infection in
13b61a7d-5605-4948-ba48-02c588960143 ASSAY Nasopharynx
Impaired local intrinsic immunity to SARS-CoV-2 infection in severe COVID-19 32588
GNLY 2.11 blood
NKG7 1.84 blood
PRF1 1.59 blood
KLRD1 1.44 blood
```

## What the adapter calls, and why

| Endpoint | Size / time | Used for |
|---|---|---|
| `dp/v1/datasets/index` | 13.1 MB, 0.6 s | all 2,238 datasets with cell types, cell counts, tissues, diseases, assays, donors. The only cheap source of per-dataset cell types |
| `dp/v1/collections/index` | 555 KB, 0.4 s | 397 collection titles, journal, year, consortia |
| `curation/v1/collections/{id}` | 21 KB, 0.9 s | description, DOI, links, authors of one collection (supported Curation API) |
| `curation/v1/collections/{id}/datasets/{dataset_id}` | 3 to 5 KB, 0.8 s | `.h5ad` asset URL and size, citation, donor ids |
| `wmg/v2/primary_filter_dimensions` | 3.6 MB, 4 s | Ensembl id to gene symbol, tissues known to WMG (once per six hours) |
| `POST wmg/v2/markers` | 0.6 KB, 0.6 s | marker genes of one human cell type in one tissue |

The documented Curation API list `curation/v1/collections` (3.2 MB, 7 to 11 s, 397 collections) has no cell types or cell counts, so it is **not** fetched. The portal has no search endpoint: both `dp` indexes are loaded together on first use (about 2 s, 14 MB) and held in memory for 15 minutes; search and relationships are then local. The `dp/v1` indexes are the web app's own and could change without notice; if they fail every method returns `[]` / `None`.

Dataset ids: the index calls the dataset *version* id `id`, whereas portal URLs and the Curation API use the stable *dataset id*. The adapter uses the stable dataset id (taken from each dataset's `explorer_url`, which matches the Curation API for all 2,238 datasets) as `primary_id` and also accepts the version id.

## Searching

`search_concepts(query, limit)` matches every query word, case-insensitively and as a whole word (a plural `s` is allowed, so `long` does not match "longitudinal"), against:

- **terms** (cell types, tissues, diseases that occur on at least one dataset): `0.95` for an exact label, `0.85` otherwise; typed `CELL_TYPE`, `TISSUE`, `DISEASE`;
- **collections**: `0.8` by title, `0.65` when a dataset inside carries a matching disease label (typed `REFERENCE`);
- **datasets**: `0.6` by title, `0.5` by disease label (typed `ASSAY`).

Buckets are interleaved, so even `limit=3` shows a term, a collection and a dataset. Within a bucket, higher score first, then larger. An ontology id as the query finds that term.

For this project's topics (2,238 datasets, October 2026):

- `long COVID-19` (`MONDO:0100233`) occurs on **one** dataset, a nasopharynx dataset (32,588 cells) of the collection *Impaired local intrinsic immunity to SARS-CoV-2 infection in severe COVID-19*; `post-COVID-19 disorder` (`MONDO:0100320`) is a separate term; `COVID-19` (`MONDO:0100096`) carries 66 datasets with a COVID-related label.
- There is **no** myalgic encephalomyelitis / chronic fatigue syndrome term: the query `chronic fatigue` returns nothing.

## Concept details

`get_concept_details(concept_id)`:

- **Collection**: index data plus the Curation API call. `definitions` = the collection description; `source_data[CELLXGENE]` has `citation`, `journal`, `year`, `is_preprint`, `consortia`, `n_datasets`, `total_cells`, `tissues`, `diseases`, `assays`, `organisms`, `n_cell_types`, `doi`, `first_authors` (5), `links` (raw data, code), `url`. Contact names and e-mails are deliberately not returned.
- **Dataset**: `collection_id`, `collection_name`, `cell_count`, `n_donors`, `organisms`, `tissues`, `diseases`, `assays`, `n_cell_types`, `cell_types` (first 50), `explorer_url`, and from the Curation API `assets` (`filetype`, `url`, `filesize_bytes`), `citation`, `donor_ids` (first 20), `schema_version`. A 268 MB `.h5ad` is described, never fetched.
- **Cell type / tissue / disease**: `n_datasets`, `n_collections`, `cells_in_datasets` (sum of the cell counts of datasets that carry the term: all cells of those datasets, not only cells of this type, and re-annotated datasets can overlap) and `top_tissues`.

If the second (Curation API) request fails, the index-based concept is still returned. Multi-valued annotations stored as `MONDO:A || MONDO:B` in the index are split into separate terms.

## Relationships

`get_relationships(concept_id, limit=25, tissue=None)`; `limit` caps every repeated type.

| From | `relation_label` |
|---|---|
| collection | `has_dataset` (largest first; `cell_count`, `tissues`, `diseases`), `has_tissue`, `has_disease` (`n_datasets`) |
| dataset | `part_of_collection`, `has_tissue`, `has_disease`, `uses_assay` (EFO), `from_organism`, `has_cell_type` (CL) |
| cell type | `found_in_tissue`, `found_in_dataset` (largest first), `has_marker_gene` |
| tissue | `contains_cell_type`, `studied_in_collection` |
| disease | `studied_in_collection` (`n_datasets`, `cells`), `observed_in_tissue`, `contains_cell_type` |

`has_marker_gene` comes from the "Where is my gene" service: Ensembl id as `related_id`, symbol as `related_name`, plus `marker_score`, `specificity`, `tissue`, `tissue_id`, `snapshot_id`. Human only. Without `tissue=`, the adapter tries, in order, the WMG tissues named directly by the cell type's datasets (best represented first), then rolled-up ancestors, up to three tries; the first tissue with markers wins (NK cells: blood, giving GNLY, NKG7, PRF1, KLRD1). Pass `tissue="UBERON:0002048"` to pin one. The WMG snapshot is fixed (id `1762972271`, November 2025), so marker scores do not follow later dataset releases. `binomtest` is rejected by the service (HTTP 500); the adapter uses `ttest`.

## Mappings

`get_mappings`: a dataset or collection maps to its `UBERON`, `MONDO` / `PATO`, `EFO`, `NCBITAXON` and `CL` terms (`mappingType` `annotation`, capped at 100); a collection also maps to `DOI:<doi>`. A term maps to itself (`exact`) so it can be passed to the Cell Ontology, UBERON or MONDO adapters. The portal exposes no PMID.

## Rate limits and errors

No limit is published. Requests are spaced 0.3 s and use the shared retry and circuit breaker with a 120 s timeout (the 13 MB index). Errors are logged; search returns `[]`, details `None`.

## Licence

Datasets are released under CC BY 4.0 or CC0 depending on the collection (see the collection page). Cite the original publication (the DOI in `source_data`) and CZ CELLxGENE Discover (CZI Single-Cell Biology Program et al., 2023).

## Live verification (2026-10-08)

| Call | Result |
|---|---|
| index load (both `dp` indexes, parse) | 2.1 s, 2,238 datasets, 397 collections, 2,128 terms |
| `curation/v1/collections` (not used) | 3.2 MB, 7 to 11 s |
| `knowledge-lookup check CELLXGENE` | pass (search 3.4 s cold, relationships incl. WMG markers 6 s cold) |
| `long covid` search | 3 results in 2 s: term, collection, dataset |
| marker request, NK cells in blood | 5 genes in 0.6 s (GNLY, NKG7, PRF1, KLRD1 among the top) |
| dataset `13b61a7d-...` | asset `https://datasets.cellxgene.cziscience.com/6a6db93e-....h5ad`, 268,167,914 bytes (not downloaded) |

## Caveats

- Dataset-level cell types: a cell type "found in" a dataset says it is annotated somewhere in it, not how many cells.
- The index mixes human and mouse (`from_organism`); markers are human only.
- Disease annotations are the submitters' (MONDO terms plus `normal`); patient groups inside one dataset are not separated.

## See also

- [Cell Ontology adapter](cellontology_adapter.md), [CellMarker adapter](cellmarker_adapter.md), [eQTL Catalogue adapter](../phenotypes/eqtlcatalogue_adapter.md)
