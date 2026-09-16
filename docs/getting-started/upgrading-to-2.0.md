---
description: Breaking changes in biomedical-knowledge-lookup 2.0 and how to update code written for 1.x.
---

# Upgrading to 2.0

Version 2.0 raises the minimum Python version, removes legacy modules, and fixes a large number of adapters and core behaviours. Most code that only calls `search_concepts()` and `get_concept_details()` keeps working unchanged. Read the checklist first, then the sections that apply to you. The full list of changes is in the [changelog](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/CHANGELOG.md).

## Checklist

| If you… | Then… |
| --- | --- |
| run Python 3.10 | upgrade to Python 3.11 or newer |
| import `knowledge_lookup.validation_models`, `knowledge_lookup.generated_models`, `knowledge_lookup.adapters.additional_adapters`, `knowledge_lookup.examples` or `knowledge_lookup.cache.cache_demo` | switch to the replacements under [Removed modules](#removed-modules) |
| call `ChEMBLAdapter.lookup_molecule()`, `lookup_drug()` or `lookup_target()` | add `await` |
| pass one plain string as `LookupConfig.api_keys` | pass a dict per service, or set `{SERVICE}_API_KEY` environment variables |
| call `BioPortalAdapter.get_concept_details()` with a short ID | pass the class IRI, or the `ontology=` acronym |
| read `get_statistics()`, `source_health` or `result.errors` | expect upper-case circuit states and skipped sources listed as errors |
| use the agent workflow's pause/resume | handle the `awaiting_approval` status |
| export to Excel | install the `export` extra; it now includes `openpyxl` |
| relied on `requests`, `tenacity` or `pyobo` being installed by this package | install them yourself |

## Python and dependencies

Python **3.11** is the minimum; CI tests 3.11, 3.12 and 3.13. Every dependency moved to its newest release, including pandas 3 in the `export` extra.

These packages are no longer installed, because the library never imported them:

* `requests` (core)
* `tenacity` (1.x pinned it below 9, which blocked other packages)
* `pyobo` (`curie` extra; CURIE handling uses `bioregistry` and `curies`)

If your own code imports one of them, add it to your project's dependencies.

The `export` extra now installs `openpyxl`, so `export_to_excel()` works without installing it separately:

```bash
pip install --upgrade "biomedical-knowledge-lookup[export]"
```

## Removed modules

These modules were duplicates of maintained code, or demos shipped inside the package. They are gone in 2.0.

| Removed | Use instead |
| --- | --- |
| `knowledge_lookup.validation_models` | `knowledge_lookup.models` (for example `from knowledge_lookup.models import ConceptAgreement, convert_generated_unified_concept`) |
| `knowledge_lookup.generated_models` | `knowledge_lookup.models`, which holds the models generated from the LinkML schema |
| `knowledge_lookup.adapters.additional_adapters` (`DBpediaAdapter`, `OxOAdapter`, `BioOntologyAdapter`) | the adapters exported by `knowledge_lookup.adapters` |
| `knowledge_lookup.examples` | the runnable scripts in [`docs/examples/`](../examples/README.md) |
| `knowledge_lookup.cache.cache_demo` | the [caching guide](../guides/caching.md) |

`knowledge_lookup.examples` also loaded `.env` and changed `sys.path` as soon as it was imported. Nothing in the package does that any more; load your `.env` in your own entry point if you need it.

## API keys

* **One string no longer serves every service.** In 1.x, a plain string in `LookupConfig.api_keys` was returned for *every* service, so one provider's key was sent to all the others. Now only a dict, or a JSON object string, is read per service. Anything else falls through to the `{SERVICE}_API_KEY` environment variables.

  ```python
  LookupConfig(api_keys={"bioportal": "...", "umls": "..."})
  ```

* **BioPortal and BioOntology send the key in a header.** Requests use `Authorization: apikey token=<key>` instead of an `apikey` query parameter, so keys no longer appear in URLs or logs. `use_auth_header` on the BioOntology adapter is accepted but has no effect. OMIM still needs the key in the URL; its log messages are redacted.
* **UMLS** also reads `UMLS_API_KEY_TU` when `UMLS_API_KEY` is not set.

`knowledge_lookup.utils.redaction.redact()` is available if you log URLs or exceptions yourself.

## Circuit breakers, timeouts and health

* **Open breakers now skip sources.** In 1.x the breaker state was tracked but never consulted. A source whose breaker is open is now not called; it appears in `result.errors` with a `Circuit breaker open` message and in `sources_failed`.
* **Circuit states are upper-case strings.** `SourceHealth.circuit_state` and `get_statistics()["source_health"][...]["state"]` are `"CLOSED"`, `"OPEN"` or `"HALF_OPEN"`. A breaker whose cooldown has passed is reported as `HALF_OPEN`, and `open_sources()` leaves it out. `get_statistics()` crashed in 1.x whenever a source was tracked.
* **Timeouts apply everywhere.** `timeout_per_source` now applies to single-source and sequential searches too, and each source's clock starts when the search starts. A timed-out source is reported as `Timed out after <n>s`.
* **Timeouts open breakers.** With health tracking enabled, a search or `get_concept_details()` call cut off by `timeout_per_source` counts as a breaker failure, so a source that keeps hanging is skipped after `circuit_breaker_threshold` timeouts (5 by default). A timeout raised by the adapter itself is not counted a second time.
* **HTTP 404 is an answer, not a failure.** Adapters that use 404 for "no match" (Reactome, PubChem) no longer open their breaker on repeated empty searches. Other 4xx and 5xx errors still count.
* **Detail lookups respect open breakers.** `get_concept_details()` no longer calls a source whose breaker is open; with `source=` it returns `None`.
* **Zero is honoured.** `circuit_breaker_threshold=0` or `circuit_breaker_cooldown=0` is used as given instead of silently falling back to the defaults.

## Cache

* Creating a `CentralKnowledgeLookup` no longer replaces a cache you configured earlier with `init_cache()`. Use `ensure_cache()` if you want "create the default cache only when none exists".
* `clear(namespace)` deletes that namespace from the memory and disk tiers; in 1.x it only logged a warning.
* The CLI's `search --cache-dir` now really sets up the disk cache. Only adapters that use the shared cache (currently UniChem) store entries there.

## Term expansion

`expand_and_search()` asks the UMLS abbreviation source about each label once per run, at most `max_abbreviation_lookups` new labels per round (default 10) and three at a time. Raise the cap if you relied on every concept being checked; long runs no longer grow with the number of concepts found.

## Agent workflow

`run_workflow()` and `resume_workflow()` finally support pausing for approval:

* A paused run returns `status="awaiting_approval"` and an `approval_request` dict. In 1.x it came back as `reviewing` and could not be resumed.
* Runs share one in-memory checkpointer per process (`get_default_checkpointer()`). Pass `checkpointer=` to both functions to use your own.
* `resume_workflow()` raises `ValueError` for a thread that is not paused.
* Each network step has a time budget and a concurrency cap and queries only the sources you selected, so runs finish in seconds to minutes instead of hanging.
* `max_iterations=0` means no refinement rounds; 1.x treated it as 3.
* A refinement searches the refined query's own term variants. Review suggestions stay in the step details and are no longer appended to the query. Synonyms that the first pass's `expand` step found are not carried into the refined pass.

## Adapter behaviour

| Adapter | What changed |
| --- | --- |
| BioPortal | `get_concept_details(concept_id, ontology=None)` needs the class IRI (the ontology acronym is inferred from BioPortal and OBO PURLs) or an explicit `ontology=`. When the ontology can't be determined, it returns `None` without a request. |
| BioOntology | `batch_annotate()` returns one list per text; `get_analytics()` applies its filters. |
| ChEMBL | `lookup_molecule()`, `lookup_drug()` and `lookup_target()` are `async`; `query_async()` is new. Searches fetch only the requested number of records in a worker thread. `check_api_status(timeout=...)` now sends real requests and can report the API as unavailable. |
| COSMIC | Unavailable (`is_available()` is `False`) without credentials; COSMIC has no query API. |
| DisGeNET | Every result is a disease concept with ID `UMLS_<CUI>`. A gene symbol or NCBI gene ID returns the diseases associated with that gene. |
| DrugBank | Data now comes from MyChem.info: IDs, names, synonyms, CAS, UNII and InChIKey, but no descriptions. The DrugBank data is licensed CC BY-NC 4.0. |
| EBI OLS | Identifiers and `source_data` are recorded under `EBIOLS` instead of `OLS`. Any `OLSAdapter` subclass now tags results with its own source; the private `EBIOLSAdapter._retag_as_ebiols()` is gone. |
| Europe PMC | Details accept `PMID:`, `PMCID:` and `PMID:PMC…` identifiers and include abstracts and authors. |
| NCBI E-utilities, QuickGO, Reactome, STRING, Tyto | Searches that returned nothing in 1.x now return results. Reactome types pathways as `PATHWAY` and reactions as `BIOLOGICAL_PROCESS`. Tyto search is an exact-label lookup in SO, SBO and NCIT. |
| Open Targets | Search hits carry names and entity types; disease details take MONDO, EFO or Orphanet IDs. |
| OxO | `get_datasources()` returns `[]`, because the upstream endpoint no longer exists. |
| Wikidata | MeSH IDs become `MeSH: <id>` categories instead of UMLS identifiers; results follow the search ranking. Each item appears once, with every instance-of value in `categories`. |
| DBpedia | Each resource appears once, with all its types in `categories`; labels and abstracts are found again. |

The [source availability page](../examples/availability-status.md) shows which sources return data today.

## Exports

`export_to_excel()` now writes the **Errors** sheet when a source failed; in 1.x it was silently missing. Error summaries in text reports and tables name the source (`BIOPORTAL`) instead of `KnowledgeSource.BIOPORTAL`.

## New in 2.0

* [MCP server](../guides/mcp-server.md): `knowledge-lookup-mcp` exposes search, details, mappings, source listing and CURIE validation to AI agents (`[mcp]` extra).
* `knowledge_lookup.cache.ensure_cache()` and `delete_prefix()` on the cache backends.
* `py.typed`, so type checkers use the package's annotations.
