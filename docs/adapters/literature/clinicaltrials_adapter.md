---
description: ClinicalTrials.gov registered studies with their conditions, interventions, phase, status and enrollment.
---

# ClinicalTrials.gov adapter

Searches the ClinicalTrials.gov registry (API v2) and fetches single studies. The *study* is the concept, not a disease or drug: each result is a registered trial or observational study with its conditions and interventions, which `get_relationships` exposes as edges to the diseases it studies and the interventions it tests. Useful for questions such as which ME/CFS or Long COVID treatments are currently in trials.

| | |
|---|---|
| Source | `KnowledgeSource.CLINICALTRIALS` |
| Class | `knowledge_lookup.adapters.ClinicalTrialsAdapter` |
| Requires | none (keyless) |
| Identifiers | `NCT07753122` (also `ClinicalTrials:NCT07753122`, case-insensitive) |
| Upstream API | `https://clinicaltrials.gov/api/v2` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ClinicalTrialsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ClinicalTrialsAdapter(LookupConfig()) as adapter:
        studies = await adapter.search_by_condition(
            "ME/CFS", limit=3, status=["RECRUITING", "NOT_YET_RECRUITING"]
        )
        for study in studies:
            data = study.source_data["CLINICALTRIALS"]
            print(study.primary_id, data["status"], data["phases"], study.primary_label[:60])

        for rel in await adapter.get_relationships("NCT07753122"):
            print(rel["relation_label"], rel["related_type"], rel["related_name"][:50])


asyncio.run(main())
```

Output (live, October 2026):

```
NCT07753122 RECRUITING ['NA'] Controlled Trial of Hydrogen Water as a Treatment for Myalgi
...
studies_condition condition Chronic Fatigue Syndrome (CFS)
studies_condition condition Fatigue Syndrome, Chronic
tests_intervention DIETARY_SUPPLEMENT Placebo condition
tests_intervention intervention Hydrogen
```

## Methods

| Method | Query parameter | Notes |
|---|---|---|
| `search_concepts(query, limit)` | `query.term` | Free text over titles, conditions, interventions, sponsors, keywords. |
| `search_by_condition(condition, limit, status=None)` | `query.cond` | Condition/disease; the registry expands synonyms. |
| `search_by_intervention(intervention, limit, status=None)` | `query.intr` | Drug, device, behavioural intervention name. |
| `get_concept_details(nct_id)` | `/studies/{NCTId}` | Full record including the summary. |
| `get_relationships(nct_id)` | `/studies/{NCTId}` | Conditions and interventions as edges. |
| `get_mappings(nct_id)` | `/studies/{NCTId}` | MeSH ids the registry assigned. |

`status` filters `overallStatus`: a string or list from `RECRUITING`, `NOT_YET_RECRUITING`, `ACTIVE_NOT_RECRUITING`, `ENROLLING_BY_INVITATION`, `COMPLETED`, `TERMINATED`, `WITHDRAWN`, `SUSPENDED`, `UNKNOWN`. An invalid value makes the API answer 400 and the search returns `[]`. Searches page with `nextPageToken` (up to 100 studies per request, at most 5 requests) and request only the needed fields, which keeps responses to a few kB per study.

## Concept model

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | NCT id / brief title |
| `concept_type` | `CLINICAL_TRIAL` for interventional studies, `OBSERVATIONAL_STUDY` for observational ones, `CLINICAL_STUDY` for anything else (e.g. expanded access). There is no registry-record type in the enum; these are the closest. |
| `definitions` | brief summary (first 1000 characters) |
| `synonyms` | official title and acronym |
| `categories` | `status:RECRUITING`, `phase:PHASE2`, `condition:...` |
| `semantic_types` | `[studyType]` |
| `source_data["CLINICALTRIALS"]` | `nct_id`, `status`, `study_type`, `phases`, `enrollment`, `enrollment_type`, `start_date`, `completion_date`, `last_update`, `sponsor`, `conditions`, `keywords`, `interventions` (name, type, description, arm groups), `condition_mesh`, `intervention_mesh`, `has_results`, `url` |

## Relationships

- `studies_condition`: one edge per listed condition (`related_id` is the condition text as registered) and one per registry-assigned condition MeSH term (`related_id` `MESH:D015673`, `derived: True`).
- `tests_intervention`: one edge per intervention (`related_id` is the name, `related_type` the registry type: `DRUG`, `BIOLOGICAL`, `DEVICE`, `BEHAVIORAL`, `DIETARY_SUPPLEMENT`, `PROCEDURE`, `OTHER`, with `description` and `arm_groups` when present) and MeSH-derived edges.

Registered intervention names are free text (`Placebo condition`, `Molecular hydrogen ... 16 weeks`), and placebo arms are listed as interventions too, so filter on `derived` or on the type when you need clean drug names. The MeSH-derived edges are the more normalised ones, but they are assigned algorithmically by the registry, so they can be missing or imprecise.

## Rate limits and caveats

- ClinicalTrials.gov documents roughly 50 requests per minute per IP. The adapter spaces requests by 1.25 s, so a search followed by details takes a couple of seconds.
- Free text is relevance-ranked over many fields, so `search_concepts("long covid")` returned COVID-era studies that only mention it in the top hits. Prefer `search_by_condition` for precision.
- `Phase` is absent for observational studies; `enrollment` may be an estimate (`enrollment_type`).
- An unknown but well-formed NCT id gives 404 (details return `None`); a malformed id is rejected locally.
- Latency in testing: 0.3 to 0.4 s per call.
- Shared retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; searches return `[]` and details return `None`.

## See also

- [PubTator adapter](pubtator_adapter.md), [Europe PMC adapter](europepmc_adapter.md)
- [All adapters](../README.md)
