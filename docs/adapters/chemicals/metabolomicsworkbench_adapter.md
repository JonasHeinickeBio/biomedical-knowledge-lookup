---
description: Metabolomics Workbench metabolomics studies (including ME/CFS and Long COVID) and RefMet metabolites with PubChem, KEGG, HMDB and ChEBI cross-references.
---

# Metabolomics Workbench adapter

Searches the NIH Metabolomics Workbench for deposited metabolomics studies and standardised metabolite names (RefMet), and links metabolites to the studies that measured them. Many ME/CFS and Long COVID studies are deposited here, for example `ST002003` (plasma case-control study of ME/CFS), `ST004941` (fecal serotonin and tryptophan metabolism in ME/CFS) and `ST003103` (mitochondrial dysfunction in Long COVID).

| | |
|---|---|
| Source | `KnowledgeSource.METABOLOMICSWORKBENCH` |
| Class | `knowledge_lookup.adapters.MetabolomicsWorkbenchAdapter` |
| Requires | none |
| Identifiers | `ST002003` (study), `RM0135904` (RefMet metabolite), `regno:37125` (compound registry number), or an exact RefMet name |
| Upstream API | `https://www.metabolomicsworkbench.org/rest` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MetabolomicsWorkbenchAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MetabolomicsWorkbenchAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue", limit=3):
            print(c.primary_id, c.primary_label[:70])

        lactate = await adapter.get_concept_details("RM0135904")
        print(lactate.primary_label, [(i.source, i.identifier) for i in lactate.identifiers])

        print([m["toId"] for m in await adapter.get_mappings("RM0135904")])
        rels = await adapter.get_relationships("ST004941", limit=3)
        print([r["related_id"] for r in rels])


asyncio.run(main())
```

Output (live, 2026-10-08):

```
ST004941 Depleted Fecal Serotonin and Altered Tryptophan Metabolism in Patients with
ST004940 Increased Serum Indole and Depleted Serotonin in Patients with Myalgic Enceph
ST002003 A case-control study on plasma metabolomics analysis in Myalgic encephalomyel
Lactic acid [('METABOLOMICSWORKBENCH', 'RM0135904'), ('PUBCHEM', '107689'), ('KEGG', 'C00186'), ('CHEBI', '422')]
['PUBCHEM:107689', 'KEGG:C00186', 'CHEBI:422', 'HMDB:HMDB0000190', 'METACYC:L-LACTATE', 'INCHIKEY:JVTAAEKCZFNVCJ-REOHCLBHSA-N']
['3-Hydroxyanthranilic acid', 'Hydroxykynurenine', '5-Hydroxyindoleacetic acid']
```

## Searching

`search_concepts(query, limit)` makes two requests:

1. `refmet/match/{text}`: the only fuzzy name lookup in the REST API (it returns one best RefMet entry, or placeholder `"-"` fields when nothing matches). A hit becomes the first result, a `METABOLITE` concept with formula, mass and chemical classes.
2. `study/study_title/{text}/summary`: a substring match on study titles, newest first. Each hit is a `STUDY` concept.

Search by compound name is not offered by the API (`compound/name/...` does not exist), and there is no disease or abstract search, so a disease term such as `chronic fatigue` only finds studies that carry it in the title. Use `get_concept_details` to see the annotated disease. An id (`ST002003`, `RM0135904`, `regno:37125`) goes straight to details.

## Concept details

`get_concept_details(concept_id)`:

- **Study** (`ST000001`): `study/study_id/{id}/summary` plus `.../disease` (2 requests). `study_id` queries are *prefix* matches on the server (`ST0020` returns every ST0020xx study), so the adapter keeps only the exact id. `primary_label` is the title, `concept_type` `STUDY`, `categories` the species and annotated disease (`COVID-19`, `Myalgic encephalomyelitis/chronic fatigue syndrome`), `semantic_types` the analysis type (`LC-MS`, `NMR` ...), and `definitions` a one-line summary (analysis type, species, samples, depositing institute). `source_data` keeps dates, version and the licence (`CC BY 4.0`). The URL of the study page is built from the id because the `study_url` field of the API is malformed in title searches.
- **Metabolite** (`RM...`, an exact RefMet name or `regno:N`): the RefMet record (`refmet/refmet_id/{id}/all`) and, when it has a positive registry number, the compound record (`compound/regno/{n}/all`). `primary_id` is the RefMet id, `primary_label` the RefMet name, `synonyms` the compound database name and systematic name, `categories` the RefMet super/main/sub class. Identifiers for PubChem, KEGG, ChEBI and LIPID MAPS are attached as `ConceptIdentifier`s; HMDB, MetaCyc, InChIKey, SMILES, formula and mass are kept in `source_data` (there is no HMDB source in the identifier enum). Lipid-class RefMet entries have a negative registry number and no compound record.

## Relationships

`get_relationships(concept_id, limit=50)`:

| Direction | `relation_label` | Notes |
|---|---|---|
| study -> metabolite | `measures_metabolite` | unique RefMet names over all analyses of the study (`analysis_ids`, `analyses`); features without a RefMet match (empty, `-`, `Standard`) are skipped |
| metabolite -> study | `measured_in_study` | study ids, newest first; `total_studies` is the full count |

`related_id` for a measured metabolite is the RefMet *name*, because the study endpoint does not return RefMet ids; pass it to `get_concept_details` to resolve the record. Study listings are capped at `limit`, but the API always sends the complete list: a big study's metabolite table is about 100 KB and takes several seconds, and a common metabolite such as lactic acid is measured in more than 1,300 studies (about 100 KB).

## Mappings

`get_mappings(concept_id)` returns `PUBCHEM`, `KEGG`, `CHEBI`, `LIPIDMAPS`, `HMDB`, `METACYC` and `INCHIKEY` cross-references of a metabolite (`xref`, confidence 0.95). They come from two registries of the same entry; the RefMet entry is usually a specific stereoisomer (L-lactic acid, PubChem 107689) while other registry numbers hold the racemate (PubChem 612), so check the InChIKey when stereochemistry matters. Studies have no mappings.

## Rate limits, licence and errors

No rate limit is published; calls are spaced at least 0.5 s apart (2 requests/s). Studies are deposited under the licence stated in each study (`CC BY 4.0` in all examples checked); cite the study and the Workbench. Slashes and colons inside names (`MG 18:0/0:0/0:0`) must stay unescaped in the URL path: the server answers 404 for `%2F`, and the adapter keeps them raw.

The API signals bad parameters with HTTP 200 and an HTML message, which is logged as an error. Unknown ids return `[]`. Search returns `[]` and details `None` on errors; see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers).

## Caveats

- The response shape depends on the number of hits: a flat object for one record, an object keyed `"1"`, `"2"` ... for several, and `[]` for none. The adapter normalises all three.
- Studies are returned with the submitters' free-text metadata; the species and disease annotations are not ontology-coded.
- `get_relationships` for a metabolite uses the RefMet name, so metabolites without a RefMet record (registry-only) return no studies.

## Live verification (2026-10-08)

`knowledge-lookup check METABOLOMICSWORKBENCH` passes (search `lactate`, details, study edges).

| Call | Latency | Size |
|---|---|---|
| `study/study_title/chronic fatigue/summary` | 0.8 s | 9 KB (15 studies) |
| `study/study_id/ST003103/summary` | 0.7 s | 0.6 KB |
| `refmet/match/lactate` | 0.7 s | 0.2 KB |
| `refmet/refmet_id/RM0135904/all` | 1.6 s | 0.3 KB |
| `compound/regno/37125/all` | 0.8 s | 0.3 KB |
| `study/study_id/ST004941/metabolites` | 0.8 s | 5 KB |
| `study/study_id/ST003103/metabolites` | 4.3 s | 106 KB |
| `study/refmet_name/Lactic acid/summary` | 1.6 s | 103 KB |
| `get_concept_details("RM0135904")` (2 calls) | 1.4 s | |

## See also

- [ChEBI adapter](chebi_adapter.md), [PubChem adapter](pubchem_adapter.md), [KEGG adapter](../pathways/kegg_adapter.md) (resolve the cross-references)
- [MetaboLights adapter](metabolights_adapter.md)
- [All adapters](../README.md)
