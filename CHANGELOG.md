# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
