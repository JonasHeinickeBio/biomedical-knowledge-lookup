---
description: DisGeNET diseases and gene–disease associations with scores and evidence metrics (API key required).
---

# DisGeNET adapter

Queries the DisGeNET v1 REST API. `search_concepts` finds diseases by name or the diseases associated with a gene, `get_concept_details` fetches a disease record, and the association methods return parsed gene–disease associations (GDAs): which genes are linked to a disease, how strongly (score, evidence index) and since when.

| | |
|---|---|
| Source | `KnowledgeSource.DISGENET` |
| Class | `knowledge_lookup.adapters.DisGeNETAdapter` |
| Requires | `DISGENET_API_KEY` |
| Identifiers | disease `UMLS_C0011849` (also `C0011849`, `MONDO_0005015`), gene symbol `CDK2`, NCBI gene ID `1017` |
| Upstream API | `https://api.disgenet.com/api/v1` |

{% hint style="warning" %}
**API key required.** The key is read with `LookupConfig.get_api_key("disgenet")`: pass `LookupConfig(api_keys={"disgenet": "..."})` or set `DISGENET_API_KEY` (a `.env` file is loaded). Without a key `is_available()` is `False` and `CentralKnowledgeLookup` skips the source. Academic accounts only see curated sources (the API adds a warning to each response).
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DisGeNETAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with DisGeNETAdapter(LookupConfig()) as adapter:
        if not adapter.is_available():
            raise SystemExit("Set DISGENET_API_KEY to use DisGeNET")

        for concept in await adapter.search_concepts("asthma", limit=2):
            print(concept.primary_id, concept.primary_label)

        for concept in await adapter.search_concepts("CDK2", limit=2):
            print(concept.primary_id, concept.primary_label, concept.confidence_score)

        asthma = await adapter.get_concept_details("UMLS_C0004096")
        print(asthma.primary_label, asthma.synonyms[:2], asthma.semantic_types)

        rows = await adapter.get_gene_disease_associations(
            {"disease": "UMLS_C0011849", "page_number": 0}
        )
        for row in (rows or [])[:3]:
            print(row["gene_symbol"], row["disease_name"], row["score"])


asyncio.run(main())
```

Output (academic account):

```
UMLS_C0004096 Asthma
UMLS_C0155877 Allergic asthma
UMLS_C3539878 Triple Negative Breast Neoplasms 0.75
UMLS_C0007134 Renal Cell Carcinoma 0.75
Asthma ['Asthmas', 'ASTHMA BRONCHIAL'] ['Disease or Syndrome (T047)']
KCNJ11 Diabetes Mellitus 1.35
ABCC8 Diabetes Mellitus 1.3
TCF7L2 Diabetes Mellitus 1.2
```

## Searching

`search_concepts(query, limit)` picks the request from the shape of the query:

| Query | Request | Results |
|---|---|---|
| digits only, e.g. `1017` | `/gda/summary?gene_ncbi_id=...` | diseases associated with the gene |
| gene-symbol-like (starts with an upper-case letter; upper-case letters, digits and hyphens; up to 15 characters), e.g. `CDK2`, `BRCA1` | `/gda/summary?gene_symbol=...`; if no gene matches (e.g. `COPD`), the disease name search below | diseases associated with the gene |
| anything else, e.g. `asthma` | `/entity/disease?disease_free_text_search_string=...` | diseases matching the name |

Every result is a disease concept:

| Field | Value |
|---|---|
| `primary_id` | `UMLS_<CUI>`, accepted by `get_concept_details` and by the `disease` association filter |
| `primary_label` | disease name |
| `concept_type` | `DISEASE` |
| `synonyms` | DisGeNET synonyms (name search only) |
| `semantic_types` | UMLS semantic types (`diseaseClasses_UMLS_ST`) |
| `categories` | MeSH disease classes (`diseaseClasses_MSH`) |
| `related` | the gene symbol (gene queries only) |
| `confidence_score` | association score, capped at `1.0` (gene queries); `0.8` (name search) |
| `identifiers` | one `DISGENET` identifier |
| `source_data[DISGENET]` | raw row |

Gene queries return DisGeNET's order (highest score first); one page holds 100 rows. A symbol-like disease name costs two requests.

## Concept details

`get_concept_details(concept_id)` calls `/entity/disease?disease=<id>` and returns the disease with the same fields as the name search, or `None` if it is unknown. It accepts `UMLS_C0004096`, a bare CUI (`C0004096`), `UMLS:C0004096` and other vocabulary IDs such as `MONDO_0004979` or `MONDO:0004979`.

## Source-specific methods

### `get_gene_disease_associations(params: dict[str, Any], raw: bool = False)`

Calls `/gda/summary` with `params` (keys whose value is `None` are dropped) and returns a list of dicts, or `None` if the response has no `payload`. Pass `raw=True` for the full JSON response, including `paging` and `warnings`. Pages hold 100 rows; use `page_number` to page.

Common filters: `gene_ncbi_id`, `gene_ensembl_id`, `gene_symbol`, `uniprot_id`, `disease` (vocabulary-prefixed IDs such as `UMLS_C0011849` or `MONDO_0000728`, comma-separated), `chemical_id`, `source`, `evidence_level`, `min_score` / `max_score` (and the `ei`, `dsi`, `dpi`, `pli` ranges), `min_yearInitial` / `max_yearFinal`, `type`, `dis_class_list`, `order_by`, `page_number`.

Each parsed row has these keys: `assocID`, `gene_symbol`, `gene_ncbi_id`, `gene_ensembl_ids`, `gene_type`, `disease_name`, `disease_vocabularies`, `disease_umls_cui`, `score`, `year_initial`, `year_final`, `num_pmids`, `num_ct_supporting_association`, `gene_dsi`, `gene_dpi`, `gene_pli`, `gene_protein_str_ids`, `gene_protein_class_names`, `disease_classes_msh`, `disease_classes_umls_st`, `disease_classes_do`, `disease_classes_hpo`, `disease_prevalence_class`, `disease_prevalence_geo_area`, `disease_prevalence_type`, `disease_inheritance`, `ei`, `el`.

### `get_gene_disease_associations_evidence(params: dict[str, Any], raw: bool = False)`

Same parameters against `/gda/evidence`. Rows are parsed with the same key mapping as the summary method, so evidence-specific fields are only available with `raw=True`.

## Rate limits and errors

`_make_request` is overridden to always send GET requests, but it still uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). HTTP 429 is retried up to four attempts with 2, 4 and 8 second pauses. The key is sent in the `Authorization` header.

`search_concepts` and `get_concept_details` log errors and return `[]` / `None`. Unlike most adapters, both association methods do **not** catch errors: HTTP failures propagate as `aiohttp.ClientResponseError`.

## See also

- [Open Targets adapter](opentargets_adapter.md): target–disease evidence without an API key
- [UMLS adapter](umls_adapter.md): resolve the CUIs DisGeNET uses for diseases
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): API keys
