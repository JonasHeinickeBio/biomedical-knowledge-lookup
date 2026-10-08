---
description: SemMedDB subject-predicate-object relations extracted from PubMed, read from a local SQLite database (UMLS licence).
---

# SemMedDB adapter

Reads SemMedDB, the NLM database of subject-predicate-object "predications" that the SemRep NLP system extracted from PubMed titles and abstracts (`Hydrocortisone -TREATS-> Chronic fatigue syndrome`), from a **local, read-only SQLite file that you build yourself**. Concepts are UMLS CUIs and every predication carries the PMID it came from, so the adapter is a good source of literature-backed relations and supporting PMIDs.

> **Verification status.** SemMedDB needs a UMLS licence and a UTS login, so the adapter and the SQLite builder have **not been run on the real NLM files**. They are tested on synthetic data in the real formats (a `mysqldump`-style file with the awkward escapes, CSV and TSV) and were measured at 2 million rows including a skewed "hub" concept (see [Scale](#scale-and-measured-numbers)). Use `--max-rows` on your real download first to confirm the format is understood.

| | |
|---|---|
| Source | `KnowledgeSource.SEMMEDDB` |
| Class | `knowledge_lookup.adapters.SemMedDBAdapter` |
| Requires | a SQLite database built from the NLM download with `knowledge-lookup semmeddb-build`, then `SEMMEDDB_PATH` (or `api_keys={"semmeddb": "/path/file"}`, a file path rather than a secret) |
| Identifiers | UMLS CUI: `C0015674`, `UMLS:C0015674` |
| Upstream | [SemMedDB](https://lhncbc.nlm.nih.gov/ii/tools/SemRep_SemMedDB_SKR/SemMedDB_download.html) (NLM Lister Hill Center), no API |

`is_available()` is true only when the file exists, so `CentralKnowledgeLookup` skips the source on machines without the data and `knowledge-lookup check SEMMEDDB` reports it as skipped.

## Licence and data

SemMedDB is distributed by the NLM Lister Hill Center. Downloading needs a free UMLS Terminology Services (UTS) account, i.e. acceptance of the UMLS licence; see the [download page](https://lhncbc.nlm.nih.gov/ii/tools/SemRep_SemMedDB_SKR/SemMedDB_download.html).

**VER43 is the final release.** NLM states there will be no further updates and has removed the earlier versions. It was processed with the MEDLINE 2022 baseline plus PubMed update files through 8 May 2024 using SemRep 1.8, and holds 37,233,341 citations and **130,480,195 predications**. The files are named `semmedVER43_2024_R_<TABLE>.sql.gz` (MySQL dump) and `semmedVER43_2024_R_<TABLE>.csv.gz` (CSV), each with `.md5sum` and `.sha1sum` checksum files. You only need the `PREDICATION` table; `PREDICATION_AUX` (character offsets and scores), `SENTENCE`, `CITATIONS`, `ENTITY` and `GENERIC_CONCEPT` are not used.

SemRep output is machine-extracted: precision is roughly 70-80% per predication, so treat counts as evidence strength, not as curated fact.

## Schema

Checked against the official SemMedDB database details page. The adapter uses only the `PREDICATION` table:

```
PREDICATION(PREDICATION_ID, SENTENCE_ID, PMID, PREDICATE,
            SUBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE, SUBJECT_NOVELTY,
            OBJECT_CUI,  OBJECT_NAME,  OBJECT_SEMTYPE,  OBJECT_NOVELTY)
```

Required columns: `PMID`, `PREDICATE`, `SUBJECT_CUI`, `SUBJECT_NAME`, `SUBJECT_SEMTYPE`, `OBJECT_CUI`, `OBJECT_NAME`, `OBJECT_SEMTYPE`. If they are not all present, the adapter logs an error and acts as unavailable. Other tables (`SENTENCE`, `CITATIONS`, `PREDICATION_AUX`, ...) are not needed. `SUBJECT_SEMTYPE` holds the UMLS semantic type abbreviation (`dsyn`, `phsu`, `aapp`, `sosy`, ...).

Note that for genes SemMedDB stores NCBI Gene ids instead of CUIs in `*_CUI` (sometimes `|`-separated lists). Those are not valid CUIs, so they do not resolve through this adapter, which accepts `C` plus 7 digits.

## Building the SQLite database

Download `semmedVER43_2024_R_PREDICATION.sql.gz` (the MySQL dump) or `semmedVER43_2024_R_PREDICATION.csv.gz`, check the checksum, and run the builder once. It streams the file (any size, memory use does not depend on it), writes `<output>.part` and renames it when finished, so an interrupted build leaves nothing half-built:

```bash
# 1. quick format check on the first 100,000 rows (seconds)
knowledge-lookup semmeddb-build semmedVER43_2024_R_PREDICATION.sql.gz -o /tmp/sample.sqlite --max-rows 100000

# 2. the real build (hours; see "Scale")
knowledge-lookup semmeddb-build semmedVER43_2024_R_PREDICATION.sql.gz -o semmeddb.sqlite
export SEMMEDDB_PATH=$PWD/semmeddb.sqlite
```

What it reads:

- **MySQL dump** (`.sql`, `.sql.gz`): `INSERT INTO `PREDICATION` VALUES (...),(...);` statements as written by `mysqldump` (extended inserts, `\'`, `\\` and `\n` escapes, `''`, `NULL`, an optional column list; column order is taken from `CREATE TABLE`). Statements for other tables are ignored, so a dump of the whole database also works. This is the unambiguous format.
- **CSV / TSV** (`.csv`, `.tsv`, `.txt`, `.gz`): with or without a header row (without one, the canonical column order from the schema above is assumed); `\N` and empty fields become NULL. It is about 3-5 times faster to parse than the dump, but NLM's exact CSV quoting could not be checked without an account: if more than 0.5% of rows are malformed the build stops with an error suggesting the dump instead. `--max-rows` shows this immediately.
- Several files may be passed to one build; rows are appended.

What it writes:

- the `PREDICATION` table with the five indexes the adapter needs (CUI, name with `COLLATE NOCASE`, PMID);
- two precomputed lookup tables, unless you pass `--no-aggregates`:
  - `CONCEPT(CUI, NAME, SEMTYPE, SIDE, N, P)`: one row per concept name with its predication count `N` and distinct-PMID count `P`. Name search (prefix **and** substring), concept details and existence checks read this table.
  - `TRIPLE(SUBJECT_CUI, PREDICATE, OBJECT_CUI, ..., PMIDS, PREDS)`: one row per distinct triple, indexed best-supported first, plus a composite (subject, object, predicate) index on `PREDICATION` for the supporting-PMID lookup. Relationships of even the biggest concepts are index range scans.

The adapter uses `CONCEPT` and `TRIPLE` when they exist and otherwise falls back to queries on `PREDICATION` (so a database you built by hand, or with `--no-aggregates`, still works, only slowly on a big table). A small export (up to 256 MB) can also be given directly as `SEMMEDDB_PATH`; it is imported on first use into `$KNOWLEDGE_LOOKUP_DATA_DIR` (default `~/.cache/knowledge_lookup/datasets`). Larger files are refused with a message pointing to the builder, because importing 130 million rows would block a lookup for hours.

### Scale and measured numbers

Measured on 2,000,000 synthetic rows in the real formats (names about 55 characters, longer than real ones), on a heavily loaded machine (load average about 20), so treat these as rough:

| | Measured |
|---|---|
| CSV, parse + insert | about 46,000 rows/s |
| MySQL dump, parse only | about 10,000-21,000 rows/s |
| Indexes | about 45 s per 2 M rows |
| Lookup tables (`CONCEPT`, `TRIPLE`) | about 72 s per 2 M rows |
| Size | 0.73 GB for the table and indexes, +0.47 GB for the lookup tables |
| Builder memory | about 0.9 GB (a 1 GB SQLite page cache) |

Extrapolating to the 130 M real predications is an **estimate, not a measurement**: roughly 45-70 GB for the table and indexes plus 20-30 GB for the lookup tables, and several hours (the load is linear, indexing and aggregation grow a little faster). Sorting needs temporary space of about the size of the table, so keep 150 GB or more free in the output volume (and in `$TMPDIR`, or set `SQLITE_TMPDIR`).

Query latency on the 2 M-row test database with a 400,000-row hub concept (20% of all rows):

| Query | Without the lookup tables | With them |
|---|---|---|
| hub concept details | 9.8 s | 0.04 s |
| hub relationships | 5.4 s | 0.01 s |
| name search, specific name | timed out (60 s) | 0.2 s |
| name search, very common prefix | timed out (60 s) | 0.7 s |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import SemMedDBAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with SemMedDBAdapter(LookupConfig()) as adapter:  # SEMMEDDB_PATH is set
        for concept in await adapter.search_concepts("chronic fatigue syndrome", limit=3):
            print(concept.primary_id, concept.primary_label, concept.semantic_types)

        for rel in await adapter.get_relationships("C0015674", limit=5):
            print(rel["direction"], rel["relation_label"], rel["related_name"], rel["pmid_count"])

        print(await adapter.get_supporting_pmids("C0020268", "TREATS", "C0015674", limit=5))


asyncio.run(main())
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | Concepts by CUI (`C0015674`, `UMLS:C0015674`) or name, aggregated per CUI and ranked by predication count; exact name matches first. The label is the CUI's most frequent name; other names become `synonyms`. |
| `get_concept_details(cui)` | The same concept for one CUI, or `None` if it does not occur. `source_data["SEMMEDDB"]` has `predication_count`, `predications_as_subject`, `predications_as_object`, `pmid_count`, `names`, `semtypes`. |
| `get_relationships(cui, limit=50, predicates=None)` | Triples grouped by (predicate, other CUI) in both directions, best-supported first. |
| `get_supporting_pmids(subject_cui, predicate, object_cui, limit=20)` | Distinct PMIDs (newest first) behind one triple, for the evidence step. |
| `get_mappings(cui)` | Identity mapping to `UMLS` when the CUI occurs in the data. |

Relationship edges carry `relation_label` (the SemMedDB predicate: `TREATS`, `CAUSES`, `ASSOCIATED_WITH`, `INTERACTS_WITH`, `PREDISPOSES`, `AFFECTS`, ...), `related_id` (CUI), `related_name`, `related_semtype`, `direction` (`outgoing` when the queried CUI is the subject, `incoming` when it is the object), `pmid_count` (distinct supporting PMIDs, the ranking key), `predication_count` (sentences) and `negated` (true for `NEG_*` predicates, kept as separate edges).

`concept_type` is derived from the most frequent UMLS semantic type (for example `dsyn`, `neop`: `DISEASE`; `sosy`: `SYMPTOM`; `phsu`: `DRUG`; `aapp`, `enzy`: `PROTEIN`; `gngm`: `GENE`) and falls back to `UNKNOWN`; the abbreviations are always kept in `semantic_types`. `confidence_score` is a fixed `0.7` because the data is machine-extracted.

## Query behaviour and safety

- The database is opened read-only (`mode=ro` URI plus `PRAGMA query_only`) on a worker thread (`asyncio.to_thread`); the adapter never writes to your database file.
- All SQL is parameterised, `LIKE` patterns escape `%`, `_` and `\`, and CUIs are validated against `C\d{7}` before use.
- Name search matches by prefix first, then by substring when fewer than `limit` concepts were found. With the `CONCEPT` table both are cheap. Without it the substring pass would scan the whole `PREDICATION` table twice, so it is skipped on databases of more than 5 million rows (`SUBSTRING_SCAN_MAX_ROWS`); you then only get prefix matches.
- Each query is aborted after `adapter.query_timeout` (60 s) so an accidental full scan cannot occupy a worker thread forever; the call then returns `[]`/`None` like any other error.
- `pmid_count` on a *concept* is summed over names and roles, so it can slightly over-count a PMID that supports a CUI in several roles; per-triple `pmid_count` in `get_relationships` is exact.

## See also

- [UMLS adapter](../core/umls_adapter.md) for CUI details, [PubTator adapter](pubtator_adapter.md), [Europe PMC adapter](europepmc_adapter.md)
- [All adapters](../README.md)
