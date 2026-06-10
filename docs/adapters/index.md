# Knowledge Source Adapters Documentation

This directory contains comprehensive documentation for all knowledge source adapters in the Biomedical Knowledge Lookup system. Each adapter provides access to a specific biomedical knowledge source or API.

## Available Adapters

### Core Knowledge Sources

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [ChEMBL](chembl_adapter.md) | [Documentation](chembl_adapter.md) | ChEMBL Database - Bioactivities, drug targets, compound properties |
| [DisGeNET](disgenet_adapter.md) | [Documentation](disgenet_adapter.md) | Gene-Disease Associations with evidence scores |
| [MONDO](mondo_adapter.md) | [Documentation](mondo_adapter.md) | Mondo Disease Ontology - Standardized disease classification |
| [OLS](ols_adapter.md) | [Documentation](ols_adapter.md) | Ontology Lookup Service (EBI) - General ontology search |
| [OpenTargets](opentargets_adapter.md) | [Documentation](opentargets_adapter.md) | Open Targets Platform - Drug target and disease associations |
| [UniProt](uniprot_adapter.md) | [Documentation](uniprot_adapter.md) | UniProt - Protein sequences and functional annotations |
| [UMLS](umls_adapter.md) | [Documentation](umls_adapter.md) | Unified Medical Language System - Comprehensive terminology |

### Chemicals & Compounds

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [PubChem](pubchem_adapter.md) | [Documentation](pubchem_adapter.md) | PubChem Compounds - Chemical compounds and properties |
| [UniChem](unichem_adapter.md) | [Documentation](unichem_adapter.md) | UniChem - Cross-reference between compound databases |

### Proteins & Genes

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [Ensembl](additional_adapters.md#ensembl-adapter) | [Additional Adapters](additional_adapters.md#ensembl-adapter) | Ensembl Genome Annotation |
| [HGNC](additional_adapters.md#hgnc-adapter) | [Additional Adapters](additional_adapters.md#hgnc-adapter) | Human Gene Nomenclature Committee |

### Ontology Services

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [BioOntology](bioontology_adapter.md) | [Documentation](bioontology_adapter.md) | BioOntology API (NCBO) |
| [EBIOLS](additional_adapters.md#ebi-ols-alternative-adapter) | [Additional Adapters](additional_adapters.md#ebi-ols-alternative-adapter) | EBI Ontology Lookup Service (Alternative) |
| [OBOFoundry](additional_adapters.md#obo-foundry-adapter) | [Documentation](additional_adapters.md#obo-foundry-adapter) | OBO Foundry Ontologies |

### Pathways & Networks

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [Reactome](additional_adapters.md#reactome-adapter) | [Documentation](additional_adapters.md#reactome-adapter) | Reactome - Biological Pathways |

### Phenotypes & Annotations

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [HPO](additional_adapters.md#hpo-human-phenotype-ontology-adapter) | [Documentation](additional_adapters.md#hpo-human-phenotype-ontology-adapter) | Human Phenotype Ontology |
| [GO](additional_adapters.md#gene-ontology-go-adapter) | [Documentation](additional_adapters.md#gene-ontology-go-adapter) | Gene Ontology |

### Other Services

| Adapter | Documentation | Description |
|---------|--------------|-------------|
| [WikiData](additional_adapters.md#wikidata-adapter) | [Documentation](additional_adapters.md#wikidata-adapter) | WikiData Knowledge Base |
| [DBPedia](additional_adapters.md#dbpedia-adapter) | [Documentation](additional_adapters.md#dbpedia-adapter) | DBpedia Structured Data |
| [OxO](additional_adapters.md#oxo-adapter) | [Documentation](additional_adapters.md#oxo-adapter) | Ontology Cross-references |
| [TYTO](additional_adapters.md#tyto-adapter) | [Documentation](additional_adapters.md#tyto-adapter) | Ontology Term Recognition |
| [ZOOMA](additional_adapters.md#zooma-adapter) | [Documentation](additional_adapters.md#zooma-adapter) | Ontology Mapping Service |

## Quick Reference

### By Category

#### Diseases & Phenotypes
- **MONDO** - Standardized disease classification
- **HPO** - Human phenotype ontology (via Additional Adapters)
- **DisGeNET** - Gene-disease associations with evidence scores

#### Chemicals & Drugs
- **ChEMBL** - Bioactivities, drug targets, compound properties
- **UniChem** - Cross-reference between compound databases
- **PubChem** - Chemical compounds and molecular properties

#### Proteins & Genes
- **UniProt** - Protein sequences and functional annotations
- **Ensembl** - Genome annotation (via Additional Adapters)
- **DisGeNET** - Gene-disease associations

#### Ontology Services
- **OLS** - General ontology search
- **BioOntology** - BioPortal API wrapper
- **OBOFoundry** - OBO Foundry collection
- **ZOOMA** - Automated ontology mapping

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

## Contributing

To add documentation for a new adapter:

1. Create a markdown file in this directory (e.g., `my_adapter.md`)
2. Follow the structure of existing adapter documentation
3. Update this index with a link to your new documentation
4. Add the adapter to the main [README.md](../README.md) table

## Additional Resources

- [Main Documentation](../README.md) - Overview of all adapters
- [API Reference](../api_reference.md) - API specifications
- [Getting Started](../getting_started.md) - Installation and setup
