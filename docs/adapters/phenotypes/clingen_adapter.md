---
description: ClinGen gene-disease validity classifications (Definitive to Refuted) and gene dosage sensitivity, from ClinGen's small CSV exports.
---

# ClinGen adapter

Answers "how well established is the link between gene X and disease Y according to the ClinGen expert panels?" and "is gene X haploinsufficient / triplosensitive?". Concepts are genes (HGNC ids) and diseases (MONDO ids); relationships carry the classification, mode of inheritance, curation date and expert panel (GCEP), with dosage sensitivity as extra keys.

| | |
|---|---|
| Source | `KnowledgeSource.CLINGEN` |
| Class | `knowledge_lookup.adapters.ClinGenAdapter` |
| Requires | opt-in download (~1.4 MB): `CLINGEN_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or a local file in `CLINGEN_PATH` |
| Identifiers | `HGNC:1100` or a symbol such as `BRCA1`; `MONDO:0007947` |
| Data files | `https://search.clinicalgenome.org/kb/gene-validity/download` (1.1 MB, 3,702 curations), `https://search.clinicalgenome.org/kb/gene-dosage/download` (0.33 MB, 1,715 genes) |
| Environment | `CLINGEN_PATH`, `CLINGEN_DOSAGE_PATH` (optional), `CLINGEN_DOWNLOAD`, `KNOWLEDGE_LOOKUP_DATA_DIR` |
| Licence | CC0 1.0; cite ClinGen |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ClinGenAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ClinGenAdapter(LookupConfig()) as adapter:  # first call downloads ~1.4 MB
        for c in await adapter.search_concepts("BRCA1"):
            print(c.primary_id, c.primary_label, c.concept_type)

        for edge in await adapter.get_relationships("HGNC:1100"):
            print(edge["relation_label"], edge["related_id"], edge["related_name"],
                  edge["classification"], edge["mode_of_inheritance"], edge["curation_date"],
                  edge["dosage_haploinsufficiency"])


asyncio.run(main())
```

Output (2026-10-07):

```
HGNC:1100 BRCA1 ConceptType.GENE
MONDO:0700268 BRCA1-related cancer predisposition ConceptType.DISEASE
associated_with MONDO:0700268 BRCA1-related cancer predisposition Definitive Autosomal dominant 2024-08-29 Sufficient Evidence for Haploinsufficiency
associated_with MONDO:0054748 Fanconi anemia, complementation group S Definitive Autosomal recessive 2020-05-14 Sufficient Evidence for Haploinsufficiency
```

## Where the data comes from

The ClinGen site has **no documented query API**. Probed live: `search.clinicalgenome.org/api/genes/HGNC:1100` and `/api/` answer 404; the web UI's typeahead helpers (`/api/genes/look/{q}`, `/api/genes/lookByName/{q}`, `/api/conditions/look/{q}`) return JSON with a `text/html` content type and are undocumented (the condition lookup took 20 s), so they are not used; the Evidence Repository API (`erepo.clinicalgenome.org/evrepo/api/...`) only serves variant classifications. The CSV exports linked on `/kb/downloads` are the supported route, so the adapter is opt-in like the other dataset-backed sources:

- `is_available()` is true when `CLINGEN_PATH` names an existing validity CSV, the validity file is already cached, or a download is allowed.
- The files are fetched lazily on the first call through `ensure_dataset` (cache `~/.cache/knowledge_lookup/datasets/clingen_gene_validity.csv` and `clingen_gene_dosage.csv`, refreshed after 7 days; a stale copy is used if a refresh fails), parsed in a worker thread and indexed in memory. Measured: validity download 3.4 s, dosage 2.4 s; the first `search_concepts` call, including both downloads, took 5 s; later calls are local (<1 ms).
- With `CLINGEN_PATH` set the dosage file is only read when `CLINGEN_DOSAGE_PATH` is set too; it is never downloaded behind a user-supplied path. Dosage data is optional: if it cannot be loaded the adapter continues without it.

Validity CSV columns: `GENE SYMBOL, GENE ID (HGNC), DISEASE LABEL, DISEASE ID (MONDO), MOI, SOP, CLASSIFICATION, ONLINE REPORT, CLASSIFICATION DATE, GCEP` after a 3-line title block and `+++` rules. In the 2026-10-07 file: Definitive 2,309, Limited 553, Moderate 459, Disputed 199, Strong 85, Refuted 49, No Known Disease Relationship 48; MOI codes AR 1,862, AD 1,490, XL 207, SD 59, MT 55, UD 29; 59 expert panels.

## What each method returns

- `search_concepts(query, limit)`: genes by symbol and diseases by label, ranked exact 1.0 / prefix 0.9 / word-start 0.8 / substring 0.7, genes first on ties, then more curations first. `HGNC:1100`, `hgnc:1100` and `MONDO:0007947` (or `mondo:7947`) resolve directly. Searching a symbol also returns diseases named after it.
- `get_concept_details(id)`: gene (`HGNC:` id or symbol; genes that only have a dosage record are included) or disease. `definitions` holds a one-sentence curation summary (and the dosage statement), `categories` says which ClinGen product covers it, `identifiers` adds HGNC/MONDO. `source_data["CLINGEN"]` has `validity_summary` (best and consensus classification, counts, conflict flag), the full `validity` list and the `dosage` record.
- `get_relationships(id, limit=50)`: gene to diseases or disease to genes, strongest classification first, newest first within a class. `relation_label` is `associated_with` for Limited or stronger and `disputed_association_with`, `refuted_association_with` or `no_known_relationship_with` otherwise, so `associated_with` never contains a contradicted claim. Extra keys: `classification`, `classification_strength` (Definitive 1.0, Strong 0.85, Moderate 0.7, Limited 0.4, ...), `mode_of_inheritance` and `moi_code`, `curation_date`, `expert_panel`, `sop`, `report_url`, and `dosage_haploinsufficiency`, `dosage_triplosensitivity`, `dosage_date` for the gene.
- `get_mappings`: not provided (the files contain no cross-references beyond HGNC and MONDO).

## ClinGen, GenCC and Monarch/OMIM

- **ClinGen** (this adapter): one authority, expert-panel curations under a published SOP, about 3,700 gene-disease pairs plus dosage sensitivity. Absence means "not curated".
- [**GenCC**](gencc_adapter.md): aggregates ClinGen and many other curators (Orphanet, PanelApp, G2P, laboratories) on the same classification scale, tens of thousands of submissions; the same pair may have disagreeing entries. ClinGen's own rows appear inside GenCC.
- **Monarch / OMIM**: catalogue or knowledge-graph gene-disease associations without a validity grade ([Monarch](monarch_adapter.md), [OMIM](omim_adapter.md)).

## Caveats

- ME/CFS and Long COVID have no ClinGen gene-disease curations (no row mentions fatigue); use BRCA1, FBN1, TAFAZZIN style examples.
- Disease labels are MONDO labels as of the file date; several MONDO classes can share a gene (e.g. `mitochondrial disease` MONDO:0044970 has dozens of genes).
- The exports are dynamic (they say `FILE CREATED:` with today's date), so two downloads on different days can differ.

## Rate limits and errors

No documented limits; two small downloads per week at most. If the download fails and no cached copy exists, every method returns `[]` / `None` and the next call retries.

## See also

- [GenCC adapter](gencc_adapter.md), [HPO annotations](hpoa_adapter.md), [Orphanet adapter](orphanet_adapter.md)
- [All adapters](../README.md)
