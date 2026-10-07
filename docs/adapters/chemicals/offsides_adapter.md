---
description: OFFSIDES off-label drug side-effect signals mined from FDA adverse-event reports (statistical, not causal; 69 MB dataset, opt-in download).
---

# OFFSIDES adapter

Searches OFFSIDES (Tatonetti lab, part of [nSIDES](https://nsides.io)): drug side-effect *signals* mined from the FDA Adverse Event Reporting System (FAERS) that are **not** already listed on the drug's label ("off-label" effects). Each drug-event pair has a proportional reporting ratio (PRR) against propensity-score-matched control drugs and a reporting frequency. Drugs are RxNorm ingredients, events are MedDRA preferred terms.

> **These are statistical signals, not causal findings.**
>
> - FAERS is voluntary, spontaneous reporting: under-reporting, stimulated reporting and duplicate reports distort the counts, and there is no denominator of patients exposed, so `reporting_frequency` is **not** an incidence.
> - **Confounding by indication** is the dominant problem. A symptom listed as a "side effect" is often a symptom of the disease the drug treats or of a co-medication. Fatigue, malaise and asthenia are textbook cases: in a population on norethindrone or an antidepressant, fatigue is reported for many reasons unrelated to the drug. For ME/CFS and Long COVID work this matters directly, because fatigue-type terms are both the symptom you study and the most commonly reported adverse event of all.
> - A PRR above 1 only says the event was reported relatively more often with this drug than with its matched controls. The table also contains many pairs with PRR at or below 1, and PRR is unstable for small counts (one report can give PRR 10). The adapter therefore ranks by the **lower 95 % bound** of the PRR and exposes the counts, but it does not decide for you what counts as a signal.
> - The data is dated (the nSIDES site calls OFFSIDES "quite a bit out of date"; the file was last modified 2024-03-30). Use it to generate hypotheses and to flag things to check, never to infer causation.

| | |
|---|---|
| Source | `KnowledgeSource.OFFSIDES` |
| Class | `knowledge_lookup.adapters.OFFSIDESAdapter` |
| Requires | a local `OFFSIDES.csv(.gz)` (`OFFSIDES_PATH`) or opt-in download (`OFFSIDES_DOWNLOAD=1`) |
| Identifiers | drugs `RXNORM:1191` (bare `1191` also accepted), events `MEDDRA:10016256` |
| Upstream | `https://nsides.io`, file on the Tatonetti lab S3 bucket |

## Getting the data

The table is only published as a file. Stable direct URL (HEAD/Range-probed 2026-10-06, `Accept-Ranges: bytes`, `application/x-gzip`, last modified 2024-03-30), linked from [nsides.io](https://nsides.io) and [tatonettilab.org/offsides](https://tatonettilab.org/offsides/):

```
https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/OFFSIDES.csv.gz   68,762,346 bytes (68.8 MB)
https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/README.txt         column definitions
```

Because of the size the adapter never downloads it by surprise (a default multi-source lookup would otherwise pull 69 MB). Choose one:

1. `export OFFSIDES_PATH=/path/to/OFFSIDES.csv.gz` (a plain `.csv` also works). `is_available()` is true when the file exists.
2. `export OFFSIDES_DOWNLOAD=1` to let the adapter fetch the URL above once, lazily on the first call that needs data, through `ensure_dataset`. It is kept **gzipped** in `KNOWLEDGE_LOOKUP_DATA_DIR` (default `~/.cache/knowledge_lookup/datasets/OFFSIDES.csv.gz`) and never refreshed. A copy already in that cache is used without any flag.

Without either, `is_available()` is false (so `CentralKnowledgeLookup` skips it) and direct method calls log the instruction and return `[]` / `None`.

Parsing and memory: the file is streamed once into compact columnar arrays shared by all adapter instances. The row count was not measured (the first 64 KiB hold ~3,000 rows, which extrapolates to roughly 3 million), so expect on the order of 10-20 s and ~150 MB RAM for the first call on the full file; those two figures are estimates.

Columns (the real header spells the first one `drug_rxnorn_id`; the parser accepts both): `drug_rxnorm_id`, `drug_concept_name`, `condition_meddra_id`, `condition_concept_name`, `A` (drug reports with the event), `B` (drug without), `C` (matched controls with), `D` (controls without), `PRR = (A/(A+B))/(C/(C+D))`, `PRR_error` (standard error of ln PRR; checked against the counts), `mean_reporting_frequency = A/(A+B)`.

## Quick example

```python
import asyncio
import os

os.environ["OFFSIDES_PATH"] = "/data/OFFSIDES.csv.gz"

from knowledge_lookup.adapters import OFFSIDESAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OFFSIDESAdapter(LookupConfig()) as adapter:
        drug = (await adapter.search_concepts("norethindrone"))[0]
        for e in await adapter.get_relationships(drug.primary_id, limit=3):
            print(e["related_name"], e["prr"], (e["prr_ci95_low"], e["prr_ci95_high"]), e["a"])

        # reverse: which drugs have a signal for fatigue (MedDRA PT 10016256)?
        for e in await adapter.get_relationships("MEDDRA:10016256", limit=5):
            print(e["related_name"], e["prr"], e["reporting_frequency"])


asyncio.run(main())
```

Real rows, as an illustration of the caveat: norethindrone-fatigue has A=132, PRR 1.18 (95 % CI 0.99-1.41), reporting frequency 0.043, i.e. no clear signal despite 132 reports, while norethindrone-jaundice has PRR 4.15 (CI 2.5-6.8).

## Searching and details

`search_concepts(query, limit)` matches drug names and event names (case-insensitive; exact > prefix > whole word > substring; drugs first on ties) and exact ids. `get_concept_details` accepts `RXNORM:<id>`, `RXCUI:<id>`, `MEDDRA:<code>`, `OFFSIDES:` prefixes or a bare number (an 8-digit `10xxxxxx` is read as MedDRA, anything else as RxNorm).

| Field | Drug | Event |
|---|---|---|
| `primary_id` | `RXNORM:<id>` | `MEDDRA:<code>` |
| `concept_type` | `DRUG` | `PHENOTYPE` |
| `source_data[OFFSIDES]` | `rxnorm_id`, `n_pairs`, `n_prr_signals_ci95_above_1` | `meddra_code`, same counts |
| `definitions` | counts plus the "not causal" caveat | same |

## Relationships

`get_relationships(concept_id, limit=50)`:

- drug -> events: `relation_label="has_adverse_event_signal"`, `related_id` `MEDDRA:<code>`
- event -> drugs: `relation_label="adverse_event_signal_of"`, `related_id` `RXNORM:<id>`

Extra keys on every edge: `prr`, `prr_error` (SE of ln PRR), `prr_ci95_low`, `prr_ci95_high`, `reporting_frequency` (A/(A+B)), the 2x2 counts `a`, `b`, `c`, `d`, `evidence` and a `caveat` string. Edges are ordered by `prr_ci95_low` descending, so well-supported signals come first. Edges with `prr_ci95_low` at or below 1 are in the table but are not signals; filter them yourself if you want only disproportionate pairs.

## Mappings

`get_mappings` returns the vocabulary id behind the concept (`RXNORM` for drugs, `MEDDRA` for events, exact, confidence 1.0). OFFSIDES carries no other cross-references; for drugs use [UniChem](unichem_adapter.md) or RxClass to reach PubChem/ChEMBL.

## Not live-verified end to end

`check OFFSIDES` needs the full file because its default query (`aspirin`) is not in the first 64 KiB sample (the sample contains ergoloid mesylates, norethindrone and candesartan). The parser and every method were tested on that real sample; a full-file run needs the 69 MB download to be authorised.

## Licence and citation

The nSIDES pages state no licence for the flat files. Cite Tatonetti NP, Ye PP, Daneshjou R, Altman RB. *Data-driven prediction of drug effects and interactions.* Sci Transl Med 2012;4:125ra31, and check [nsides.io](https://nsides.io) before redistributing.

## See also

- [SIDER adapter](sider_adapter.md) (label-listed side effects, the complement of OFFSIDES)
- [All adapters](../README.md)

## Live verification (2026-10-07)

Run against the full file (`OFFSIDES.csv.gz`, 68,762,346 bytes). Building the index takes about 27 s per process (peak about 170 MB); after that searches and relationship lookups take about 0.01 s. `fatigue` finds Fatigue, Chronic fatigue syndrome and Muscle fatigue; ibuprofen (`RXNORM:5640`) has 50 adverse-event edges with PRR values. Remember these are statistical signals, not causal effects.
