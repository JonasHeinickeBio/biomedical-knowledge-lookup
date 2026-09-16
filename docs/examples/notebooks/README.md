---
description: Interactive Jupyter notebooks that walk through searching, API keys, rate limits and error handling.
---

# Notebooks

Each notebook runs top to bottom against the live public services. Cells that need an
API key print a message instead of failing when the key is not set.

| Notebook | What it covers |
| --- | --- |
| [01 Getting started](01-getting-started.ipynb) | Create a lookup, search several sources at once, narrow a search by source and concept type, look up a concept by identifier, work with results, configure `LookupConfig`, and the UMLS-specific adapter features. |
| [02 API keys](02-api-keys.ipynb) | Which sources need a key, how keys are resolved (`api_keys` or `<SERVICE>_API_KEY` and `.env`), checking which key-gated sources are usable, and keeping keys out of notebooks and logs. |
| [03 Rate limits, retries and timeouts](03-rate-limiting.ipynb) | The built-in retry strategies, per-source pacing with `rate_limits`, bounded concurrency for batches, `timeout_per_source`, and caching repeated queries with `KnowledgeLookupCache`. |
| [04 Error handling](04-error-handling.ipynb) | Where failures show up (`lookup.adapters`, `result.errors`, `result.sources_failed`, `None` details, logs), retry-then-fallback, source health and circuit breakers, and the errors that do raise. |

## Run the notebooks

The notebooks need Python 3.11 or newer.

{% tabs %}
{% tab title="pip" %}
```bash
pip install "biomedical-knowledge-lookup[all]" jupyterlab
jupyter lab docs/examples/notebooks
```
{% endtab %}

{% tab title="From a clone" %}
```bash
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
pip install -e ".[all]" jupyterlab
jupyter lab docs/examples/notebooks
```
{% endtab %}
{% endtabs %}

The `[all]` extra installs every optional dependency. Without it, the notebooks still run,
but ChEMBL, UMLS and the `bioservices`-based sources are reported as unavailable.

{% hint style="info" %}
The library is asynchronous. Jupyter runs `await` at the top level of a cell, which is
what the notebooks use. In a script, put the calls in an `async def main()` and run it
with `asyncio.run(main())`, as the [per-source examples](../README.md) do.
{% endhint %}

## See also

- [Per-source examples](../README.md): one runnable script for each of the 36 sources.
- [Use cases](../use-cases.md): complete tasks built from several sources.
- [Availability status](../availability-status.md): which sources returned data in the last run.
