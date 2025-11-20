# Testing Guide

This document provides comprehensive information about the test suite for the biomedical-knowledge-lookup project.

## Test Structure

The test suite is organized into several categories:

```
tests/
├── unit/               # Unit tests for individual components
├── integration/        # Integration tests with mocked APIs
├── performance/        # Performance benchmarks
└── fixtures/          # Test data and mock responses
```

## Running Tests

### Run All Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=knowledge_lookup --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit -v

# Integration tests only
pytest tests/integration -v -m integration

# Performance tests (slow)
pytest tests/performance -v -m slow

# Skip slow tests
pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Test models
pytest tests/unit/test_models.py -v

# Test adapters
pytest tests/unit/test_adapters.py -v

# Test cache
pytest tests/unit/test_cache.py -v
```

## Test Coverage

The project aims for >90% test coverage. Check current coverage:

```bash
# Generate coverage report
pytest --cov=knowledge_lookup --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=knowledge_lookup --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Writing Tests

### Unit Tests

Unit tests should test individual components in isolation using mocks:

```python
import pytest
from unittest.mock import patch, AsyncMock
from knowledge_lookup.adapters.ols_adapter import OLSAdapter

@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_search_concepts(mock_get, lookup_config):
    """Test OLS adapter search."""
    adapter = OLSAdapter(lookup_config)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"results": []})
    mock_get.return_value.__aenter__.return_value = mock_response
    
    results = await adapter.search_concepts("diabetes")
    assert isinstance(results, list)
```

### Integration Tests

Integration tests verify that components work together:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_source_search(lookup):
    """Test searching across multiple sources."""
    results = await lookup.search_concepts(
        "diabetes",
        sources=[KnowledgeSource.OLS, KnowledgeSource.BIOPORTAL]
    )
    assert isinstance(results, dict)
    assert len(results) > 0
```

### Performance Tests

Performance tests benchmark critical operations:

```python
@pytest.mark.slow
def test_cache_performance(cache):
    """Benchmark cache operations."""
    import time
    
    start = time.time()
    for i in range(1000):
        cache.set(f"key_{i}", f"value_{i}")
    duration = time.time() - start
    
    assert duration < 1.0  # Should complete in under 1 second
```

## Test Fixtures

Common test fixtures are defined in `tests/conftest.py`:

- `lookup_config`: Default LookupConfig for testing
- `sample_unified_concept`: Sample UnifiedConcept instance
- `sample_unified_concepts`: List of sample concepts
- `mock_*_response`: Mock API responses for various adapters

Use fixtures in your tests:

```python
def test_with_config(lookup_config):
    """Test using the lookup_config fixture."""
    adapter = OLSAdapter(lookup_config)
    assert adapter.config == lookup_config
```

## Mocking External APIs

All tests that would normally call external APIs should use mocks:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_api_call(mock_get):
    """Test with mocked API call."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": "test"})
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Your test code here
```

## Test Markers

Tests are marked with pytest markers for categorization:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow-running tests (>1 second)
- `@pytest.mark.network`: Tests requiring network access
- `@pytest.mark.asyncio`: Async tests

Run tests by marker:

```bash
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Continuous Integration

Tests are automatically run in CI/CD on:

- Every push to `main` and `develop` branches
- Every pull request
- Multiple Python versions (3.10, 3.11, 3.12)
- Multiple operating systems (Ubuntu, macOS, Windows)

See `.github/workflows/tests.yml` for CI configuration.

## Test Data

Mock response data is provided in `tests/fixtures/mock_responses.py`:

```python
from tests.fixtures.mock_responses import (
    OLS_SEARCH_RESPONSE,
    BIOPORTAL_CONCEPT_DETAILS,
    CHEMBL_MOLECULE_DETAILS,
)

def test_with_mock_data():
    """Test using pre-defined mock data."""
    # Use mock data in your tests
    assert OLS_SEARCH_RESPONSE["_embedded"]["terms"]
```

## Debugging Tests

### Run a Single Test

```bash
pytest tests/unit/test_models.py::TestUnifiedConcept::test_unified_concept_creation -v
```

### Show Print Statements

```bash
pytest -s  # Show stdout
pytest -vv  # Very verbose
```

### Drop into Debugger on Failure

```bash
pytest --pdb  # Drop into pdb on failure
pytest --pdb --maxfail=1  # Stop on first failure
```

### View Test Output

```bash
pytest -v --tb=short  # Short traceback
pytest -v --tb=long   # Long traceback
pytest -v --tb=line   # One line per failure
```

## Code Quality

### Linting

```bash
# Run black formatter
black src/knowledge_lookup

# Run ruff linter
ruff check src/knowledge_lookup

# Run mypy type checker
mypy src/knowledge_lookup --ignore-missing-imports
```

### Pre-commit Hooks

Install pre-commit hooks to automatically check code quality:

```bash
pip install pre-commit
pre-commit install
```

## Contributing Tests

When contributing new features:

1. **Write tests first** (TDD approach recommended)
2. **Ensure all tests pass** before submitting PR
3. **Maintain or improve coverage** (aim for >90%)
4. **Add integration tests** for new adapters
5. **Document test fixtures** if adding new ones
6. **Use appropriate markers** for test categorization

### Test Checklist for New Adapters

When adding a new adapter, ensure you have:

- [ ] Unit tests for adapter initialization
- [ ] Unit tests for `search_concepts()`
- [ ] Unit tests for `get_concept_details()`
- [ ] Unit tests for error handling
- [ ] Integration tests with mocked API responses
- [ ] Test coverage >90%
- [ ] Mock responses in `tests/fixtures/mock_responses.py`

## Performance Benchmarking

Run performance benchmarks:

```bash
# Run all performance tests
pytest tests/performance -v -m slow

# Run with pytest-benchmark (if installed)
pytest tests/performance --benchmark-only
```

Performance tests help identify:
- Cache efficiency
- API response time impact
- Batch operation performance
- Memory usage patterns

## Troubleshooting

### Tests Hanging

If async tests hang:
- Check for missing `@pytest.mark.asyncio` decorator
- Verify all async functions are properly awaited
- Look for deadlocks in concurrent operations

### Import Errors

If you get import errors:
- Ensure package is installed: `pip install -e .`
- Check PYTHONPATH includes project root
- Verify test structure matches package structure

### Fixture Errors

If fixtures aren't working:
- Check `tests/conftest.py` is present
- Verify fixture scope is correct
- Ensure fixture names don't conflict

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
