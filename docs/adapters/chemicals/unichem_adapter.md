---
description: EMBL-EBI UniChem - cross-reference one compound across ChEMBL, DrugBank, PubChem, ChEBI and other chemistry databases.
---

# UniChem adapter

Maps a compound identifier to the same structure in other chemistry resources through EMBL-EBI UniChem. Starting from an InChIKey, InChI, UniChem compound ID (UCI) or a source ID such as `CHEMBL25`, you get the matching IDs in ChEMBL, DrugBank, PubChem, ChEBI, PDB ligands and many more, with URLs. It wraps the `bioservices` UniChem client.

| | |
|---|---|
| Source | `KnowledgeSource.UNICHEM` |
| Class | `knowledge_lookup.adapters.UniChemAdapter` |
| Requires | `[bioservices]` extra |
| Identifiers | InChIKey `BSYNRYMUTXBXSQ-UHFFFAOYSA-N`, UCI `161671`, or a source ID such as `CHEMBL25` |
| Upstream API | `https://www.ebi.ac.uk/unichem` (via `bioservices`) |

{% hint style="warning" %}
**Requires the `[bioservices]` extra.** Without it `is_available()` is `False` and every method returns an empty result.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import UniChemAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with UniChemAdapter(LookupConfig()) as adapter:
        if not adapter.is_available():
            raise SystemExit("Install the [bioservices] extra to use UniChem")

        # Aspirin by InChIKey
        for concept in await adapter.search_concepts("BSYNRYMUTXBXSQ-UHFFFAOYSA-N"):
            print(concept.primary_id, concept.primary_label, len(concept.identifiers))
            print([(i.label, i.identifier) for i in concept.identifiers[:4]])

        xrefs = await adapter.get_cross_references("CHEMBL25")
        print(xrefs["drugbank"])


asyncio.run(main())
```

Output:

```
161671 UCI_161671 1018
[('UniChem Compound Identifier', '161671'), ('chembl ID', 'CHEMBL25'), ('drugbank ID', 'DB00945'), ('rcsb_pdb ID', 'AIN')]
[{'id': 'DB00945', 'url': 'https://go.drugbank.com/drugs/DB00945'}]
```

Well-known drugs have very many cross-references. For aspirin most of the 1018 identifiers are ClinicalTrials.gov records.

## Searching

`search_concepts(query, limit)` is an identifier lookup. It tries these strategies in order and collects results until `limit` is reached:

1. **UCI**, if the query is all digits
2. **InChIKey**, if the query is 27 characters with two hyphens
3. **InChI**, if the query starts with `InChI=`
4. **Source compound ID**, looked up in `chembl`, `chebi`, `pubchem` and `drugbank`

Each matched compound becomes one concept:

| Field | Value |
|---|---|
| `primary_id` | UCI |
| `primary_label` | `UCI_<uci>` |
| `concept_type` | `CHEMICAL` |
| `identifiers` | the UCI (URL `https://www.ebi.ac.uk/unichem/compounds/<uci>`), then one entry per source record, labelled `<source> ID`, with the source URL; all identifiers use source `UNICHEM` |
| `categories` | short names of the sources, one per record (repeats included) |
| `confidence_score` | `0.9` |
| `source_data[UNICHEM]` | raw compound record |

## Concept details

`get_concept_details(concept_id)` tries the ID as a UCI first, then as a ChEMBL, ChEBI, PubChem or DrugBank ID, and converts the first compound found.

## Source-specific methods

| Method | Returns |
|---|---|
| `get_cross_references(concept_id)` | `dict[str, list[dict]]`: source short name → `[{"id", "url"}]`; accepts a UCI or source ID |
| `get_compounds(compound, source_type)` | raw compound data; `source_type` is `uci`, `inchi`, `inchikey` or a source name such as `chembl`; cached for 1 hour |
| `get_connectivity(compound, source_type)` | compounds sharing the same connectivity (e.g. salts, stereoisomers) |
| `get_structure(compound_id, src_id)` | `standardinchi` and `standardinchikey` for a source compound |
| `get_inchi_from_inchikey(inchikey)` | InChI strings for an InChIKey |
| `get_sources_by_inchikey(inchikey)`, `get_sources_by_inchikey_verbose(inchikey)` | sources that contain the structure |
| `get_sources()`, `get_all_src_ids()`, `get_source_info_by_id(source_id)`, `get_source_info_by_name(source_name)`, `get_id_from_name(name)` | UniChem source catalogue; cached for 24 hours |
| `get_images(uci, filename=None)` | SVG depiction of a compound |
| `get_cache_stats()`, `clear_cache(namespace="unichem")` | cache helpers |

All of these are `async` except the two cache helpers.

## Rate limits and errors

`search_concepts` and `get_concept_details` run the synchronous `bioservices` calls in a worker thread through `_thread_with_retry`, which applies the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). The other methods call `bioservices` directly in a thread, without retry. `get_cross_references` runs its lookup synchronously and briefly blocks the event loop. Errors are logged and turned into empty results.

## See also

- [ChEMBL adapter](../core/chembl_adapter.md), [PubChem adapter](pubchem_adapter.md), [DrugBank adapter](drugbank_adapter.md)
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): extras
