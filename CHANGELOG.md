# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

This is a major release. The breaking changes and how to adapt code written
for 1.x are collected in
[Upgrading to 2.0](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/docs/getting-started/upgrading-to-2.0.md).

### Added
- **Iterative term expansion** (`CentralKnowledgeLookup.search_concepts_expanded()`,
  `knowledge_lookup.core.term_expansion`): instead of searching a term once,
  searches it, harvests synonyms and long-form variants from what it finds
  (e.g. "COPD" also picks up "chronic obstructive pulmonary disease"),
  searches those too, and repeats until a round finds nothing genuinely new
  or a round cap is hit. Abbreviation candidates (via a UMLS Metathesaurus
  atom-term-type source when the `[umls]` extra and an API key are
  available) are recorded but never searched — a bare abbreviation is prone
  to colliding with unrelated concepts (e.g. "PEM" matching "pemphigoid"
  instead of "post-exertional malaise"). Every term tried, and every
  abbreviation found but not searched, is recorded durably via the new
  `knowledge_lookup.core.expansion_store.ExpansionStore` (SQLite-backed,
  never evicts). Core-level capability, usable without the `[agents]`
  extra; also wired into the LangGraph agent workflow as a new `expand`
  node between `preprocess` and `lookup`.
- `scripts/demo_expanded_lookup_mecfs.py`: live demo of iterative term
  expansion over 10 ME/CFS-related terms.
- **MCP server** (`knowledge_lookup.mcp_server`, `[mcp]` extra,
  `knowledge-lookup-mcp` console script). Exposes the lookup to LLM agents over
  the Model Context Protocol using the official `mcp` 2.x SDK: five read-only,
  annotated tools (`biomed_search_concepts`, `biomed_get_concept`,
  `biomed_find_mappings`, `biomed_list_sources`, `biomed_validate_curie`) with
  structured output, concise/detailed response formats, pagination and a
  25,000-character result cap; `biomed://sources` and
  `biomed://concept/{concept_id}` resources; and `normalize_terms` /
  `annotate_text` prompts. Identifiers are routed to the source that owns them
  (CURIE prefix, OBO PURL, accession shape) instead of asking every adapter, and
  adapters built on synchronous clients (ChEMBL, Tyto, EUtils, QuickGO,
  UniChem) run on their own event-loop threads so a slow query cannot stall the
  server. Supports stdio and Streamable HTTP. See `docs/guides/mcp-server.md`.
- `knowledge_lookup.cache.ensure_cache()` (creates the default cache only when
  none is configured) and `delete_prefix()` on the memory and disk cache
  backends.
- Agent workflow: `get_default_checkpointer()`, an optional `checkpointer=`
  argument on `run_workflow()` / `resume_workflow()`, and an
  `approval_request` key in paused results.
- `knowledge_lookup.utils.redaction.redact()` masks API keys and auth tokens in
  log messages.
- `expand_and_search(max_abbreviation_lookups=10)` caps UMLS abbreviation
  lookups per expansion round; `SourceHealthTracker.record_failure()`;
  `ChEMBLAdapter.check_api_status(timeout=...)`.
- `py.typed` marker, so type checkers use the package's inline annotations.

### Changed
- **Release process:** the `staging` branch and its bot-merged promotion are
  gone; pull requests target `main`. After each merge the release workflow
  opens or updates a `chore(release): vX.Y.Z` pull request with the
  CHANGELOG cut, and merging that pull request creates the draft release.
  One `ci.yml` workflow replaces `staging.yml` and `tests.yml`, and
  `publish.yml` now runs once per release (on the tag) and never cancels a
  running upload. See `CONTRIBUTING.md`.
- **Breaking: Python >= 3.11 is now required** (was >= 3.10); CI tests 3.11,
  3.12 and 3.13. This lets every dependency move to its newest release (the
  newest pandas, bioregistry and curies need 3.11+). Ruff and mypy now target
  Python 3.11: `asyncio.TimeoutError` aliases are replaced with `TimeoutError`,
  and `UP042` is ignored because turning the generated `(str, Enum)` classes
  into `StrEnum` would change their `str()` output.
- **Dependencies upgraded to the newest resolvable releases** and re-locked
  (`poetry.lock`, `uv.lock`, `requirements.txt`), with version floors raised
  to match. Core: aiohttp 3.14, rdflib 7.6, pydantic 2.13, python-dotenv 1.2,
  rich 15, typer 0.27. Extras: pandas 3.0, langgraph 1.2.11, bioregistry 0.14,
  curies 0.15. Dev: pytest 9, pytest-asyncio 1.4, pytest-cov 7,
  pytest-rerunfailures 16, ruff 0.16, mypy 2.3, ipykernel 7, linkml 1.11.
  Build: poetry-core 2.4, poetry-dynamic-versioning 1.10.
  Pre-commit hooks follow suit (pre-commit-hooks 6.0, ruff 0.16.7, mypy 2.3.1).
- **Breaking:** `ChEMBLAdapter.lookup_molecule()`, `lookup_drug()` and
  `lookup_target()` are now `async` (they returned un-awaited coroutines
  before) and must be awaited. The new `query_async()` runs ChEMBL queries in a
  worker thread.
- pandas 3.0 for the `export` extra. It was held below 3.0 by pyobo, whose
  `bioregistry[align]` dependency caps pandas, and pyobo is no longer a
  dependency (see Removed).
- Test tooling: removed the custom `event_loop` fixture (dropped in
  pytest-asyncio 1.x) and marked the async functional-test fixtures with
  `@pytest_asyncio.fixture`. Ruff now also ignores `UP045` (the `Optional[X]`
  half of `UP007`) for the generated LinkML models, and `src/` is reformatted
  with ruff 0.16.

### Removed
- **Breaking: legacy duplicate and demo modules.**
  `knowledge_lookup.validation_models` and `knowledge_lookup.generated_models`
  (duplicates of `knowledge_lookup.models`),
  `knowledge_lookup.adapters.additional_adapters` (outdated copies of the
  DBpedia, OxO and BioOntology adapters), and the demo modules
  `knowledge_lookup.examples` (which loaded `.env` and changed `sys.path` on
  import) and `knowledge_lookup.cache.cache_demo`. The LinkML `make
  generate-python` target now writes to `knowledge_lookup/models/`.
- `MANIFEST.in`, which the Poetry build backend never read.
- **`tenacity` dependency.** Nothing in the package imports it, but 1.2.0 still
  pinned `tenacity<9.0.0`, so it could not be installed alongside packages that
  need tenacity 9 (e.g. `pyeuropepmc` 2.2.1).
- **Other dependencies nothing used**: `requests` (core), `pyobo` (`curie`
  extra; CURIE handling only uses `bioregistry` and `curies`), and from the dev
  tooling `setuptools`, `linkml-runtime` (already required by `linkml`) and the
  whole `docs` group (`sphinx`, `sphinx-rtd-theme`; the repo has no Sphinx
  configuration). The pre-commit mypy hook no longer installs `types-requests`
  and `types-setuptools`.

### Fixed
- **BioPortal details**: `get_concept_details` built an invalid URL and never
  returned data. It now requests
  `/ontologies/{ACRONYM}/classes/{IRI}`, inferring the ontology from BioPortal
  and OBO PURLs (or taking an explicit `ontology=`), and skips the request when
  the ontology can't be determined. BioOntology details infer the ontology the
  same way.
- **BioOntology**: `batch_annotate` now annotates each text concurrently and
  returns one list per text; `get_analytics` applies its `ontology`, `month` and
  `year` filters.
- **UMLS**: the `UMLS_API_KEY_TU` fallback key is honoured, and concept details
  fall back to semantic-type TUIs when the type name is unmapped
  (`ConceptType.UNKNOWN` is truthy, so the old `or` fallback never ran).
- **`LookupConfig.get_api_key`** returned a plain-string `api_keys` value for
  every service. Only a JSON object is now read per service, then the
  `{SERVICE}_API_KEY` environment variables.
- **`CentralKnowledgeLookup`**:
  - `lookup_and_convert_to_rdf` raised `ModuleNotFoundError`.
  - `get_statistics` crashed on the string circuit state and never counted open
    breakers; `MultiSourceAnnotator` stats had the same crash.
  - Open circuit breakers never skipped a source. Searches now skip open sources
    (recorded in `errors`), and health snapshots report `HALF_OPEN` once the
    cooldown has passed.
  - `timeout_per_source` applied only to parallel searches, and later sources
    got extra time; every search path now times each source from the start.
  - Creating a lookup replaced a cache configured earlier with `init_cache()`.
  - `export_to_excel` wrote the Errors sheet after the workbook was closed, so it
    was silently missing.
  - An explicit `circuit_breaker_threshold` or `circuit_breaker_cooldown` of 0
    was replaced by the default.
  - Error summaries printed `KnowledgeSource.X` instead of the source name.
  - A source that hung until `timeout_per_source` never opened its circuit
    breaker; such timeouts now count as failures. `get_concept_details` also
    skips sources whose breaker is open.
  - An HTTP 404 counted as a breaker failure, so repeated no-match queries
    (Reactome, PubChem) opened the breaker. A 404 now counts as an answer.
- **Cache**: `clear(namespace)` only logged a warning; it now deletes that
  namespace from the memory and disk tiers.
- **Agent workflow**:
  - `resume_workflow` could never resume a paused run (each call used a fresh
    checkpointer), and a pause was reported as `reviewing`. Runs now share one
    checkpointer, pauses return `awaiting_approval` with `approval_request`,
    and the CLI keeps prompting until the run finishes.
  - Runs could hang for many minutes: term expansion ignored the selected
    sources and nodes fanned out without limits. Each network node now has a
    time budget and a concurrency cap and queries only the selected sources.
  - A failed per-term lookup crashed the next node's state validation.
  - `max_iterations=0` was treated as 3.
  - A refinement kept searching the first pass's terms, and review
    suggestions were appended to the query text.
- **Term expansion** asked the UMLS abbreviation source about every concept,
  one at a time and again in every round. Each label is now asked once per
  run, at most `max_abbreviation_lookups` new labels per round, three at a
  time.
- **CLI**: `sources` and `info` list all 36 sources; `search --cache-dir` now
  configures the disk cache, closes the lookup, and reports only the queried
  sources in JSON output.
- **Adapters**:
  - Reactome search read the grouped response incorrectly and returned nothing;
    pathways and reactions are now typed `PATHWAY` and `BIOLOGICAL_PROCESS`
    instead of `UNKNOWN`.
  - STRING rejected its `text/json` responses.
  - DrugBank used an OLS ontology that no longer exists; it now uses
    MyChem.info (keyless).
  - Open Targets search hits lacked names and types, and disease details used
    fields the API no longer has.
  - DisGeNET read outdated fields and sent disease names to an ID-only
    parameter; details raised instead of returning `None`.
  - Europe PMC details rejected `PMID:` identifiers and returned no abstracts.
  - ClinVar ignored the current `germline_classification` fields.
  - COSMIC has no query API: the adapter is now unavailable without
    credentials instead of silently returning nothing.
  - NCBI E-utilities returned nothing: it parsed an outdated bioservices
    response shape, swallowed per-database errors, and PubMed details requested
    an empty format. Search and details (PubMed, Gene, Protein, Taxonomy) work.
  - QuickGO search sent free text to an ID-only endpoint; it now uses the
    QuickGO term search, and annotations are requested only for gene products.
  - Tyto called functions the `tyto` package doesn't have. Details resolve SO,
    SBO and NCIT term IRIs, and search is an exact-label lookup.
  - ChEMBL: `search_concepts` downloaded every matching record and ran the
    synchronous client on the event loop; results are now sliced lazily and
    fetched in a worker thread. Target details matched an unrelated drug
    through a filter field the drug endpoint doesn't have.
  - OxO called the removed `/api/datasources` endpoint and added each
    identifier twice.
  - Wikidata and DBpedia put search text into SPARQL queries unescaped;
    Wikidata recorded MeSH IDs as UMLS identifiers, and DBpedia never found
    labels or abstracts (it compared prefixed names with full IRIs).
  - EBI OLS recorded its identifiers under `OLS` instead of `EBIOLS`; every
    `OLSAdapter` subclass now tags results with its own source.
  - Wikidata and DBpedia returned a resource once per type or instance-of
    value, and the repeats counted toward `limit`; each resource now appears
    once with all its types in `categories`.
  - `ChEMBLAdapter.check_api_status()` never sent a request and always
    reported the API as available.
- The root `example_notebooks/clinical_symptom_validation.ipynb` was not valid
  JSON and checked semantic-type TUIs against type names; it is rebuilt and
  runs against live UMLS.
- `knowledge_lookup.models.convert_generated_unified_concept()`,
  `convert_generated_lookup_result()` and `convert_generated_lookup_config()`
  raised a validation error on every call (they passed dicts into the
  generated models' JSON-string fields); they work now.
- `knowledge_lookup.__version__` was hard-coded to `"1.0.0"` in source
  checkouts and editable installs; it now reports the installed version.
- Packaging: `openpyxl` is part of the `export` extra (needed by
  `export_to_excel`), and the package ships `py.typed`.

### Security
- **API keys no longer leak into logs.** BioPortal and BioOntology sent the key
  as an `apikey` query parameter, and failed requests logged the full URL
  (aiohttp includes it in the exception message). Both now authenticate with
  the `Authorization: apikey token=...` header. OMIM still needs the key in the
  URL, so its error messages are masked with the new
  `knowledge_lookup.utils.redaction.redact()` helper, which the BioPortal and
  BioOntology error logs use as well.
- Removed a BioPortal API key from the stored cell outputs of
  `example_notebooks/bioontology_adapter_example.ipynb`,
  `bioportal_adapter_example.ipynb` and `rdf_converter_demo.ipynb`, where it
  appeared in logged request URLs. The key remains in earlier commits, so it
  must be revoked and replaced.


## [1.2.0] - 2026-09-11

### Added
- **Richer agent workflow** (`knowledge_lookup.agents`, `[agents]` extra).
  The LangGraph graph gained four stages between lookup and review:
  `preprocess` (splits comma-separated terms and generates umlaut-expanded /
  normalized / German-compound-split search variants, run in parallel),
  `filter` (drops non-clinical concepts — questionnaires, measurement
  scales, geographic/gazetteer entries — and boosts confidence for
  clinically relevant semantic types), `quality_gate` (scores the filtered
  results before the LLM review), and `detail_gather` (cross-source detail
  enrichment: definitions, synonyms, semantic types, contributing sources).
  A new `aggregate` node builds a structured text report for the LLM
  reviewer, and a `prune` node drops consumed intermediate state
  (`aggregated_context`, the raw `lookup_result`) before export to keep
  checkpoints small. `review` now always builds a deterministic
  term→UMLS-CUI→ontology-IDs→type concept map alongside the LLM's
  rubric-based quality judgment (6 weighted dimensions, reasoning-before-
  score, JSON extracted via cascading strategies, 3 retries with backoff),
  and both the concept map and the LLM's explanation flow through to
  `export` and the `workflow` CLI command.
- **`knowledge_lookup.curie_utils`** (`[curie]` extra): CURIE/URI parsing,
  prefix validation, and identifier/CURIE normalization via `bioregistry` +
  `curies`, plus `ConceptIdentifier.to_curies_reference()` /
  `.from_curies_reference()` and a local-`Converter` builder. Standalone
  toolkit for now — see [docs/curie-management.md](docs/curie-management.md)
  for exactly what is (and isn't yet) wired into `CentralKnowledgeLookup`.
- `scripts/batch_lookup.py`: CSV batch lookup + LLM review helper script.

### Changed
- **Lean core install.** Heavy / niche dependencies moved out of the base
  install into optional extras: `pandas` → `[export]`, `chembl-webresource-client`
  → `[chembl]`, `bioservices` → `[bioservices]` (EUtils/QuickGO/UniChem),
  `tyto` → `[tyto]`, `langgraph` → `[agents]`, plus `[curie]`
  (`bioregistry`/`curies`/`pyobo`) and the existing `[umls]`. A new `[all]`
  extra installs everything. `pip install biomedical-knowledge-lookup` now
  pulls only `aiohttp`/`requests`/`rdflib`/`pydantic`/`rich`/`typer` and the
  small helpers — every HTTP-only adapter still works.
- `requires-python` relaxed `>=3.11` → `>=3.10,<4` (CI already tests 3.10; ruff
  and mypy target py310).
- Extras declared as PEP 621 `[project.optional-dependencies]` (was the
  deprecated `[tool.poetry.extras]`).

### Fixed
- `ChEMBLAdapter` and `knowledge_lookup.agents` now raise a clear
  `ImportError` naming the required extra instead of a bare
  `ModuleNotFoundError`; `chembl_adapter` no longer fails to import when
  `chembl-webresource-client` is absent.
- **Adapter CURIE-parsing snippet removed.** A `parse_curie_or_uri` /
  `validate_prefix` block (debug-logging only, no behaviour) had been pasted
  into ~30 adapter methods; in `oxo`, `zooma`, `obofoundry`, `disgenet`,
  `tyto` and `biolinker` it referenced an out-of-scope `concept_id` / `query`
  (or, in `oxo`, an import trapped inside the class docstring), so those
  adapters raised `NameError` and returned nothing. All of it is gone; those
  six adapters work again (29 unit tests unblocked). CURIE-aware input
  handling, if reintroduced, belongs once in the base class.
- **HPO adapter**: `hpo.jax.org/api/ontological` (now 404) → the current
  `ontology.jax.org/api/hp` API; search/details work again and UMLS xrefs
  are captured.
- **`CentralKnowledgeLookup.find_mappings`** now returns real cross-references
  from OxO (was a stub returning the concept's own id), de-duplicated, with a
  working `target_sources` filter.
- **`search_concepts(concept_types=[...])`** no longer silently drops every
  result: concepts an adapter left as `UNKNOWN` pass the filter instead of
  being discarded.
- Retry backoff is skipped under pytest (`PYTEST_CURRENT_TEST`), so error-path
  tests no longer spend ~10 s sleeping; set `BKL_RETRY_SLEEP=1` to force it.
- New `tests/unit/conftest.py` stubs the agent-workflow LLM call so unit tests
  are deterministic and offline (fixes two flaky `review_node` tests).
- `zooma_adapter`: removed a duplicated `if concept.categories is not None`.
- **`curie_utils` was non-functional end-to-end**: every function was written
  against an older `curies.Converter` API (`.record_map`, `.normalize()`)
  that no longer exists on the installed version, so `validate_prefix`,
  `normalize_curie`, `parse_curie_or_uri`, `get_prefix_mapping`, and
  `get_source_prefix_mapping` silently returned `False`/`None`/`{}` for
  every input; `normalize_identifier` called pyobo's `wrap_norm_prefix`
  as if it were a normalizer instead of the decorator it actually is. All
  five now use the real `curies` API (`has_prefix`, `standardize_curie`,
  `standardize_identifier`, `parse`, `.records`) and are verified against
  live bioregistry data.
- `curie_utils.create_local_converter`: unconditionally appended `/` to every
  `uri_prefix`, breaking OBO-style underscore URIs (`DOID_9351`) so a local
  converter's `compress`/`expand` never matched. The URI prefix is now used
  verbatim, as the caller supplied it.
- `curie_utils.reference_to_concept_identifier`: `url` was always `None`
  because it checked `hasattr(reference, "uri")`, an attribute a bare
  `curies.Reference` never has; now documented and left `None` honestly
  (resolving a URI needs a `Converter`, not a bare `Reference`).
- `CentralKnowledgeLookup._deduplicate_concepts` called
  `get_bioregistry_converter()` and discarded the result — a no-op that
  didn't do the CURIE-based normalization its docstring claimed. Removed;
  dedup is exact-label matching, honestly documented.
- Agent `filter` node: `_has_non_clinical_source_only` (drops concepts that
  come only from non-clinical sources like the GAZ gazetteer) was defined
  but never called; now wired into the filter pipeline. Also removed a
  tautological `sources == {"WIKIDATA"} or sources == {"WIKIDATA"}` check.
- Agent `prune` node: now actually clears `lookup_result` after copying it
  to `final_result`, matching its own docstring/purpose (reduce checkpoint
  size); previously only `aggregated_context` was cleared.
- README.md / docs/README.md / docs/curie-management.md described
  CentralKnowledgeLookup as auto-parsing CURIE/URI search queries and
  `normalize_curie` as cross-mapping ontologies (e.g. DOID → MONDO) —
  neither is true; corrected to describe actual behavior, and a
  duplicated/broken doc-list entry was fixed.

### Known / follow-up
- Adapters built on a library client (ChEMBL, EUtils/QuickGO/UniChem, Tyto,
  UMLS, EBI-OLS) don't route through the shared retry + circuit-breaker.
- Some agent-workflow nodes (`filter`, `aggregate`, `detail_gather`,
  `preprocess`) still have no dedicated unit tests — covered only
  indirectly via `test_langgraph_workflow.py`'s end-to-end graph tests.
- Dependabot reports outstanding dependency vulnerabilities on the branch.
- **Version is not actually dynamic.** `[build-system]` points at
  `poetry_dynamic_versioning.backend`, but `[project] version = "1.1.0"` is
  not listed in `dynamic = [...]`, so PEP 621 requires build backends to
  leave it alone — every past release (1.0.0 → 1.1.0) bumped `version`
  manually before tagging, and the next one needs the same manual bump
  (CI's publish workflow fails the tag-vs-`poetry version` check otherwise).
  To make versioning actually tag-driven, add `"version"` to `dynamic` and a
  `[tool.poetry-dynamic-versioning]` table with `enable = true` — left
  undone here since it changes the release process itself.

## [1.1.0] - 2026-06-24

### Added
- Pydantic model regeneration for type-safe field handling across all models.
- `KnowledgeSourceAdapter` backward-compatible wrapper (`extensions.py`) to insulate callers from generated model changes.
- `_SourceList` wrapper class for source list backward compatibility.
- `get_status()` method on `CentralKnowledgeLookup` for runtime introspection.

### Changed
- **Breaking (internal):** Regenerated pydantic models from LinkML schema — fields `source_data`, `labels`, `errors`, `api_keys` changed from `Dict` to `Optional[str]` (JSON-serialized), `sources` fields from `list[KnowledgeSource]` to `list[str]`, and `concept_type` from `ConceptType` enum to `str`.
- Wrapper classes (`UnifiedConcept`, `LookupResult`, `LookupConfig`, `ConceptIdentifier`, `ConceptMapping`) now intercept pydantic's generated field types via `__init__`, `__getattribute__`, and `__setattr__` overrides to maintain the original dict/enum-based API.
- Adapter builders (`disgenet_adapter`, `kegg_adapter`, `chembl_adapter`) updated for None-safe optional field handling.
- Export functions (`exports.py`) use `isinstance` guards for source enum→string conversion.
- UMLS RDF module (`umls/rdf.py`) uses `str(src)` instead of `src.value` for string-typed source fields.
- CLI `__main__.py`, `examples.py`, and `benchmarks/run_benchmark.py` updated for string-typed sources.

### Fixed
- `multi_source_annotator.py`: Fixed import path (`from .models → from ..models`).
- ChEMBL adapter: Handles None identifiers by falling back to empty string for required pydantic fields.
- All adapters: `concept_type` is `None`-safe throughout formatting and export pipelines.
- LookupConfig: `__getattribute__` intercepts `api_keys` to return the internal dict instead of the generated `Optional[str]`.
- LookupResult: `__getattribute__` intercepts `errors`, `source_health`, `sources_succeeded`, `sources_failed` for backward-compatible dict/list access.
- Resolved `'str' object has no attribute 'value'` errors in `umls/rdf.py`, `examples.py`, and `central_lookup.py` format strings.
- Resolved `1 validation error for UnifiedConcept: source_data` in ChEMBL adapter when passing dict values.

### Removed
- Dependencies on `umls-python-client` made optional (extras `[umls]`).

## [1.0.0] - 2026-06-12

### Added
- Initial release of Biomedical Knowledge Lookup.
- Support for 29+ biomedical knowledge sources.
- Unified API for searching concepts and getting details.
- Multi-source annotation system with consensus analysis.
- RDF export capabilities for knowledge graph integration.
- Intelligent caching system for API results.
- Comprehensive unit and integration test suite.
- Detailed documentation for core adapters.
- Command-line interface for concept lookup.
- Example notebooks for all major features.

### Changed
- Refactored adapter architecture for better extensibility.
- Improved error handling and retry logic for API calls.
- Enhanced performance of multi-source annotation.
- Migrated from Black to Ruff for code formatting.
- Updated mypy configuration to resolve duplicate module name errors.

### Fixed
- Fixed issues with rate limiting in several adapters.
- Resolved dependency conflicts between different knowledge sources.
- Improved reliability of UMLS and BioPortal integrations.
- Fixed duplicate module name error with Poetry's .pth file handling.
- Updated typing syntax for Python 3.10+ compatibility.
- Fixed Typer compatibility issues with Optional and Annotated types.

### Documentation
- Complete documentation overhaul with professional formatting.
- Added comprehensive adapter documentation for all 29+ knowledge sources.
- Created Getting Started guide with installation and usage examples.
- Added API reference documentation for developers.
- Improved docs folder structure with consistent organization.
- Added architecture diagrams and adapter category listings.
