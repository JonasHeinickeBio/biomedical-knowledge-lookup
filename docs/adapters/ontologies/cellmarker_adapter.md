---
description: CellMarker cell-type marker genes (human/mouse) from a lazily downloaded dataset: markers per cell type and cell types per gene, with tissue, species and PMID evidence.
---

# CellMarker adapter

Answers "which genes mark this cell type?" and "which cell types does this gene mark?" from CellMarker, a manually curated collection of cell-type marker genes with the tissue, species, technology and PMID behind every record. Cell types carry Cell Ontology IDs when CellMarker has one, so the results connect to the [Cell Ontology adapter](cellontology_adapter.md).

| | |
|---|---|
| Source | `KnowledgeSource.CELLMARKER` |
| Class | `knowledge_lookup.adapters.CellMarkerAdapter` |
| Requires | a downloaded data file (fetched on first use, or `CELLMARKER_PATH`) |
| Identifiers | `CL:0000084` or a cell name, a gene symbol (`CD4`), a marker alias (`CD16`), `NCBIGene:920` |
| Upstream | `http://bio-bigdata.hrbmu.edu.cn/CellMarker/` (no query API, files only) |
| Licence | academic use; check the CellMarker terms before commercial use. Cite Hu C et al., *Nucleic Acids Res* 2023 |

## Quick example

```python
import asyncio
import os

# Optional: use a local file instead of downloading (xlsx, tsv, csv, txt, .gz)
# os.environ["CELLMARKER_PATH"] = "/data/Cell_marker_Human.xlsx"

from knowledge_lookup.adapters import CellMarkerAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with CellMarkerAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("CD4", limit=3):
            print(c.primary_id, c.primary_label, c.concept_type)

        for rel in await adapter.get_relationships("CL:0000623", limit=3):  # NK cell
            print(rel["relation_label"], rel["related_name"], rel["pmid_count"], rel["species"])

        print(await adapter.get_mappings("CD4"))


asyncio.run(main())
```

## Data source

CellMarker has no API. The adapter downloads **one** file the first time a method needs data (never at import or construction), caches it under `$KNOWLEDGE_LOOKUP_DATA_DIR` (default `~/.cache/knowledge_lookup/datasets`) for 90 days, parses it in a worker thread, and keeps an aggregated in-memory index. The index is also saved next to the file as `<file>.index.json.gz`, so the one-off parse of about a million rows happens once per data file. If a refresh fails, the stale copy is used.

URLs checked on 2026-10-06 with HEAD and range requests only (nothing was downloaded in full):

| File | Size | Notes |
|---|---|---|
| `http://117.50.127.228/CellMarker/CellMarker_download_files/file/Cell_marker_Human.xlsx` | 7,982,475 B | **default**; CellMarker 2.0, 2022-09-28, 20 columns, 1,013,379 rows, 62 MB sheet XML |
| `.../Cell_marker_Mouse.xlsx` / `Cell_marker_All.xlsx` / `Cell_marker_Seq.xlsx` | 3.7 MB / 10.0 MB / 6.0 MB | same host and layout; `All` is human + mouse |
| `http://bio-bigdata.hrbmu.edu.cn/CellMarker/file/human_cell_marker.zip` | 48,740,702 B | CellMarker **3.0** (the official host now serves 3.0 as a JavaScript app); the zip holds `human_cell_marker.txt`, 577,624,367 B of TSV |
| `.../all_cell_marker.zip`, `mouse_cell_marker.zip`, `single_cell_marker.zip`, `method_cell_marker.zip` | 71.8 / 23.1 / 12.1 / 65.2 MB | 3.0; `all` unpacks to 830 MB |

The old official paths (`bio-bigdata.hrbmu.edu.cn/CellMarker/CellMarker_download_files/file/*.xlsx`) now answer 404; the 2.0 files are still served by the bare-IP server `117.50.127.228`, which is why the default URL looks unusual. Because that is an HTTP IP address with no stability guarantee, pin your own copy for reproducible work.

Configuration (read at call time; add them to `.env` if you want them persistent):

- `CELLMARKER_PATH`: local file; skips any download. Accepts `.xlsx`, `.tsv`, `.txt`, `.csv`, optionally gzipped.
- `CELLMARKER_URL`: alternative download URL, an `.xlsx`, or a zip/gz of a TSV/CSV (for example a 3.0 zip, with the memory caveat below).

The 3.0 files work (their header is understood) but the human file has roughly 1.7 million rows; expect minutes of parsing and several hundred MB of RAM on the first load. The 2.0 human file is the practical default.

Column names differ between releases and are matched case-insensitively ignoring punctuation (`Symbol`/`symbol`, `UNIPROTID`/`uniprot_id`, `uberonongology_id` [sic]/`uberon_id`, `cancer_type`/`disease`). Required: `cell_name` and `symbol` or `marker`. Read: species, tissue_class, tissue_type, uberon id, cancer_type/disease, cellontology_id, marker, Symbol, GeneID, gene type, gene name, UniProt, marker_source, PMID.

### xlsx without openpyxl

`openpyxl` is not a dependency. `knowledge_lookup.adapters._xlsx.iter_xlsx_rows(path)` is a small stdlib reader (`zipfile` + `xml.etree`): first sheet only, strings from shared strings, inline strings or raw values, empty cells kept as `""` so columns stay aligned, rows streamed. It was tested on a synthetic workbook built in the tests and on a workbook assembled from real range-read pieces of `Cell_marker_Human.xlsx` (header plus the first 2,160 rows).

## Index and matching

Records are aggregated per (cell type, marker gene). A cell type is keyed by its CL ID when present, else by its lower-cased name (`CellMarker:<name>` as ID); different cell names with the same CL ID are merged under the most frequent name. A gene is keyed by the case-insensitive symbol (so human `CD4` and mouse `Cd4` merge); the `marker` text that differs from the symbol (`CD16` for `FCGR3A`) is kept as an alias. Rows without cell name or marker are skipped; a marker without symbol is kept under its marker text.

## Searching

`search_concepts(query, limit)` ranks: exact gene symbol or exact cell name/CL ID, then marker alias, then prefix matches, then substring matches in cell names (3+ characters); ties go to the entity with more evidence. Genes come back as `GENE`, cell types as `CELL_TYPE`, `confidence_score` falls with rank.

## Concept details

`get_concept_details(concept_id)` resolves, in order: a CL ID (`CL:0000084`, `CL_0000084`), an Entrez ID (`920`, `NCBIGene:920`, `GeneID:920`), `CellMarker:<cell name>`, a gene symbol, a marker alias, an exact cell name.

- Cell type: `primary_id` is the CL ID (or `CellMarker:<name>`), `synonyms` are the other names, `categories` hold `tissue: <name>` (10), the CL ID is also added as a `CELLONTOLOGY` identifier, `source_data[CELLMARKER]` has `cl_id`, `species`, `tissues`, `uberon_ids`, `conditions` (non-normal cancer types), `marker_count`, `pmid_count`, `top_markers` (25, most PMIDs first).
- Marker gene: `primary_id` is the symbol, `primary_label` the gene name, `synonyms` symbol plus aliases, `identifiers` NCBI Gene and UniProt, `semantic_types` the gene type, `source_data[CELLMARKER]` has `cell_type_count`, `record_count`, `top_cell_types`.

## Relationships

`get_relationships(concept_id, limit=25)`:

- cell type: `has_marker` -> genes (`related_id` is `NCBIGene:<id>`, or the symbol when CellMarker has no Gene ID);
- gene: `is_marker_of` -> cell types (`related_id` is the CL ID or `CellMarker:<name>`).

Sorted by distinct PMIDs, then record count. Each item adds `species`, `tissues` (up to 5), `tissue_count`, `pmid_count`, `record_count`, `pmids` (up to 5) and `evidence_types` (`Experiment`, `Review`, `Single-cell sequencing`, ...).

## Mappings

- cell type: `CL:xxxxxxx` (`toSource: "CL"`, 0.95) when CellMarker has one;
- gene: `NCBIGene` Entrez ID and every `UniProt` accession (0.95 / 0.9), `fromId` is the `NCBIGene:` reference.

## Caveats

- Not verified against a full download: the full 8 MB / 1 M-row parse, memory use and the persisted index were not run (range-read head only, about 2,160 rows, plus the unit tests). Authorise a full run to measure them.
- Marker evidence is literature-curated and heterogeneous: `Experiment`, `Review` and (in 3.0) computational `Method` rows are all counted. Look at `evidence_types` and `pmid_count`.
- Cell names are free text across tissues and diseases; the same CL ID can come with many different names. Disease context (`cancer_type`) is only exposed as the set of non-normal conditions per cell type.
- Species: the default file is human only; with `All` or mouse files the evidence items list the species.

## Errors

`is_available()` is `True` unless `CELLMARKER_PATH` points at a missing file. If the dataset cannot be downloaded or parsed, the error is logged and the circuit breaker notified; search returns `[]` and the other methods `None`/`[]`, and the next call tries again.

## See also

- [Cell Ontology adapter](cellontology_adapter.md)
- [All adapters](../README.md)
