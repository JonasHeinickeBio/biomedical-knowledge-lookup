---
description: Expose the lookup library to Claude, Cursor, VS Code and other LLM agents through the Model Context Protocol.
---

# MCP server

`knowledge_lookup.mcp_server` exposes the lookup library to LLM agents over the
[Model Context Protocol](https://modelcontextprotocol.io). Any MCP client
(Claude Code, Claude Desktop, Cursor, VS Code, ...) can then search 36
biomedical ontologies and databases, resolve identifiers and cross-walk them
between vocabularies.

It is built on the official `mcp` Python SDK (2.x, `MCPServer`) and ships as the
optional `mcp` extra. Like the rest of the library it requires Python 3.11 or newer.

## Install and run

```bash
pip install "biomedical-knowledge-lookup[mcp,curie]"   # curie: offline CURIE validation
knowledge-lookup-mcp                                    # stdio transport (default)
```

Without installing, via [uv](https://docs.astral.sh/uv/):

```bash
uvx --from "biomedical-knowledge-lookup[mcp,curie]" knowledge-lookup-mcp
```

Serve over Streamable HTTP instead (endpoint `http://127.0.0.1:8000/mcp`):

```bash
knowledge-lookup-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

`python -m knowledge_lookup.mcp_server` is equivalent to `knowledge-lookup-mcp`.

### Claude Code

```bash
claude mcp add biomedical-knowledge-lookup \
  -e UMLS_API_KEY=... -e BIOPORTAL_API_KEY=... \
  -- uvx --from "biomedical-knowledge-lookup[mcp,curie,umls]" knowledge-lookup-mcp
```

### Claude Desktop / `.mcp.json`

```json
{
  "mcpServers": {
    "biomedical-knowledge-lookup": {
      "command": "uvx",
      "args": ["--from", "biomedical-knowledge-lookup[mcp,curie,umls]", "knowledge-lookup-mcp"],
      "env": {
        "UMLS_API_KEY": "your-umls-key",
        "BIOPORTAL_API_KEY": "your-bioportal-key"
      }
    }
  }
}
```

{% hint style="info" %}
API keys are optional: sources that need one are simply reported as unavailable
by `biomed_list_sources`. See [Configuration](../getting-started/configuration.md) for
the keys each source uses.
{% endhint %}

## Tools

All tools are read-only and annotated as such (`readOnlyHint`, `idempotentHint`,
not destructive). Every tool returns structured content with a published output
schema, plus the same JSON as text for clients that only read text.

| Tool | Purpose | Key parameters |
|------|---------|----------------|
| `biomed_search_concepts` | Free-text term -> ranked candidate concepts, merged and de-duplicated across sources | `query`, `sources`, `concept_types`, `limit` (1-50), `offset`, `expand_synonyms`, `response_format` |
| `biomed_get_concept` | Full record for one identifier: definitions, synonyms, type, xrefs, parents/children | `concept_id`, `source` (optional override), `response_format` |
| `biomed_find_mappings` | Cross-walk an identifier to other vocabularies (MeSH, NCIT, DOID, UMLS, ICD, ...) via the concept's xrefs and EBI OxO | `concept_id`, `target_prefixes`, `distance` (1-3), `limit` |
| `biomed_list_sources` | Every source with availability, default-search membership and what an unavailable source needs | — |
| `biomed_validate_curie` | Offline Bioregistry check: prefix registered? local ID matches pattern? canonical CURIE and IRI | `identifier` |

Typical agent workflow: `biomed_search_concepts` -> `biomed_get_concept` ->
`biomed_find_mappings`.

### Response design

- **`response_format`**: `concise` (default for search) returns id, label, type,
  sources, score, the first definition and a few synonyms; `detailed` adds all
  definitions, cross-references, semantic types and hierarchy. Empty fields are
  omitted.
- **Pagination**: search results carry `total`, `count`, `offset`, `has_more` and
  `next_offset`. Pages of the same query are served from a short-lived cache, so
  paging is consistent and does not re-query upstream APIs.
- **Size cap**: a page is trimmed to stay under 25,000 characters, with a warning
  explaining how to fetch the rest.
- **Partial failures**: a source that errors or times out is listed in
  `source_errors`; results from the other sources are still returned.
- **Actionable errors**: anticipated problems (unknown identifier, unavailable
  source, invalid arguments) come back as tool errors whose message says what to
  try next.
- **Identifiers**: OBO-style IDs are always shown as CURIEs (`MONDO:0005148`),
  even when a source reports `MONDO_0005148` or a term IRI, so they can be passed
  straight into the next tool call.

### Identifier routing

`biomed_get_concept` sends an identifier only to the source that owns it instead
of asking every adapter:

- CURIE prefixes route to their adapter (`HP:` -> HPO, `MONDO:` -> MONDO,
  `UniProtKB:` -> UniProt, `HGNC:` -> HGNC, ...), with the ID in the form that
  adapter expects.
- OBO-style CURIEs (`CHEBI:15365`, `DOID:9351`) and ontology IRIs resolve through
  OLS.
- Bare accessions are recognized by shape: `C0011849` (UMLS), `P38398` (UniProt),
  `ENSG00000012048` (Ensembl), `R-HSA-1640170` (Reactome), `CHEMBL25`, `DB00945`,
  `Q12136`, `IPR000719`, `PF00069`.
- Anything else falls back to an exact-ID search in OLS.

## Resources and prompts

| Kind | Name | Description |
|------|------|-------------|
| Resource | `biomed://sources` | Source catalog as JSON |
| Resource template | `biomed://concept/{concept_id}` | Detailed concept record, e.g. `biomed://concept/HP:0001250` |
| Prompt | `normalize_terms` | Map a list of terms to their best ontology identifiers (`terms`, `preferred_sources`) |
| Prompt | `annotate_text` | Extract biomedical entities from free text and ground them (`text`) |

## Configuration

Command-line flags override environment variables.

| Flag | Environment variable | Default |
|------|----------------------|---------|
| `--transport` | `KNOWLEDGE_LOOKUP_MCP_TRANSPORT` | `stdio` |
| `--host`, `--port` | — | `127.0.0.1`, `8000` |
| `--default-sources` | `KNOWLEDGE_LOOKUP_MCP_DEFAULT_SOURCES` | `OLS,MONDO,HPO,GENEONTOLOGY,HGNC,UNIPROT,PUBCHEM,REACTOME,UMLS,BIOPORTAL` (unavailable ones skipped) |
| `--enabled-sources` | `KNOWLEDGE_LOOKUP_MCP_ENABLED_SOURCES` | all adapters |
| `--timeout` | `KNOWLEDGE_LOOKUP_MCP_TIMEOUT` | `15` seconds per source |
| `--persist-expansions` | `KNOWLEDGE_LOOKUP_MCP_PERSIST_EXPANSIONS` | off |
| `--log-level` | `KNOWLEDGE_LOOKUP_MCP_LOG_LEVEL` | `WARNING` |

Source API keys use the library's usual variables (`UMLS_API_KEY`,
`BIOPORTAL_API_KEY`, `DISGENET_API_KEY`, `OMIM_API_KEY`, also read from `.env`).

`--persist-expansions` records synonym-expansion trails in the durable
`ExpansionStore` (`~/.cache/knowledge-lookup/expansion_history.db`; see
[Term expansion](term-expansion.md)). It is off by default so tool calls have no
side effects.

## Operational notes

- **stdio safety**: the server logs only to stderr; stdout carries the protocol.
- **Fast startup**: importing the library and initialising the adapters takes a
  few seconds, so this runs in a worker thread when the server starts. The
  protocol handshake is not blocked; the first tool call waits for it.
- **Blocking adapters are isolated**: ChEMBL, Tyto, EUtils, QuickGO and UniChem
  wrap synchronous client libraries. Each runs on its own event-loop
  thread, so a slow query cannot freeze the server and per-source timeouts still
  fire.
- **Speed**: naming `sources` explicitly is faster and more precise than the
  default set. `expand_synonyms=true` issues several rounds of searches and is
  noticeably slower.

## Development

```bash
poetry install --all-extras
poetry run pytest tests/unit/test_mcp_server.py          # in-memory client, no network
npx @modelcontextprotocol/inspector .venv/bin/knowledge-lookup-mcp   # interactive testing
```

Tests use the SDK's in-memory `mcp.Client` against `create_server(...)` with a
fake `CentralKnowledgeLookup` injected through `lookup_factory`. The server code
lives in `src/knowledge_lookup/mcp_server/` (`server.py` for tools and settings,
`sources.py` for the source catalog and identifier routing).

## Next steps

* [Knowledge source adapters](../adapters/README.md): what each source provides
* [Searching concepts](searching-concepts.md): the Python API behind the tools
* [Architecture](../reference/architecture.md)
