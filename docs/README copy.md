# Knowledge Lookup Adapters Documentation

This directory contains documentation for all knowledge source adapters in the AID-PAIS Knowledge Graph system. Each adapter provides access to different biomedical knowledge sources and APIs.

## Available Adapters

### Fully Implemented Adapters

| Adapter | Source | Description | Documentation |
|---------|--------|-------------|---------------|
| **BioLinker** | TIB BioLinker AI | AI-powered entity and relation extraction from text | [Doc](biolinker_adapter.md) |
| **ChEMBL** | ChEMBL Database | Chemical compounds, bioactivities, and drug targets | [Doc](chembl_adapter.md) |
| **DisGeNET** | DisGeNET | Gene-disease associations with evidence scores | [Doc](disgenet_adapter.md) |
| **BioOntology** | BioPortal | Biomedical ontology search and concept details | [Doc](bioontology_adapter.md) |
| **OLS** | EBI OLS | Ontology Lookup Service for biomedical ontologies | [Doc](ols_adapter.md) |
| **UMLS** | UMLS | Unified Medical Language System concepts | [Doc](umls_adapter.md) |
| **PubChem** | PubChem | Chemical compounds and molecular properties | [Doc](pubchem_adapter.md) |
| **UniProt** | UniProt | Protein sequences and functional annotations | [Doc](uniprot_adapter.md) |
| **MONDO** | Mondo Disease Ontology | Standardized disease classification | [Doc](mondo_adapter.md) |
| **DrugBank** | DrugBank | Drug information and pharmacological data | [Doc](additional_adapters.md) |
| **Ensembl** | Ensembl | Genome annotation and sequence data | [Doc](additional_adapters.md) |
| **OpenTargets** | Open Targets | Drug target identification and validation | [Doc](additional_adapters.md) |
| **HPO** | HPO | Human Phenotype Ontology terms | [Doc](additional_adapters.md) |
| **Gene Ontology** | GO | Molecular functions and biological processes | [Doc](additional_adapters.md) |
| **Reactome** | Reactome | Biological pathways and reactions | [Doc](additional_adapters.md) |
| **WikiData** | WikiData | General knowledge base with biomedical content | [Doc](additional_adapters.md) |
| **DBPedia** | DBPedia | Structured data extracted from Wikipedia | [Doc](additional_adapters.md) |
| **OBO Foundry** | OBO Foundry | Collection of biomedical ontologies | [Doc](additional_adapters.md) |
| **ZOOMA** | ZOOMA | Ontology mapping and annotation | [Doc](additional_adapters.md) |
| **TYTO** | TYTO | Ontology term recognition | [Doc](additional_adapters.md) |
| **OxO** | OxO | Ontology cross-references | [Doc](additional_adapters.md) |
| **EBI OLS** | EBI OLS | Alternative OLS implementation | [Doc](additional_adapters.md) |

## Adapter Capabilities

### Data Types Supported

- **Chemical Compounds**: ChEMBL, PubChem
- **Proteins**: UniProt, ChEMBL (targets)
- **Diseases**: DisGeNET, MONDO, OLS, BioOntology, UMLS
- **Genes**: DisGeNET, Ensembl
- **Ontologies**: OLS, BioOntology, MONDO, HPO, GO
- **Text Mining**: BioLinker (AI-powered entity extraction)
- **Pathways**: Reactome
- **General Knowledge**: WikiData, DBPedia

### Function Categories

#### Search Functions
- `search_concepts(query, limit)`: Search for concepts by text query
- Returns `List[UnifiedConcept]` or raw data structures

#### Detail Functions
- `get_concept_details(concept_id)`: Get detailed information for specific concept
- Returns `UnifiedConcept` or raw API data

#### Specialized Functions
- **DisGeNET**: `get_gene_disease_associations()`, `get_gene_disease_associations_evidence()`
- **BioLinker**: `annotate_sentence()`, `annotate_multiple_sentences()`, `search_concepts_with_depth()`
- **ChEMBL**: `query()`, `lookup_molecule()`, `get_activities_for_molecule()`

## Data Structures

### UnifiedConcept
Standardized concept representation used across adapters:

```json
{
  "primary_id": "string",
  "primary_label": "string",
  "concept_type": "DISEASE|PROTEIN|CHEMICAL|GENE|etc.",
  "semantic_types": ["array", "of", "types"],
  "confidence_score": 0.0,
  "definitions": ["array", "of", "definitions"],
  "source_data": {
    "SOURCE_NAME": {
      // Raw source-specific data
    }
  }
}
```

### Raw Data Structures
Each adapter also provides access to raw API responses for maximum flexibility.

## Usage Patterns

### Basic Search
```python
# Search for concepts
concepts = await adapter.search_concepts("diabetes", limit=10)

# Get concept details
details = await adapter.get_concept_details("MONDO_0005148")
```

### Specialized Queries
```python
# Gene-disease associations
associations = await disgenet_adapter.get_gene_disease_associations({
    "gene_ncbi_id": "7124",
    "min_score": 0.5
})

# Text annotation
annotation = await biolinker_adapter.annotate_sentence(
    "TNF-alpha causes inflammation in rheumatoid arthritis"
)
```

## Authentication Requirements

- **DisGeNET**: Requires API key
- **ChEMBL**: Optional API key for higher limits
- **BioOntology**: Optional API key for higher limits
- **All others**: Public APIs (no authentication)

## Implementation Status

- **Fully Implemented**: Complete API integration with all major functions for all 29+ listed adapters.

## Contributing

When adding new adapters:
1. Create adapter class inheriting from `KnowledgeSourceAdapter`
2. Implement `get_source()`, `search_concepts()`, `get_concept_details()`
3. Add comprehensive documentation following the established format
4. Include example data structures and usage patterns
5. Update this README with the new adapter information
