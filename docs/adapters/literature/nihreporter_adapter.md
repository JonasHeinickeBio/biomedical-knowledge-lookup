---
description: NIH RePORTER funded research projects (ME/CFS, Long COVID and every other area) with institutes, RCDC categories, terms and linked publications (keyless).
---

# NIH RePORTER adapter

Searches [NIH RePORTER](https://reporter.nih.gov/), the public database of research projects funded by NIH and other US HHS agencies (CDC, AHRQ, FDA, VA) since 1985. It answers "who funds this topic, how much, through which institute, and which papers came out of it": the free-text query `myalgic encephalomyelitis` finds 866 projects on 2026-10-08, and the RECOVER Long COVID initiative and the NIH ME/CFS collaborative research centres are all in there.

| | |
|---|---|
| Source | `KnowledgeSource.NIHREPORTER` |
| Class | `knowledge_lookup.adapters.NIHReporterAdapter` |
| Requires | none (keyless, JSON over POST) |
| Identifiers | core project number `R01AI170850` (the concept id); also full project numbers `5R01AI170850-05` and application ids `APPL:11391125`, each optionally with a `NIHREPORTER:` prefix |
| Upstream API | `https://api.reporter.nih.gov/v2` (`projects/search`, `publications/search`) |
| Licence | US Government data, freely available for public use with no stated licence restriction; please acknowledge NIH RePORTER |
| Concept type | `STUDY` (closest fit for a funded research project) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import NIHReporterAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with NIHReporterAdapter(LookupConfig()) as adapter:
        for p in await adapter.search_concepts("myalgic encephalomyelitis", limit=3):
            print(p.primary_id, p.primary_label[:60])

        # RECOVER / Long COVID projects of fiscal year 2023, largest awards first
        for p in await adapter.search_projects(
            "long covid RECOVER", limit=3, fiscal_years=[2023], sort="award_amount"
        ):
            print(p.primary_id, p.source_data["NIHREPORTER"]["award_amount"])

        grant = await adapter.get_concept_details("R01AI170850")
        data = grant.source_data["NIHREPORTER"]
        print(data["institute"]["abbreviation"], data["fiscal_year"], data["award_amount"])
        for rel in await adapter.get_relationships("R01AI170850", limit=5):
            if rel["relation_label"] in ("funded_by", "has_publication"):
                print(rel["relation_label"], rel["related_id"])


asyncio.run(main())
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | one concept per grant matching the free text (title, abstract, terms; words AND-ed, quotes make a phrase), newest fiscal year first. An identifier-shaped query (core/full project number) resolves that grant |
| `search_projects(query, limit, fiscal_years=None, sort="fiscal_year")` | the search itself; `sort` is a RePORTER field (`award_amount`, `project_start_date`, ...) or `"relevance"` |
| `get_concept_details(id)` | the grant by core number, full number or application id, with every fiscal-year application listed |
| `get_relationships(id, limit=100)` | `has_publication` (PMIDs), `funded_by` (institutes), `has_spending_category` (RCDC), `has_term`, `conducted_at` |
| `get_mappings(id)` | core number to full project numbers, application ids and PMIDs |

### Concepts

A grant runs for years and RePORTER publishes one *application* record per fiscal year (plus supplements such as `3R01AI170850-04S1`). The concept is the **grant**, identified by its core project number; the fiscal-year records are merged.

| Field | Value |
|---|---|
| `primary_id` | core project number, e.g. `R01AI170850` |
| `primary_label` | project title |
| `definitions` | abstract, then the public health relevance statement (details only) |
| `semantic_types` | `[activity code]`, e.g. `R01` |
| `categories` | `fiscal_year:`, `institute:<abbreviation>`, `rcdc:<spending category>` |
| `identifiers` | `NIHREPORTER` `APPL:<application id>` with the RePORTER project URL |
| `source_data[NIHREPORTER]` | `project_num`, `appl_id`, `fiscal_year`, `award_amount` (that fiscal year's total, USD), `is_active`, project start/end dates, `institute`, `organization` (name, city, state, country, department type), `principal_investigators` (name and contact flag only), `spending_categories`, `spending_category_ids`, `terms`, `covid_response`, `applications` (appl id, project number, fiscal year, award per application), `url` |

The representative record is the newest fiscal year (the base award rather than a supplement). RCDC spending categories are only assigned after a fiscal year closes, so they are null on the running year; the newest non-null value of the grant is used.

### Relationships

| `relation_label` | `related_id` | Notes |
|---|---|---|
| `has_publication` | `PMID:<n>` | from `publications/search`, de-duplicated, at most `limit` (default 100, max 500). One extra request. RePORTER returns only PMIDs (no titles): fetch them from Europe PMC, PubMed or [LitCovid](litcovid_adapter.md) |
| `funded_by` | `NIHREPORTER:IC:<code>` | administering institute (`administering: True`, e.g. `NS` = NINDS) plus co-funding institutes of the latest year |
| `has_spending_category` | `NIHREPORTER:RCDC:<name>` | NIH Research, Condition, and Disease Categorization, e.g. "Chronic Fatigue Syndrome (ME/CFS)" or "Post-Acute Sequelae of SARS-CoV-2 infection (PASC) including Long COVID" |
| `has_term` | `NIHREPORTER:TERM:<term>` | first 50 NIH-preferred indexing terms (many are generic: "Adult", "Address") |
| `conducted_at` | `NIHREPORTER:ORG:<UEI>` | awardee organisation |

I chose `has_publication` (project to paper) over `published_in`, which reads as paper to journal.

### Mappings

`fromId` is the core number. `toSource` is `NIH_PROJECT_NUMBER` (every fiscal year, `exact`), `NIH_APPLICATION_ID` (`exact`) and `PMID` (`related`: a paper acknowledging a grant is not the grant itself).

## Rate limit and usage policy

The API home page asks for **no more than one request per second** and to run large jobs on weekends or between 9 pm and 5 am US Eastern; NIH may block clients that do not comply. The adapter spaces its requests at least one second apart (per adapter instance), fetches at most 300 records per search, and a lookup by core number costs 1 request (2 for full numbers or application ids, which first resolve the core number; relationships and mappings add 1 for publications). Page limits of the API: 500 records per request, offset up to 14,999 (projects) and 9,999 (publications).

## Personal data

RePORTER publishes principal-investigator names and organisations. Only the names and the contact-PI flag are kept; profile ids, job titles and program officers are dropped, and nothing is derived from the names (no author disambiguation or linking). Keep downstream use in line with NIH's data access policy.

## Caveats found while verifying

- The documented `core_project_nums` criterion is **silently ignored** by `projects/search`: it returned all 2.98 million projects. The adapter passes the bare core number as `project_nums`, which matches every fiscal year of the grant. Wildcards match nothing; malformed numbers return HTTP 400 `["Invalid project number"]` (the adapter validates the format first). `publications/search` does honour `core_project_nums`.
- Without `include_fields` each record carries a 6-7 KB `terms` string; the adapter always sends a field list (about 3.6 KB per search hit, mostly the abstract; 40 KB for a grant with six applications).
- `spending_categories` ids and `spending_categories_desc` names are not guaranteed to be in matching order, so they are not paired.
- Abstracts are as submitted: some start with "Abstract" or "DESCRIPTION (provided by applicant)", some contain line breaks.
- Free text uses AND over title, abstract and terms: `long covid` finds about 6,200 projects, 190 of them with the words in the title. Use quotes for an exact phrase.
- Python's `urllib` took about 2 minutes per request against this host, while `curl` and `aiohttp` (which the adapter uses) answered in 0.2 to 2 s. If you script against the API yourself, use one of the latter.
- Not covered: reports/RePORT-ER result sets beyond PMIDs (patents, clinical studies), per-IC funding history beyond the latest year, subproject (`subproject_id`) records of multi-component centres beyond what the search returns.

## Live verification (2026-10-08)

Against the real API, keyless:

- `search_concepts("myalgic encephalomyelitis", 5)` returned five grants in 1.2 s (866 matching projects, 32 KB for 9 records; newest fiscal year first).
- `get_concept_details("R01AI170850")`: 0.2 to 1.0 s, six application records (FY2022 to FY2026 plus a supplement, 40 KB); the FY2026 record has no RCDC categories yet while FY2025 lists nine, including "Chronic Fatigue Syndrome (ME/CFS)" and the PASC / Long COVID category.
- `get_relationships("R01AI170850")`: 12 publications, NIAID as administering institute, the awardee organisation and 50 terms in about 2 s (two requests).
- `get_mappings("5R01AI170850-05")`: 24 mappings (6 project numbers, 6 application ids, 12 PMIDs).
- Unknown core number `R01XX999999`: empty result, `None`. `python -m knowledge_lookup check NIHREPORTER` passes.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [ClinicalTrials.gov adapter](clinicaltrials_adapter.md), [OpenAlex adapter](openalex_adapter.md), [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
