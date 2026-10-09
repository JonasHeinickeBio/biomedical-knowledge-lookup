---
description: OpenAIRE research graph: publications, datasets, software and projects with funders, organisations, repositories and open-access/licence fields (keyless; optional access token).
---

# OpenAIRE Graph adapter

Looks up research products and funded projects in the [OpenAIRE Graph](https://graph.openaire.eu), a European open graph that links publications, datasets and software to the projects that funded them, the organisations behind them and the repositories or journals that host them. Use it to answer "who funded this paper, under which grant?", "is there an open copy, and under which licence?", "which datasets and software came out of this project?".

| | |
|---|---|
| Source | `KnowledgeSource.OPENAIRE` |
| Class | `knowledge_lookup.adapters.OpenAIREAdapter` |
| Requires | none. Optional `OPENAIRE_ACCESS_TOKEN` (personal access token, sent only as `Authorization: Bearer`) |
| Identifiers | products: OpenAIRE id (`doi_dedup___::3e70f14256ea2d001e1c0b0d23f65ad1`, also `50\|...`, `openaire:...`, explore URLs), DOI (`10.1038/s41579-022-00846-2`, `doi:`, `https://doi.org/...`), `PMID:36639608`, `PMC9839201`, `arXiv:2003.06265`; projects: `project:sfi_________::4f8b833f348de3405b0a868063f9db50` |
| Upstream API | `https://api.openaire.eu/graph/v3` (machine-readable spec: `/graph/v3/api-docs`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OpenAIREAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OpenAIREAdapter(LookupConfig()) as adapter:
        paper = await adapter.get_concept_details("10.1038/s41593-024-01576-9")
        oa = paper.source_data["OPENAIRE"]["open_access"]
        print(paper.primary_id, oa["best_access_right"], oa["color"], oa["licenses"])

        for edge in await adapter.get_relationships(paper.primary_id, limit=5):
            if edge["relation_label"] in ("funded_by", "hosted_by"):
                print(edge["relation_label"], edge["related_name"][:50], edge.get("grant_code"), edge.get("license"))

        for dataset in await adapter.search_concepts("long covid", limit=3, product_type="dataset"):
            print(dataset.primary_id, dataset.primary_label[:60])


asyncio.run(main())
```

## Methods

| Method | What it does |
|---|---|
| `search_concepts(query, limit=20, product_type=None)` | Full-text search over research products (title and abstract). Without `product_type`, up to 3 projects are appended (when `limit >= 6`). A DOI, PMID, PMC, arXiv or OpenAIRE id as the query resolves to that record. |
| `search_products(query, limit, product_type, open_access_only, from_year)` | Products only. `product_type` is `publication`, `dataset`, `software` or `other`; `open_access_only` sets `accessRightLabel="Open Access"`; `from_year` sets `fromPublicationYear`. |
| `search_projects(query, limit=10)` | Projects by title, keywords and summary. |
| `get_concept_details(id)` | A product by OpenAIRE id or persistent id, or a project (`project:<id>`). A bare OpenAIRE id is tried as a product first, then as a project (the two id shapes are identical). |
| `get_relationships(id, limit=25)` | See below. `limit` caps each group. |
| `get_mappings(id)` | Product -> `DOI`, `PMID`, `PMCID`, `ARXIV`, `HANDLE` (and any other scheme in upper case), taken from the record and from the ids of its individual copies. Projects have none in the v3 API (`[]`). |
| `get_project_outputs(project_id, limit=25)` | The products produced by a project (`relProjectId`) as concepts. |

All methods return `[]` / `None` on errors, unknown ids and empty queries.

## What the concepts contain

Products have type `CITATION` (publications) or `REFERENCE` (datasets, software, other). `definitions` hold the first abstract (HTML stripped, capped at 4,000 characters), `synonyms` the keyword subjects and other titles, `categories` `year:`, `journal:`, `access:` and `oa:` entries, and `identifiers` the DOI / PMID / PMC id (as `EUROPEPMC` identifiers so concepts merge with other literature sources). `source_data["OPENAIRE"]` carries:

- `open_access`: `best_access_right` (+ `_code`), `color`, `is_green`, `is_in_diamond_journal`, `publicly_funded`, `embargo_end_date`, `licenses`
- `instances`: up to 10 individual copies, each with `type`, `license`, `access_right`, `open_access_route`, `refereed`, `urls`, `hosted_by`, `collected_from`
- `projects`, `organizations`, `collected_from`, `communities`, `authors` (first 10, with ORCID), `citation_count` / `citation_class` (OpenAIRE's own indicators), `pids`, `url` (OpenAIRE Explore)

Projects have type `UNKNOWN`, id `project:<OpenAIRE id>`, and `source_data` with `code` (grant id), `acronym`, `call`, `funder`, `funding_stream`, start and end date, `funded_amount` / `currency`, and the open-access mandate flags.

### Open access and licences: what the fields do and do not say

The adapter reports the fields as OpenAIRE returns them and infers nothing:

- `best_access_right` is the best right among **all** copies of the product (`OPEN`, `CLOSED`, `EMBARGO`, `RESTRICTED`, ...). `OPEN` means some copy is open, not that the publisher version is.
- `color` (`gold`, `hybrid`, `bronze`, ...) is `null` for most records; `is_green` says only that a repository copy was found.
- `license` exists **per copy** (`instances[].license`) and is frequently absent even for open copies. An absent licence is reported as `None`, never as "all rights reserved" or "open". Do not read `CC BY` on a repository copy as the licence of the publisher version.
- The same work usually appears as several `instances` (publisher, PubMed Central, repository, preprint); `hosted_by` edges list each data source with the licence and access right of its copy.

## Relationships

For products:

| `relation_label` | `related_id` | Notes |
|---|---|---|
| `funded_by` | `project:<id>` | `funder`, `grant_code`, `acronym`, `funding_stream` (level 0/1/2 path), `trust` of the link. Funder-only links without a grant record are named `<funder> (unidentified project)`. |
| `affiliated_with` | OpenAIRE organisation id | `ror`, `country` |
| `hosted_by` | data source id | repository or journal holding a copy, with that copy's `license`, `access_right`, `urls` |
| `collected_from` | data source id | sources the record was harvested from (Crossref, Europe PMC, ...) |
| `cites`, `is_supplemented_by`, `is_related_to`, ... | OpenAIRE product id | Scholix links (`research-products/links?sourcePid=`), only for products with a DOI; relation names are OpenAIRE's, converted to snake case; `provenance` lists who asserted the link, `total_links` the full count |

For projects: `funded_by` (the funder, with `jurisdiction`), `has_participant` (organisations, with `ror`) and `has_output` (products, `total_outputs` is the full count).

## Rate limits, licence and terms

- **Documented limits** ([terms of use](https://graph.openaire.eu/docs/apis/terms/)): 60 requests per hour anonymous, 7,200 per hour with a personal access token (sliding one-hour window). **Measured 2026-10-09**: the response headers `x-ratelimit-limit: 7199` / `x-ratelimit-used` count every call, and 77 calls in one session were never refused, i.e. the documented anonymous limit of 60 per hour is not enforced right now. The adapter does not rely on that: it spaces requests by 1 s (at most 3,600 per hour, below even the authenticated limit). If OpenAIRE starts enforcing the anonymous limit you will see HTTP 429 and empty results; set `OPENAIRE_ACCESS_TOKEN` then.
- A token is read from the environment variable only and sent as `Authorization: Bearer ...`. Tokens expire after one hour (renewal with a refresh token is not implemented); an expired token gives errors, so unset it rather than leave a stale one.
- Data licence: records are **CC-BY 4.0**; credit OpenAIRE as the data source when you reuse them. The API is free for third-party services.
- `pageSize` is capped at 100 (400 above), page-based paging stops at 10,000 records.

## Why v3 and not v1

The task brief named `/graph/v1`. v1 and v2 answer HTTP 200 but are marked deprecated in the live OpenAPI description, and v1 lacks the `projects`, `organizations`, `links` and `collectedFrom` blocks that funding relationships need. v3 is the current stable version (v4 is a beta with a different filter grammar). Parameter names differ from the brief: v3 uses `search`, `pid`, `type`, `fromPublicationYear`, `accessRightLabel`, `relProjectId`, `pageSize`, `cursor` (cursor paging is not used).

## Live verification (2026-10-09)

- `knowledge-lookup check OPENAIRE`: PASS (search 5 results 0.55 s, details, relationships 2.1 s incl. the Scholix call and spacing).
- Measured: product by `pid` 0.13-0.25 s (about 9-15 KB); search `pageSize=20` 0.47 s (133 KB), `pageSize=100` 0.79 s (783 KB); Scholix links 0.2-0.4 s. 111,488 products match "long covid"; 3,240 of them are datasets.
- Verified on real responses: the `pid` filter works for DOI (case-insensitive), PMID, PMC id and arXiv number; unknown product ids answer 404, an unmatched `pid` answers 200 with `results: []`; `isPubliclyFunded`, `type` and `relProjectId` really filter.
- Project records carry no persistent ids, so `get_mappings` is empty for projects.
- Not covered: persons (`/persons` exists in v3 but is out of scope), `cursor` paging, v4.

## See also

- [OpenAlex adapter](openalex_adapter.md), [Crossref adapter](crossref_adapter.md), [Unpaywall adapter](unpaywall_adapter.md), [DOAJ adapter](doaj_adapter.md)
- [All adapters](../README.md)
