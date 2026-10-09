---
description: DOAJ, the Directory of Open Access Journals: vetted open-access journals (licence, APC, peer review, subjects) and their articles (keyless, CC0 metadata).
---

# DOAJ adapter

Looks up journals and articles in the [Directory of Open Access Journals](https://doaj.org). The typical use is vetting a cited journal: is it a fully open access title that DOAJ reviewed, what licence does it use, does it charge an APC, which peer review does it declare, what are its ISSNs?

| | |
|---|---|
| Source | `KnowledgeSource.DOAJ` |
| Class | `knowledge_lookup.adapters.DOAJAdapter` |
| Requires | none (keyless) |
| Identifiers | journals `journal:<32-hex DOAJ id>` or `https://doaj.org/toc/<id>`, ISSN (`1932-6203`, `ISSN:`, `eISSN:`); articles `article:<id>` or `https://doaj.org/article/<id>`, DOI (`10.1371/journal.pone.0326790`, `doi:`, `https://doi.org/...`); a bare 32-hex id is tried as journal, then as article |
| Upstream API | `https://doaj.org/api/v4` (spec: `/api/v4/swagger.json`, docs: `/api/v4/docs`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DOAJAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with DOAJAdapter(LookupConfig()) as adapter:
        journal = await adapter.get_concept_details("1932-6203")  # ISSN -> journal
        data = journal.source_data["DOAJ"]
        print(journal.primary_label, data["licenses"][0]["type"], data["apc"], data["peer_review"])

        for edge in await adapter.get_relationships("10.1371/journal.pone.0326790"):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])

        print(await adapter.get_mappings(journal.primary_id))
        for article in await adapter.search_articles("long covid fatigue", limit=3):
            print(article.primary_id, article.primary_label[:60])


asyncio.run(main())
```

## Methods

| Method | What it does |
|---|---|
| `search_concepts(query, limit=20)` | Journals first (about a quarter of `limit`, at least one), then articles; two requests. An ISSN or DOI as the query resolves to that journal or article. |
| `search_journals(query, limit)` / `search_articles(query, limit)` | One kind only. `limit` <= 100. |
| `get_concept_details(id)` | Journal or article (see Identifiers). |
| `get_relationships(id, limit=25)` | Journal: `has_subject` (Library of Congress subject, `LCC:<code>`), `has_license` (`related_id` is the licence type such as `CC BY-NC-SA`, with `attribution` / `non_commercial` / `no_derivatives` / `share_alike` flags and URL), `published_by` (publisher, with country). Article: `published_in` (`journal:<DOAJ id>` when the article's ISSN resolves to a journal still in DOAJ, otherwise `ISSN:<issn>` with `journal_in_doaj=False`) and `has_subject`. `limit` caps subjects and licences. |
| `get_mappings(id)` | Journal -> `ISSN` (print) and `EISSN`; article -> `DOI` and its journal's `ISSN`s. |

All methods return `[]` / `None` on errors, unknown ids and empty queries.

## What the concepts contain

Journals have type `UNKNOWN` (there is no journal concept type), id `journal:<DOAJ id>`, `synonyms` = alternative title and keywords, `categories` = `subject:`, `license:` and `apc:yes|no`. `source_data["DOAJ"]` holds: `pissn`, `eissn`, `publisher` (+ country), `institution`, `languages`, `subjects` (LCC code and term), `licenses` (type, URL, BY/NC/ND/SA flags), `apc` (`has_apc`, `max` list of `{price, currency}`, URL), `other_charges`, `waiver`, `peer_review` (DOAJ's wording, e.g. `Single anonymous peer review`), `publication_time_weeks`, `oa_start`, `boai`, `author_retains_copyright`, `plagiarism_detection`, `preservation`, `pid_scheme`, `ticked`, `seal`, `in_doaj`, `last_updated`.

Articles have type `CITATION`, id `article:<DOAJ id>`, the abstract as definition, and `source_data["DOAJ"]` with DOI, year, journal, ISSNs, volume/pages, first 10 authors (with ORCID when given), keywords, LCC subjects and full-text URLs.

### What DOAJ inclusion does and does not mean

- **Does mean:** the journal is fully open access (no subscription, no hybrid) and passed DOAJ's editorial review against its published inclusion criteria, which cover open access statements, licensing, transparent editorial and peer-review information, and fee disclosure. DOAJ publishes the journal's own declarations (APC, licence, review type); they are the journal's claims as checked by DOAJ at review time.
- **Does not mean:** a quality or impact ranking, a guarantee of rigorous peer review in practice, or that a given article was reviewed. DOAJ also removes titles that stop meeting the criteria (`in_doaj` reflects the lookup moment).
- **Absence does not mean predatory.** Subscription and hybrid journals (e.g. *Nature Reviews Microbiology*, ISSN 1740-1526: 0 hits) are out of scope, as are journals that never applied. An article can be open access elsewhere (see [Unpaywall](unpaywall_adapter.md), [OpenAIRE](openaire_adapter.md)).
- The old DOAJ **Seal** is not exposed by the public API (`admin.seal:true` matches nothing), so `seal` is always `None`. `ticked` is DOAJ's internal review flag, passed through unchanged; DOAJ does not explain it in the API documentation, so no meaning is attached to it here.

## Query grammar (learned live, the docs only say "Elasticsearch query string")

- The query is a **path segment**, not a parameter (`/search/journals/<query>`); the adapter URL-encodes it.
- Several words are **AND-ed over every indexed field**. "long covid" matches 22,601 articles but **0 journals**; "chronic fatigue syndrome" matches 0 journals. An empty journal list means "no journal mentions all these words", not an error. `long OR covid` would give 46 journals (any mention), mostly noise, so the adapter never rewrites a query.
- Field syntax works: `title:medicine` (539 journals), `bibjson.title:"lancet"` (12), `issn:1897-4252` (print or electronic ISSN), `publisher:dove`, `license:CC-BY`; for articles `doi:10.1371/journal.pone.0326790`, `abstract:...`, `title:...`. `eissn:` is not a shorthand. `AND`/`OR`/`NOT` must be upper case.
- **`doi:` matching is case-sensitive** against the DOI as the publisher registered it (`10.7554/eLife.40553`); the adapter tries the spelling you give, then the lower-case form. Wildcards are rejected (HTTP 400, immediately).
- **A malformed query (unbalanced quote or parenthesis, trailing `AND`, leading `(`) makes the server wait about 27 seconds before answering HTTP 400.** Measured three times (27.5, 28.2, 27.5 s). `sanitize_query()` therefore passes through only well-formed structured queries and otherwise replaces every reserved character with a space, so `COVID-19: long (review` is sent as `COVID 19 long review`. Use field syntax deliberately, with balanced quotes.
- `pageSize` above 100 is silently capped; the hit count is in the `x-total-count` header and the `total` field.

## Rate limit, licence and terms

- Documented: **two requests per second** on every route, bursts of up to five queued requests are served if they average two per second. The adapter spaces requests by 0.6 s.
- Journal and article **metadata is CC0** ([terms](https://doaj.org/terms/)). No attribution is required; the DOAJ name, logo and site design are not covered by the waiver.
- The API is read-only here; no key is used. DOAJ also publishes a full data dump (not used).

## Live verification (2026-10-09)

- `knowledge-lookup check DOAJ`: PASS (search 5 results 0.74 s, details, 4 relationship edges 0.6 s).
- Measured latency: searches 0.13-0.30 s (journal page of 3: 7 KB; 100 articles: 415 KB, 0.29 s); single records 0.2 s (about 3 KB). `title:"PLoS ONE"` 0.64 s, ISSN lookup 1.0 s on a cold call.
- Index size on that day (`*` query): 23,580 journals and 13,768,272 articles.
- Verified on real responses: ISSN and DOI resolution, journal -> subjects/licence/publisher edges, article -> journal resolution through the ISSN, 404 for unknown ids.
- Not verified: authenticated endpoints (applications, bulk article upload) are out of scope.

## See also

- [Unpaywall adapter](unpaywall_adapter.md), [OpenAIRE adapter](openaire_adapter.md), [Crossref adapter](crossref_adapter.md)
- [All adapters](../README.md)
