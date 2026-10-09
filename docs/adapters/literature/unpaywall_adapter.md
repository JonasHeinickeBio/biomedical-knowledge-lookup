---
description: Unpaywall open-access status and free full-text locations for DOIs (needs a contact e-mail you choose in UNPAYWALL_EMAIL; not live-verified).
---

# Unpaywall adapter

Asks [Unpaywall](https://unpaywall.org) whether a free, legal full-text copy of a DOI exists, and where: open access status (`gold`, `hybrid`, `bronze`, `green`, `closed`), the best copy, every other copy found, each with its version, licence and host (publisher or repository).

> **Status: implemented from the documentation, NOT live-verified.** Unpaywall refuses every request without an `email` parameter (HTTP 422, verified 2026-10-09 for the DOI and the search endpoint), and that address has to be a contact address *you* choose. It was deliberately not invented or borrowed while this adapter was written, so response parsing follows the documented schema and is covered by synthetic fixtures, not by a captured response. Run the live check yourself (below) and report differences.

| | |
|---|---|
| Source | `KnowledgeSource.UNPAYWALL` |
| Class | `knowledge_lookup.adapters.UnpaywallAdapter` |
| Requires | **`UNPAYWALL_EMAIL`**: your own contact e-mail address. Without it `is_available()` is `False`, no request is made and `knowledge-lookup check UNPAYWALL` reports "skipped" |
| Identifiers | DOIs only: `10.1038/s41586-020-2012-7`, `doi:...`, `https://doi.org/...` (case-insensitive) |
| Upstream API | `https://api.unpaywall.org/v2` |

## Set-up and live check

```bash
export UNPAYWALL_EMAIL="you@your-institution.org"   # an address you are happy to give Unpaywall
knowledge-lookup check UNPAYWALL                     # search -> details -> relationships against the live API
knowledge-lookup check UNPAYWALL --id 10.1038/s41586-020-2012-7
```

How the address is handled:

- Read **only** from `UNPAYWALL_EMAIL` (a `.env` file works), with `UNPAYWALL_API_KEY` / the `api_keys` setting under the name `unpaywall` as a fallback. It is never defaulted and never taken from git, system or application settings. An invalid-looking value (no `@`, spaces) counts as unset.
- It is sent **only** as the `email` query parameter of Unpaywall requests, as the API requires. Unpaywall asks for it so that it can contact you about your usage.
- It is never logged. HTTP client errors quote the full request URL, so the adapter logs failures as the exception type and status code (`ClientResponseError (HTTP 422)`) only.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import UnpaywallAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    adapter = UnpaywallAdapter(LookupConfig())  # reads UNPAYWALL_EMAIL
    if not adapter.is_available():
        raise SystemExit("set UNPAYWALL_EMAIL")
    async with adapter:
        work = await adapter.get_concept_details("10.1038/s41586-020-2012-7")
        data = work.source_data["UNPAYWALL"]
        print(data["is_oa"], data["oa_status"], data["best_oa_location"])
        for edge in await adapter.get_relationships(work.primary_id, limit=5):
            if edge["relation_label"] == "available_at":
                print(edge["related_id"], edge["version"], edge["license"], edge["host_type"])


asyncio.run(main())
```

## Methods

| Method | What it does |
|---|---|
| `get_concept_details(doi)` | The work: title, year, journal, publisher, `is_oa`, `oa_status`, `has_repository_copy`, `journal_is_oa`, `journal_is_in_doaj`, `best_oa_location`, `oa_locations` (capped at 10; `n_oa_locations` is the full count), `n_embargoed_locations`, first 10 authors. Type `CITATION`, id = the lower-case DOI. |
| `get_relationships(doi, limit=25)` | `available_at` one edge per OA copy, best first (`related_id` is the copy's URL; `version`, `license`, `host_type`, `is_best`, `repository_institution`, `url_for_pdf`, `oa_date`, `evidence` reported verbatim), then `published_in` (journal, `ISSN:<issn-l>`) and `published_by` (publisher). `limit` caps the copies. |
| `get_mappings(doi)` | `DOI`, `ISSN-L` and `ISSN`s of the journal. |
| `search_concepts(query, limit, open_access_only=None)` | Title search through `/v2/search?query=...` (`open_access_only` maps to `is_oa`). A DOI as the query resolves directly. The search response envelope is parsed defensively because it is not live-verified: a list `results` whose entries hold the DOI object under `response` (or are DOI objects). |

All methods return `[]` / `None` on errors, unknown DOIs and invalid ids. The DOI record is cached per adapter instance (64 DOIs), so details, relationships and mappings of one DOI cost one call.

## Reading the open access fields

Reported as Unpaywall returns them, without interpretation:

- `oa_status`: `gold` (open at the publisher in a fully OA journal), `hybrid` (open at the publisher under a licence in a subscription journal), `bronze` (free at the publisher without a clear licence), `green` (only a repository copy), `closed`.
- `version`: `submittedVersion` (preprint), `acceptedVersion` (author manuscript), `publishedVersion` (version of record). A green copy is usually *not* the published version: check `version` before quoting from it.
- `license` is the licence found on **that copy** (`cc-by`, ...) and is often `None` even for an open copy; `None` means "not found", not "none applies". Repository and bronze copies frequently have no machine-readable licence.
- `host_type`: `publisher` or `repository`; `repository_institution` names the repository.
- `evidence`, `pmh_id`, `endpoint_id` are Unpaywall's internal debugging fields.
- Coverage is Crossref DOIs; a DOI Unpaywall does not know answers 404 (`None` here).

## Limits and terms

- Documented ([API page](https://unpaywall.org/products/api)): "please limit use to 100,000 calls per day"; for heavier use Unpaywall asks you to download the data snapshot instead. It is a request, not an enforced quota, but the adapter honours it: it counts its own calls per UTC day and refuses further requests after 100,000 (a cache hit costs nothing), and spaces requests by 0.2 s. The counter is per adapter instance; if you run several processes, keep their total under the limit yourself.
- Unpaywall data are CC0; the service is free. Only DOIs from the lookup are sent (nothing else), plus your address.
- No other authentication exists for this API.

## Not verified live (check these on first use)

1. The response parsing against a real DOI object (field names follow the [data format page](https://unpaywall.org/data-format); `journal_issns` is read as a comma-separated string, a list also works).
2. The search endpoint: path `/v2/search?query=...&email=...` (the request without email answered 422 like the DOI endpoint, so the path exists), `is_oa` and `page` parameters, the result envelope and the page size.
3. The 404 body for unknown DOIs (`{"error": true, "message": ...}` is assumed; any error status gives `None`).
4. Whether Unpaywall rejects particular e-mail domains (placeholder addresses such as `@example.com` may be refused; a rejection would answer 422 and yield empty results with a logged status code).

Verified live (2026-10-09, without an address): `GET /v2/<doi>` and `GET /v2/search?query=...` both answer HTTP 422 `{"HTTP_status_code": 422, "error": true, "message": "Email address required in API call, see http://unpaywall.org/products/api"}` in about 0.4 s.

## See also

- [OpenAIRE adapter](openaire_adapter.md) (copies with licences per repository, no key needed), [DOAJ adapter](doaj_adapter.md), [Crossref adapter](crossref_adapter.md), [OpenAlex adapter](openalex_adapter.md)
- [All adapters](../README.md)
