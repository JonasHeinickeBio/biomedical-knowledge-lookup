---
description: HGNC approved human gene symbols and names, with NCBI Gene, UniProt and Ensembl cross-references.
---

# HGNC adapter

Searches the HUGO Gene Nomenclature Committee database and fetches approved human gene records. Full records include aliases, previous symbols, locus, gene groups and cross-references to NCBI Gene, UniProt and Ensembl, which makes this a good hub for normalising human gene names.

| | |
|---|---|
| Source | `KnowledgeSource.HGNC` |
| Class | `knowledge_lookup.adapters.HGNCAdapter` |
| Requires | none |
| Identifiers | `HGNC:1100` or an approved symbol such as `BRCA1` |
| Upstream API | `https://rest.genenames.org` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import HGNCAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with HGNCAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("BRCA1", limit=3):
            print(concept.primary_id, concept.primary_label)

        brca1 = await adapter.get_concept_details("HGNC:1100")
        print(brca1.primary_label, brca1.synonyms)
        print([(i.source, i.identifier) for i in brca1.identifiers])


asyncio.run(main())
```

Output:

```
HGNC:1100 BRCA1
HGNC:25829 ABRAXAS1
HGNC:20691 NBR2
BRCA1 DNA repair associated ['BRCA1', 'RNF53', 'BRCC1', 'PPP1R53', 'FANCS']
[('HGNC', 'HGNC:1100'), ('NCBI', '672'), ('UNIPROT', 'P38398'), ('ENSEMBL', 'ENSG00000012048')]
```

## Searching

`search_concepts(query, limit)` calls `/search/{query}`, which matches symbols, aliases, previous symbols and names. HGNC search documents only contain the HGNC ID, the symbol and a score, so search results are thin:

- `primary_id` is the HGNC ID and `primary_label` the symbol
- `synonyms` is `[symbol]`
- `concept_type` is `GENE`, `confidence_score` `0.9`
- there are no cross-references

Call `get_concept_details` for the full record.

## Concept details

`get_concept_details(concept_id)` uses `/fetch/hgnc_id/{id}` when the ID starts with `HGNC:` (case-insensitive) and `/fetch/symbol/{symbol}` otherwise. Only current approved symbols resolve.

| Field | Value |
|---|---|
| `primary_label` | approved gene name |
| `synonyms` | approved symbol, alias symbols, previous symbols |
| `categories` | `locus:<location>` and gene group names |
| `semantic_types` | `[locus_type]`, e.g. `gene with protein product` |
| `identifiers` | `HGNC`, plus `NCBI` (Entrez Gene), `UNIPROT` and `ENSEMBL` with URLs |
| `sources` | `['HGNC']` |
| `source_data[HGNC]` | full HGNC record |

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`.

## See also

- [Ensembl adapter](ensembl_adapter.md), [UniProt adapter](../core/uniprot_adapter.md)
- [All adapters](../README.md)
