# AGENTS.md

## Quick Start

```bash
poetry install                     # Setup dev environment
poetry run pytest                  # Run tests
poetry run pre-commit run --all-files  # Lint/format
poetry run knowledge-lookup search "query"  # CLI
```

## Architecture

- **Core**: `src/knowledge_lookup/` contains adapters, `CentralKnowledgeLookup`, `MultiSourceAnnotator`
- **Testing**: `tests/unit/`, `tests/integration/`, `tests/fixtures/mock_responses.py` has all mock API responses
- **CLI**: `src/knowledge_lookup/__main__.py` via `knowledge-lookup` command

## Critical Patterns

- **All adapter methods are async** (`async def search_concepts(...)`)
- **Adapters extend `KnowledgeSourceAdapter`** from `base.py` - implement `get_source()`, `search_concepts()`, `get_concept_details()`
- **Use fixtures** from `tests/conftest.py` and `tests/fixtures/mock_responses.py`
- **Test markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.network`, `@pytest.mark.api`
- **Rate limiting**: Per-source in adapters via `get_rate_limit()` (returns `config.rate_limits.get(self.source, 1.0)`)
- **Session management**: Use `await self._get_session()` for HTTP requests
- **Circuit breaker**: All adapters receive a shared `CircuitBreaker` injected via `set_circuit_breaker()` from `SourceHealthTracker`
- **Mock dependencies**: `chembl_webresource_client` and `bioservices` must be mocked in `sys.modules` before importing `knowledge_lookup` (see `tests/conftest.py` lines 21-26)

## Development Workflow

1. **Add new adapter**: Create in `adapters/`, add to `models.KnowledgeSource` enum, `adapters/__init__.py`, `ADAPTER_CLASSES` dict
2. **Testing**: Write unit tests, ensure >90% coverage, add mock to `tests/fixtures/mock_responses.py`
3. **Pre-commit**: Ruff format + lint (line-length=99), MyPy (with `--ignore-missing-imports`), runs on `src/`
   - **Note**: Pre-commit excludes `UP007` and `E501` from linting (`ruff --ignore=UP007,E501`)
4. **UMLS adapter**: Optional - requires `umls-python-client` and `UMLS_API_KEY` env var

## Test Commands

```bash
poetry run pytest -m unit                    # Unit tests (excludes slow)
poetry run pytest -m integration            # Integration tests
poetry run pytest -m "not slow"             # Skip slow tests
poetry run pytest --cov=knowledge_lookup    # With coverage
poetry run pytest tests/unit/test_all_adapters.py  # Test all adapters
```

## Environment

- **Python**: 3.10+ (pyproject.toml: `python = "^3.10"`)
- **Package manager**: Poetry only (no pip)
- **API keys**: Set as env vars (`{SOURCE}_API_KEY` or `{source}_api_key`), or in `.env`
  - `BIOPORTAL_API_KEY`, `UMLS_API_KEY` required for their adapters
  - Other sources (OLS, Wikidata, etc.) work without keys
- **CLI options**: `knowledge-lookup search --partial` enables fuzzy matching for UMLS only

## Known Gotchas

- **Slow tests**: Tests marked `@pytest.mark.slow` include network calls or heavy adapters (UMLS, UniProt); use `-m "not slow"` to skip
- **Parallel queries**: `CentralKnowledgeLookup.search_concepts()` runs sources in parallel by default
- **Circuit breaker**: Opens after 5 consecutive failures (`circuit_breaker_threshold`), cooldown 30s
- **Deduplication**: Results are deduplicated by normalized label (lowercase, stripped)
- **Async context**: All adapters use `aiohttp.ClientSession`; ensure proper cleanup with `await adapter.close()`
