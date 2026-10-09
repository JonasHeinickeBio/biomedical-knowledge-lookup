---
description: OmicsDI omics dataset discovery across ArrayExpress, PRIDE, GEO, MetaboLights, ENA and 20+ more repositories (metadata and URLs only, keyless).
---

# OmicsDI adapter

Searches the [Omics Discovery Index](https://www.omicsdi.org/) (OmicsDI, EMBL-EBI), a metadata index over 29 public omics repositories (4.93 million datasets on 2026-10-09). It is the quickest way to answer "which transcriptomics, proteomics, metabolomics or microbiome datasets exist for ME/CFS or Long COVID?" in one query across repositories. The adapter returns **dataset metadata and URLs only**; it never downloads data files.

| | |
|---|---|
| Source | `KnowledgeSource.OMICSDI` |
| Class | `knowledge_lookup.adapters.OmicsDIAdapter` |
| Requires | none (keyless, JSON) |
| Identifiers | `<database>:<accession>` such as `geo:GSE16059`, `pride:PXD076216`, `metabolights_dataset:MTBLS161`, `biostudies-arrayexpress:E-GEOD-16059`. Bare accessions (`GSE16059`, `PXD076216`, `MSV000090685`, `MTBLS161`, `ST000450`, `E-MTAB-14669`, `PRJNA1265093`, `S-EPMC...`, `EGAS...`, `phs...`) are mapped to their repository by shape. A friendly prefix (`arrayexpress:`, `metabolights:`, `ena:`) is accepted |
| Upstream API | `https://www.omicsdi.org/ws` |
| Licence | free EMBL-EBI service, open index metadata under the EMBL-EBI terms of use. Each dataset keeps the licence of its source repository (follow `source_data["OMICSDI"]["url"]`); credit the original repository when you reuse data |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OmicsDIAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OmicsDIAdapter(LookupConfig()) as adapter:
        # proteomics datasets on Long COVID in human samples
        for c in await adapter.search_datasets(
            "long covid", limit=3, filters={"omics_type": "Proteomics", "organism": "human"}
        ):
            print(c.primary_id, c.primary_label[:60])

        # one dataset in detail, its publication and similar datasets
        c = await adapter.get_concept_details("pride:PXD076216")
        print(c.source_data["OMICSDI"]["tissues"], c.source_data["OMICSDI"]["pmids"])
        for rel in await adapter.get_relationships("pride:PXD076216"):
            print(rel["relation_label"], rel["related_id"])


asyncio.run(main())
```

Output (2026-10-09):

```
pride:PXD045508 ...
pride:PXD036969 ...
iprox:PXD027557 ...
['Cerebrospinal Fluid'] ['41932997']
has_publication PMID:41932997
has_organism NCBITaxon:9606
has_disease OMICSDI:DISEASE:Chronic Fatigue Syndrome
has_tissue OMICSDI:TISSUE:Cerebrospinal Fluid
has_omics_type OMICSDI:OMICS_TYPE:Proteomics
similar_to pride:PXD072203
...
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | datasets (type `STUDY`) matching `query`, best first. A dataset accession as query (`geo:GSE16059`, `PXD076216`) resolves to that dataset |
| `search_datasets(query, limit, filters, phrase)` | the search itself, up to 100 results, with facet filters (below) |
| `get_concept_details(id)` | one dataset: title, description, organisms (+ taxonomy ids), omics types, publication date, PMIDs, instruments, experiment types, tissues, diseases, submitting organisations, secondary accessions, citation/view/download counts, repository link |
| `get_relationships(id)` | `has_publication` (`PMID:n`), `has_organism` (`NCBITaxon:n` when known), `has_disease`, `has_tissue`, `has_omics_type`, `uses_instrument` (each capped at 50) and `similar_to` (at most 10, with OmicsDI similarity `score`) |
| `get_mappings(id)` | dataset to its repository accession (`exact`), secondary accessions such as BioProject or the PXD id of a MassIVE dataset (`related`), PMIDs (`PubMed`) and NCBI Taxonomy ids (`NCBITaxon`) |

Concept fields: `primary_id` is `<database>:<accession>`, `primary_label` the title, `definitions` the description (HTML stripped). `categories` has `repository:`, `omics:`, `organism:`, `disease:`, `tissue:` and `year:` entries; `semantic_types` the omics types. For PRIDE and ArrayExpress datasets the same accession is added as a `PRIDE` or `BIOSTUDIES` identifier, so the result can be joined with the [PRIDE](../proteins/pride_adapter.md) and [BioStudies](biostudies_adapter.md) adapters. `source_data["OMICSDI"]` carries the normalised record plus `url` (the repository page, e.g. the GEO or PRIDE page) and `omicsdi_url`.

## Query syntax and filters

The query is Lucene. Unquoted words are **OR-ed**: `chronic fatigue` matches 3,315 datasets, most containing only one word. Multi-word text, and text containing `/` or `-` (`ME/CFS`), is therefore sent as a quoted phrase by default (`phrase=True`); pass `phrase=False` for the broad form, or your own syntax (`"ME/CFS" OR "long covid"`, `disease:"..."`), which is passed through unchanged.

`filters` become `AND` clauses (a list value is OR-ed):

| Filter | Example | Notes |
|---|---|---|
| `omics_type` | `"Proteomics"`, `"Transcriptomics"`, `"Metabolomics"`, `"Genomics"` | case-insensitive. Also `Multiomics`, `Methylation profiling`, `Clinical`, `Models`, `Microarray`, `Other`, `Unknown`. Microbiome studies are `Genomics` (ENA) |
| `organism` | `9606`, `"human"`, `"Mus musculus"` | taxonomy id or common name; unmapped names are ignored |
| `repository` | `"geo"`, `"pride"`, `"arrayexpress"`, `"metabolights"`, `"ena"` | source key or friendly name, translated to OmicsDI's facet spelling |
| `disease`, `tissue` | `"Chronic Fatigue Syndrome"`, `"Blood plasma"` | exact facet values |

Results stay in relevance order; the server's `sortfield` is unusable (see caveats).

## Repository coverage

`/ws/database/all` lists 29 repositories (`source` key in brackets): PRIDE (`pride`), MassIVE (`massive`), jPOST (`jpost`), iProX (`iprox`), PeptideAtlas (`peptide_atlas`), PAXdb (`paxdb`), GPMDB (`gpmdb`), Panorama (`panorama`), MetaboLights (`metabolights_dataset`), Metabolomics Workbench (`metabolomics_workbench`), GNPS (`gnps`), GEO (`geo`), ArrayExpress (`biostudies-arrayexpress`), Expression Atlas (`atlas-experiments`), LINCS (`lincs`), ENA projects (`project`), EVA (`eva`), EGA (`ega`), dbGaP (`dbgap`), BioModels (`biomodels`), Physiome (`physiome`), Cell Collective (`cellcollective`), FAIRDOMHub (`fairdomhub`), BioImages (`bioimages`), BioStudies literature (`biostudies-literature`, the Europe PMC supplementary files, `S-EPMC...`) and `biostudies-other`, NODE (`node`), NCBI (`NCBI`) and ECRIN MDR (`ecrin-mdr-crc`).

Dataset counts by omics type (`/ws/statistics/omics`, 2026-10-09): Genomics 1,192,258; Transcriptomics 287,377; Proteomics 67,143; Metabolomics 10,294; Clinical 10,579; Methylation profiling 9,095; Models 5,098; Multiomics 464; Other 17,201; Unknown 3,332,444 (mostly literature records). Phrase hit counts (all repositories): `"chronic fatigue syndrome"` 927, `"ME/CFS"` 516, `"long covid"` 2,112.

## Caveats and quirks

- **The service is flaky.** A slow request (30-40 s seen) ends in HTTP 404 `Not Found`, and the same URL then answers 404 for a while; a query without any hit can also answer 404 instead of `count: 0`. The adapter treats a 404 from search as "no result", uses a 60 s timeout floor and does not retry 404 (the base class never does). If a query that should match returns `[]`, try again a minute later.
- `dataset/get` and `getSimilar` take `accession=` (the older `acc=` answers HTTP 400). `sortfield=publication_date` answers 404 and `sortfield=id` silently switches to AND semantics, so sorting is not offered.
- `dataset/get` cannot resolve ENA projects (`source: project`, `PRJ...`); `get_concept_details` then rebuilds the concept from the search hit, which has no PMIDs, tissues or diseases.
- ArrayExpress records report all five omics types in `omics_type` in their detail (a catch-all). The adapter reports `[]` for them (raw list in `omics_types_raw`); search hits carry the correct single type, so prefer `search_datasets` for omics-type decisions.
- `publicationDate` is spelled five different ways across repositories; the adapter normalises to `YYYY-MM-DD` and leaves it empty when absent (Metabolomics Workbench often has none). Titles and organisms are sometimes missing; a missing title falls back to the accession.
- The same study appears more than once: GEO `GSE16059` and ArrayExpress `E-GEOD-16059` are separate records (they show up as each other's `similar_to`).
- The detail record contains submitter and lab-head names and e-mail addresses (`submitter`, `submitterMail`, `labHeadMail`). They are not copied into concepts, relationships or test fixtures.
- Not provided: file lists, reanalysis links, the OmicsDI statistics and facet endpoints other than the omics-type counts quoted above.

## Rate limits and errors

No limit is documented. The adapter spaces its requests at least 0.5 s apart (at most 2 per second) and uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]`, details return `None`, relationships and mappings return `[]`.

## Live verification (2026-10-09)

Keyless access confirmed. Measured from this environment:

| Request | Latency | Size |
|---|---|---|
| `dataset/search` `size=1..5` (warm) | 0.05-0.5 s | 5-29 KB (facets included; filtered queries are smaller) |
| `dataset/search` `size=1..5` (cold) | 2-13 s | same |
| `dataset/search` `size=100` | 5.0 s | 108 KB |
| `dataset/search` `size=500` | 6.5 s | 332 KB |
| backend timeout | 30-40 s, then HTTP 404 | 106 B |
| `dataset/get` | 0.04-3.7 s | 1-5 KB |
| `dataset/getSimilar` | 0.2-0.5 s | 17-21 KB |

`python -m knowledge_lookup check OMICSDI` passed (search 0.2 s, details 0.3 s, relationships 1.0 s; one earlier run failed during a backend blip and one relationships call took 20 s). Filters were checked on real responses: `omics_type`, `TAXONOMY`, `repository` and `disease` change the hit count as expected (`chronic fatigue` AND `omics_type:"Proteomics"` 18 hits).

## See also

- [BioStudies / ArrayExpress adapter](biostudies_adapter.md), [PRIDE adapter](../proteins/pride_adapter.md), [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
