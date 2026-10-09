---
description: Step-by-step guide to adding a knowledge source - the adapter contract, a skeleton, live verification, tests that pass on Windows and macOS, and the docs.
---

# Writing an adapter

An adapter connects one knowledge source to the common `UnifiedConcept` model. This guide walks from "I found an API" to a merged pull request. The [architecture](../reference/architecture.md) page explains how adapters fit into the library; [Contributing](README.md) covers the general workflow.

## 1. Check the source first

Do this before writing code. Four batches of new sources taught us that documented APIs drift:

* **Call it live.** Endpoints get retired (the GWAS Catalog legacy API, Unpaywall's title search, the eQTL Catalogue REST API all answered HTTP 410 or 404 while their documentation still described them), parameters are ignored (PRIDE ignores `keyword`), and some answer HTTP 200 with an error inside. Save a few trimmed real responses as test fixtures.
* **Read the terms.** Note the licence, any non-commercial clause, rate limits, and whether a key or contact e-mail is required. They go in the class docstring and the docs page.
* **Decide the access model.**
  * A query API: preferred.
  * A bulk file only: make it **opt-in**. `is_available()` is true only when the data is cached, a local path variable is set, or `downloads_allowed("<NAME>_DOWNLOAD")` (see `utils/dataset_cache.py` and `hpoa_adapter.py`). Never download by default, and never from plain HTTP or a bare IP.
  * A free key or account: implement it credential-gated and test with mocks.
* **Privacy.** Never put the user's name or e-mail in a request. Contact parameters (`mailto`, `email`) come only from an optional environment variable and are omitted when it is unset.

## 2. The contract

Subclass `KnowledgeSourceAdapter` (`knowledge_lookup/base.py`). All methods are `async`.

| Method | Required | Rules |
|---|---|---|
| `get_source()` | yes | returns the `KnowledgeSource` member |
| `is_available()` | override if needed | true unless a key, file or opt-in is missing; read keys with `config.get_api_key("<name>") or os.getenv("<ENV>")` |
| `search_concepts(query, limit=20)` | yes | respects `limit`, de-duplicates, returns `[]` on any failure |
| `get_concept_details(concept_id)` | yes | accepts the identifier forms the source uses (CURIE and bare); returns `None` when not found |
| `get_relationships(concept_id)` | where the source has links | dicts with `relation_label`, `related_id`, `related_name`, `source`, plus optional extras (`score`, `evidence`, counts). Use typed predicates, not `related_to` |
| `get_mappings(concept_id)` | where the source has cross-references | dicts with `fromId`, `toId`, `fromSource`, `toSource`, `mappingType`, `confidence` |

**Interface methods never raise.** Validate and normalise the id first, catch everything, log, and return `[]` or `None`. Use `self._make_request(url, params, headers, json_data)` for JSON and `self._make_request_text(...)` for text; both retry by error category and report to the circuit breaker. For a slow upstream set `min_request_timeout = 60.0` on the class. For XML use the standard library's `xml.etree`.

Build concepts with `self._create_concept(id, label, ConceptType.X)`, then fill what the source offers: `definitions`, `synonyms`, `parents`, `children`, `categories`, extra identifiers with `concept.add_identifier(...)`, and the raw upstream record in `concept.source_data[KnowledgeSource.X]`. Pick the best-fitting `ConceptType`.

### Skeleton

```python
"""Example adapter - one paragraph on what the source is, its licence and rate limits."""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.example.org/v1"


class ExampleAdapter(KnowledgeSourceAdapter):
    """Adapter for Example (https://example.org). Licence: CC BY 4.0."""

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.EXAMPLE

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            data = await self._make_request(f"{BASE_URL}/search", params={"q": query, "n": limit})
            return [c for item in data.get("results", [])[:limit] if (c := self._to_concept(item))]
        except Exception as e:
            logger.error(f"Example search_concepts failed: {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        try:
            data = await self._make_request(f"{BASE_URL}/records/{concept_id.removeprefix('EX:')}")
            return self._to_concept(data)
        except Exception as e:
            logger.error(f"Example get_concept_details failed: {e}")
            return None

    def _to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        if not item.get("id") or not item.get("name"):
            return None
        concept = self._create_concept(f"EX:{item['id']}", item["name"], ConceptType.DISEASE)
        concept.synonyms = list(item.get("synonyms", []))
        concept.source_data[KnowledgeSource.EXAMPLE] = item
        return concept
```

## 3. Register it

1. **Enum.** Add the member to `KnowledgeSource` in `linkml/biomedical_knowledge_schema.yaml` and to the generated `models/biomedical_knowledge_models.py` (see `linkml/Makefile`).
2. **Spec.** Add `KnowledgeSource.EXAMPLE: ("example_adapter", "ExampleAdapter")` to `_ADAPTER_SPECS` in `adapters/__init__.py`. That feeds the lazy `ADAPTER_CLASSES` and the package attributes.
3. **Lazy imports.** No module-level imports of heavy or optional client libraries; `import knowledge_lookup` must never import adapters or touch the network. `tests/unit/test_lazy_imports.py` enforces this.
4. **MCP catalog.** Add the source to `SOURCE_CATALOG` and `SourceName` in `mcp_server/sources.py`; a test checks both cover every adapter.
5. **Smoke-test query.** Add a default query to `_CHECK_QUERIES` in `__main__.py` if "BRCA1" does not suit the source, and `_CHECK_CREDENTIALS` if it needs a key or opt-in.
6. **Environment variables.** Add new variables to [Environment variables](../reference/environment-variables.md); `tests/unit/test_docs_index.py` fails otherwise. Add them to `.env.example` too.

## 4. Verify it live

```bash
poetry run knowledge-lookup check EXAMPLE            # search -> details -> relationships against the real API
poetry run knowledge-lookup check EXAMPLE --id EX:123
```

Keep requests courteous (at most about 2 per second, nothing bulk) while developing. Record measured latency and response sizes for the docs.

## 5. Tests

Put them in `tests/unit/test_example_adapter.py` with fixtures in their own module (`tests/fixtures/example_responses.py`; do not edit `mock_responses.py`). Mark them `@pytest.mark.unit`. Cover search, details, relationships, mappings, id normalisation, empty and error responses, `limit`, `is_available` and throttling, and aim for at least 95 % line coverage of the module.

Tests must pass on Windows and macOS, which run only after merge to `main`:

* Never assert a delay with an exact boundary (`delay <= 0.55`). Clocks are coarse and floats drift: use `<= x + 1e-6`, or assert on ordering and calls, and patch `asyncio.sleep` and `time.monotonic` when testing throttling.
* Pass `encoding="utf-8"` to every `read_text`, `write_text` and `open` that touches non-ASCII data (the Windows default is cp1252); use `newline=""` for CSV.
* Use `tmp_path`; no `/tmp`, no POSIX-only paths, no reliance on file mode bits.
* Do not depend on the wall clock.

`chembl_webresource_client` and `bioservices` are mocked in `tests/conftest.py`; keep it that way.

## 6. Document it

Create `docs/adapters/<folder>/example_adapter.md`, following [HGNC](../adapters/proteins/hgnc_adapter.md):

* front-matter `description:` and an info table with `Source`, `Class`, `Requires`, `Identifiers`, `Upstream API`;
* a quick example with **real output**;
* what each method returns, accepted identifier forms, rate limits and licence;
* a "Live verification (date)" section with measured latency and sizes.

Then add the source to a domain in `scripts/_source_taxonomy.py` and run:

```bash
poetry run python scripts/build_source_index.py
```

This regenerates the sidebar, the adapter index and the README tables. Refresh [What each source returns](../guides/data-coverage.md) with `scripts/harvest_source_samples.py --only EXAMPLE` when you can.

## 7. Before you open the pull request

```bash
poetry run pre-commit run --all-files                      # ruff format + lint, mypy
poetry run pytest tests/unit/test_all_adapters.py tests/unit/test_example_adapter.py \
    tests/unit/test_lazy_imports.py tests/unit/test_mcp_server.py tests/unit/test_docs_index.py
poetry run knowledge-lookup check EXAMPLE
```

A checklist for the description: live-verified (with the `check` result), test count and coverage, licence and terms noted, opt-in or key handling, any privacy implication (does the source store what you send?), and known limitations.
