---
description: Fixes for the problems people hit most - unavailable sources, empty results, slow or failing calls, rate limits and notebook errors.
---

# Troubleshooting and FAQ

Start with the two commands that answer most questions:

```bash
knowledge-lookup sources            # which sources are available here, and what the others need
knowledge-lookup check HGNC         # live smoke test of one source: search -> details -> relationships
```

`check` names the environment variable to set when a source is skipped, and shows timing for each step, so you can tell "my network" from "their server".

## A source is missing or reported unavailable

| What you see | Cause | Fix |
|---|---|---|
| `<SOURCE> adapter not available` in the log | a key, extra, file or opt-in is missing | `knowledge-lookup check <SOURCE>` prints what to set |
| `BIOPORTAL`, `UMLS`, `DISGENET`, `OMIM` unavailable | no API key | set `<SERVICE>_API_KEY`; see [Configuration](configuration.md) |
| `ICD11`, `LOINC` unavailable | these need a free account | set `ICD11_CLIENT_ID`/`ICD11_CLIENT_SECRET` or `LOINC_USERNAME`/`LOINC_PASSWORD` |
| `ICD10GM`, `CELLMARKER`, `SEMMEDDB` unavailable | they read a file you provide | set `ICD10GM_CLAML_PATH`, `CELLMARKER_PATH` or `SEMMEDDB_PATH` |
| `HPOA`, `SIDER`, `OFFSIDES`, `CTD`, `CLINGEN`, `GENCC` unavailable | dataset downloads are opt-in | set `<NAME>_DOWNLOAD=1`, or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1` for all of them |
| `UNPAYWALL` returns nothing | it needs a contact e-mail and only resolves DOIs | set `UNPAYWALL_EMAIL`; pass a DOI, not a title (title search was retired upstream) |
| `ChEMBLAdapter is None`, `UniChem`/`QuickGO`/`EUTILS` unavailable | optional extra not installed | `pip install "biomedical-knowledge-lookup[chembl,bioservices]"` |

{% hint style="info" %}
Nothing is downloaded behind your back. A dataset-backed source stays unavailable until you opt in, so a fresh install never pulls hundreds of megabytes.
{% endhint %}

## My `.env` file is ignored

The library looks for `.env` **upward from the installed package**, not from your script's working directory. That works in a source checkout and in Jupyter. For an installed package, export the variables in your shell or call `dotenv.load_dotenv()` yourself before creating `CentralKnowledgeLookup`.

## Searches return nothing, or the wrong thing

* **Check the query shape.** Some sources only understand names (`aspirin`), some only identifiers (`UniChem` takes an InChIKey, `Unpaywall` a DOI), some only exact ontology labels. The adapter page lists what it accepts.
* **The first hit is not always the canonical entity.** Search is lexical: "aspirin" can return *aspirin trelamine* first, and "BRCA1" can return a plant protein from UniProt. Look at several hits, or fetch by exact identifier with `get_concept_details`.
* **The disease may not be in that source.** ME/CFS is not in `phenotype.hpoa`; use Monarch, MedGen or the GWAS Catalog. See [Which source for which question](../guides/choosing-sources.md).
* **Zero relationships is normal for lookup services.** HGNC, UniProt, PubChem and Wikidata return a record but no edges. See [What each source returns](../guides/data-coverage.md).

## Calls are slow or time out

| Symptom | Explanation |
|---|---|
| First call to a dataset-backed source takes many seconds | it loads the file once (OFFSIDES took about 38 s in testing); later calls are fast |
| Rhea relationships take close to a minute | the SPARQL endpoint is slow; raise `timeout_per_source` |
| `get_concept_details` without `source=` is slow | it asks every enabled adapter; pass `source=` |
| `CentralKnowledgeLookup()` starts slowly | it creates every adapter; pass `LookupConfig(enabled_sources=[...])` |
| NCBI E-utilities hang for about 100 s, then fail | Python `requests` waits on an unreachable IPv6 route on some networks. Test with `curl -4`. Disable IPv6 for the process: `import urllib3.util.connection as c; c.HAS_IPV6 = False` before the first call, or fix the route |
| ChEMBL fails with HTTP 500 | the upstream API is down while the client loads its schema; retry later |
| SNOMED CT times out | the public Snowstorm host is unreachable; run your own and set `SNOMED_SNOWSTORM_URL` |

`knowledge-lookup check <SOURCE>` separates a slow server from a library problem: it prints the time of each step.

## HTTP 429 and rate limits

* Without a key, [Semantic Scholar](../adapters/literature/semanticscholar_adapter.md) rate-limits search heavily. A free key fixes it.
* [openFDA](../adapters/chemicals/openfdalabels_adapter.md) allows about 1,000 keyless requests per day.
* Lower the request rate with `LookupConfig(rate_limits={KnowledgeSource.X: 0.5})`. See [Configuration](configuration.md) and [Rate limits, retries and circuit breakers](../adapters/README.md#rate-limits-retries-and-circuit-breakers).

A source that keeps failing is skipped for a while when `enable_source_health_tracking=True`: the circuit breaker opens after 5 failures and probes again after 30 s.

## Errors in scripts and notebooks

| Error | Fix |
|---|---|
| `asyncio.run() cannot be called from a running event loop` (Jupyter, IPython) | use `await lookup.search_concepts(...)` directly in a cell |
| `Unclosed client session` warning | call `await lookup.close()` in a `finally` block, or use an adapter as `async with` |
| `ValidationError: Extra inputs are not permitted` on `LookupConfig` | the field name is wrong; see [Configuration](configuration.md) |
| `UnicodeDecodeError` on Windows when reading exports | pass `encoding="utf-8"`; the Windows default is cp1252 |
| `ModuleNotFoundError: knowledge_lookup` | the package is in a different environment; check `python -m pip show biomedical-knowledge-lookup` |

## Privacy and data

**Does the library send my queries to third parties?** Yes: each query goes to the public API of every source you enable, as it would from a browser. Enrichr additionally **stores** the gene list you send. Use local sources (the dataset-backed and file-backed ones) for sensitive work.

**Does it send my e-mail or name?** Only if you set a variable such as `UNPAYWALL_EMAIL` or an OpenAlex mailto, and only to that service.

**Is anything cached?** Almost nothing: most adapters call the upstream API every time (UniChem, the MCP server and the UMLS helpers keep small caches). See [Caching](../guides/caching.md). The exception is the opt-in datasets, which are stored locally once you download them.

## Still stuck?

Run the check with `--timeout 120` and open an [issue](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/issues) with its output, your Python version and `pip show biomedical-knowledge-lookup`.
