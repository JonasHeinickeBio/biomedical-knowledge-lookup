---
description: Map drug and brand names to RxCUI and WHO ATC classes (and back) with NLM RxNav RxClass; harmonise registry medications to ATC.
---

# RxClass (ATC) adapter

Resolves a drug name (generic or brand) to its RxNorm ingredient RxCUI and to the WHO ATC classes RxClass assigns to it, and navigates the ATC tree. The main use is harmonising medication lists from patient registries to ATC. Keyless.

| | |
|---|---|
| Source | `KnowledgeSource.RXCLASS` |
| Class | `knowledge_lookup.adapters.RxClassAdapter` |
| Requires | none |
| Identifiers | RxCUI (`1191`, `RXCUI:1191`, `RxNorm:1191`) for drugs; ATC code (`N02BA`, `ATC:N02BA`) for classes; level 5 codes (`N02BA01`) resolve to the drug that carries them |
| Upstream API | `https://rxnav.nlm.nih.gov/REST/rxclass/` and RxNorm `https://rxnav.nlm.nih.gov/REST/` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import RxClassAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with RxClassAdapter(LookupConfig()) as adapter:
        # Name or brand -> ingredient RxCUI(s) with ATC classes (one request)
        for drug in await adapter.get_atc_for_drug("Advil"):
            print(drug["rxcui"], drug["name"], [c["id"] for c in drug["atc_classes"]])

        # Drug -> ATC level 4 classes and level 5 codes
        for m in await adapter.get_mappings("1191"):
            print(m["mappingType"], m["toId"])

        # ATC class: parent, children and member drugs
        for e in await adapter.get_relationships("N02BA", limit=3):
            print(e["relation_label"], e["related_id"], e["related_name"])

        print((await adapter.search_concepts("analgesics", limit=2))[0].primary_label)


asyncio.run(main())
```

Output (captured live, 2026-10-06):

```
5640 ibuprofen ['C01EB', 'G02CC', 'M01AE', 'M02AA', 'R02AX']
atc_class A01AD
atc_class B01AC
atc_class N02BA
atc5 A01AD05
atc5 B01AC06
atc5 N02BA01
has_parent N02B OTHER ANALGESICS AND ANTIPYRETICS
has_member 1191 aspirin
has_member 1372 benorilate
ANALGESICS
```

## What RxClass actually provides

Verified against the live service:

- **ATC is available to level 4 only as classes** (class type `ATC1-4`): `N`, `N02`, `N02B`, `N02BA`. The substance-level code (`N02BA01`, ATC level 5) is not a class; RxClass returns it as the `SourceId` attribute of a class member. The adapter reads it from `classMembers`, which is how level 5 codes appear in `get_mappings` and in the `atc_code` field of member edges.
- **The ATC hierarchy follows the code** (`N02BA` -> `N02B` -> `N02` -> `N`), and `allClasses?classTypes=ATC1-4` returns all ~1,300 classes in one 113 KB response (about 1.4 s). Class search, class details, parents and children are served from that one cached response, so after the first call they cost no requests. (The adapter keeps it in memory for the life of the adapter instance.)
- **`class/byDrugName` resolves brands** ("Advil" -> ibuprofen) and also returns *combination products* containing the ingredient (e.g. "aspirin / codeine", its own RxCUI with its own ATC class `N02AJ`). Ingredient (`IN`/`PIN`) RxCUIs sort first.
- A drug may have several ATC classes (aspirin: `A01AD`, `B01AC`, `N02BA`; ibuprofen has five including topical and throat-preparation classes). Choose by route/indication for your registry.
- **XML by default**: every endpoint answers XML unless the path ends in `.json`. The adapter always uses the `.json` form.
- "No match" is an empty object `{}` with HTTP 200, not an error.

## Searching

`search_concepts(query, limit)`:

- an identifier (`1191`, `N02BA`, `N02BA01`) goes straight to `get_concept_details`
- otherwise it runs, in parallel, a class-name search over the cached class list (exact, prefix, substring) and `class/byDrugName`
- results are ordered: exact label matches first, then drugs, then classes
- if neither finds anything it falls back to RxNorm `approximateTerm` for misspellings and accepts a candidate only with a score of at least 10 (typos of real ingredients, e.g. "fluoxetin", score about 12; poor guesses such as "asprin" score 5 to 9 and point at unrelated products, so they are dropped and the search returns `[]`)

Both drugs and ATC classes are returned as `ConceptType.DRUG`; distinguish them with `source_data[RXCLASS]["kind"]` (`drug` or `atc_class`).

## Concept details

| | Drug (RxCUI) | ATC class |
|---|---|---|
| `primary_id` | RxCUI | ATC code |
| `primary_label` | RxNorm name | class name (RxClass writes levels 1 to 3 in capitals) |
| `semantic_types` | `[tty]`, e.g. `IN`, `MIN` | `['ATC class']` |
| `categories` | `ATC <class id>` per class | `['ATC level N']` |
| `parents` / `children` | | labels from the class list |
| `source_data[RXCLASS]` | `kind`, `rxcui`, `tty`, `atc_classes` | `kind`, `class_type`, `atc_level`, `parent_id` |

Drug details cost two requests (RxNorm `properties` and `class/byRxcui`). `byRxcui` also lists classes of combination products that contain the ingredient; the adapter keeps only rows for the exact RxCUI.

## Relationships

`get_relationships(concept_id, limit=25)`:

| Input | `relation_label` | Related |
|---|---|---|
| RxCUI | `has_atc_class` | ATC level 4 classes of that RxCUI (`atc_level` extra) |
| ATC class (levels 1 to 4) | `has_parent` | parent class |
| | `has_child` | child classes |
| | `has_member` | drugs (RxCUI) in the class, capped by `limit`; extras `tty`, `atc_code` |

For levels 1 to 3 member drugs are requested with `ttys=IN` (ingredients only); an organ-system class otherwise lists hundreds of products. Level 5 codes are not classes, so `get_relationships("N02BA01")` returns `[]`.

## Mappings

`get_mappings(concept_id)`, in the usual `fromId`, `toId`, `fromSource`, `toSource`, `mappingType`, `confidence` shape:

- RxCUI -> ATC level 4 classes (`atc_class`) and ATC level 5 codes (`atc5`; one `classMembers` request per class, at most 8 classes, cached)
- RxCUI -> UMLS CUI (`umls_cui`, 0.9) only when RxNorm lists one; for the ingredients tested the `umlscui` property was empty
- ATC level 5 code -> RxCUI (`atc5_to_rxcui`)
- other ATC classes: `[]`

## Helpers for registry harmonisation

- `get_atc_for_drug(name)`: one request; list of `{rxcui, name, tty, atc_classes}`
- `lookup_rxcui(name)`: RxNorm exact (normalised) match, then approximate match; returns the RxCUI string or `None`

## Rate limits, licence and errors

RxNav allows 20 requests per second per IP; the adapter spaces requests at least 60 ms apart (about 16/s) and normally issues one to three requests per call. Typical latency is 0.8 s per request. Shared retry/circuit-breaker applies (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). RxNorm and RxClass are public NLM services; the ATC classification content is owned by the WHO Collaborating Centre for Drug Statistics Methodology, so check <https://www.whocc.no/> for terms before redistributing ATC data. Interface methods never raise: search returns `[]`, details `None`.

## Caveats

- RxClass's ATC data lags the current WHO release and lacks level 5 classes; its level 5 codes come only through class membership.
- Brand names resolve through RxNorm, which is US-centred: the German brands "Ibuflam" and "Thomapyrin" returned no match in testing. Map such products to their ingredient first.
- Dose and form text ("Ibuprofen 400 mg") is tolerated by `byDrugName` but also returns combination products; prefer the bare ingredient name.

## See also

- [DrugBank adapter](drugbank_adapter.md), [ChEMBL adapter](../core/chembl_adapter.md)
- [All adapters](../README.md)
