# OLS (Ontology Lookup Service) Adapter Documentation

## Overview
The OLS adapter provides access to the EMBL-EBI Ontology Lookup Service, a comprehensive repository of biomedical ontologies with advanced search and browsing capabilities.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search for concepts across all OLS-hosted ontologies.

**Parameters:**
- `query`: Search term for biomedical concepts
- `limit`: Maximum results (default: 20, max: 100)

**Returns:** `List[UnifiedConcept]` - Ontology concepts matching the query

**Example Data Structure:**
```python
{
    'primary_id': 'http://purl.obolibrary.org/obo/DOID_162',
    'primary_label': 'cancer',
    'concept_type': ConceptType.DISEASE,
    'definitions': ['A disease of cellular proliferation...'],
    'categories': ['doid - Human Disease Ontology'],
    'identifiers': [ConceptIdentifier(
        source='OLS',
        identifier='DOID:162',
        label='cancer',
        url='https://www.ebi.ac.uk/ols/ontologies/doid/terms?iri=http%3A%2F%2Fpurl.obolibrary.org%2Fobo%2FDOID_162'
    )]
}
```

#### `get_concept_details(concept_id)` [async]
Get detailed information about a specific ontology term.

**Parameters:**
- `concept_id`: Ontology term IRI (e.g., 'http://purl.obolibrary.org/obo/DOID_162')

**Returns:** `UnifiedConcept` or `None` - Detailed concept information

## Data Types and Structures

### UnifiedConcept Fields for OLS
- `primary_id`: Ontology IRI (e.g., 'http://purl.obolibrary.org/obo/DOID_162')
- `primary_label`: Preferred term label
- `concept_type`: Auto-detected concept type (DISEASE, GENE, etc.)
- `definitions`: Term definitions and descriptions
- `categories`: Ontology names with prefixes
- `identifiers`: OLS identifiers with EBI URLs
- `synonyms`: Alternative terms and labels

### Raw OLS Search Response Fields
- `iri`: Term IRI
- `label`: Term label
- `description`: Term description
- `short_form`: Compact identifier (e.g., 'DOID:162')
- `obo_id`: OBO identifier
- `ontology_name`: Source ontology name
- `ontology_prefix`: Ontology prefix (e.g., 'doid')

### Raw OLS Term Response Fields
- `iri`: Term IRI
- `label`: Term label
- `description`: Term description
- `synonyms`: List of synonyms
- `annotation`: Additional annotations
- `links`: Related term links
- `ontology`: Ontology metadata

## Supported Ontologies
OLS hosts 300+ ontologies including:
- **DOID**: Human Disease Ontology
- **GO**: Gene Ontology
- **HP**: Human Phenotype Ontology
- **MONDO**: Mondo Disease Ontology
- **UBERON**: Uber-anatomy ontology
- **CL**: Cell Ontology
- **CHEBI**: Chemical Entities of Biological Interest
- **EFO**: Experimental Factor Ontology

## Error Handling
- Public API access (no authentication required)
- HTTP error handling with aiohttp
- IRI parsing and URL encoding for term lookups
- Graceful handling of malformed responses
- Comprehensive logging of search operations

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = OLSAdapter(config)

# Search for disease concepts
diseases = await adapter.search_concepts('diabetes', limit=10)

# Get detailed concept information
concept = await adapter.get_concept_details('http://purl.obolibrary.org/obo/DOID_9351')

# Search with different ontologies
results = await adapter.search_concepts('cancer')
```

## Features
- **No API Key Required**: Publicly accessible service
- **Comprehensive Coverage**: 300+ biomedical ontologies
- **Advanced Search**: Full-text search with relevance ranking
- **Term Details**: Complete term metadata and relationships
- **Cross-References**: Links to original ontology sources
- **Auto-Detection**: Automatic concept type classification
