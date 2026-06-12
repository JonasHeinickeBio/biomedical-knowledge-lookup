# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
