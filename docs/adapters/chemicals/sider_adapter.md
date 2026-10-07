---
description: SIDER 4.1 drug side effects text-mined from drug labels, with frequencies, ATC and PubChem mappings (outdated, 2015; CC BY-SA).
---

# SIDER adapter

Searches and links the Side Effect Resource (SIDER 4.1, EMBL): side effects that were text-mined from FDA drug-label package inserts and mapped to MedDRA, for about 1,430 drugs. You can look a drug up by name and get its labelled side effects (with label frequencies where the label gave one), or start from a side effect such as "fatigue" and list the drugs whose labels mention it.

> **Outdated.** SIDER 4.1 was released in October 2015 and is no longer updated (the site was last touched in 2016). Labels have changed since. Use it for historical, label-derived side-effect lists, not as a current safety reference. "Listed on a label" is not "proven to cause", and many listed side effects (fatigue, nausea, headache) are also symptoms of the disease being treated.
>
> **Licence.** The SIDER download page currently states Creative Commons Attribution-Share Alike 4.0 (older SIDER releases and the original paper used CC BY-NC-SA, so if you redistribute or use it commercially, check the licence yourself). Attribute: Kuhn M, Letunic I, Jensen LJ, Bork P. *The SIDER database of drugs and side effects.* Nucleic Acids Res 2016;44:D1075-9.

| | |
|---|---|
| Source | `KnowledgeSource.SIDER` |
| Class | `knowledge_lookup.adapters.SIDERAdapter` |
| Requires | opt-in download (~5.5 MB): `SIDER_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or local files in `SIDER_DATA_DIR` |
| Identifiers | drugs: STITCH compound id `CID100002244`; side effects: UMLS CUI `C0015672` |
| Upstream | `https://sideeffects.embl.de/media/download/` (flat files, no API) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import SIDERAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with SIDERAdapter(LookupConfig()) as adapter:
        # side effect -> drugs
        fatigue = (await adapter.search_concepts("fatigue"))[0]
        print(fatigue.primary_id, fatigue.primary_label)
        for edge in (await adapter.get_relationships(fatigue.primary_id, limit=3)):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])

        # drug -> side effects with label frequency
        for edge in await adapter.get_relationships("CID100000444", limit=3):  # bupropion
            print(edge["related_name"], edge.get("frequency"), edge.get("placebo_frequency_max"))

        print(await adapter.get_mappings("CID100000143"))  # leucovorin


asyncio.run(main())
```

The first call downloads and indexes the files (a few seconds); later calls, and later adapters in the same process, reuse the in-memory index.

## Data files

`https://sideeffects.embl.de/media/download/` (HEAD-probed 2026-10; the `http://sideeffects.embl.de/download/<file>` links in older documentation return 404, the real path is `/media/download/` on https). All support HTTP Range requests.

| File | Size | Used for |
|---|---|---|
| `drug_names.tsv` | 34 KB | STITCH flat id -> drug name |
| `drug_atc.tsv` | 33 KB | flat id -> ATC code(s) |
| `meddra_all_se.tsv.gz` | 2.4 MB | drug -> side effect (UMLS CUI, MedDRA term) |
| `meddra_freq.tsv.gz` | 2.1 MB | label frequencies, loaded on the first `get_relationships` call |
| `meddra.tsv.gz` | 1.1 MB | UMLS CUI -> MedDRA code, loaded on the first side-effect `get_mappings` call |

Files are fetched lazily through `knowledge_lookup.utils.dataset_cache.ensure_dataset`: never at import or construction, and never refreshed (the release is frozen). Set `SIDER_DATA_DIR` to a directory that already holds (or should receive) these files to work offline or choose where they live; both the `.gz` and a decompressed `.tsv` copy are accepted. Otherwise they go to `KNOWLEDGE_LOOKUP_DATA_DIR` or `~/.cache/knowledge_lookup/datasets`.

## Searching

`search_concepts(query, limit)` matches case-insensitively against drug names, side-effect names (MedDRA preferred terms), ATC codes (`N06AX` finds bupropion) and exact ids. Ranking is exact (1.0), prefix (0.9), whole word (0.8), substring (0.6); drugs come before side effects on ties. `search_concepts("fatigue")` returns `C0015672` "Fatigue" first.

## Concept details

`get_concept_details(concept_id)` accepts a STITCH flat id (`CID100002244`), a stereo id (`CID000002244`), `PUBCHEM:2244`, a UMLS CUI (`C0015672` or `UMLS:C0015672`), with or without a `SIDER:` prefix.

| Field | Drug | Side effect |
|---|---|---|
| `concept_type` | `DRUG` | `PHENOTYPE` |
| `primary_label` | SIDER's (STITCH-derived, sometimes truncated) name | MedDRA preferred term |
| `identifiers` | `SIDER`, `PUBCHEM` (CID) | `SIDER`, `UMLS` |
| `categories` | `ATC:<code>` | none |
| `source_data[SIDER]` | flat/stereo ids, PubChem CID, ATC codes, number of side effects | CUI, number of drugs |

Drug names are SIDER's automatic names and are sometimes only a fragment ("gamma-aminobutyric"); use the ATC code or PubChem mapping to normalise.

## Relationships

`get_relationships(concept_id, limit=50)`:

- drug -> side effects: `relation_label="has_side_effect"`, `related_id` = CUI, `related_name` = MedDRA preferred term. Side effects the label gave a frequency for come first, highest lower bound first. Extra keys: `frequency` (label text of the most specific high figure, e.g. `"21%"`, `"rare"`, `"postmarketing"`), `frequency_min` / `frequency_max` (that entry's bounds as fractions), `frequency_all` (every distinct figure on the labels) and `placebo_frequency_max` (when a placebo arm was reported).
- side effect -> drugs: `relation_label="side_effect_of"`, ordered by drug name.

Real sample (bupropion, SIDER 4.1): Insomnia up to 45% (placebo up to 21%), Fatigue 5% (placebo 8.6%), Amnesia "rare". Frequencies of the form "frequent" (bounds 0.01-1) are bands, not measurements.

## Mappings

`get_mappings(concept_id)`:

- drug: STITCH flat id -> PubChem CID (`CID1xxxxxxxx` = PubChem CID + 100,000,000; verified for aspirin 2244, metformin 4091 and ibuprofen 3672 against PubChem), confidence 1.0; the stereo-specific compound ids as further PubChem CIDs (`stereoisomer`, 0.8); ATC codes (`xref`, 0.9).
- side effect: UMLS CUI (exact), MedDRA preferred-term code (exact) and lower-level-term codes (`synonym`, 0.8).

## Rate limits and errors

No requests are made after the files are cached. Download failures fall back to a cached copy if one exists, otherwise `search_concepts` returns `[]`, `get_concept_details` returns `None` and the error is logged. Methods never raise.

## See also

- [OFFSIDES adapter](offsides_adapter.md), [PubChem adapter](pubchem_adapter.md), [UniChem adapter](unichem_adapter.md)
- [All adapters](../README.md)
