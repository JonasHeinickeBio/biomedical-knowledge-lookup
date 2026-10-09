# Table of contents

* [Introduction](README.md)

## Getting started

* [Installation](getting-started/installation.md)
* [Quickstart](getting-started/quickstart.md)
* [Configuration](getting-started/configuration.md)
* [Troubleshooting and FAQ](getting-started/troubleshooting.md)
* [Upgrading to 2.0](getting-started/upgrading-to-2.0.md)

## Guides

* [Searching concepts](guides/searching-concepts.md)
* [Term expansion](guides/term-expansion.md)
* [Multi-source annotation](guides/multi-source-annotation.md)
* [CURIE management](guides/curie-management.md)
* [Caching](guides/caching.md)
* [Exporting results](guides/exporting-results.md)
* [Command-line interface](guides/cli.md)
* [Agent workflow](guides/agent-workflow.md)
* [MCP server](guides/mcp-server.md)

## Choosing sources

* [Which source for which question](guides/choosing-sources.md)
* [Recipes](guides/recipes.md)
* [What each source returns](guides/data-coverage.md)
* [All adapters](adapters/README.md)


## Sources: Ontology services and mappings

* [OLS](adapters/core/ols_adapter.md)
* [EBI OLS](adapters/ontologies/ebiols_adapter.md)
* [BioPortal](adapters/ontologies/bioportal_adapter.md)
* [BioOntology](adapters/ontologies/bioontology_adapter.md)
* [OBO Foundry](adapters/ontologies/obofoundry_adapter.md)
* [ZOOMA](adapters/ontologies/zooma_adapter.md)
* [OxO](adapters/other/oxo_adapter.md)
* [NCATS Node Normalizer and Name Resolver](adapters/ontologies/nodenorm_adapter.md)
* [UMLS](adapters/core/umls_adapter.md)
* [Tyto](adapters/other/tyto_adapter.md)
* [BioLinker](adapters/other/biolinker_adapter.md)

## Sources: Clinical terminologies and coding

* [MeSH](adapters/ontologies/mesh_adapter.md)
* [SNOMED CT (Snowstorm)](adapters/ontologies/snomedct_adapter.md)
* [WHO ICD-11](adapters/ontologies/icd11_adapter.md)
* [ICD-10-GM](adapters/ontologies/icd10gm_adapter.md)
* [LOINC](adapters/ontologies/loinc_adapter.md)
* [NCI Thesaurus (EVS)](adapters/ontologies/ncievs_adapter.md)
* [NLM Clinical Tables](adapters/ontologies/clinicaltables_adapter.md)
* [FHIR terminology server](adapters/ontologies/fhirterminology_adapter.md)
* [NCBI Taxonomy](adapters/ontologies/ncbitaxonomy_adapter.md)

## Sources: Diseases and phenotypes

* [Mondo](adapters/core/mondo_adapter.md)
* [Disease Ontology](adapters/ontologies/doid_adapter.md)
* [HPO](adapters/phenotypes/hpo_adapter.md)
* [HPO annotations (phenotype.hpoa)](adapters/phenotypes/hpoa_adapter.md)
* [Orphanet](adapters/phenotypes/orphanet_adapter.md)
* [OMIM](adapters/phenotypes/omim_adapter.md)
* [MedGen](adapters/phenotypes/medgen_adapter.md)
* [Monarch Initiative](adapters/phenotypes/monarch_adapter.md)
* [MedlinePlus](adapters/literature/medlineplus_adapter.md)
* [GenCC](adapters/phenotypes/gencc_adapter.md)
* [ClinGen](adapters/phenotypes/clingen_adapter.md)
* [PanelApp](adapters/phenotypes/panelapp_adapter.md)
* [DisGeNET](adapters/core/disgenet_adapter.md)
* [Open Targets](adapters/core/opentargets_adapter.md)
* [GWAS Catalog](adapters/phenotypes/gwascatalog_adapter.md)

## Sources: Genes, variants and expression

* [HGNC](adapters/proteins/hgnc_adapter.md)
* [NCBI Gene](adapters/proteins/ncbigene_adapter.md)
* [MyGene.info](adapters/proteins/mygeneinfo_adapter.md)
* [Ensembl](adapters/proteins/ensembl_adapter.md)
* [ClinVar](adapters/phenotypes/clinvar_adapter.md)
* [dbSNP](adapters/phenotypes/dbsnp_adapter.md)
* [gnomAD](adapters/phenotypes/gnomad_adapter.md)
* [COSMIC](adapters/other/cosmic_adapter.md)
* [GTEx](adapters/proteins/gtex_adapter.md)
* [Human Protein Atlas](adapters/proteins/hpa_adapter.md)
* [eQTL Catalogue](adapters/phenotypes/eqtlcatalogue_adapter.md)
* [Gene Ontology](adapters/phenotypes/geneontology_adapter.md)
* [QuickGO](adapters/phenotypes/quickgo_adapter.md)
* [IMPC](adapters/phenotypes/impc_adapter.md)
* [Alliance of Genome Resources](adapters/proteins/alliance_adapter.md)

## Sources: Proteins, structures and interactions

* [UniProt](adapters/core/uniprot_adapter.md)
* [AlphaFold DB](adapters/proteins/alphafold_adapter.md)
* [PDB](adapters/families/pdb_adapter.md)
* [InterPro](adapters/families/interpro_adapter.md)
* [Pfam](adapters/families/pfam_adapter.md)
* [STRING](adapters/families/string_adapter.md)
* [IntAct](adapters/proteins/intact_adapter.md)

## Sources: Drugs and pharmacology

* [DrugBank](adapters/chemicals/drugbank_adapter.md)
* [RxNorm](adapters/chemicals/rxnorm_adapter.md)
* [RxClass (ATC)](adapters/chemicals/rxclass_adapter.md)
* [ChEMBL](adapters/core/chembl_adapter.md)
* [DGIdb](adapters/chemicals/dgidb_adapter.md)
* [ClinPGx (PharmGKB)](adapters/chemicals/clinpgx_adapter.md)
* [openFDA drug labels (DailyMed)](adapters/chemicals/openfdalabels_adapter.md)
* [openFDA adverse events (FAERS)](adapters/chemicals/openfdaevents_adapter.md)
* [SIDER](adapters/chemicals/sider_adapter.md)
* [OFFSIDES](adapters/chemicals/offsides_adapter.md)
* [CTD](adapters/chemicals/ctd_adapter.md)

## Sources: Chemicals and metabolites

* [PubChem](adapters/chemicals/pubchem_adapter.md)
* [ChEBI](adapters/chemicals/chebi_adapter.md)
* [UniChem](adapters/chemicals/unichem_adapter.md)
* [LIPID MAPS](adapters/chemicals/lipidmaps_adapter.md)
* [Rhea](adapters/chemicals/rhea_adapter.md)
* [Metabolomics Workbench](adapters/chemicals/metabolomicsworkbench_adapter.md)
* [MetaboLights](adapters/chemicals/metabolights_adapter.md)

## Sources: Pathways and enrichment

* [Reactome](adapters/pathways/reactome_adapter.md)
* [KEGG](adapters/pathways/kegg_adapter.md)
* [WikiPathways](adapters/pathways/wikipathways_adapter.md)
* [Enrichr](adapters/pathways/enrichr_adapter.md)

## Sources: Immunology and cell types

* [Cell Ontology](adapters/ontologies/cellontology_adapter.md)
* [CellMarker](adapters/ontologies/cellmarker_adapter.md)
* [CZ CELLxGENE](adapters/ontologies/cellxgene_adapter.md)
* [IEDB](adapters/proteins/iedb_adapter.md)

## Sources: Literature and citations

* [Europe PMC](adapters/literature/europepmc_adapter.md)
* [NCBI E-utilities](adapters/other/eutils_adapter.md)
* [PubTator 3](adapters/literature/pubtator_adapter.md)
* [LitCovid](adapters/literature/litcovid_adapter.md)
* [OpenAlex](adapters/literature/openalex_adapter.md)
* [Semantic Scholar](adapters/literature/semanticscholar_adapter.md)
* [SemMedDB](adapters/literature/semmeddb_adapter.md)
* [Crossref](adapters/literature/crossref_adapter.md)
* [bioRxiv / medRxiv](adapters/literature/biorxiv_adapter.md)
* [OpenCitations](adapters/literature/opencitations_adapter.md)
* [Unpaywall](adapters/literature/unpaywall_adapter.md)
* [DOAJ](adapters/literature/doaj_adapter.md)
* [OpenAIRE Graph](adapters/literature/openaire_adapter.md)

## Sources: Trials, grants and datasets

* [ClinicalTrials.gov](adapters/literature/clinicaltrials_adapter.md)
* [ISRCTN registry](adapters/literature/isrctn_adapter.md)
* [NIH RePORTER](adapters/literature/nihreporter_adapter.md)
* [GEO](adapters/literature/geo_adapter.md)
* [OmicsDI](adapters/literature/omicsdi_adapter.md)
* [BioStudies / ArrayExpress](adapters/literature/biostudies_adapter.md)
* [PRIDE](adapters/proteins/pride_adapter.md)
* [Zenodo](adapters/literature/zenodo_adapter.md)

## Sources: General knowledge

* [Wikidata](adapters/other/wikidata_adapter.md)
* [DBpedia](adapters/other/dbpedia_adapter.md)

## Examples

* [Examples overview](examples/README.md)
* [Use cases](examples/use-cases.md)
* [Source availability](examples/availability-status.md)
* [Notebooks](examples/notebooks/README.md)

## Reference

* [API reference](reference/api-reference.md)
* [Architecture](reference/architecture.md)
* [Environment variables](reference/environment-variables.md)
* [Glossary](reference/glossary.md)

## Project

* [Contributing](contributing/README.md)
* [Writing an adapter](contributing/writing-an-adapter.md)
* [Changelog](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/blob/main/CHANGELOG.md)
