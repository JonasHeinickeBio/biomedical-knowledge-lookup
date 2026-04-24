# Knowledge Lookup Adapters Documentation

This directory contains documentation for all knowledge source adapters in the Biomedical Knowledge Lookup system. Each adapter provides access to different biomedical knowledge sources and APIs.

## Available Knowledge Sources

| Source | Description | Status |
|--------|-------------|--------|
| UMLS | Unified Medical Language System | Fully Implemented |
| OLS | Ontology Lookup Service (EBI) | Fully Implemented |
| BIOPORTAL | NCBO BioPortal | Fully Implemented |
| BIOONTOLOGY | BioOntology API | Fully Implemented |
| CHEMBL | ChEMBL Database | Fully Implemented |
| UNICHEM | UniChem Compound IDs | Fully Implemented |
| BIOLINKER | TIB BioLinker AI | Fully Implemented |
| DISGENET | Gene-Disease Associations | Fully Implemented |
| MONDO | Mondo Disease Ontology | Fully Implemented |
| PUBCHEM | PubChem Compounds | Fully Implemented |
| UNIPROT | UniProt Proteins | Fully Implemented |
| WIKIDATA | WikiData Knowledge Base | Fully Implemented |
| DBPEDIA | DBpedia Structured Data | Fully Implemented |
| OXO | Ontology Cross-references | Fully Implemented |
| TYTO | Ontology Term Recognition | Fully Implemented |
| ZOOMA | Ontology Mapping Service | Fully Implemented |
| OPENTARGETS | Open Targets Platform | Fully Implemented |
| REACTOME | Biological Pathways | Fully Implemented |
| DRUGBANK | Drug Information | Fully Implemented |
| GENEONTOLOGY | Gene Ontology | Fully Implemented |
| HPO | Human Phenotype Ontology | Fully Implemented |
| OBOFOUNDRY | OBO Foundry Ontologies | Fully Implemented |
| EBIOLS | EBI Ontology Lookup | Fully Implemented |
| ENSEMBL | Ensembl Genome | Fully Implemented |
| KEGG | KEGG Pathways | Fully Implemented |
| QUICKGO | QuickGO Gene Ontology | Fully Implemented |
| EUTILS | NCBI E-utilities | Fully Implemented |

## Data Coverage by Category

### Diseases & Phenotypes
- **MONDO** - Standardized disease classification
- **HPO** - Human phenotype ontology
- **DisGeNET** - Gene-disease associations with evidence scores
- **OLS/BioOntology** - General ontology search

### Chemicals & Drugs
- **ChEMBL** - Bioactivities, drug targets, compound properties
- **UniChem** - Cross-reference between compound databases
- **PubChem** - Chemical compounds and molecular properties
- **DrugBank** - Drug information and pharmacology

### Proteins & Genes
- **UniProt** - Protein sequences and functional annotations
- **Ensembl** - Genome annotation
- **DisGeNET** - Gene-disease associations

### Ontology Services
- **OLS** - General ontology search
- **BioOntology** - BioPortal API wrapper
- **OBOFoundry** - OBO Foundry collection
- **ZOOMA** - Automated ontology mapping

## Usage Patterns

### Basic Search
```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()
result = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.BIOPORTAL])

for concept in result.concepts:
    print(f"{concept.primary_label} ({concept.primary_id})")
```

## Authentication

Most sources are public APIs. Some require API keys:

| Source | API Key Required |
|--------|------------------|
| BIOPORTAL | Yes (optional, higher limits) |
| UMLS | Yes |
| DISGENET | Yes |
| CHEMBL | No (optional) |
| Others | No |

## Adapter Architecture

Each adapter extends `KnowledgeSourceAdapter` and implements:
- `get_source()` - Returns the `KnowledgeSource` enum value
- `search_concepts(query, limit)` - Search for matching concepts
- `get_concept_details(concept_id)` - Get detailed information

See individual adapter docs in this directory for source-specific features:

- [ChEMBL](adapters/chembl_adapter.md) - Chemical compounds and bioactivities
- [DisGeNET](adapters/disgenet_adapter.md) - Gene-disease associations
- [MONDO](adapters/mondo_adapter.md) - Disease classification
- [OLS](adapters/ols_adapter.md) - Ontology lookup
- [UniProt](adapters/uniprot_adapter.md) - Protein data
