---
description: Europe PMC literature search - articles and preprints with abstracts, authors and DOIs.
---

# Europe PMC adapter

Searches Europe PMC (PubMed, PMC, preprints and more) and fetches single articles. Each result is a `CITATION` concept carrying the title, abstract, authors, journal, year and DOI.

| | |
|---|---|
| Source | `KnowledgeSource.EUROPEPMC` |
| Class | `knowledge_lookup.adapters.EuropePMCAdapter` |
| Requires | none |
| Identifiers | `PMID:23193287`, `MED:23193287` or `23193287`; `PMC...` and `PPR...` IDs |
| Upstream API | `https://www.ebi.ac.uk/europepmc/webservices/rest` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EuropePMCAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with EuropePMCAdapter(LookupConfig()) as adapter:
        # Europe PMC query syntax, e.g. restrict to titles
        concepts = await adapter.search_concepts('TITLE:"long covid"', limit=3)
        for concept in concepts:
            print(concept.primary_id, concept.primary_label[:50], concept.categories[-1])

        # IDs returned by search can be passed straight back
        article = await adapter.get_concept_details(concepts[0].primary_id)
        print(article.primary_id == concepts[0].primary_id)

        article = await adapter.get_concept_details("MED:23193287")
        print(article.primary_label, [i.identifier for i in article.identifiers])


asyncio.run(main())
```

Output:

```
PMID:42659593 Pregnancy Outcomes in Individuals With Long COVID. year:2026
PMID:PMC13554463 Microvascular Dysfunction and Redox Imbalance in L year:2026
PMID:42709774 Kinetics of the PASC Index in Long COVID. year:2026
True
GenBank. ['PMID:23193287', 'DOI:10.1093/nar/gks1195']
```

## Searching

`search_concepts(query, limit)` calls `/search` with `resultType=core`, `pageSize=min(limit, 25)` and `format=json`. The query is passed through unchanged, so Europe PMC syntax (`TITLE:`, `AUTH:`, `PUB_YEAR:`, boolean operators) works. Results come in Europe PMC's default order.

| Field | Value |
|---|---|
| `primary_id` | `PMID:<pmid>`; records without a PMID use their Europe PMC `id` instead, e.g. `PMID:PMC13554463` or `PMID:PPR1319214` for preprints |
| `primary_label` | title |
| `concept_type` | `CITATION` |
| `definitions` | abstract, cut to 1000 characters |
| `categories` | `authors:<Last Initials, ...>`, `journal:<title>`, `year:<pubYear>` (when present) |
| `identifiers` | `EUROPEPMC` ID plus `DOI:<doi>` with a `https://doi.org/` URL |
| `sources` | `['EUROPEPMC']` |
| `confidence_score` | `0.85` |

## Concept details

`get_concept_details(concept_id)` calls `/article/{source}/{id}` with `resultType=core` and returns the same fields as search. It accepts:

- the IDs produced by search: `PMID:<pmid>` (fetched from `MED`), `PMID:PMC...` (from `PMC`) and `PMID:PPR...` (from `PPR`);
- a Europe PMC `<source>:<id>` pair such as `MED:23193287` or `PMC:PMC7654321`, and `PMCID:PMC7654321`;
- a bare ID, treated as `MED` (bare `PMC...` IDs as `PMC`).

Prefixes are case-insensitive. Unknown IDs return `None`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [NCBI E-utilities adapter](../other/eutils_adapter.md)
- [All adapters](../README.md)
