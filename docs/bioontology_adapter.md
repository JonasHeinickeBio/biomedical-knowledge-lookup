# BioOntology Adapter Documentation

## Overview
The BioOntology adapter provides access to the BioPortal ontology repository, offering comprehensive biomedical ontology services including concept search, term mapping, and ontology metadata.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20, raw=False)` [async]
Search for concepts across BioPortal ontologies.

**Parameters:**
- `query`: Search term for biomedical concepts
- `limit`: Maximum results (default: 20, max: 50)
- `raw`: Return raw API response instead of UnifiedConcepts

**Returns:** `List[UnifiedConcept]` - Ontology concepts matching the query

**Example Data Structure:**
```python
{
    'primary_id': 'http://purl.obolibrary.org/obo/DOID_162',
    'primary_label': 'cancer',
    'concept_type': ConceptType.DISEASE,
    'definitions': ['A disease of cellular proliferation...'],
    'categories': ['Disease Ontology (DO)'],
    'identifiers': [ConceptIdentifier(
        source='BioOntology',
        identifier='DOID:162',
        label='cancer',
        url='https://bioportal.bioontology.org/ontologies/DOID/?p=classes&conceptid=DOID%3A162'
    )]
}
```

#### `get_concept_details(concept_id, raw=False)` [async]
Get detailed information about a specific ontology concept.

**Parameters:**
- `concept_id`: Ontology concept URI or identifier
- `raw`: Return raw API response

**Returns:** `UnifiedConcept` or `None` - Detailed concept information

### Utility Methods

#### `get_analytics()` [async]
Get usage analytics and statistics for BioPortal.

**Returns:** `Dict` - Analytics data including:
- Ontology usage statistics
- Search metrics
- API usage patterns

## Data Types and Structures

### UnifiedConcept Fields for BioOntology
- `primary_id`: Ontology URI (e.g., 'http://purl.obolibrary.org/obo/DOID_162')
- `primary_label`: Preferred term label
- `concept_type`: DISEASE, GENE, ANATOMY, etc. (auto-detected)
- `definitions`: Concept definitions and descriptions
- `categories`: Ontology source names
- `identifiers`: BioPortal identifiers with URLs
- `synonyms`: Alternative terms and synonyms

### Raw API Response Fields
- `id`: Concept URI
- `prefLabel`: Preferred label
- `definition`: Concept definition
- `synonym`: List of synonyms
- `links`: Related concept links
- `ontology`: Source ontology information

## Supported Ontologies
BioPortal hosts 800+ biomedical ontologies including:
- **DOID**: Human Disease Ontology
- **GO**: Gene Ontology
- **HP**: Human Phenotype Ontology
- **MONDO**: Mondo Disease Ontology
- **UBERON**: Uber-anatomy ontology
- **CL**: Cell Ontology
- **CHEBI**: Chemical Entities of Biological Interest

## Error Handling
- API key validation and availability checks
- HTTP error handling with aiohttp
- Graceful degradation on API failures
- Comprehensive logging of search operations

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = BioOntologyAdapter(config)

# Search for disease concepts
diseases = await adapter.search_concepts('diabetes', limit=10)

# Get detailed concept information
concept = await adapter.get_concept_details('http://purl.obolibrary.org/obo/DOID_9351')

# Raw API response
raw_results = await adapter.search_concepts('cancer', raw=True)
```

## Configuration
Requires BioPortal API key in configuration:
```python
config = LookupConfig()
config.api_keys['bioontology'] = 'your_api_key_here'
# or
config.api_keys['bioportal'] = 'your_api_key_here'
```
