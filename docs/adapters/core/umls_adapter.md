---
description: UMLS Metathesaurus concepts (CUIs) with definitions, relations and crosswalks to SNOMED CT, MeSH, ICD and more.
---

# UMLS adapter

Gives full access to the UMLS Metathesaurus through the async client of `umls-python-client`. You can search with vocabulary and semantic-type filters, fetch complete concept profiles (definitions, atoms, relations) and crosswalk a CUI to source vocabularies such as SNOMED CT, MeSH, ICD-10-CM and RxNorm.

| | |
|---|---|
| Source | `KnowledgeSource.UMLS` |
| Class | `knowledge_lookup.adapters.UMLSAdapter` |
| Requires | `[umls]` extra and `UMLS_API_KEY` |
| Identifiers | CUI, e.g. `C0011849` |
| Upstream API | UTS REST API `https://uts-ws.nlm.nih.gov/rest` (via `umls-python-client`) |

{% hint style="warning" %}
**Two requirements.** Without the `[umls]` extra, `UMLSAdapter` is `None` and `KnowledgeSource.UMLS` is missing from `ADAPTER_CLASSES`. Without a key, `is_available()` is `False`. The key comes from `LookupConfig(api_keys={"umls": "..."})` or the `UMLS_API_KEY` environment variable (a `.env` file is loaded). You need a free UTS account to get one.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import UMLSAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    if UMLSAdapter is None:
        raise SystemExit("Install the [umls] extra to use UMLS")

    async with UMLSAdapter(LookupConfig()) as adapter:
        if not adapter.is_available():
            raise SystemExit("Set UMLS_API_KEY to use UMLS")

        hits = await adapter.search_concepts("diabetes", limit=3, semantic_types="T047")
        for concept in hits:
            print(concept.primary_id, concept.primary_label, concept.concept_type)

        dm = await adapter.get_concept_details("C0011849")
        print(dm.primary_label, dm.semantic_types, len(dm.synonyms), len(dm.definitions))

        for m in await adapter.get_mappings("C0011849", target_source="SNOMEDCT_US", limit=2):
            print(m["source"], m["source_id"], m["source_name"])


asyncio.run(main())
```

Output:

```
C0011849 Diabetes Mellitus DISEASE
C0011860 Diabetes Mellitus, Non-Insulin-Dependent DISEASE
C0011847 Diabetes DISEASE
Diabetes Mellitus ['Disease or Syndrome'] 85 12
SNOMEDCT_US 267467004 Diabetes mellitus
SNOMEDCT_US 154671004 Diabetes mellitus
```

## Searching

```python
async def search_concepts(
    query: str,
    limit: int = 20,
    *,
    sabs: str | None = None,             # e.g. "SNOMEDCT_US,RXNORM"
    semantic_groups: str | None = None,  # e.g. "DISO"
    semantic_types: str | None = None,   # TUIs, e.g. "T047,T191"
    search_type: str = "words",          # "exact", "leftTruncation", "normalizedString", ...
    partial_search: bool = False,
) -> list[UnifiedConcept]
```

Requests `min(limit, 100)` results with `returnIdType=concept`. For each result:

| Field | Value |
|---|---|
| `primary_id` | CUI |
| `identifiers` | one `UMLS` identifier, URL `https://uts.nlm.nih.gov/uts/umls/concept/<CUI>` |
| `categories` | `[root_source]`, e.g. `['MTH']` |
| `concept_type` | from the root source (SNOMED CT and ICD → `DISEASE`, RxNorm → `DRUG`, MeSH → `CHEMICAL`, HPO → `PHENOTYPE`, ...); for `MTH` or unknown sources, from the semantic type names in the response |
| `confidence_score` | `0.95` exact label match, `0.85` if one contains the other, else `0.75` |
| `source_data[UMLS]` | `{"root_source", "uri"}` |

Search results have no synonyms or definitions; use `get_concept_details` for those.

{% hint style="info" %}
As of the 2026AA release `semantic_groups` may return zero results. Filter with `semantic_types` TUIs instead.
{% endhint %}

## Concept details

`get_concept_details("C0011849")` fetches the CUI record and the concept profile (definitions, relations and atoms) and returns:

- `semantic_types`: semantic type names, e.g. `['Disease or Syndrome']`
- `concept_type`: from the semantic type names, falling back to the semantic type TUIs (e.g. `T047` → `DISEASE`)
- `definitions`: from every source vocabulary
- `synonyms`: the preferred atom name plus all other atom names, in every language
- `categories`: the root sources of the atoms, unordered
- `parents` / `children` / `related`: relation targets as returned by UTS (URIs), sorted by relation label (`PAR`/`isa` → parents, `CHD` → children, everything else → related)
- `source_data[UMLS]`: semantic types, atoms and relations as dicts
- `confidence_score`: `0.95`

## Source-specific methods

| Method | Returns |
|---|---|
| `get_mappings(concept_id, *, target_source=None, limit=50)` | crosswalk from a CUI's atoms: dicts with `source`, `source_id`, `source_name`, `term_type`, `language`, `cui`, de-duplicated by source and code |
| `get_relationships(concept_id, *, relation_labels=None, limit=100)` | dicts with `relation_label`, `additional_label`, `related_id`, `related_name`, `related_id_name`, `source`, `uri`; filter with e.g. `relation_labels="PAR,CHD"` |
| `bulk_search(queries, limit=5, *, sabs=None, semantic_groups=None)` | `dict[str, list[UnifiedConcept]]`, one entry per query |
| `iter_definitions(concept_id, page_size=25)` | async iterator of `{value, root_source, source_originated}` |
| `iter_relations(concept_id, page_size=200, *, relation_labels=None)` | async iterator of the same dicts as `get_relationships` |

## Rate limits and errors

This adapter does not use the shared HTTP retry. Retries and throttling are left to `umls-python-client`, and a circuit breaker attached by `CentralKnowledgeLookup` is never notified. Every method logs failures and returns an empty result (`[]`, `{}` or `None`). `close()` closes the client session.

## See also

- [BioLinker adapter](../other/biolinker_adapter.md): links free text to CUIs
- [BioPortal adapter](../ontologies/bioportal_adapter.md): SNOMED CT, MeSH and ICD as separate ontologies
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): API keys and extras
- [Searching concepts](../../guides/searching-concepts.md)
