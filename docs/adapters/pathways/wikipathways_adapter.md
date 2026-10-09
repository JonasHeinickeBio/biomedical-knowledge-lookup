---
description: WikiPathways community-curated pathways, searched client-side from the site's bulk JSON files (no key).
---

# WikiPathways adapter

Searches [WikiPathways](https://www.wikipathways.org/), the community-curated pathway collection, and returns pathways with species, description and, for human pathways, their member genes as relationships.

| | |
|---|---|
| Source | `KnowledgeSource.WIKIPATHWAYS` |
| Class | `knowledge_lookup.adapters.WikiPathwaysAdapter` |
| Requires | none |
| Identifiers | `WP254` or `WIKIPATHWAYS:WP254` |
| Upstream API | `https://www.wikipathways.org/json/` (bulk files) |

{% hint style="warning" %}
WikiPathways retired its per-query web service. There is **no live search or per-pathway endpoint any more**, only three bulk JSON files. The adapter downloads the file it needs on first use, indexes it in memory and answers every later call from that index.
{% endhint %}

## Quick example

```python
import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import WikiPathwaysAdapter


async def main() -> None:
    async with WikiPathwaysAdapter(LookupConfig()) as wp:
        for hit in await wp.search_concepts("interleukin", limit=3):
            print(hit.primary_id, hit.primary_label, hit.categories)
        pathway = await wp.get_concept_details("WP254")
        print(pathway.primary_label, pathway.definitions[0][:80])
        for edge in await wp.get_relationships("WP254", limit=3):
            print(edge["relation_label"], edge["related_id"])


asyncio.run(main())
```

```
WP2637 Interleukin-1 (IL-1) structural pathway ['Homo sapiens']
WP3159 Interleukin-11 signaling pathway ['Bos taurus']
WP3178 Interleukin-1 (IL-1) structural pathway ['Bos taurus']
Apoptosis Apoptosis is a distinct form of cell death that is functionally and morphologica
has_gene MIR29B1
has_gene MIR29A
has_gene PMAIP1
```

## Methods

| Method | What it does |
|---|---|
| `search_concepts(query, limit=20)` | case-insensitive substring match against, in rank order, the pathway name, annotations, participating gene and metabolite names, and description. Name matches rank above description matches |
| `get_concept_details(id)` | one pathway from the `getPathwayInfo` index: name, species, description (first 500 characters), revision, authors, citations, link |
| `get_relationships(id, limit=10)` | `has_gene` edges to HGNC symbols (`related_id` is the symbol). Non-human pathways and pathways without HGNC annotations return `[]` |
| `get_mappings(id)` | not provided (`[]`) |

Search is a plain substring scan, not a full-text index: "fatigue" matches nothing because no pathway mentions it, while "mitochondrial" and "interleukin" do. Searching by gene symbol (`BRCA1`) finds pathways listing that gene as a data node.

## What comes back

| Field | Content |
|---|---|
| `primary_id` / `primary_label` | `WP254`, `Apoptosis` |
| `concept_type` | `PATHWAY` |
| `categories` | the species, for example `Homo sapiens` or `Bos taurus`. **The same pathway often exists once per species**, so filter on `categories` |
| `definitions` | the curator's description |
| `source_data` | the raw bulk entry: `id`, `url`, `name`, `species`, `revision`, `authors`, `description`, `citedIn` |

## Cost, rate limits and licence

* Three bulk files, all served over HTTP/2 without a key: `findPathwaysByText` 2.3 MB (search), `getPathwayInfo` 1.2 MB (details), `findPathwaysByXref` 12 MB (relationships). Measured downloads took 0.2 to 0.6 s.
* The first search or details call pays one download; later calls take milliseconds. `get_relationships` downloads the 12 MB file once, which took about 3.6 s on the first call in testing.
* Parsed files are kept for 6 hours through the adapter cache.
* WikiPathways publishes its content under CC0 (stated on its About page).

## Live verification (2026-10-09)

| Call | Result |
|---|---|
| `search_concepts("BRCA1")` | 5 hits in 0.9 s, first `WP1014` Androgen receptor signaling pathway |
| `search_concepts("interleukin")` | 5 hits in 10 ms after the first download |
| `get_concept_details("WP254")` | `Apoptosis`, species `Homo sapiens` |
| `get_relationships("WP254")` | 10 `has_gene` edges |
| `get_relationships("WP1263")` | 0 edges: this pathway carries no HGNC symbols in the bulk index |
