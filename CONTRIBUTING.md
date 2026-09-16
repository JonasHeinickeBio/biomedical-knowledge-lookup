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

The version number is **not** hand-edited anywhere — `pyproject.toml`'s
`version` is a placeholder (`0.0.0`) that `poetry-dynamic-versioning`
overwrites at build time from the nearest `vX.Y.Z` git tag. There is nothing
to bump manually; the pipeline below computes it for you.

### The pipeline: pull request → release pull request → draft release → publish

`main` is the only long-lived branch, and the "Protect Main" ruleset requires
a pull request for every change to it, including the CHANGELOG cut.

1. **Open a pull request into `main`** with a `CHANGELOG.md` entry under
   `## [Unreleased]`. The entries decide the next version: a line starting
   with `- **Breaking` means a major release, a `### Added` section a minor
   release, anything else a patch release. `.github/workflows/ci.yml` runs on
   the pull request: ruff and mypy, unit and integration tests on Python
   3.11–3.13, wheel packaging smoke tests, and the live-API functional tests.

2. **Merge it with your own account** (the merge button or `gh pr merge`).
   CI runs again on `main`, including unit tests on macOS and Windows.

   Don't leave merges to a workflow: events caused by a workflow's
   `GITHUB_TOKEN` (such as a bot-enabled auto-merge) never trigger other
   workflows, so nothing downstream would run. That is what broke the old
   `staging → main` promotion.

3. **`.github/workflows/release-draft.yml` opens the release pull request.**
   After each merge it cuts `[Unreleased]` into `## [X.Y.Z] - <date>` on the
   `release/next` branch (rebuilt from `main` every time) and opens or updates
   the pull request `chore(release): vX.Y.Z`. More merges before you release
   are added to it automatically. The pull request only changes
   `CHANGELOG.md`, and CI does not run on it.

4. **Merge the release pull request when you want to release.** The push to
   `main` runs the same workflow, which now finds no release for the newest
   CHANGELOG section and creates the **draft** release `vX.Y.Z` on that commit,
   with the section as its notes. Nothing is tagged or published yet. While
   the draft is unpublished, later merges only collect entries in
   `[Unreleased]`.

5. **Review and publish the draft** (Releases → the draft → *Publish
   release*). This is the manual checkpoint before PyPI: check the version
   number and the notes.

6. **`.github/workflows/publish.yml`** runs on the `vX.Y.Z` tag that
   publishing creates. It re-verifies, builds, generates Sigstore provenance
   attestations, uploads to PyPI with **Trusted Publishing (OIDC)** — no API
   tokens needed — and attaches the distributions to the release. The upload
   waits for the `pypi` environment's approval if you configured one.

To continue after publishing a draft without waiting for the next merge, run
the workflow by hand (Actions → Release → Run workflow).

A tag pushed by hand (`git tag vX.Y.Z && git push origin vX.Y.Z`) runs
`publish.yml` the same way. The release workflow is not involved then, so cut
the CHANGELOG yourself first.

### One-time repo setup this pipeline needs

- **Settings → Actions → General → Workflow permissions → "Allow GitHub
  Actions to create and approve pull requests"**, so the release workflow can
  open the release pull request.
- The `main` ruleset must not cover `release/next`; the workflow force-pushes
  that branch.
- **Strongly recommended:** Settings → Environments → `pypi` → add yourself
  (or the maintainer team) as a **required reviewer**. This is the current
  PyPA-recommended hardening for OIDC trusted publishing from Actions — it
  forces one explicit human approval on the actual PyPI upload step of
  `publish.yml`, on top of the draft-release review in step 5. Without it,
  step 5 (publishing the draft) is the *only* human checkpoint before PyPI.

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
