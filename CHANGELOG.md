# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Known / follow-up
- Adapters built on a library client (ChEMBL, EUtils/QuickGO/UniChem, Tyto,
  UMLS, EBI-OLS) don't route through the shared retry + circuit-breaker.
- Agent-workflow node coverage is low (7–64%).
- Dependabot reports outstanding dependency vulnerabilities on the branch.

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
