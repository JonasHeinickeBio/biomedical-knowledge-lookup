---
description: Semantic Scholar papers, citations, references and TLDR summaries (keyless but heavily rate limited; optional API key).
---

# Semantic Scholar adapter

Searches the [Semantic Scholar Academic Graph](https://www.semanticscholar.org/product/api), an index of roughly 200 million papers across all fields. Beyond bibliographic metadata it provides a machine-generated one-sentence **TLDR**, an **influential citation** flag on every citation edge, fields of study and open-access PDF links, and resolves papers from DOI, PMID, PMCID, arXiv or its own ids. Useful for literature mining around ME/CFS and Long COVID where citation context matters.

| | |
|---|---|
| Source | `KnowledgeSource.SEMANTICSCHOLAR` |
| Class | `knowledge_lookup.adapters.SemanticScholarAdapter` |
| Requires | nothing; an optional API key (`SEMANTIC_SCHOLAR_API_KEY` or `config.api_keys["semanticscholar"]`) gives a dedicated rate limit |
| Identifiers | the 40-hex `paperId` (the concept id); also `DOI:10.1038/...` / bare DOI / `https://doi.org/...`, `PMID:36639608` (bare digits are read as a PMID), `PMC9839201` / `PMCID:9839201`, `ARXIV:2006.10256`, `CorpusId:255800506`, `MAG:`, `ACL:`, `DBLP:`, `URL:` |
| Upstream API | `https://api.semanticscholar.org/graph/v1` |
| Licence | governed by the Semantic Scholar API License Agreement (accepted when requesting a key) and Terms of Service; read them before redistributing data or using it commercially. Abstracts are withheld for papers whose publisher forbids redistribution |
| Concept type | `CITATION` |

## Keyless use and the 429 problem

The product page says keyless requests share one pool ("1000 requests per second shared among all unauthenticated users"). In practice this means that **many keyless requests are answered with HTTP 429 immediately**, whatever your own request rate. A key from the [request form](https://www.semanticscholar.org/product/api#api-key-form) has a dedicated pool with an introductory limit of **1 request per second on all endpoints**.

How the adapter copes:

- `is_available()` is always `True`, so the source is tried without a key.
- The key is read from `config.get_api_key("semanticscholar")` or the environment variable `SEMANTIC_SCHOLAR_API_KEY` and sent **only** as the `x-api-key` header (never in the URL or the logs).
- Requests are spaced at least one second apart per adapter instance, with or without a key.
- A 429 is retried at most twice, waiting for the `Retry-After` header when the server sends one (it did not in our probes) and otherwise 2 s, then 4 s, never more than 30 s. After that the call returns `[]` / `None` and logs `Semantic Scholar rate limit (HTTP 429) persists for '<path>' (keyless pool is shared; set SEMANTIC_SCHOLAR_API_KEY for a key)`.
- A 429 does not count as a failure of the source for the circuit breaker, and the base class' four-fold backoff is bypassed so the shared pool is not hammered.
- Unknown papers (HTTP 404, also returned for malformed ids such as `PMID:abc`) give `None`, not an error.

Callers that need reliable results should set a key; without one expect empty results at busy times and check the log.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import SemanticScholarAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with SemanticScholarAdapter(LookupConfig()) as adapter:
        for paper in await adapter.search_concepts("long covid", limit=3):
            print(paper.primary_id, paper.primary_label[:60])

        davis = await adapter.get_concept_details("DOI:10.1038/s41579-022-00846-2")
        data = davis.source_data["SEMANTICSCHOLAR"]
        print(data["citation_count"], data["influential_citation_count"], data["tldr"])

        for rel in await adapter.get_relationships("PMID:36639608", limit=5):
            print(rel["relation_label"], rel.get("is_influential"), rel["related_name"][:50])

        print([(m["toSource"], m["toId"]) for m in await adapter.get_mappings("PMID:36639608")])


asyncio.run(main())
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | relevance-ranked papers from `paper/search` (one request, at most 100). An identifier-shaped query (DOI, PMID, PMC, arXiv, `CorpusId:`...) resolves that paper first and falls back to text search if it is unknown |
| `get_concept_details(id)` | one paper in any of the identifier forms above |
| `get_relationships(id, limit=25)` | `cites` (references, `paper/{id}/references`) and `cited_by` (`paper/{id}/citations`); two requests, each direction capped at `limit` (max 100). Edges carry `is_influential` (when the API provides it), `year`, and `doi` / `pmid` when known |
| `get_mappings(id)` | external ids: `DOI`, `PMID`, `PMCID` (with the `PMC` prefix), `ArXiv`, `MAG`, `ACL`, `DBLP`, `CorpusId` |

### Concept fields

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `paperId` / title |
| `definitions` | the abstract (omitted when the API returns none) |
| `semantic_types` | publication types (`JournalArticle`, `Review`, ...) |
| `categories` | `year:`, `venue:`, `open_access`, `field:<field of study>` |
| `identifiers` | `EUROPEPMC` entries for `DOI:`, `PMID:` and `PMC...` ids with URLs |
| `source_data[SEMANTICSCHOLAR]` | `paperId`, `corpusId`, `year`, `venue`, `publication_date`, `publication_types`, `fields_of_study`, `authors` (names only), **`tldr`**, `citation_count`, `influential_citation_count`, `reference_count`, `is_open_access`, `open_access_pdf`, `external_ids`, `url` |

Paper edges are ordered the way the API returns them (not by importance). References without a Semantic Scholar record are skipped. The adapter requests a fixed field list and never fetches author profiles.

## Caveats

- `tldr` exists only for part of the corpus; `abstract` is null for some publishers; `citationCount` counts citations Semantic Scholar has indexed and differs from OpenAlex, Crossref and Google Scholar.
- `paper/search` is relevance ranked and returns at most 100 results per request here (the API allows paging up to 1,000 hits; not used).
- A bare number is read as a PMID in `get_concept_details` but searched as text in `search_concepts`.
- Duplicated versions of a paper (preprint, journal version) are separate records with different `paperId`s.

## Live verification (2026-10-08)

Probed keyless with polite spacing (4 to 20 s between requests). **About two thirds of the other requests (15 of 23) were answered with HTTP 429** (the body says "apply for a key for higher rate limits"), with no `Retry-After` header; the answers that did come back were quick (0.3 to 1.5 s):

| Call | Result |
|---|---|
| `paper/DOI:10.1038/s41579-022-00846-2` with the full field list | 200, 3.3 KB: title, abstract, TLDR, 3,472 citations (166 influential), 223 references, open-access PDF |
| `.../references?limit=5`, `.../citations?limit=5` | 200, 2.5 KB and 1.6 KB; `isInfluential` present on every row; references carry a top-level `citingPaperInfo` block (a copy of the paper) that the adapter ignores |
| `paper/PMCID:9839201` (digits only, no `PMC` prefix) | 200 |
| `paper/ARXIV:2006.10256`, `paper/CorpusId:219792763` | 200 |
| `paper/DOI:10.9999/doesnotexist`, `paper/PMID:abc` | 404 `{"error": "Paper with id ... not found"}` |
| `paper/search?query=long covid&fields=...` | **429 on all 17 attempts over about an hour (spacing 4 s to 2.5 min): the search endpoint could not be verified live**; its parsing is covered only by a fixture built from the documented response shape (`total`, `offset`, `next`, `data`) |
| `python -m knowledge_lookup check SEMANTICSCHOLAR` | search degraded to `[]` after the bounded backoff (6.8 s) and the check reports FAIL, as expected under 429; an end-to-end run of the adapter's `get_concept_details`, `get_relationships` and `get_mappings` against the real API succeeded (details with TLDR, 5 references and 5 citations, DOI/PMID/PMCID/CorpusId mappings), the first 429s being absorbed by the bounded retry |

The endpoints that did answer are covered by trimmed real responses in the unit tests; rerun the check with a key (`SEMANTIC_SCHOLAR_API_KEY=... python -m knowledge_lookup check SEMANTICSCHOLAR`) to confirm search.

## Rate limits and errors

Uses the shared circuit breaker for outages (HTTP 5xx, network errors; see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); rate limiting is handled as described above. Errors are logged; search returns `[]` and details return `None`.

## See also

- [OpenAlex adapter](openalex_adapter.md), [Europe PMC adapter](europepmc_adapter.md), [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
