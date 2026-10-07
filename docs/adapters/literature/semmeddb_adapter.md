---
description: SemMedDB subject-predicate-object relations extracted from PubMed, read from a local SQLite database (UMLS licence).
---

# SemMedDB adapter

Reads SemMedDB, the NLM database of subject-predicate-object "predications" that the SemRep NLP system extracted from PubMed titles and abstracts (`Hydrocortisone -TREATS-> Chronic fatigue syndrome`), from a **local, read-only SQLite file that you build yourself**. Concepts are UMLS CUIs and every predication carries the PMID it came from, so the adapter is a good source of literature-backed relations and supporting PMIDs.

> **Not live-verified.** SemMedDB has no public API and the data needs a UMLS licence, so this adapter was tested only against a small synthetic SQLite database (100% line coverage), and the schema was checked against the official database details page, not against a real SemMedDB dump. Run it against your own build before relying on it.

| | |
|---|---|
| Source | `KnowledgeSource.SEMMEDDB` |
| Class | `knowledge_lookup.adapters.SemMedDBAdapter` |
| Requires | a local database file: `SEMMEDDB_PATH` (or `api_keys={"semmeddb": "/path/file"}`, a file path rather than a secret) |
| Identifiers | UMLS CUI: `C0015674`, `UMLS:C0015674` |
| Upstream | [SemMedDB](https://lhncbc.nlm.nih.gov/ii/tools/SemRep_SemMedDB_SKR/SemMedDB_download.html) (NLM Lister Hill Center), no API |

`is_available()` is true only when the file exists, so `CentralKnowledgeLookup` skips the source on machines without the data and `knowledge-lookup check SEMMEDDB` reports it as skipped.

## Licence and data

SemMedDB is distributed as a MySQL dump by the NLM Lister Hill Center. Downloading it requires a (free) UMLS Metathesaurus licence; see the SemMedDB download page. The NLM announced that SemRep/SemMedDB tooling would no longer be maintained after December 2024, so the most recent release is likely the final one (the archived details page names `semmedVER30` as the latest; check the download page for the current name). The full PREDICATION table is very large (tens of millions of rows or more), so create the indexes in the recipe below before querying. SemRep output is machine-extracted: precision is far from perfect, and negated findings are encoded in the predicate (`NEG_TREATS`).

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

Option A, from the licensed MySQL dump, loading only `PREDICATION` into SQLite. Export from MySQL, then import (adjust the database name):

```bash
# 1. restore the PREDICATION dump into a MySQL/MariaDB instance, then export to TSV
mysql semmeddb -e "SELECT PREDICATION_ID, SENTENCE_ID, PMID, PREDICATE, SUBJECT_CUI, SUBJECT_NAME,
  SUBJECT_SEMTYPE, SUBJECT_NOVELTY, OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE, OBJECT_NOVELTY
  FROM PREDICATION" --batch --raw --skip-column-names > predication.tsv

# 2. load into SQLite
sqlite3 semmeddb.sqlite <<'SQL'
CREATE TABLE PREDICATION (
  PREDICATION_ID INTEGER, SENTENCE_ID INTEGER, PMID TEXT, PREDICATE TEXT,
  SUBJECT_CUI TEXT, SUBJECT_NAME TEXT, SUBJECT_SEMTYPE TEXT, SUBJECT_NOVELTY INTEGER,
  OBJECT_CUI TEXT,  OBJECT_NAME TEXT,  OBJECT_SEMTYPE TEXT,  OBJECT_NOVELTY INTEGER);
.mode tabs
.import predication.tsv PREDICATION
-- indexes: CUI lookups, relationship grouping, and case-insensitive name prefix search
CREATE INDEX idx_pred_subject_cui  ON PREDICATION (SUBJECT_CUI);
CREATE INDEX idx_pred_object_cui   ON PREDICATION (OBJECT_CUI);
CREATE INDEX idx_pred_subject_name ON PREDICATION (SUBJECT_NAME COLLATE NOCASE);
CREATE INDEX idx_pred_object_name  ON PREDICATION (OBJECT_NAME COLLATE NOCASE);
CREATE INDEX idx_pred_pmid         ON PREDICATION (PMID);
ANALYZE;
SQL
export SEMMEDDB_PATH=$PWD/semmeddb.sqlite
```

MySQL's `--batch --raw` writes NULL as the text `NULL`; only the two `*_NOVELTY` columns are normally affected and the adapter does not use them. The `COLLATE NOCASE` name indexes are what make prefix name search fast (`LIKE 'fatigue%'` becomes an index range scan). Substring search (`%fatigue%`) cannot use an index; see "Query behaviour".

Option B, point `SEMMEDDB_PATH` at a TSV or CSV export of `PREDICATION` (optionally `.gz`). On first use the adapter streams it into an indexed SQLite file under `$KNOWLEDGE_LOOKUP_DATA_DIR` (default `~/.cache/knowledge_lookup/datasets`) and reuses that file while the export is unchanged. A header row with column names is detected by the `PREDICATE` column; a file without a header must use the column order shown in the schema above. `\N` becomes NULL and rows with the wrong number of fields are skipped. This is convenient for small or filtered exports (a PubMed subset, say); for the full table, Option A is faster and more transparent. You can also call `knowledge_lookup.adapters.semmeddb_adapter.import_predication_export(src, dest)` directly.

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
- Name search matches by prefix first, which uses the `COLLATE NOCASE` indexes, then by substring when fewer than `limit` concepts were found. Substring search scans the table; set `adapter.allow_substring_search = False` on very large databases.
- Each query is aborted after `adapter.query_timeout` (60 s) so an accidental full scan cannot occupy a worker thread forever; the call then returns `[]`/`None` like any other error.
- `pmid_count` on a *concept* is summed over names and roles, so it can slightly over-count a PMID that supports a CUI in several roles; per-triple `pmid_count` in `get_relationships` is exact.

## See also

- [UMLS adapter](../core/umls_adapter.md) for CUI details, [PubTator adapter](pubtator_adapter.md), [Europe PMC adapter](europepmc_adapter.md)
- [All adapters](../README.md)
