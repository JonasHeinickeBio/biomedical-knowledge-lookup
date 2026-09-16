---
description: How the package is organised, how a search flows through the orchestrator and adapters, and where resilience, models and front-ends fit in.
---

# Architecture

Biomedical Knowledge Lookup is a layered library: front-ends call an orchestrator, the orchestrator fans requests out to per-source adapters, and every adapter converts its source's response into the shared data model.

## Layers

```
 Front-ends      Python API   knowledge-lookup CLI   agents (LangGraph)   knowledge-lookup-mcp
                      \                 |                    |                 /
 Orchestration        CentralKnowledgeLookup   MultiSourceAnnotator   term expansion
                      parallel search, timeouts, de-duplication, ranking, source health
                                               |
 Adapters             36 KnowledgeSourceAdapter subclasses, registered in ADAPTER_CLASSES
                      HTTP helpers with retry and circuit breaker | third-party client wrappers
                                               |
 External APIs        OLS, MONDO, HPO, UMLS, BioPortal, UniProt, ChEMBL, OxO, Reactome, ...

 Cross-cutting        models (LinkML -> pydantic) | cache | curie_utils | ExpansionStore | RDF services
```

## Package layout

| Path (under `src/knowledge_lookup/`) | Responsibility |
| --- | --- |
| `__init__.py` | Public exports |
| `__main__.py` | Typer CLI (`knowledge-lookup`) |
| `base.py` | `KnowledgeSourceAdapter` base class: HTTP session, retry, circuit breaker, cache helpers |
| `adapters/` | One module per source, plus the `ADAPTER_CLASSES` registry in `adapters/__init__.py` |
| `core/central_lookup.py` | `CentralKnowledgeLookup` and `SourceHealthTracker` |
| `core/multi_source_annotator.py` | `MultiSourceAnnotator` and its result dataclasses |
| `core/term_expansion.py`, `core/expansion_store.py` | Iterative synonym/abbreviation expansion and its SQLite store |
| `core/factory.py` | `create_knowledge_lookup()` |
| `models/biomedical_knowledge_models.py` | Pydantic models generated from `linkml/biomedical_knowledge_schema.yaml` |
| `models/extensions.py` | Wrappers that add defaults and helper methods to the generated models |
| `cache/` | Memory and disk TTL cache |
| `curie_utils/` | Bioregistry-based CURIE parsing, validation and normalization |
| `services/` | `UnifiedRDFConverter`, `OntologyConceptLoader` |
| `export/` | Module-level JSON and CSV export |
| `utils/retry_utils.py` | `CircuitBreaker`, error classification |
| `agents/` | LangGraph workflow (`graph.py`, `nodes/`, `runners.py`, `state.py`) |
| `mcp_server/` | MCP server (`server.py`, source catalog and routing in `sources.py`, thread isolation in `isolation.py`) |
| `umls/` | UMLS cache, batch processing, LLM normalization, embeddings, RDF helpers |
| `benchmarks/` | Benchmarks behind `knowledge-lookup benchmark` |

## Start-up

When `CentralKnowledgeLookup(config)` is created it:

1. creates the global cache with `init_cache()` defaults, unless one was configured beforehand,
2. for every entry in `ADAPTER_CLASSES` whose source is enabled, instantiates the adapter with the config and keeps it only if `is_available()` returns `True` (API key present, client library importable). Adapters that raise during construction are logged and skipped,
3. attaches a circuit breaker to each adapter when `enable_source_health_tracking` is on,
4. computes a source-to-CURIE-prefix map with Bioregistry (empty without the `curie` extra).

ChEMBL and UMLS are added to `ADAPTER_CLASSES` only when their client libraries import successfully.

## A search, step by step

`search_concepts(query, concept_types, sources, max_results, parallel)`:

1. **Select sources**: the requested sources that have an initialised adapter (all of them when `sources` is `None`).
2. **Split the limit**: each source is asked for `max(1, max_results // number_of_sources)` concepts.
3. **Fan out**: one task per source (run concurrently, or one after another with `parallel=False`). A source whose circuit breaker is open is skipped and recorded as an error. Otherwise the task waits `1 / rate_limit` seconds, then calls `adapter.search_concepts(query, limit)`, bounded by `timeout_per_source`. A search cut off by that timeout counts as a failure on the source's breaker.
4. **Collect**: successful sources add their concepts (and are listed in `sources_succeeded`); exceptions and timeouts become entries in `errors` and `sources_failed`.
5. **Filter** by `concept_types`, keeping `UNKNOWN` concepts.
6. **De-duplicate** by normalized label with `UnifiedConcept.merge_with()`.
7. **Rank** by `confidence_score` and truncate to `max_results`.
8. **Annotate** the result with `execution_time` and, if enabled, a `source_health` snapshot.

`get_concept_details()` skips sources whose breaker is open and records timeouts in the same way; without a source it runs the other adapters concurrently and returns the first non-`None` answer in registry order. `find_mappings()` combines the concept's identifiers with EBI OxO cross-references.

## Adapters

Every adapter subclasses `KnowledgeSourceAdapter` and implements `get_source()`, `search_concepts(query, limit)` and `get_concept_details(concept_id)`. There are two kinds:

* **HTTP adapters** call REST or GraphQL APIs through `_make_request()`, which runs inside `_call_with_retry()`. Errors are classified (network, rate limited, server, client, transient, unknown) and retried with a per-category strategy; the attempts and delays are listed in [Configuration](../getting-started/configuration.md). The circuit breaker is checked before every attempt and updated after it.
* **Client-library adapters** (ChEMBL, EUtils, QuickGO, UniChem, Tyto, UMLS) wrap synchronous or third-party clients, usually through `asyncio.to_thread`, and rely on the library's own retries.

Each adapter maps its source's payload to `UnifiedConcept`, keeping the raw data in `source_data`. Per-adapter behaviour, identifier formats and limits are documented in [Knowledge source adapters](../adapters/README.md).

### Circuit breakers

`SourceHealthTracker` keeps one `CircuitBreaker` per source. A breaker is **closed** normally, **opens** after `circuit_breaker_threshold` consecutive failures (searches and `get_concept_details()` then skip the source, and adapters reject requests with `CircuitBreakerOpen`), and becomes **half-open** after `circuit_breaker_cooldown` seconds, allowing one probe that either closes or re-opens it. Failures are recorded by `_call_with_retry()` once retries are exhausted, and by `CentralKnowledgeLookup` when `timeout_per_source` cuts a call off. An HTTP 404 is recorded as a success: the service answered, and several APIs use 404 for "no match".

## Data model

The models are defined once in a [LinkML](https://linkml.io/) schema (`linkml/biomedical_knowledge_schema.yaml`) and generated into pydantic v2 classes with `extra="forbid"` and `use_enum_values=True`. `models/extensions.py` wraps the generated `UnifiedConcept`, `LookupResult`, `LookupConfig`, `ConceptIdentifier` and `ConceptMapping` to:

* default list fields to `[]` and scores to `0.0`,
* keep dictionary-valued data (`errors`, `source_health`, `api_keys`, `source_data`, `labels`) that the generated schema types as strings,
* add helper methods such as `add_concepts()`, `get_best_matches()`, `merge_with()` and `get_api_key()`.

`knowledge_lookup.models` exports the wrappers, which is what the rest of the library uses.

## Supporting components

* **Cache** (`cache/`): a global two-tier TTL cache. See [Caching](../guides/caching.md) for which components use it.
* **Term expansion** (`core/term_expansion.py`): repeated searches that harvest synonyms and UMLS abbreviation/long-form pairs; every run is recorded in the SQLite `ExpansionStore`. See [Term expansion](../guides/term-expansion.md).
* **CURIE utilities** (`curie_utils/`): Bioregistry and curies wrappers. See [CURIE management](../guides/curie-management.md).
* **RDF** (`services/rdf_converter.py`): type-aware conversion of concepts to `rdflib` graphs. See [Exporting results](../guides/exporting-results.md).

## Front-ends

* **CLI** (`__main__.py`): Typer commands that create a `CentralKnowledgeLookup` per invocation. See [Command-line interface](../guides/cli.md).
* **Agent workflow** (`agents/`): a LangGraph `StateGraph` (preprocess, expand, lookup, filter, quality gate, detail gathering, UMLS enrichment, aggregation, review, approval, refine, prune, export) with an in-memory checkpointer. See [Agent workflow](../guides/agent-workflow.md).
* **MCP server** (`mcp_server/`): an `MCPServer` that initialises the lookup in a worker thread, routes identifiers to the adapter that owns them, runs blocking adapters on their own event-loop threads and caches search pages. See [MCP server](../guides/mcp-server.md).

## Adding a knowledge source

1. Create `src/knowledge_lookup/adapters/<name>_adapter.py` with a `KnowledgeSourceAdapter` subclass. Implement `get_source()`, `search_concepts()` and `get_concept_details()`, and override `is_available()` if the source needs a key or an optional client.
2. Add the source to the `KnowledgeSource` enum in `linkml/biomedical_knowledge_schema.yaml` and regenerate the models (see `linkml/Makefile`).
3. Register the class in `ADAPTER_CLASSES` in `adapters/__init__.py`.
4. Add the source to `SOURCE_CATALOG` and `SourceName` in `mcp_server/sources.py`; the MCP tests check that both cover every adapter.
5. Add unit tests with mocked responses and a documentation page under `docs/adapters/<category>/`.

See [Contributing](../contributing/README.md) for the development workflow.
