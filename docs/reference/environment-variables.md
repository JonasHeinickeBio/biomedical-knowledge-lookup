---
description: Every environment variable the library reads - API keys, accounts, dataset switches, endpoints, MCP server and agent settings.
---

# Environment variables

All variables are optional unless a source says otherwise. They are read when the adapter is created, from the process environment or a `.env` file (see [Configuration](../getting-started/configuration.md#how-keys-are-resolved) for the lookup order and for passing the same values through `LookupConfig(api_keys=...)`). The library never writes a variable and never sends one to a service other than the one it belongs to.

{% hint style="info" %}
`knowledge-lookup check <SOURCE>` prints the variable a source needs when it is skipped. Any `<SERVICE>_API_KEY` is also found through `LookupConfig(api_keys={"<service>": "..."})`.
{% endhint %}

## API keys and accounts

| Variable | Used by | Purpose |
|---|---|---|
| `BIOPORTAL_API_KEY` | [BioPortal](../adapters/ontologies/bioportal_adapter.md), [BioOntology](../adapters/ontologies/bioontology_adapter.md) | required; free key from bioportal.bioontology.org |
| `UMLS_API_KEY` | [UMLS](../adapters/core/umls_adapter.md) | required; also needs the `[umls]` extra |
| `UMLS_API_KEY_TU` | UMLS | fallback name read when `UMLS_API_KEY` is not set |
| `DISGENET_API_KEY` | [DisGeNET](../adapters/core/disgenet_adapter.md) | required |
| `OMIM_API_KEY` | [OMIM](../adapters/phenotypes/omim_adapter.md) | required |
| `COSMIC_API_KEY` | [COSMIC](../adapters/other/cosmic_adapter.md) | optional |
| `ICD11_CLIENT_ID`, `ICD11_CLIENT_SECRET` | [WHO ICD-11](../adapters/ontologies/icd11_adapter.md) | required for the WHO cloud API (OAuth client credentials) |
| `LOINC_USERNAME`, `LOINC_PASSWORD` | [LOINC](../adapters/ontologies/loinc_adapter.md) | required; your loinc.org account |
| `SEMANTIC_SCHOLAR_API_KEY` | [Semantic Scholar](../adapters/literature/semanticscholar_adapter.md) | optional; keyless search is heavily rate limited |
| `OPENALEX_API_KEY` | [OpenAlex](../adapters/literature/openalex_adapter.md) | optional; free key raises the daily budget |
| `OPENFDA_API_KEY` | [openFDA labels](../adapters/chemicals/openfdalabels_adapter.md), [events](../adapters/chemicals/openfdaevents_adapter.md) | optional; the keyless limit is about 1,000 requests per day |
| `NCBI_API_KEY` | E-utilities based sources ([MedGen](../adapters/phenotypes/medgen_adapter.md), [GEO](../adapters/literature/geo_adapter.md), [dbSNP](../adapters/phenotypes/dbsnp_adapter.md), ClinVar, E-utilities) | optional; raises NCBI's limit from 3 to 10 requests per second |
| `ZENODO_ACCESS_TOKEN` | [Zenodo](../adapters/literature/zenodo_adapter.md) | optional; sent only as a bearer header |
| `OPENAIRE_ACCESS_TOKEN` | [OpenAIRE](../adapters/literature/openaire_adapter.md) | optional; lifts the anonymous 60 requests per hour limit |
| `OPENCITATIONS_ACCESS_TOKEN` | [OpenCitations](../adapters/literature/opencitations_adapter.md) | optional |
| `FHIR_TERMINOLOGY_TOKEN` | [FHIR terminology server](../adapters/ontologies/fhirterminology_adapter.md) | bearer token for a protected server |
| `FHIR_TERMINOLOGY_USER`, `FHIR_TERMINOLOGY_PASSWORD` | FHIR terminology server | HTTP Basic, used only when both are set and no token is set |

## Contact addresses (sent only if you set them)

| Variable | Used by | Purpose |
|---|---|---|
| `UNPAYWALL_EMAIL` | [Unpaywall](../adapters/literature/unpaywall_adapter.md) | **required** by Unpaywall; any contact address you choose |
| `OPENALEX_MAILTO` | OpenAlex | polite-pool address |
| `CROSSREF_MAILTO` | [Crossref](../adapters/literature/crossref_adapter.md) | polite-pool address |
| `NCBI_EMAIL` | E-utilities based sources | contact address NCBI asks heavy users to send |
| `MEDLINEPLUS_EMAIL` | [MedlinePlus](../adapters/literature/medlineplus_adapter.md) | contact address for NLM |

## Datasets: opt-in downloads and local files

Dataset-backed sources stay unavailable until you opt in or point them at a file you already have. Nothing is downloaded otherwise.

| Variable | Used by | Purpose |
|---|---|---|
| `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS` | all dataset sources | `1` allows every dataset download below |
| `KNOWLEDGE_LOOKUP_DATA_DIR` | all dataset sources | where downloaded files are kept (default `~/.cache/knowledge_lookup/datasets/`) |
| `HPOA_DOWNLOAD`, `HPOA_PATH` | [HPO annotations](../adapters/phenotypes/hpoa_adapter.md) | download (~36 MB) or use a local `phenotype.hpoa` |
| `SIDER_DOWNLOAD`, `SIDER_DATA_DIR` | [SIDER](../adapters/chemicals/sider_adapter.md) | download (~5.5 MB) or use a local directory |
| `OFFSIDES_DOWNLOAD`, `OFFSIDES_PATH` | [OFFSIDES](../adapters/chemicals/offsides_adapter.md) | download (~69 MB) or use a local file |
| `CTD_DOWNLOAD`, `CTD_DATA_DIR` | [CTD](../adapters/chemicals/ctd_adapter.md) | download (~220 MB, non-commercial) or use a local directory |
| `CLINGEN_DOWNLOAD`, `CLINGEN_PATH`, `CLINGEN_DOSAGE_PATH` | [ClinGen](../adapters/phenotypes/clingen_adapter.md) | download (~1.4 MB) or local files; the dosage file is read only when its own path is set |
| `GENCC_DOWNLOAD`, `GENCC_PATH` | [GenCC](../adapters/phenotypes/gencc_adapter.md) | download (~28 MB) or a local file |
| `CELLMARKER_PATH`, `CELLMARKER_URL` | [CellMarker](../adapters/ontologies/cellmarker_adapter.md) | a file you provide, or a download URL you choose |
| `ICD10GM_CLAML_PATH` | [ICD-10-GM](../adapters/ontologies/icd10gm_adapter.md) | the BfArM ClaML file |
| `ICD10GM_URL`, `ICD10GM_YEAR`, `ICD10GM_MEMBER` | ICD-10-GM | optional mirror URL (`{year}` is replaced with `ICD10GM_YEAR`) and the XML name inside a zip |
| `SEMMEDDB_PATH` | [SemMedDB](../adapters/literature/semmeddb_adapter.md) | SQLite file built with `knowledge-lookup semmeddb-build` |

## Endpoints and source options

| Variable | Used by | Purpose |
|---|---|---|
| `FHIR_TERMINOLOGY_URL` | FHIR terminology server | base URL (default `https://tx.fhir.org/r4`) |
| `FHIR_TERMINOLOGY_SYSTEMS` | FHIR terminology server | comma-separated code systems searched by default; `alias@version` pins a version |
| `SNOMED_SNOWSTORM_URL` | [SNOMED CT](../adapters/ontologies/snomedct_adapter.md) | your own Snowstorm server instead of the public browser instance |
| `SNOMED_SNOWSTORM_BRANCH` | SNOMED CT | Snowstorm branch (default `MAIN`) |
| `ICD11_API_BASE` | ICD-11 | API root, for a self-hosted container (no token is then sent) |
| `ICD11_RELEASE` | ICD-11 | MMS release id (default `2025-01`) |
| `ICD11_LANGUAGE` | ICD-11 | `Accept-Language` value (default `en`, for example `de`) |
| `PANELAPP_API_BASE` | [PanelApp](../adapters/phenotypes/panelapp_adapter.md) | another PanelApp API root |
| `GTEX_DATASET_ID` | [GTEx](../adapters/proteins/gtex_adapter.md) | dataset (default `gtex_v10`; `gtex_v8` selects the older release) |
| `EQTLCATALOGUE_RELEASE` | [eQTL Catalogue](../adapters/phenotypes/eqtlcatalogue_adapter.md) | `r7` (default) or `r8_beta` |
| `ALLIANCE_SPECIES` | [Alliance of Genome Resources](../adapters/proteins/alliance_adapter.md) | default species filter for search |
| `ENRICHR_LIBRARIES` | [Enrichr](../adapters/pathways/enrichr_adapter.md) | comma-separated library names replacing the default set |
| `CLINICALTABLES_TABLES` | [NLM Clinical Tables](../adapters/ontologies/clinicaltables_adapter.md) | comma-separated tables searched by default |

## MCP server

Each variable mirrors a command-line option of `knowledge-lookup-mcp`; see the [MCP server guide](../guides/mcp-server.md).

| Variable | Option | Default |
|---|---|---|
| `KNOWLEDGE_LOOKUP_MCP_TRANSPORT` | `--transport` | `stdio` |
| `KNOWLEDGE_LOOKUP_MCP_LOG_LEVEL` | `--log-level` | `WARNING` |
| `KNOWLEDGE_LOOKUP_MCP_TIMEOUT` | `--timeout` | `15` seconds per source |
| `KNOWLEDGE_LOOKUP_MCP_ENABLED_SOURCES` | `--enabled-sources` | all adapters |
| `KNOWLEDGE_LOOKUP_MCP_DEFAULT_SOURCES` | `--default-sources` | a general-purpose set; unavailable ones are skipped |
| `KNOWLEDGE_LOOKUP_MCP_PERSIST_EXPANSIONS` | `--persist-expansions` | off |

## Agent workflow (LLM review)

The first provider that has a key is used; with none, the review falls back to rule-based checks. See [Agent workflow](../guides/agent-workflow.md).

| Variable | Provider | Default |
|---|---|---|
| `BLABLADOR_API_KEY`, `BLABLADOR_API_BASE`, `BLABLADOR_MODEL` | Blablador (Helmholtz AI, OpenAI-compatible) | base `https://api.helmholtz-blablador.fz-juelich.de/v1/`, model `alias-fast` |
| `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL` | OpenAI or a compatible server | model `gpt-4o-mini` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Anthropic | model `claude-sonnet-4-20250514` |

## Testing

Setting `BKL_RETRY_SLEEP` to `1` makes the retry backoff really sleep while running under pytest (tests skip the sleeps by default).
