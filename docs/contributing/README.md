---
description: Set up a development environment, run tests and linters, and contribute code or documentation.
---

# Contributing

Contributions of code, adapters and documentation are welcome. This page summarises the workflow; the authoritative guides live in the repository:

* [CONTRIBUTING.md](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/CONTRIBUTING.md): pull requests, commit messages and the release pipeline
* [TESTING.md](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/TESTING.md): test layout, fixtures and coverage
* [AGENTS.md](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/AGENTS.md): a compact overview of conventions and gotchas

## Set up a development environment

The project uses [Poetry](https://python-poetry.org/) and Python 3.11 or newer.

```bash
git clone https://github.com/<your-username>/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
poetry install --all-extras
poetry run pre-commit install
git checkout -b feature/your-feature
```

Put API keys for the sources you work on in your environment or a `.env` file; see [Configuration](../getting-started/configuration.md).

## Run the tests

```bash
poetry run pytest                          # full suite
poetry run pytest -m "not slow"            # skip slow and network-heavy tests
poetry run pytest -m unit                  # unit tests only
poetry run pytest tests/unit/test_mcp_server.py
poetry run pytest --cov=knowledge_lookup --cov-report=term-missing
```

Available markers: `unit`, `integration`, `functional` (live adapter tests), `network`, `api` (needs API keys) and `slow`. Unit tests mock HTTP responses; shared fixtures are in `tests/conftest.py` and `tests/fixtures/`.

## Lint and type-check

```bash
poetry run pre-commit run --all-files
```

The hooks run Ruff (lint and format, line length 99), mypy and basic file checks (trailing whitespace, end of file, YAML, large files).

## Submit a change

1. Keep changes focused and add or update tests.
2. Add an entry to `CHANGELOG.md` under `## [Unreleased]`.
3. Use conventional commit prefixes such as `feat:`, `fix:`, `docs:`, `test:` or `refactor:`.
4. Open a pull request against the `staging` branch. After CI passes there, changes are promoted to `main` and released; CONTRIBUTING.md describes the pipeline.

## Add a knowledge source

The steps (adapter class, `KnowledgeSource` enum, registry, MCP source catalog, tests and docs) are listed in [Architecture](../reference/architecture.md). Existing adapters in `src/knowledge_lookup/adapters/` are the best templates.

## Improve the documentation

The documentation is a [GitBook](https://www.gitbook.com/) site built from the `docs/` directory; the navigation is defined in `docs/SUMMARY.md`.

| Folder | Contents |
| --- | --- |
| `docs/getting-started/` | Installation, quickstart, configuration |
| `docs/guides/` | Task-oriented guides |
| `docs/reference/` | API reference and architecture |
| `docs/adapters/` | One page per knowledge source |
| `docs/examples/` | Scripts, notebooks and use cases |
| `docs/contributing/` | This page |

Conventions:

* Start every page with a single `# Title`, optionally preceded by YAML front matter with a `description:`.
* Name folder landing pages `README.md` and add new pages to `docs/SUMMARY.md`.
* Use relative links between pages (`../guides/caching.md`) and GitHub URLs for files outside `docs/`.
* Verify every API name, parameter and default against `src/knowledge_lookup/`.
* Make code examples runnable: scripts use `asyncio.run(main())` and close the lookup in a `finally` block. Label notebook-only snippets that use top-level `await`.
* Run the examples you add, and use GitBook blocks (`{% hint %}`, `{% tabs %}`, `{% code %}`) only where they help.

## Get help

Open an issue on [GitHub](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/issues) for bugs, questions and feature requests.
