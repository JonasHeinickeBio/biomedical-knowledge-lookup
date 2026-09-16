# Biomedical Knowledge Lookup

**One async Python API for 36 biomedical knowledge sources** (ontologies, clinical terminologies,
and gene, protein, chemical, pathway and disease databases). Results come back as deduplicated,
cross-referenced concepts you can export, load into a knowledge graph or hand to an AI agent.

[![PyPI](https://img.shields.io/pypi/v/biomedical-knowledge-lookup)](https://pypi.org/project/biomedical-knowledge-lookup/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![CI](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/actions/workflows/ci.yml/badge.svg)](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Highlights

- **One API, 36 sources.** `search_concepts` queries OLS, UMLS, BioPortal, MONDO, HPO, UniProt,
  ChEMBL, Reactome and many more in parallel. It merges the hits into deduplicated,
  confidence-ranked `UnifiedConcept` records with IDs, labels, synonyms, definitions and
  cross-references.
- **Identifier-aware.** Fetch a concept by CURIE and collect cross-references with
  `find_mappings` (the concept's own identifiers plus EBI OxO). You can also validate and
  normalize CURIEs and URIs against [bioregistry](https://bioregistry.io/) (`[curie]` extra).
- **Term expansion.** `search_concepts_expanded` follows synonyms and long forms over several
  rounds ("COPD" → "chronic obstructive pulmonary disease"). Every term it tries is recorded in
  a local SQLite store.
- **Multi-source annotation.** `MultiSourceAnnotator` compares what several sources return for
  the same text and scores how far they agree.
- **Exports.** JSON, CSV, RDF/Turtle, a plain-text summary report, pandas DataFrame and Excel.
- **Resilient by default.** The library uses per-source timeouts, retries with exponential
  backoff, circuit breakers with per-source health tracking, and in-memory plus optional on-disk
  caching. Sources that lack an API key or optional extra are skipped rather than failing.
- **Agent workflow.** An optional LangGraph pipeline (`[agents]` extra) searches, filters,
  enriches and LLM-reviews results, then pauses for human approval before exporting.
- **MCP server.** `knowledge-lookup-mcp` (`[mcp]` extra) gives Claude, Cursor and other MCP
  clients read-only tools to search concepts, resolve identifiers, find mappings and validate
  CURIEs.
- **Lean core.** The base install needs only aiohttp, pydantic, rdflib, rich, typer, backoff
  and python-dotenv. Heavier dependencies are opt-in extras.

## Installation

```bash
pip install biomedical-knowledge-lookup                 # core: every HTTP-only adapter
pip install "biomedical-knowledge-lookup[curie,export]" # add extras as needed
pip install "biomedical-knowledge-lookup[all]"          # everything
```

Requires Python 3.11 or newer. Coming from 1.x? Read [Upgrading to 2.0](docs/getting-started/upgrading-to-2.0.md)
for the breaking changes.

| Extra | Enables | Installs |
|-------|---------|----------|
| `curie` | CURIE/URI validation and normalization (`knowledge_lookup.curie_utils`) | bioregistry, curies |
| `umls` | UMLS adapter and UMLS-backed abbreviation expansion | umls-python-client |
| `chembl` | ChEMBL adapter | chembl-webresource-client |
| `bioservices` | NCBI E-utilities, QuickGO and UniChem adapters | bioservices |
| `tyto` | Tyto adapter | tyto |
| `export` | `export_to_dataframe()` and `export_to_excel()` | pandas 3, openpyxl |
| `agents` | LangGraph agent workflow (`knowledge_lookup.agents`, `knowledge-lookup workflow`) | langgraph |
| `mcp` | MCP server for AI agents (`knowledge-lookup-mcp`) | mcp |
| `all` | All of the above | |

Every optional dependency guards its own import. `import knowledge_lookup` always works, and a
feature whose extra is missing is simply unavailable.

## Quick start

### Search concepts

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource


async def main() -> None:
    lookup = CentralKnowledgeLookup()
    try:
        result = await lookup.search_concepts(
            "type 2 diabetes",
            sources=[KnowledgeSource.OLS, KnowledgeSource.MONDO, KnowledgeSource.HPO],
            max_results=5,
        )
        for concept in result.concepts:
            print(concept.primary_id, concept.primary_label, concept.sources)
    finally:
        await lookup.close()


asyncio.run(main())
```

Leave out `sources` to query every available adapter.

### Concept details, mappings and exports

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig


async def main() -> None:
    # Initialise only the adapters you need. Start-up is faster, and calls that ask every
    # adapter (find_mappings, get_concept_details without a source) stay quick.
    config = LookupConfig(
        enabled_sources=[
            KnowledgeSource.OLS,
            KnowledgeSource.HPO,
            KnowledgeSource.MONDO,
            KnowledgeSource.OXO,
        ],
        timeout_per_source=20,
    )
    lookup = CentralKnowledgeLookup(config)
    try:
        seizure = await lookup.get_concept_details("HP:0001250", source=KnowledgeSource.HPO)
        print(seizure.primary_label, seizure.synonyms[:3])
        # e.g. Seizure ['Epileptic seizure', 'Seizures', 'Epilepsy']

        mappings = await lookup.find_mappings("MONDO:0005148")
        print([m.identifier for m in mappings[:3]])
        # e.g. ['DOID:9352', 'ICD10CM:E11', 'ICD10WHO:E11']

        result = await lookup.search_concepts("asthma", sources=[KnowledgeSource.OLS])
        lookup.export_to_json(result, "asthma.json")
        lookup.export_to_csv(result, "asthma.csv")
        lookup.export_to_ttl(result, "asthma.ttl")  # RDF / Turtle
        df = lookup.export_to_dataframe(result)  # needs the [export] extra
        print(df.shape)
    finally:
        await lookup.close()


asyncio.run(main())
```

### Term expansion and CURIE utilities

```python
# inside an async function, with `lookup` as above
result = await lookup.search_concepts_expanded(
    "COPD", sources=[KnowledgeSource.OLS], max_rounds=2
)
```

Expansion is slower than a single search because it runs one search per discovered term. With
the `[umls]` extra and a `UMLS_API_KEY` it also expands abbreviations through the UMLS
Metathesaurus.

```python
# needs the [curie] extra
from knowledge_lookup.curie_utils import normalize_curie, parse_curie_or_uri, validate_prefix

validate_prefix("mondo")                                         # True
normalize_curie("MONDO:0005148")                                 # 'mondo:0005148'
parse_curie_or_uri("http://purl.obolibrary.org/obo/HP_0001250")  # ('hp', '0001250')
```

### Command line

```bash
knowledge-lookup search "type 2 diabetes" --source OLS --limit 5
knowledge-lookup search "BRCA1" --source HGNC --output json   # table (default), json or csv
knowledge-lookup --help                                       # also: workflow, info, benchmark, explore
```

### MCP server for AI agents

Register the server with Claude Code in one line:

```bash
claude mcp add biomedical-knowledge-lookup -- uvx --from "biomedical-knowledge-lookup[mcp,curie]" knowledge-lookup-mcp
```

Or run it yourself:

```bash
pip install "biomedical-knowledge-lookup[mcp,curie]"
knowledge-lookup-mcp                                         # stdio (Claude Desktop, Cursor, ...)
knowledge-lookup-mcp --transport streamable-http --port 8000 # serves http://127.0.0.1:8000/mcp
```

The server has five read-only tools: `biomed_search_concepts`, `biomed_get_concept`,
`biomed_find_mappings`, `biomed_list_sources` and `biomed_validate_curie`. Pass API keys to it
as environment variables, for example with `claude mcp add ... -e UMLS_API_KEY=...`. See the
[MCP server guide](docs/guides/mcp-server.md) for configuration and client setup.

## Knowledge sources

36 adapters, grouped by domain. Pass the name as `KnowledgeSource.<NAME>` in Python or as
`--source <NAME>` on the CLI. A source marked **—** works without an API key or extra.

<details>
<summary><strong>Show all 36 sources and their requirements</strong></summary>

**Diseases and phenotypes**

| Name | Description | Requires |
|------|-------------|----------|
| `MONDO` | Mondo Disease Ontology, e.g. `MONDO:0005148` | — |
| `HPO` | Human Phenotype Ontology, e.g. `HP:0001250` | — |
| `OMIM` | OMIM Mendelian disorders and genes | `OMIM_API_KEY` |
| `DISGENET` | DisGeNET gene–disease associations | `DISGENET_API_KEY` |
| `OPENTARGETS` | Open Targets target–disease evidence | — |
| `CLINVAR` | ClinVar variants and clinical significance | — |
| `COSMIC` | COSMIC somatic cancer mutations | — (optional `COSMIC_API_KEY`) |

**Genes, proteins and structures**

| Name | Description | Requires |
|------|-------------|----------|
| `HGNC` | HGNC human gene nomenclature, e.g. `HGNC:1100` (BRCA1) | — |
| `UNIPROT` | UniProtKB proteins, e.g. `P38398` | — |
| `ENSEMBL` | Ensembl genes and transcripts, e.g. `ENSG00000012048` | — |
| `GENEONTOLOGY` | Gene Ontology terms, e.g. `GO:0008150` | — |
| `QUICKGO` | EBI QuickGO annotations | `[bioservices]` |
| `INTERPRO` | InterPro protein families and domains, e.g. `IPR000719` | — |
| `PFAM` | Pfam protein families, e.g. `PF00069` | — |
| `PDB` | RCSB Protein Data Bank structures | — |
| `STRING` | STRING protein–protein interactions | — |

**Chemicals and drugs**

| Name | Description | Requires |
|------|-------------|----------|
| `PUBCHEM` | PubChem compounds (CIDs) | — |
| `CHEMBL` | ChEMBL bioactive molecules and drugs, e.g. `CHEMBL25` | `[chembl]` |
| `DRUGBANK` | DrugBank drugs, e.g. `DB00945` | — |
| `UNICHEM` | UniChem chemical cross-references | `[bioservices]` |

**Pathways**

| Name | Description | Requires |
|------|-------------|----------|
| `REACTOME` | Reactome pathways, e.g. `R-HSA-1640170` | — |
| `KEGG` | KEGG diseases, drugs and pathways | — |

**Ontologies, terminologies and mappings**

| Name | Description | Requires |
|------|-------------|----------|
| `OLS` | EBI Ontology Lookup Service: 250+ ontologies (DOID, EFO, NCIT, UBERON, ChEBI, ...) | — |
| `EBIOLS` | EMBL-EBI OLS (variant of the OLS adapter) | — |
| `BIOPORTAL` | NCBO BioPortal: 1000+ ontologies (SNOMED CT, MeSH, ICD, ...) | `BIOPORTAL_API_KEY` |
| `BIOONTOLOGY` | NCBO BioOntology search API | `BIOPORTAL_API_KEY` |
| `UMLS` | UMLS Metathesaurus concepts (CUIs, e.g. `C0011849`) spanning SNOMED CT, MeSH, ICD, ... | `[umls]` + `UMLS_API_KEY` |
| `OXO` | EBI OxO ontology cross-reference mappings | — |
| `ZOOMA` | EBI ZOOMA text-to-ontology annotation | — |
| `OBOFOUNDRY` | OBO Foundry ontology registry | — |
| `TYTO` | Tyto ontology term lookup | `[tyto]` |

**Literature and general knowledge**

| Name | Description | Requires |
|------|-------------|----------|
| `EUROPEPMC` | Europe PMC literature | — |
| `EUTILS` | NCBI E-utilities (PubMed, Gene, MeSH) | `[bioservices]` |
| `WIKIDATA` | Wikidata items, e.g. `Q12136` | — |
| `DBPEDIA` | DBpedia resources (general knowledge) | — |
| `BIOLINKER` | BioLinker entity linking | — |

</details>

Per-source details are in the [adapter documentation](docs/adapters/README.md). The
[`example_notebooks/`](example_notebooks/) folder has a notebook for most adapters.

## Configuration

### API keys

Keys are optional. Set them as environment variables:

```bash
export BIOPORTAL_API_KEY=...   # BioPortal and BioOntology — https://bioportal.bioontology.org/
export UMLS_API_KEY=...        # UMLS and abbreviation expansion — https://uts.nlm.nih.gov/
export DISGENET_API_KEY=...    # DisGeNET — https://www.disgenet.com/
export OMIM_API_KEY=...        # OMIM — https://www.omim.org/api
```

Without a key, the matching source is reported as unavailable and skipped.

A `.env` file with the same variables is also read, but it is searched for upward from the
installed package, not from your script's working directory. That works in a source checkout
and in Jupyter or the REPL. For an installed package, export the variables or call
`dotenv.load_dotenv()` yourself before creating the lookup.

The agent workflow's LLM review uses `BLABLADOR_API_KEY`, `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY`, whichever is set first. With none of them set, it falls back to rule-based
review.

### `LookupConfig`

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

config = LookupConfig(
    enabled_sources=[KnowledgeSource.OLS, KnowledgeSource.MONDO, KnowledgeSource.BIOPORTAL],
    max_results_per_source=20,
    timeout_per_source=15,  # seconds
    circuit_breaker_threshold=5,  # failures before a source is skipped (default 5)
    circuit_breaker_cooldown=30,  # seconds before it is probed again (default 30)
    api_keys={"bioportal": "your-key"},  # instead of environment variables
)
lookup = CentralKnowledgeLookup(config)
```

See the [configuration guide](docs/getting-started/configuration.md) for every option, and the
[caching guide](docs/guides/caching.md) for the memory and disk caches.

## Documentation

| | |
|---|---|
| **Getting started** | [Installation](docs/getting-started/installation.md) · [Quick start](docs/getting-started/quickstart.md) · [Configuration](docs/getting-started/configuration.md) |
| **Guides** | [Searching concepts](docs/guides/searching-concepts.md) · [Term expansion](docs/guides/term-expansion.md) · [Multi-source annotation](docs/guides/multi-source-annotation.md) · [CURIE management](docs/guides/curie-management.md) · [Caching](docs/guides/caching.md) · [Exporting results](docs/guides/exporting-results.md) · [CLI](docs/guides/cli.md) · [Agent workflow](docs/guides/agent-workflow.md) · [MCP server](docs/guides/mcp-server.md) |
| **Reference** | [API reference](docs/reference/api-reference.md) · [Architecture](docs/reference/architecture.md) · [Knowledge-source adapters](docs/adapters/README.md) |
| **More** | [Examples](docs/examples/README.md) · [Example notebooks](example_notebooks/) · [Contributing](docs/contributing/README.md) · [Changelog](CHANGELOG.md) |

Start at the [documentation home](docs/README.md).

### Package layout

```text
src/knowledge_lookup/
├── core/          CentralKnowledgeLookup, term expansion, MultiSourceAnnotator
├── adapters/      one adapter per knowledge source (ADAPTER_CLASSES)
├── models/        Pydantic models generated from the LinkML schema in linkml/
├── curie_utils/   CURIE/URI parsing, validation and normalization   [curie]
├── cache/         in-memory and on-disk cache
├── export/        JSON and CSV export helpers
├── agents/        LangGraph agent workflow                          [agents]
├── mcp_server/    Model Context Protocol server                     [mcp]
└── __main__.py    knowledge-lookup CLI
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [TESTING.md](TESTING.md).

```bash
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
poetry install --all-extras      # library, every extra and the dev tools
poetry run pre-commit install    # ruff, ruff-format and mypy on every commit
poetry run pytest tests/unit     # unit tests
poetry run pytest -m "not slow"  # broader run; functional tests call live APIs
```

Report bugs and request features on
[GitHub Issues](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/issues).

## Citation

If you use this library in your research, please cite the repository:

```bibtex
@software{heinicke_biomedical_knowledge_lookup,
  author  = {Heinicke, Jonas},
  title   = {Biomedical Knowledge Lookup: unified concept lookup across biomedical knowledge sources},
  url     = {https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup},
  license = {MIT},
  year    = {2026}
}
```

## License

Released under the [MIT License](LICENSE).

## Acknowledgments

- Built as part of the AID-PAIS knowledge graph project.
- Thanks to the teams who build and maintain the knowledge sources this library connects to,
  and to everyone who has contributed.
