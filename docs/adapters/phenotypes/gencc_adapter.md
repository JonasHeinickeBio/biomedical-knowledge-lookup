---
description: GenCC harmonised gene-disease validity submissions from ClinGen, Orphanet, PanelApp, G2P and laboratories, with a per-pair consensus (submissions export, opt-in download).
---

# GenCC adapter

Answers "which curators assert a link between gene X and disease Y, and how strongly?". GenCC (Gene Curation Coalition) maps submissions from many groups onto one classification scale (Definitive, Strong, Moderate, Supportive, Limited, Disputed Evidence, Refuted Evidence, Animal Model Only, No Known Disease Relationship). The adapter indexes the full submissions export and returns, for each gene-disease pair, every submitter's classification plus a computed best / consensus summary.

| | |
|---|---|
| Source | `KnowledgeSource.GENCC` |
| Class | `knowledge_lookup.adapters.GenCCAdapter` |
| Requires | opt-in download (~28.4 MB): `GENCC_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or a local copy in `GENCC_PATH` |
| Identifiers | genes `HGNC:1100` or `BRCA1`; diseases `MONDO:0008426` and the ids submitters used, `OMIM:182212`, `Orphanet:558` |
| Data file | `https://thegencc.org/download/action/submissions-export-csv` |
| Environment | `GENCC_PATH`, `GENCC_DOWNLOAD`, `KNOWLEDGE_LOOKUP_DATA_DIR` |
| Licence | CC0 1.0; cite GenCC (DiStefano et al., Genet Med 2022) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import GenCCAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with GenCCAdapter(LookupConfig()) as adapter:  # first call downloads ~28 MB
        for edge in await adapter.get_relationships("BRCA1", limit=5):
            print(edge["related_id"], edge["related_name"], edge["best_classification"],
                  edge["consensus_classification"], edge["n_submitters"], edge["conflicting"])
            for s in edge["submissions"]:
                print("   ", s["submitter"], s["classification"], s["mode_of_inheritance"], s["date"])


asyncio.run(main())
```

Not live-verified end to end (see below), so no output is shown.

## Where the data comes from

The site (`search.thegencc.org`, a Livewire app) has **no query API**: `/api`, `/api/docs` and `/swagger` all answer 404. The downloads page offers the submissions export in three formats (checked with HEAD requests, 2026-10-07):

| Format | Size | URL suffix |
|---|---|---|
| CSV | 28,355,883 bytes | `submissions-export-csv` |
| TSV | 26,541,421 bytes | `submissions-export-tsv` |
| XLSX | 7,262,917 bytes | `submissions-export-xlsx` |

All are uncompressed on the wire (no `Content-Encoding: gzip`), support `Range`, and were last modified 2026-10-04 (weekly refresh). The page also links `?format=new` variants; the plain CSV URL was the one sampled and has 30 columns (header row `uuid, gene_curie, gene_symbol, disease_curie, disease_title, disease_original_curie, disease_original_title, classification_curie, classification_title, moi_curie, moi_title, submitter_curie, submitter_title, submitted_as_*..., submitted_run_date`). The CSV was chosen because its format could be verified from 64 KiB `Range` samples; the 7 MB XLSX would need a full download to inspect. The host answers **HTTP 429** if several downloads or HEAD requests arrive within a few seconds, and one Range request timed out; allow a pause between attempts.

Because of the size, the adapter is opt-in:

- `is_available()` is true when `GENCC_PATH` names an existing file, the file is already cached (`~/.cache/knowledge_lookup/datasets/gencc-submissions.csv`), or `GENCC_DOWNLOAD=1` / `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1` is set.
- The first call downloads once via `ensure_dataset` (refreshed after 30 days, a stale copy is used if a refresh fails), parses with the `csv` module in a worker thread and builds in-memory indexes by gene, by disease and by submitted id. The long free-text `submitted_as_notes` are discarded. Columns are read by header name.
- `knowledge_lookup check GENCC` reports "no adapter available" unless opted in. **Full-file load time and memory were not measured**, because the 28 MB file was deliberately not downloaded; the parser and every method are tested on real rows from four 64 KiB `Range` samples (offsets 0, 3.5 MB, 7 MB, 11 MB: 118 Ambry Genetics rows and about 20 ClinGen rows per later sample) and a few clearly marked composed rows that add other submitters. To run it for real: `GENCC_DOWNLOAD=1 poetry run knowledge-lookup check GENCC`.

## What each method returns

- `search_concepts(query, limit)`: genes by symbol and diseases by (MONDO) label; ranking exact 1.0, prefix 0.9, word-start 0.8, substring 0.7, genes first on ties, then more submissions first. `HGNC:1100`, `MONDO:...`, `OMIM:...` and `Orphanet:...` resolve directly.
- `get_concept_details(id)`: gene or disease. `definitions` gives submission counts, number of partners and the strongest classification; `source_data["GENCC"]` has the submitter list, an overall `validity_summary` and, in detail mode, a per-partner summary (`diseases` for a gene, `genes` for a disease). An `OMIM:` or `Orphanet:` id returns the disease as submitted and lists the MONDO ids GenCC mapped it to as identifiers.
- `get_relationships(id, limit=50)`: gene to diseases or disease to genes, **one edge per pair**, strongest first. Keys: `relation_label` (from the best classification: `associated_with` for Limited or stronger, else `disputed_association_with`, `refuted_association_with`, `no_known_relationship_with`, `animal_model_association_with`), `best_classification`, `consensus_classification`, `classification_strength`, `n_submitters`, `classification_counts`, `conflicting`, `modes_of_inheritance`, `latest_date` and `submissions`: a list with `submitter`, `classification`, `mode_of_inheritance`, `date`, `original_disease_id`, `report_url`, `pmids`, `assertion_criteria_url` for every submitter.
- `get_mappings(id)`: the id mappings GenCC applied. A MONDO id returns the submitted ids (`OMIM:`, `ORPHA:`, ...) with `mappingType` `submitted_as`; an OMIM/Orphanet id returns its MONDO id(s). ClinGen rows (which submit MONDO ids) contribute nothing.

### How the consensus is computed

`best_classification` is the strongest given by anyone (order: Definitive, Strong, Moderate, Supportive, Limited, Animal Model Only, No Known Disease Relationship, Disputed, Refuted). `consensus_classification` is the most frequent classification; ties go to the weaker side (conservative). `conflicting` is true when a Moderate-or-stronger assertion coexists with a Disputed or Refuted one. These are conveniences, not GenCC outputs: always look at `submissions` before relying on a pair.

## GenCC, ClinGen and Monarch/OMIM

- **GenCC**: aggregator; many submitters, one scale, per-submitter rows; includes ClinGen's own curations, Orphanet's gene-disease assessments, PanelApp and Gene2Phenotype panels and clinical laboratories, so pairs can be strongly supported by some and disputed by others.
- [**ClinGen**](clingen_adapter.md): a single curator with its own SOPs and expert panels; also has dosage sensitivity; much smaller (1 MB) and quick to download.
- **Monarch / OMIM** ([Monarch](monarch_adapter.md), [OMIM](omim_adapter.md)): knowledge-graph or catalogue associations without a validity grade; OMIM ids appear inside GenCC only as the "original" disease id of submitters.

## Quirks seen in real rows

- Ambry Genetics rows put their PMID text (`PMID: 28106320` or a PMC URL) into `submitted_as_assertion_criteria_url`, leaving `submitted_as_pmids` empty; ClinGen rows put a GCI report URL and a PMID list in the right columns. `submissions[].pmids` and `assertion_criteria_url` therefore need to be read together.
- Dates have mixed shapes (`2018-03-30 13:31:56`, `2021-02-12T00:00:00.000000Z`); the adapter keeps the date part.
- `submitted_as_notes` of ClinGen rows can be several kB of text (not kept).
- The mode-of-inheritance title is harmonised (`Autosomal dominant`); the submitted wording is not retained.

## Rate limits and errors

One download per month at most; the host rate limits bursts (429). If the download fails and nothing is cached, every method returns `[]` / `None` and the next call retries.

## See also

- [ClinGen adapter](clingen_adapter.md), [Orphanet adapter](orphanet_adapter.md), [HPO annotations](hpoa_adapter.md)
- [All adapters](../README.md)
