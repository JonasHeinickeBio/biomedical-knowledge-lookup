---
description: Crossref DOI metadata, references and retraction/correction notices (keyless).
---

# Crossref adapter

Searches [Crossref](https://www.crossref.org/), the DOI registration agency behind most journals, books and the bioRxiv/medRxiv preprints, and fetches the metadata publishers deposit: title, journal, authors, abstract, citation count and reference list. The main value for literature mining is the **update layer**: retractions, corrections, expressions of concern and withdrawals (deposited by publishers or imported from the Retraction Watch database) and the preprint-to-article links. `check_retraction(doi)` answers "has this paper been retracted?" in one call.

| | |
|---|---|
| Source | `KnowledgeSource.CROSSREF` |
| Class | `knowledge_lookup.adapters.CrossrefAdapter` |
| Requires | none (keyless, JSON); optional `CROSSREF_MAILTO` for Crossref's polite pool |
| Identifiers | DOIs: `10.1038/s41586-020-2012-7`, `doi:10.1038/...` and `https://doi.org/10.1038/...` are all accepted (stored lower-cased) |
| Upstream API | `https://api.crossref.org` |
| Licence | Crossref metadata are released without restrictions (CC0). Abstracts and reference lists are only present when the publisher deposited them, and abstracts stay the publisher's copyright: do not redistribute them in bulk |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import CrossrefAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with CrossrefAdapter(LookupConfig()) as adapter:
        # journal articles since 2023 (relevance ranked)
        works = await adapter.search_works(
            "long covid", limit=3, filters={"type": "journal-article", "from_year": 2023}
        )
        for w in works:
            print(w.primary_id, w.primary_label[:60])

        # the main value: retractions and corrections
        check = await adapter.check_retraction("10.1016/S0140-6736(97)11096-0")
        print(check["retracted"], [(n["type"], n["date"]) for n in check["notices"]])

        for rel in await adapter.get_relationships("10.1038/s41586-020-2012-7"):
            if rel["relation_label"] != "cites":
                print(rel["relation_label"], rel["related_id"])


asyncio.run(main())
```

Output (recorded 2026-10-08):

```
True [('correction', '2004-03-06'), ('retraction', '2010-02-06')]
addendum_by 10.1038/s41586-020-2951-z
has_preprint 10.1101/2020.01.22.914952
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | works (CITATION) ranked by Crossref's relevance (`works?query=`), at most 100. A DOI (any accepted form) resolves to that single work |
| `search_works(query, limit, filters, sort)` | the search itself. `filters` keys: `type`, `from_year`, `until_year`, `from_date`, `until_date`, `issn`, `prefix`, `has_abstract`, `has_references`, `has_update`, `is_update`, `update_type` (e.g. `retraction`). `sort="published"` / `"is-referenced-by-count"` sorts descending |
| `get_concept_details(doi)` | one work: title, container, date, type, publisher, ISSN, author count and the first 15 authors, citation count, reference count, volume/issue/page, licence URLs, abstract (as the definition, markup stripped), `retracted` flag |
| `get_relationships(doi)` | update notices first, then preprint/version links, then references (see below) |
| `get_mappings(doi)` | ISSN and ISBN of the container; PMID/PMCID/arXiv ids when a publisher deposited them as relations |
| `check_retraction(doi)` | dict: `doi`, `found`, `retracted`, `expression_of_concern`, `corrected`, `title_flagged`, `notices` (each `{doi, type, label, date, asserted_by}`) and `is_notice_for`. Always asks Crossref afresh |
| `doi_agency(doi)` | registration agency id (`crossref`, ...) from `works/{doi}/agency` |

Concept fields: `primary_id` is the lower-cased DOI, `concept_type` `CITATION`, `categories` carries `type:`, `journal:`, `year:`, `publisher:` and, when a retraction notice exists, `retracted` (also `expression_of_concern`). `source_data["CROSSREF"]` has the structured record.

### Relationships

| `relation_label` | Meaning | Source field |
|---|---|---|
| `retracted_by`, `partially_retracted_by`, `withdrawn_by`, `removed_by`, `expression_of_concern_by`, `corrected_by` (correction/corrigendum/erratum), `addendum_by`, `clarified_by`; other types become `<type>_by` | the work was updated by the notice in `related_id` | `updated-by` |
| `retracts`, `corrects`, `expresses_concern_about`, ... | the work *is* a notice for `related_id` | `update-to` |
| `has_preprint`, `is_preprint_of`, `has_version`, `is_version_of` | preprint / version links, 25 per type at most | `relation` |
| `cites` | up to 100 references | `reference` |

Notice edges carry `update_type`, `notice_date` (ISO, may be only a year or month) and `asserted_by` (`publisher` or `retraction-watch`). Many references have no DOI: they are **kept**, with `related_id` `<doi>#<reference key>`, `has_doi: false`, the citation text in `related_name` and `unstructured`, and `total_references` giving Crossref's exact count.

## Polite pool and rate limits

Verified from response headers on 2026-10-08: single-work lookups (`works/{doi}`) report `x-rate-limit-limit: 5` per `1s`, list and search queries `1` per `1s`, and both `x-concurrency-limit: 1`. The adapter therefore serialises its requests and spaces them by at least 1.1 s (lists) or 0.25 s (single works); one `get_relationships` after a `get_concept_details` of the same DOI reuses a small per-instance cache (32 works) instead of a second request.

Crossref documents a faster "polite pool" for requests that include a `mailto` parameter. The adapter sends **nothing identifying** by default; set the environment variable `CROSSREF_MAILTO=you@example.org` to opt in. The value is read from that variable only, never from any other place. The headers did not change for requests from this client, so the 1 s / 5 per second spacing is kept either way.

## Caveats

- **A missing notice is not proof that a paper stands.** Only notices that publishers deposited or that were imported from Retraction Watch are visible; unknown DOI gives `found: false`, which means "not in Crossref", not "clean". `title_flagged` catches titles beginning with `RETRACTED` / `WITHDRAWN`.
- `select=` is validated strictly: an unknown field is HTTP 400 (`subtype` and `institution` are not selectable on the list route).
- DOIs registered with another agency (DataCite, mEDRA, ...) are 404 on `works/{doi}`; `get_concept_details` returns `None` and logs the agency.
- Titles and abstracts contain markup (`<i>`, `<jats:p>`); it is stripped. Reference lists, abstracts and `relation` entries are publisher-dependent and often absent.
- `is-referenced-by-count` is Crossref's own count of DOI-to-DOI citations and differs from OpenAlex, Google Scholar or [OpenCitations](opencitations_adapter.md).

## Live verification (2026-10-08)

| Call | Latency | Response |
|---|---|---|
| `works?query=long covid&rows=3&select=...` | 0.4 to 0.6 s | 1.6 KB; 2,340,354 matches |
| `works/10.1016/s0140-6736(97)11096-0` (Wakefield, 26 references) | 0.5 s | 11 KB; `updated-by` has a correction (2004) and a retraction (2010), both `source: retraction-watch` |
| `works/10.1038/s41586-020-2012-7` (16 references, 3 without DOI) | 0.55 s | 15 KB; `has-preprint` 10.1101/2020.01.22.914952, an addendum notice |
| `works?filter=updates:<doi>` | 0.6 s | confirms the same two notices from the other side |
| `knowledge-lookup check CROSSREF` | | PASS |

## See also

- [bioRxiv / medRxiv adapter](biorxiv_adapter.md) for the preprint side of `has_preprint` links, [OpenCitations adapter](opencitations_adapter.md) for the open citation graph, [OpenAlex adapter](openalex_adapter.md)
- [All adapters](../README.md)
