---
description: Zenodo research datasets, software and publications: search, record metadata, licences and DOI links (no file downloads).
---

# Zenodo adapter

Searches [Zenodo](https://zenodo.org), the CERN/OpenAIRE repository where researchers deposit datasets, code, preprints and posters under a DOI. The adapter is meant for **finding** material (for example ME/CFS or Long COVID datasets, analysis code, supplementary data of a paper). It returns metadata and the record URL; it never downloads, lists or links files. File information is reduced to a count and a total size in bytes.

| | |
|---|---|
| Source | `KnowledgeSource.ZENODO` |
| Class | `knowledge_lookup.adapters.ZenodoAdapter` |
| Requires | none (`ZENODO_ACCESS_TOKEN` is optional) |
| Identifiers | numeric record id `10576421`; also `zenodo.10576421`, `10.5281/zenodo.10576421`, `doi:...`, `https://doi.org/10.5281/zenodo.10576421` and `https://zenodo.org/records/10576421` |
| Upstream API | `https://zenodo.org/api` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ZenodoAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ZenodoAdapter(LookupConfig()) as adapter:
        hits = await adapter.search_concepts('"long covid"', limit=3, resource_type="dataset")
        for concept in hits:
            print(concept.primary_id, concept.primary_label[:70])

        record = await adapter.get_concept_details("10.5281/zenodo.3708367")
        data = record.source_data[adapter.get_source()]
        print(data["license"], data["file_count"], data["total_size_bytes"])
        for rel in await adapter.get_relationships("3708367"):
            print(rel["relation_label"], rel["related_id"])


asyncio.run(main())
```

Output (recorded 2026-10-09):

```
10576421 Characterising long COVID-like COVID-19 vaccine reactions
6078874 Phenotyping long COVID
7308463 Long Covid collection
cc-by-4.0 1 2300868810
has_license cc-by-4.0
in_community zenodo-community:humanitasirccs
is_version_of DOI:10.5281/zenodo.3708366
is_supplement_to PMID:30777853
is_supplement_to DOI:10.1158/0008-5472.CAN-18-1544
```

## Searching

`search_concepts(query, limit=20, resource_type=None, sort="bestmatch")` calls `GET /records`.

- `query` is Elasticsearch query-string syntax. A bare `long covid` means *long* OR *covid* (21,358 datasets), so quote phrases: `"long covid"`, `"myalgic encephalomyelitis" AND (cytokine OR metabolomics)`, or use fields such as `metadata.keywords:"ME/CFS"`. A query that is itself a record id or Zenodo DOI goes straight to details; a bare number shorter than six digits is treated as a search word.
- `resource_type` is one of `dataset`, `software`, `publication`, `image`, `video`, `poster`, `presentation`, `lesson`, `physicalobject`, `other`. Zenodo silently returns zero hits for any other value, so the adapter validates it and returns `[]` (as it does for an invalid `sort`). Without it all types are searched; for dataset discovery pass `resource_type="dataset"`.
- `sort` is `bestmatch` or `mostrecent`.
- `limit` is capped at 50: two pages of 25, the largest page anonymous callers may request (larger sizes answer HTTP 400). The page size stays at 25 for both pages because Zenodo computes the offset as `(page - 1) * size`.
- Only the latest version of each record is returned. Search hits are complete records, so a search costs no extra detail calls.

`concept_type` is `STUDY` for datasets, `REFERENCE` for publications and `UNKNOWN` for software and everything else; `confidence_score` falls from 0.9 with the position.

## Concept details

| Field | Value |
|---|---|
| `primary_id` | numeric record id (`"10576421"`) |
| `primary_label` | title |
| `definitions` | description with HTML stripped (capped at 4,000 characters) |
| `categories` | the record's keywords |
| `semantic_types` | resource type title (`Dataset`, `Software`, `Publication`, ...) |
| `identifiers` | record id with the Zenodo URL, and `DOI:<doi>` with the doi.org URL |
| `source_data[ZENODO]` | `record_id`, `url`, `doi`, `concept_doi` / `concept_record_id`, `resource_type`, `resource_subtype`, `creators` (first 25) and `creator_count`, `publication_date`, `version`, `language`, `keywords`, `communities` (slugs), `license` (id), `access_right`, `embargo_date`, `file_count`, `total_size_bytes`, `attribution`, `license_note` |

`doi` is the record's own DOI, which is not always a Zenodo one: records imported from Dryad carry `10.5061/dryad...` and have no concept DOI. `file_count` and `total_size_bytes` come from the `files` array as returned; embargoed and restricted records list no files (0 and 0).

## Relationships and mappings

`get_relationships(id, limit=50)`:

| `relation_label` | `related_id` |
|---|---|
| `has_license` | licence id such as `cc-by-4.0`, `cc-zero`, `mit-license` |
| `in_community` | `zenodo-community:<slug>` (`url` is the community page; Zenodo lists only the slug) |
| `is_version_of` | `DOI:<concept DOI>`, the DOI that always resolves to the newest version (`kind: concept_doi`) |
| every `related_identifiers` entry | snake-case DataCite relation: `cites`, `is_cited_by`, `references`, `is_supplement_to`, `is_part_of`, `has_version`, `is_version_of`, `is_continued_by`, ...; `related_id` is `DOI:...`, `PMID:...`, `arXiv:...`, a URL or `<scheme>:<id>` (LSID, handle, ...), with `datacite_relation`, `scheme` and, where present, the target's `resource_type` as extra keys |

`get_mappings(id)` returns the identifiers that can be looked up elsewhere, always with confidence 1.0:

| `mappingType` | `toId` / `toSource` |
|---|---|
| `same_as` | `DOI:<record DOI>` / `DOI` |
| `version_group` | `DOI:<concept DOI>` / `DOI` |
| the snake-case relation (`is_supplement_to`, `cites`, ...) | `PMID:<id>` / `PUBMED`, `arXiv:<id>` / `ARXIV`, `DOI:<doi>` / `DOI` of the linked work |

URL, LSID and handle targets are relationships only. A relation such as `is_supplement_to` means "this record is data for that paper", not equivalence, so check `mappingType` before treating a mapping as `sameAs`.

## Rate limits, licences and terms

- Verified from the `X-RateLimit-Limit` header: **30 requests/minute** for `/records` searches and about **133/minute** for single-record reads (separate counters). The adapter spaces searches by 2.1 s and record reads by 0.5 s. Fifty search results (two pages) therefore take about 3 s.
- A personal access token (`ZENODO_ACCESS_TOKEN`, or `zenodo` in `LookupConfig.api_keys`) is **optional**. If set it is sent as an `Authorization: Bearer` header, never in the URL, and the search spacing drops to 1 s. Zenodo documents higher limits and larger pages for authenticated callers; that could not be tested without a token, so the page size stays at 25. Never commit a token.
- Zenodo metadata is CC0, but the *content* of a record has its own licence and access right. `source_data` carries `license`, `access_right` (`open`, `embargoed`, `restricted`, `closed`) and a ready-made `attribution` string (`Author et al. (year). Title. Zenodo. https://doi.org/...`) and `license_note`. Honour them, and note that open access does not imply a permissive licence (some records are `cc-by-nc-nd-4.0`).
- Shared HTTP retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). All methods log errors and return `[]` / `None`; a 404 for an unknown record id gives `None`.

## Caveats

- `GET /records/1` and a few other very small ids answer HTTP 500 instead of 404 (observed); they are reported as not found, but each one counts as a failure for the circuit breaker.
- `q` does not validate syntax: an unbalanced `chronic fatigue AND (` is accepted and matches millions of records.
- Search hits are large (about 7-8 KB per record; 180-190 KB for a page of 25). The adapter does not ask for facets or files separately.
- Community titles are not part of the record; only the slug and URL are returned.
- Zenodo is not curated: titles and keywords are as free-form as the depositor wrote them, and many ME/CFS and Long COVID hits are papers rather than datasets. Combine `resource_type="dataset"` with phrase queries.

## Live verification (2026-10-09)

- `GET /records?q=long covid&size=1`: HTTP 200, 8.7 KB, 0.3 s; 21,358 dataset hits for `long covid`, 393 records (21 datasets, 4 software) for `myalgic encephalomyelitis`.
- A page of 25 dataset hits: 180-190 KB in 0.5-1.2 s; two pages (50 hits) 3.2 s including the 2.1 s spacing; `GET /records/<id>`: 4-6 KB in 0.1-0.4 s.
- Checked on real records: 10576421 (Long COVID vaccine-reaction survey, CC-BY-4.0), 4960364 (ME/CFS cytokines, Dryad DOI, CC0), 3708367 (supplement of PMID 30777853, concept DOI, community), 12762596 (figure with LSID/URL targets), 20414304 (software, MIT), 21302835 (embargoed until 2026-12-30). Unknown `type` gives zero hits, `sort=bogus` and `size=500` give HTTP 400, `page=9999` gives HTTP 400.
- `python -m knowledge_lookup check ZENODO` passes.
- Not verified: authenticated limits and page sizes (no token was used).

## See also

- [GEO adapter](geo_adapter.md), [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
