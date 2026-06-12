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
- **Test markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.network`
- **Rate limiting**: Per-source in adapters via `get_rate_limit()`
- **Session management**: Use `await self._get_session()` for HTTP requests

## Development Workflow

1. **Add new adapter**: Create in `adapters/`, add to `models.KnowledgeSource` enum, `adapters/__init__.py`, `ADAPTER_CLASSES` in `central_lookup.py`
2. **Testing**: Write unit tests, ensure >90% coverage
3. **Pre-commit**: Black (line-length=99), Ruff, MyPy all run on `src/`

## Test Commands

```bash
poetry run pytest -m unit                    # Unit tests
poetry run pytest -m integration            # Integration tests
poetry run pytest -m "not slow"             # Skip slow tests
poetry run pytest --cov=knowledge_lookup    # With coverage
```

## Environment

- **Python**: 3.10+
- **Package manager**: Poetry only (no pip)
- **API keys**: Set as env vars (`BIOPORTAL_API_KEY`, `UMLS_API_KEY`, etc.) or in `.env`
