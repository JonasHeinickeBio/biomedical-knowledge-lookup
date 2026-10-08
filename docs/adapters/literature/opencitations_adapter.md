---
description: OpenCitations open citation links between DOIs (CC0) with citation dates, timespans and self-citation flags.
---

# OpenCitations adapter

Reads the [OpenCitations](https://opencitations.net/) Index, the open (CC0) graph of citations between scholarly works. For a DOI it returns which works it cites and which works cite it, each with the citation's creation date, the time between the two papers and journal / author self-citation flags, plus citation and reference counts. Bibliographic metadata and cross-identifiers (PMID, OMID, OpenAlex id, ISSN) come from OpenCitations Meta.

| | |
|---|---|
| Source | `KnowledgeSource.OPENCITATIONS` |
| Class | `knowledge_lookup.adapters.OpenCitationsAdapter` |
| Requires | none (keyless, JSON); optional access token `OPENCITATIONS_ACCESS_TOKEN` |
| Identifiers | DOIs `10.1038/s41586-020-2012-7` (also `doi:` and `https://doi.org/`), `pmid:32015507` (bare digits count as a PMID), `omid:br/06130344922` |
| Upstream API | `https://api.opencitations.net/index/v2` (citations) and `https://api.opencitations.net/meta/v1` (metadata) |
| Licence | citation data and metadata are open under CC0 (public domain); the API documentation is CC BY 4.0 |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OpenCitationsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OpenCitationsAdapter(LookupConfig()) as adapter:
        work = await adapter.get_concept_details("10.1038/s41586-020-2012-7")
        data = work.source_data["OPENCITATIONS"]
        print(work.primary_label[:50], data["citation_count"], data["reference_count"])

        refs = await adapter.get_references("doi:10.1038/s41586-020-2012-7", limit=2)
        for r in refs:
            print(r["relation_label"], r["related_id"], r["creation"], r["timespan"])

        for m in await adapter.get_mappings("pmid:32015507"):
            print(m["toSource"], m["toId"])


asyncio.run(main())
```

Output (recorded 2026-10-08; the first call took about 15 s on a cold server cache):

```
A Pneumonia Outbreak Associated With A New Coronavirus 19265 14
cites 10.1038/nature12711 2020-02-03 P6Y3M4D
cites 10.1073/pnas.1517719113 2020-02-03 P3Y10M20D
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | the work for an identifier (DOI, `pmid:`, `omid:`). **There is no text search**: any other query returns `[]` |
| `get_concept_details(id)` | work (CITATION) from Meta (title, authors, date, venue, ISSN, volume/issue/page, type, publisher) plus `citation_count` and `reference_count` (3 requests). `primary_id` is the DOI when OpenCitations knows one |
| `get_relationships(id)` | `cites` (works this one references) and `cited_by` (works that cite it), up to 100 each, newest first |
| `get_references(id, limit)` / `get_citations(id, limit)` | the two directions on their own |
| `get_mappings(id)` | DOI, `PubMed` (PMID), `OPENALEX`, `OMID` (and `PMC`) ids from Meta, plus the venue's ISSNs (`container_id`); the queried id itself is not repeated |

Relationship dicts have the standard keys plus `oci` (the citation's identifier), `creation` (date of the citing paper, `2026-10` or `2020-02-03`), `timespan` (ISO 8601 duration such as `P6Y3M4D`) and `timespan_years` (approximate), `journal_self_citation` / `author_self_citation` (booleans from `journal_sc` / `author_sc`) and `other_ids` (every identifier the index holds for the other work). `related_name` repeats the id because the index stores no titles; resolve titles with [Crossref](crossref_adapter.md) or [OpenAlex](openalex_adapter.md).

## Citation data are open, but the index lags

- Citations come from DOI-to-DOI links deposited in Crossref, DataCite, PubMed and similar open sources. References without a DOI and very recent papers are missing, so counts are **lower bounds** (the first SARS-CoV-2 bat-origin paper has 19,265 citations here; the newest citing paper in the 2026-10 listing was dated `2026-10`). Do not mix these counts with Google Scholar, Dimensions or OpenAlex numbers.
- `creation` is the citing paper's date and has varying precision (`2026`, `2026-10`, `2026-03-09`).

## Quirks learned live

- The old base `https://opencitations.net/index/api/v2/...` answers **HTTP 301** to `https://api.opencitations.net/index/v2/...`; the adapter uses the new base directly.
- **Cold-cache requests are slow**: `citation-count` for the 19k-citation paper took 9 to 13 s (pmid or doi form), a filtered `citations` call 11 to 13 s, while `reference-count`, `references` and Meta took 0.4 to 1.4 s. The request timeout floor is therefore 120 s and `get_concept_details` of a famous paper can take 15 s.
- **There is no paging or `limit`.** `citations`/`references` return the complete set (19,265 rows is about 8 MB). RAMOSE's `sort=desc(creation)`, `filter=creation:>2024` (string comparison) and `require=<field>` work. For works with more than 3,000 citations the adapter therefore only requests citations created after December of the year before last (`creation:>YYYY-12`, i.e. roughly since January of last year; for reference, `creation:>2024` returned 1,919 rows, 700 KB), then keeps the newest 100. For other works the whole list is fetched and the newest 100 kept.
- Unknown ids are HTTP 200 with `[]` (not 404); counts of a missing id are `"0"`.
- Meta accepts doi, pmid, omid, issn, isbn and openalex ids (the docs text lists fewer than the id regex accepts).
- Not wrapped: `venue-citation-count`, Meta's `author` and `editor` routes, `citation/{oci}` (rows already carry all its fields).

## Access token, rate limits and errors

The documented limit is 180 requests per minute per IP address without a token. Requests are serialised and spaced by at least 0.4 s (2.5 per second). OpenCitations recommends an access token for application use: set `OPENCITATIONS_ACCESS_TOKEN` (or the `opencitations` entry of the config's API keys) and it is sent in the `authorization` header, only when set. Shared retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; relationships and mappings return `[]`, details return `None`.

## Live verification (2026-10-08)

| Call | Latency | Response |
|---|---|---|
| `meta/v1/metadata/doi:10.1038/s41586-020-2012-7` | 1.1 to 1.4 s | 1.7 KB, ids `doi pmid omid openalex`, venue with 5 ISSNs |
| `index/v2/citation-count/...` | 9 to 13 s cold | `[{"count": "19265"}]` |
| `index/v2/reference-count/...` | 0.4 s | `[{"count": "14"}]` |
| `index/v2/references/...` | 0.6 s | 14 rows, 5.4 KB |
| `index/v2/citations/...?filter=creation:>2024&sort=desc(creation)` | 11 s | 1,919 rows, 700 KB |
| `knowledge-lookup check OPENCITATIONS` | | PASS (details 14.7 s, relationships 5.8 s) |

## See also

- [Crossref adapter](crossref_adapter.md) (reference lists, retractions), [OpenAlex adapter](openalex_adapter.md) (broader citation counts), [bioRxiv / medRxiv adapter](biorxiv_adapter.md)
- [All adapters](../README.md)
