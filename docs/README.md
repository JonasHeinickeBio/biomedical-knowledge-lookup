---
description: One async Python API for searching, resolving and cross-walking concepts across 36 biomedical ontologies and databases.
---

# Biomedical Knowledge Lookup

**Biomedical Knowledge Lookup** (`biomedical-knowledge-lookup` on PyPI, imported as `knowledge_lookup`) gives you one asynchronous interface to biomedical terminologies and databases: OLS, MONDO, HPO, UMLS, BioPortal, UniProt, ChEMBL, Reactome and 28 more. Every source returns the same `UnifiedConcept` model, so you can query several sources at once, merge the hits and export them without writing per-source code.

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig


async def main() -> None:
    lookup = CentralKnowledgeLookup(
        LookupConfig(enabled_sources=[KnowledgeSource.MONDO, KnowledgeSource.HPO])
    )
    try:
        result = await lookup.search_concepts("type 2 diabetes", max_results=6)
        for concept in result.concepts:
            print(concept.primary_id, concept.primary_label, concept.sources)
    finally:
        await lookup.close()


asyncio.run(main())
```

## What you can do

| Task | Guide |
| --- | --- |
| Search many sources in parallel and get merged, de-duplicated, ranked results | [Searching concepts](guides/searching-concepts.md) |
| Resolve an identifier such as `HP:0001250` and map it to other vocabularies | [Searching concepts](guides/searching-concepts.md) |
| Widen a search with synonyms and abbreviation/long-form variants, with a durable record of every term tried | [Term expansion](guides/term-expansion.md) |
| Compare what several sources return for the same text and score their agreement | [Multi-source annotation](guides/multi-source-annotation.md) |
| Parse, validate and normalize CURIEs with Bioregistry | [CURIE management](guides/curie-management.md) |
| Export results to JSON, CSV, Turtle, pandas, Excel, a text report or an RDF graph | [Exporting results](guides/exporting-results.md) |
| Query from the terminal | [Command-line interface](guides/cli.md) |
| Run a LangGraph search, review and approval workflow | [Agent workflow](guides/agent-workflow.md) |
| Give LLM agents (Claude, Cursor, VS Code, ...) lookup tools over the Model Context Protocol | [MCP server](guides/mcp-server.md) |

## Design at a glance

* **Async first.** All lookups are coroutines; sources are queried concurrently with a per-source timeout.
* **Partial failure is expected.** A source that errors or times out is reported in `result.errors`; results from the other sources are still returned.
* **Light core install.** Heavy clients (ChEMBL, UMLS, bioservices, LangGraph, MCP, pandas) are optional extras. An adapter whose extra or API key is missing is skipped, not fatal.
* **One data model.** Pydantic models generated from a LinkML schema: `UnifiedConcept`, `LookupResult`, `LookupConfig`, `KnowledgeSource`, `ConceptType`.

## Documentation map

**Getting started**

* [Installation](getting-started/installation.md): requirements, extras, verifying the install
* [Quickstart](getting-started/quickstart.md): search, resolve, map and export in one script
* [Configuration](getting-started/configuration.md): `LookupConfig`, API keys, timeouts, rate limits

**Guides**

* [Searching concepts](guides/searching-concepts.md)
* [Term expansion](guides/term-expansion.md)
* [Multi-source annotation](guides/multi-source-annotation.md)
* [CURIE management](guides/curie-management.md)
* [Caching](guides/caching.md)
* [Exporting results](guides/exporting-results.md)
* [Command-line interface](guides/cli.md)
* [Agent workflow](guides/agent-workflow.md)
* [MCP server](guides/mcp-server.md)

**Reference**

* [API reference](reference/api-reference.md)
* [Architecture](reference/architecture.md)
* [Knowledge source adapters](adapters/README.md): one page per source
* [Examples](examples/README.md): scripts, notebooks and use cases

**Project**

* [Contributing](contributing/README.md)

## Project links

* Source code: [github.com/JonasHeinickeBio/biomedical-knowledge-lookup](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup)
* Package: [pypi.org/project/biomedical-knowledge-lookup](https://pypi.org/project/biomedical-knowledge-lookup/)
* Changelog: [CHANGELOG.md](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/CHANGELOG.md)
* Issues: [GitHub issues](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/issues)
* License: MIT
