# Contributing to Biomedical Knowledge Lookup

Thank you for your interest in contributing to Biomedical Knowledge Lookup! This document provides guidelines and information for contributors.

## 🚀 Quick Start

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/biomedical-knowledge-lookup.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate the environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
5. Install dependencies: `poetry install`
6. Install pre-commit hooks: `poetry run pre-commit install`
7. Create a feature branch: `git checkout -b feature/your-feature-name`

## 🧪 Development Workflow

### Code Style

We use the following tools for code quality:

- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Run all checks with:
```bash
poetry run pre-commit run --all-files
```

### Testing

- Write tests for new features in `tests/unit/` or `tests/integration/`
- Run tests with: `poetry run pytest`
- Aim for >90% test coverage

### Adding New Adapters

To add support for a new knowledge source:

1. **Create the adapter** in `src/knowledge_lookup/adapters/`
   ```python
   from ..base import KnowledgeSourceAdapter
   from ..models import KnowledgeSource, UnifiedConcept

   class NewSourceAdapter(KnowledgeSourceAdapter):
       def get_source(self) -> KnowledgeSource:
           return KnowledgeSource.NEW_SOURCE

       async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
           # Implementation here
           pass
   ```

2. **Add to KnowledgeSource enum** in `src/knowledge_lookup/models.py`
   ```python
   class KnowledgeSource(Enum):
       # ... existing sources ...
       NEW_SOURCE = "new_source"
   ```

3. **Update adapters __init__.py**
   ```python
   from .new_source_adapter import NewSourceAdapter

   __all__ = [
       # ... existing adapters ...
       "NewSourceAdapter",
   ]
   ```

4. **Add tests** in `tests/unit/test_adapters/test_new_source_adapter.py`

5. **Update documentation** in `docs/adapters/`

## 📝 Commit Guidelines

- Use clear, descriptive commit messages
- Start with a verb: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Reference issues: `feat: add OLS adapter (#123)`

### Example Commit Messages

```
feat: add support for ChEMBL database
fix: handle rate limiting in BioPortal adapter
docs: update installation instructions
test: add integration tests for multi-source annotation
refactor: simplify cache implementation
```

## 🐛 Reporting Issues

- Use the GitHub issue tracker
- Provide a clear description of the problem
- Include steps to reproduce
- Add relevant error messages and stack traces
- Specify your environment (Python version, OS, etc.)

## 💡 Feature Requests

- Check existing issues first
- Provide a clear use case
- Describe the expected behavior
- Consider implementation complexity

## 📚 Documentation

- Update docstrings for new functions/classes
- Add examples for new features
- Update the README if needed
- Keep API documentation current

## 🔄 Pull Request Process

1. Ensure all tests pass
2. Update documentation
3. Add tests for new features
4. Ensure code style compliance
5. Write a clear PR description
6. Reference related issues

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Code refactoring

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Commit messages are clear
```

## 🎯 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn and contribute
- Maintain professional communication

## 📞 Getting Help

- **Issues**: For bugs and feature requests
- **Discussions**: For questions and general discussion
- **Email**: jonas.heinicke@helmholtz-hzi.de

## 📦 Release Process

### Creating a Release

1. **Update version** in `pyproject.toml` and commit:
   ```bash
   poetry version <major|minor|patch>
   git add pyproject.toml
   git commit -m "chore: bump version to $(poetry version --short)"
   ```

2. **Update CHANGELOG.md** with the new version and release date.

3. **Push and tag**:
   ```bash
   git push origin main
   git tag v$(poetry version --short)
   git push origin v$(poetry version --short)
   ```

4. **Automated publishing**:
   - The `publish.yml` workflow is triggered when a tag matching `v*` is pushed.
   - It builds the package, runs checks, generates Sigstore provenance attestations, and publishes to PyPI using **Trusted Publishing (OIDC)** — no API tokens needed.
   - A GitHub Release is automatically drafted with the distribution files attached.

### Manual TestPyPI Publishing

Trigger the publish workflow manually from GitHub Actions:
```
workflow_dispatch → environment: testpypi
```

### Setting Up Trusted Publisher (one-time)

Before the first automated release, configure a trusted publisher in PyPI:

| Field | Value |
|---|---|
| PyPI Project Name | `biomedical-knowledge-lookup` |
| Owner | `JonasHeinickeBio` |
| Repository name | `biomedical-knowledge-lookup` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` (optional but recommended) |

Go to: https://pypi.org/manage/account/publishing/ → "Add a new pending publisher"

### Package Signing

This project uses **Sigstore** for package signing via GitHub's `attest-build-provenance` action. Every published package includes a signed provenance attestation, ensuring supply chain security without managing GPG keys.

Thank you for contributing to Biomedical Knowledge Lookup! 🎉
