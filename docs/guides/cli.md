---
description: Search sources, run the agent workflow, inspect the installation and benchmark adapters with the knowledge-lookup command.
---

# Command-line interface

Installing the package adds the `knowledge-lookup` command (also available as `python -m knowledge_lookup`). The separate `knowledge-lookup-mcp` command starts the [MCP server](mcp-server.md).

```bash
knowledge-lookup --help
```

| Command | Purpose |
| --- | --- |
| `search` | Search knowledge sources and print a table, JSON or CSV |
| `workflow` | Run the LangGraph [agent workflow](agent-workflow.md) with review and approval |
| `sources` | List all 36 sources with their requirements and whether they are available |
| `info` | Show the version and how many sources are available |
| `benchmark` | Run latency and resilience benchmarks against live sources |
| `explore` | Start a local web UI for browsing UMLS |

## `search`

```bash
knowledge-lookup search "seizure" --source HPO --source MONDO --limit 10
knowledge-lookup search "BRCA1" -s HGNC -s UNIPROT --output json
knowledge-lookup search "diabetes mellitus" -s OLS -o csv > diabetes.csv
```

| Option | Default | Description |
| --- | --- | --- |
| `QUERY` | required | Search text |
| `--source`, `-s` | all available | Source name, case-insensitive (`HPO`, `mondo`, ...). Repeat for several sources. |
| `--limit`, `-l` | `10` | Maximum number of results in total, split across the selected sources (passed to `search_concepts(max_results=...)`) |
| `--output`, `-o` | `table` | `table`, `json` or `csv` |
| `--partial`, `-p` | off | Partial (fuzzy) matching in the UMLS adapter. Applies when UMLS is selected or no source is given, and then returns UMLS results only. |
| `--cache-dir` | none | Directory for an on-disk cache, set up with `init_cache(disk_cache_dir=...)` before the search; without it the cache is in memory only. Only adapters that use the shared cache store entries there (currently UniChem); most searches are not cached. |

{% hint style="info" %}
Without `--source`, every available adapter is initialised and queried, which can take a long time. Name the sources you need.
{% endhint %}

The `table` output shows ID, name, source, type and a shortened description. `json` output looks like this, where `sources` lists the sources that were queried:

```json
{
  "query": "seizure",
  "sources": ["HPO"],
  "total_results": 3,
  "results": [
    {
      "id": "HP:0001250",
      "name": "Seizure",
      "description": "A seizure is an intermittent abnormality of nervous system physiology ...",
      "source": "HPO",
      "type": "PHENOTYPE",
      "uri": null,
      "score": 0.95
    }
  ]
}
```

`csv` output has the columns `ID`, `Name`, `Description`, `Source`, `Type`, `URI` and `Score`. An unknown source name exits with status 1 and lists the valid names.

## `workflow`

Requires the `agents` extra.

```bash
knowledge-lookup workflow "diabetes" --source OLS --source UMLS
knowledge-lookup workflow "BRCA1, BRCA2, TP53" --limit 10 --auto-approve 0.7
knowledge-lookup workflow "seizure" -s HPO --format json --format csv --export-path results/
```

| Option | Default | Description |
| --- | --- | --- |
| `QUERY` | required | Search text; separate several terms with commas |
| `--source`, `-s` | all available | Sources for term expansion and the main lookup (repeatable) |
| `--limit`, `-l` | `20` | Maximum results per search term; also the number of concepts kept after filtering |
| `--format`, `-f` | `json` | Export formats: `json`, `csv`, `ttl` (repeatable) |
| `--export-path`, `-e` | system temp directory | Directory for exported files |
| `--max-iter` | `3` | Maximum lookup passes (initial search plus refinements) |
| `--auto-approve` | `0.8` | Review score at or above which results are exported without asking |
| `--type`, `-t` | none | Concept types to keep, e.g. `DISEASE` (repeatable) |

The command prints the review score, a concept map (term, UMLS CUI, ontology IDs, type), strengths, weaknesses and suggestions. If the score is below `--auto-approve`, the workflow pauses and asks `Do you approve these results?`:

* **Yes** exports the results.
* **No** asks whether to refine the search. Refining takes optional notes, searches again and can ask again, up to `--max-iter` lookup passes. Declining stops without exporting.

When standard input is closed or not interactive (for example in a script or CI job) and the workflow pauses, the command stops without exporting and exits with status 1. Pass `--auto-approve 0` to export without asking. At the end the command prints the export paths and the executed steps. With one or two sources, a run usually takes well under a minute; see [Agent workflow](agent-workflow.md) for what each step does and its time limits.

## `sources`

```bash
knowledge-lookup sources
```

Prints a table of all 36 sources that have an adapter, with a description, what the source requires (an API key environment variable or an optional extra, `-` for nothing) and whether it is available in the current environment, followed by `<n>/36 sources available in this environment`. The same catalog backs the MCP server's `biomed_list_sources` tool; see [Knowledge source adapters](../adapters/README.md) for details on each adapter.

## `info`

```bash
knowledge-lookup info
```

Prints the version, description, repository URL and `Available sources: <n>/36`, where `<n>` is the number of adapters that initialised with your extras and API keys.

## `benchmark`

```bash
knowledge-lookup benchmark --quick
knowledge-lookup benchmark --output benchmark.json
```

Runs benchmarks against live APIs: single-source latency, parallel versus sequential speedup, circuit-breaker isolation, concurrent load and the multi-source annotator. `--quick` (`-q`) runs only the single-source and parallel-speedup benchmarks; `--output` (`-o`) saves the results as JSON.

## `explore`

```bash
knowledge-lookup explore --port 8080 --no-browser
```

Starts a small web server on `127.0.0.1` (default port `8080`, `--port`/`-p` to change) with a search page and a code crosswalk page for UMLS. It opens your browser unless you pass `--no-browser`. Press Ctrl+C to stop.

The server also exposes JSON endpoints:

| Endpoint | Parameters |
| --- | --- |
| `GET /api/search` | `query`, `limit` (default 10), `sabs` (optional UMLS source vocabulary) |
| `GET /api/crosswalk` | `source`, `code`, `target_source` (optional) |
| `GET /api/health` | none |

The UMLS endpoints need the `umls` extra and `UMLS_API_KEY`; otherwise they return HTTP 503.

## Next steps

* [Searching concepts](searching-concepts.md): the Python API behind `search`
* [Agent workflow](agent-workflow.md)
* [MCP server](mcp-server.md)
