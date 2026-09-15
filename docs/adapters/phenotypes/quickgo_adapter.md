---
description: Gene Ontology terms and gene-product annotations from EBI QuickGO through bioservices.
---

# QuickGO adapter

Uses the `bioservices` QuickGO client to search Gene Ontology terms by free text, fetch GO terms by ID (typed by GO aspect) and look up the GO annotations of gene products such as UniProt proteins.

| | |
|---|---|
| Source | `KnowledgeSource.QUICKGO` |
| Class | `knowledge_lookup.adapters.QuickGOAdapter` |
| Requires | `[bioservices]` extra |
| Identifiers | `GO:0006915`; gene products such as `UniProtKB:P04637` or `P04637` |
| Upstream API | `https://www.ebi.ac.uk/QuickGO` (via `bioservices`) |

## Quick example

```python
import asyncio

from knowledge_lookup import KnowledgeSource
from knowledge_lookup.adapters import QuickGOAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with QuickGOAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("apoptosis", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        term = await adapter.get_concept_details("GO:0006915")
        print(term.primary_label, term.synonyms[:2], term.definitions[0][:40])

        for annotation in await adapter.search_concepts("UniProtKB:P04637", limit=2):
            raw = annotation.source_data[KnowledgeSource.QUICKGO]
            print(annotation.primary_id, raw["symbol"], raw["qualifier"], raw["go_evidence"])


asyncio.run(main())
```

Output:

```
GO:0097194 execution phase of apoptosis BIOLOGICAL_PROCESS
GO:0070227 lymphocyte apoptotic process BIOLOGICAL_PROCESS
GO:1902489 hepatoblast apoptotic process BIOLOGICAL_PROCESS
apoptotic process ['activation of apoptosis', 'apoptosis'] A programmed cell death process which be
UniProtKB:P04637_GO:0008285 TP53 acts_upstream_of ISS
UniProtKB:P04637_GO:0051726 TP53 acts_upstream_of ISS
```

## Searching

`search_concepts(query, limit)` combines two lookups and cuts the result to `limit`:

- GO terms from QuickGO's free-text term search (`/ontology/go/search`, via `go_search`), in QuickGO's order. The closest term does not necessarily come first: in the example, `GO:0006915` (apoptotic process) is not among the first three results for `apoptosis`.
- If the query looks like a gene product ID (`UniProtKB:P04637`, or a bare UniProt accession such as `P04637`), also its annotations from `Annotation(geneProductId=...)`. Each annotation becomes a concept `<gene product>_<GO ID>` typed `GENE_DISEASE_ASSOCIATION`. Free text is never sent to the annotation endpoint, which rejects it.

GO term concepts look like this:

| Field | Value |
|---|---|
| `primary_id`, `primary_label` | GO ID and term name |
| `concept_type` | by aspect: `BIOLOGICAL_PROCESS`, `MOLECULAR_FUNCTION`, `CELLULAR_COMPONENT` |
| `identifiers` | one `QUICKGO` identifier |
| `definitions` | the definition text |
| `sources` | `['QUICKGO']` |
| `confidence_score` | `0.0` |
| `source_data[QUICKGO]` | `go_aspect`, `definition` (dict with `text`), `obsolete`, `description` |

Annotation concepts have no identifiers. Their `source_data[QUICKGO]` holds `gene_id`, `symbol`, `go_id`, `qualifier`, `evidence_code` (an ECO ID), `go_evidence` (a GO evidence code such as `ISS`) and `aspect`.

## Concept details

For IDs starting with `GO:`, `get_concept_details` calls `get_go_terms(<id>)` and returns a GO term concept as above. It also fills `synonyms` with the synonym names and adds `synonyms` (with synonym types), `comment`, `usage` and `full_details` to `source_data[QUICKGO]`.

For a gene product ID it returns the first of up to 10 annotations, with the extra `source_data` keys `reference`, `withFrom`, `taxonId`, `date`, `assignedBy`, `extensions` and `full_annotation`. Any other ID returns `None` without a request.

## Rate limits and errors

The `bioservices` calls run in a worker thread through `_thread_with_retry`, which applies the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). `bioservices` returns HTTP errors as an `HTTPResponseError` value instead of raising; the adapter treats those as failures. If one of the two search lookups fails, a warning is logged and the other's results are returned. If every lookup fails, the error is retried, reported to the circuit breaker and logged, and search returns `[]`. Details errors are logged and return `None`.

`is_available()` is `False` when `bioservices` is not installed.

## See also

- [Gene Ontology adapter](geneontology_adapter.md)
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): extras
