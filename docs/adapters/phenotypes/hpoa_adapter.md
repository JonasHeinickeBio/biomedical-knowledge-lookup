---
description: HPO disease-to-phenotype annotations with frequency, onset and evidence (phenotype.hpoa download).
---

# HPO annotations (phenotype.hpoa) adapter

Looks up rare diseases (OMIM, Orphanet, DECIPHER) and the HPO phenotypes annotated to them, including how often each phenotype occurs, at what onset and with which evidence. It is the offline counterpart of the [Monarch adapter](monarch_adapter.md) for disease-phenotype questions: the `phenotype.hpoa` file is downloaded once, parsed into in-memory indexes and every call after that is local.

| | |
|---|---|
| Source | `KnowledgeSource.HPOA` |
| Class | `knowledge_lookup.adapters.HPOAAdapter` |
| Requires | none (downloads ~36 MB on first use; or set `HPOA_PATH`) |
| Identifiers | `OMIM:154700`, `ORPHA:558`, `DECIPHER:5` (diseases); `HP:0012432` (phenotypes, relationships only) |
| Data file | `https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa` |
| Environment | `HPOA_PATH` (optional), `KNOWLEDGE_LOOKUP_DATA_DIR` (cache location) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import HPOAAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with HPOAAdapter(LookupConfig()) as adapter:  # first call downloads the file
        hit = (await adapter.search_concepts("marfan syndrome", limit=1))[0]
        print(hit.primary_id, hit.primary_label)

        for edge in await adapter.get_relationships(hit.primary_id, limit=3):
            print(edge["relation_label"], edge["related_id"], edge.get("frequency_label"),
                  edge.get("frequency"), edge.get("onset_label"))

        # which diseases have chronic fatigue (HP:0012432), most frequent first?
        for edge in await adapter.get_relationships("HP:0012432", limit=3):
            print(edge["related_id"], edge["related_name"], edge.get("frequency"))


asyncio.run(main())
```

## The data file

Release 2026-09-02 (HPO 2026-09-01): `phenotype.hpoa` is 35,816,037 bytes, 8,478 OMIM, 4,357 Orphanet and 47 DECIPHER diseases (the header says `[8478: OMIM; 47: DECIPHER; 4357 ORPHANET]`). The GitHub `latest/download` URL redirects to a signed asset URL; `https://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa` redirects to the same file.

The format was learned from the first 64 KiB (a `Range` request), never from a full download. Tab separated; four `#key: value` header lines (`description`, `version`, `tracker`, `hpo-version`), one column-header row, then one row per annotation:

`database_id`, `disease_name`, `qualifier` (empty or `NOT`), `hpo_id`, `reference`, `evidence` (`PCS`, `TAS`, `IEA`), `onset` (HP onset term), `frequency`, `sex`, `modifier`, `aspect` (`P` phenotype, `I` inheritance, `C` clinical course, `M` modifier), `biocuration`.

`frequency` is an HP frequency term (`HP:0040280`..`HP:0040285`), a fraction `n/m` or a percentage `x%`; in the sample 364 of 554 rows had `n/m`, 7 a term and the rest were empty. The sample held OMIM rows only: `NOT`, percentage and `ORPHA:`/`DECIPHER:` rows follow the documented format but were not seen in the sample (the unit-test fixture adds hand-written rows for them and says so).

### Loading

- Nothing is downloaded at import or construction. The first call that needs data runs `ensure_dataset(...)`, which caches the file (default `~/.cache/knowledge_lookup/datasets/phenotype.hpoa`, re-fetched when older than 30 days; a stale copy is used if a refresh fails).
- `HPOA_PATH=/path/to/phenotype.hpoa` (plain or `.gz`) skips the download. If it points at a missing file `is_available()` returns `False`.
- Parsing happens once per adapter in a worker thread and builds: disease id -> rows and HP id -> rows.
- If the download fails, the interface methods return `[]`/`None` and the next call retries.

## Searching

`search_concepts(query, limit)` matches disease **names** case-insensitively as a substring, or a disease id, or an HP id:

| Query | Result |
|---|---|
| `marfan` | diseases whose name contains it, ranked exact 1.0, prefix 0.9, word-start 0.8, other substring 0.7 (ties: more annotations first) |
| `OMIM:154700`, `154700`, `orphanet:558` | that disease |
| `HP:0012432` | the diseases annotated with that phenotype (excluding `NOT` annotations) |

Concepts are `DISEASE` with `confidence_score` as above and `categories == ["hpoa:OMIM"]` (or `hpoa:ORPHA`, ...).

## Concept details

`get_concept_details(disease_id)` returns the disease with an OMIM `identifier` (for OMIM ids) and a summary in `source_data[HPOA]`: `annotations`, `phenotypes`, `excluded_phenotypes`, `inheritance` (HP ids), `clinical_course`, `references` (first 50), `hpoa_version`, `hpo_version`. HP ids return `None`: the file contains HPO ids but **no HPO term labels**. Pair it with the [HPO adapter](hpo_adapter.md) or [Monarch adapter](monarch_adapter.md) for labels.

## Relationships

`get_relationships(concept_id, limit=50, aspect="P")`:

- **disease id** -> phenotypes: `relation_label` `has_phenotype` (or `not_has_phenotype` for `NOT` rows), `related_id` the HP id (`related_name` is also the HP id, see above).
- **HP id** -> diseases: `phenotype_of` / `not_phenotype_of`, `related_name` the disease name.

Extra keys per edge: `frequency` (numeric fraction), `frequency_label`, `frequency_raw`, `frequency_term`, `onset` (+ `onset_label`), `evidence` (+ `evidence_label`), `references` (all PMIDs/ids; repeated annotations of the same term are merged), `sex`, `modifier`, `aspect`, `direction`. Frequency conversion: `n/m` -> n/m, `x%` -> x/100, HP terms -> the midpoint of the term's range (Obligate 1.0, Very frequent 0.9, Frequent 0.55, Occasional 0.17, Very rare 0.025, Excluded 0.0). Results are sorted by `frequency`, most frequent first, unknown frequency last.

`aspect` keeps one annotation kind: `"P"` (default, phenotypic abnormalities), `"I"` inheritance (`has_inheritance`), `"C"` clinical course (`has_clinical_course`), `"M"` modifier (`has_clinical_modifier`), or `None` for all. `get_mappings` is not provided.

## Licence and caveats

- HPO annotations are free for research use; see <https://hpo.jax.org/license>. OMIM-derived rows carry OMIM's terms.
- Only HP ids are present, no phenotype labels; only disease-level data, no genes (use Monarch for gene-disease links).
- ORPHA ids are written `ORPHA:<n>` in the file; `Orphanet:` and `orphanet:` are accepted as aliases.
- The whole file is held in memory after loading (one tuple per annotation row); share one adapter instance rather than creating many. Memory use for the full file was not measured.
- Verification used only the 64 KiB sample (the CLI `check` was run with `HPOA_PATH` pointing at it); the full 35.8 MB file has not been downloaded or parsed.

## See also

- [Monarch adapter](monarch_adapter.md), [HPO adapter](hpo_adapter.md), [OMIM adapter](omim_adapter.md)
- [All adapters](../README.md)
