---
description: UniProtKB protein entries - names, genes, function and organism.
---

# UniProt adapter

Searches UniProtKB and fetches protein entries by accession. Results carry the gene name, the recommended protein name, the function annotation and the organism, with the full UniProt JSON entry kept in `source_data`.

| | |
|---|---|
| Source | `KnowledgeSource.UNIPROT` |
| Class | `knowledge_lookup.adapters.UniProtAdapter` |
| Requires | none |
| Identifiers | accession, e.g. `P38398` |
| Upstream API | `https://rest.uniprot.org/uniprotkb` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import UniProtAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with UniProtAdapter(LookupConfig()) as adapter:
        # Any UniProt query syntax works, e.g. field filters
        for concept in await adapter.search_concepts("gene:BRCA1 AND organism_id:9606", limit=3):
            print(concept.primary_id, concept.primary_label, concept.synonyms)

        p38398 = await adapter.get_concept_details("P38398")
        print(p38398.primary_label, p38398.categories, p38398.definitions[0][:60])


asyncio.run(main())
```

Output:

```
P38398 BRCA1 ['Breast cancer type 1 susceptibility protein']
E7ENB7 BRCA1 ['Breast cancer type 1 susceptibility protein']
H0Y8D8 BRCA1 ['Breast cancer type 1 susceptibility protein']
BRCA1 ['Organism: Homo sapiens'] E3 ubiquitin-protein ligase that specifically mediates the f
```

## Searching

`search_concepts(query, limit)` calls `/search?query=...&format=json&size=min(limit, 50)`. The query is passed through unchanged, so UniProt query syntax works (`gene:`, `organism_id:`, `reviewed:true`, `AND`/`OR`). A bare `BRCA1` matches entries from every organism and anything that mentions the term; add filters to narrow it.

| Field | Value |
|---|---|
| `primary_id` | primary accession |
| `primary_label` | first gene name; falls back to the recommended protein name, then the accession |
| `concept_type` | `PROTEIN` |
| `synonyms` | recommended protein name (if different from the label) and further gene names |
| `definitions` | texts of the `FUNCTION` comments |
| `categories` | `Organism: <scientific name>` |
| `identifiers` | one `UNIPROT` identifier, URL `https://www.uniprot.org/uniprotkb/<accession>` |
| `confidence_score` | `0.95` |
| `source_data[UNIPROT]` | full UniProt entry |

## Concept details

`get_concept_details(accession)` fetches `/uniprotkb/{accession}.json` and converts it the same way. Unknown accessions return `None`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors left after retries are logged; `search_concepts` then returns `[]` and `get_concept_details` returns `None`.

## See also

- [HGNC adapter](../proteins/hgnc_adapter.md): human gene symbols with UniProt cross-references
- [InterPro adapter](../families/interpro_adapter.md), [STRING adapter](../families/string_adapter.md), [PDB adapter](../families/pdb_adapter.md)
- [All adapters](../README.md)
