---
description: Configure LookupConfig, provide API keys, and tune timeouts, rate limits, retries and circuit breakers.
---

# Configuration

All runtime behaviour of `CentralKnowledgeLookup` is controlled by a `LookupConfig` object plus a handful of environment variables for API keys. Caching is configured separately; see [Caching](../guides/caching.md).

## A typical configuration

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

config = LookupConfig(
    enabled_sources=[KnowledgeSource.HPO, KnowledgeSource.MONDO, KnowledgeSource.BIOPORTAL],
    timeout_per_source=15,
    rate_limits={KnowledgeSource.HPO: 5.0, KnowledgeSource.MONDO: 5.0},
    api_keys={"bioportal": "your-bioportal-key"},
    enable_source_health_tracking=True,
)


async def main() -> None:
    lookup = CentralKnowledgeLookup(config)
    try:
        print([source.value for source in lookup.get_available_sources()])
    finally:
        await lookup.close()


asyncio.run(main())
```

## `LookupConfig` fields

| Field | Type | Default | Effect |
| --- | --- | --- | --- |
| `enabled_sources` | `list[KnowledgeSource]` or `None` | `None` | Adapters to initialise. `None` means all of them. |
| `timeout_per_source` | `float` | `30` | Seconds allowed per source for each search and detail lookup; also the total timeout of each adapter's HTTP session. |
| `rate_limits` | `dict` | `{}` | Requests per second per source. See [Rate limits](#rate-limits). |
| `api_keys` | `dict[str, str]` | `{}` | API keys by service name; overrides environment variables. See [API keys](#api-keys). |
| `enable_deduplication` | `bool` | `True` | Merge search results that share a normalized label. |
| `enable_source_health_tracking` | `bool` or `None` | `None` (off) | Attach a circuit breaker to every adapter and report `result.source_health`. |
| `circuit_breaker_threshold` | `int` or `None` | `None` (5) | Consecutive failures before a source's breaker opens. |
| `circuit_breaker_cooldown` | `float` or `None` | `None` (30.0) | Seconds before an open breaker allows a probe request. |
| `enable_ontology_mapping` | `bool` or `None` | `None` | ChEMBL adapter only: map compound categories to ontology terms. |

The following fields are accepted for schema compatibility but are **not applied** by `CentralKnowledgeLookup` today:

| Field | Default | Use instead |
| --- | --- | --- |
| `max_results_per_source` | `20` | The `max_results` argument of `search_concepts()` |
| `parallel_queries` | `True` | The `parallel` argument of `search_concepts()` |
| `concept_types` | `None` | The `concept_types` argument of `search_concepts()` |
| `min_confidence_threshold`, `similarity_threshold`, `merge_similar_concepts`, `preferred_languages` | `None` | Filter `result.concepts` yourself |

{% hint style="warning" %}
`LookupConfig` rejects unknown fields. Options that appear in older examples, such as `cache_enabled`, `cache_ttl`, `cache_dir`, `global_timeout`, `max_retries` or `retry_on_failure`, raise a pydantic `ValidationError`.
{% endhint %}

Helpers on the model:

* `LookupConfig.with_all_sources()`: a config with every `KnowledgeSource` enabled
* `config.is_source_enabled(source)`: `True` if the source is enabled (or no filter is set)
* `config.get_api_key(service)`: resolve a key as described below

`create_knowledge_lookup(api_keys=None, enabled_sources=None, **config_fields)` is a shortcut that builds the config and the lookup in one call. Its `fast_mode` parameter is accepted but has no effect.

## API keys

Most sources are open. These need a key:

| Environment variable | `api_keys` name | Used by | Without it |
| --- | --- | --- | --- |
| `BIOPORTAL_API_KEY` | `bioportal` | BioPortal, BioOntology | Adapters unavailable |
| `UMLS_API_KEY` | `umls` | UMLS (also needs the `umls` extra), UMLS abbreviation discovery | Adapter unavailable; expansion falls back to synonyms only |
| `DISGENET_API_KEY` | `disgenet` | DisGeNET | Adapter unavailable |
| `OMIM_API_KEY` | `omim` | OMIM | Adapter unavailable |
| `COSMIC_API_KEY` | `cosmic` | COSMIC | Adapter still works with public endpoints |

Get keys from [BioPortal](https://bioportal.bioontology.org/account), the [UMLS Terminology Services](https://uts.nlm.nih.gov/uts/signup-login) (requires a UMLS license), [DisGeNET](https://www.disgenet.com/) and [OMIM](https://www.omim.org/api).

The EUtils adapter sends a contact e-mail with each request. Set it with `api_keys={"ncbi_email": "you@example.org"}`; it defaults to `anonymous@example.com`.

### How keys are resolved

`config.get_api_key("bioportal")` checks, in order:

1. `api_keys={"bioportal": "..."}` passed to `LookupConfig`
2. The environment variable `BIOPORTAL_API_KEY` (or lowercase `bioportal_api_key`), after loading a `.env` file with python-dotenv

```bash
export BIOPORTAL_API_KEY="..."
export UMLS_API_KEY="..."
```

{% hint style="warning" %}
The library calls `load_dotenv()` without a path. From a script, python-dotenv then searches for `.env` starting in the directory where `knowledge_lookup` is installed and walking up the tree, not in your working directory (a REPL or Jupyter kernel uses the working directory). A `.env` in your project root is found for a source checkout or a virtual environment inside the project, but not for a global install. To be explicit, load it yourself before creating the lookup:

```python
from dotenv import load_dotenv

load_dotenv()  # searches from your script's directory; variables already set are kept
```
{% endhint %}

To see which sources started, call `lookup.get_available_sources()` or run `knowledge-lookup info`.

## Timeouts

* `timeout_per_source` bounds each source's search, whether sources are queried in parallel (the default) or one after another with `search_concepts(..., parallel=False)`, and each `get_concept_details()` call. `get_concept_details()` also accepts a `timeout=` override.
* A source that times out appears in `result.errors` as `Timed out after <n>s`; the other results are kept.
* There is no global timeout for a whole search. With `parallel=False` a search can take up to `timeout_per_source` times the number of sources; wrap the call in `asyncio.wait_for()` if you need a limit.

## Rate limits

Before each adapter search, `search_concepts()` waits `1 / rate` seconds, where `rate` comes from `rate_limits` and defaults to **1 request per second** for every source. This is a fixed delay per call, not a token bucket.

```python
from knowledge_lookup import KnowledgeSource, LookupConfig

config = LookupConfig(
    rate_limits={
        KnowledgeSource.OLS: 10.0,  # wait 0.1 s before each OLS search
        "HPO": 5.0,                 # string source names work as keys too
        KnowledgeSource.UMLS: 0,    # 0 disables the delay
    }
)
```

## Retries

HTTP-based adapters retry failed requests automatically, choosing a strategy by error category:

| Error category | Attempts | Delay between attempts |
| --- | --- | --- |
| Network error (connection, DNS, timeout, SSL) | 3 | none |
| Rate limited (HTTP 429 or quota 403) | 4 | 2 s, 4 s, 8 s (capped at 60 s) |
| Server error (HTTP 5xx) | 4 | 1.5 s, 3 s, 6 s (capped at 30 s) |
| Transient | 2 | none |
| Not found (HTTP 404) | 1 | not retried; counts as an answer for the circuit breaker |
| Client error (other HTTP 4xx) | 1 | not retried |
| Unknown | 2 | 1 s |

Adapters built on third-party clients (ChEMBL, EUtils, QuickGO, UniChem, Tyto, UMLS) rely on the retry behaviour of those libraries instead.

## Circuit breakers

With `enable_source_health_tracking=True`, each source gets a circuit breaker. After `circuit_breaker_threshold` consecutive failures (default 5) the breaker opens: `search_concepts()` skips the source without calling it and records `Circuit breaker open (...)` in `result.errors`, and HTTP-based adapters reject other requests, such as `get_concept_details()`, immediately. `get_concept_details()` skips an open source too. After `circuit_breaker_cooldown` seconds (default 30) the next request is let through as a probe; success closes the breaker again, failure re-opens it. A failure is a request that still fails once its retries are exhausted, or a search or detail lookup cut off by `timeout_per_source`. An HTTP 404 counts as an answer, not a failure, because several APIs use it for "no match". See [Searching concepts](../guides/searching-concepts.md) for reading `result.source_health`.

## Other configuration

* **LLM backends** for the agent workflow: `BLABLADOR_*`, `OPENAI_*` and `ANTHROPIC_*` variables; see [Agent workflow](../guides/agent-workflow.md).
* **MCP server** settings: `KNOWLEDGE_LOOKUP_MCP_*` variables and flags; see [MCP server](../guides/mcp-server.md).
* **Logging** uses the standard `logging` module under the `knowledge_lookup` logger. Adapter initialisation logs at `INFO`, unavailable sources at `WARNING`.

## Next steps

* [Searching concepts](../guides/searching-concepts.md)
* [Caching](../guides/caching.md)
* [Knowledge source adapters](../adapters/README.md): per-source requirements and limits
