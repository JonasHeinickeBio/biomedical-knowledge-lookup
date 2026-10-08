---
description: NCI Thesaurus, NCI Metathesaurus and other terminologies (SNOMED CT, ICD-10-CM, LOINC, MedDRA, ...) via the keyless NCI EVS REST API, with synonyms, definitions, roles, associations and cross-references.
---

# NCI Thesaurus (EVS) adapter

Reads the NCI Thesaurus (NCIt) and its sister terminologies from the National Cancer Institute's Enterprise Vocabulary Services (EVS). NCIt is a large biomedical reference terminology (diseases, findings, drugs, genes, anatomy, study and assessment concepts such as CTCAE and PROMIS items); the **NCI Metathesaurus** (`ncim`) is a UMLS-style hub that links the codes of dozens of sources to one concept, which makes it a convenient way to get SNOMED CT, MeSH, ICD-10-CM, LOINC, HPO and OMIM codes for the same idea. The adapter returns concepts with synonyms, definitions and semantic types, typed relationships (hierarchy, roles, associations) and mappings.

| | |
|---|---|
| Source | `KnowledgeSource.NCIEVS` |
| Class | `knowledge_lookup.adapters.NCIEVSAdapter` |
| Requires | none (no key, no registration) |
| Identifiers | `NCIT:C3036` (or bare `C3036`), `NCIM:C0015674` (or a bare CUI `C0015674` / `CL...`), and `<terminology>:<code>` such as `SNOMEDCT_US:52702003`, `ICD10CM:G93.32` |
| Upstream API | `https://api-evsrest.nci.nih.gov/api/v1` |
| Licence | see below: NCIM, SNOMED CT and MedDRA carry restrictions |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import NCIEVSAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with NCIEVSAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue syndrome", limit=3):
            print(c.primary_id, c.primary_label, c.concept_type, c.semantic_types)

        cfs = await adapter.get_concept_details("NCIT:C3037")
        print(cfs.primary_label, cfs.synonyms[:3], cfs.parents)

        for r in (await adapter.get_relationships("NCIT:C3037"))[:3]:
            print(r["relation_label"], r["related_id"], r["related_name"])

        wanted = {"MESH", "SNOMEDCT", "ICD10CM", "UMLS"}
        for m in await adapter.get_mappings("NCIT:C3037"):
            if m["toSource"] in wanted and m["mappingType"] == "xref":
                print(m["toSource"], m["toId"], m.get("via", "direct"))

        # the same idea in SNOMED CT
        for c in await adapter.search_concepts("chronic fatigue syndrome", 2, terminology="snomedct_us"):
            print(c.primary_id, c.primary_label)


asyncio.run(main())
```

Output:

```
NCIT:C3037 Chronic Fatigue Syndrome DISEASE ['Disease or Syndrome']
NCIT:C227796 Chronic Fatigue Syndrome Primary Factor Question UNKNOWN ['Intellectual Product']
NCIT:C39574 Autoimmune Lymphoproliferative Syndrome with FAS Mutation DISEASE ['Disease or Syndrome']
Chronic Fatigue Syndrome ['Myalgic encephalomyelitis/chronic fatigue syndrome', 'Myalgic Encephalomyelitis'] ['NCIT:C3131']
is_a NCIT:C3131 Immunodeficiency Syndrome
Disease_Has_Primary_Anatomic_Site NCIT:C12735 Immune System
Concept_In_Subset NCIT:C191200 ACC/AHA Cardiovascular and Noncardiovascular Complications of COVID-19 Terminology
UMLS C0015674 direct
ICD10CM G93.32 NCIM:C0015674
ICD10CM R53.82 NCIM:C0015674
ICD10CM G93.31 NCIM:C0015674
MESH D015673 NCIM:C0015674
SNOMEDCT 52702003 NCIM:C0015674
SNOMEDCT 51771007 NCIM:C0015674
SNOMEDCT_US:52702003 Chronic fatigue syndrome
SNOMEDCT_US:10692761000119107 Asthma-chronic obstructive pulmonary disease overlap syndrome
```

(The unrelated hits are real: EVS `contains` search matches any concept containing the words and ranks by its own score; use `search_type="match"` or `"startsWith"` for stricter matching.)

## Terminologies and ids

`terminology` defaults to `ncit` and can be set per call (`search_concepts(..., terminology="ncim")`, `get_concept_details("G93.32", terminology="icd10cm")`) or by a prefix in the id. The prefix is the EVS terminology name, case-insensitive; `SNOMEDCT` / `SNOMED` map to `snomedct_us`, `LOINC` to `lnc`, `MEDDRA` to `mdr`. The latest versions on 2026-10-08 were NCIt 26.09d and NCIM 202608; `GET /metadata/terminologies` lists the rest (`snomedct_us`, `icd10cm`, `icd10`, `icd9cm`, `lnc`, `mdr`, `hgnc`, `go`, `chebi`, `radlex`, `ctcae5`, `ctcae6`, `medrt`, ...). Ids are `<TERMINOLOGY>:<code>` in upper case (`NCIT:C3036`, `NCIM:C0015672`, `SNOMEDCT_US:52702003`). A bare id is read as NCIt, except a bare 7-digit CUI (`C0015672`) or local NCIM id (`CL412928`), which goes to NCIM; an explicit `terminology=` always wins over that guess. Malformed ids return `None` / `[]` without a request.

## Searching

`search_concepts(query, limit=20, *, terminology=None, search_type="contains")` calls `concept/<terminology>/search?term=..&include=summary&pageSize=<limit>` (page size capped at 100). `search_type` is the EVS `type` parameter: `contains` (default), `match`, `startsWith`, `phrase`, `AND`, `OR` or `fuzzy`.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `NCIT:C3036` / the preferred name |
| `synonyms` | all synonym names (NCIt `FULL_SYN`, NCIM per-source terms), minus the label |
| `definitions` | the NCI definition first, then alternative definitions; HTML (NCIM carries whole MedlinePlus pages) is converted to text |
| `semantic_types` | the `Semantic_Type` properties, e.g. `Sign or Symptom`, `Disease or Syndrome` |
| `concept_type` | from the semantic type: diseases and syndromes `DISEASE`, `Sign or Symptom` `SYMPTOM`, `Finding` `OBSERVATION`, genes, proteins, drugs, procedures, anatomy and so on; otherwise `UNKNOWN` |
| `identifiers` | the concept itself plus cross-references that are also sources here: `UMLS` CUI (NCIt property `UMLS_CUI`, other terminologies `NCI_META_CUI`), and on NCIM `MESH`, `SNOMEDCT`, `LOINC`, `OMIM`, `HPO`, `MEDLINEPLUS`, ... |
| `categories` | `[terminology]` |
| `confidence_score` | 0.9; 0.3 for inactive (retired) concepts |
| `source_data[NCIEVS]` | terminology, code, version, `active`, `leaf`, concept status |

## Concept details, relationships

`get_concept_details` adds `parents` and `children` (as prefixed ids) to the summary.

`get_relationships(concept_id)` fetches parents, children, roles, inverse roles, associations and inverse associations in one call:

| `relation_label` | `direction` | Meaning |
|---|---|---|
| `is_a` | outgoing | related concept is a parent (superclass) |
| `has_subclass` | incoming | related concept is a child |
| NCIt role types, e.g. `Disease_Has_Primary_Anatomic_Site`, `Disease_May_Have_Finding` | outgoing (roles) / incoming (inverse roles) | description-logic roles |
| NCIt association types, e.g. `Concept_In_Subset`, `Has_PCDC_HL_Authorized_Value` | outgoing / incoming | associations, including value-set membership |
| NCIM `RELA` qualifier (`measures`, `Concept_In_Subset`, ...) or `related_to` / `possibly_related_to` / `broader_than` / `narrower_than` for the `RO` / `RQ` / `RB` / `RN` types | outgoing | relationships asserted by individual sources (key `asserted_by`) |

Entries also carry `related_id`, `related_name`, `source="NCIEVS"` and `direction`. Incoming role/association lists are capped at 100 each (`ncievs_adapter.MAX_INVERSE`): Fatigue has 93 inverse roles, bigger concepts more. Outgoing lists are returned in full (Fatigue in NCIM has 241 associations).

## Mappings

`get_mappings(concept_id)` combines

1. the concept's `maps`: for NCIt, concept-to-code maps (`targetCode` in MedDRA, GDC, ...; type `Has Synonym` confidence 0.9, others 0.6); for NCIM, the **SNOMED CT to ICD-10-CM / ICD-10 rule maps** of its constituent concepts (`fromId="SNOMEDCT_US:52702003"`, `toSource="ICD10CM"`, with `rank`, `rule`, `mapset`; rank 1 confidence 0.8, otherwise 0.6),
2. identifier properties: the UMLS CUI, OMIM number, CAS registry number, UNII, Entrez Gene id, ChEBI id, HGNC id, UniProt (Swiss-Prot) id, ... and `oboInOwl:hasDbXref` entries such as `IMDRF:E2312`,
3. on NCIM, the **code-bearing synonyms** of MeSH (`MSH`), SNOMED CT, ICD-10-CM, ICD-10, ICD-9-CM, LOINC, OMIM, HPO, MedlinePlus (the numeric topic id), MedDRA, RxNorm, Orphanet and NCIt (`mappingType="xref"`, confidence 0.9). Metathesaurus-generated placeholder codes (`MTHU...`) are skipped.

NCIt itself exposes the UMLS CUI but not the SNOMED/MeSH/ICD codes, so for an NCIt concept with a CUI the adapter reads the NCIM concept of that CUI as well (**one extra request**) and adds its mappings, marked with `via="NCIM:C0015674"`. If that extra request fails, the NCIt mappings are returned alone. A MedlinePlus code from NCIM (for example `5324` for Fatigue) is the numeric health-topic id of the [MedlinePlus adapter](../literature/medlineplus_adapter.md).

## Rate limits, usage terms and caveats

EVS publishes no numeric rate limit; the adapter spaces requests by 0.1 s and uses the shared HTTP retry and circuit breaker. Errors and unknown ids are logged (a 404 only at info level); search returns `[]`, details `None`, relationships and mappings `[]`.

**Licences.** The terminology metadata the API serves (`/metadata/terminologies`, checked 2026-10-08) says: the NCI Metathesaurus "includes various sources, some of which are proprietary and included, by permission, for non-commercial use only"; SNOMED CT is allowed inside EVS but "requires licensing for other purposes"; MedDRA is "licensed for NCI work" and other uses are prohibited without a MedDRA subscription. The NCI Thesaurus entry carries no licence text. Treat anything beyond `ncit` as research / non-commercial use and check the source licences before redistributing concepts.

- `include=full` and `include=summary,...` return many fields; the adapter asks only for what each method needs. A NCIM concept like Fatigue is 70 - 110 kB with summary + associations.
- An invalid `include` value is a 400, an unknown terminology a 404; neither is retried.
- NCIt `synonyms` mix many source vocabularies (CTCAE, CDISC, FDA, ...), so a concept can carry many near-identical labels.

## Live verification (2026-10-08)

All endpoints, include values and shapes above were read live (NCIt 26.09d: 438 `contains` hits for "fatigue", NCIM 202608: 1,140). `python -m knowledge_lookup check NCIEVS` passes (search "fatigue", details of the first hit, relationships). Latency 0.5 - 0.9 s per request, 2.2 s for the largest `include=full` NCIM answer (112 kB). The fixtures in `tests/fixtures/ncievs_responses.py` are real answers recorded through the adapter; long lists were trimmed (every code-bearing NCIM synonym was kept).

## See also

- [Clinical Tables adapter](clinicaltables_adapter.md) (ICD-10-CM, LOINC items), [SNOMED CT adapter](snomedct_adapter.md), [MeSH adapter](mesh_adapter.md), [LOINC adapter](loinc_adapter.md)
- [MedlinePlus adapter](../literature/medlineplus_adapter.md)
- [All adapters](../README.md)
