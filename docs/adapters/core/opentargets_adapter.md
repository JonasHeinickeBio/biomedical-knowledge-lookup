---
description: Targets and diseases from the Open Targets Platform GraphQL API.
---

# Open Targets adapter

Searches targets (genes) and diseases on the Open Targets Platform and fetches target records by Ensembl gene ID and disease records by ontology ID. Treat it as an entry point into Open Targets IDs. The adapter does not expose association or evidence queries.

| | |
|---|---|
| Source | `KnowledgeSource.OPENTARGETS` |
| Class | `knowledge_lookup.adapters.OpenTargetsAdapter` |
| Requires | none |
| Identifiers | target `ENSG00000012048`; disease `MONDO_0004979`, `EFO_0000270`, `Orphanet_145` |
| Upstream API | `https://api.platform.opentargets.org/api/v4/graphql` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OpenTargetsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OpenTargetsAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("asthma", limit=3):
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        brca1 = await adapter.get_concept_details("ENSG00000012048")
        print(brca1.primary_label, brca1.definitions[-1], brca1.identifiers[0].url)

        asthma = await adapter.get_concept_details("MONDO_0004979")
        print(asthma.primary_label, asthma.categories, asthma.synonyms[:2])


asyncio.run(main())
```

Output:

```
MONDO_0004979 asthma DISEASE
MONDO_0005405 childhood onset asthma DISEASE
MONDO_0004784 allergic asthma DISEASE
BRCA1 Biotype: protein_coding https://platform.opentargets.org/target/ENSG00000012048
asthma ['phenotype', 'respiratory or thoracic disease'] ['bronchial hyperreactivity', 'chronic obstructive asthma']
```

## Searching

`search_concepts(query, limit)` POSTs a GraphQL `search(queryString, entityNames: ["target", "disease"], page: {index: 0, size: min(limit, 100)})` query. Each hit is converted with its own entity type:

| Field | Target hit | Disease hit |
|---|---|---|
| `primary_id` | Ensembl gene ID | ontology ID, e.g. `MONDO_0004979` |
| `primary_label` | gene symbol | disease name |
| `concept_type` | `GENE` | `DISEASE` |
| `definitions` | hit description (approved name) | hit description |
| `categories` | hit categories (biotype) | hit categories (therapeutic areas) |
| `identifiers` | URL `https://platform.opentargets.org/target/<id>` | URL `https://platform.opentargets.org/disease/<id>` |

Every concept has `confidence_score` `0.9` and the raw hit (`id`, `name`, `entity`, `description`, `category`) in `source_data`.

## Concept details

`get_concept_details(concept_id)` decides the entity type from the ID:

- IDs starting with `ENSG` are targets, looked up with `target(ensemblId: ...)`.
- Everything else is a disease or phenotype (`EFO_`, `MONDO_`, `Orphanet_`, `HP_`, ...), looked up with `disease(efoId: ...)`. CURIE-style IDs are normalized: `MONDO:0004979` becomes `MONDO_0004979`, `ORPHA:145` becomes `Orphanet_145`.

A target comes back as a `GENE` concept: label `approvedSymbol`, `definitions` `[<first function description>, "Biotype: <biotype>"]`, `synonyms` approved symbol, approved name and synonym labels, identifier URL `https://platform.opentargets.org/target/<id>`.

A disease comes back as a `DISEASE` concept: label `name`, `definitions` `[description]`, `synonyms` all synonym terms, `categories` therapeutic area names, identifier URL `https://platform.opentargets.org/disease/<id>`; cross-references (`dbXRefs`) are in `source_data`. Unknown IDs return `None`.

## Rate limits and errors

Requests are JSON POSTs through the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). GraphQL errors arrive as HTTP 200 responses without `data`; they are logged as warnings and surface as `[]` or `None` rather than as exceptions.

## See also

- [DisGeNET adapter](disgenet_adapter.md): gene–disease association scores
- [Ensembl adapter](../proteins/ensembl_adapter.md), [Mondo adapter](mondo_adapter.md)
- [All adapters](../README.md)
