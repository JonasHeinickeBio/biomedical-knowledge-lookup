# Knowledge Source Adapters Documentation

This directory contains comprehensive documentation for all knowledge source adapters in the Biomedical Knowledge Lookup system. Each adapter provides access to a specific biomedical knowledge source or API.

## Available Adapters

### Core Knowledge Sources

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [ChEMBL](core/chembl_adapter.md) | [Documentation](core/chembl_adapter.md) | ChEMBL Database - Bioactivities, drug targets, compound properties |
| [DisGeNET](core/disgenet_adapter.md) | [Documentation](core/disgenet_adapter.md) | Gene-Disease Associations with evidence scores |
| [MONDO](core/mondo_adapter.md) | [Documentation](core/mondo_adapter.md) | Mondo Disease Ontology - Standardized disease classification |
| [OLS](core/ols_adapter.md) | [Documentation](core/ols_adapter.md) | Ontology Lookup Service (EBI) - General ontology search |
| [OpenTargets](core/opentargets_adapter.md) | [Documentation](core/opentargets_adapter.md) | Open Targets Platform - Drug target and disease associations |
| [UniProt](core/uniprot_adapter.md) | [Documentation](core/uniprot_adapter.md) | UniProt - Protein sequences and functional annotations |
| [UMLS](core/umls_adapter.md) | [Documentation](core/umls_adapter.md) | Unified Medical Language System - Comprehensive terminology |

### Chemicals & Compounds

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [PubChem](chemicals/pubchem_adapter.md) | [Documentation](chemicals/pubchem_adapter.md) | PubChem Compounds - Chemical compounds and properties |
| [UniChem](chemicals/unichem_adapter.md) | [Documentation](chemicals/unichem_adapter.md) | UniChem - Cross-reference between compound databases |
| [DrugBank](chemicals/drugbank_adapter.md) | [Documentation](chemicals/drugbank_adapter.md) | DrugBank - Drug and pharmaceutical information |

### Proteins & Genes

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [Ensembl](proteins/ensembl_adapter.md) | [Documentation](proteins/ensembl_adapter.md) | Ensembl Genome Annotation |
| [HGNC](proteins/hgnc_adapter.md) | [Documentation](proteins/hgnc_adapter.md) | HGNC Human Gene Nomenclature |
| [UniProt](proteins/uniprot_adapter.md) | [Documentation](proteins/uniprot_adapter.md) | UniProt - Protein sequences |

### Protein Families

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [InterPro](families/interpro_adapter.md) | [Documentation](families/interpro_adapter.md) | InterPro - Protein domains and families |
| [Pfam](families/pfam_adapter.md) | [Documentation](families/pfam_adapter.md) | Pfam - Protein family database |
| [PDB](families/pdb_adapter.md) | [Documentation](families/pdb_adapter.md) | PDB - Protein structural data |
| [STRING](families/string_adapter.md) | [Documentation](families/string_adapter.md) | STRING - Protein-protein interactions |

### Phenotypes & Annotations

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [HPO](phenotypes/hpo_adapter.md) | [Documentation](phenotypes/hpo_adapter.md) | Human Phenotype Ontology |
| [GO](phenotypes/geneontology_adapter.md) | [Documentation](phenotypes/geneontology_adapter.md) | Gene Ontology functional annotations |
| [QuickGO](phenotypes/quickgo_adapter.md) | [Documentation](phenotypes/quickgo_adapter.md) | QuickGO - GO annotations |
| [ClinVar](phenotypes/clinvar_adapter.md) | [Documentation](phenotypes/clinvar_adapter.md) | ClinVar - Genetic variations |
| [DBVar](phenotypes/dbvar_adapter.md) | [Documentation](phenotypes/dbvar_adapter.md) | DBVar - Genomic structural variation |
| [OMIM](phenotypes/omim_adapter.md) | [Documentation](phenotypes/omim_adapter.md) | OMIM - Mendelian inheritance in man |

### Ontology Services

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [BioPortal](ontologies/bioportal_adapter.md) | [Documentation](ontologies/bioportal_adapter.md) | NCBI BioPortal Ontology Service |
| [BioOntology](ontologies/bioontology_adapter.md) | [Documentation](ontologies/bioontology_adapter.md) | BioOntology API (NCBO) |
| [OBOFoundry](ontologies/obofoundry_adapter.md) | [Documentation](ontologies/obofoundry_adapter.md) | OBO Foundry Ontologies |
| [ZOOMA](ontologies/zooma_adapter.md) | [Documentation](ontologies/zooma_adapter.md) | Ontology Mapping Service |
| [EBI OLS](ontologies/ebiols_adapter.md) | [Documentation](ontologies/ebiols_adapter.md) | EBI Ontology Lookup Service |

### Pathways & Networks

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [Reactome](pathways/reactome_adapter.md) | [Documentation](pathways/reactome_adapter.md) | Reactome - Biological Pathways |
| [KEGG](pathways/kegg_adapter.md) | [Documentation](pathways/kegg_adapter.md) | KEGG - Pathways and diseases |

### Literature & Publications

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [EuropePMC](literature/europepmc_adapter.md) | [Documentation](literature/europepmc_adapter.md) | Europe PubMed Central |
| [EUtils](other/eutils_adapter.md) | [Documentation](other/eutils_adapter.md) | NCBI Entrez Utilities (Pubmed, Gene, Protein, Taxonomy) |

### Other Services

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [WikiData](other/wikidata_adapter.md) | [Documentation](other/wikidata_adapter.md) | WikiData Knowledge Base |
| [DBPedia](other/dbpedia_adapter.md) | [Documentation](other/dbpedia_adapter.md) | DBpedia Structured Data |
| [OxO](other/oxo_adapter.md) | [Documentation](other/oxo_adapter.md) | Ontology Cross-references |
| [TYTO](other/tyto_adapter.md) | [Documentation](other/tyto_adapter.md) | Ontology Term Recognition |
| [COSMIC](other/cosmic_adapter.md) | [Documentation](other/cosmic_adapter.md) | Catalogue of Somatic Mutations in Cancer |
| [BioLinker](other/biolinker_adapter.md) | [Documentation](other/biolinker_adapter.md) | TIB BioLinker AI Entity and Relation Extraction |

## Quick Reference

### By Category

#### Diseases & Phenotypes
- **MONDO** - Standardized disease classification
- **HPO** - Human phenotype ontology
- **DisGeNET** - Gene-disease associations with evidence scores
- **ClinVar** - Genetic variations and clinical significance
- **OMIM** - Mendelian inheritance in man

#### Chemicals & Drugs
- **ChEMBL** - Bioactivities, drug targets, compound properties
- **UniChem** - Cross-reference between compound databases
- **PubChem** - Chemical compounds and molecular properties
- **DrugBank** - Drug and pharmaceutical information

#### Proteins & Genes
- **UniProt** - Protein sequences and functional annotations
- **Ensembl** - Genome annotation
- **HGNC** - Human gene nomenclature
- **InterPro** - Protein domains and families
- **Pfam** - Protein family database

#### Ontology Services
- **BioPortal** - NCBI BioPortal ontology service
- **OLS** - General ontology search
- **BioOntology** - BioPortal API wrapper
- **OBOFoundry** - OBO Foundry collection
- **ZOOMA** - Automated ontology mapping

#### Pathways & Networks
- **Reactome** - Biological pathways
- **KEGG** - Pathways and diseases
- **STRING** - Protein-protein interactions

#### Literature & Publications
- **EuropePMC** - PubMed Central literature

#### Annotations
- **GO** - Gene Ontology functional annotations
- **QuickGO** - Quick GO annotations

#### Structural Data
- **PDB** - Protein structural data
- **dbVar** - Genomic structural variation (planned)

## Documentation Structure

Each adapter documentation follows a consistent structure:

1. **Overview** - Purpose and scope
2. **Key Features** - Main capabilities
3. **API Information** - Endpoint details and authentication
4. **Key Functions** - Method signatures and parameters
5. **Data Structures** - Response formats and field descriptions
6. **Configuration** - How to configure the adapter
7. **Usage Examples** - Code snippets demonstrating common use cases
8. **Error Handling** - Common error scenarios and patterns
9. **Rate Limiting** - Rate limit considerations and best practices
10. **Architecture** - Component diagrams and data flow

## Getting Started

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

# Create lookup instance
lookup = CentralKnowledgeLookup()

# Search across multiple sources
result = await lookup.search_concepts(
    query="diabetes",
    sources=[
        KnowledgeSource.OPENTARGETS,
        KnowledgeSource.MONDO,
        KnowledgeSource.DISGENET
    ]
)

# Process results
for concept in result.concepts:
    print(f"{concept.primary_label}: {concept.concept_type.value}")
```

## Authentication

Most sources are public APIs. Some require API keys:

| Source | API Key Required | Environment Variable |
|--------|------------------|---------------------|
| BIOPORTAL | Yes (optional, higher limits) | `BIOPORTAL_API_KEY` |
| UMLS | Yes | `UMLS_API_KEY` or `UMLS_API_KEY_TU` |
| DISGENET | Yes | `DISGENET_API_KEY` |
| CHEMBL | No (optional) | `CHEMBL_API_KEY` |
| Others | No | N/A |

See `docs/guides/api_keys.md` for detailed API key setup.

## Contributing

To add documentation for a new adapter:

1. Create a markdown file in the appropriate subfolder (e.g., `core/my_adapter.md`)
2. Follow the structure of existing adapter documentation
3. Update this index with a link to your new documentation
4. Add the adapter to the main [README.md](../README.md) table

## Additional Resources

- [Main Documentation](../README.md) - Overview of all adapters
- [API Reference](../api_reference.md) - API specifications
- [Getting Started](../getting_started.md) - Installation and setup
- [API Keys Guide](../guides/api_keys.md) - API key configuration
- [Caching Guide](../guides/caching.md) - Caching configuration
- [Rate Limiting Guide](../guides/rate_limiting.md) - Rate limiting strategies
- [Error Handling Guide](../guides/error_handling.md) - Error handling patterns
