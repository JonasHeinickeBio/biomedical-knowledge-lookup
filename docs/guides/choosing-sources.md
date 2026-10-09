---
description: Which of the 106 sources to use for which question, what each one gives back, and which need a key, a download or a licence.
---

# Which source for which question

There are 106 adapters, and no single one answers everything. This page starts from the **question** you have and points to the sources that answer it. The examples use ME/CFS and Long COVID because that is the research the library grew out of, but the pattern is the same for any disease area.

{% hint style="info" %}
Every number on this page was measured against the live APIs; see [What each source returns](data-coverage.md) for the evidence and the raw field names.
{% endhint %}

## By question

### "I have a name; what are its codes?"

| Need | Use | Example result |
|---|---|---|
| a MeSH heading and tree | [MeSH](../adapters/ontologies/mesh_adapter.md) | "chronic fatigue syndrome" gives `D015673` with 35 allowed qualifiers |
| a UMLS CUI and its cross-references | [MedGen](../adapters/phenotypes/medgen_adapter.md), [UMLS](../adapters/core/umls_adapter.md) (key) | `C0015674` with 7 cross-references |
| an NCI Thesaurus concept | [NCI EVS](../adapters/ontologies/ncievs_adapter.md) | "fatigue" gives `NCIT:C3036` with 29 mappings and 134 relations |
| ICD-10-CM codes | [Clinical Tables](../adapters/ontologies/clinicaltables_adapter.md) | `R53.83` "Other fatigue" |
| SNOMED CT, LOINC or any FHIR code system | [FHIR terminology server](../adapters/ontologies/fhirterminology_adapter.md) | `snomed\|84229001` Fatigue (tx.fhir.org) |
| German ICD-10-GM, ICD-11, LOINC with the official sources | [ICD-10-GM](../adapters/ontologies/icd10gm_adapter.md), [ICD-11](../adapters/ontologies/icd11_adapter.md), [LOINC](../adapters/ontologies/loinc_adapter.md) | need a file or free account |
| every equivalent identifier at once | [Node Normalizer](../adapters/ontologies/nodenorm_adapter.md), [OxO](../adapters/other/oxo_adapter.md) | 13 equivalent identifiers for "diabetes mellitus" |
| drug classes (ATC) | [RxClass](../adapters/chemicals/rxclass_adapter.md) | aspirin: 6 classification mappings |

### "What phenotypes, genes and diseases belong together?"

| Need | Use |
|---|---|
| disease to phenotype with frequencies | [HPO annotations](../adapters/phenotypes/hpoa_adapter.md) (50 edges for Marfan), [Orphanet](../adapters/phenotypes/orphanet_adapter.md) (60) |
| gene-disease evidence | [Open Targets](../adapters/core/opentargets_adapter.md), [DisGeNET](../adapters/core/disgenet_adapter.md) (key), [GenCC](../adapters/phenotypes/gencc_adapter.md), [ClinGen](../adapters/phenotypes/clingen_adapter.md), [PanelApp](../adapters/phenotypes/panelapp_adapter.md) |
| a graph across genes, diseases and phenotypes | [Monarch](../adapters/phenotypes/monarch_adapter.md) (30 edges for BRCA1) |
| GWAS hits for a trait | [GWAS Catalog](../adapters/phenotypes/gwascatalog_adapter.md): ME/CFS resolves to `MONDO:0005404` |
| plain-language health information | [MedlinePlus](../adapters/literature/medlineplus_adapter.md) |

{% hint style="warning" %}
ME/CFS is **not** in `phenotype.hpoa`, so [HPO annotations](../adapters/phenotypes/hpoa_adapter.md) is shown with a rare disease in the coverage tables. Use Monarch, MedGen or GWAS Catalog for ME/CFS itself.
{% endhint %}

### "Tell me about this gene or variant"

| Need | Use |
|---|---|
| the canonical symbol and IDs | [HGNC](../adapters/proteins/hgnc_adapter.md), [NCBI Gene](../adapters/proteins/ncbigene_adapter.md) (53 edges, 5 mappings), [MyGene.info](../adapters/proteins/mygeneinfo_adapter.md) (25 mappings) |
| cross-references to everything | [Ensembl](../adapters/proteins/ensembl_adapter.md): 90 mappings for BRCA1 |
| where it is expressed | [GTEx](../adapters/proteins/gtex_adapter.md), [Human Protein Atlas](../adapters/proteins/hpa_adapter.md) |
| variants and frequencies | [ClinVar](../adapters/phenotypes/clinvar_adapter.md), [dbSNP](../adapters/phenotypes/dbsnp_adapter.md) (22 mappings for `rs1801133`), [gnomAD](../adapters/phenotypes/gnomad_adapter.md) |
| model organisms | [IMPC](../adapters/phenotypes/impc_adapter.md), [Alliance of Genome Resources](../adapters/proteins/alliance_adapter.md) (32 edges) |
| what it does | [Gene Ontology](../adapters/phenotypes/geneontology_adapter.md), [Reactome](../adapters/pathways/reactome_adapter.md), [KEGG](../adapters/pathways/kegg_adapter.md), [Enrichr](../adapters/pathways/enrichr_adapter.md) |
| the protein | [UniProt](../adapters/core/uniprot_adapter.md), [AlphaFold DB](../adapters/proteins/alphafold_adapter.md), [STRING](../adapters/families/string_adapter.md), [IntAct](../adapters/proteins/intact_adapter.md) (25 edges, 59 mappings) |

### "What do we know about this drug?"

| Need | Use |
|---|---|
| names, ingredients and brands | [RxNorm](../adapters/chemicals/rxnorm_adapter.md): 76 relations for aspirin |
| indications, warnings, adverse reactions on the label | [openFDA drug labels](../adapters/chemicals/openfdalabels_adapter.md) |
| reported adverse events | [openFDA events (FAERS)](../adapters/chemicals/openfdaevents_adapter.md), [SIDER](../adapters/chemicals/sider_adapter.md), [OFFSIDES](../adapters/chemicals/offsides_adapter.md) |
| targets and interactions | [ChEMBL](../adapters/core/chembl_adapter.md), [DGIdb](../adapters/chemicals/dgidb_adapter.md), [ClinPGx](../adapters/chemicals/clinpgx_adapter.md) |
| chemical-gene-disease links | [CTD](../adapters/chemicals/ctd_adapter.md) |

### "Which metabolites and studies exist?"

[MetaboLights](../adapters/chemicals/metabolights_adapter.md) returns the study *Metabolic profiling reveals anomalous energy metabolism and oxidative stress pathways* for "chronic fatigue" with 41 measured compounds. [Metabolomics Workbench](../adapters/chemicals/metabolomicsworkbench_adapter.md) resolves "lactate" to RefMet names and 50 related records. [ChEBI](../adapters/chemicals/chebi_adapter.md), [LIPID MAPS](../adapters/chemicals/lipidmaps_adapter.md) and [Rhea](../adapters/chemicals/rhea_adapter.md) give structures, lipid classes and reactions.

### "Which public datasets exist?"

[GEO](../adapters/literature/geo_adapter.md) (53 relations for the ME/CFS query), [OmicsDI](../adapters/literature/omicsdi_adapter.md), [BioStudies](../adapters/literature/biostudies_adapter.md), [PRIDE](../adapters/proteins/pride_adapter.md) and [Zenodo](../adapters/literature/zenodo_adapter.md) return accessions (`GSE...`, `PXD...`, `E-GEOD-...`), titles and links. OmicsDI spans several repositories at once; start there.

### "Which papers, trials and grants?"

| Need | Use |
|---|---|
| general literature | [Europe PMC](../adapters/literature/europepmc_adapter.md), [OpenAlex](../adapters/literature/openalex_adapter.md) (25 cites, 25 cited-by), [Semantic Scholar](../adapters/literature/semanticscholar_adapter.md) (free key advised) |
| Long COVID specifically | [LitCovid](../adapters/literature/litcovid_adapter.md), [bioRxiv / medRxiv](../adapters/literature/biorxiv_adapter.md) |
| text-mined genes, diseases, chemicals | [PubTator 3](../adapters/literature/pubtator_adapter.md), [SemMedDB](../adapters/literature/semmeddb_adapter.md) (local database) |
| citation links and open access | [OpenCitations](../adapters/literature/opencitations_adapter.md) (114 links for one paper), [Crossref](../adapters/literature/crossref_adapter.md), [Unpaywall](../adapters/literature/unpaywall_adapter.md) (DOI only) |
| trials | [ClinicalTrials.gov](../adapters/literature/clinicaltrials_adapter.md), [ISRCTN](../adapters/literature/isrctn_adapter.md) |
| funded projects | [NIH RePORTER](../adapters/literature/nihreporter_adapter.md): 61 relations for "myalgic encephalomyelitis" |

### "Which immune cells and epitopes?"

[Cell Ontology](../adapters/ontologies/cellontology_adapter.md) gives cell types with parents and children, [CELLxGENE](../adapters/ontologies/cellxgene_adapter.md) links them to single-cell datasets, [CellMarker](../adapters/ontologies/cellmarker_adapter.md) to marker genes (you supply the file), and [IEDB](../adapters/proteins/iedb_adapter.md) holds epitopes and assays.

## What you need before a source works

Most sources need nothing. The ones that do:

| Needs | Sources |
|---|---|
| **A free key** | [BioPortal](../adapters/ontologies/bioportal_adapter.md) and [BioOntology](../adapters/ontologies/bioontology_adapter.md) (`BIOPORTAL_API_KEY`), [UMLS](../adapters/core/umls_adapter.md) (`UMLS_API_KEY` and the `[umls]` extra), [DisGeNET](../adapters/core/disgenet_adapter.md) (`DISGENET_API_KEY`), [OMIM](../adapters/phenotypes/omim_adapter.md) (`OMIM_API_KEY`), [Semantic Scholar](../adapters/literature/semanticscholar_adapter.md) (optional, lifts the rate limit) |
| **A free account** | [WHO ICD-11](../adapters/ontologies/icd11_adapter.md) (`ICD11_CLIENT_ID`/`SECRET`), [LOINC](../adapters/ontologies/loinc_adapter.md) (`LOINC_USERNAME`/`PASSWORD`) |
| **A contact e-mail you choose** | [Unpaywall](../adapters/literature/unpaywall_adapter.md) (`UNPAYWALL_EMAIL`) |
| **A pip extra** | `[chembl]` ChEMBL, `[bioservices]` UniChem, QuickGO and NCBI E-utilities, `[tyto]` Tyto |
| **An opt-in download** | [HPO annotations](../adapters/phenotypes/hpoa_adapter.md) (~36 MB), [SIDER](../adapters/chemicals/sider_adapter.md) (~5.5 MB), [OFFSIDES](../adapters/chemicals/offsides_adapter.md) (~69 MB), [CTD](../adapters/chemicals/ctd_adapter.md) (~220 MB), [ClinGen](../adapters/phenotypes/clingen_adapter.md) (~1.4 MB), [GenCC](../adapters/phenotypes/gencc_adapter.md) (~28 MB): set `<NAME>_DOWNLOAD=1`, or `KNOWLEDGE_LOOKUP_ALLOW_DOWNLOADS=1` for all |
| **A file you provide** | [ICD-10-GM](../adapters/ontologies/icd10gm_adapter.md) (`ICD10GM_CLAML_PATH`), [CellMarker](../adapters/ontologies/cellmarker_adapter.md) (`CELLMARKER_PATH`), [SemMedDB](../adapters/literature/semmeddb_adapter.md) (`SEMMEDDB_PATH`, built with `knowledge-lookup semmeddb-build`) |

{% hint style="success" %}
Nothing is downloaded unless you ask for it. A dataset-backed source reports itself unavailable until you opt in, and `knowledge-lookup check <SOURCE>` tells you which variable to set.
{% endhint %}

## Terms of use worth knowing

The library does not change a source's licence; you still have to follow it.

* **Non-commercial or restricted:** [CTD](../adapters/chemicals/ctd_adapter.md) (non-commercial), [PanelApp](../adapters/phenotypes/panelapp_adapter.md) (terms exclude commercial and diagnostic use), [NCI EVS](../adapters/ontologies/ncievs_adapter.md) (NCIM, SNOMED CT and MedDRA texts), [SNOMED CT](../adapters/ontologies/snomedct_adapter.md) (national licence; the public server is for light use), [UMLS](../adapters/core/umls_adapter.md) (UMLS licence) and [SemMedDB](../adapters/literature/semmeddb_adapter.md) (UMLS licence).
* **Share-alike or attribution:** [SIDER](../adapters/chemicals/sider_adapter.md) (CC BY-SA 4.0, frozen in 2016), [ClinPGx](../adapters/chemicals/clinpgx_adapter.md) (CC BY-SA), [Human Protein Atlas](../adapters/proteins/hpa_adapter.md) (CC BY 4.0).
* **Your data leaves your machine:** [Enrichr](../adapters/pathways/enrichr_adapter.md) uploads the gene list to maayanlab.cloud, which stores it. Do not send identifiable or unpublished data.
* **Daily budgets without a key:** [openFDA](../adapters/chemicals/openfdalabels_adapter.md) allows about 1,000 requests per day; [Semantic Scholar](../adapters/literature/semanticscholar_adapter.md) rate-limits keyless search heavily.

Each adapter page has a "Rate limits and licence" section with the details.

## Combining sources

`CentralKnowledgeLookup` searches several sources in parallel and merges the answers. Pick sources by role rather than using all of them:

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

SOURCES = [
    KnowledgeSource.MESH,        # heading and tree
    KnowledgeSource.MEDGEN,      # UMLS CUI and cross-references
    KnowledgeSource.NCIEVS,      # NCIt concept with many mappings
    KnowledgeSource.CLINICALTABLES,  # ICD-10-CM
]


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=SOURCES))
    try:
        result = await lookup.search_concepts("chronic fatigue syndrome", max_results=8)
        for concept in result.concepts:
            print(concept.primary_id, concept.primary_label, concept.sources)
        print("errors:", result.errors)
    finally:
        await lookup.close()


asyncio.run(main())
```

Always set `enabled_sources`. Creating all 106 adapters is slow, and `get_concept_details` without `source=` asks every one of them. See [Searching concepts](searching-concepts.md) and [Multi-source annotation](multi-source-annotation.md).
