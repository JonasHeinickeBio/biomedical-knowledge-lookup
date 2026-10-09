---
description: EMBL-EBI BioStudies and ArrayExpress functional genomics studies (metadata, publications, GEO/ENA links; keyless, no file downloads).
---

# BioStudies / ArrayExpress adapter

Searches [EMBL-EBI BioStudies](https://www.ebi.ac.uk/biostudies/), which since 2021 also hosts **ArrayExpress** (microarray, RNA-seq, spatial transcriptomics, methylation and other functional genomics studies; accessions `E-MTAB-`, `E-GEOD-`, `E-MEXP-`...). It is a good place to find transcriptomics studies on ME/CFS or Long COVID together with their publication (PMID, DOI), organism, assay technology and the matching GEO or ENA record. The adapter returns study **metadata and URLs only**: it never lists or downloads files, only their count and the link of the study's file directory.

| | |
|---|---|
| Source | `KnowledgeSource.BIOSTUDIES` |
| Class | `knowledge_lookup.adapters.BioStudiesAdapter` |
| Requires | none (keyless, JSON) |
| Identifiers | study accession `E-GEOD-16059`, `E-MTAB-14669`, `S-EPMC7260435`; a `BIOSTUDIES:` or `ARRAYEXPRESS:` prefix is accepted |
| Upstream API | `https://www.ebi.ac.uk/biostudies/api/v1` |
| Licence | EMBL-EBI terms of use, open metadata; every study keeps the licence stated by its submitters |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import BioStudiesAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with BioStudiesAdapter(LookupConfig()) as adapter:
        # ArrayExpress studies on chronic fatigue, newest first
        for c in await adapter.search_studies(
            "chronic fatigue syndrome", limit=3, sort="release_date", phrase=True
        ):
            print(c.primary_id, c.source_data["BIOSTUDIES"]["release_date"], c.primary_label[:50])

        study = await adapter.get_concept_details("E-GEOD-16059")
        print(study.source_data["BIOSTUDIES"]["organisms"], study.source_data["BIOSTUDIES"]["files_count"])
        for rel in await adapter.get_relationships("E-GEOD-16059"):
            print(rel["relation_label"], rel["related_id"])
        for m in await adapter.get_mappings("E-GEOD-16059"):
            print(m["toSource"], m["toId"])


asyncio.run(main())
```

Output (2026-10-09):

```
E-MTAB-9674 2021-11-11 ...
...
['Homo sapiens'] 178
has_publication PMID:19503787
has_organism NCBITaxon:9606
has_experiment_type EFO:0002768
uses_technology BIOSTUDIES:TECHNOLOGY:Array assay
has_assay_molecule BIOSTUDIES:ASSAY_MOLECULE:RNA assay
has_geo_series GEO:GSE16059
ArrayExpress E-GEOD-16059
PubMed 19503787
DOI 10.1371/journal.pone.0005805
GEO GSE16059
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | studies (type `STUDY`) from the **ArrayExpress collection** matching `query`. An accession as query resolves to that study |
| `search_studies(query, limit, collection, sort, descending, phrase)` | the search itself, up to 100 results. `collection` defaults to `arrayexpress`; `"all"` searches the whole archive; any other collection name (for example `bioimages`) works too. `sort` is `relevance`, `release_date`, `files`, `links` or `views`. `phrase=True` quotes multi-word text |
| `get_concept_details(id)` | the full study record plus the file count (two requests: `studies/<acc>` and `.../info`) |
| `get_relationships(id)` | `has_publication` (`PMID:n`; `DOI:...` when only a DOI is recorded; `doi` as extra key), `has_organism` (`NCBITaxon:n`), `has_experiment_type` (`EFO:n` when the submitter gave a term), `uses_technology`, `has_assay_molecule`, `linked_study` (another BioStudies accession) and `has_geo_series` / `has_ena_project` / `has_biosample` / `has_external_record` for other links |
| `get_mappings(id)` | own accession (`ArrayExpress` or `BioStudies`, `exact`), PMIDs (`PubMed`), DOIs (`DOI`) and recorded external accessions: GEO (`exact`), ENA, BioSamples, SRA, BioProject, PRIDE, MetaboLights (`related`) |

Concept fields: `primary_id` is the accession, `primary_label` the title, `definitions` the description (details only). `categories` has `collection:`, `organism:`, `study_type:`, `technology:`, `disease:` and `year:` entries, `semantic_types` the study (experiment) types. ArrayExpress accessions also get an `OMICSDI` identifier (`biostudies-arrayexpress:<acc>`) for joining with the [OmicsDI adapter](omicsdi_adapter.md). `source_data["BIOSTUDIES"]` holds: release date, organisms and taxonomy ids, study types with EFO term ids, technologies, assay molecules, sample count, **author count** (names and e-mails are deliberately not copied), submitting organisations, publications (PMID, DOI, title), links, `files_count`, `files_url` and the study page URL. Search hits are thinner: title, release date, file count, link count and view count only.

## Collections and query behaviour

- **Default collection.** Without a collection the search covers the whole archive and is dominated by 100,000+ Europe PMC supplementary records (`S-EPMC...`): `long covid` finds 46,395 studies across the archive but 2,623 in ArrayExpress. `search_concepts` therefore searches `arrayexpress`; use `collection="all"` deliberately.
- **Synonym expansion.** The engine expands words with EFO synonyms (`chronic fatigue` also matches `tiredness` and `exhaustion`), so unquoted text is broad (`chronic fatigue syndrome` finds 3,485 ArrayExpress studies, relevance ordered). `phrase=True` finds the 18 that contain the exact phrase; `"long covid"` as a phrase finds 1 (E-MTAB-14669). `ME/CFS` finds none in ArrayExpress, so combine terms (`myalgic encephalomyelitis OR chronic fatigue`) and read the top of the relevance list.
- `page` starts at 1 and the page size is kept constant while paging (the API counts pages, not offsets); 100 per page was verified. `totalHits` is flagged inexact upstream and is not exposed.

## Caveats

- `studies/<acc>` is a nested "section" tree. For studies with many files it embeds per-file metadata (159 KB for E-GEOD-16059's 178 files); only the JSON metadata is read, no file is fetched and none is reported except the count.
- Organism, disease and technology are free text typed by submitters; there is no controlled vocabulary except the optional EFO term of the study type. Studies outside ArrayExpress (BioImages, literature supplements) have other section layouts; the adapter reads what is present and leaves the rest empty.
- GEO ids appear only where the submitter or curator recorded the link (ArrayExpress `E-GEOD-n` mirrors GEO `GSEn`, but the adapter does not infer that).
- An unknown accession answers HTTP 404 `{"errorMessage": "Study not found"}`; the adapter returns `None`/`[]`.

## Rate limits and errors

No limit is documented. The adapter spaces its requests at least 0.5 s apart (at most 2 per second) and uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]`, details return `None`, relationships and mappings return `[]`.

## Live verification (2026-10-09)

Keyless access confirmed.

| Request | Latency | Size |
|---|---|---|
| `arrayexpress/search` `pageSize=3` | 0.2-0.5 s | 2.3 KB |
| `arrayexpress/search` `pageSize=100` | 0.6 s | 1 KB (one hit) |
| `studies/E-GEOD-16059` | 0.5 s | 159 KB |
| `studies/E-MTAB-14669` | 0.14 s | 18 KB |
| `studies/<acc>/info` | 0.06 s | 1.3 KB |

`python -m knowledge_lookup check BIOSTUDIES` passed (search 0.3 s, details, 5 relationship edges in 1.0 s). Confirmed on real responses: the collection filter (`/arrayexpress/search` and `?collection=arrayexpress` both return only `E-` accessions; an unknown collection returns 0 hits), `sortBy=release_date` ordering, and that `type=study` does not change the result.

## See also

- [OmicsDI adapter](omicsdi_adapter.md), [PRIDE adapter](../proteins/pride_adapter.md), [Europe PMC adapter](europepmc_adapter.md)
- [All adapters](../README.md)
