---
description: What adapters are, how to use them directly or through CentralKnowledgeLookup, and the full list of 36 knowledge-source adapters.
---

# Adapters

An adapter connects the library to one knowledge source: an ontology service, a database REST API, a SPARQL endpoint or a client library. It translates that source's responses into the common `UnifiedConcept` model, so results from OLS, UMLS, UniProt or ChEMBL can be handled the same way. The library ships **36 adapters**, one per `KnowledgeSource`, registered in `knowledge_lookup.adapters.ADAPTER_CLASSES`.

## The common interface

Every adapter subclasses `KnowledgeSourceAdapter` (`knowledge_lookup.base`) and is constructed with a `LookupConfig`.

| Member | Description |
|---|---|
| `get_source() -> KnowledgeSource` | the source the adapter serves |
| `async search_concepts(query, limit=20) -> list[UnifiedConcept]` | search the source; what `query` means depends on the source (free text, a gene symbol, a CURIE, a sentence) |
| `async get_concept_details(concept_id) -> UnifiedConcept \| None` | fetch one record by identifier; accepted formats differ per source |
| `async get_mappings(concept_id) -> list[dict]` | cross-references; `[]` unless the adapter overrides it (UMLS) |
| `async get_relationships(concept_id) -> list[dict]` | relations; `[]` unless the adapter overrides it (UMLS) |
| `is_available() -> bool` | whether the adapter can work here (API key present, library installed) |
| `get_rate_limit() -> float` | requests per second from `LookupConfig.rate_limits` (default `1.0`) |
| `async close()` | closes the HTTP session; adapters are also async context managers (`async with`) |

Some adapters accept extra keyword arguments (UMLS search filters, the BioOntology `ontology=` parameter) or add their own methods (DisGeNET associations, UniChem cross-references, ChEMBL queries). Each adapter page documents them.

A `UnifiedConcept` has `primary_id`, `primary_label`, `concept_type` (a `ConceptType` value stored as a string, e.g. `"DISEASE"`), `identifiers` (`ConceptIdentifier` objects with `source`, `identifier`, `label`, `url`), `synonyms`, `definitions`, `semantic_types`, `categories`, `parents`, `children`, `related`, `mappings`, `sources`, `confidence_score` and `source_data`, a dict keyed by `KnowledgeSource` that holds the raw upstream record. Adapters fill very different subsets of these fields; `categories` in particular carries source-specific extras such as `Organism: Homo sapiens` or `Xref: DOID:9352`.

{% hint style="info" %}
`sources` is not filled consistently: many adapters leave it empty and record the source only in `identifiers`. Use `concept.has_source(KnowledgeSource.HPO)`, which checks both.
{% endhint %}

## Using adapters

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.adapters import HPOAdapter

SOURCES = [KnowledgeSource.HPO, KnowledgeSource.MONDO, KnowledgeSource.OLS]


async def main():
    # 1. One adapter, used directly
    async with HPOAdapter(LookupConfig()) as hpo:
        seizure = await hpo.get_concept_details("HP:0001250")
        print(seizure.primary_id, seizure.primary_label)

    # 2. Several adapters through the orchestrator
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=SOURCES))
    try:
        print("available:", [s.value for s in lookup.get_available_sources()])
        result = await lookup.search_concepts("seizure", max_results=6)
        for concept in result.concepts:
            print(concept.sources, concept.primary_id, concept.primary_label)
        print("errors:", result.errors)
    finally:
        await lookup.close()


asyncio.run(main())
```

Output:

```
HP:0001250 Seizure
available: ['OLS', 'MONDO', 'HPO']
['OLS', 'MONDO', 'HPO'] http://purl.obolibrary.org/obo/HP_0001250 Seizure
['MONDO'] MONDO_0043264 post-traumatic epilepsy
['HPO'] HP:0033349 Seizure cluster
errors: {}
```

The first search result was found by all three sources and merged into one concept.

### Directly

Import the class from `knowledge_lookup.adapters` and use it as an async context manager. You choose the source and get every source-specific parameter and method, the raw `source_data`, and no extra delays. You also handle availability, throttling and failures yourself.

### Through `CentralKnowledgeLookup`

`CentralKnowledgeLookup(config)` creates every adapter in `ADAPTER_CLASSES` that is enabled in `LookupConfig.enabled_sources` (all of them when the list is unset or empty) and whose `is_available()` returns `True`. Unavailable adapters are skipped with a log warning. Set `enabled_sources` explicitly: creating all 36 adapters also initialises the ChEMBL, UniChem and UMLS clients.

- `search_concepts(query, concept_types=None, sources=None, max_results=50, parallel=True)` asks each source for `max(1, max_results // len(sources))` results. In parallel mode every source must finish within `timeout_per_source` (default 30 s). Results are merged when `enable_deduplication` is on (the default), filtered by `concept_types` (concepts typed `UNKNOWN` are kept), sorted by `confidence_score` and returned as a `LookupResult` with `concepts`, `errors` (per source), `sources_succeeded`, `sources_failed` and `execution_time`. Because most adapters catch their own errors and return `[]`, `errors` mainly shows timeouts and the few adapters that raise.
- `get_concept_details(concept_id, source=None, timeout=None)` queries one adapter when `source` is given.
- `get_available_sources()`, `add_source(source)` (raises `RuntimeError` if the adapter is unavailable), `remove_source(source)` and `close()` manage the adapter set.

{% hint style="warning" %}
`get_concept_details` **without** `source` sends the ID to every enabled adapter in parallel and waits for all of them before returning the first hit. That is slow, and most adapters only understand their own ID format. Pass `source=` whenever you know it.
{% endhint %}

See [Searching concepts](../guides/searching-concepts.md) for concept-type filtering, term expansion and result handling.

## Availability: API keys and extras

`is_available()` tells you whether an adapter can do anything in the current environment.

**API keys** are looked up with `LookupConfig.get_api_key(service)`. The lookup checks `LookupConfig(api_keys={"bioportal": "..."})` first, then the environment variable `<SERVICE>_API_KEY`, after loading a `.env` file with python-dotenv.

**Extras** install the client libraries some adapters are built on: `pip install "biomedical-knowledge-lookup[chembl]"`, or `[all]` for everything.

| Requirement | Adapters | Without it |
|---|---|---|
| `BIOPORTAL_API_KEY` | BioPortal, BioOntology | `is_available()` is `False` |
| `UMLS_API_KEY` | UMLS | `is_available()` is `False` |
| `DISGENET_API_KEY` | DisGeNET | `is_available()` is `False` |
| `OMIM_API_KEY` | OMIM | `is_available()` is `False` |
| `[chembl]` extra | ChEMBL | `ChEMBLAdapter` is `None`; the source is missing from `ADAPTER_CLASSES` |
| `[umls]` extra | UMLS | `UMLSAdapter` is `None`; the source is missing from `ADAPTER_CLASSES` |
| `[bioservices]` extra | UniChem, QuickGO, NCBI E-utilities | `is_available()` is `False` |
| `[tyto]` extra | Tyto | `is_available()` is `False` |

All other adapters use public APIs without a key. See [Configuration](../getting-started/configuration.md) for setting keys.

## Rate limits, retries and circuit breakers

**Retries.** HTTP adapters send requests through `KnowledgeSourceAdapter._make_request` / `_make_request_text`, which retry by error category:

| Error | Attempts | Pause between attempts |
|---|---|---|
| network error (connection, timeout, DNS) | 3 | none |
| HTTP 429 or "rate limit" | 4 | 2 s, 4 s, 8 s |
| HTTP 5xx | 4 | 1.5 s, 3 s, 6 s |
| HTTP 404 | 1 | not retried; not a circuit-breaker failure (see below) |
| other HTTP 4xx | 1 | not retried |
| anything else | 2 | 1 s |

Adapters built on synchronous libraries (NCBI E-utilities, QuickGO and UniChem via `bioservices`) apply the same rules in a worker thread (`_thread_with_retry`). ChEMBL retries its `query()` calls with its own backoff decorator (up to four tries). UMLS and Tyto rely on their libraries and do not use the shared retry.

**Errors.** Once retries are exhausted, most adapters log the error and return `[]` from `search_concepts` and `None` from `get_concept_details`. Exceptions to this rule are noted on the adapter pages.

**Throttling.** Adapters do not throttle on their own. `CentralKnowledgeLookup` waits `1 / rate_limit` seconds before each search on a source, where the rate comes from `LookupConfig.rate_limits` (default 1 request per second, i.e. a one-second delay). Raise it per source, for example `LookupConfig(rate_limits={KnowledgeSource.OLS: 10.0})`.

**Circuit breakers** are off by default. With `LookupConfig(enable_source_health_tracking=True)`, `CentralKnowledgeLookup` gives each adapter a breaker. The breaker opens after `circuit_breaker_threshold` consecutive failures (default 5) and lets a probe request through after `circuit_breaker_cooldown` seconds (default 30). A failure is a request that still fails once its retries are exhausted, or a search or `get_concept_details()` call cut off by `timeout_per_source`. An HTTP 404 is not a failure: the service answered, and APIs such as Reactome and PubChem use 404 for "no match", so it counts as a success (and closes a half-open breaker). While a breaker is open, calls to that adapter fail fast, `search_concepts()` and `get_concept_details()` skip the source, and `LookupResult.source_health` reports the state.

## All adapters

Pages are grouped by category.

### Core sources

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [ChEMBL](core/chembl_adapter.md) | bioactive molecules, drugs, targets, bioactivity records | `CHEMBL25` | `[chembl]` extra |
| [DisGeNET](core/disgenet_adapter.md) | gene–disease associations with scores | `UMLS_C0011849` | `DISGENET_API_KEY` |
| [Mondo](core/mondo_adapter.md) | Mondo Disease Ontology (via OLS) | `MONDO:0005148` | none |
| [OLS](core/ols_adapter.md) | search across all EBI OLS4 ontologies | `http://purl.obolibrary.org/obo/HP_0001250` | none |
| [Open Targets](core/opentargets_adapter.md) | Open Targets Platform targets and diseases | `ENSG00000012048` | none |
| [UMLS](core/umls_adapter.md) | UMLS Metathesaurus: CUIs, definitions, relations, crosswalks | `C0011849` | `[umls]` extra, `UMLS_API_KEY` |
| [UniProt](core/uniprot_adapter.md) | UniProtKB protein entries | `P38398` | none |

### Chemicals and drugs

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [DrugBank](chemicals/drugbank_adapter.md) | DrugBank drugs via MyChem.info | `DB00945` | none |
| [PubChem](chemicals/pubchem_adapter.md) | compounds by name or CID | `2244` | none |
| [UniChem](chemicals/unichem_adapter.md) | compound cross-references between chemistry databases | `BSYNRYMUTXBXSQ-UHFFFAOYSA-N` | `[bioservices]` extra |

### Genes and proteins

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [Ensembl](proteins/ensembl_adapter.md) | Ensembl gene records, human symbol lookup | `ENSG00000139618` | none |
| [HGNC](proteins/hgnc_adapter.md) | approved human gene symbols with cross-references | `HGNC:1100` | none |

### Protein families, structures and interactions

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [InterPro](families/interpro_adapter.md) | protein families and domains | `IPR000719` | none |
| [PDB](families/pdb_adapter.md) | RCSB 3D structure entries | `4HHB` | none |
| [Pfam](families/pfam_adapter.md) | Pfam families via the InterPro API | `PF00069` | none |
| [STRING](families/string_adapter.md) | human protein interaction partners | `TP53` | none |

### Phenotypes, variants and annotations

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [ClinVar](phenotypes/clinvar_adapter.md) | clinical variants (NCBI E-utilities) | `17661` | none |
| [Gene Ontology](phenotypes/geneontology_adapter.md) | GO terms (QuickGO REST) | `GO:0006915` | none |
| [HPO](phenotypes/hpo_adapter.md) | Human Phenotype Ontology | `HP:0001250` | none |
| [OMIM](phenotypes/omim_adapter.md) | Mendelian disorders and genes | `OMIM:219700` | `OMIM_API_KEY` |
| [QuickGO](phenotypes/quickgo_adapter.md) | GO terms and annotations via `bioservices` | `GO:0006915` | `[bioservices]` extra |

### Ontology services

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [BioOntology](ontologies/bioontology_adapter.md) | BioPortal REST client: search, class details, Annotator | IRI plus ontology, e.g. `MESH` | `BIOPORTAL_API_KEY` |
| [BioPortal](ontologies/bioportal_adapter.md) | search across BioPortal ontologies | `http://purl.bioontology.org/ontology/MESH/D003920` | `BIOPORTAL_API_KEY` |
| [EBI OLS](ontologies/ebiols_adapter.md) | the OLS adapter under a second source name | `http://purl.obolibrary.org/obo/HP_0001250` | none |
| [OBO Foundry](ontologies/obofoundry_adapter.md) | lightweight OLS4 term search | `NCIT_C17557` | none |
| [ZOOMA](ontologies/zooma_adapter.md) | text value → ontology term annotation | `http://purl.obolibrary.org/obo/HP_0001658` | none |

### Pathways

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [KEGG](pathways/kegg_adapter.md) | KEGG diseases and drugs | `H00409`, `D00944` | none |
| [Reactome](pathways/reactome_adapter.md) | Reactome pathways and reactions | `R-HSA-109581` | none |

### Literature

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [Europe PMC](literature/europepmc_adapter.md) | articles and preprints | `MED:23193287` | none |

### Other sources

| Adapter | Covers | Identifier example | Requires |
|---|---|---|---|
| [BioLinker](other/biolinker_adapter.md) | entity linking in free text (TIB BioLinker AI) | text in, CUIs such as `C0025598` out | none |
| [COSMIC](other/cosmic_adapter.md) | cancer genes | `COSMIC:TP53` | none |
| [DBpedia](other/dbpedia_adapter.md) | general knowledge via SPARQL | `Metformin` | none |
| [NCBI E-utilities](other/eutils_adapter.md) | PubMed, Gene, Protein, Taxonomy | `PMID:23193287` | `[bioservices]` extra |
| [OxO](other/oxo_adapter.md) | ontology cross-reference mappings | `MONDO:0005148` | none |
| [Tyto](other/tyto_adapter.md) | ontology term labels via `tyto` | `http://identifiers.org/SBO:0000241` | `[tyto]` extra |
| [Wikidata](other/wikidata_adapter.md) | Wikidata items via SPARQL | `Q18216` | none |

{% hint style="warning" %}
**Known issues (tested September 2026).** Details are on each page.

- **No data at all:** [COSMIC](other/cosmic_adapter.md) (COSMIC has no query API; the adapter is unavailable without credentials).
- **Slow:** [ChEMBL](core/chembl_adapter.md) multi-word and target searches (e.g. `EGFR`) can exceed the 30-second per-source timeout; molecule names and ChEMBL IDs are fast.
- **Partial:** [DrugBank](chemicals/drugbank_adapter.md) (served by MyChem.info: names, synonyms and identifiers, no descriptions), [Tyto](other/tyto_adapter.md) (exact-label search in SO, SBO and NCIT only), [DBpedia](other/dbpedia_adapter.md) (the public endpoint currently has few English abstracts).
{% endhint %}

## Adding an adapter

1. Add a member to `KnowledgeSource` in `knowledge_lookup.models`.
2. Create `src/knowledge_lookup/adapters/<name>_adapter.py` with a subclass of `KnowledgeSourceAdapter`. Implement `get_source`, `search_concepts` and `get_concept_details`, and override `is_available` if the source needs a key or library.
3. Send HTTP requests through `_make_request` / `_make_request_text`, or wrap synchronous libraries with `_thread_with_retry`, so the retries and circuit breaker apply. `_create_concept(concept_id, label, concept_type)` creates a concept with the identifier and `sources` already set.
4. Register the class in `adapters/__init__.py` (`ADAPTER_CLASSES` and `__all__`), and add the source to `SOURCE_CATALOG` and `SourceName` in `knowledge_lookup/mcp_server/sources.py`.
5. Add unit tests and a page in the matching `docs/adapters/<category>/` folder, following the structure of the existing pages.

## See also

- [Searching concepts](../guides/searching-concepts.md)
- [Configuration](../getting-started/configuration.md)
- [Examples](../examples/README.md)
