---
description: What adapters are, how to use them directly or through CentralKnowledgeLookup, and the full list of 106 knowledge-source adapters.
---

# Adapters

An adapter connects the library to one knowledge source: an ontology service, a database REST API, a SPARQL endpoint or a client library. It translates that source's responses into the common `UnifiedConcept` model, so results from OLS, UMLS, UniProt or ChEMBL can be handled the same way. The library ships **106 adapters**, one per `KnowledgeSource`, registered in `knowledge_lookup.adapters.ADAPTER_CLASSES`. To see what each one actually returns (hits, relationships, cross-references, raw fields), measured live, read [What each source returns](../guides/data-coverage.md).

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

`CentralKnowledgeLookup(config)` creates every adapter in `ADAPTER_CLASSES` that is enabled in `LookupConfig.enabled_sources` (all of them when the list is unset or empty) and whose `is_available()` returns `True`. Unavailable adapters are skipped with a log warning. Set `enabled_sources` explicitly: creating all 106 adapters also imports every adapter module and initialises the ChEMBL, UniChem and UMLS clients. Disabled sources are never imported.

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

The 106 adapters are grouped by what they are used for. "Access" says what you need before the adapter works; most need nothing.

### Ontology services and mappings

Search hundreds of ontologies at once and translate identifiers between them.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [OLS](core/ols_adapter.md) | Free-text search across every ontology in the EMBL-EBI Ontology Lookup Service (OLS4) | term IRI, e.g. `http://purl.obolibrary.org/obo/MONDO_0005148` | none |
| [EBI OLS](ontologies/ebiols_adapter.md) | A second registration of the OLS adapter under KnowledgeSource.EBIOLS | term IRI, e.g. `http://purl.obolibrary.org/obo/HP_0001250` | none |
| [BioPortal](ontologies/bioportal_adapter.md) | Search across 1000+ ontologies in NCBO BioPortal - SNOMED CT, MeSH, LOINC, ICD and more (API key required) | class IRI, e.g. `http://purl.bioontology.org/ontology/MESH/D003920` | `BIOPORTAL_API_KEY` |
| [BioOntology](ontologies/bioontology_adapter.md) | Full NCBO BioPortal REST client - search, class details, Annotator and generic endpoints (API key required) | class IRI plus ontology acronym, e.g. `http://purl.bioontology.org/ontology/MESH/D003920` in `MESH` | `BIOPORTAL_API_KEY` |
| [OBO Foundry](ontologies/obofoundry_adapter.md) | Lightweight term search over the ontologies in OLS4, labelled as OBO Foundry | OLS short form, e.g. `NCIT_C17557` | none |
| [ZOOMA](ontologies/zooma_adapter.md) | EBI ZOOMA - map free-text annotation values to ontology terms using curated annotations | ontology term IRIs, e.g. `http://purl.obolibrary.org/obo/HP_0001658` | none |
| [OxO](other/oxo_adapter.md) | EBI OxO cross-references between ontology and vocabulary identifiers (CURIEs) | CURIE, e.g. `MONDO:0005148`, `DOID:162` | none |
| [NCATS Node Normalizer and Name Resolver](ontologies/nodenorm_adapter.md) | NCATS Translator Node Normalizer / Name Resolver: equivalent identifiers across MONDO, HP, UMLS, MeSH, NCBIGene | any CURIE, prefix case does not matter: `MONDO:0005404`, `mesh:D015673`, `ncbigene:672` | none (keyless) |
| [UMLS](core/umls_adapter.md) | UMLS Metathesaurus concepts (CUIs) with definitions, relations and crosswalks to SNOMED CT, MeSH, ICD and more | CUI, e.g. `C0011849` | `[umls]` extra and `UMLS_API_KEY` |
| [Tyto](other/tyto_adapter.md) | Ontology term lookup (SO, SBO, NCIT) through the tyto library | term URI, e.g. `http://purl.obolibrary.org/obo/SO_0000167`, `http://identifiers.org/SBO:0000241` | `[tyto]` extra |
| [BioLinker](other/biolinker_adapter.md) | TIB BioLinker AI - link entities and predicates in free text to UMLS concepts | input is text; results use UMLS CUIs, e.g. `C0025598` | none |

### Clinical terminologies and coding

The code systems used in registries and health records.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [MeSH](ontologies/mesh_adapter.md) | NLM Medical Subject Headings descriptors, supplementary concepts and qualifiers with entry terms, scope notes, tree… | `D015673` (descriptor), `C000657245` (supplementary concept), `Q000175` (qualifier); also `MESH:D015673`, `MeSH:D015673` and the full `http://id.nlm.nih.gov/mesh/D015673` URI | none |
| [SNOMED CT (Snowstorm)](ontologies/snomedct_adapter.md) | SNOMED CT concepts, synonyms, is-a hierarchy and attribute relationships through a Snowstorm server (SNOMED… | SCTID: `84229001` (fatigue), `52448006` (dementia); also `SNOMEDCT:84229001`, `SNOMED:84229001`, `SCTID:84229001` | none for the code; **a SNOMED CT licence for the content** (see below) |
| [WHO ICD-11](ontologies/icd11_adapter.md) | WHO ICD-11 (MMS) entities and codes via the ICD-API, with parents and children as typed relationships | MMS code `8E49`, `ICD11:8E49`, numeric MMS entity id (the number at the end of a WHO URI), or a WHO URI | `ICD11_CLIENT_ID` and `ICD11_CLIENT_SECRET` (free registration at <https://icd.who.int/icdapi>), **or** `ICD11_API_BASE` pointing at a self-hosted ICD-API container |
| [ICD-10-GM](ontologies/icd10gm_adapter.md) | German ICD-10-GM (BfArM) classification read from a local ClaML file, with German labels and hierarchy | `G93.3`, `G933`, `ICD10GM:G93.3`, block codes `G90-G99`, chapter numerals `VI` | a ClaML file: `ICD10GM_CLAML_PATH` (or an optional `ICD10GM_URL`) |
| [LOINC](ontologies/loinc_adapter.md) | LOINC laboratory and clinical observation codes through the Regenstrief FHIR R4 terminology server, with the six LOINC… | LOINC codes `2093-3`, `LOINC:2093-3` (LP part codes such as `LP15099-2` are accepted by `$lookup`) | `LOINC_USERNAME` and `LOINC_PASSWORD` (free account at <https://loinc.org>; also read from `config.get_api_key("loinc_username")` / `("loinc_password")`) |
| [NCI Thesaurus (EVS)](ontologies/ncievs_adapter.md) | NCI Thesaurus, NCI Metathesaurus and other terminologies (SNOMED CT, ICD-10-CM, LOINC, MedDRA, ...) via the keyless… | `NCIT:C3036` (or bare `C3036`), `NCIM:C0015674` (or a bare CUI `C0015674` / `CL...`), and `<terminology>:<code>` such as `SNOMEDCT_US:52702003`, `ICD10CM:G93.32` | none (no key, no registration) |
| [NLM Clinical Tables](ontologies/clinicaltables_adapter.md) | NLM Clinical Table Search Service: ICD-10-CM, LOINC items, consumer conditions, HPO, ICD-11 and ClinVar disease names… | `ICD10CM:G93.32` (or bare `G93.32` / `G9332`), `CONDITIONS:12927`, `LOINC:70735-6` (or bare `70735-6`), `HP:0012378`, `ICD11:MG22`, `DISEASE_NAMES:C0015672` (or a bare CUI) | none (no key, no registration) |
| [FHIR terminology server](ontologies/fhirterminology_adapter.md) | Generic HL7 FHIR terminology server client (tx.fhir.org, Ontoserver, German MII or any $lookup/$expand server) | `<system>\\|<code>` with an alias or a URI: `loinc\\|2093-3`, `snomed\\|84229001`, `http://loinc.org\\|2093-3`; `<system>\\|<code>\\|<version>` pins a code system version | none for the default public server; optional credentials for protected servers |
| [NCBI Taxonomy](ontologies/ncbitaxonomy_adapter.md) | NCBI Taxonomy organisms and viruses (SARS-CoV-2, EBV, HHV-6, enteroviruses) with lineage, synonyms and cross-references | `2697049`, `NCBITaxon:2697049`, `taxid:2697049` | none (an NCBI key only raises the rate limit) |

### Diseases and phenotypes

Disease ontologies, phenotype annotations and gene-disease evidence.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [Mondo](core/mondo_adapter.md) | Mondo Disease Ontology terms, served from the EBI Ontology Lookup Service | `MONDO:0005148` | none |
| [Disease Ontology](ontologies/doid_adapter.md) | Human Disease Ontology (DOID) diseases with definitions, synonyms, typed relations and cross-references to MeSH, OMIM… | `DOID:9351`, `DOID_9351`, bare `9351` or the full IRI `http://purl.obolibrary.org/obo/DOID_9351` | none |
| [HPO](phenotypes/hpo_adapter.md) | Human Phenotype Ontology terms from the JAX ontology API | `HP:0001250` | none |
| [HPO annotations (phenotype.hpoa)](phenotypes/hpoa_adapter.md) | HPO disease-to-phenotype annotations with frequency, onset and evidence (phenotype.hpoa download) | `OMIM:154700`, `ORPHA:558`, `DECIPHER:5` (diseases); `HP:0012432` (phenotypes, relationships only) | opt-in download (~36 MB): `HPOA_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or a local file in `HPOA_PATH` |
| [Orphanet](phenotypes/orphanet_adapter.md) | Orphanet rare-disease nosology (ORPHAcodes), genes, HPO phenotypes with frequency, prevalence and cross-references via… | `ORPHA:558`; also `Orphanet_558`, `orphanet:558`, `ORPHAcode 558`, bare `558` | none (keyless) |
| [OMIM](phenotypes/omim_adapter.md) | OMIM Mendelian disorders and genes (API key required) | `OMIM:219700` (also `MIM:219700` or `219700`) | `OMIM_API_KEY` |
| [MedGen](phenotypes/medgen_adapter.md) | NCBI MedGen conditions and phenotypes keyed by UMLS CUI, with cross-references to MeSH, OMIM, Orphanet, MONDO, HPO… | UMLS CUI (`C0015674`, also `UMLS:C0015674`, `MedGen:C0015674`) or MedGen UID (`5130`, `MedGen:5130`) | none (optional `NCBI_API_KEY` raises the rate limit from 3 to 10 requests/s) |
| [Monarch Initiative](phenotypes/monarch_adapter.md) | Monarch Initiative gene-disease-phenotype associations (HPO, MONDO, OMIM, Orphanet) with frequency and onset qualifiers | `HGNC:1100`, `MONDO:0005148`, `HP:0012432`; also `OMIM:`, `Orphanet:`/`ORPHA:`, `UMLS:` and non-human `NCBIGene:` ids (see below) | none (keyless) |
| [MedlinePlus](literature/medlineplus_adapter.md) | MedlinePlus plain-language health topics by text search, URL slug or ICD-10-CM / SNOMED CT / ICD-9-CM / LOINC / RxNorm… | a topic slug or URL: `MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome`, `fatigue`, `https://medlineplus.gov/fatigue.html`, Spanish `spanish/fatigue`; a code: `ICD10CM:G93.32` (or bare `G93.32`), `SNOMEDCT:52702003`, `ICD9CM:780.71`, `LOINC:2951-2` (or bare), `RXNORM:861004`, `NDC:<code>` | none (no key, no registration) |
| [GenCC](phenotypes/gencc_adapter.md) | GenCC harmonised gene-disease validity submissions from ClinGen, Orphanet, PanelApp, G2P and laboratories, with a… | genes `HGNC:1100` or `BRCA1`; diseases `MONDO:0008426` and the ids submitters used, `OMIM:182212`, `Orphanet:558` | opt-in download (~28.4 MB): `GENCC_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or a local copy in `GENCC_PATH` |
| [ClinGen](phenotypes/clingen_adapter.md) | ClinGen gene-disease validity classifications (Definitive to Refuted) and gene dosage sensitivity, from ClinGen's… | `HGNC:1100` or a symbol such as `BRCA1`; `MONDO:0007947` | opt-in download (~1.4 MB): `CLINGEN_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or a local file in `CLINGEN_PATH` |
| [PanelApp](phenotypes/panelapp_adapter.md) | Genomics England PanelApp expert-reviewed gene panels, with green/amber/red gene evidence, inheritance and phenotypes | panel: numeric id (`158`, `panelapp:158`); gene: `HGNC:1100` or the symbol `BRCA1` | none (keyless) |
| [DisGeNET](core/disgenet_adapter.md) | DisGeNET diseases and gene–disease associations with scores and evidence metrics (API key required) | disease `UMLS_C0011849` (also `C0011849`, `MONDO_0005015`), gene symbol `CDK2`, NCBI gene ID `1017` | `DISGENET_API_KEY` |
| [Open Targets](core/opentargets_adapter.md) | Targets and diseases from the Open Targets Platform GraphQL API | target `ENSG00000012048`; disease `MONDO_0004979`, `EFO_0000270`, `Orphanet_145` | none |
| [GWAS Catalog](phenotypes/gwascatalog_adapter.md) | NHGRI-EBI GWAS Catalog traits and variant-trait associations (REST API v2, no key) | traits `MONDO:0005404`, `EFO:0004540`, `HP:0012378` (also `MONDO_0005404`); variants `rs1801270` | none |

### Genes, variants and expression

Gene records, variants, population frequencies and tissue expression.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [HGNC](proteins/hgnc_adapter.md) | HGNC approved human gene symbols and names, with NCBI Gene, UniProt and Ensembl cross-references | `HGNC:1100` or an approved symbol such as `BRCA1` | none |
| [NCBI Gene](proteins/ncbigene_adapter.md) | NCBI Gene records, summaries and cross-references (Datasets API) | Entrez Gene id `672` (primary), `NCBIGene:672`, `GeneID:672`, `Entrez:672`; an official symbol (`BRCA1`) also works in `get_concept_details` | none (an optional `NCBI_API_KEY` raises the polite request rate) |
| [MyGene.info](proteins/mygeneinfo_adapter.md) | MyGene.info gene annotation with Entrez, Ensembl, HGNC, UniProt and OMIM cross-references, pathways and orthologs | `NCBIGene:672` (primary), bare Entrez `672`, `ENSG00000012048`, `HGNC:1100`, UniProt `P38398`, symbol/alias `BRCA1` | none |
| [Ensembl](proteins/ensembl_adapter.md) | Ensembl gene records by stable ID or human gene symbol, plus a full catalog of the Ensembl REST API as async adapter… | stable ID, e.g. `ENSG00000139618` | none |
| [ClinVar](phenotypes/clinvar_adapter.md) | ClinVar variant records from NCBI, searched with Entrez query syntax | ClinVar variation ID, e.g. `17661` (also `ClinVar:17661`, `VCV000017661`) | none |
| [dbSNP](phenotypes/dbsnp_adapter.md) | NCBI dbSNP reference SNPs (rsIDs) with placements, allele frequencies, genes and ClinVar clinical significance via the… | `rs1801133`, bare `1801133`, `dbSNP:rs1801133`; also SPDI (`NC_000001.11:11796320:G:A`) and genomic HGVS (`NC_000001.11:g.11796321G>A`), which are first resolved to an rsID | none; an optional NCBI key (`NCBI_API_KEY`) shortens the request spacing |
| [gnomAD](phenotypes/gnomad_adapter.md) | gnomAD population allele frequencies and gene constraint (pLI, LOEUF, missense z) via the public GraphQL API | gene: `ENSG00000012048` (a symbol such as `BRCA1` is accepted as input); variant: `1-11796321-G-A` (GRCh38 `chrom-pos-ref-alt`), or an rsID such as `rs1801133` | none (no key) |
| [COSMIC](other/cosmic_adapter.md) | COSMIC cancer genes and somatic mutations (requires COSMIC account credentials; no query API is currently available) | `COSMIC:TP53` | COSMIC account credentials (`COSMIC_API_KEY`) |
| [GTEx](proteins/gtex_adapter.md) | GTEx Portal gene expression across 54 tissues (median TPM, tissue specificity) and single-tissue eQTL variants | Ensembl gene id `ENSG00000012048` (with or without version) or HGNC symbol `BRCA1`. Entrez ids, HGNC ids and free text are **not** searchable | none |
| [Human Protein Atlas](proteins/hpa_adapter.md) | Human Protein Atlas gene expression by tissue and blood immune cell type, plasma protein and subcellular location… | Ensembl gene id `ENSG00000012048`; approved symbols such as `BRCA1` are accepted wherever an id is | none |
| [eQTL Catalogue](phenotypes/eqtlcatalogue_adapter.md) | EBI eQTL Catalogue dataset, study and tissue metadata (the association REST API has been retired; no gene or variant… | dataset `QTD000021`, study `QTS000002`, tissue / cell type `CL:0000235`, `UBERON:0000178` (underscore form accepted) | none |
| [Gene Ontology](phenotypes/geneontology_adapter.md) | Gene Ontology terms (processes, functions, components) from the QuickGO ontology API | `GO:0006915` | none |
| [QuickGO](phenotypes/quickgo_adapter.md) | Gene Ontology terms and gene-product annotations from EBI QuickGO through bioservices | `GO:0006915`; gene products such as `UniProtKB:P04637` or `P04637` | `[bioservices]` extra |
| [IMPC](phenotypes/impc_adapter.md) | International Mouse Phenotyping Consortium knockout-mouse genes and significant phenotype calls (MP terms), with human… | `MGI:95489` (gene), `MP:0004952` (phenotype); gene symbols (mouse `Fbn1` or human `FBN1`) are accepted by `get_concept_details`, `get_mappings` and `get_relationships` | none (public, keyless) |
| [Alliance of Genome Resources](proteins/alliance_adapter.md) | Alliance of Genome Resources genes of eight model organisms and human, with orthologs, disease annotations, phenotypes… | `HGNC:1100`, `MGI:104537`, `RGD:2218`, `ZFIN:ZDB-GENE-990415-72`, `SGD:S000003865`, `WB:WBGene00004930`, `FB:FBgn0003462`, `Xenbase:XB-GENE-1006488`; a bare symbol (`TNF`) is resolved through search, human first | none (public, keyless) |

### Proteins, structures and interactions

Protein records, predicted and solved structures, families and interaction networks.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [UniProt](core/uniprot_adapter.md) | UniProtKB protein entries - names, genes, function and organism | accession, e.g. `P38398` | none |
| [AlphaFold DB](proteins/alphafold_adapter.md) | AlphaFold DB predicted protein structures: pLDDT confidence, model and PAE URLs, UniProt mapping and links to… | UniProt accession `P38398` (isoform `P38398-2` allowed), AlphaFold entry id `AF-P38398-F1` (`AF-P38398-2-F1` for an isoform), or a gene symbol / protein name (resolved to a human UniProt accession) | none (no key) |
| [PDB](families/pdb_adapter.md) | RCSB Protein Data Bank structure entries - titles, experimental method, resolution | `4HHB` (or `PDB:4HHB`) | none |
| [InterPro](families/interpro_adapter.md) | InterPro protein families, domains and repeats | `IPR000719` | none |
| [Pfam](families/pfam_adapter.md) | Pfam protein families and domains, served through the InterPro API | `PF00069` | none |
| [STRING](families/string_adapter.md) | STRING human protein identifiers and their top interaction partners | protein name `TP53` or STRING ID `9606.ENSP00000269305` | none |
| [IntAct](proteins/intact_adapter.md) | IntAct curated experimental molecular interactions with detection method, score and PubMed evidence | UniProt accession `P38398` (primary), IntAct `EBI-349905`, isoform `P38398-1`, exact gene name `BRCA1` | none |

### Drugs and pharmacology

Drug names and classes, targets, labels, adverse events and toxicogenomics.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [DrugBank](chemicals/drugbank_adapter.md) | DrugBank IDs, names and synonyms, looked up without an API key through MyChem.info | `DB00945` (also `DRUGBANK:DB00945`) | none |
| [RxNorm](chemicals/rxnorm_adapter.md) | NLM RxNorm drug concepts (ingredients, brands, clinical drugs, dose forms) and relations, with ATC, DrugBank, SNOMED… | RxCUI: `1191`, `RXCUI:1191` or `RxNorm:1191` | none |
| [RxClass (ATC)](chemicals/rxclass_adapter.md) | Map drug and brand names to RxCUI and WHO ATC classes (and back) with NLM RxNav RxClass; harmonise registry… | RxCUI (`1191`, `RXCUI:1191`, `RxNorm:1191`) for drugs; ATC code (`N02BA`, `ATC:N02BA`) for classes; level 5 codes (`N02BA01`) resolve to the drug that carries them | none |
| [ChEMBL](core/chembl_adapter.md) | ChEMBL bioactive molecules, drugs and targets, plus raw access to any ChEMBL endpoint (requires the chembl extra) | ChEMBL ID of a molecule, drug or target, e.g. `CHEMBL25` | `[chembl]` extra |
| [DGIdb](chemicals/dgidb_adapter.md) | DGIdb aggregated drug-gene interactions (v5 GraphQL API, no key) | genes `hgnc:1100`; drugs `rxcui:1191`, `chembl:CHEMBL1703` (DGIdb's own primary concept ids); bare symbols or exact drug names also work | none |
| [ClinPGx (PharmGKB)](chemicals/clinpgx_adapter.md) | ClinPGx/PharmGKB pharmacogenomic genes, drugs, variants and haplotypes with clinical annotations, CPIC/DPWG guidelines… | PA ids: `PA128` (gene CYP2D6), `PA449088` (drug codeine), `PA166156104` (variant rs3892097), `PA165816579` (haplotype CYP2D6*4); `CLINPGX:PA128` and `PHARMGKB:PA128` accepted | none |
| [openFDA drug labels (DailyMed)](chemicals/openfdalabels_adapter.md) | FDA structured drug labels (DailyMed SPL) via openFDA - indications, boxed warnings, contraindications, adverse… | SPL set id (UUID), e.g. `0058175f-3474-40c3-a046-6cfaec86d84b`; `DAILYMED:<set id>` accepted | none; optional `OPENFDA_API_KEY` (or `api_keys["openfda"]`) raises the daily quota |
| [openFDA adverse events (FAERS)](chemicals/openfdaevents_adapter.md) | FDA adverse event reports (FAERS) by drug and reaction via openFDA; descriptive report counts, not risks (keyless) | drugs `FAERS:DRUG:ASPIRIN`; reactions `FAERS:REACTION:FATIGUE`. Bare names (`aspirin`, `fatigue`) are accepted; a bare name is tried as a drug first, then as a reaction. Also `DRUG:`, `REACTION:`, `PT:` and `MEDDRA:` prefixes. Names are upper-cased. MedDRA codes are not published by this API, so none are claimed | none. Optional `OPENFDA_API_KEY` (raises the daily quota) |
| [SIDER](chemicals/sider_adapter.md) | SIDER 4.1 drug side effects text-mined from drug labels, with frequencies, ATC and PubChem mappings (outdated, 2015… | drugs: STITCH compound id `CID100002244`; side effects: UMLS CUI `C0015672` | opt-in download (~5.5 MB): `SIDER_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or local files in `SIDER_DATA_DIR` |
| [OFFSIDES](chemicals/offsides_adapter.md) | OFFSIDES off-label drug side-effect signals mined from FDA adverse-event reports (statistical, not causal; 69 MB… | drugs `RXNORM:1191` (bare `1191` also accepted), events `MEDDRA:10016256` | a local `OFFSIDES.csv(.gz)` (`OFFSIDES_PATH`) or opt-in download (`OFFSIDES_DOWNLOAD=1`) |
| [CTD](chemicals/ctd_adapter.md) | Comparative Toxicogenomics Database chemical-gene-disease links from CTD bulk files (non-commercial use, citation… | chemicals `MESH:D001241` (or a CAS number); diseases `MESH:D003920`, `OMIM:264300`; genes `NCBIGene:672` | opt-in download (~220 MB core reports): `CTD_DOWNLOAD=1` or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1`, or a local copy in `CTD_DATA_DIR` |

### Chemicals and metabolites

Small molecules, lipids, reactions and metabolomics studies.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [PubChem](chemicals/pubchem_adapter.md) | PubChem compounds by name or CID - title, IUPAC name, formula and InChIKey | CID, e.g. `2244` | none |
| [ChEBI](chemicals/chebi_adapter.md) | ChEBI chemical entities with definitions, formula/mass/structure, ontology relations (including roles) and database… | `CHEBI:15365`, `chebi:15365`, `CHEBI_15365`, bare `15365` or the OBO IRI | none |
| [UniChem](chemicals/unichem_adapter.md) | EMBL-EBI UniChem - cross-reference one compound across ChEMBL, DrugBank, PubChem, ChEBI and other chemistry databases | InChIKey `BSYNRYMUTXBXSQ-UHFFFAOYSA-N`, UCI `161671`, or a source ID such as `CHEMBL25` | `[bioservices]` extra |
| [LIPID MAPS](chemicals/lipidmaps_adapter.md) | LIPID MAPS (LMSD) lipid structures, classification and cross-references to PubChem, ChEBI, HMDB, KEGG, SwissLipids and… | LMSD id `LMGP01010005`; class codes `LMGP` (category), `LMGP01` (main class), `LMGP0101` (sub class) | none (keyless) |
| [Rhea](chemicals/rhea_adapter.md) | Rhea expert-curated biochemical reactions with ChEBI participants, EC numbers, GO terms and KEGG/MetaCyc/Reactome… | `RHEA:23444`, or the bare number `23444` | none (keyless) |
| [Metabolomics Workbench](chemicals/metabolomicsworkbench_adapter.md) | Metabolomics Workbench metabolomics studies (including ME/CFS and Long COVID) and RefMet metabolites with PubChem… | `ST002003` (study), `RM0135904` (RefMet metabolite), `regno:37125` (compound registry number), or an exact RefMet name | none |
| [MetaboLights](chemicals/metabolights_adapter.md) | EMBL-EBI MetaboLights metabolomics studies (including ME/CFS and Long COVID) and ChEBI-based reference metabolites | `MTBLS161` (study), `MTBLC16651` or `CHEBI:16651` (reference metabolite) | none |

### Pathways and enrichment

Curated pathways and gene-set enrichment.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [Reactome](pathways/reactome_adapter.md) | Reactome pathways and reactions through the Reactome ContentService | stable ID, e.g. `R-HSA-109581` | none |
| [KEGG](pathways/kegg_adapter.md) | KEGG pathways, genes, compounds, diseases and drugs through the public KEGG REST API | `hsa00010` (pathway), `C11378` (compound), `H00409` (disease), `D00109` (drug) | none |
| [WikiPathways](pathways/wikipathways_adapter.md) | WikiPathways community-curated pathways, searched client-side from the site's bulk JSON files (no key) | `WP254` or `WIKIPATHWAYS:WP254` | none |
| [Enrichr](pathways/enrichr_adapter.md) | Enrichr gene-set enrichment: which pathways, GO terms, phenotypes and diseases a list of genes is over-represented in… | a gene symbol or a list (`IL6 TNF IL1B`) as the search query; concept ids are `<library>::<term>` (`KEGG_2026::MALARIA`) | none (public, keyless) |

### Immunology and cell types

Cell types, marker genes, single-cell datasets and epitopes.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [Cell Ontology](ontologies/cellontology_adapter.md) | Cell Ontology (CL) cell types with synonyms, definitions, typed relations and cross-references, via EBI OLS4 | `CL:0000084`, `CL_0000084`, bare `0000084` or the full IRI `http://purl.obolibrary.org/obo/CL_0000084` | none |
| [CellMarker](ontologies/cellmarker_adapter.md) | CellMarker cell-type marker genes (human/mouse) from a lazily downloaded dataset: markers per cell type and cell types… | `CL:0000084` or a cell name, a gene symbol (`CD4`), a marker alias (`CD16`), `NCBIGene:920` | a data file you provide: `CELLMARKER_PATH`, or `CELLMARKER_URL` for a download you choose |
| [CZ CELLxGENE](ontologies/cellxgene_adapter.md) | CZ CELLxGENE Discover single-cell collections, datasets, cell types (CL), tissues (UBERON), diseases (MONDO) and… | collection / dataset UUID, cell type `CL:0000623`, tissue `UBERON:0000178`, disease `MONDO:0100233` (underscore form accepted) | none (keyless) |
| [IEDB](proteins/iedb_adapter.md) | Immune Epitope Database (IEDB) epitopes with source antigen, organism, assay counts, MHC alleles and diseases, via the… | epitope `IEDB_EPITOPE:1309147` (or bare `1309147`); antigen `UNIPROT:P0DTC2` (or bare `P0DTC2`) | none (keyless) |

### Literature and citations

Papers, preprints, citation links, text-mined entities and open-access status.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [Europe PMC](literature/europepmc_adapter.md) | Europe PMC literature search - articles and preprints with abstracts, authors and DOIs | `PMID:23193287`, `MED:23193287` or `23193287`; `PMC...` and `PPR...` IDs | none |
| [NCBI E-utilities](other/eutils_adapter.md) | NCBI E-utilities (PubMed, Gene, Protein, Taxonomy) through bioservices | `PMID:23193287`, `GeneID:672`, `TaxID:9606`, `Protein:<uid>`, `NP_000483` | `[bioservices]` extra |
| [PubTator 3](literature/pubtator_adapter.md) | PubTator 3 literature entities (genes, diseases, chemicals, variants) and text-mined relations for PubMed/PMC | `@GENE_BRCA1`, `@DISEASE_Fatigue_Syndrome_Chronic`; also MeSH (`D015673`, `MESH:D015673`) and NCBI Gene (`672`, `NCBIGene:672`) | none (keyless) |
| [LitCovid](literature/litcovid_adapter.md) | NCBI LitCovid COVID-19 and Long COVID literature with topic categories and entity annotations (keyless) | articles `PMID:34316076` (bare digits, `LITCOVID:PMID:...` and PMCIDs also accepted); topics `LITCOVID:TOPIC:Treatment` | none (keyless, JSON) |
| [OpenAlex](literature/openalex_adapter.md) | OpenAlex scholarly works, topics and citation links (keyless; optional API key and polite-pool mailto from environment… | works `W4316014106`, `OPENALEX:W...`, `https://openalex.org/W...`, DOI (`10.1038/s41579-022-00846-2`, `doi:`, `https://doi.org/...`), `PMID:36639608` (or a PubMed URL), `mag:3143129303`; topics `T11368` | none. Optional `OPENALEX_API_KEY` (free key, 10x daily budget) and `OPENALEX_MAILTO` (polite-pool address) |
| [Semantic Scholar](literature/semanticscholar_adapter.md) | Semantic Scholar papers, citations, references and TLDR summaries (keyless but heavily rate limited; optional API key) | the 40-hex `paperId` (the concept id); also `DOI:10.1038/...` / bare DOI / `https://doi.org/...`, `PMID:36639608` (bare digits are read as a PMID), `PMC9839201` / `PMCID:9839201`, `ARXIV:2006.10256`, `CorpusId:255800506`, `MAG:`, `ACL:`, `DBLP:`, `URL:` | nothing; an optional API key (`SEMANTIC_SCHOLAR_API_KEY` or `config.api_keys["semanticscholar"]`) gives a dedicated rate limit |
| [SemMedDB](literature/semmeddb_adapter.md) | SemMedDB subject-predicate-object relations extracted from PubMed, read from a local SQLite database (UMLS licence) | UMLS CUI: `C0015674`, `UMLS:C0015674` | a SQLite database built from the NLM download with `knowledge-lookup semmeddb-build`, then `SEMMEDDB_PATH` (or `api_keys={"semmeddb": "/path/file"}`, a file path rather than a secret) |
| [Crossref](literature/crossref_adapter.md) | Crossref DOI metadata, references and retraction/correction notices (keyless) | DOIs: `10.1038/s41586-020-2012-7`, `doi:10.1038/...` and `https://doi.org/10.1038/...` are all accepted (stored lower-cased) | none (keyless, JSON); optional `CROSSREF_MAILTO` for Crossref's polite pool |
| [bioRxiv / medRxiv](literature/biorxiv_adapter.md) | bioRxiv and medRxiv preprints (many Long COVID papers appear here first); preprints are not peer reviewed | preprint DOIs: `10.1101/2020.01.22.914952`, with a version (`...914952v2`), as `doi:` / `https://doi.org/` or as a biorxiv.org / medrxiv.org URL. Since 2026 medRxiv mints `10.64898/...` DOIs (e.g. `10.64898/2026.09.22.26363331`); no prefix is assumed | none (keyless, JSON) |
| [OpenCitations](literature/opencitations_adapter.md) | OpenCitations open citation links between DOIs (CC0) with citation dates, timespans and self-citation flags | DOIs `10.1038/s41586-020-2012-7` (also `doi:` and `https://doi.org/`), `pmid:32015507` (bare digits count as a PMID), `omid:br/06130344922` | none (keyless, JSON); optional access token `OPENCITATIONS_ACCESS_TOKEN` |
| [Unpaywall](literature/unpaywall_adapter.md) | Unpaywall open-access status and free full-text locations for DOIs (DOI lookups only; needs a contact e-mail you… | DOIs only: `10.1038/s41586-020-2012-7`, `doi:...`, `https://doi.org/...` (case-insensitive) | **`UNPAYWALL_EMAIL`**: your own contact e-mail address. Without it `is_available()` is `False`, no request is made and `knowledge-lookup check UNPAYWALL` reports "skipped" |
| [DOAJ](literature/doaj_adapter.md) | DOAJ, the Directory of Open Access Journals: vetted open-access journals (licence, APC, peer review, subjects) and… | journals `journal:<32-hex DOAJ id>` or `https://doaj.org/toc/<id>`, ISSN (`1932-6203`, `ISSN:`, `eISSN:`); articles `article:<id>` or `https://doaj.org/article/<id>`, DOI (`10.1371/journal.pone.0326790`, `doi:`, `https://doi.org/...`); a bare 32-hex id is tried as journal, then as article | none (keyless) |
| [OpenAIRE Graph](literature/openaire_adapter.md) | OpenAIRE research graph: publications, datasets, software and projects with funders, organisations, repositories and… | products: OpenAIRE id (`doi_dedup___::3e70f14256ea2d001e1c0b0d23f65ad1`, also `50\\|...`, `openaire:...`, explore URLs), DOI (`10.1038/s41579-022-00846-2`, `doi:`, `https://doi.org/...`), `PMID:36639608`, `PMC9839201`, `arXiv:2003.06265`; projects: `project:sfi_________::4f8b833f348de3405b0a868063f9db50` | none. Optional `OPENAIRE_ACCESS_TOKEN` (personal access token, sent only as `Authorization: Bearer`) |

### Trials, grants and datasets

Clinical-trial registries, funded projects and public omics datasets.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [ClinicalTrials.gov](literature/clinicaltrials_adapter.md) | ClinicalTrials.gov registered studies with their conditions, interventions, phase, status and enrollment | `NCT07753122` (also `ClinicalTrials:NCT07753122`, case-insensitive) | none (keyless) |
| [ISRCTN registry](literature/isrctn_adapter.md) | ISRCTN clinical trial registry (UK-based, international) | `ISRCTN54285094` (also `ISRCTN:54285094`, `isrctn 54285094`, case-insensitive) | none (keyless) |
| [NIH RePORTER](literature/nihreporter_adapter.md) | NIH RePORTER funded research projects (ME/CFS, Long COVID and every other area) with institutes, RCDC categories… | core project number `R01AI170850` (the concept id); also full project numbers `5R01AI170850-05` and application ids `APPL:11391125`, each optionally with a `NIHREPORTER:` prefix | none (keyless, JSON over POST) |
| [GEO](literature/geo_adapter.md) | NCBI Gene Expression Omnibus series, curated datasets, platforms and samples via E-utilities (metadata and URLs only) | `GSE226260` (series), `GDS5435` (curated dataset), `GPL21145` (platform), `GSM9652321` (sample); lower case and a `GEO:` prefix are accepted | none (`NCBI_API_KEY` raises the rate limit, `NCBI_EMAIL` is optional) |
| [OmicsDI](literature/omicsdi_adapter.md) | OmicsDI omics dataset discovery across ArrayExpress, PRIDE, GEO, MetaboLights, ENA and 20+ more repositories (metadata… | `<database>:<accession>` such as `geo:GSE16059`, `pride:PXD076216`, `metabolights_dataset:MTBLS161`, `biostudies-arrayexpress:E-GEOD-16059`. Bare accessions (`GSE16059`, `PXD076216`, `MSV000090685`, `MTBLS161`, `ST000450`, `E-MTAB-14669`, `PRJNA1265093`, `S-EPMC...`, `EGAS...`, `phs...`) are mapped to their repository by shape. A friendly prefix (`arrayexpress:`, `metabolights:`, `ena:`) is accepted | none (keyless, JSON) |
| [BioStudies / ArrayExpress](literature/biostudies_adapter.md) | EMBL-EBI BioStudies and ArrayExpress functional genomics studies (metadata, publications, GEO/ENA links; keyless, no… | study accession `E-GEOD-16059`, `E-MTAB-14669`, `S-EPMC7260435`; a `BIOSTUDIES:` or `ARRAYEXPRESS:` prefix is accepted | none (keyless, JSON) |
| [PRIDE](proteins/pride_adapter.md) | PRIDE Archive proteomics projects (PXD) with species, tissues, diseases, instruments, modifications and publications… | project accession `PXD076216`, `PAD000026`, `RPXD...`; a `PRIDE:` prefix and lower case are accepted | none (keyless, JSON) |
| [Zenodo](literature/zenodo_adapter.md) | Zenodo research datasets, software and publications: search, record metadata, licences and DOI links (no file downloads) | numeric record id `10576421`; also `zenodo.10576421`, `10.5281/zenodo.10576421`, `doi:...`, `https://doi.org/10.5281/zenodo.10576421` and `https://zenodo.org/records/10576421` | none (`ZENODO_ACCESS_TOKEN` is optional) |

### General knowledge

Broad knowledge graphs for names and facts that specialist sources lack.

| Adapter | Covers | Identifier example | Access |
|---|---|---|---|
| [Wikidata](other/wikidata_adapter.md) | Wikidata items via the Wikidata Query Service - labels, descriptions, UMLS and MeSH cross-references | `Q18216` | none |
| [DBpedia](other/dbpedia_adapter.md) | DBpedia resources via the public SPARQL endpoint - general knowledge from Wikipedia | resource name `Metformin` or `http://dbpedia.org/resource/Metformin` | none |
