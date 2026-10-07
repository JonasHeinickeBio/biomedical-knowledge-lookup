---
description: FDA adverse event reports (FAERS) by drug and reaction via openFDA; descriptive report counts, not risks (keyless).
---

# openFDA adverse events (FAERS) adapter

Queries the [openFDA drug adverse event API](https://open.fda.gov/apis/drug/event/), which serves the FDA Adverse Event Reporting System (FAERS): spontaneous reports submitted by patients, clinicians and manufacturers. The adapter exposes **drugs** (openFDA generic name) and **reactions** (MedDRA preferred term, as text) and the report counts that connect them.

> **FAERS counts are reporting counts, not risks. Read this before using any number.**
>
> - **Spontaneous and unverified.** Anyone can report; reports are not validated and there is no confirmation that the drug was taken as stated.
> - **No causality.** A report lists a drug and a reaction that occurred; it does not say the drug caused it. A drug may be *suspect*, *concomitant* or *interacting* in a report, and the searches here match the drug anywhere in the report (openFDA cannot tie the role to the drug name).
> - **No denominator.** There is no count of patients exposed, so `report_proportion` (reports with this reaction / reports mentioning the drug) is descriptive, not an incidence or a risk.
> - **Duplicates.** The same event often arrives through several routes (patient, physician, manufacturer, literature), inflating counts.
> - **Reporting bias.** Under-reporting of mild or well-known events, stimulated reporting after publicity or litigation, and heavy over-representation of newer drugs, serious events and the US.
> - **Confounding by indication.** The reaction is often a symptom of the disease the drug treats. Fatigue is the textbook example: aspirin has 33,155 fatigue reports out of 533,828 (6.2 %), but patients on aspirin are, among other things, cardiovascular patients, and fatigue is co-reported with prednisone, adalimumab and acetaminophen at similar or higher volume. For ME/CFS and Long COVID work, fatigue and malaise are *the symptom you study*, so fatigue "signals" in FAERS say more about who takes a drug than about the drug. `include_indications=True` in `get_relationships` shows what the drug was reported as taken for, to make the confounder visible.
> - **Reaction to drugs is dominated by popularity.** The drugs listed for a reaction are everything co-listed on those reports, so commonly used drugs top the list whether or not they are related.

| | |
|---|---|
| Source | `KnowledgeSource.OPENFDAEVENTS` |
| Class | `knowledge_lookup.adapters.OpenFDAEventsAdapter` |
| Requires | none. Optional `OPENFDA_API_KEY` (raises the daily quota) |
| Identifiers | drugs `FAERS:DRUG:ASPIRIN`; reactions `FAERS:REACTION:FATIGUE`. Bare names (`aspirin`, `fatigue`) are accepted; a bare name is tried as a drug first, then as a reaction. Also `DRUG:`, `REACTION:`, `PT:` and `MEDDRA:` prefixes. Names are upper-cased. MedDRA codes are not published by this API, so none are claimed |
| Upstream API | `https://api.fda.gov/drug/event.json` |
| Licence / terms | public data under the [openFDA terms](https://open.fda.gov/terms/); every response carries the disclaimer "Do not rely on openFDA to make decisions regarding medical care" |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OpenFDAEventsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OpenFDAEventsAdapter(LookupConfig()) as adapter:
        aspirin = await adapter.get_concept_details("aspirin")
        print(aspirin.source_data["OPENFDAEVENTS"]["total_reports"])

        rels = await adapter.get_relationships("FAERS:DRUG:ASPIRIN", limit=5, include_indications=True)
        for rel in rels:
            print(rel["relation_label"], rel["related_name"], rel["report_count"], rel["report_proportion"])


asyncio.run(main())
```

Output (counts as of the 2026-07-30 openFDA update):

```
533828
reported_adverse_event FATIGUE 33155 0.062108
reported_adverse_event DYSPNOEA 28112 0.052661
reported_adverse_event DIARRHOEA 27506 0.051526
reported_adverse_event NAUSEA 27443 0.051408
reported_adverse_event DIZZINESS 23142 0.043351
reported_indication PRODUCT USED FOR UNKNOWN INDICATION 222242 0.416314
reported_indication HYPERTENSION 53409 0.100049
...
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | drugs and reactions whose name contains every query word (2 requests, drugs get half of `limit` rounded up). `report_count` in `source_data` is the number of reports listing that exact name |
| `get_concept_details(id)` | a drug (`DRUG`) or reaction (`PHENOTYPE`) with `total_reports`, `serious_reports`, `non_serious_reports` (1 request) |
| `get_relationships(id, limit=25, include_indications=False)` | drug: `reported_adverse_event` edges to reactions; reaction: `reported_with_drug` edges to co-listed drugs. Each edge has `report_count`, `total_reports`, `report_proportion`, `entity_type` and an `evidence` caveat. Drug with `include_indications`: up to ten `reported_indication` edges. 2 requests (3 with indications) |
| `get_indication_counts(drug, limit)` | `{indication: reports}` (case variants folded) |
| `get_mappings(id)` | always `[]`: openFDA offers no cross-references for these names |

The predicate is deliberately `reported_adverse_event`, never "causes" or "has side effect".

## How queries are built (and what they mean)

- Drug: `patient.drug.openfda.generic_name.exact:"ASPIRIN"`; reaction: `patient.reaction.reactionmeddrapt.exact:"FATIGUE"`. The `.exact` fields are case-sensitive and upper-case, so names are upper-cased. Searching without `.exact` is token-based and would, for example, match "CHRONIC FATIGUE SYNDROME" for "fatigue".
- Counts use `count=<field>.exact`, which returns the most frequent values (at most 1000) over all reports matching the search. This is why `search_concepts` filters the returned names: the count also contains every other drug or reaction that was listed on those reports.
- The report total comes from `count=serious` (1 = serious, 2 = not serious), because the exact `meta.results.total` needs a `limit=1` request that transfers about 100 KB of one full report. The two differ by about 0.05 % (a few reports lack the `serious` field): aspirin 533,828 here against 534,081 reports by the `ASPIRIN` name count.
- Only the openFDA harmonised generic name is used. Reports that carry a drug only as free text (`medicinalproduct`), or under a brand name without harmonisation, are not found.
- Variants of a name are separate values: `ASPIRIN`, `ASPIRIN 81 MG` and `ASPIRIN 325 MG` are different generic names, and combinations such as `ACETAMINOPHEN, ASPIRIN, AND CAFFEINE` are their own entries. Free-text indications also have case variants (`HYPERTENSION` and `Hypertension`), which the adapter folds by adding counts (a report listing both is counted twice, so a folded count can slightly overstate).

## Rate limits and quirks (verified 2026-10-07)

- Keyless: 240 requests per minute and **1,000 requests per day** per IP; with a key: 240 per minute and 120,000 per day per key (documented at open.fda.gov/apis/authentication). The responses carry no rate-limit headers. Budget: a `search_concepts` call is 2 requests, a relationship call 2 to 3, so about 300 relationship lookups per day without a key. The key is sent as `api_key` (`OPENFDA_API_KEY`).
- `limit` above 1000 is rejected with a misleading `403 API_KEY_MISSING`; the adapter clamps to 1000.
- "No matches" is `404 NOT_FOUND` rather than an empty list. The shared retry layer treats it as an answer (it does not open the circuit breaker) and the adapter returns `[]` / `None`, logging it at debug level only.
- Latency is 0.4 to 2.5 s. Failures are logged; searches return `[]` and detail calls `None`.

## OFFSIDES, SIDER and this adapter

All three derive from the same underlying phenomenon (adverse events reported to or about drugs) but answer different questions:

| | openFDA events (this adapter) | [OFFSIDES](offsides_adapter.md) | [SIDER](sider_adapter.md) |
|---|---|---|---|
| Data | raw FAERS report counts, live API | FAERS mined for *off-label* signals with a PRR against matched control drugs | side effects extracted from drug labels (text mining) |
| Statistics | none: counts and a simple proportion | PRR and its standard error, ranked by the lower 95 % bound | frequencies where labels give them |
| Currency | refreshed by the FDA (`last_updated` 2026-07-30 at the time of writing) | static file, dated (last modified 2024-03-30) | static, outdated (SIDER 4.1, 2015) |
| Access | keyless REST, 1,000 requests per day | 69 MB file, opt-in download | small opt-in download (~5.5 MB) |
| Identifiers | names (generic name, MedDRA term text) | RxNorm, MedDRA codes | STITCH compound ids, UMLS CUIs |
| Best for | current, descriptive "how often is X reported with Y" and what else is on those reports | hypothesis generation about unlabelled effects | what a label already states as known |

None of them establishes causation. When all three are consulted, agree on the question first: a high FAERS count for a drug and a symptom does not mean OFFSIDES will flag it (it may be labelled, or an artefact of the indication), and a SIDER entry shows only that the label mentions it.

## See also

- [OFFSIDES adapter](offsides_adapter.md), [SIDER adapter](sider_adapter.md), [RxClass adapter](rxclass_adapter.md)
- [All adapters](../README.md)
