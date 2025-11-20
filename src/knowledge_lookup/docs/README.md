# Knowledge Lookup Adapters Documentation

This directory contains documentation for all knowledge source adapters in the AID-PAIS Knowledge Graph system. Each adapter provides access to different biomedical knowledge sources and APIs.

## Available Adapters

### Major Implemented Adapters

| Adapter | Source | Description | Status |
|---------|--------|-------------|--------|
| [BioLinker](biolinker_adapter.md) | TIB BioLinker AI | AI-powered entity and relation extraction from text | ✅ Fully Implemented |
| [ChEMBL](chembl_adapter.md) | ChEMBL Database | Chemical compounds, bioactivities, and drug targets | ✅ Fully Implemented |
| [DisGeNET](disgenet_adapter.md) | DisGeNET | Gene-disease associations with evidence scores | ✅ Fully Implemented |
| [BioOntology](bioontology_adapter.md) | BioPortal | Biomedical ontology search and concept details | ✅ Fully Implemented |
| [OLS](ols_adapter.md) | EBI OLS | Ontology Lookup Service for various biomedical ontologies | ✅ Fully Implemented |
| [UMLS](umls_adapter.md) | UMLS | Unified Medical Language System concepts | ✅ Fully Implemented |
| [PubChem](pubchem_adapter.md) | PubChem | Chemical compounds and molecular properties | ✅ Partially Implemented |
| [UniProt](uniprot_adapter.md) | UniProt | Protein sequences and functional annotations | ✅ Partially Implemented |
| [MONDO](mondo_adapter.md) | Mondo Disease Ontology | Standardized disease classification | ✅ Partially Implemented |

### Stub Adapters (Not Yet Implemented)

| Adapter | Source | Description |
|---------|--------|-------------|
| DrugBank | DrugBank | Drug information and pharmacological data |
| Ensembl | Ensembl | Genome annotation and sequence data |
| OpenTargets | Open Targets | Drug target identification and validation |
| HPO | Human Phenotype Ontology | Human disease phenotypes |
| Gene Ontology | GO | Molecular functions, biological processes, cellular components |
| Reactome | Reactome | Biological pathways and reactions |
| WikiData | WikiData | General knowledge base with biomedical content |
| DBPedia | DBPedia | Structured data extracted from Wikipedia |
| OBO Foundry | OBO Foundry | Collection of biomedical ontologies |
| ZOOMA | ZOOMA | Ontology mapping and annotation |
| TYTO | TYTO | Ontology term recognition |
| OxO | OxO | Ontology cross-references |
| EBIOlsAdapter | EBI OLS | Alternative OLS implementation |

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

- **Fully Implemented**: Complete API integration with all major functions
- **Partially Implemented**: Basic search functionality, details retrieval may be limited
- **Stub**: Placeholder implementation, returns empty results

## Contributing

When adding new adapters:
1. Create adapter class inheriting from `KnowledgeSourceAdapter`
2. Implement `get_source()`, `search_concepts()`, `get_concept_details()`
3. Add comprehensive documentation following the established format
4. Include example data structures and usage patterns
5. Update this README with the new adapter information
