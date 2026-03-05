# Test Suite

Comprehensive test suite for the biomedical-knowledge-lookup package.

## Overview

This directory contains tests organized by category:

- **unit/**: Unit tests for individual components
- **integration/**: Integration tests with mocked API calls
- **performance/**: Performance benchmarks and stress tests
- **fixtures/**: Test data and mock API responses

## Quick Start

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=knowledge_lookup

# Run specific category
pytest tests/unit -v
pytest tests/integration -v -m integration
pytest tests/performance -v -m slow
```

## Test Coverage

Current test files:

### Unit Tests
- `test_models.py` - Data model tests
- `test_base.py` - Base adapter class tests
- `test_cache.py` - Caching system tests
- `test_adapters.py` - Adapter implementation tests

### Integration Tests
- `test_central_lookup.py` - CentralKnowledgeLookup integration tests

### Performance Tests
- `test_benchmarks.py` - Performance benchmarks for caching and search operations

### Fixtures
- `mock_responses.py` - Mock API responses for all adapters

## Writing Tests

See [TESTING.md](../TESTING.md) for detailed guidelines on:
- Writing unit tests
- Writing integration tests
- Using fixtures
- Mocking external APIs
- Running specific tests
- Debugging tests

## CI/CD

Tests are automatically run on:
- Push to main/develop
- Pull requests
- Multiple Python versions (3.10, 3.11, 3.12)
- Multiple platforms (Linux, macOS, Windows)

See `.github/workflows/tests.yml` for CI configuration.
