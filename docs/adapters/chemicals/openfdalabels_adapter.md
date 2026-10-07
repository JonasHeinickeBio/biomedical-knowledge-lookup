---
description: FDA structured drug labels (DailyMed SPL) via openFDA - indications, boxed warnings, contraindications, adverse reactions, interactions - plus UNII, RxCUI, NDC and pharmacologic classes.
---

# openFDA drug labels (DailyMed) adapter

Searches the openFDA drug label endpoint, which mirrors the structured product labels (SPL) published on DailyMed. A concept is one drug label; the label's text sections (indications, boxed warning, contraindications, adverse reactions, drug interactions, dosage ...) stay available, and an `openfda` block links each label to substances (UNII), products (RxCUI, NDC) and pharmacologic classes. Good for questions such as "what does the approved US label say about fatigue as an adverse reaction", "which labels carry a boxed warning", "which labels list this indication".

| | |
|---|---|
| Source | `KnowledgeSource.OPENFDALABELS` |
| Class | `knowledge_lookup.adapters.OpenFDALabelsAdapter` |
| Requires | none; optional `OPENFDA_API_KEY` (or `api_keys["openfda"]`) raises the daily quota |
| Identifiers | SPL set id (UUID), e.g. `0058175f-3474-40c3-a046-6cfaec86d84b`; `DAILYMED:<set id>` accepted |
| Upstream API | `https://api.fda.gov/drug/label.json` |

## How it differs from openFDA events and DrugBank

| | openFDA labels (this adapter) | [openFDA events](openfdaevents_adapter.md) | [DrugBank](drugbank_adapter.md) |
|---|---|---|---|
| Content | what the manufacturer's approved US label *states* (regulatory text) | spontaneous adverse event *reports* (FAERS), unverified, reporting-biased | curated drug knowledge base (targets, pharmacology, interactions) |
| Unit | a label (per product / manufacturer) | a patient report | a drug |
| Use for | indications, contraindications, boxed warnings, labelled adverse reactions, label interactions | signal detection, counts of reported reactions | mechanism, targets, drug-drug interaction network |
| Access | keyless | keyless | key / licence |

A reaction that is in the label is *expected*; one that is frequently reported but absent from the label is a candidate signal. Combine the two (and RxNorm for harmonised ingredient names) for pharmacovigilance-style reasoning. Labels are per product, so one ingredient has hundreds of labels (aspirin: 695; bupropion: 245).

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OpenFDALabelsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OpenFDALabelsAdapter(LookupConfig()) as adapter:
        label = (await adapter.search_concepts("bupropion", limit=1))[0]
        print(label.primary_id, label.primary_label, label.categories)

        boxed = await adapter.get_label_section(label.primary_id, "boxed warning")
        print(boxed[:70])

        for r in (await adapter.get_relationships(label.primary_id))[:2]:
            print(r["relation_label"], r["related_id"], r["unii"])

        for hit in await adapter.search_concepts("fatigue", limit=3):   # indication text
            print(hit.primary_label)


asyncio.run(main())
```

Output (live, October 2026):

```
004d8121-59d4-46c4-acb8-b2dd097bf556 buPropion Hydrochloride XL ['HUMAN PRESCRIPTION DRUG', 'route:ORAL', 'boxed warning']
WARNING: SUICIDAL THOUGHTS AND BEHAVIORS SUICIDALITY AND ANTIDEPRESSANT DRUGS Antidepressants increa
has_ingredient BUPROPION HYDROCHLORIDE ZG7E5POY8O
has_rxnorm_product 993541 None
911 Adrenal Burnout and Fatigue
Miranda Castros Phosphorus 5 Cell Salts ...
STRESS / FATIGUE
```

## Searching

`search_concepts(query, limit)`:

1. Name search: `openfda.generic_name:"q" OR openfda.brand_name:"q" OR openfda.substance_name:"q"`. `aspirin` and `Advil` land here.
2. If that finds nothing, phrase search in `indications_and_usage:"q"`. `fatigue` finds 3,362 labels, mostly over-the-counter and homeopathic products that claim fatigue relief, not drugs that *cause* it; for adverse reactions fetch the `adverse_reactions` section of a known label instead (see below).
3. A set id returns that label.

Results come in the API's order, not ranked by relevance. The query is sanitised (quotes and backslashes removed) so it cannot alter the search expression. One call asks for at most 100 labels.

**Size warning.** openFDA has no field selection: every hit returns the whole label (18 KB for a short OTC label, around 170 KB for a prescription label; 3 bupropion labels were 530 KB). Keep `limit` small. The concept keeps only trimmed text, so memory is not an issue after the call, but the transfer is.

## Concept details

`get_concept_details(set_id)` searches `set_id:"..."` (limit 1).

| Field | Value |
|---|---|
| `primary_id` | SPL set id (stable across label versions) |
| `primary_label` | first brand name, else first generic name, else the start of the SPL product text (labels with an empty `openfda` block, e.g. old or homeopathic ones, get e.g. "Citalopram Hydrobromide citalopram hydrobromide ...") |
| `concept_type` | `DRUG` (semantic type `drug label`) |
| `synonyms` | other brand names, generic names, substance names |
| `categories` | product type (`HUMAN PRESCRIPTION DRUG`, `HUMAN OTC DRUG`), `route:ORAL`, `boxed warning` when present |
| `definitions` | the first 500 characters of the indications |
| `identifiers` | `OPENFDALABELS` set id with the DailyMed URL |
| `source_data[OPENFDALABELS]` | `set_id`, `spl_id` (this version), `version`, `effective_time`, the `openfda` fields, `sections` (see below), `sections_truncated`, `section_names` |

`sections` keeps nine sections, each cut to 1,500 characters: `indications_and_usage`, `boxed_warning`, `contraindications`, `warnings`, `warnings_and_cautions`, `precautions`, `adverse_reactions`, `drug_interactions`, `dosage_and_administration`. `sections_truncated` names those that were cut; `section_names` lists every text section the label has (including ones not kept, such as `clinical_studies`).

## Full label text: `get_label_section`

```python
text = await adapter.get_label_section(set_id, "adverse_reactions")
```

Fetches the label live and returns the full, untrimmed section (paragraphs joined by blank lines), or `None` for an unknown label or a section the label lacks (an OTC aspirin label has no `boxed_warning`). `section` is the openFDA field name or an alias: `boxed` / `black box`, `indications`, `dosage`, `interactions`, `adverse`, `side effects`, `warning`. Names are validated (`[a-z_]+`, no metadata fields). Nothing is cached, so large sections are not held in memory; for a bupropion XL label `adverse_reactions` is 11.6 kB.

## Relationships

`get_relationships(set_id, limit=25)` (one request; `limit` caps each label):

| Label | Target | Notes |
|---|---|---|
| `has_ingredient` | substance name | `related_id` is the `substance_name`. `unii` is set only when the label has exactly one substance and one UNII; `label_uniis` lists all UNIIs |
| `has_pharm_class` | class text, e.g. `Cyclooxygenase Inhibitors [MoA]` | `class_type` is `EPC` (established pharmacologic class), `MoA`, `PE` or `CS`; aspirin has six |
| `has_rxnorm_product` | RxCUI | product-level (SCD/SBD, e.g. `308416`), not the ingredient's RxCUI; resolve with the [RxNorm adapter](rxnorm_adapter.md) |

**Why UNIIs are not paired with names:** `openfda.substance_name` and `openfda.unii` are not index-aligned. An ibuprofen/acetaminophen label lists the names as [IBUPROFEN, ACETAMINOPHEN] and the UNIIs as [WK2XYI10QM, 362O9ITL9D] (acetaminophen first), and another label of the same product orders them differently. Pairing by position would silently mislabel ingredients. Labels with an empty `openfda` block have no relationships.

## Mappings

`get_mappings(set_id)` returns rows with `fromSource` `SPL`: `DailyMed` (page URL), `RxNorm` (product RxCUIs, `product_rxcui`), `UNII`, `NDC` (product NDCs `product_ndc`, plus up to 25 package NDCs `package_ndc`) and `FDA_APPLICATION` (NDA / ANDA / BLA / monograph numbers). To get from an RxCUI to labels, search by drug name; the endpoint also accepts `openfda.rxcui:"308416"`, but that field holds product-level RxCUIs only (an ingredient RxCUI such as `1191` finds nothing).

## Limits, quirks, terms

- Without a key: 240 requests/min and 1,000 requests/day per IP; with a key: 240/min and 120,000/day per key (documented at https://open.fda.gov/apis/authentication/). Requests are spaced at about 3.5/s. The key is sent as the `api_key` parameter and read from `OPENFDA_API_KEY` or `api_keys["openfda"]`. A typical session of searches stays far below 1,000 per day; a bulk job needs a key.
- No match is HTTP 404 `{"error": {"code": "NOT_FOUND"}}`; the adapter treats it as "no results".
- Section text is plain text with the label's own numbering; tables (`*_table` keys) are HTML and are not included in concepts.
- openFDA's disclaimer: do not rely on it for medical decisions; the data is unvalidated. Terms and licence: https://open.fda.gov/terms/ and https://open.fda.gov/license/ (the openFDA contribution is CC0; the label text is public FDA data).
- `check OPENFDALABELS` (default query `aspirin`) passes.

## See also

- [openFDA events adapter](openfdaevents_adapter.md), [RxNorm adapter](rxnorm_adapter.md), [DrugBank adapter](drugbank_adapter.md), [ClinPGx adapter](clinpgx_adapter.md)
- [All adapters](../README.md)
