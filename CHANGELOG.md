# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
