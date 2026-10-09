---
description: ISRCTN clinical trial registry (UK-based, international).
---

# ISRCTN registry adapter

Searches the ISRCTN registry, the UK-based primary registry for clinical studies of any design, and fetches single records. The PACE trial for ME/CFS and many Long COVID studies are registered here. As with the ClinicalTrials.gov adapter, the *study* is the concept (id `ISRCTN12345678`, label = public title); the conditions, interventions, sponsor and funders are exposed as relationships, and the other registry numbers the record lists (NCT, EudraCT, CTIS, IRAS, protocol codes) as mappings.

| | |
|---|---|
| Source | `KnowledgeSource.ISRCTN` |
| Class | `knowledge_lookup.adapters.ISRCTNAdapter` |
| Requires | none (keyless) |
| Identifiers | `ISRCTN54285094` (also `ISRCTN:54285094`, `isrctn 54285094`, case-insensitive) |
| Upstream API | `https://www.isrctn.com/api/query/format/default?q=...&limit=...` (XML) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ISRCTNAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ISRCTNAdapter(LookupConfig()) as adapter:
        for study in await adapter.search_concepts('condition:"chronic fatigue syndrome"', limit=3):
            data = study.source_data["ISRCTN"]
            print(study.primary_id, study.concept_type, data["status"], study.primary_label[:55])

        for rel in await adapter.get_relationships("ISRCTN62918594"):
            print(rel["relation_label"], rel["related_type"], rel["related_id"][:30])
        for m in await adapter.get_mappings("ISRCTN62918594"):
            print(m["toSource"], m["toId"], m["mappingType"])


asyncio.run(main())
```

Output (live, 2026-10-09):

```
ISRCTN15375673 OBSERVATIONAL_STUDY Recruiting Long Covid and myalgic encephalomyelitis/chronic fa
ISRCTN16025168 CLINICAL_TRIAL Recruiting Multicentre study on coaching and point-of-care tech
ISRCTN16132141 OBSERVATIONAL_STUDY No longer recruiting Brain response to light stimulation in people with myalgic e
studies_condition condition Bladder Cancer
studies_condition condition Triple Negative Breast Cancer
...
tests_intervention Drug HMBD-001
has_sponsor organisation ROR:054225q67
funded_by organisation Cancer Research UK
CLINICALTRIALS NCT05057013 same_study
EudraCT 2020-005891-36 same_study
CTIS 2020-005891-36-00 same_study
IRAS IRAS:298897 secondary_id
CPMS CPMS:49816 secondary_id
Protocol serial number CRUKD/22/002 protocol_number
DOI 10.1186/ISRCTN62918594 doi
```

## Searching

`search_concepts(query, limit)` sends `q` and `limit` to `/api/query/format/default`. The query is Lucene-style (all verified live):

| Query | Meaning (records on 2026-10-09) |
|---|---|
| `fatigue` | any word in any field (1,513) |
| `long covid` | plain words are OR-ed: 1,218 records. Quote a phrase for precision: `"long covid"` 56 |
| `ME/CFS` | 11 |
| `title:fatigue`, `condition:fatigue`, `intervention:exercise`, `primaryStudyDesign:Observational` | field queries (121, 94, 1,759 and so on) |
| `condition:fatigue AND intervention:exercise` | `AND` / `OR` (14) |
| `NCT05057013` | other registry numbers find the record that lists them |

`sponsor:` and `country:` are not fields (0 hits). The API honours only `q` and `limit`: `offset`, `page`, `start`, `skip`, `from` and `sort` were all tried and silently ignored, so there is **no paging**; ask for a larger `limit` instead. `limit` is capped at 100 by the adapter, because records are large (see below). Result order is the server's (the broad queries tried returned the most recently registered studies first); no sort option is honoured.

Every search result is a complete record (the API has no light format), so search and details return the same fields.

## Concept details

`get_concept_details("ISRCTN54285094")` queries the registry with the id itself (`q=ISRCTN54285094`) and picks the record whose id matches exactly. The direct endpoint `api/trial/<id>/format/default` answers an HTML **HTTP 500** for a well-formed id that does not exist (and 400 for a malformed one), which would send the shared retry loop through four attempts, so it is not used.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `ISRCTN...` / public title |
| `concept_type` | `primaryStudyDesign` Interventional = `CLINICAL_TRIAL`, Observational = `OBSERVATIONAL_STUDY`, anything else `CLINICAL_STUDY` |
| `definitions` | plain-English summary, else the study hypothesis (unless the registrant wrote "Not provided at time of registration") |
| `synonyms` | scientific title, acronym |
| `categories` | `status:<status>`, `phase:<phase>`, `condition:<condition>` (one per line when the registrant lists several) |
| `semantic_types` | primary and secondary study design (`Observational`, `Cohort study`) |
| `source_data["ISRCTN"]` | title, scientific title, acronym, hypothesis, outcomes (primary/secondary with method and time points), study design (allocation, masking, control, assignment, purposes), status, recruitment start/end and overall end date, target and final enrolment, countries, trial centre names (first 20), age range and gender, conditions, interventions, sponsors, funders, external references, publication stage and details, dates assigned and updated, record URL |

**Recruitment status** is not part of the default format. The adapter derives it: a registrant override (`recruitmentStatusOverride`) wins; otherwise a start date in the future is "Not yet recruiting", an end date in the past "No longer recruiting", and anything else with a start date "Recruiting". `status_derived` in `source_data` says which applies. The derivation agreed with the WHO format's `recruitment_status` for 100 of 100 records checked, but none of them had an override, so suspended/stopped records could not be compared.

**Contact persons are deliberately not extracted.** Records carry names, e-mail addresses and phone numbers of contacts and principal investigators; the adapter reads none of them, and the test fixtures have them removed.

## Relationships

`get_relationships(id)`:

- `studies_condition`: each condition line the registrant wrote (`related_type` `condition`), the specific disease chosen in the registry's classification (`diseaseClass2`, `derived=True`) and the broad disease category (`diseaseClass1`, e.g. "Infections and Infestations", `related_type` `condition_category`). ISRCTN does not code conditions to MeSH or ICD, so the ids are the texts.
- `tests_intervention`: one edge per named drug when the record has `drugNames` (`related_type` the intervention type: `Drug`, `Behavioural`, `Supplement`, `Device`, `Procedure/Surgery`, ...), otherwise one per intervention with the start of its description as `related_id` (120 characters). `description` and `phase` are in the edge.
- `has_sponsor` and `funded_by`: organisations. `related_id` is `ROR:<id>` when the registry knows the organisation's ROR, otherwise the name; `commercial_status` is on sponsor edges.

## Mappings

`get_mappings(id)` lists the identifiers in `externalRefs`: `same_study` for ClinicalTrials.gov (`CLINICALTRIALS`), EudraCT, CTIS (canonical form with the `-00` part) and ChiCTR numbers; `secondary_id` for IRAS and CPMS numbers; `protocol_number` for sponsor, funder or other protocol codes (`toSource` is the label the registrant chose, e.g. "Protocol serial number"); `doi` for the registry's own DOI (`10.1186/ISRCTN...`). Duplicates (an NCT number listed twice) are merged.

## Rate limits, size and errors

No limit is documented; the adapter waits 0.5 s between requests. Measured on 2026-10-09: one record 11-30 KB and 0.2 s; three records 74 KB and 0.5 s; 100 records 1.8 MB and 1.1 s. A first request for a rarely used query can take 2-3 s. Unknown ids and queries with no hits return an empty `allTrials`; the adapter logs and returns `[]` / `None` for HTTP errors and for responses that are not XML. The registry's data are published for reuse with attribution to ISRCTN; check the site terms for bulk use.

## Live verification (2026-10-09)

`knowledge-lookup check ISRCTN` passes (search, details, relationships). ME/CFS and Long COVID queries returned the HERITAGE study (ISRCTN15375673, Long Covid and ME/CFS), the gefapixant breathlessness trial (ISRCTN38597726) and, for PACE (ISRCTN54285094), the full record with the Medical Research Council and three other funders. Recruitment status, field queries, paging parameters and the 500-on-unknown-id behaviour were all checked against live responses.

## See also

- [ClinicalTrials.gov adapter](clinicaltrials_adapter.md): the US registry; the same relationship vocabulary
- [All adapters](../README.md)
