"""
README for Functional Adapter Tests

This directory contains functional tests that validate adapters against real API responses.

## Test Categories

### Unit Tests (tests/unit/)
- Mocked responses
- Fast execution
- No API calls

### Functional Tests (tests/functional/)
- Real API calls
- Validate actual response structures
- Detect API changes

## Running Tests

### All tests
```bash
poetry run pytest
```

### Only functional tests
```bash
poetry run pytest -m functional
```

### Functional tests with network access
```bash
poetry run pytest -m functional -m network
```

### With API key support
```bash
# Set API keys first (only needed for some adapters)
export BIOPORTAL_API_KEY="your_key"
export UMLS_API_KEY="your_key"

# Note: OpenTargets and ChEMBL no longer require API keys
# OpenTargets: Free public API
# ChEMBL: Free public API (no key needed)

# Run with API tests
poetry run pytest -m functional -m network -m api
```

### Using the test runner
```bash
# Run network tests
python tests/functional/run_tests.py --network

# Run with API tests
python tests/functional/run_tests.py --api
```

## API Response Validation

### Fixtures
Responses are cached in `tests/functional/api_fixtures/`:
- `uniprot_responses.json`
- `ols_responses.json`
- `bioportal_responses.json`
- And more...

### Change Detection
The validator detects:
- New keys added to responses
- Keys removed from responses
- Type changes in response fields
- List length changes

### Warnings
When API changes are detected:
1. Tests still pass (non-breaking)
2. Warnings are printed
3. Fixture files are updated

## Writing New Tests

```python
@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_adapter_search(adapter, response_validator, warning_manager):
    """Test adapter search with real API call."""
    adapter = MyAdapter(adapter.config)
    
    results = await adapter.search_concepts("query", limit=5)
    
    # Validate results
    assert isinstance(results, list)
    assert len(results) >= 1
    
    # Check response structure
    if results:
        response_data = {
            "total_results": len(results),
            "sample": [c.__dict__ for c in results[:2]]
        }
        
        validator = response_validator(KnowledgeSource.MYSOURCE)
        changes = validator.validate_response("my_search", response_data)
        for change in changes:
            warning_manager.add_warning(KnowledgeSource.MYSOURCE, "my_search", change)
```

## CI/CD Integration

Functional tests are disabled by default in CI to avoid:
- Network dependencies
- Rate limiting issues
- Flaky tests

Run locally for adapter development:
```bash
poetry run pytest -m functional -m network
```

## Troubleshooting

### Timeout errors
Increase timeout in config or use simpler queries.

### Rate limiting
Some APIs have strict rate limits. Add delays or use fewer queries.

### API key errors
Set environment variables for private APIs:
```bash
export BIOPORTAL_API_KEY="your_key"
export UMLS_API_KEY="your_key"
export DISGENET_API_KEY="your_key"
export DRUGBANK_API_KEY="your_key"
```

Note: OpenTargets and ChEMBL no longer require API keys. They are free public APIs.

### Connection errors
Check your internet connection and API availability.
