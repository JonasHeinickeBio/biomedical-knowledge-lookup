---
description: EMBL-EBI MetaboLights metabolomics studies (including ME/CFS and Long COVID) and ChEBI-based reference metabolites.
---

# MetaboLights adapter

Searches EMBL-EBI MetaboLights for metabolomics studies (`MTBLS...`) and curated reference metabolites (`MTBLC...`, whose number is the ChEBI id). ME/CFS and Long COVID studies include `MTBLS161` (NMR profiling of serum and urine from ME/CFS patients) and `MTBLS11718` (gut microecology of long COVID).

| | |
|---|---|
| Source | `KnowledgeSource.METABOLIGHTS` |
| Class | `knowledge_lookup.adapters.MetaboLightsAdapter` |
| Requires | none |
| Identifiers | `MTBLS161` (study), `MTBLC16651` or `CHEBI:16651` (reference metabolite) |
| Upstream APIs | `https://www.ebi.ac.uk/ebisearch/ws/rest/metabolights` (search, study records) and `https://www.ebi.ac.uk/metabolights/ws` (compound records) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MetaboLightsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MetaboLightsAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("long covid", limit=3):
            print(c.primary_id, c.primary_label[:60])

        study = await adapter.get_concept_details("MTBLS161")
        print(study.categories, study.semantic_types)

        rels = await adapter.get_relationships("MTBLS161", limit=3)
        print([(r["related_id"], r["related_name"]) for r in rels[:3]])

        print([m["toId"] for m in await adapter.get_mappings("MTBLC16651")])


asyncio.run(main())
```

Output (live, 2026-10-08):

```
MTBLS14790 Brain corticogenesis promotes SARS-CoV-2 neuro-glial tropis
MTBLS11718 Gut microecology of long COVID persisting for 2 years
MTBLS7919 Delayed gut microbiota maturation in the first year of life
['Homo sapiens', 'Chronic Fatigue Syndrome'] ['NMR spectroscopy']
[('MTBLC16797', '1-methylnicotinamide'), ('MTBLC15366', 'acetic acid'), ('MTBLC16977', 'L-alanine')]
['CHEBI:16651', 'INCHIKEY:JVTAAEKCZFNVCJ-REOHCLBHSA-M']
```

## Why two services

The MetaboLights web service has no text search: `ws/studies` returns about 3,500 bare study ids (43 KB), `ws/compounds/list` about 33,000 bare compound ids (470 KB) and `ws/studies/technology` only the technology per id, so there is nothing to cache and filter locally. EBI Search indexes both studies and compounds of MetaboLights in one domain (`id:MTBLS*` / `id:MTBLC*`), with full-text search, study metadata and cross-reference fields, so it serves search and study records. The compound record (formula, InChI, InChIKey, ChEBI id, organisms) comes from the web service. There is no `ws/v2` prefix.

## Searching

`search_concepts(query, limit)` runs two EBI Search queries, `({query}) AND id:MTBLC*` and `({query}) AND id:MTBLS*`, so a term like `lactate` returns both reference metabolites and studies. All words must match (AND). Lucene operators in the text are replaced by spaces (`ME/CFS` becomes `ME CFS`). Up to half of `limit` is given to metabolites when both kinds are available, the rest to studies (and the other way round when one side is short). Studies come newest first. `chronic fatigue` finds `MTBLS161`; `ME/CFS` finds the same study; `long covid` finds seven studies. An id goes straight to details.

Study hits carry title, description, organisms, technology and factors; metabolite hits only name and description (formula and cross-references are empty in the search index).

## Concept details

- **Study** (1 EBI Search `entry/{id}` request): `primary_label` is the title, `definitions` the description, `categories` organisms and study factors, `semantic_types` the technology type (`NMR spectroscopy`, `mass spectrometry assay`). `source_data` keeps design descriptors, tissues, instruments, status, submission/release dates, the publication string, parsed `pubmed_ids` and `dois`, and the number of reported compounds.
- **Metabolite** (1 web service request, `compounds/{MTBLC}`): `primary_label` is the name, `definitions` the ChEBI description, `synonyms` the IUPAC names, `categories` the organisms the compound was found in, and a `CHEBI` identifier. `source_data` keeps formula, InChI, InChIKey, the NMR/MS/pathway/reaction flags and the MetaboLights study accessions listed on the record.

## Relationships

`get_relationships(concept_id, limit=50)` (limit capped at 100):

| Direction | `relation_label` | Notes |
|---|---|---|
| study -> compound | `measures_compound` | reference metabolites the study reports; names come from one extra batch request; `total_compounds` is the full count |
| study -> organism | `studies_organism` | organism name, or `NCBITaxon:<id>` where the submitter annotated a taxonomy id |
| study -> publication | `has_publication` | `PMID:` if known, otherwise `doi:` |
| metabolite -> study | `measured_in_study` | studies that report the compound's ChEBI id, newest first; `total_studies` is the full count (143 for `MTBLC422`) |
| metabolite -> organism | `found_in_organism` | `metSpecies` of the compound record, `NCBITaxon:<id>` where MetaboLights has one |

The study-to-metabolite link is the study's ChEBI-annotated compound list in EBI Search; the reverse link is a search for `"CHEBI:<n>"`, because compounds do not store their studies completely (the `crossReference` list of the compound record holds only a few curated studies).

## Mappings

`get_mappings(concept_id)`: metabolites give `CHEBI` (`exactMatch`, since `MTBLC<n>` is `CHEBI:<n>`) and `INCHIKEY`; studies give `PMID`, `doi` and, where annotated, `NCBITaxon` ids. MetaboLights does **not** expose KEGG, HMDB or PubChem ids on reference compounds (the fields exist in the search index but are empty for compounds), so use the [ChEBI adapter](chebi_adapter.md) to continue from the ChEBI id.

## Rate limits, licence and errors

EMBL-EBI publishes no fixed limit; calls are spaced 0.2 s apart (5 requests/s). Data are open under the EMBL-EBI terms of use, and each study states its dataset licence; cite the study accession. A missing compound answers HTTP 403 and a missing study HTTP 400; the adapter treats these (and 404) as "not found" without retrying and without counting them as failures for the circuit breaker. Other errors are logged and the methods return `[]` / `None`; see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers).

## Caveats

- Free-text search matches title, description and many other indexed fields, so a short term such as `lactate` also matches studies that only mention it in a protocol.
- `PUBMED` is empty for many studies; the DOI inside the `publication` string is then the only publication id (for example `MTBLS161`).
- Studies in preparation may have a publication without any id.
- Wildcard queries (`id:MTBLC*`) are slower than plain ones (up to 2 s).

## Live verification (2026-10-08)

`knowledge-lookup check METABOLIGHTS` passes (search `chronic fatigue`, details, study-to-compound edges).

| Call | Latency | Size |
|---|---|---|
| EBI Search `(chronic fatigue) AND id:MTBLS*` | 0.3-0.6 s | 0.3 KB |
| EBI Search `(lactate) AND id:MTBLC*` | 1.8 s | 0.6 KB (5 hits) |
| EBI Search `entry/MTBLS161` (all study fields) | 1.1 s | 1 KB |
| EBI Search `entry/<41 compound ids>` (names) | 0.3 s | 3 KB |
| `ws/compounds/MTBLC16651` | 0.2 s | 1.1 KB |
| `ws/compounds/MTBLC422` (cold) | 3.3 s | 1.6 KB |
| `get_relationships("MTBLS161", 4)` | 0.4 s | |
| `get_relationships("MTBLC422", 3)` | 0.5 s | |

## See also

- [ChEBI adapter](chebi_adapter.md), [Metabolomics Workbench adapter](metabolomicsworkbench_adapter.md)
- [All adapters](../README.md)
