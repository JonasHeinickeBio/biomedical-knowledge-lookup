# Biomedical Knowledge Lookup

**Ask 106 biomedical sources one question; get one answer format back.** A single asynchronous
Python API, command line and MCP server over ontologies, clinical code systems (ICD, SNOMED CT,
LOINC, MeSH), gene, protein and drug databases, literature indexes, trial registries and omics
dataset repositories. Results are merged, deduplicated and cross-referenced, ready to export, load
into a knowledge graph or hand to an AI agent.

[![PyPI](https://img.shields.io/pypi/v/biomedical-knowledge-lookup)](https://pypi.org/project/biomedical-knowledge-lookup/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![CI](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/actions/workflows/ci.yml/badge.svg)](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[Documentation](docs/README.md) ·
[Which source for which question](docs/guides/choosing-sources.md) ·
[What each source returns](docs/guides/data-coverage.md) ·
[Quickstart](docs/getting-started/quickstart.md) ·
[Troubleshooting](docs/getting-started/troubleshooting.md)

## A first look

One phrase, four sources: a UMLS CUI, an ICD-10-CM code, an NCI Thesaurus concept and a MeSH
heading, from the live APIs.

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

SOURCES = [KnowledgeSource.MESH, KnowledgeSource.MEDGEN,
           KnowledgeSource.NCIEVS, KnowledgeSource.CLINICALTABLES]


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=SOURCES))
    try:
        result = await lookup.search_concepts("chronic fatigue syndrome", max_results=8)
        for concept in result.concepts:
            print(concept.primary_id, concept.primary_label, concept.sources)
    finally:
        await lookup.close()


asyncio.run(main())
```

```text
C0015674 Myalgic encephalomeyelitis/chronic fatigue syndrome ['MEDGEN']
ICD10CM:G93.32 Myalgic encephalomyelitis/chronic fatigue syndrome ['CLINICALTABLES']
CONDITIONS:12927 Chronic fatigue syndrome ['CLINICALTABLES', 'NCIEVS']
NCIT:C227796 Chronic Fatigue Syndrome Primary Factor Question ['NCIEVS']
D015673 Fatigue Syndrome, Chronic ['MESH']
```

## Why use it

| | |
|---|---|
| **One model for 106 sources** | every adapter returns a `UnifiedConcept` with IDs, labels, synonyms, definitions and, where the source has them, typed relationships and cross-references |
| **Honest about what works** | [live-measured samples](docs/guides/data-coverage.md) for every source: hits, latency, relationships, mappings and raw fields |
| **Identifier-aware** | fetch by CURIE, collect cross-references with `find_mappings`, validate and normalise against [Bioregistry](https://bioregistry.io/) |
| **Term expansion** | `search_concepts_expanded` follows synonyms and long forms ("COPD" to "chronic obstructive pulmonary disease"), recording every term tried |
| **Multi-source annotation** | `MultiSourceAnnotator` compares what several sources say about a text and scores their agreement |
| **Exports** | JSON, CSV, RDF/Turtle, text report, pandas DataFrame and Excel |
| **Resilient** | per-source timeouts, retries with backoff, optional circuit breakers; a source that fails or lacks a key is skipped, not fatal |
| **Agent-ready** | an [MCP server](docs/guides/mcp-server.md) for Claude, Cursor and other clients, and an optional LangGraph review workflow |
| **No surprises** | datasets download only if you opt in, your e-mail is sent only if you set it, importing the package never touches the network |

## Installation

```bash
pip install biomedical-knowledge-lookup                 # core: every HTTP-only adapter
pip install "biomedical-knowledge-lookup[curie,export]" # add extras as needed
pip install "biomedical-knowledge-lookup[all]"          # everything
```

Requires Python 3.11 or newer. Coming from 1.x? Read
[Upgrading to 2.0](docs/getting-started/upgrading-to-2.0.md).

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
knowledge-lookup sources                                      # which sources work here, and what the rest need
knowledge-lookup check HGNC                                   # live smoke test of one source (or 'all')
```

`knowledge-lookup --help` also lists `workflow`, `info`, `benchmark` and `explore`.

### MCP server for AI agents

```bash
claude mcp add biomedical-knowledge-lookup -- uvx --from "biomedical-knowledge-lookup[mcp,curie]" knowledge-lookup-mcp
```

Or run it yourself with `pip install "biomedical-knowledge-lookup[mcp,curie]"` and
`knowledge-lookup-mcp` (stdio) or `knowledge-lookup-mcp --transport streamable-http --port 8000`.
Five read-only tools: `biomed_search_concepts`, `biomed_get_concept`, `biomed_find_mappings`,
`biomed_list_sources` and `biomed_validate_curie`. Pass API keys as environment variables, for
example `claude mcp add ... -e UMLS_API_KEY=...`. See the [MCP server guide](docs/guides/mcp-server.md).

## Knowledge sources

<!-- sources:start -->
106 adapters in 12 domains; 75 work with no key, extra or download. Use the name as `KnowledgeSource.<NAME>` in Python or `--source <NAME>` on the CLI.

| Domain | Sources | Examples |
|---|---|---|
| **Ontology services and mappings**<br>Search hundreds of ontologies at once and translate identifiers between them. | 11 | OLS, EBI OLS, BioPortal, BioOntology, OBO Foundry and 6 more |
| **Clinical terminologies and coding**<br>The code systems used in registries and health records. | 9 | MeSH, SNOMED CT, WHO ICD-11, ICD-10-GM, LOINC and 4 more |
| **Diseases and phenotypes**<br>Disease ontologies, phenotype annotations and gene-disease evidence. | 15 | Mondo, Disease Ontology, HPO, HPO annotations, Orphanet and 10 more |
| **Genes, variants and expression**<br>Gene records, variants, population frequencies and tissue expression. | 15 | HGNC, NCBI Gene, MyGene.info, Ensembl, ClinVar and 10 more |
| **Proteins, structures and interactions**<br>Protein records, predicted and solved structures, families and interaction networks. | 7 | UniProt, AlphaFold DB, PDB, InterPro, Pfam and 2 more |
| **Drugs and pharmacology**<br>Drug names and classes, targets, labels, adverse events and toxicogenomics. | 11 | DrugBank, RxNorm, RxClass, ChEMBL, DGIdb and 6 more |
| **Chemicals and metabolites**<br>Small molecules, lipids, reactions and metabolomics studies. | 7 | PubChem, ChEBI, UniChem, LIPID MAPS, Rhea and 2 more |
| **Pathways and enrichment**<br>Curated pathways and gene-set enrichment. | 4 | Reactome, KEGG, WikiPathways, Enrichr |
| **Immunology and cell types**<br>Cell types, marker genes, single-cell datasets and epitopes. | 4 | Cell Ontology, CellMarker, CZ CELLxGENE, IEDB |
| **Literature and citations**<br>Papers, preprints, citation links, text-mined entities and open-access status. | 13 | Europe PMC, NCBI E-utilities, PubTator 3, LitCovid, OpenAlex and 8 more |
| **Trials, grants and datasets**<br>Clinical-trial registries, funded projects and public omics datasets. | 8 | ClinicalTrials.gov, ISRCTN registry, NIH RePORTER, GEO, OmicsDI and 3 more |
| **General knowledge**<br>Broad knowledge graphs for names and facts that specialist sources lack. | 2 | Wikidata, DBpedia |

<details>
<summary><strong>Every source by name, with what it needs</strong></summary>


**Ontology services and mappings**: [`OLS`](docs/adapters/core/ols_adapter.md) · [`EBIOLS`](docs/adapters/ontologies/ebiols_adapter.md) · [`BIOPORTAL`](docs/adapters/ontologies/bioportal_adapter.md) (key) · [`BIOONTOLOGY`](docs/adapters/ontologies/bioontology_adapter.md) (key) · [`OBOFOUNDRY`](docs/adapters/ontologies/obofoundry_adapter.md) · [`ZOOMA`](docs/adapters/ontologies/zooma_adapter.md) · [`OXO`](docs/adapters/other/oxo_adapter.md) · [`NODENORM`](docs/adapters/ontologies/nodenorm_adapter.md) · [`UMLS`](docs/adapters/core/umls_adapter.md) (key) · [`TYTO`](docs/adapters/other/tyto_adapter.md) (extra) · [`BIOLINKER`](docs/adapters/other/biolinker_adapter.md)

**Clinical terminologies and coding**: [`MESH`](docs/adapters/ontologies/mesh_adapter.md) · [`SNOMEDCT`](docs/adapters/ontologies/snomedct_adapter.md) · [`ICD11`](docs/adapters/ontologies/icd11_adapter.md) (key) · [`ICD10GM`](docs/adapters/ontologies/icd10gm_adapter.md) (file) · [`LOINC`](docs/adapters/ontologies/loinc_adapter.md) (key) · [`NCIEVS`](docs/adapters/ontologies/ncievs_adapter.md) · [`CLINICALTABLES`](docs/adapters/ontologies/clinicaltables_adapter.md) · [`FHIRTERMINOLOGY`](docs/adapters/ontologies/fhirterminology_adapter.md) · [`NCBITAXONOMY`](docs/adapters/ontologies/ncbitaxonomy_adapter.md)

**Diseases and phenotypes**: [`MONDO`](docs/adapters/core/mondo_adapter.md) · [`DOID`](docs/adapters/ontologies/doid_adapter.md) · [`HPO`](docs/adapters/phenotypes/hpo_adapter.md) · [`HPOA`](docs/adapters/phenotypes/hpoa_adapter.md) (download) · [`ORPHANET`](docs/adapters/phenotypes/orphanet_adapter.md) · [`OMIM`](docs/adapters/phenotypes/omim_adapter.md) (key) · [`MEDGEN`](docs/adapters/phenotypes/medgen_adapter.md) (key) · [`MONARCH`](docs/adapters/phenotypes/monarch_adapter.md) · [`MEDLINEPLUS`](docs/adapters/literature/medlineplus_adapter.md) · [`GENCC`](docs/adapters/phenotypes/gencc_adapter.md) (download) · [`CLINGEN`](docs/adapters/phenotypes/clingen_adapter.md) (download) · [`PANELAPP`](docs/adapters/phenotypes/panelapp_adapter.md) · [`DISGENET`](docs/adapters/core/disgenet_adapter.md) (key) · [`OPENTARGETS`](docs/adapters/core/opentargets_adapter.md) · [`GWASCATALOG`](docs/adapters/phenotypes/gwascatalog_adapter.md)

**Genes, variants and expression**: [`HGNC`](docs/adapters/proteins/hgnc_adapter.md) · [`NCBIGENE`](docs/adapters/proteins/ncbigene_adapter.md) (key) · [`MYGENEINFO`](docs/adapters/proteins/mygeneinfo_adapter.md) · [`ENSEMBL`](docs/adapters/proteins/ensembl_adapter.md) · [`CLINVAR`](docs/adapters/phenotypes/clinvar_adapter.md) · [`DBSNP`](docs/adapters/phenotypes/dbsnp_adapter.md) (key) · [`GNOMAD`](docs/adapters/phenotypes/gnomad_adapter.md) · [`COSMIC`](docs/adapters/other/cosmic_adapter.md) (key) · [`GTEX`](docs/adapters/proteins/gtex_adapter.md) · [`HUMANPROTEINATLAS`](docs/adapters/proteins/hpa_adapter.md) · [`EQTLCATALOGUE`](docs/adapters/phenotypes/eqtlcatalogue_adapter.md) · [`GENEONTOLOGY`](docs/adapters/phenotypes/geneontology_adapter.md) · [`QUICKGO`](docs/adapters/phenotypes/quickgo_adapter.md) (extra) · [`IMPC`](docs/adapters/phenotypes/impc_adapter.md) · [`ALLIANCE`](docs/adapters/proteins/alliance_adapter.md)

**Proteins, structures and interactions**: [`UNIPROT`](docs/adapters/core/uniprot_adapter.md) · [`ALPHAFOLD`](docs/adapters/proteins/alphafold_adapter.md) · [`PDB`](docs/adapters/families/pdb_adapter.md) · [`INTERPRO`](docs/adapters/families/interpro_adapter.md) · [`PFAM`](docs/adapters/families/pfam_adapter.md) · [`STRING`](docs/adapters/families/string_adapter.md) · [`INTACT`](docs/adapters/proteins/intact_adapter.md)

**Drugs and pharmacology**: [`DRUGBANK`](docs/adapters/chemicals/drugbank_adapter.md) · [`RXNORM`](docs/adapters/chemicals/rxnorm_adapter.md) · [`RXCLASS`](docs/adapters/chemicals/rxclass_adapter.md) · [`CHEMBL`](docs/adapters/core/chembl_adapter.md) (extra) · [`DGIDB`](docs/adapters/chemicals/dgidb_adapter.md) · [`CLINPGX`](docs/adapters/chemicals/clinpgx_adapter.md) · [`OPENFDALABELS`](docs/adapters/chemicals/openfdalabels_adapter.md) (key) · [`OPENFDAEVENTS`](docs/adapters/chemicals/openfdaevents_adapter.md) (key) · [`SIDER`](docs/adapters/chemicals/sider_adapter.md) (download) · [`OFFSIDES`](docs/adapters/chemicals/offsides_adapter.md) (download) · [`CTD`](docs/adapters/chemicals/ctd_adapter.md) (download)

**Chemicals and metabolites**: [`PUBCHEM`](docs/adapters/chemicals/pubchem_adapter.md) · [`CHEBI`](docs/adapters/chemicals/chebi_adapter.md) · [`UNICHEM`](docs/adapters/chemicals/unichem_adapter.md) (extra) · [`LIPIDMAPS`](docs/adapters/chemicals/lipidmaps_adapter.md) · [`RHEA`](docs/adapters/chemicals/rhea_adapter.md) · [`METABOLOMICSWORKBENCH`](docs/adapters/chemicals/metabolomicsworkbench_adapter.md) · [`METABOLIGHTS`](docs/adapters/chemicals/metabolights_adapter.md)

**Pathways and enrichment**: [`REACTOME`](docs/adapters/pathways/reactome_adapter.md) · [`KEGG`](docs/adapters/pathways/kegg_adapter.md) · [`WIKIPATHWAYS`](docs/adapters/pathways/wikipathways_adapter.md) · [`ENRICHR`](docs/adapters/pathways/enrichr_adapter.md)

**Immunology and cell types**: [`CELLONTOLOGY`](docs/adapters/ontologies/cellontology_adapter.md) · [`CELLMARKER`](docs/adapters/ontologies/cellmarker_adapter.md) (file) · [`CELLXGENE`](docs/adapters/ontologies/cellxgene_adapter.md) · [`IEDB`](docs/adapters/proteins/iedb_adapter.md)

**Literature and citations**: [`EUROPEPMC`](docs/adapters/literature/europepmc_adapter.md) · [`EUTILS`](docs/adapters/other/eutils_adapter.md) (extra) · [`PUBTATOR`](docs/adapters/literature/pubtator_adapter.md) · [`LITCOVID`](docs/adapters/literature/litcovid_adapter.md) · [`OPENALEX`](docs/adapters/literature/openalex_adapter.md) (key) · [`SEMANTICSCHOLAR`](docs/adapters/literature/semanticscholar_adapter.md) (key) · [`SEMMEDDB`](docs/adapters/literature/semmeddb_adapter.md) (key) · [`CROSSREF`](docs/adapters/literature/crossref_adapter.md) · [`BIORXIV`](docs/adapters/literature/biorxiv_adapter.md) · [`OPENCITATIONS`](docs/adapters/literature/opencitations_adapter.md) · [`UNPAYWALL`](docs/adapters/literature/unpaywall_adapter.md) (key) · [`DOAJ`](docs/adapters/literature/doaj_adapter.md) · [`OPENAIRE`](docs/adapters/literature/openaire_adapter.md)

**Trials, grants and datasets**: [`CLINICALTRIALS`](docs/adapters/literature/clinicaltrials_adapter.md) · [`ISRCTN`](docs/adapters/literature/isrctn_adapter.md) · [`NIHREPORTER`](docs/adapters/literature/nihreporter_adapter.md) · [`GEO`](docs/adapters/literature/geo_adapter.md) (key) · [`OMICSDI`](docs/adapters/literature/omicsdi_adapter.md) · [`BIOSTUDIES`](docs/adapters/literature/biostudies_adapter.md) · [`PRIDE`](docs/adapters/proteins/pride_adapter.md) · [`ZENODO`](docs/adapters/literature/zenodo_adapter.md)

**General knowledge**: [`WIKIDATA`](docs/adapters/other/wikidata_adapter.md) · [`DBPEDIA`](docs/adapters/other/dbpedia_adapter.md)

</details>

*No tag* means the source needs nothing. *(key)* needs a free key or account, *(extra)* a pip extra, *(download)* an opt-in dataset download (`<NAME>_DOWNLOAD=1`), *(file)* a file you provide. See [which source for which question](docs/guides/choosing-sources.md) for what to use when.
<!-- sources:end -->

Per-source pages are linked from the [adapter index](docs/adapters/README.md).
[What each source returns](docs/guides/data-coverage.md) shows live samples of the data each API
sends back, and the [`example_notebooks/`](example_notebooks/) folder has a notebook for most
adapters.

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
| **Getting started** | [Installation](docs/getting-started/installation.md) · [Quickstart](docs/getting-started/quickstart.md) · [Configuration](docs/getting-started/configuration.md) · [Troubleshooting](docs/getting-started/troubleshooting.md) |
| **Guides** | [Searching](docs/guides/searching-concepts.md) · [Term expansion](docs/guides/term-expansion.md) · [Multi-source annotation](docs/guides/multi-source-annotation.md) · [CURIEs](docs/guides/curie-management.md) · [Caching](docs/guides/caching.md) · [Exporting](docs/guides/exporting-results.md) · [CLI](docs/guides/cli.md) · [Agent workflow](docs/guides/agent-workflow.md) · [MCP server](docs/guides/mcp-server.md) |
| **Choosing sources** | [Which source for which question](docs/guides/choosing-sources.md) · [Recipes](docs/guides/recipes.md) · [What each source returns](docs/guides/data-coverage.md) · [All adapters](docs/adapters/README.md) |
| **Reference** | [API reference](docs/reference/api-reference.md) · [Architecture](docs/reference/architecture.md) · [Environment variables](docs/reference/environment-variables.md) · [Glossary](docs/reference/glossary.md) |
| **More** | [Examples](docs/examples/README.md) · [Example notebooks](example_notebooks/) · [Contributing](docs/contributing/README.md) · [Writing an adapter](docs/contributing/writing-an-adapter.md) · [Changelog](CHANGELOG.md) |

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
