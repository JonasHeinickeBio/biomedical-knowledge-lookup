# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

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

### Fixed
- Fixed issues with rate limiting in several adapters.
- Resolved dependency conflicts between different knowledge sources.
- Improved reliability of UMLS and BioPortal integrations.
