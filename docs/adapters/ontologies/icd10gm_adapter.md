---
description: German ICD-10-GM (BfArM) classification read from a local ClaML file, with German labels and hierarchy.
---

# ICD-10-GM adapter

Looks up codes and German titles of the ICD-10-GM (German Modification of ICD-10, published yearly by the BfArM), for example `G93.3` Chronisches Fatigue-Syndrom (ME/CFS in German diagnosis coding), `R53` Unwohlsein und Ermüdung or `U09.9` Post-COVID-19-Zustand. There is no query API, so the adapter reads the official ClaML/XML file locally.

| | |
|---|---|
| Source | `KnowledgeSource.ICD10GM` |
| Class | `knowledge_lookup.adapters.ICD10GMAdapter` |
| Requires | a ClaML file: `ICD10GM_CLAML_PATH` (or an optional `ICD10GM_URL`) |
| Identifiers | `G93.3`, `G933`, `ICD10GM:G93.3`, block codes `G90-G99`, chapter numerals `VI` |
| Data source | BfArM "ICD-10-GM Systematik ClaML/XML" download |

## Getting the file

The BfArM publishes each year's Systematik at <https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html> (file `icd10gm<year>syst-claml.zip`, for example `icd10gm2026syst-claml.zip`, about **17 MB** for 2026). The link leads to a consent page ("Zustimmung zum Download") where you accept the BfArM download terms (the Systematik is an official work, s. 5(2) UrhG: free use with attribution, no modification). No stable direct file URL is exposed (plain HEAD requests to the site return 400), so the adapter does **not** download from the BfArM on its own. Download the zip once in a browser and point the adapter at it. The zip can be used as it is: the XML member (name containing `claml`) is picked automatically.

## Configuration

| Variable | Meaning |
|---|---|
| `ICD10GM_CLAML_PATH` | path to the ClaML `.xml` or the BfArM `.zip` (also readable as `config.get_api_key("icd10gm")`) |
| `ICD10GM_URL` | optional URL of a copy you control, for example an internal mirror; `{year}` is replaced with `ICD10GM_YEAR`. Fetched lazily on first use with `knowledge_lookup.utils.dataset_cache.ensure_dataset`, never at construction, and never refreshed (the year is pinned by the URL) |
| `ICD10GM_YEAR` | fills `{year}` in the URL and names the cached file |
| `ICD10GM_MEMBER` | XML file name inside the zip, only needed for a multi-file zip fetched through `ICD10GM_URL` |

`is_available()` is true when a path or URL is configured; the file itself is read on the first search.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ICD10GMAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    # export ICD10GM_CLAML_PATH=~/data/icd10gm2026syst-claml.zip
    async with ICD10GMAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("G93.3"):
            print(concept.primary_id, concept.primary_label)
        for concept in await adapter.search_concepts("muedigkeit", limit=5):
            print(concept.primary_id, concept.primary_label)  # matches "Müdigkeit"
        details = await adapter.get_concept_details("G93.3")
        print(details.categories)
        for edge in await adapter.get_relationships("G93.3"):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

## What each method returns

- **`search_concepts(query, limit)`**: a code-like query (`G93.3`, `g933`, `G93`) returns the exact class first and then classes whose code starts with it (chapters skipped). Otherwise it matches the German title, case- and umlaut-insensitively (`Ermüdung`, `ermudung` and `ermuedung` all find `R53`), ranked by exact title, title prefix, substring, all words in any order, and finally inclusion terms (`Myalgische Enzephalomyelitis` finds `G93.3`). Categories rank before blocks and chapters. `confidence_score` encodes the match type (1.0 exact code or title, 0.9 prefix, 0.8 substring, 0.7 all words, 0.6 inclusion term).
- **`get_concept_details(code)`**: label (German, also in `labels["de"]`), `synonyms` (inclusion terms), `semantic_types` (class kind, plus `dagger`/`aster` usage), `parents`/`children` codes, and `categories` listing the ancestors (`chapter:VI ...`, `block:G90-G99 ...`). `source_data["ICD10GM"]` holds the hierarchy path from chapter to code, the file version, and the free-text inclusion, exclusion and note rubrics. Codes starting with `R` (symptoms and signs) are typed `SYMPTOM`, everything else `DISEASE`.
- **`get_relationships(code, limit=50)`**: `is_a` (superclass), `has_subtype` (subclasses, capped at `limit`), and `excludes` / `includes` for exclusion and inclusion rubrics that reference another code (for example R53 excludes G93.3). Free-text rubrics without a reference are not edges.
- **`get_mappings`** is not implemented: ClaML carries no cross-terminology links.

## Implementation notes

The file is stream-parsed with `xml.etree.ElementTree.iterparse` in a worker thread on first use (Class `kind` chapter/block/category, `SuperClass`/`SubClass`, `Rubric` kinds `preferred`, `preferredLong`, `inclusion`, `exclusion`, `note`) and kept in memory; adapters share the parsed index per file and modification time. Interface methods never raise: a missing or corrupt file is logged and gives `[]` / `None`.

## Caveats

- Not verified against the full official file: the BfArM download is consent-gated and large, so the parser is tested on a small **synthetic** ClaML sample (`tests/fixtures/icd10gm_claml_sample.xml`) built from the documented ClaML structure. Its German wording is illustrative, not an authoritative copy of the catalogue. Run `knowledge-lookup check ICD10GM` against your real file before relying on it.
- Only the German preferred label is read; the BfArM file has no other languages.
- Cite the BfArM as the source when showing ICD-10-GM content, and do not modify the classification text.

## See also

- [ICD-11 adapter](icd11_adapter.md), [LOINC adapter](loinc_adapter.md)
- [All adapters](../README.md)
