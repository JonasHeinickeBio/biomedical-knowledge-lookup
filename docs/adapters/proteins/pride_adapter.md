---
description: PRIDE Archive proteomics projects (PXD) with species, tissues, diseases, instruments, modifications and publications (metadata only, keyless).
---

# PRIDE adapter

Searches the [PRIDE Archive](https://www.ebi.ac.uk/pride/) (EMBL-EBI, ProteomeXchange), the main repository for mass-spectrometry proteomics. A project (`PXD...`, or `PAD...` for affinity proteomics) records species, tissues, diseases, instruments, identified modifications and the publication that describes it, so you can find, for example, cerebrospinal-fluid or plasma proteomes of ME/CFS and Long COVID patients. The adapter returns project **metadata and URLs only**: raw and result files are never downloaded, only their number is reported.

| | |
|---|---|
| Source | `KnowledgeSource.PRIDE` |
| Class | `knowledge_lookup.adapters.PRIDEAdapter` |
| Requires | none (keyless, JSON) |
| Identifiers | project accession `PXD076216`, `PAD000026`, `RPXD...`; a `PRIDE:` prefix and lower case are accepted |
| Upstream API | `https://www.ebi.ac.uk/pride/ws/archive/v2` |
| Licence | metadata under the EMBL-EBI terms of use; each project states its own data licence (`license`, for example CC0 or "EBI terms of use") |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import PRIDEAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with PRIDEAdapter(LookupConfig()) as adapter:
        # human plasma proteomics projects annotated with chronic fatigue syndrome
        for c in await adapter.search_projects(
            "fatigue",
            limit=3,
            filters={"disease": "Chronic fatigue syndrome", "tissue": "Blood plasma"},
        ):
            print(c.primary_id, c.primary_label[:60])

        project = await adapter.get_concept_details("PXD076216")
        data = project.source_data["PRIDE"]
        print(data["tissues"], data["license"], data["files_count"])
        for rel in await adapter.get_relationships("PXD076216"):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])


asyncio.run(main())
```

Output (2026-10-09):

```
PXD073644 Proteomic characterization of plasma extracellular vesicles ...
PXD072203 Higher concentration of extracellular vesicles in plasma ...
PXD068504 Mapping the complexity of ME/CFS: Evidence for abnormal ...
[{'name': 'Cerebrospinal fluid', 'id': 'BTO:0000237'}] Creative Commons Public Domain (CC0) 36
has_species NCBITaxon:9606 Homo sapiens (human)
has_tissue BTO:0000237 Cerebrospinal fluid
has_disease DOID:8544 Chronic fatigue syndrome
uses_instrument MS:1001911 Q Exactive
has_modification MOD:00425 monohydroxylated residue
...
has_publication PMID:41932997 PubMed 41932997
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | projects (type `STUDY`) matching the keyword. A `PXD`/`PAD` accession as query resolves to that project |
| `search_projects(query, limit, filters, sort, descending)` | the search itself: up to 100 results, 0-based pages. Filters `species`, `disease`, `tissue` (exact values as shown in results); `sort` is `relevance` (newest first when scores tie), `submission_date` or `publication_date` |
| `get_concept_details(id)` | one project with ontology-annotated terms, publications, licence, dataset DOI and **file count** (one extra 1-row request that only reads a response header) |
| `get_relationships(id)` | `has_species` (`NCBITaxon:n`), `has_tissue` (`BTO:n`), `has_disease` (`DOID:n`), `uses_instrument` (`MS:n`), `has_modification` (`MOD:n`), `has_experiment_type` (`PRIDE:n`) and `has_publication` (`PMID:n`, `doi` as extra key). Each list is capped at 50 |
| `get_mappings(id)` | own accession (`PRIDE`, `exact`), the dataset DOI (`10.6019/PXD...`, `exact`), publication PMIDs (`PubMed`) and DOIs (`DOI`), NCBI Taxonomy ids (`NCBITaxon`) |

Concept fields: `primary_id` is the accession, `primary_label` the title, `definitions` the project description, `synonyms` the submitter keywords. `categories` has `species:`, `tissue:`, `disease:`, `instrument:`, `experiment_type:` and `year:` entries, `semantic_types` the experiment types (for example "Data-dependent acquisition"). An `OMICSDI` identifier `pride:<acc>` links to the [OmicsDI adapter](../literature/omicsdi_adapter.md). `source_data["PRIDE"]` holds the normalised record: species, tissues, diseases, instruments and modifications (name plus ontology id when known), experiment types, software, quantification methods, dates, PMIDs, DOIs, licence, submission type, institutional `affiliations`, countries, file count and the project page URL.

Search hits carry plain term names only (no ontology ids, no modifications, no licence). Ontology and taxonomy ids in relationships and mappings therefore come from the detail call, one request each.

## Privacy

The raw project records contain submitter and lab-head **names, e-mail addresses and ORCIDs**. The adapter never reads those fields: only the institutional `affiliations` and `countries` (lab group level) are kept, and neither the concepts nor the test fixtures contain personal contact details.

## Caveats

- **`projects?keyword=` ignores the keyword.** It just lists projects (a nonsense keyword returns the same five as `fatigue`), which is what the upstream documentation suggests for keyword search. The adapter uses `search/projects`, which really filters. A reference implementation based on the documented endpoint would return unrelated projects.
- `filter` accepts `field==value` pairs joined by commas; the working field names are `organisms`, `diseases` and `organismsPart` (the documented `*_facet` names are silently ignored). Values are case-sensitive; there is no OR syntax, so a list value uses its first entry.
- `sortConditions` works for `submissionDate` and `publicationDate`; other values (`downloadCount`) are ignored. Some hits show a `publicationDate` later than the submission by months (embargo-style release dates), so do not read it as the day the data became public.
- `projects/<acc>` answers `Content-Type: text/plain` with JSON inside; the adapter parses the body itself.
- The search response has no total; `total_records` is only in a response header, which the adapter reads for file counts but not for search totals.
- A missing accession answers HTTP 404 with a plain-text message; the adapter returns `None`/`[]`.
- Not provided: file listings and download links, the `stats` and `facet` endpoints, the protein-level and spectrum-level PRIDE data.

## Rate limits and errors

No limit is documented. The adapter spaces its requests at least 0.5 s apart (at most 2 per second) and uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]`, details return `None`, relationships and mappings return `[]`.

## Live verification (2026-10-09)

Keyless access confirmed.

| Request | Latency | Size |
|---|---|---|
| `search/projects` `pageSize=5` | 0.1-0.4 s | 27 KB |
| `search/projects` `pageSize=100` (19 hits) | 2.7 s | 191 KB |
| `projects/PXD076216` | 0.1 s | 5.5 KB |
| `projects/PXD076216/files?pageSize=1` | 0.1-2.5 s | 1 KB (header `total_records: 36`) |

`python -m knowledge_lookup check PRIDE` passed (search 1.8 s, details, 9 relationship edges in 0.5 s). Checked on real responses that filters filter (`organisms==Mus musculus (mouse)` returns only mouse projects, `diseases==Chronic fatigue syndrome` only annotated projects) and that `sortDirection=ASC` reverses the order. Hit counts seen: `fatigue` 26, `long covid` 19.

## See also

- [OmicsDI adapter](../literature/omicsdi_adapter.md), [BioStudies / ArrayExpress adapter](../literature/biostudies_adapter.md), [UniProt adapter](../core/uniprot_adapter.md)
- [All adapters](../README.md)
