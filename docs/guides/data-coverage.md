# What each source returns

This page shows **what works and what data comes back** from every knowledge source, measured
against the live APIs on 2026-10-09. For each source the harvest script ran one realistic query,
fetched the first hit, and then asked for its relationships and cross-references. Nothing on
this page is copied from vendor documentation: the numbers, identifiers and field names are what
the library actually received.

**106 sources** are registered. **95 answered end to end** (search, details), 65 of them also returned relationships and 55 cross-references. 8 were not tested because they need a key, a local file or an opt-in download ([listed below](#not-tested-here)); 3 failed or returned nothing ([listed below](#did-not-answer)).

Looking for the right source for a question? Start with [Which source for which question](choosing-sources.md); this page is the evidence behind it.

## Things the harvest showed

- **Search is lexical, so the first hit is not always the canonical entity.** ChEBI answers
  "aspirin" with *aspirin trelamine*, UniProt answers "BRCA1" with a plant protein, ClinVar answers
  with a variant in a different gene. Look at all hits, or fetch by exact identifier.
- **Identifier formats differ per source** (`HP:0001250`, `ENSG00000012048`, `PMID:42826492`,
  `snomed|84229001`, `1191`). Use `get_mappings()` or the [CURIE guide](curie-management.md) to
  move between them.
- **Some sources are dataset-backed** (HPOA, SIDER, OFFSIDES, CTD, GenCC, ClinGen). They answer
  from a local copy and download nothing unless you opt in with `<NAME>_DOWNLOAD=1`.
- **Edges and cross-references vary a lot.** Ontologies with rich graphs (NCI EVS: 134 edges, UMLS:
  100) and association databases (HPOA, Orphanet, OpenCitations, NIH RePORTER) return many typed
  edges; plain lookup services (HGNC, UniProt, PubChem, Wikidata) return none, only the record.

## How to read the tables

Every adapter turns its upstream response into the same `UnifiedConcept` model, so the columns
are the same for all sources.

| Column | Meaning |
|---|---|
| **Query** | the smoke-test query (the one `knowledge-lookup check` uses) |
| **Hits** | results returned by `search_concepts(query, limit=5)` and the time it took |
| **Details** | time for `get_concept_details()` on the first hit; ✓ when a record came back |
| **Edges** | `get_relationships()`: typed links to other records (parents, genes, drugs, papers ...) |
| **Maps** | `get_mappings()`: cross-references to identifiers in other vocabularies |
| **Filled fields** | which `UnifiedConcept` fields the details call populated, with item counts |

A `0` in Edges or Maps is not an error: many sources simply do not offer that kind of data
(a literature index has no cross-references, a gene nomenclature has no parent classes). The
tables for each category show what you can expect, and the linked adapter page lists the exact
parameters.

## Try it yourself

```bash
knowledge-lookup check HPO                        # search -> details -> relationships for one source
knowledge-lookup check all                        # every source (several minutes)
poetry run python scripts/harvest_source_samples.py --out samples.json   # the data behind this page
```

```python
import asyncio
from knowledge_lookup.adapters import HPOAdapter
from knowledge_lookup import LookupConfig

async def main():
    async with HPOAdapter(LookupConfig()) as hpo:
        hit = (await hpo.search_concepts("fatigue", limit=3))[0]
        concept = await hpo.get_concept_details(hit.primary_id)
        print(concept.primary_id, concept.primary_label, concept.synonyms[:3])
        for edge in (await hpo.get_relationships(hit.primary_id))[:3]:
            print(edge["relation_label"], edge["related_id"], edge["related_name"])
        for m in (await hpo.get_mappings(hit.primary_id))[:3]:
            print(m["toSource"], m["toId"])

asyncio.run(main())
```

Relationship dicts always carry `relation_label`, `related_id`, `related_name` and `source`;
mapping dicts carry `fromId`, `toId`, `fromSource`, `toSource`, `mappingType` and `confidence`.
Anything else a source offers (scores, evidence, counts) is an extra key on the same dict, and the
raw upstream record stays available as `concept.source_data`.


## Ontology services and mappings

Search hundreds of ontologies at once and translate identifiers between them.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [OLS](../adapters/core/ols_adapter.md) | `BRCA1` | 5 (0.5 s) | 0.2 s ✓ | 1 | 0 | synonyms 9, definitions 1, identifiers 1, parents 1, categories 6 |
| [EBI OLS](../adapters/ontologies/ebiols_adapter.md) | `BRCA1` | 5 (0.2 s) | 0.1 s ✓ | 1 | 0 | synonyms 9, definitions 1, identifiers 1, parents 1, categories 6 |
| [BioPortal](../adapters/ontologies/bioportal_adapter.md) | `BRCA1` | 5 (0.7 s) | 0.2 s ✓ | 0 | 0 | identifiers 1 |
| [BioOntology](../adapters/ontologies/bioontology_adapter.md) | `BRCA1` | 5 (0.7 s) | 2.5 s ✓ | 0 | 0 | identifiers 1, categories 1, semantic_types 1 |
| [OBO Foundry](../adapters/ontologies/obofoundry_adapter.md) | `diabetes` | 5 (0.7 s) | 0.1 s ✓ | 0 | 0 | identifiers 1, categories 1 |
| [ZOOMA](../adapters/ontologies/zooma_adapter.md) | `diabetes` | 5 (0.2 s) | 1.0 s ✓ | 0 | 0 | definitions 1, identifiers 1, categories 1 |
| [OxO](../adapters/other/oxo_adapter.md) | `BRCA1` | 1 (0.3 s) | 0.1 s ✓ | 0 | 0 | identifiers 1, mappings 2 |
| [NCATS Node Normalizer and Name Resolver](../adapters/ontologies/nodenorm_adapter.md) | `diabetes mellitus` | 5 (2.2 s) | 0.6 s ✓ | 0 | 13 | synonyms 3, definitions 2, identifiers 6, semantic_types 6 |
| [UMLS](../adapters/core/umls_adapter.md) | `BRCA1` | 5 (0.9 s) | 1.6 s ✓ | 100 | 13 | synonyms 59, definitions 7, identifiers 1, parents 1, related 24, categories 23, semantic_types 1 |
| [Tyto](../adapters/other/tyto_adapter.md) | `gene` | 3 (10.8 s) | 0.0 s ✓ | 0 | 0 | identifiers 1, categories 1 |
| [BioLinker](../adapters/other/biolinker_adapter.md) | `BRCA1` | 1 (5.8 s) | 0.0 s ✓ | 0 | 0 | synonyms 1, definitions 1, identifiers 1, categories 1, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| OLS | `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/1100` BRCA1 (UNKNOWN) | `has_broader` ×1 | - | `iri`, `lang`, `description`, `synonyms`, `annotation`, `label`, `ontology_name`, `ontology_prefix` |
| EBI OLS | `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/1100` BRCA1 (UNKNOWN) | `has_broader` ×1 | - | `iri`, `lang`, `description`, `synonyms`, `annotation`, `label`, `ontology_name`, `ontology_prefix` |
| BioPortal | `http://purl.bioontology.org/ontology/LNC/LP36227-4` BRCA1 (UNKNOWN) | - | - | `prefLabel`, `synonym`, `definition`, `cui`, `semanticType`, `obsolete`, `created`, `modified` |
| BioOntology | `http://purl.bioontology.org/ontology/LNC/LP36227-4` BRCA1 (UNKNOWN) | - | - | `page`, `pageCount`, `totalCount`, `prevPage`, `nextPage`, `links`, `collection` |
| OBO Foundry | `HP_0005978` Type II diabetes mellitus (UNKNOWN) | - | - | `iri`, `lang`, `description`, `synonyms`, `annotation`, `label`, `ontology_name`, `ontology_prefix` |
| ZOOMA | `http://purl.obolibrary.org/obo/DOID_9351` diabetes (UNKNOWN) | - | - | `iri`, `lang`, `description`, `synonyms`, `annotation`, `label`, `ontology_name`, `ontology_prefix` |
| OxO | `MGI:104537` Brca1 (UNKNOWN) | - | - | `queryId`, `querySource`, `curie`, `label`, `mappingResponseList` |
| NCATS Node Normalizer and Name Resolver | `MONDO:0005015` diabetes mellitus (DISEASE) | - | MEDDRA ×3, DOID ×1, EFO ×1, UMLS ×1, MESH ×1 | `id`, `label`, `type`, `types`, `equivalent_identifiers`, `information_content`, `descriptions`, `taxa` |
| UMLS | `C0376571` BRCA1 gene (GENE) | `RQ` ×36, `RO` ×33, `SY` ×23, `CHD` ×3 | LNC ×2, MSHCZE ×1, MSHDUT ×1, HGNC ×1, MEDLINEPLUS ×1 | `semantic_types`, `definitions`, `synonyms`, `sources`, `atoms`, `relations` |
| Tyto | `https://identifiers.org/SO:0000704` gene (UNKNOWN) | - | - | `ontology`, `uri`, `label` |
| BioLinker | `C0376571` brca1 (GENE) | - | - | `surface_form`, `text_position`, `category`, `biolinker_source` |

## Clinical terminologies and coding

The code systems used in registries and health records.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [MeSH](../adapters/ontologies/mesh_adapter.md) | `chronic fatigue syndrome` | 1 (2.3 s) | 0.1 s ✓ | 40 | 0 | synonyms 10, definitions 1, identifiers 1, categories 1, semantic_types 1 |
| [NCI Thesaurus (EVS)](../adapters/ontologies/ncievs_adapter.md) | `fatigue` | 5 (1.1 s) | 0.2 s ✓ | 134 | 29 | synonyms 2, definitions 6, identifiers 2, parents 1, children 5, categories 1, semantic_types 1 |
| [NLM Clinical Tables](../adapters/ontologies/clinicaltables_adapter.md) | `fatigue` | 5 (0.8 s) | 0.1 s ✓ | 0 | 0 | identifiers 1, categories 1 |
| [FHIR terminology server](../adapters/ontologies/fhirterminology_adapter.md) | `fatigue` | 5 (2.3 s) | 0.5 s ✓ | 16 | 0 | synonyms 2, definitions 1, identifiers 2, parents 2, children 14, categories 2, semantic_types 1 |
| [NCBI Taxonomy](../adapters/ontologies/ncbitaxonomy_adapter.md) | `SARS-CoV-2` | 5 (0.8 s) | 0.8 s ✓ | 15 | 1 | synonyms 3, definitions 1, identifiers 2, categories 2, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| MeSH | `D015673` Fatigue Syndrome, Chronic (DISEASE) | `allowed_qualifier` ×35, `broader_than` ×4, `see_also` ×1 | - | `ui`, `record_type`, `tree_numbers`, `active` |
| NCI Thesaurus (EVS) | `NCIT:C3036` Fatigue (SYMPTOM) | `Disease_May_Have_Finding` ×93, `Concept_In_Subset` ×23, `has_subclass` ×5, `Has_SeroNet_Authorized_Value` ×5 | MEDDRA ×10, ICD10CM ×6, SNOMEDCT ×3, ICD10 ×3, UMLS ×1 | `terminology`, `code`, `version`, `active`, `leaf`, `concept_status` |
| NLM Clinical Tables | `ICD10CM:R53.83` Other fatigue (DISEASE) | - | - | `table`, `code` |
| FHIR terminology server | `snomed\|84229001` Fatigue (UNKNOWN) | `has_subtype` ×14, `is_a` ×2 | - | `server`, `system`, `code`, `version`, `name`, `abstract`, `properties`, `designations` |
| NCBI Taxonomy | `2901879` Severe acute respiratory syndrome coronavirus (ORGANISM) | `descendant_of` ×13, `is_a` ×1, `has_subclass` ×1 | NCBITAXON ×1 | `tax_id`, `rank`, `classification`, `parents`, `children`, `counts`, `genomic_moltype`, `secondary_tax_ids` |

## Diseases and phenotypes

Disease ontologies, phenotype annotations and gene-disease evidence.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [Mondo](../adapters/core/mondo_adapter.md) | `BRCA1` | 5 (0.4 s) | 0.1 s ✓ | 0 | 0 | synonyms 11, definitions 1, identifiers 1, categories 9 |
| [Disease Ontology](../adapters/ontologies/doid_adapter.md) | `diabetes mellitus` | 5 (0.4 s) | 0.3 s ✓ | 8 | 6 | synonyms 1, definitions 1, identifiers 2, parents 1, children 5, categories 6 |
| [HPO](../adapters/phenotypes/hpo_adapter.md) | `seizure` | 5 (0.4 s) | 0.2 s ✓ | 0 | 0 | synonyms 1, definitions 1, identifiers 1 |
| [HPO annotations (phenotype.hpoa)](../adapters/phenotypes/hpoa_adapter.md) | `marfan` | 5 (3.8 s) | 0.0 s ✓ | 50 | 0 | identifiers 2, categories 1 |
| [Orphanet](../adapters/phenotypes/orphanet_adapter.md) | `marfan` | 5 (2.1 s) | 3.6 s ✓ | 60 | 8 | synonyms 1, definitions 1, identifiers 6, parents 8, children 2, categories 2, semantic_types 1 |
| [MedGen](../adapters/phenotypes/medgen_adapter.md) | `chronic fatigue syndrome` | 1 (0.8 s) | 3.0 s ✓ | 0 | 7 | synonyms 34, definitions 1, identifiers 2, semantic_types 1 |
| [Monarch Initiative](../adapters/phenotypes/monarch_adapter.md) | `BRCA1` | 5 (0.7 s) | 3.9 s ✓ | 30 | 4 | synonyms 10, identifiers 5, categories 2, semantic_types 1 |
| [MedlinePlus](../adapters/literature/medlineplus_adapter.md) | `chronic fatigue syndrome` | 5 (0.6 s) | 0.3 s ✓ | 5 | 1 | synonyms 6, definitions 1, identifiers 3, related 1, categories 2 |
| [GenCC](../adapters/phenotypes/gencc_adapter.md) | `BRCA1` | 2 (3.0 s) | 0.0 s ✓ | 6 | 0 | definitions 1, identifiers 2, categories 1, semantic_types 1 |
| [PanelApp](../adapters/phenotypes/panelapp_adapter.md) | `ataxia` | 5 (5.0 s) | 0.5 s ✓ | 26 | 0 | synonyms 3, definitions 1, identifiers 2, categories 1 |
| [DisGeNET](../adapters/core/disgenet_adapter.md) | `BRCA1` | 5 (1.5 s) | 0.7 s ✓ | 20 | 0 | synonyms 11, identifiers 1, categories 5, semantic_types 1 |
| [Open Targets](../adapters/core/opentargets_adapter.md) | `BRCA1` | 5 (0.9 s) | 0.1 s ✓ | 20 | 0 | synonyms 21, definitions 2, identifiers 1 |
| [GWAS Catalog](../adapters/phenotypes/gwascatalog_adapter.md) | `chronic fatigue syndrome` | 1 (0.8 s) | 1.7 s ✓ | 9 | 1 | definitions 2, identifiers 2, categories 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| Mondo | `1100` BRCA1 (DISEASE) | - | - | `iri`, `lang`, `description`, `synonyms`, `annotation`, `label`, `ontology_name`, `ontology_prefix` |
| Disease Ontology | `DOID:9351` diabetes mellitus (DISEASE) | `has_subclass` ×5, `is_a` ×1, `has_phenotype` ×1, `has_symptom` ×1 | ICD10CM ×1, ICD9CM ×1, MESH ×1, NCIT ×1, SNOMEDCT_US ×1 | `iri`, `obo_id`, `label`, `in_subset`, `is_obsolete`, `term_replaced_by` |
| HPO | `HP:0032894` Seizure precipitated by febrile infection (PHENOTYPE) | - | - | `id`, `name`, `definition`, `comment`, `descendantCount`, `synonyms`, `xrefs`, `publicationReferences` |
| HPO annotations (phenotype.hpoa) | `OMIM:154700` Marfan syndrome (DISEASE) | `has_phenotype` ×50 | - | `annotations`, `phenotypes`, `excluded_phenotypes`, `inheritance`, `clinical_course`, `references`, `hpoa_version`, `hpo_version` |
| Orphanet | `ORPHA:558` Marfan syndrome (DISEASE) | `has_phenotype` ×50, `subclass_of` ×8, `has_subclass` ×2 | OMIM ×2, ICD10 ×1, ICD11 ×1, MONDO ×1, MESH ×1 | `orphacode`, `typology`, `disorder_group`, `flags`, `url`, `release_date`, `prevalence`, `average_age_of_onset` |
| MedGen | `C0015674` Myalgic encephalomeyelitis/chronic fatigue syndrome (DISEASE) | - | SNOMEDCT_US ×2, MESH ×1, NCIT ×1, GTR ×1, MONDO ×1 | `uid`, `conceptid`, `semantic_type`, `semantic_type_id`, `definition_sources`, `source_vocabularies`, `omim`, `associated_genes` |
| Monarch Initiative | `HGNC:1100` BRCA1 (GENE) | `has_phenotype` ×10, `orthologous_to` ×8, `gene_associated_with_condition` ×7, `causes` ×3 | ENSEMBL ×1, OMIM ×1, NCBIGene ×1, UniProtKB ×1 | `id`, `category`, `name`, `xref`, `synonym`, `in_taxon`, `in_taxon_label`, `file_source` |
| MedlinePlus | `MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome` Myalgic Encephalomyelitis/Chronic Fatigue Syndrome (DISEASE) | `member_of_group` ×2, `related_topic` ×1, `has_translation` ×1, `primary_institute` ×1 | MESH ×1 | `topic_id`, `url`, `language`, `meta_description`, `audience`, `groups`, `mesh`, `primary_institute` |
| GenCC | `HGNC:1100` BRCA1 (GENE) | `associated_with` ×6 | - | `url`, `n_submissions`, `n_diseases`, `submitters`, `validity_summary`, `diseases` |
| PanelApp | `488` Hereditary ataxia and cerebellar anomalies, childhood onset (DISEASE) | `has_gene` ×25, `has_relevant_disorder` ×1 | - | `version`, `version_created`, `disease_group`, `disease_sub_group`, `relevant_disorders`, `stats`, `types`, `status` |
| DisGeNET | `UMLS_C0677776` Hereditary Breast and Ovarian Cancer Syndrome (DISEASE) | `has_gene` ×20 | - | `diseaseClasses_MSH`, `diseaseClasses_UMLS_ST`, `diseaseClasses_DO`, `diseaseClasses_HPO`, `name`, `diseaseUMLSCUI`, `disease_prevalence_class`, `disease_prevalence_geo_area` |
| Open Targets | `ENSG00000012048` BRCA1 (GENE) | `associated_with_disease` ×20 | - | `id`, `approvedSymbol`, `approvedName`, `biotype`, `functionDescriptions`, `synonyms` |
| GWAS Catalog | `MONDO:0005404` myalgic encephalomeyelitis/chronic fatigue syndrome (DISEASE) | `associated_variant` ×9 | MONDO ×1 | `efo_trait`, `uri`, `efo_id`, `_links`, `gwas_counts` |

## Genes, variants and expression

Gene records, variants, population frequencies and tissue expression.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [HGNC](../adapters/proteins/hgnc_adapter.md) | `BRCA1` | 5 (0.2 s) | 0.1 s ✓ | 0 | 0 | synonyms 5, identifiers 4, categories 7, semantic_types 1 |
| [NCBI Gene](../adapters/proteins/ncbigene_adapter.md) | `BRCA1` | 5 (1.4 s) | 0.4 s ✓ | 53 | 5 | synonyms 18, definitions 1, identifiers 5, categories 3, semantic_types 1 |
| [MyGene.info](../adapters/proteins/mygeneinfo_adapter.md) | `BRCA1` | 5 (0.8 s) | 1.0 s ✓ | 38 | 25 | synonyms 18, definitions 1, identifiers 6, categories 2, semantic_types 1 |
| [Ensembl](../adapters/proteins/ensembl_adapter.md) | `BRCA1` | 1 (22.5 s) | 12.8 s ✓ | 10 | 90 | definitions 1, identifiers 1, categories 2 |
| [ClinVar](../adapters/phenotypes/clinvar_adapter.md) | `BRCA1` | 5 (0.8 s) | 0.1 s ✓ | 0 | 0 | identifiers 1, categories 4, semantic_types 2 |
| [dbSNP](../adapters/phenotypes/dbsnp_adapter.md) | `rs1801133` | 1 (0.7 s) | 0.7 s ✓ | 8 | 22 | synonyms 6, definitions 1, identifiers 2, categories 2, semantic_types 1 |
| [gnomAD](../adapters/phenotypes/gnomad_adapter.md) | `BRCA1` | 2 (0.6 s) | 0.1 s ✓ | 10 | 4 | synonyms 1, definitions 1, identifiers 4, semantic_types 1 |
| [GTEx](../adapters/proteins/gtex_adapter.md) | `BRCA1` | 2 (0.8 s) | 0.5 s ✓ | 20 | 4 | definitions 1, identifiers 3, categories 1 |
| [Human Protein Atlas](../adapters/proteins/hpa_adapter.md) | `BRCA1` | 5 (0.4 s) | 0.2 s ✓ | 20 | 3 | synonyms 5, definitions 1, identifiers 4, categories 7, semantic_types 1 |
| [eQTL Catalogue](../adapters/phenotypes/eqtlcatalogue_adapter.md) | `macrophage` | 5 (1.0 s) | 0.0 s ✓ | 27 | 1 | identifiers 1 |
| [Gene Ontology](../adapters/phenotypes/geneontology_adapter.md) | `BRCA1` | 5 (0.2 s) | 0.0 s ✓ | 0 | 0 | definitions 1, identifiers 1, categories 1 |
| [QuickGO](../adapters/phenotypes/quickgo_adapter.md) | `BRCA1` | 5 (1.1 s) | 1.4 s ✓ | 0 | 0 | definitions 1, identifiers 1 |
| [IMPC](../adapters/phenotypes/impc_adapter.md) | `Brca1` | 1 (0.4 s) | 0.3 s ✓ | 1 | 1 | synonyms 2, definitions 1, identifiers 1, categories 1, semantic_types 1 |
| [Alliance of Genome Resources](../adapters/proteins/alliance_adapter.md) | `BRCA1` | 5 (4.2 s) | 0.2 s ✓ | 32 | 10 | synonyms 23, definitions 1, identifiers 1, categories 1, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| HGNC | `HGNC:1100` BRCA1 (GENE) | - | - | `locus_group`, `gencc`, `status`, `name`, `mgd_id`, `gene_group_id`, `vega_id`, `locus_type` |
| NCBI Gene | `672` BRCA1 (GENE) | `has_transcript` ×25, `encodes` ×25, `located_on` ×2, `has_ortholog` ×1 | NCBIGENE ×1, HGNC ×1, ENSEMBL ×1, OMIM ×1, UNIPROT ×1 | `gene_id`, `symbol`, `description`, `tax_id`, `taxname`, `common_name`, `type`, `orientation` |
| MyGene.info | `NCBIGene:672` BRCA1 (GENE) | `participates_in` ×31, `ortholog` ×7 | UniProt ×11, PDB ×10, Ensembl ×1, HGNC ×1, OMIM ×1 | `HGNC`, `MIM`, `_id`, `_version`, `alias`, `ensembl`, `entrezgene`, `map_location` |
| Ensembl | `ENSG00000012048` BRCA1 (GENE) | `ortholog` ×10 | Reactome_gene ×59, Uniprot_gn ×19, MIM_MORBID ×4, ENS_LRG_gene ×1, ArrayExpress ×1 | `end`, `start`, `Transcript`, `species`, `display_name`, `logic_name`, `strand`, `assembly_name` |
| ClinVar | `ClinVar:5008101` NM_004656.4(BAP1):c.1105T>G (p.Ser369Ala) (MOLECULAR_ENTITY) | - | - | `uid`, `obj_type`, `accession`, `accession_version`, `title`, `variation_set`, `supporting_submissions`, `germline_classification` |
| dbSNP | `rs1801133` rs1801133 (MOLECULAR_ENTITY) | `has_clinical_association` ×7, `located_in` ×1 | ClinVar ×12, HGVS ×6, dbSNP ×3, NCBI ×1 | `rsid`, `requested_id`, `status`, `merged_from`, `merged_rsids`, `variant_type`, `anchor`, `created` |
| gnomAD | `ENSG00000012048` BRCA1 (GENE) | `has_variant` ×10 | HGNC ×1, NCBI ×1, OMIM ×1, Ensembl ×1 | `kind`, `gene_id`, `symbol`, `name`, `hgnc_id`, `ncbi_id`, `omim_id`, `chrom` |
| GTEx | `ENSG00000012048` BRCA1 (GENE) | `expressed_in` ×10, `has_eqtl_variant` ×10 | NCBIGene ×1, HGNC ×1, ENSEMBL ×1, HGNC.SYMBOL ×1 | `dataset`, `gencode_id`, `gencode_version`, `gene_type`, `chromosome`, `start`, `end`, `strand` |
| Human Protein Atlas | `ENSG00000012048` BRCA1 (GENE) | `expressed_in` ×10, `expressed_in_cell_type` ×10 | ENSEMBL ×1, UNIPROT ×1, HGNC ×1 | `ensembl`, `symbol`, `description`, `uniprot`, `chromosome`, `position`, `protein_class`, `evidence` |
| eQTL Catalogue | `CL:0000235` macrophage (CELL_TYPE) | `has_dataset` ×25, `profiled_in_study` ×2 | CL ×1 | `release`, `n_datasets`, `studies`, `conditions`, `quant_methods` |
| Gene Ontology | `GO:0070533` BRCA1-C complex (GENE) | - | - | `id`, `isObsolete`, `name`, `definition`, `aspect`, `usage` |
| QuickGO | `GO:0070533` BRCA1-C complex (CELLULAR_COMPONENT) | - | - | `go_aspect`, `definition`, `obsolete`, `synonyms`, `comment`, `usage`, `full_details` |
| IMPC | `MGI:104537` Brca1 (GENE) | `ortholog_of` ×1 | HGNC ×1 | `kind`, `marker_symbol`, `marker_name`, `human_gene_symbol`, `human_symbol_synonym`, `chromosome`, `strand`, `start` |
| Alliance of Genome Resources | `HGNC:1100` BRCA1 (GENE) | `has_phenotype` ×10, `associated_with_disease` ×9, `interacts_with` ×8, `ortholog_of` ×5 | UniProt ×5, RGD ×1, Ensembl ×1, NCBI Gene ×1, OMIM ×1 | `name`, `species`, `taxon`, `gene_type`, `cross_references`, `location`, `evidence_note` |

## Proteins, structures and interactions

Protein records, predicted and solved structures, families and interaction networks.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [UniProt](../adapters/core/uniprot_adapter.md) | `BRCA1` | 5 (0.3 s) | 0.0 s ✓ | 0 | 0 | synonyms 1, definitions 1, identifiers 1, categories 1 |
| [AlphaFold DB](../adapters/proteins/alphafold_adapter.md) | `BRCA1` | 1 (0.5 s) | 0.1 s ✓ | 10 | 1 | synonyms 4, definitions 1, identifiers 2, categories 1, semantic_types 1 |
| [PDB](../adapters/families/pdb_adapter.md) | `BRCA1` | 5 (1.2 s) | 0.1 s ✓ | 0 | 0 | identifiers 1, categories 1 |
| [InterPro](../adapters/families/interpro_adapter.md) | `kinase` | 5 (0.2 s) | 0.1 s ✓ | 0 | 0 | definitions 1, identifiers 1, semantic_types 1 |
| [Pfam](../adapters/families/pfam_adapter.md) | `kinase` | 5 (0.2 s) | 0.1 s ✓ | 0 | 0 | identifiers 1, semantic_types 1 |
| [STRING](../adapters/families/string_adapter.md) | `BRCA1` | 1 (0.4 s) | 0.1 s ✓ | 10 | 0 | definitions 1, identifiers 1, related 5, categories 1 |
| [IntAct](../adapters/proteins/intact_adapter.md) | `BRCA1` | 5 (0.4 s) | 0.1 s ✓ | 25 | 59 | synonyms 1, definitions 1, identifiers 3, categories 2, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| UniProt | `Q8RXD4` BRCA1 (PROTEIN) | - | - | `entryType`, `primaryAccession`, `secondaryAccessions`, `uniProtkbId`, `entryAudit`, `annotationScore`, `organism`, `proteinExistence` |
| AlphaFold DB | `AF-P38398-F1` Breast cancer type 1 susceptibility protein (PROTEIN) | `has_experimental_structure` ×9, `has_predicted_structure` ×1 | UniProt ×1 | `entry_id`, `uniprot_accession`, `uniprot_id`, `gene`, `description`, `organism`, `tax_id`, `sequence_length` |
| PDB | `PDB:2CP8` Solution structure of the RSGI RUH-046, a UBA domain from human Next to BRCA1 gene 1 prot… (PROTEIN) | - | - | `audit_author`, `citation`, `database_2`, `entry`, `exptl`, `pdbx_SG_project`, `pdbx_audit_revision_category`, `pdbx_audit_revision_details` |
| InterPro | `InterPro:IPR000023` Phosphofructokinase domain (MOLECULAR_ENTITY) | - | - | `metadata` |
| Pfam | `Pfam:PF00069` Protein kinase domain (MOLECULAR_ENTITY) | - | - | `metadata` |
| STRING | `STRING:9606.ENSP00000418960` BRCA1 (PROTEIN) | `interaction` ×10 | - | `queryIndex`, `queryItem`, `stringId`, `ncbiTaxonId`, `taxonName`, `preferredName`, `annotation` |
| IntAct | `P38398` BRCA1 (PROTEIN) | `interacts_with` ×25 | PDB ×10, Reactome ×10, RefSeq ×10, InterPro ×9, Orphanet ×7 | `interactorAc`, `interactorName`, `interactorIntactName`, `interactorPreferredIdentifier`, `interactorDescription`, `interactorAlias`, `interactorAliasNames`, `interactorAltIds` |

## Drugs and pharmacology

Drug names and classes, targets, labels, adverse events and toxicogenomics.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [DrugBank](../adapters/chemicals/drugbank_adapter.md) | `aspirin` | 5 (1.1 s) | 0.2 s ✓ | 0 | 0 | synonyms 19, identifiers 1, categories 3 |
| [RxNorm](../adapters/chemicals/rxnorm_adapter.md) | `aspirin` | 1 (1.2 s) | 0.1 s ✓ | 76 | 9 | definitions 1, identifiers 1, categories 1, semantic_types 1 |
| [RxClass (ATC)](../adapters/chemicals/rxclass_adapter.md) | `aspirin` | 2 (1.0 s) | 0.3 s ✓ | 3 | 6 | identifiers 1, categories 3, semantic_types 1 |
| [DGIdb](../adapters/chemicals/dgidb_adapter.md) | `BRCA1` | 1 (0.6 s) | 0.2 s ✓ | 25 | 9 | synonyms 12, definitions 2, identifiers 1, categories 6 |
| [ClinPGx (PharmGKB)](../adapters/chemicals/clinpgx_adapter.md) | `CYP2D6` | 1 (1.1 s) | 0.6 s ✓ | 75 | 10 | synonyms 11, definitions 1, identifiers 9, categories 2, semantic_types 1 |
| [openFDA drug labels (DailyMed)](../adapters/chemicals/openfdalabels_adapter.md) | `aspirin` | 5 (1.2 s) | 0.3 s ✓ | 8 | 6 | synonyms 1, definitions 1, identifiers 1, categories 2, semantic_types 1 |
| [openFDA adverse events (FAERS)](../adapters/chemicals/openfdaevents_adapter.md) | `aspirin` | 5 (1.9 s) | 0.4 s ✓ | 25 | 0 | identifiers 1, categories 1, semantic_types 1 |
| [SIDER](../adapters/chemicals/sider_adapter.md) | `aspirin` | 1 (1.0 s) | 0.0 s ✓ | 50 | 4 | definitions 1, identifiers 2, categories 3, semantic_types 1 |
| [OFFSIDES](../adapters/chemicals/offsides_adapter.md) | `aspirin` | 3 (37.8 s) | 0.0 s ✓ | 50 | 1 | definitions 1, identifiers 1, semantic_types 1 |
| [CTD](../adapters/chemicals/ctd_adapter.md) | `aspirin` | 5 (1.2 s) | 1.0 s ✓ | 0 | 4 | synonyms 19, definitions 1, identifiers 3, parents 1, categories 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| DrugBank | `DB00945` Acetylsalicylic acid (DRUG) | - | - | `_license`, `accession_number`, `cas`, `id`, `inchi_key`, `name`, `synonyms`, `unii` |
| RxNorm | `1191` aspirin (DRUG) | `ingredient_of` ×50, `has_tradename` ×25, `has_form` ×1 | ATC ×3, SNOMEDCT ×2, DrugBank ×1, UNII ×1, USP ×1 | `rxcui`, `name`, `synonym`, `tty`, `language`, `suppress`, `umlscui` |
| RxClass (ATC) | `1191` aspirin (DRUG) | `has_atc_class` ×3 | ATC ×6 | `kind`, `rxcui`, `tty`, `atc_classes` |
| DGIdb | `hgnc:1100` BRCA1 (GENE) | `interacts_with` ×25 | HGNC ×1, ENSEMBL ×1, NCBI ×1, ORPHANET ×1, UNIPROT ×1 | `name`, `conceptId`, `longName`, `geneAliases`, `geneCategories`, `interactions` |
| ClinPGx (PharmGKB) | `PA128` CYP2D6 (GENE) | `has_clinical_annotation` ×25, `has_guideline` ×25, `has_haplotype` ×25 | OMIM ×2, UNIPROT ×2, CTD ×1, ENSEMBL ×1, GeneCards ×1 | `objCls`, `id`, `symbol`, `name`, `alleleFile`, `alleleFunctionSource`, `amp`, `buildVersion` |
| openFDA drug labels (DailyMed) | `0058175f-3474-40c3-a046-6cfaec86d84b` Low Dose Aspirin (DRUG) | `has_pharm_class` ×6, `has_ingredient` ×1, `has_rxnorm_product` ×1 | NDC ×2, DailyMed ×1, RxNorm ×1, UNII ×1, FDA_APPLICATION ×1 | `set_id`, `spl_id`, `version`, `effective_time`, `openfda`, `sections`, `sections_truncated`, `section_names` |
| openFDA adverse events (FAERS) | `FAERS:DRUG:ASPIRIN` ASPIRIN (DRUG) | `reported_adverse_event` ×25 | - | `kind`, `term`, `caveat`, `total_reports`, `serious_reports`, `non_serious_reports` |
| SIDER | `CID100002244` aspirin (DRUG) | `has_side_effect` ×50 | ATC ×3, PUBCHEM ×1 | `stitch_flat_id`, `stitch_stereo_ids`, `pubchem_cid`, `atc_codes`, `n_side_effects`, `release` |
| OFFSIDES | `RXNORM:1191` Aspirin (DRUG) | `has_adverse_event_signal` ×50 | RXNORM ×1 | `rxnorm_id`, `n_pairs`, `n_prr_signals_ci95_above_1` |
| CTD | `MESH:D001241` Aspirin (CHEMICAL) | - | MESH ×1, CAS ×1, PUBCHEM ×1, DSSTOX ×1 | `ChemicalName`, `ChemicalID`, `CasRN`, `PubChemCID`, `DTXSID`, `InChIKey`, `TreeNumbers` |

## Chemicals and metabolites

Small molecules, lipids, reactions and metabolomics studies.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [PubChem](../adapters/chemicals/pubchem_adapter.md) | `aspirin` | 1 (2.0 s) | 0.8 s ✓ | 0 | 0 | synonyms 1, identifiers 2, categories 1 |
| [ChEBI](../adapters/chemicals/chebi_adapter.md) | `aspirin` | 5 (0.3 s) | 0.1 s ✓ | 5 | 0 | synonyms 6, identifiers 2, parents 1, categories 4, semantic_types 1 |
| [UniChem](../adapters/chemicals/unichem_adapter.md) | `BSYNRYMUTXBXSQ-UHFFFAOYSA-N` | 1 (1.3 s) | 0.6 s ✓ | 0 | 0 | identifiers 1018, categories 1017 |
| [LIPID MAPS](../adapters/chemicals/lipidmaps_adapter.md) | `cholesterol` | 5 (0.7 s) | 0.5 s ✓ | 3 | 7 | synonyms 5, definitions 1, identifiers 4, parents 1, categories 3, semantic_types 1 |
| [Rhea](../adapters/chemicals/rhea_adapter.md) | `lactate` | 5 (0.5 s) | 0.6 s ✓ | 10 | 5 | identifiers 3, categories 1, semantic_types 1 |
| [Metabolomics Workbench](../adapters/chemicals/metabolomicsworkbench_adapter.md) | `lactate` | 5 (1.9 s) | 5.8 s ✓ | 50 | 6 | synonyms 2, definitions 1, identifiers 4, categories 2 |
| [MetaboLights](../adapters/chemicals/metabolights_adapter.md) | `chronic fatigue` | 1 (0.4 s) | 0.1 s ✓ | 43 | 1 | definitions 1, identifiers 1, categories 2, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| PubChem | `2244` Aspirin (CHEMICAL) | - | - | `InformationList` |
| ChEBI | `CHEBI:759292` aspirin trelamine (CHEMICAL) | `has_role` ×4, `is_a` ×1 | - | `stars`, `formula`, `mass`, `monoisotopic_mass`, `charge`, `smiles`, `inchi`, `inchikey` |
| UniChem | `161671` UCI_161671 (CHEMICAL) | - | - | `inchi`, `sources`, `standardInchiKey`, `uci` |
| LIPID MAPS | `LMST01010001` Cholesterol (CHEMICAL) | `is_a` ×3 | PubChem ×1, ChEBI ×1, HMDB ×1, KEGG ×1, LipidBank ×1 | `regno`, `sys_name`, `abbrev`, `core`, `main_class`, `sub_class`, `formula`, `exactmass` |
| Rhea | `RHEA:19909` (S)-lactate + 2 Fe(III)-[cytochrome c] = 2 Fe(II)-[cytochrome c] + pyruvate + 2 H(+) (MOLECULAR_FUNCTION) | `has_product` ×3, `has_substrate` ×2, `has_directional_variant` ×2, `has_ec_number` ×1 | EC ×1, KEGG ×1, MetaCyc ×1, GO ×1, UniProt ×1 | `equation`, `ec`, `chebi_ids`, `chebi_names`, `pubmed`, `go`, `kegg`, `metacyc` |
| Metabolomics Workbench | `RM0135904` Lactic acid (METABOLITE) | `measured_in_study` ×50 | PUBCHEM ×1, KEGG ×1, CHEBI ×1, HMDB ×1, METACYC ×1 | `kind`, `refmet_id`, `regno`, `formula`, `exactmass`, `smiles`, `inchi_key`, `hmdb_id` |
| MetaboLights | `MTBLS161` Metabolic profiling reveals anomalous energy metabolism and oxidative stress pathways in … (STUDY) | `measures_compound` ×41, `studies_organism` ×1, `has_publication` ×1 | DOI ×1 | `kind`, `organisms`, `technology`, `factors`, `release_date`, `design_descriptors`, `tissues`, `instruments` |

## Pathways and enrichment

Curated pathways and gene-set enrichment.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [Reactome](../adapters/pathways/reactome_adapter.md) | `BRCA1` | 5 (1.1 s) | 0.1 s ✓ | 10 | 0 | definitions 1, identifiers 1 |
| [KEGG](../adapters/pathways/kegg_adapter.md) | `diabetes` | 5 (3.3 s) | 0.3 s ✓ | 0 | 4 | definitions 1, identifiers 1 |
| [WikiPathways](../adapters/pathways/wikipathways_adapter.md) | `BRCA1` | 5 (0.9 s) | 0.3 s ✓ | 0 | 0 | definitions 1, identifiers 2, categories 1 |
| [Enrichr](../adapters/pathways/enrichr_adapter.md) | `BRCA1` | 5 (3.2 s) | 1.1 s ✓ | 7 | 0 | definitions 1, identifiers 1, categories 1, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| Reactome | `R-GGA-265987` Phosphorylation of BRCA1 (BIOLOGICAL_PROCESS) | `part_of` ×7, `has_participant` ×3 | - | `dbId`, `displayName`, `stId`, `stIdVersion`, `isInDisease`, `isInferred`, `maxDepth`, `name` |
| KEGG | `H00252` Congenital nephrogenic diabetes insipidus (DISEASE) | - | OMIM ×2, ICD-11 ×1, MeSH ×1 | `raw_text` |
| WikiPathways | `WP1014` Androgen receptor signaling pathway (PATHWAY) | - | - | `id`, `url`, `name`, `species`, `revision`, `authors`, `description`, `citedIn` |
| Enrichr | `GO_Biological_Process_2025::DNA Strand Resection Involved in Replication Fork Processing (GO:0110025)` DNA Strand Resection Involved in Replication Fork Processing (GO:0110025) (BIOLOGICAL_PROCESS) | `has_member` ×7 | - | `library`, `term_id`, `n_genes`, `genes`, `truncated` |

## Immunology and cell types

Cell types, marker genes, single-cell datasets and epitopes.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [Cell Ontology](../adapters/ontologies/cellontology_adapter.md) | `T cell` | 5 (3.5 s) | 0.3 s ✓ | 25 | 6 | synonyms 5, definitions 1, identifiers 2, parents 1, children 9, categories 6 |
| [CZ CELLxGENE](../adapters/ontologies/cellxgene_adapter.md) | `natural killer cell` | 5 (3.6 s) | 0.0 s ✓ | 75 | 1 | identifiers 1 |
| [IEDB](../adapters/proteins/iedb_adapter.md) | `spike` | 5 (1.0 s) | 7.6 s ✓ | 11 | 5 | definitions 2, identifiers 3, categories 1, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| Cell Ontology | `CL:0000084` T cell (CELL_TYPE) | `has_subclass` ×9, `inverse_occurs_in` ×5, `inverse_has_primary_input` ×3, `inverse_acts_on_population_of` ×2 | BTO ×1, CALOHA ×1, FMA ×1, MESH ×1, VHOG ×1 | `iri`, `obo_id`, `label`, `in_subset`, `is_obsolete`, `term_replaced_by`, `annotation` |
| CZ CELLxGENE | `CL:0000623` natural killer cell (CELL_TYPE) | `found_in_tissue` ×25, `found_in_dataset` ×25, `has_marker_gene` ×25 | CL ×1 | `kind`, `n_datasets`, `n_collections`, `cells_in_datasets`, `top_tissues` |
| IEDB | `IEDB_EPITOPE:146741` AAAGVPFSLSVQYRI (MOLECULAR_ENTITY) | `restricted_by_mhc_allele` ×4, `has_source_antigen` ×2, `has_source_organism` ×2, `has_host_organism` ×2 | NCBITaxon ×2, UniProt ×1, NCBI Protein ×1, PubMed ×1 | `structure_type`, `linear_sequence`, `linear_sequence_length`, `antigens`, `organisms`, `tcell_assay_count`, `mhc_classes`, `mhc_alleles` |

## Literature and citations

Papers, preprints, citation links, text-mined entities and open-access status.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [Europe PMC](../adapters/literature/europepmc_adapter.md) | `BRCA1` | 5 (8.6 s) | 0.1 s ✓ | 0 | 0 | definitions 1, identifiers 2, categories 3 |
| [PubTator 3](../adapters/literature/pubtator_adapter.md) | `BRCA1` | 5 (0.6 s) | 0.4 s ✓ | 50 | 1 | identifiers 2, categories 1 |
| [LitCovid](../adapters/literature/litcovid_adapter.md) | `long covid` | 5 (0.8 s) | 0.2 s ✓ | 1 | 2 | identifiers 2, categories 3 |
| [OpenAlex](../adapters/literature/openalex_adapter.md) | `chronic fatigue syndrome` | 5 (1.0 s) | 0.2 s ✓ | 53 | 3 | synonyms 9, identifiers 3, categories 6, semantic_types 1 |
| [Semantic Scholar](../adapters/literature/semanticscholar_adapter.md) | `long covid` | 5 (1.5 s) | 2.6 s ✓ | 50 | 4 | definitions 1, identifiers 4, categories 4, semantic_types 2 |
| [Crossref](../adapters/literature/crossref_adapter.md) | `long covid` | 5 (0.9 s) | 0.4 s ✓ | 0 | 0 | definitions 1, identifiers 1, categories 4 |
| [bioRxiv / medRxiv](../adapters/literature/biorxiv_adapter.md) | `long covid` | 5 (14.6 s) | 0.7 s ✓ | 1 | 1 | definitions 1, identifiers 1, categories 5 |
| [OpenCitations](../adapters/literature/opencitations_adapter.md) | `10.1038/s41586-020-2012-7` | 1 (1.3 s) | 1.4 s ✓ | 114 | 8 | identifiers 2, categories 3 |
| [Unpaywall](../adapters/literature/unpaywall_adapter.md) | `10.1038/s41586-020-2012-7` | 1 (0.5 s) | 0.0 s ✓ | 8 | 4 | identifiers 2, categories 3, semantic_types 1 |
| [DOAJ](../adapters/literature/doaj_adapter.md) | `long covid` | 5 (0.7 s) | 0.6 s ✓ | 4 | 1 | synonyms 5, definitions 1, identifiers 2, categories 5, semantic_types 1 |
| [OpenAIRE Graph](../adapters/literature/openaire_adapter.md) | `long covid` | 5 (0.4 s) | 0.6 s ✓ | 2 | 1 | synonyms 1, definitions 1, identifiers 2, categories 1, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| Europe PMC | `PMID:42826492` The BRCA1-A complex: At the edge of resection and the beauty of restraint. (CITATION) | - | - | `id`, `source`, `pmid`, `doi`, `title`, `authorString`, `authorList`, `journalInfo` |
| PubTator 3 | `@GENE_BRCA1` BRCA1 (GENE) | `associate` ×46, `inhibit` ×2, `negative_correlate` ×1, `interact` ×1 | NCBI Gene ×1 | `_id`, `biotype`, `db_id`, `db`, `name`, `description`, `match` |
| LitCovid | `PMID:36972723` Long COVID? What is that? (CITATION) | `annotated_with_condition` ×1 | PubMed ×1, PMC ×1 | `pmid`, `pmcid`, `title`, `journal`, `year`, `date_publication`, `authors`, `volume` |
| OpenAlex | `W3143129303` Chronic fatigue syndrome (CITATION) | `cites` ×25, `cited_by` ×25, `has_topic` ×3 | DOI ×1, PMID ×1, MAG ×1 | `id`, `doi`, `pmid`, `pmcid`, `mag`, `year`, `publication_date`, `type` |
| Semantic Scholar | `e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6` Long COVID: major findings, mechanisms and recommendations (CITATION) | `cites` ×25, `cited_by` ×25 | DOI ×1, PMID ×1, PMCID ×1, CorpusId ×1 | `paperId`, `corpusId`, `title`, `year`, `venue`, `publication_date`, `publication_types`, `fields_of_study` |
| Crossref | `10.36255/long-covid-public-education` Long COVID: Public Education (CITATION) | - | - | `doi`, `title`, `container`, `date`, `year`, `type`, `publisher`, `issn` |
| bioRxiv / medRxiv | `10.64898/2026.09.22.26363331` Worsening pre-existing health conditions in U.S. adults with Long COVID (CITATION) | `has_earlier_version` ×1 | DOI ×1 | `doi`, `title`, `authors`, `corresponding_author`, `corresponding_institution`, `category`, `date`, `version` |
| OpenCitations | `10.1038/s41586-020-2012-7` A Pneumonia Outbreak Associated With A New Coronavirus Of Probable Bat Origin (CITATION) | `cited_by` ×100, `cites` ×14 | ISSN ×5, OPENALEX ×1, PubMed ×1, OMID ×1 | `ids`, `title`, `authors`, `pub_date`, `venue`, `issn`, `volume`, `issue` |
| Unpaywall | `10.1038/s41586-020-2012-7` A pneumonia outbreak associated with a new coronavirus of probable bat origin (CITATION) | `available_at` ×6, `published_in` ×1, `published_by` ×1 | ISSN ×2, DOI ×1, ISSN-L ×1 | `doi`, `title`, `genre`, `year`, `published_date`, `journal`, `journal_issns`, `journal_issn_l` |
| DOAJ | `article:0000a525710d408db4971f44da5a6e0c` IMPACT OF COVID-19 ON EUROPEAN AND TURKEY AIR TRAFFIC NETWORKS (CITATION) | `has_subject` ×3, `published_in` ×1 | DOI ×1 | `id`, `doi`, `year`, `month`, `journal`, `journal_issns`, `publisher`, `journal_country` |
| OpenAIRE Graph | `doi_________::f1f64d679d42c1024e9d4067946afbe6` Rolle psychosozialer Faktoren beim Entstehen von Long Covid (CITATION) | `hosted_by` ×1, `collected_from` ×1 | DOI ×1 | `id`, `type`, `doi`, `pmid`, `pmcid`, `arxiv`, `pids`, `publication_date` |

## Trials, grants and datasets

Clinical-trial registries, funded projects and public omics datasets.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [ClinicalTrials.gov](../adapters/literature/clinicaltrials_adapter.md) | `long covid` | 5 (0.5 s) | 0.9 s ✓ | 3 | 1 | synonyms 2, definitions 1, identifiers 1, categories 2, semantic_types 1 |
| [ISRCTN registry](../adapters/literature/isrctn_adapter.md) | `chronic fatigue` | 5 (0.3 s) | 0.3 s ✓ | 5 | 1 | synonyms 2, definitions 1, identifiers 1, categories 2, semantic_types 2 |
| [NIH RePORTER](../adapters/literature/nihreporter_adapter.md) | `myalgic encephalomyelitis` | 5 (1.2 s) | 0.2 s ✓ | 61 | 8 | definitions 2, identifiers 2, categories 9, semantic_types 1 |
| [GEO](../adapters/literature/geo_adapter.md) | `chronic fatigue syndrome` | 5 (0.8 s) | 0.2 s ✓ | 53 | 3 | definitions 1, identifiers 1, categories 1, semantic_types 2 |
| [OmicsDI](../adapters/literature/omicsdi_adapter.md) | `chronic fatigue syndrome` | 5 (0.4 s) | 0.1 s ✓ | 12 | 1 | definitions 1, identifiers 1, categories 3, semantic_types 1 |
| [BioStudies / ArrayExpress](../adapters/literature/biostudies_adapter.md) | `chronic fatigue` | 5 (0.3 s) | 0.8 s ✓ | 5 | 2 | definitions 1, identifiers 2, categories 5, semantic_types 1 |
| [PRIDE](../adapters/proteins/pride_adapter.md) | `fatigue` | 5 (0.3 s) | 0.8 s ✓ | 9 | 4 | synonyms 6, definitions 1, identifiers 2, categories 6, semantic_types 1 |
| [Zenodo](../adapters/literature/zenodo_adapter.md) | `long covid` | 5 (0.7 s) | 0.1 s ✓ | 2 | 2 | definitions 1, identifiers 2, categories 4, semantic_types 1 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| ClinicalTrials.gov | `NCT04583293` Acute KIDnEy Injury in CoviD-19 (OBSERVATIONAL_STUDY) | `studies_condition` ×2, `tests_intervention` ×1 | MeSH ×1 | `nct_id`, `brief_title`, `official_title`, `acronym`, `brief_summary`, `status`, `study_type`, `phases` |
| ISRCTN registry | `ISRCTN85256968` Sarcopenia and diabetes in elderly adults with type 2 diabetes (OBSERVATIONAL_STUDY) | `studies_condition` ×2, `tests_intervention` ×1, `has_sponsor` ×1, `funded_by` ×1 | DOI ×1 | `isrctn`, `title`, `scientific_title`, `acronym`, `summary`, `hypothesis`, `primary_outcomes`, `secondary_outcomes` |
| NIH RePORTER | `R01NS131967` Non-Invasive Multi-Modal Neuromonitoring in Adults Undergoing Extracorporeal Membrane Oxy… (STUDY) | `has_term` ×50, `has_spending_category` ×7, `has_publication` ×2, `funded_by` ×1 | NIH_PROJECT_NUMBER ×3, NIH_APPLICATION_ID ×3, PMID ×2 | `core_project_num`, `project_num`, `appl_id`, `fiscal_year`, `award_amount`, `is_active`, `activity_code`, `project_start_date` |
| GEO | `GSE327255` PTPRN2 hypomethylation and PHB2-modulated miR-153-3p maturation reveal dual epigenetic me… (STUDY) | `has_sample` ×50, `uses_platform` ×1, `has_publication` ×1, `has_organism` ×1 | PUBMED ×1, NCBITAXON ×1, BIOPROJECT ×1 | `uid`, `accession`, `entry_type`, `url`, `organisms`, `data_type`, `platforms`, `series` |
| OmicsDI | `metabolights_dataset:MTBLS161` Metabolic profiling reveals anomalous energy metabolism and oxidative stress pathways in … (STUDY) | `similar_to` ×10, `has_omics_type` ×1, `uses_instrument` ×1 | MetaboLights ×1 | `accession`, `database`, `repository`, `title`, `organisms`, `taxon_ids`, `omics_types`, `omics_types_raw` |
| BioStudies / ArrayExpress | `E-GEOD-59489` DNA methylation modifications associated with Chronic Fatigue Syndrome (STUDY) | `has_organism` ×1, `has_experiment_type` ×1, `uses_technology` ×1, `has_assay_molecule` ×1 | ArrayExpress ×1, GEO ×1 | `accession`, `title`, `collection`, `release_date`, `organisms`, `taxon_ids`, `study_types`, `technologies` |
| PRIDE | `PXD076216` Proteomic Signatures in Cerebrospinal Fluid and Their Clinical Associations in Patients w… (STUDY) | `has_modification` ×3, `has_species` ×1, `has_tissue` ×1, `has_disease` ×1 | PRIDE ×1, PubMed ×1, DOI ×1, NCBITaxon ×1 | `accession`, `title`, `keywords`, `species`, `taxon_ids`, `tissues`, `diseases`, `instruments` |
| Zenodo | `10576421` Characterising long COVID-like COVID-19 vaccine reactions (STUDY) | `has_license` ×1, `is_version_of` ×1 | DOI ×2 | `record_id`, `url`, `doi`, `concept_doi`, `concept_record_id`, `resource_type`, `resource_subtype`, `creators` |

## General knowledge

Broad knowledge graphs for names and facts that specialist sources lack.

| Source | Query | Hits | Details | Edges | Maps | Filled fields |
|---|---|---|---|---|---|---|
| [Wikidata](../adapters/other/wikidata_adapter.md) | `BRCA1` | 5 (2.0 s) | 0.2 s ✓ | 0 | 0 | definitions 1, identifiers 2, categories 2 |
| [DBpedia](../adapters/other/dbpedia_adapter.md) | `BRCA1` | 3 (0.4 s) | 0.0 s ✓ | 0 | 0 | identifiers 1, categories 3 |

**What comes back**

| Source | First hit | Edge types | Mapping targets | Raw upstream fields |
|---|---|---|---|---|
| Wikidata | `Q17487737` BRCA1 (PROTEIN) | - | - | `item`, `umlsCui`, `meshId`, `itemLabel`, `itemDescription`, `instanceOfLabel` |
| DBpedia | `BRCA1` BRCA1 (UNKNOWN) | - | - | `property`, `value` |

## Not tested here

These adapters are real, but they cannot run without something only you can provide (a licence key, a local file, or an explicit opt-in to a download).

| Source | To enable |
|---|---|
| CellMarker | CELLMARKER_PATH or CELLMARKER_URL |
| ClinGen | CLINGEN_DOWNLOAD=1 (downloads ~1.4 MB) or CLINGEN_PATH |
| COSMIC | COSMIC_API_KEY |
| ICD-10-GM | ICD10GM_CLAML_PATH |
| WHO ICD-11 | ICD11_CLIENT_ID |
| LOINC | LOINC_USERNAME |
| OMIM | OMIM_API_KEY |
| SemMedDB | SEMMEDDB_PATH (build the file with `knowledge-lookup semmeddb-build`) |

## Did not answer

These returned no usable result during the harvest. The cause is listed; most are upstream or network conditions rather than library bugs.

| Source | Status | Detail |
|---|---|---|
| ChEMBL | empty | ChEMBL's API answered HTTP 500 while the client loaded its schema (upstream outage) |
| NCBI E-utilities | failed | Python `requests` waited ~100 s on IPv6 on the test machine; works over IPv4 |
| SNOMED CT (Snowstorm) | failed | the public Snowstorm browser host was unreachable (time-out) |

---
*Generated 2026-10-09 by `scripts/build_data_coverage_doc.py` from `scripts/harvest_source_samples.py`. Latencies come from one machine and one run; treat them as orders of magnitude.*
