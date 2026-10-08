---
description: LIPID MAPS (LMSD) lipid structures, classification and cross-references to PubChem, ChEBI, HMDB, KEGG, SwissLipids and RefMet.
---

# LIPID MAPS adapter

Looks up lipids in the LIPID MAPS Structure Database (LMSD): names, systematic names, abbreviations, formula, mass, InChIKey/SMILES, the three-level classification (category, main class, sub class) and cross-references. Useful for metabolomics/lipidomics work, where the same lipid shows up as `PC 34:1`, `PC(16:0/18:1)` or `POPC` depending on the platform.

| | |
|---|---|
| Source | `KnowledgeSource.LIPIDMAPS` |
| Class | `knowledge_lookup.adapters.LipidMapsAdapter` |
| Requires | none (keyless) |
| Identifiers | LMSD id `LMGP01010005`; class codes `LMGP` (category), `LMGP01` (main class), `LMGP0101` (sub class) |
| Upstream APIs | REST `https://www.lipidmaps.org/rest`, SPARQL `https://lipidmaps.org/sparql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import LipidMapsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with LipidMapsAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("cholesterol", limit=3):
            print(c.primary_id, c.primary_label)

        popc = await adapter.get_concept_details("LMGP01010005")
        print(popc.primary_label, popc.synonyms[:3], popc.categories)

        for rel in await adapter.get_relationships("LMGP01010005"):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])
        for m in await adapter.get_mappings("LMST01010001"):
            print(m["toSource"], m["toId"])


asyncio.run(main())
```

Output (abridged):

```
LMST01010001 Cholesterol
LMST01010081 Epicholesterol
LMST01010093 Cholesterol(d7)
PC 16:0/18:1(9Z) ['1-hexadecanoyl-2-(9Z-octadecenoyl)-sn-glycero-3-phosphocholine', 'PC 34:1', 'PC 16:0_18:1'] ['Glycerophospholipids', 'Glycerophosphocholines', 'Diacylglycerophosphocholines']
is_a LMGP0101 Diacylglycerophosphocholines
is_a LMGP01 Glycerophosphocholines
is_a LMGP Glycerophospholipids
PubChem 5997
ChEBI CHEBI:16113
HMDB HMDB0000067
KEGG C00187
LipidBank SST9061
SwissLipids SLM:000000287
RefMet RM0135639
```

## Why two services

The REST API only does exact look-ups on a fixed set of fields (`lm_id`, `abbrev`, `abbrev_chains`, `formula`, `inchi_key`, `pubchem_cid`, `chebi_id`, `hmdb_id`, `kegg_id`, `regno`, `smiles`). **There is no name search**: `compound/name/cholesterol` answers `200 text/html` ("This input item does not exist"). A miss is `200 []`. The SPARQL endpoint has the labels, so free-text searches and class membership go through it. SPARQL answers `application/json` only when `Accept: application/json` is sent.

## Searching

`search_concepts(query, limit)` picks the lookup from the shape of the query and falls back to a name search on a miss:

| Query | Lookup |
|---|---|
| `LMGP01010005` | REST `lm_id` |
| `LMST0101`, `ST0101`, `[ST0101]`, `LMST` | class concept (SPARQL) |
| `WTJKGGKOPKCXLL-VYOBOKEXSA-N` | REST `inchi_key` |
| `HMDB0000067` (5 to 7 digits), `CHEBI:16113`, `CID:5997` / `PUBCHEM:5997`, `C00187` | REST `hmdb_id` / `chebi_id` / `pubchem_cid` / `kegg_id` |
| `PC(34:1)`, `PC 34:1`, `ST 27:1;O` | REST `abbrev` (bulk abbreviation, many isomers) |
| `PC(16:0_18:1)` | REST `abbrev_chains`, then `abbrev` |
| `C27H46O` | REST `formula` |
| anything else | SPARQL label search |

The label search lower-cases the query, requires every word (up to 4) to occur in the common or systematic name, ranks an exact name first and then shorter names, and de-duplicates (each lipid has two labels). Trivial names of other lipids (`POPC`) are not labels; use the abbreviation form instead. Name-search results are thin (id, name, formula, abbreviation, sub class); call `get_concept_details` for the full record.

Slashes in abbreviations such as `PC(16:0/20:4(5Z,8Z,11Z,14Z))` must stay raw in the URL (`%2F` gives a 404); the adapter takes care of that.

## Concept details

`get_concept_details(concept_id)` fetches `compound/lm_id/<id>/all` (one request). It also accepts an InChIKey, `HMDB...`, `CHEBI:n`, `CID:n` or a KEGG compound id and returns the first lipid. Class codes return a class concept.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | LMSD id / common name |
| `concept_type` | `CHEMICAL` |
| `synonyms` | systematic name, abbreviation, chain abbreviation, listed synonyms (max 50) |
| `categories` | category, main class, sub class names |
| `parents` | sub class name |
| `definitions` | one generated classification sentence |
| `identifiers` | `LIPIDMAPS` (URL), `PUBCHEM`, `CHEBI`, `KEGG` |
| `source_data[LIPIDMAPS]` | `regno`, `sys_name`, `abbrev`, `abbrev_chains`, classification, `formula`, `exactmass`, `inchi_key`, `inchi`, `smiles`, `hmdb_id`, `lipidbank_id` |

## Relationships

`get_relationships(concept_id, limit=25)`:

- **lipid**: `is_a` its sub class, main class and category (`related_id` is a class code such as `LMGP0101`; `level` is `sub_class`/`main_class`/`core`, `direct` is true for the sub class).
- **sub class** (`LMST0101`): `is_a` main class and category, plus `has_member` lipids (at most `limit`, unordered).
- **main class / category** (`LMST01`, `LMST`): `is_a` the parent and `has_subclass` for each child class.

The class members are read from SPARQL because the REST `.../all/download` table has no row cap (the sterol sub class alone is 318 KB, glycerophospholipids are tens of MB) and ignores `Range` requests, so it is deliberately not used. The category hierarchy is stored inverted in the RDF (parent `subClassOf` child), so child classes are found by label code instead.

## Mappings

`get_mappings(lm_id)` returns PubChem CID, ChEBI, HMDB, KEGG and LipidBank (REST record), SwissLipids (SPARQL `owl:equivalentClass`), and RefMet (looked up by InChIKey at `https://www.metabolomicsworkbench.org/rest/refmet/inchi_key/<key>/all`, because LIPID MAPS itself does not carry it). The SwissLipids and RefMet calls are best effort: if they fail, the other mappings are still returned. HMDB, SwissLipids, RefMet and LipidBank have no `KnowledgeSource` member, so they appear only here and in `source_data`.

## Rate limits, licence and errors

No limit is published; requests are spaced 0.5 s apart (about 2 per second) and use the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Interface methods log errors and return `[]` / `None`.

LIPID MAPS data is free to use with attribution; cite the LIPID MAPS Structure Database (Sud et al., *Nucleic Acids Res.* 2007) and see https://www.lipidmaps.org/about/terms_of_use for the current terms.

## Caveats

- Abbreviation searches return all isomers sharing the sum composition (`PC 34:1` has dozens); results are capped at `limit`.
- Name search only sees labels, not synonyms. `POPC` finds nothing by name but `PC 34:1` or the LM id works.
- `abbrev` is case-sensitive (`pc(34:1)` is a miss).

## Live verification (2026-10-08)

`knowledge-lookup check LIPIDMAPS` passes. Measured against the live services: REST look-ups 0.35 to 0.5 s (1.7 s once), SPARQL 0.3 to 0.65 s; `search_concepts("cholesterol")` 0.84 s, `PC(34:1)` 0.5 s, `get_mappings` (REST + SPARQL + RefMet, RefMet alone up to 2 s) about 1.5 to 3 s. Responses are tiny (a full record is about 1 KB).

## See also

- [ChEBI adapter](chebi_adapter.md), [Metabolomics Workbench adapter](metabolomicsworkbench_adapter.md)
- [All adapters](../README.md)
