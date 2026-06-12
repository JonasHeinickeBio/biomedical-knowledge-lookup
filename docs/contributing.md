# Contributing Guide

Thank you for your interest in contributing to Biomedical Knowledge Lookup! This guide will help you get started.

## Getting Started

### 1. Fork the Repository

1. Visit https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup
2. Click "Fork" in the top-right corner
3. Clone your fork locally:
```bash
git clone https://github.com/YOUR_USERNAME/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
```

### 2. Set Up Development Environment

```bash
# Install Poetry if not already installed
pip install poetry

# Install dependencies
poetry install --with dev

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Branch

```bash
# Create a new branch for your changes
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

## Development Workflow

### Coding Standards

1. **Code Style**: Follow PEP 8 guidelines
2. **Type Hints**: Use type hints for all function signatures
3. **Documentation**: Document all public functions
4. **Testing**: Write tests for all new code

### Type Hints Example

```python
from typing import List, Optional
from knowledge_lookup.models import UnifiedConcept

async def search_concepts(
    query: str,
    sources: List[str],
    limit: int = 10
) -> Optional[List[UnifiedConcept]]:
    """Search for concepts across multiple sources."""
    # implementation
```

### Documentation Requirements

- Document all public classes, methods, and functions
- Include type hints for all parameters and return values
- Add docstring examples where helpful
- Update README.md if adding new features

### Testing Requirements

1. Write unit tests for new functionality
2. Update existing tests if modifying code
3. Run tests before committing:
```bash
poetry run pytest
poetry run pytest --cov=knowledge_lookup
```

## Submitting Changes

### 1. Run Pre-commit Checks

```bash
pre-commit run --all-files
```

This will automatically:
- Format code with ruff
- Lint with ruff
- Run type checking with mypy

### 2. Commit Your Changes

```bash
git add .
git commit -m "feat: add new adapter for SourceX"
```

Commit message format:
- `feat: Add new feature`
- `fix: Fix bug in adapter`
- `docs: Update documentation`
- `test: Add tests for X`
- `chore: Update dependencies`

### 3. Push Your Branch

```bash
git push origin feature/your-feature-name
```

### 4. Open a Pull Request

1. Visit your fork on GitHub
2. Click "Compare & pull request"
3. Fill in the PR template with:
   - Description of changes
   - Related issues (if any)
   - Testing steps
   - Any breaking changes

## Adding New Adapters

To add a new knowledge source adapter:

### 1. Create the Adapter File

Create `src/knowledge_lookup/adapters/newsource_adapter.py`:

```python
from src.knowledge_lookup.adapters.base import KnowledgeSourceAdapter
from src.knowledge_lookup.models import LookupConfig, UnifiedConcept

class NewSourceAdapter(KnowledgeSourceAdapter):
    """Adapter for NewSource knowledge source."""
    
    def __init__(self, config: LookupConfig):
        super().__init__(config)
    
    @staticmethod
    def get_source() -> str:
        return "NewSource"
    
    async def search_concepts(self, query: str, limit: int = 10) -> List[UnifiedConcept]:
        # Implementation
        pass
    
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        # Implementation
        pass
```

### 2. Register the Adapter

Add to `src/knowledge_lookup/models.py`:

```python
class KnowledgeSource(Enum):
    # ... existing sources ...
    NEWSOURCE = "NewSource"
```

Add to `src/knowledge_lookup/adapters/__init__.py`:

```python
from .newsource_adapter import NewSourceAdapter

ADAPTER_CLASSES = {
    # ... existing adapters ...
    KnowledgeSource.NEWSOURCE: NewSourceAdapter,
}
```

### 3. Update Documentation

Create `docs/adapters/newsource_adapter.md`:
- Overview and purpose
- API information
- Data structures
- Usage examples
- Rate limiting details

### 4. Add Tests

Create `tests/unit/test_newsource_adapter.py`:
- Test successful search
- Test error handling
- Test rate limiting
- Test authentication

### 5. Run Tests

```bash
poetry run pytest tests/unit/test_newsource_adapter.py
```

## Documentation Contributions

### Updating Existing Documentation

1. Edit Markdown files in `docs/`
2. Test links work: `markdown-link-check docs/**/*.md`
3. Preview changes if using a markdown previewer

### Adding New Documentation

1. Create new Markdown file in appropriate `docs/` subdirectory
2. Follow existing documentation style
3. Include code examples where applicable
4. Add to navigation if needed

## Release Process

### For Maintainers

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create and push tag:
```bash
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
```

4. Publish to PyPI:
```bash
poetry build
poetry publish
```

## Questions?

- Open an issue for questions
- Join our Discord community (link)
- Email: jonas.heinicke@helmholtz-hzi.de

Thank you for contributing!
