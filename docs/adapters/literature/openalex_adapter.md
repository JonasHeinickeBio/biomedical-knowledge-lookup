---
description: OpenAlex scholarly works, topics and citation links (keyless; optional API key and polite-pool mailto from environment variables).
---

# OpenAlex adapter

Looks up scholarly works and research topics in [OpenAlex](https://openalex.org), an open (CC0) catalogue of scholarly works with a citation graph, topic assignments with scores, and open-access information. It complements [Europe PMC](europepmc_adapter.md) and [LitCovid](litcovid_adapter.md) for literature mining: abstracts (when the publisher allows), citation counts, who cites whom, and DOI/PMID/PMCID/MAG cross-references.

| | |
|---|---|
| Source | `KnowledgeSource.OPENALEX` |
| Class | `knowledge_lookup.adapters.OpenAlexAdapter` |
| Requires | none. Optional `OPENALEX_API_KEY` (free key, 10x daily budget) and `OPENALEX_MAILTO` (polite-pool address) |
| Identifiers | works `W4316014106`, `OPENALEX:W...`, `https://openalex.org/W...`, DOI (`10.1038/s41579-022-00846-2`, `doi:`, `https://doi.org/...`), `PMID:36639608` (or a PubMed URL), `mag:3143129303`; topics `T11368` |
| Upstream API | `https://api.openalex.org` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OpenAlexAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OpenAlexAdapter(LookupConfig()) as adapter:
        review = await adapter.get_concept_details("PMID:36639608")  # free lookup
        data = review.source_data["OPENALEX"]
        print(review.primary_id, data["cited_by_count"], data["open_access"]["status"])

        for rel in await adapter.get_relationships(review.primary_id, limit=3):
            print(rel["relation_label"], rel["related_id"], rel["related_name"][:50])

        print(await adapter.get_mappings("W4316014106"))
        for w in await adapter.search_works(
            "post-acute sequelae of covid-19", limit=3, filters={"year": 2024, "oa": True},
            sort="cited_by_count:desc",
        ):
            print(w.primary_id, w.primary_label[:60])


asyncio.run(main())
```

## Methods

| Method | Returns | Cost (keyless budget) |
|---|---|---|
| `search_concepts(query, limit)` | works plus the best 3 topics; a DOI / `PMID:` / OpenAlex id resolves directly | 20 credits (two searches); ids are free |
| `search_works(query, limit, filters, sort)` | works, `limit` <= 100, relevance order by default | 10 credits |
| `search_topics(query, limit)` | topics | 10 credits |
| `get_concept_details(id)` | work or topic by singleton lookup | free |
| `get_relationships(id, limit=25)` | see below | free singleton + 1 credit per citation list |
| `get_mappings(id)` | work: DOI, PMID, PMCID, MAG; topic: Wikipedia | free |
| `get_referenced_works(id, limit)`, `get_citing_works(id, limit)` | the `cites` / `cited_by` edges only | 1 credit each |

`filters` takes friendly names (`year`, `type`, `open_access`/`oa`, `topic`, `primary_topic`, `from_date`, `to_date`, `cites`, `has_abstract`, `language`) or raw OpenAlex filter names; list values are OR-ed with `|`. Values containing characters outside a conservative set are dropped rather than sent. `sort` is OpenAlex syntax (`cited_by_count:desc`, `publication_date:desc`).

## What the concepts contain

Works are `CITATION` concepts: `primary_id` the W-id, label the title, `definitions[0]` the rebuilt abstract when OpenAlex has one, `synonyms` the OpenAlex keywords, `semantic_types` the work type (article, review, ...), `categories` with `year:`, `journal:`, `oa:<status>` and `topic:<name>`. DOI, PMID and PMCID are added as `EUROPEPMC` identifiers (`DOI:10...`, `PMID:...`). `source_data["OPENALEX"]` holds the curated record: authors (first 10, with ORCID), citation and reference counts, field-weighted citation impact, retraction flag, open-access status and URL, topics with scores and field/subfield/domain, keywords, the older concept tags with Wikidata ids, and the abstract. Topics are `UNKNOWN`-typed concepts (there is no research-topic type) with the description, keywords, and subfield/field/domain.

`get_relationships(id, limit)` for a work:

- `has_topic`: the work's topics (up to 3) with OpenAlex's score and field
- `cites`: the first `limit` referenced works, titled through one batch lookup (`filter=openalex:W1|W2...`). The order is the record's own, not by importance
- `cited_by`: the `limit` most-cited citing works, each with `total_citing` (the full count from the response meta) and `cited_by_count`. `limit=0` skips both citation calls

For a topic: `part_of` subfield / field / domain, and `sibling_topic`.

## Rate limits and cost (changed since the old polite pool; measured 2026-10-07)

OpenAlex now meters usage in **credits per day**, reported in `X-RateLimit-*` response headers:

- keyless: 1,000 credits per day (USD 0.10), reset every 24 h
- a free account key raises this tenfold (`OPENALEX_API_KEY`, sent as `api_key`); the docs say requests above 100 per second, or beyond the budget, answer HTTP 429
- singleton lookups (`works/W...`, `works/pmid:...`, `works/doi:...`, `topics/T...`) cost **0**; a `filter` list costs **1**; a `search` list costs **10**. That means roughly 100 keyless searches per day, and a `search_concepts` call (two searches) costs 20
- `per-page` is at most 100; basic paging is limited to 10,000 results
- the adapter does not see response headers, so it cannot warn before the budget is spent; a 429 is logged and the call returns `[]` / `None`

The optional `mailto` is sent **only** if the environment variable `OPENALEX_MAILTO` is set; it is never read from the config object, `.env` keys, git or anywhere else, and nothing is sent otherwise. It had no measurable effect on cost or latency in the headers. Latency is 0.3 to 1.2 s.

## Quirks learned live

- `search` matches full text as well as title and abstract, so it is broad (335,404 hits for "chronic fatigue syndrome", 2,032,658 for "long covid" as separate words). Pass an exact phrase and filters (`year`, `type`, `topic`) to focus it.
- `abstract_inverted_index` is `null` for many works (publisher restrictions; for example the Nature Reviews Microbiology Long COVID review W4316014106). It is rebuilt from `{word: [positions]}` when present (the JAMA PASC definition paper W4378212766 has one).
- Citation counts are OpenAlex's own and differ from Scopus, Web of Science and PubMed.
- `works/pmcid:...` returned 404 for a PMC id that is known to OpenAlex; PMCIDs are only available as output (`ids.pmcid`), not as a lookup form.
- Unknown ids give HTTP 404 with an HTML body; the adapter returns `None`.
- The result record is large (about 25 KB); the adapter sends `select=` to keep list responses small.

## See also

- [Europe PMC adapter](europepmc_adapter.md), [LitCovid adapter](litcovid_adapter.md)
- [All adapters](../README.md)
