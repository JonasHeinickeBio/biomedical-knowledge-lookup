# AI Coding Agent Instructions for Biomedical Knowledge Lookup

## Project Overview
This is a unified Python library for biological concept lookup across 29+ biomedical knowledge sources. It provides a single API to search and retrieve concepts from databases like BioPortal, OLS, UniProt, ChEMBL, DisGeNET, and more.

## Architecture
- **Central Coordinator**: `CentralKnowledgeLookup` in `central_lookup.py` orchestrates queries across multiple adapters
- **Adapter Pattern**: Each knowledge source has an adapter extending `KnowledgeSourceAdapter` in `base.py`
- **Unified Models**: `UnifiedConcept`, `LookupResult`, and related models in `models.py` standardize data across sources
- **Factory Pattern**: `factory.py` creates configured lookup instances
- **Multi-source Features**: Cross-referencing via `MultiSourceAnnotator`, RDF export via `rdf_converter.py`

## Key Files and Directories
- `src/knowledge_lookup/central_lookup.py`: Main lookup coordinator with parallel/sequential querying
- `src/knowledge_lookup/adapters/`: Individual source adapters (extend `base.py`)
- `src/knowledge_lookup/models.py`: Data models, enums for sources and concept types
- `src/knowledge_lookup/base.py`: Abstract adapter base class
- `src/knowledge_lookup/multi_source_annotator.py`: Cross-source concept annotation
- `src/knowledge_lookup/rdf_converter.py`: RDF export utilities
- `src/knowledge_lookup/cache.py`: Intelligent caching system
- `tests/unit/`: Unit tests for adapters and core functionality
- `tests/functional/`: Integration tests

## Development Workflows
- **Setup**: `poetry install` (includes dev dependencies)
- **Testing**: `poetry run pytest` (unit/integration markers available) - Note: run through Poetry to ensure correct environment
- **Code Quality**: `poetry run pre-commit run --all-files` (Black, Ruff, MyPy)
- **CLI**: `poetry run knowledge-lookup search "diabetes"` (via `__main__.py`)
- **API Keys**: Set as environment variables (e.g., `BIOPORTAL_API_KEY`) or in `.env`

## Coding Patterns
- **Async First**: All adapter methods are async (`async def search_concepts(...)`)
- **Rate Limiting**: Implemented per source in adapters (`get_rate_limit()`)
- **Error Handling**: Adapters catch exceptions, return empty lists or None
- **Deduplication**: Results merged by normalized label in `central_lookup.py`
- **Configuration**: `LookupConfig` class manages sources, timeouts, API keys
- **Testing**: Use `pytest-asyncio` for async tests, mock external APIs

## Adding New Adapters
1. Create `adapters/new_source_adapter.py` extending `KnowledgeSourceAdapter`
2. Add `KnowledgeSource.NEW_SOURCE = "new_source"` to `models.py`
3. Update `adapters/__init__.py` to export new adapter
4. Add to `ADAPTER_CLASSES` dict in `central_lookup.py`
5. Create unit tests in `tests/unit/test_adapters/`
6. Update documentation in `docs/adapters/`

## Common Patterns
- **Concept Creation**: Use `self._create_concept(id, label, type)` helper
- **Type Detection**: Override `_determine_concept_type()` for source-specific logic
- **Session Management**: Use `await self._get_session()` for HTTP requests
- **Confidence Scoring**: Set `concept.confidence_score` based on source reliability
- **Cross-references**: Add via `concept.add_identifier(source, id, label, url)`

## Quality Assurance
- Run tests before commits: `poetry run pytest -m "unit"`
- Check code style: `poetry run black . && poetry run ruff check .`
- Type checking: `poetry run mypy src/`
- Integration tests: `poetry run pytest -m "integration"`

## Deployment
- **PyPI**: Configured via `pyproject.toml` with Poetry
- **CLI Entry Point**: `knowledge-lookup` command via `scripts` in `pyproject.toml`
- **Dependencies**: Managed by Poetry, includes optional groups for docs/dev

## Example Usage Patterns
```python
# Basic search
lookup = CentralKnowledgeLookup()
results = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.BIOPORTAL])

# Multi-source annotation
annotator = MultiSourceAnnotator()
annotations = await annotator.annotate_text("Type 2 diabetes", confidence_threshold=0.7)

# RDF export
rdf_graph = lookup.export_to_rdf(results)
```
