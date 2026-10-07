---
description: NCBI LitCovid COVID-19 and Long COVID literature with topic categories and entity annotations (keyless).
---

# LitCovid adapter

Searches [NCBI LitCovid](https://www.ncbi.nlm.nih.gov/research/coronavirus/), a curated hub of COVID-19 / SARS-CoV-2 literature (about 490,000 PubMed articles on 2026-10-07). Every article is classified into one or more of eight topic categories and tagged with a few entities. LitCovid carries a dedicated `LongCovid` condition tag, which makes it a quick way to pull Long COVID / post-acute sequelae literature and to find overlap with ME/CFS (`"chronic fatigue syndrome" OR "myalgic encephalomyelitis"` finds 617 articles).

| | |
|---|---|
| Source | `KnowledgeSource.LITCOVID` |
| Class | `knowledge_lookup.adapters.LitCovidAdapter` |
| Requires | none (keyless, JSON) |
| Identifiers | articles `PMID:34316076` (bare digits, `LITCOVID:PMID:...` and PMCIDs also accepted); topics `LITCOVID:TOPIC:Treatment` |
| Upstream API | `https://www.ncbi.nlm.nih.gov/research/coronavirus-api` |
| Licence | US Government work, no restrictions. Please cite Chen, Allot & Lu, *Nature* 579:193 (2020) and *Nucleic Acids Res.* (2020), as requested in the official export header |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import LitCovidAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with LitCovidAdapter(LookupConfig()) as adapter:
        # newest Long COVID articles that LitCovid classed as Treatment
        for a in await adapter.search_articles(
            "long covid", limit=3, filters={"topic": "Treatment"}, sort="date"
        ):
            print(a.primary_id, a.primary_label[:60])

        article = await adapter.get_concept_details("PMID:39472619")
        print(article.source_data["LITCOVID"]["entities"])
        for rel in await adapter.get_relationships("PMID:39472619"):
            print(rel["relation_label"], rel["related_name"])

        print(await adapter.get_topic_counts("post-acute sequelae"))


asyncio.run(main())
```

## Methods

| Method | Returns |
|---|---|
| `search_concepts(query, limit)` | articles (CITATION) matching `query`, plus the topic categories whose name contains it. A bare `PMID:n` query resolves that article. A multi-word phrase that finds nothing is retried as `w1 AND w2 ...` |
| `search_articles(query, limit, filters, sort)` | the article search itself: up to 100 results (10 per request, paged), optional filters, `sort="date"` for newest first |
| `get_concept_details(id)` | one article (by PMID or PMCID) or topic category (with its article count) |
| `get_relationships(id)` | article: `has_topic`, `annotated_with_condition`, `mentions_drug`, `mentions_variant`, `mentions_vaccine`, `mentions_strain` (each capped at 50). Topic: up to ten newest `has_article` edges |
| `get_mappings(id)` | article: PMID to `PubMed` and, when present, to its `PMC` id |
| `get_topic_counts(query=None, topic=None)` | `{topic: article count}` for the eight categories (8 requests), optionally restricted to a query |

Concept fields: `primary_id` `PMID:<n>`, `primary_label` the title, `concept_type` `CITATION`. `categories` has `journal:`, `year:`, `topic:`, `country:` and `condition:LongCovid` entries. A PMC id is added as an `EUROPEPMC` identifier. `source_data["LITCOVID"]` holds the curated record: journal, year, authors, volume/issue/pages, topics, countries, `entities` (condition, drug, variant, vaccine, strain), the NLM-style citation and the PubMed URL. **LitCovid returns no abstracts**; fetch them from [Europe PMC](europepmc_adapter.md) or PubMed by PMID.

## Query syntax and filters

`search_articles` sends the text as an exact phrase when it is plain multi-word text (`long covid` becomes `"long covid"`). Text with quotes, `AND`/`OR`/`NOT`, parentheses or `field:value` is passed through unchanged. `filters` accepts `topic`, `journal`, `country`, `condition` (e.g. `LongCovid`), `drug`, `variant`, `vaccine` and `strain`; a list value is OR-ed; all clauses are AND-ed. Fields can also be written directly: `topics:Diagnosis`, `e_condition:LongCovid`, `countries:Germany`, `journal:"Sci Rep"`, `pmid:34316076`, `pmcid:PMC9878254`.

Topic categories (counts measured 2026-10-07; an article may have several): Treatment 124,820, Prevention 110,449, Diagnosis 80,725, Mechanism 57,625, Case Report 20,653, Transmission 9,706, Epidemic Forecasting 4,179, General Info 1,939. Within `"long covid"` (8,030 articles): Treatment 3,016, Diagnosis 2,566, Mechanism 1,366, Prevention 633, Case Report 210. The API publishes no definition text for the topics.

## Quirks learned live

- **The query parameter is `text`.** `query=`, `q=`, `page_size=`, `limit=`, `size=` and `fq=` are silently ignored: `?query=long%20covid` returns the whole database (493,888 hits), not a Long COVID subset. The page size is fixed at 10.
- Unquoted `long covid` means `long OR covid` (428,626 hits); the quoted phrase gives 8,030.
- Entity coverage is partial: `e_condition`, `e_variants`, `e_vaccines`, `e_strains` come with each result, but **`e_drugs` only appears in the response's facet block**, so drug entities are available from `get_concept_details` / `get_relationships` (a one-article `pmid:` query) but not from search results. There are no gene or disease entities. `e_variants` can list dozens of rs numbers or HGVS changes for one article.
- Wildcards (`e_drugs:*`) do not work, and malformed queries return an empty result rather than an error.
- `export/tsv` ignores `limit`, returns the whole result set (1 MB for 8,030 hits) and only contains pmid/title/journal, so it is not used.
- Relevance ranking is the default; `sort=date desc` is honoured. Deep paging works (page 803 of 803) but costs one request per 10 articles.

## Rate limits, latency and errors

No limit is documented. The adapter stays under about 3 requests per second (0.35 s between the paged or per-topic requests of one call) and uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Measured latency is 0.2 to 3 s; the largest topic count took 13.7 s once, so `min_request_timeout` is 60 s. Errors are logged; searches return `[]` and detail calls return `None`.

## See also

- [Europe PMC adapter](europepmc_adapter.md) for abstracts and full-text search, [PubTator adapter](pubtator_adapter.md) for gene/disease/chemical entities per article, [OpenAlex adapter](openalex_adapter.md) for the citation graph
- [All adapters](../README.md)
