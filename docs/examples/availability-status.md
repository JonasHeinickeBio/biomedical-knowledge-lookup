---
description: Which per-source examples return data, as of the last recorded run.
---

# Availability status

Results of running every per-source example on 2026-09-15. The public services change and go down from time to time, so treat this as a snapshot.

{% hint style="info" %}
This page is generated. To refresh it, run `python docs/examples/scripts/generate_status.py` from the repository root; it also rewrites every `*_example_output.txt` and [`scripts/all_adapters_test_results.json`](scripts/all_adapters_test_results.json).
{% endhint %}

## Summary

| Status | Sources | Meaning |
| --- | ---: | --- |
| Working | 34 | search and (if the example has one) the details lookup returned data |
| Partial | 0 | only one of search and details returned data |
| No results | 0 | the adapter is available but returned nothing |
| Skipped | 2 | the adapter is not available here (API key or optional extra missing) |
| Timeout | 0 | the example did not finish within the timeout |
| Error | 0 | the example exited with an error |

Examples that need an API key print `SKIPPED` and exit cleanly when the key is not set. See [the examples overview](README.md#api-keys-and-extras) for the keys.

## By source

| Category | Source | Status | Search hits | Details | Needs | Notes |
| --- | --- | --- | ---: | --- | --- | --- |
| Core | [ChEMBL](core/chembl/chembl_example.py) | Working | 5 | found | `[chembl]` extra | Multi-word and target searches (e.g. EGFR) can exceed the 30-second per-source timeout and return nothing; molecule names and ChEMBL IDs are fast. |
| Core | [DisGeNET](core/disgenet/disgenet_example.py) | Working | 5 | n/a | `DISGENET_API_KEY` | Academic DisGeNET accounts only see curated sources; searches can return no associations. |
| Core | [Mondo](core/mondo/mondo_example.py) | Working | 5 | found |  |  |
| Core | [OLS](core/ols/ols_example.py) | Working | 1 | found |  |  |
| Core | [Open Targets](core/opentargets/opentargets_example.py) | Working | 5 | found |  |  |
| Core | [UMLS](core/umls/umls_example.py) | Working | 5 | found | `[umls]` extra and `UMLS_API_KEY` |  |
| Chemicals | [DrugBank](chemicals/drugbank/drugbank_example.py) | Working | 5 | n/a |  | MyChem.info returns names, synonyms and identifiers only (no descriptions); its DrugBank data is licensed CC BY-NC 4.0. |
| Chemicals | [PubChem](chemicals/pubchem/pubchem_example.py) | Working | 1 | found |  |  |
| Chemicals | [UniChem](chemicals/unichem/unichem_example.py) | Working | 1 | found | `[bioservices]` extra |  |
| Phenotypes | [ClinVar](phenotypes/clinvar/clinvar_example.py) | Working | 5 | found |  |  |
| Phenotypes | [Gene Ontology](phenotypes/geneontology/geneontology_example.py) | Working | 5 | found |  |  |
| Phenotypes | [HPO](phenotypes/hpo/hpo_example.py) | Working | 5 | found |  |  |
| Phenotypes | [OMIM](phenotypes/omim/omim_example.py) | Skipped |  |  | `OMIM_API_KEY` |  |
| Phenotypes | [QuickGO](phenotypes/quickgo/quickgo_example.py) | Working | 5 | found | `[bioservices]` extra |  |
| Proteins | [Ensembl](proteins/ensembl/ensembl_example.py) | Working | 1 | found |  | The symbol search is slow (often 30 seconds or more) and sometimes returns nothing; get_concept_details is fast. |
| Proteins | [HGNC](proteins/hgnc/hgnc_example.py) | Working | 5 | found |  |  |
| Proteins | [UniProt](proteins/uniprot/uniprot_example.py) | Working | 3 | found |  |  |
| Pathways | [KEGG](pathways/kegg/kegg_example.py) | Working | 5 | found |  |  |
| Pathways | [Reactome](pathways/reactome/reactome_example.py) | Working | 1 | found |  |  |
| Ontologies | [BioOntology](ontologies/bioontology/bioontology_example.py) | Working | 1 | n/a | `BIOPORTAL_API_KEY` |  |
| Ontologies | [BioPortal](ontologies/bioportal/bioportal_example.py) | Working | 1 | n/a | `BIOPORTAL_API_KEY` |  |
| Ontologies | [EBI OLS](ontologies/ebiols/ebiols_example.py) | Working | 1 | found |  |  |
| Ontologies | [OBO Foundry](ontologies/obofoundry/obofoundry_example.py) | Working | 1 | n/a |  |  |
| Ontologies | [ZOOMA](ontologies/zooma/zooma_example.py) | Working | 1 | n/a |  |  |
| Families | [InterPro](families/interpro/interpro_example.py) | Working | 5 | found |  |  |
| Families | [PDB](families/pdb/pdb_example.py) | Working | 5 | found |  |  |
| Families | [Pfam](families/pfam/pfam_example.py) | Working | 5 | found |  |  |
| Families | [STRING](families/string/string_example.py) | Working | 1 | n/a |  |  |
| Literature | [Europe PMC](literature/europepmc/europepmc_example.py) | Working | 5 | found |  |  |
| Literature | [NCBI E-utilities](literature/eutils/eutils_example.py) | Working | 5 | found | `[bioservices]` extra |  |
| Other | [BioLinker](other/biolinker/biolinker_example.py) | Working | 1 | n/a |  |  |
| Other | [COSMIC](other/cosmic/cosmic_example.py) | Skipped |  | n/a | COSMIC account credentials in `COSMIC_API_KEY` | COSMIC offers no query API (only credential-gated file downloads); the REST endpoint answers 404 even with credentials, so no results are returned. |
| Other | [DBpedia](other/dbpedia/dbpedia_example.py) | Working | 1 | found |  |  |
| Other | [OxO](other/oxo/oxo_example.py) | Working | 1 | found |  |  |
| Other | [Tyto](other/tyto/tyto_example.py) | Working | 1 | found | `[tyto]` extra | Search matches exact labels only; a label that is ambiguous within an ontology is skipped, and tyto logs an error for it. |
| Other | [Wikidata](other/wikidata/wikidata_example.py) | Working | 2 | found |  |  |
