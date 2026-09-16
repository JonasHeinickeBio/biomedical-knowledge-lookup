---
description: Install the core package, add the optional extras you need, and check that everything works.
---

# Installation

## Requirements

* Python **3.11 or newer** (CI tests 3.11, 3.12 and 3.13)
* Network access to the public APIs you want to query
* API keys only for the few sources that need them; see [Configuration](configuration.md)

The core install pulls in only lightweight dependencies: `aiohttp`, `pydantic`, `rdflib`, `backoff`, `python-dotenv`, `rich` and `typer`.

## Install the package

{% tabs %}
{% tab title="pip" %}
```bash
pip install biomedical-knowledge-lookup
```
{% endtab %}

{% tab title="uv" %}
```bash
uv add biomedical-knowledge-lookup
```
{% endtab %}

{% tab title="Poetry" %}
```bash
poetry add biomedical-knowledge-lookup
```
{% endtab %}
{% endtabs %}

The distribution is called `biomedical-knowledge-lookup`; the import name is `knowledge_lookup`.

## Optional extras

| Extra | Installs | Enables |
| --- | --- | --- |
| `export` | `pandas`, `openpyxl` | `export_to_dataframe()` and `export_to_excel()` |
| `chembl` | `chembl-webresource-client` | ChEMBL adapter |
| `bioservices` | `bioservices` | EUtils, QuickGO and UniChem adapters |
| `tyto` | `tyto` | Tyto adapter |
| `umls` | `umls-python-client` | UMLS adapter and UMLS-based abbreviation discovery in [term expansion](../guides/term-expansion.md) (needs `UMLS_API_KEY`) |
| `curie` | `bioregistry`, `curies` | [CURIE management](../guides/curie-management.md) utilities and offline CURIE validation in the MCP server |
| `agents` | `langgraph` | [Agent workflow](../guides/agent-workflow.md) (`knowledge_lookup.agents`, `knowledge-lookup workflow`) |
| `mcp` | `mcp` | [MCP server](../guides/mcp-server.md) (`knowledge-lookup-mcp`) |
| `all` | all of the above | Everything |

```bash
pip install "biomedical-knowledge-lookup[curie,umls]"
pip install "biomedical-knowledge-lookup[all]"
```

{% hint style="info" %}
Missing extras never break `import knowledge_lookup`. The ChEMBL and UMLS adapters are only registered when their extra is installed, and other adapters whose client library is missing are skipped (with a log message) when `CentralKnowledgeLookup` starts. Importing `knowledge_lookup.agents` or running `knowledge-lookup-mcp` without its extra raises an error that names the extra to install.
{% endhint %}

## Install from source

For development, clone the repository and install with [Poetry](https://python-poetry.org/):

```bash
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
poetry install --all-extras
poetry run pre-commit install
```

See [Contributing](../contributing/README.md) for the test and lint workflow.

## Verify the installation

The `info` command prints the version and how many sources could be initialised:

```bash
knowledge-lookup info
```

```
Biomedical Knowledge Lookup
Version: <installed version>
Description: Unified biological concept lookup across multiple knowledge sources
Repository: https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup
Available sources: <n>/40
```

`<n>` is the number of adapters that started successfully, which depends on the extras and API keys you have. The denominator counts every `KnowledgeSource` enum member; 36 of the 40 members have an adapter.

From Python:

```python
from knowledge_lookup import ADAPTER_CLASSES

print(f"{len(ADAPTER_CLASSES)} adapters registered")  # 36 with the chembl and umls extras
```

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'knowledge_lookup'` | The package is installed in a different environment. Check with `python -m pip show biomedical-knowledge-lookup` using the same interpreter. |
| A source is missing from `lookup.get_available_sources()` | Its extra or API key is missing. The log shows `<SOURCE> adapter not available` or `Failed to initialize <SOURCE> adapter`. See [Configuration](configuration.md). |
| `ImportError: The agent workflow requires the 'agents' extra` | Install `biomedical-knowledge-lookup[agents]`. |
| `knowledge-lookup-mcp` exits with `The MCP server needs the optional 'mcp' extra` | Install `biomedical-knowledge-lookup[mcp]`. |
| `ValidationError: ... Extra inputs are not permitted` when creating `LookupConfig` | `LookupConfig` rejects unknown fields (for example `cache_enabled`). See [Configuration](configuration.md) for the supported fields. |

## Next steps

* [Quickstart](quickstart.md): run your first search
* [Configuration](configuration.md): API keys, timeouts and source selection
