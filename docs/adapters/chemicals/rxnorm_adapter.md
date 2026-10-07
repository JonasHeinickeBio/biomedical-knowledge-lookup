---
description: NLM RxNorm drug concepts (ingredients, brands, clinical drugs, dose forms) and relations, with ATC, DrugBank, SNOMED CT, UNII and NDC links.
---

# RxNorm adapter

Resolves drug names to RxNorm concept unique identifiers (RxCUIs) through the keyless NLM RxNav service, walks the ingredient / brand / clinical drug / dose form graph, and maps an RxCUI to codes in other vocabularies. The main use is harmonising registry medications: a free-text entry such as "Advil" or "ibuprofen 200 mg" becomes an RxCUI, from there an ingredient, an ATC code, a DrugBank id and (for products) NDCs. For ATC *classes* (hierarchy, members) use the [RxClass adapter](rxclass_adapter.md).

| | |
|---|---|
| Source | `KnowledgeSource.RXNORM` |
| Class | `knowledge_lookup.adapters.RxNormAdapter` |
| Requires | none |
| Identifiers | RxCUI: `1191`, `RXCUI:1191` or `RxNorm:1191` |
| Upstream API | `https://rxnav.nlm.nih.gov/REST` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import RxNormAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with RxNormAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("Advil", limit=3):
            print(c.primary_id, c.primary_label, c.categories)   # 153010 Advil ['tty:BN']

        for rel in await adapter.get_relationships("153010", limit=3):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])

        for m in await adapter.get_mappings("5640"):             # ibuprofen
            print(m["toSource"], m["toId"])

        print(await adapter.get_ndc("243670"))                   # aspirin 81 MG Oral Tablet


asyncio.run(main())
```

Output (live, October 2026):

```
153010 Advil ['tty:BN']
tradename_of 5640 ibuprofen
has_branded_drug 153008 ibuprofen 200 MG Oral Tablet [Advil]
has_branded_drug 206878 ibuprofen 20 MG/ML Oral Suspension [Advil]
ATC C01EB16 / DrugBank DB01050 / SNOMEDCT 38268001 / UNII WK2XYI10QM / VUID 4017840 ...
['21130048112', '21130048120', '21130048132', '21130048150', '71800004002', '84324001701']
```

## Concepts and term types

Every concept is an RxCUI with a term type (`tty`), kept in `categories` as `tty:IN` and in `semantic_types` as a readable label. `concept_type` is `DRUG`.

| TTY | Meaning | Example |
|---|---|---|
| `IN` | ingredient | `1191` aspirin |
| `PIN` | precise ingredient (salt/ester form) | `314293` acetylsalicylate sodium |
| `MIN` | multiple ingredients | aspirin / caffeine |
| `BN` | brand name | `153010` Advil |
| `SCD` / `SBD` | semantic clinical / branded drug (ingredient + strength + dose form) | `243670` aspirin 81 MG Oral Tablet |
| `SCDC`, `SBDC`, `SCDF`, `SBDF`, `SCDG`, `SBDG` | components, forms and groups | `316074` ibuprofen 200 MG |
| `DF` | dose form | `317541` Oral Tablet |
| `GPCK` / `BPCK` | generic / branded packs | |

## Searching

`search_concepts(query, limit)` tries three strategies and returns the first that finds something:

1. **Exact** (`rxcui.json?name=...&search=2`): normalised exact match, which also resolves brand names (`Advil` -> `153010`). `confidence_score` 0.95. One request plus one `properties` call per hit.
2. **Contains** (`drugs.json?name=...`): every concept whose name contains the query, grouped by term type; results are sorted ingredient, precise ingredient, brand, multiple ingredient, clinical drug, branded drug, and so on. `confidence_score` 0.7.
3. **Fuzzy** (`approximateTerm.json`): for misspellings (`fluoxetin` -> fluoxetine). Candidates with a score below 10 are dropped (`chronic fatigue` scores 7.9 against "chromic chloride"; `asprin` also falls under the threshold and returns nothing), at most five are resolved. `confidence_score` 0.6, the score is in `source_data["RXNORM"]["approximate_score"]`.

An RxCUI query (`1191`, `RxNorm:1191`) returns that concept. Search by drug name only: symptom or indication text is not searchable here (use [openFDA labels](openfdalabels_adapter.md)).

## Concept details

`get_concept_details("1191")` calls `rxcui/{id}/properties.json`. Unknown or retired RxCUIs answer `{}` and return `None`.

| Field | Value |
|---|---|
| `primary_label` | RxNorm name, e.g. `aspirin 81 MG Oral Tablet` |
| `synonyms` | the RxNorm synonym when it differs (`ASA 81 MG Oral Tablet`) |
| `categories` / `semantic_types` | `tty:SCD` / `clinical drug` |
| `identifiers` | `RXNORM` (with RxNav link), plus `UMLS` when RxNorm lists a CUI (often empty) |
| `source_data[RXNORM]` | the raw properties (`tty`, `language`, `suppress`, `umlscui`) |

## Relationships

`get_relationships(concept_id, limit=25)` uses one `rxcui/{id}/related.json?tty=...` call (plus the properties call that tells the term type). `limit` caps each relation label, because an ingredient has hundreds of products.

| From | Label | To |
|---|---|---|
| IN | `has_tradename` | BN |
| IN | `has_form` | PIN |
| IN, MIN | `ingredient_of` | SCD, SBD |
| MIN | `has_tradename` | BN |
| PIN | `form_of` | IN |
| BN | `tradename_of` | IN |
| BN | `has_branded_drug` | SBD |
| SCD | `has_ingredient` / `has_dose_form` / `has_tradename` | IN / DF / SBD |
| SBD | `has_ingredient` / `has_dose_form` / `has_brand_name` / `tradename_of` | IN / DF / BN / SCD |

Every edge also has `tty` and `source` (`RxNorm`). `has_tradename`, `ingredient_of`, `has_dose_form`, `tradename_of` and `form_of` are RxNorm's own relation names (verified with `related.json?rela=`); `has_branded_drug`, `has_brand_name` and `has_ingredient` are this adapter's names for the reverse direction. Other term types (components, forms, groups, packs, dose forms) return `[]`: a dose form relates to thousands of drugs.

Note that an ingredient's brands include brands of *combination* products that contain it (aspirin lists Pamprin Max Formula, BC Arthritis, Excedrin PM ...). Filter on the SBD names if you need single-ingredient brands.

## Mappings

`get_mappings(concept_id)` reads `rxcui/{id}/allProperties.json?prop=codes`:

| Code in RxNorm | `toSource` | Notes |
|---|---|---|
| `DRUGBANK` | `DrugBank` | ingredients |
| `UNII_CODE` | `UNII` | ingredients |
| `SNOMEDCT` | `SNOMEDCT` | often two codes (substance and medicinal product) |
| `ATC` | `ATC` | level 5 codes, `mappingType` `atc_code`; aspirin has A01AD05, B01AC06, N02BA01 |
| `VUID`, `USP`, `HCPCS`, `GFC`, `GCN_SEQNO`, `HIC_SEQN`, `CVX` | same | when present |
| `umlscui` property | `UMLS` | confidence 0.9, usually empty |

Not mapped on purpose: SPL set ids (an ingredient carries up to ~1,000 of them; ibuprofen's response is 150 KB; use the [openFDA labels adapter](openfdalabels_adapter.md)) and Multum (`MMSL_CODE`) codes. **MeSH is not served**: RxNav's `idtypes.json` lists no MeSH type, so there is no MeSH mapping (use [MeSH](../ontologies/mesh_adapter.md) by name, or the ClinPGx adapter, which carries MeSH ids for drugs). Mapping rows have `fromSource` `RxNorm`. The codes response is cached on the adapter (64 RxCUIs).

## NDC helper

`await adapter.get_ndc(rxcui)` returns the 11-digit NDCs (`rxcui/{id}/ndcs.json`). NDCs exist only for product-level concepts: `243670` (SCD) returns six, while ingredients and brands (`1191`, `153010`) return `[]`. To go from a registry entry to NDCs, take the SCD/SBD RxCUIs from `get_relationships`.

## Rate limits, speed and quirks

- RxNav allows 20 requests/s per IP; calls are spaced to about 16/s. Measured latency was 0.3 to 9 seconds per call (the service is sometimes slow, especially the first call after idling), so the request timeout floor is 30 s.
- Every path must end in `.json`; without it RxNav returns XML whatever `Accept` says. "No match" is HTTP 200 with `{}` or an empty group, not 404.
- `check RXNORM` (default query `aspirin`) passes: search, details, 76 relationship edges and mappings.
- RxNorm is a US National Library of Medicine product, free to use; some source vocabularies it links to are licensed separately (see the [RxNorm terms](https://www.nlm.nih.gov/research/umls/rxnorm/)).

## See also

- [RxClass adapter](rxclass_adapter.md) for ATC classes and class membership
- [openFDA labels adapter](openfdalabels_adapter.md), [DrugBank adapter](drugbank_adapter.md), [ClinPGx adapter](clinpgx_adapter.md)
- [All adapters](../README.md)
