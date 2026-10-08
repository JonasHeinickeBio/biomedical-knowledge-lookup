---
description: NLM Clinical Table Search Service: ICD-10-CM, LOINC items, consumer conditions, HPO, ICD-11 and ClinVar disease names behind one keyless search API.
---

# NLM Clinical Tables adapter

Looks codes and names up in the NLM Clinical Table Search Service (CTSS), a set of small coding tables behind one uniform, keyless search API. It is the quickest way to get **ICD-10-CM** and **LOINC** codes for registry harmonisation, and to turn a consumer-style condition name into ICD-10-CM / ICD-9-CM codes and a MedlinePlus page. Every row becomes one concept whose id carries the table (`ICD10CM:G93.32`, `LOINC:70735-6`, `HP:0012378`).

> **ICD-10-CM is not ICD-10-GM.** This service serves the US clinical modification (CDC). German registry coding uses ICD-10-GM, which differs in places (ME/CFS is `G93.32` in ICD-10-CM but `G93.3` in ICD-10-GM); use the [ICD-10-GM adapter](icd10gm_adapter.md) for that. Use this adapter for the US code, or to cross-check.

| | |
|---|---|
| Source | `KnowledgeSource.CLINICALTABLES` |
| Class | `knowledge_lookup.adapters.ClinicalTablesAdapter` |
| Requires | none (no key, no registration) |
| Identifiers | `ICD10CM:G93.32` (or bare `G93.32` / `G9332`), `CONDITIONS:12927`, `LOINC:70735-6` (or bare `70735-6`), `HP:0012378`, `ICD11:MG22`, `DISEASE_NAMES:C0015672` (or a bare CUI) |
| Upstream API | `https://clinicaltables.nlm.nih.gov/api/<table>/v3/search` |
| Environment | `CLINICALTABLES_TABLES` (optional, comma separated table names) |
| Licence | free "as is" service; LOINC content is under the [LOINC Terms of Use](https://loinc.org/terms-of-use) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ClinicalTablesAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ClinicalTablesAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue", limit=6):
            print(c.primary_id, c.primary_label)

        mecfs = await adapter.get_concept_details("G93.32")        # bare ICD-10-CM code
        print(mecfs.primary_id, mecfs.primary_label)

        for m in await adapter.get_mappings("CONDITIONS:12927"):
            print(m["toSource"], m["toId"])

        facit = await adapter.get_concept_details("LOINC:70735-6")
        print(facit.primary_label)

        print(await adapter.get_relationships("HP:0012432"))


asyncio.run(main())
```

Output:

```
ICD10CM:R53.82 Chronic fatigue, unspecified
CONDITIONS:12927 Chronic fatigue syndrome
LOINC:38939-5 Deprecated VA Compensation and Pension (C and P) examination chronic fatigue syndrome
HP:0012432 Chronic fatigue
ICD10CM:G93.32 Myalgic encephalomyelitis/chronic fatigue syndrome
LOINC:71151-5 Pediatric - Functional Assessment of Chronic Illness Therapy - Fatigue Questionnaire (Peds-FACIT-Fatigue)
ICD10CM:G93.32 Myalgic encephalomyelitis/chronic fatigue syndrome
ICD10CM R53.82
ICD9CM 780.71
MEDLINEPLUS http://www.nlm.nih.gov/medlineplus/chronicfatiguesyndrome.html
Functional Assessment of Chronic Illness Therapy-Fatigue Questionnaire -13 items - version 4 (FACIT - fatigue 13)
[{'relation_label': 'is_a', 'related_id': 'HP:0012378', 'related_name': 'Fatigue', 'source': 'CLINICALTABLES'}]
```

## Tables

| Table | Id prefix | Concept type | Rows | Content |
|---|---|---|---|---|
| `icd10cm` | `ICD10CM` | `DISEASE` | 74,879 (data version 2027, CDC) | billable ICD-10-CM codes with the long description |
| `conditions` | `CONDITIONS` | `DISEASE` | 2,418 (2026-10-01) | consumer conditions (Regenstrief / NLM PHR) with ICD-10-CM and ICD-9-CM codes, synonyms and MedlinePlus links |
| `loinc_items` | `LOINC` | `OBSERVATION` | 112,405 (LOINC 2.83) | LOINC observations (laboratory tests such as `14724-9` Ferritin), panels, forms and survey questions (FACIT-Fatigue, PROMIS, ...) |
| `hpo` | `HP` | `PHENOTYPE` | 20,481 (2026-09-01) | Human Phenotype Ontology terms with definition, synonyms and `is_a` |
| `icd11_codes` | `ICD11` | `DISEASE` | 35,664 (2026-01) | WHO ICD-11 MMS stem and extension codes with definition and index terms |
| `disease_names` | `DISEASE_NAMES` | `DISEASE` | ClinVar disease names | disease name keyed by its UMLS/MedGen CUI |

`search_concepts` queries the default set **`icd10cm`, `conditions`, `loinc_items`, `hpo`**. Change it for one call with `tables=[...]`, or for every call with the `CLINICALTABLES_TABLES` environment variable (for example `CLINICALTABLES_TABLES=icd10cm,loinc_items`) or `adapter.tables = ("hpo",)`. Unknown names are ignored with a warning. `rxterms`, `hcpcs`, `icd9cm_dx` and the other CTSS tables are not wired in (RxNorm has its own adapter).

## Searching

`search_concepts(query, limit=20, *, tables=None)` queries the chosen tables in parallel (one request each, `maxList=limit`, capped at the service limit of 500) and **interleaves** the answers round-robin so a big table cannot crowd out the others, then trims to `limit`. Details of the table queries:

- Words are AND-ed and each is a prefix match (`fatig` finds `fatigue`).
- The ICD-10-CM table only searches the code by default; the adapter adds `sf=code,name`, so both `G93.3` and `chronic fatigue` work.
- `primary_label` is the table's display text (LOINC: the long common name), `synonyms` the table's synonyms (conditions: consumer name and synonyms; HPO: synonym terms; ICD-11: index terms), `definitions` the HPO / ICD-11 definition, `parents` the HPO `is_a` ids, `categories` `["clinicaltables:<table>"]`, `confidence_score` 0.9.
- `source_data["CLINICALTABLES"]` holds the table name, the code and table specific fields (conditions: the ICD-10-CM / ICD-9-CM codes and info links; LOINC: component, property, method, data type, `isCopyrighted` and the terms-of-use URL; ICD-11: type, chapter, WHO foundation URI).

## Concept details

`get_concept_details(concept_id)` accepts `<PREFIX>:<code>` or a bare code it can recognise (ICD-10-CM shaped `G93.32` / `g9332`, LOINC shaped `70735-6`, an HPO id, a `C0015672` CUI). The service search is prefix based, so the adapter requests a page of 100 rows for the code and keeps only the **exact** code (`G93.3` is not in the billable-code table and returns `None`; `G93.32` is). Unknown or malformed ids return `None` without a request.

## Mappings and relationships

`get_mappings` uses the extra fields of the row itself:

| Table | Mappings |
|---|---|
| `conditions` | `ICD10CM` code(s) and the `ICD9CM` code (`mappingType="suggested_code"`), `MEDLINEPLUS` page URLs (`info_link`) |
| `hpo` | `xref` ids when present (the live data rarely has any) |
| `disease_names` | the `UMLS` CUI |
| `icd10cm`, `loinc_items`, `icd11_codes` | none |

The `conditions` table does **not** carry SNOMED CT or MeSH ids, and its ICD-10-CM suggestions are curated and older than the `icd10cm` table (it maps "Chronic fatigue syndrome" to `R53.82`, not `G93.32`); use the [NCI EVS adapter](ncievs_adapter.md) or the [MedlinePlus adapter](../literature/medlineplus_adapter.md) when you need SNOMED CT / MeSH. Some ICD-10-CM suggestions end in `?` (an episode-of-care placeholder for injury codes) and are returned as they are.

`get_relationships` returns the HPO `is_a` parents (`relation_label="is_a"`); no other CTSS table exposes a hierarchy.

## Rate limits, usage terms and caveats

Free, no key, no registration. NLM advises at most **25 requests/s** (a soft limit; check `X-RateLimit-Limit` / `Retry-After`; a 503 can happen under load) and asks you not to send PHI/PII in queries. The adapter spaces requests by 0.1 s and uses the shared HTTP retry and circuit breaker. A search over four tables is four requests.

- Errors in one table are logged and the other tables still answer; `get_concept_details` returns `None` on errors, mappings / relationships `[]`.
- Unknown `ef=` field names are silently returned as `null` by the service, so a wrong field never fails; the adapter only requests the fields documented per table.
- LOINC: using LOINC content is subject to the LOINC Terms of Use and some items have an additional external copyright (`source_data["CLINICALTABLES"]["isCopyrighted"]`, for example the FACIT questionnaires). The service holds surveys and forms as well as laboratory observations.
- Datasets are refreshed regularly (the index page lists the data version of each table); ICD-10-CM here is the CDC release the service currently serves (labelled 2027 on 2026-10-08).

## Live verification (2026-10-08)

Every table, query parameter and response shape above was checked against the live service before the parser was written, and the fixtures in `tests/fixtures/clinicaltables_responses.py` are real answers recorded through the adapter. `python -m knowledge_lookup check CLINICALTABLES` passes (search "fatigue", first hit `ICD10CM:R53.83 Other fatigue`).

Measured latency from the development machine: 0.35 - 0.5 s per request (one LOINC query took 3.0 s); a three-row answer is 100 B - 1.5 KB, the largest answers (ICD-11 with definition and index terms) a few KB. Findings that shaped the adapter: the ICD-10-CM table needs `sf=code,name` for names, dot-less codes do not match, lower case does, unknown `ef` fields come back `null`, `maxList` is capped at 500 and `count`/`offset` page up to 7,500 rows, the `conditions` table has no SNOMED CT / MeSH ids (only ICD-10-CM, ICD-9-CM and MedlinePlus links).

## See also

- [ICD-10-GM adapter](icd10gm_adapter.md) (German modification), [ICD-11 adapter](icd11_adapter.md), [LOINC adapter](loinc_adapter.md), [HPO adapter](../phenotypes/hpo_adapter.md)
- [NCI EVS adapter](ncievs_adapter.md), [MedlinePlus adapter](../literature/medlineplus_adapter.md)
- [All adapters](../README.md)
