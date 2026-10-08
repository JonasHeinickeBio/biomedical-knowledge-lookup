---
description: bioRxiv and medRxiv preprints (many Long COVID papers appear here first); preprints are not peer reviewed.
---

# bioRxiv / medRxiv adapter

Looks up preprints on [bioRxiv](https://www.biorxiv.org/) and [medRxiv](https://www.medrxiv.org/) by DOI, finds the journal version of a published preprint, lists earlier versions, and searches preprints by free text. medRxiv is where many Long COVID and ME/CFS papers first appear, often months before the journal version.

> **Preprints are not peer reviewed.** Findings are preliminary and may change or be withdrawn. Every concept carries the category `not_peer_reviewed` and `source_data["BIORXIV"]["peer_reviewed"] = False` with a notice; check `is_preprint_of` for the journal version before citing.

| | |
|---|---|
| Source | `KnowledgeSource.BIORXIV` |
| Class | `knowledge_lookup.adapters.BioRxivAdapter` |
| Requires | none (keyless, JSON) |
| Identifiers | preprint DOIs: `10.1101/2020.01.22.914952`, with a version (`...914952v2`), as `doi:` / `https://doi.org/` or as a biorxiv.org / medrxiv.org URL. Since 2026 medRxiv mints `10.64898/...` DOIs (e.g. `10.64898/2026.09.22.26363331`); no prefix is assumed |
| Upstream API | `https://api.biorxiv.org` (details, pubs); search through `https://www.ebi.ac.uk/europepmc/webservices/rest/search` |
| Licence | each preprint carries its author-chosen licence in `source_data["BIORXIV"]["license"]` (`cc_by`, `cc0`, `cc_by_nc`, ... or `cc_no` = all rights reserved). The API itself states no terms; the adapter stays below 3 requests per second |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import BioRxivAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with BioRxivAdapter(LookupConfig()) as adapter:
        # newest medRxiv preprints on ME/CFS (Europe PMC index, abstracts included)
        for p in await adapter.search_preprints("ME/CFS", limit=3, server="medrxiv", sort="date"):
            print(p.primary_id, p.primary_label[:60])

        preprint = await adapter.get_concept_details("10.1101/2020.01.22.914952")
        print(preprint.source_data["BIORXIV"]["peer_reviewed"], preprint.source_data["BIORXIV"]["versions"])
        for rel in await adapter.get_relationships("10.1101/2020.01.22.914952"):
            print(rel["relation_label"], rel["related_id"], rel["related_name"][:30])


asyncio.run(main())
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | preprints (CITATION) matching free text, at most 100; a DOI or biorxiv.org / medrxiv.org URL resolves to that preprint |
| `search_preprints(query, limit, server, sort, start, end, category)` | the search itself (see "Search" below) |
| `get_concept_details(doi)` | latest version (or the version in `...v2`) with title, authors, corresponding author and institution, category, date, licence, abstract (as the definition), `versions` list, `published_doi`, JATS XML URL and web URL |
| `get_relationships(doi)` | `is_preprint_of` (journal DOI as `related_id`, journal name as `related_name`, `published_date`, and `related_pmid` when Europe PMC links the article) and one `has_earlier_version` edge per older version (`<doi>v1`, with `version_date`) |
| `get_mappings(doi)` | the preprint DOI (`DOI`, exact), the journal DOI (`DOI`, `published_version`) and the journal article's PMID (`PubMed`, `published_version`) when Europe PMC links it |

`primary_id` is the DOI, `concept_type` `CITATION`, `categories` has `preprint`, `not_peer_reviewed`, `server:`, `category:` (e.g. `infectious diseases`), `year:` and `published_in_journal` when a journal version exists. The API exposes **no PMID for the preprint itself**; the PMID in the mappings is that of the published article.

## Search: there is no free-text search in the bioRxiv API

The API only lists by DOI or by date window (`details/{server}/{start}/{end}/{cursor}`, 30 rows per page). The adapter therefore searches through Europe PMC's keyless REST API, which indexes every bioRxiv and medRxiv preprint as source `PPR`: the query is `(<text>) AND SRC:PPR AND (PUBLISHER:"bioRxiv" OR PUBLISHER:"medRxiv")` with `resultType=core`. This gives relevance ranking, abstracts, `sort="date"` for newest first and full Europe PMC query syntax (quotes, `AND`/`OR`, `AUTH:`), in 0.3 s. Results are marked `from_search_index` in `source_data`; call `get_concept_details` for versions, licence and the published DOI.

Fallback and explicit windows: if Europe PMC is unreachable, or when `start` / `end` (`YYYY-MM-DD`) is passed, the adapter scans the bioRxiv API's date window and keeps rows whose title, abstract or category contain **every** query word (case-insensitive). The default fallback window is the last 7 days; one scan fetches at most 10 pages of 30 rows per server (`SCAN_MAX_PAGES`), so it sees at most 300 preprints per server and is meant for "what is new" questions, not exhaustive search. `category="infectious_diseases"` is applied server side and shrinks the window a lot. Volume measured on 2025-09-01 to 2025-09-03: medRxiv 189 rows in 3 days, bioRxiv 413 rows in 2 days, so a 7-day window is about 10 to 25 pages per server.

## Quirks learned live

- **A first probe of a medRxiv date interval returned HTTP 500; that was transient, not a changed path.** The same URLs later returned 200 (and failed again on other attempts): `details/medrxiv/2025-09-01/2025-09-03/<cursor>` failed on cursors 130, 188, 189 and 200 in one pass and on 0, 60, 100, 130, 189 and 200 in the next, while the others succeeded. A cursor beyond `total` is always a 500. The shared retry absorbs the transient cases; the scan stops at `total`.
- A few records fail consistently on `details/{server}/{doi}` (e.g. `10.1101/2021.01.27.21250617` returned 500 on four attempts) while `pubs/{server}/{doi}` for the same DOI works. The adapter then builds a **partial** concept from `pubs` (`source_data["BIORXIV"]["partial"] = True`, no version list).
- **Page size is 30**, although the documentation says 100. The cursor is a row offset.
- The documented "last N posts" and "last N days" forms (`details/medrxiv/10/0`, `details/medrxiv/2d/0`, with or without `/json`) answer `Both dates must be in yyyy-mm-dd format` and are not used. `pubs/{server}/{start}/{end}/{cursor}` also returned 500 for a month window; `publisher/{prefix}/{start}/{end}/{cursor}` works (59 rows for `10.1038`, 2025-09-01 to 2025-09-10) but is not wrapped.
- `details/{server}/{doi}` returns one row per version, oldest first, and `published` is `"NA"` for unpublished preprints. A DOI asked of the wrong server gives `{"status": "no posts found"}` with HTTP 200, so the adapter tries medRxiv first for 8-digit medRxiv numbering and bioRxiv first otherwise, and falls through to the other server.
- `type` is usually "new results"/"confirmatory results" but newer rows show `PUBLISHAHEADOFPRINT`; it is passed through unchanged. Titles from Europe PMC contain HTML (`<i>`), which is stripped.
- Not wrapped: PDF/XML full texts (`jatsxml` URL is returned), usage statistics, funder endpoints.

## Rate limits, latency and errors

No limit is documented. Requests are serialised and spaced by at least 0.35 s (under 3 per second), with the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; searches return `[]` and detail calls return `None`.

## Live verification (2026-10-08)

| Call | Latency | Response |
|---|---|---|
| `details/biorxiv/10.1101/2020.01.22.914952` | 0.4 s | 4.6 KB, 2 versions, `published` 10.1038/s41586-020-2012-7 |
| `pubs/biorxiv/10.1101/2020.01.22.914952` | 0.35 s | 2.3 KB, journal "Nature", published 2020-02-03 |
| `details/medrxiv/10.64898/2026.09.22.26363331` | 0.4 s | 5 KB, `published: "NA"`, licence `cc0` |
| `details/medrxiv/2025-09-01/2025-09-03/0` | 0.85 to 1.25 s | 80 KB, 30 rows of 189 |
| Europe PMC `"long covid" AND SRC:PPR AND PUBLISHER:medRxiv` | 0.3 s | 1,169 hits (1,451 with bioRxiv) |
| `knowledge-lookup check BIORXIV` | | PASS |

## See also

- [Crossref adapter](crossref_adapter.md) (its `has_preprint` / `is_preprint_of` relations), [Europe PMC adapter](europepmc_adapter.md) for full-text search, [LitCovid adapter](litcovid_adapter.md) for curated COVID-19 literature
- [All adapters](../README.md)
