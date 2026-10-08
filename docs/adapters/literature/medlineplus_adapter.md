---
description: MedlinePlus plain-language health topics by text search, URL slug or ICD-10-CM / SNOMED CT / ICD-9-CM / LOINC / RxNorm code (MedlinePlus Connect), with related topics, groups and MeSH links.
---

# MedlinePlus adapter

Gives the **patient-facing** explanation of a condition, symptom, test or drug from the U.S. National Library of Medicine's MedlinePlus. Two keyless services are combined: the health-topic web service (text search, full topic records) and MedlinePlus Connect (code in, MedlinePlus page out). Typical uses are a plain-language summary next to a coded concept in a registry, a patient-information link for an ICD-10-CM / SNOMED CT code, and the MeSH heading of a topic.

> **Audience.** MedlinePlus summaries are written for patients and families (consumer language, roughly 8th-grade reading level). They are not clinical definitions or terminology; concept types are coarse heuristics (see below). Combine them with the coded sources ([ICD-10-GM](../ontologies/icd10gm_adapter.md), [SNOMED CT](../ontologies/snomedct_adapter.md), [NCI EVS](../ontologies/ncievs_adapter.md), [Clinical Tables](../ontologies/clinicaltables_adapter.md)).

| | |
|---|---|
| Source | `KnowledgeSource.MEDLINEPLUS` |
| Class | `knowledge_lookup.adapters.MedlinePlusAdapter` |
| Requires | none (no key, no registration) |
| Identifiers | a topic slug or URL: `MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome`, `fatigue`, `https://medlineplus.gov/fatigue.html`, Spanish `spanish/fatigue`; a code: `ICD10CM:G93.32` (or bare `G93.32`), `SNOMEDCT:52702003`, `ICD9CM:780.71`, `LOINC:2951-2` (or bare), `RXNORM:861004`, `NDC:<code>` |
| Upstream APIs | `https://wsearch.nlm.nih.gov/ws/query` (health-topic search), `https://connect.medlineplus.gov/service` (MedlinePlus Connect) |
| Environment | `MEDLINEPLUS_EMAIL` (optional, see below) |
| Licence | see "Usage terms" |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MedlinePlusAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MedlinePlusAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue syndrome", limit=3):
            print(c.primary_id, "|", c.primary_label, "|", c.concept_type)

        topic = await adapter.get_concept_details("ICD10CM:G93.32")   # code -> patient page
        print(topic.primary_id, topic.synonyms[:3], topic.categories)
        print(topic.definitions[0][:160].replace("\n", " "))

        for r in await adapter.get_relationships(topic.primary_id):
            print(r["relation_label"], r["related_id"], r["related_name"])

        for m in await adapter.get_mappings("ICD10CM:G93.32"):
            print(m["fromId"], "->", m["toSource"], m["toId"])

        # all pages for a code: topics, lab-test pages, drug pages
        for c in await adapter.concepts_for_code("LOINC", "2951-2"):
            print(c.primary_id, c.concept_type)


asyncio.run(main())
```

Output:

```
MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome | Myalgic Encephalomyelitis/Chronic Fatigue Syndrome | DISEASE
MEDLINEPLUS:fatigue | Fatigue | SYMPTOM
MEDLINEPLUS:postcovidconditionslongcovid | Post-COVID Conditions (Long COVID) | DISEASE
MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome ['CFS', 'Chronic fatigue syndrome', 'ME/CFS'] ['Bones, Joints and Muscles', 'Infections']
What is myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS)?  Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is a serious, long-term illnes
related_topic MEDLINEPLUS:fatigue Fatigue
member_of_group MEDLINEPLUS_GROUP:10 Bones, Joints and Muscles
member_of_group MEDLINEPLUS_GROUP:12 Infections
has_translation MEDLINEPLUS:spanish/myalgicencephalomyelitischronicfatiguesyndrome Encefalomielitis miálgica/Síndrome de fatiga crónica
primary_institute http://www.ninds.nih.gov/ National Institute of Neurological Disorders and Stroke
ICD10CM:G93.32 -> MEDLINEPLUS MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome
MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome -> MESH D015673
MEDLINEPLUS:lab-tests/electrolyte-panel OBSERVATION
MEDLINEPLUS:lab-tests/sodium-blood-test OBSERVATION
```

## Searching

`search_concepts(query, limit=20)` calls the health-topic web service (`db=healthTopics&rettype=topic`) once and returns the ranked topics as full records (page size capped at 50, since a topic record is 15 - 40 kB). The query is passed through, so the service's field limiters work: `title:asthma`, `alt-title:`, `mesh:`, `full-summary:`, `group:"Symptoms"`; words are AND-ed and `OR` is supported. Only English topics are searched; Spanish topics are reachable by slug (`spanish/...`).

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `MEDLINEPLUS:<url slug>` / the topic title |
| `synonyms` | the "Also called" terms and see-references (`CFS`, `ME/CFS`, `SEID`, ...) |
| `definitions` | `[plain-text summary]` (HTML converted; headings and lists become lines) |
| `categories` | the topic groups (`Symptoms`, `Infections`, `Bones, Joints and Muscles`, ...) |
| `related` | related topic ids |
| `identifiers` | `MEDLINEPLUS` numeric topic id (`89`) with the page URL, `MESH` descriptor ids |
| `concept_type` | heuristic: group `Symptoms` -> `SYMPTOM`; groups `Drug Therapy`, `Complementary and Alternative Therapies`, `Surgery and Rehabilitation`, `Transplantation and Donation` -> `TREATMENT`; `Diagnostic Tests` -> `PROCEDURE`; otherwise `DISEASE` |
| `source_data[MEDLINEPLUS]` | topic id, URL, language, meta description, groups, MeSH, primary NIH institute, number of external links, audience note and the attribution text |

## Concept details

`get_concept_details(concept_id)` resolves

- a **slug or URL** (`fatigue`, `MEDLINEPLUS:fatigue`, `https://medlineplus.gov/fatigue.html?utm_source=x`, `spanish/fatigue`): the web service has no id lookup, but a query for the slug ranks the page first; the adapter requests 10 hits (second try: the quoted URL) and keeps the hit whose URL slug matches exactly. The numeric topic id (`89`) cannot be searched and is **not** accepted as an id;
- a **code** (`ICD10CM:G93.32`, `SNOMEDCT:52702003`, `ICD9CM:780.71`, `LOINC:2951-2`, `RXNORM:861004`, `NDC:...`; bare ICD-10-CM and LOINC codes are recognised): MedlinePlus Connect returns the matching pages and the adapter returns the first one. Health-topic pages are upgraded to the full topic record with one more web-service call; lab-test (`lab-tests/...`) and drug (`druginfo/...`) pages stay Connect entries (title, summary, URL) and cannot be re-fetched by slug. `concepts_for_code(system, code, language="en")` returns all pages (ICD-10-CM `G93.31` gives *Fatigue*, *Neurologic Diseases* and *Viral Infections*; `LOINC:2951-2` gives the *Electrolyte Panel* and *Sodium Blood Test* pages; `RXNORM:861004` the *Metformin* drug page and *Diabetes Medicines*).

`source_data[MEDLINEPLUS]["matched_code"]` records the code that led to a page. Codes without a MedlinePlus page (`ICD10CM:ZZZ99`) give `None`.

Connect's coverage: ICD-10-CM `2.16.840.1.113883.6.90`, ICD-9-CM `...6.103`, SNOMED CT `...6.96` (focused on the CORE Problem List subset and its descendants), LOINC `...6.1`, RxNorm `...6.88`, NDC `...6.69` (accepted per documentation; no hit was exercised live). Connect silently treats an **unknown OID as ICD-9-CM**, so the adapter only ever sends these six. It is designed for the US health care system; ICD-10-GM codes are not supported.

## Relationships and mappings

`get_relationships(concept_id)` (slug, URL or code id) returns

| `relation_label` | `related_id` |
|---|---|
| `related_topic` | `MEDLINEPLUS:<slug>` of each related health topic |
| `member_of_group` | `MEDLINEPLUS_GROUP:<group id>` (with the group page `url`) |
| `has_translation` | `MEDLINEPLUS:spanish/<slug>` (with `language`) |
| `primary_institute` | the lead NIH institute's URL, with its name |

`get_mappings(concept_id)` returns the topic's **MeSH descriptors** (`toSource="MESH"`, e.g. `D015673` Fatigue Syndrome, Chronic; `mappingType="mesh_heading"`) and, when the id is a code, the Connect match `ICD10CM:G93.32 -> MEDLINEPLUS:...` (`connect_match`). MedlinePlus cannot be asked in reverse ("which codes point to this topic"), so a slug id gives MeSH only; the [NCI EVS adapter](../ontologies/ncievs_adapter.md) can supply ICD-10-CM / SNOMED CT codes for the same idea (its NCI Metathesaurus record lists the numeric MedlinePlus topic id, for example `5324` for Fatigue).

## Usage terms, rate limits and caveats

Free, no key. From [MedlinePlus: Linking to and using content](https://medlineplus.gov/about/using/usingcontent/) and the web-service / Connect pages:

- Topic summaries, medical-test pages and several other areas are US-government works in the public domain. A.D.A.M. encyclopedia articles and the ASHP drug monographs (the drug pages Connect returns for RxNorm / NDC codes) are **copyrighted**; do not ingest or re-brand them.
- Acknowledge the source, for example "Courtesy of MedlinePlus from the National Library of Medicine"; do not use the MedlinePlus logo or imply endorsement. Concepts carry this text in `source_data`.
- Limits: **85 requests/minute** (web service) and **100 requests/minute** (Connect) per IP address; an IP over the Connect limit is blocked for 300 s. NLM recommends caching results for 12 - 24 hours (data updates Tuesday - Saturday). The adapter spaces requests by 0.8 s per service and does not cache; cache upstream if you loop over many codes. One code lookup is one Connect request plus up to two web-service requests per health-topic page.
- The web service accepts optional `tool` and `email` parameters for NLM to contact heavy users. The adapter always sends `tool=biomedical-knowledge-lookup` and sends `email` only when `MEDLINEPLUS_EMAIL` is set; nothing else identifying is sent.
- The adapter refuses XML answers that declare a DTD/entity. Errors are logged; search returns `[]`, details `None`, relationships and mappings `[]`.

Known gaps: lookup by the numeric topic id is not possible (the service cannot search ids); only English topic search is exposed (`spanish/<slug>` ids resolve through the Spanish database; Spanish Connect output is available via `concepts_for_code(..., language="es")`); topics are tagged with a coarse `ConceptType` only.

## Live verification (2026-10-08)

Endpoints, parameters, OIDs and shapes were checked live before coding; `python -m knowledge_lookup check MEDLINEPLUS` passes (search "chronic fatigue syndrome", details, relationships). Observed: the web service answers in 0.5 - 1.6 s (a `rettype=topic` answer with 2 - 3 topics is 29 - 70 kB), Connect in 0.35 - 1.1 s (a topic entry 8 kB, the lab-test pages for one LOINC code 32 kB); the first slug lookup of a topic costs one web-service request (1 - 2.6 s including spacing). `ICD10CM:G93.32`, `SNOMEDCT:52702003` and `ICD9CM:780.71` all give the ME/CFS page; `ICD10CM:U09.9` gives *COVID-19*; `G93.31` three pages. The fixtures in `tests/fixtures/medlineplus_responses.py` are real answers recorded through the adapter, with site lists dropped and long summaries cut.

## See also

- [Clinical Tables adapter](../ontologies/clinicaltables_adapter.md) (its `conditions` table links to MedlinePlus pages), [NCI EVS adapter](../ontologies/ncievs_adapter.md), [MeSH adapter](../ontologies/mesh_adapter.md)
- [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
