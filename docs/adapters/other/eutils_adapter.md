---
description: NCBI E-utilities (PubMed, Gene, Protein, Taxonomy) through bioservices.
---

# NCBI E-utilities adapter

Searches several NCBI Entrez databases in one call (PubMed, Gene, Protein and Taxonomy) and fetches full records, using the `EUtils` client from `bioservices`.

| | |
|---|---|
| Source | `KnowledgeSource.EUTILS` |
| Class | `knowledge_lookup.adapters.EUtilsAdapter` |
| Requires | `[bioservices]` extra |
| Identifiers | `PMID:23193287`, `GeneID:672`, `TaxID:9606`, `Protein:<uid>`, `NP_000483` |
| Upstream API | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (via `bioservices`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EUtilsAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    config = LookupConfig(api_keys={"ncbi_email": "you@example.org"})
    async with EUtilsAdapter(config) as adapter:
        for concept in await adapter.search_concepts("BRCA1", limit=4):
            print(concept.primary_id, concept.concept_type, concept.primary_label[:50])

        article = await adapter.get_concept_details("PMID:23193287")
        print(article.primary_label, article.concept_type)


asyncio.run(main())
```

Output:

```
PMID:42741651 CITATION Overcoming Resistance to PARP Inhibitors in BRCA-M
GeneID:148364138 GENE bap1
Protein:3392429547 PROTEIN BRCT domain-containing protein [Streptococcus sp.]
GenBank. CITATION
```

NCBI returns hits in its own order (newest first for PubMed), so results change over time and the best match is not necessarily included.

## Searching

`search_concepts(query, limit)` sends the query unchanged to `ESearch` on four databases, then fetches the hits of each database with one batched `ESummary` request. Each database contributes up to `ceil(limit / 4)` hits (at least one). Results are returned in the order pubmed, gene, protein, taxonomy and cut to `limit`, so with a small `limit` the later databases can be cut off.

| Database | `primary_id` | `concept_type` | `primary_label` | `source_data[EUTILS]` |
|---|---|---|---|---|
| pubmed | `PMID:<id>` | `CITATION` | article title | `pmid`, `title`, `authors` (names), `journal`, `pubdate` |
| gene | `GeneID:<id>` | `GENE` | gene symbol | `gene_id`, `name`, `description`, `organism` |
| protein | `Protein:<id>` | `PROTEIN` | sequence title | `protein_id`, `name`, `accession` |
| taxonomy | `TaxID:<id>` | `ORGANISM` | scientific name | `tax_id`, `scientific_name`, `common_name` |

Every entry in `source_data[EUTILS]` also has `database` and a one-line summary. Concepts have no identifiers, `sources` is `['EUTILS']` and `confidence_score` is `0.0`.

## Concept details

The ID prefix selects the database: `PMID:` → pubmed, `GeneID:` → gene, `TaxID:` → taxonomy, `Protein:` or `NP_`/`XP_` → protein, `NM_`/`XM_` → nuccore, anything else → pubmed. The adapter calls `EFetch` in text mode (`rettype` `abstract` for pubmed, `gp` for protein, `gb` for nuccore, `full` otherwise) and stores the record in `source_data[EUTILS]["full_record"]`. An empty record returns `None`.

The label comes from `ESummary`: the article title, gene symbol, sequence title or scientific name. If that request fails, the label is a placeholder such as `PubMed Article 23193287`. Types match search (`CITATION`, `GENE`, `PROTEIN`, `ORGANISM`); nuccore records are `MOLECULAR_ENTITY`.

The contact e-mail sent to NCBI comes from `config.get_api_key("ncbi_email")`: pass `api_keys={"ncbi_email": ...}` as in the example, or set `NCBI_EMAIL_API_KEY`. The default is `anonymous@example.com`.

## Rate limits and errors

The `bioservices` calls run in a worker thread through `_thread_with_retry`, which applies the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). If one database fails, a warning is logged and the other databases still return results. Only when all four fail is the error retried and reported to the circuit breaker; search then logs an error and returns `[]`. Details errors are logged and return `None`.

`is_available()` is `False` when `bioservices` is not installed. No NCBI API key is sent, so NCBI's limit of 3 requests per second applies; a search makes up to eight requests (`ESearch` and `ESummary` per database) and a details lookup two.

## See also

- [Europe PMC adapter](../literature/europepmc_adapter.md), [ClinVar adapter](../phenotypes/clinvar_adapter.md)
- [All adapters](../README.md)
- [Configuration](../../getting-started/configuration.md): extras
