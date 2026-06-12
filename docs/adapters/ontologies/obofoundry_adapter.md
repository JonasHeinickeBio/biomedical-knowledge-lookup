# OBOFoundry Adapter Documentation

## Overview
The OBOFoundry adapter provides access to OBO Foundry ontologies through the EBI Ontology Lookup Service. It enables querying of standardized biomedical ontologies following the OBO Foundry principles.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search OBO Foundry ontologies for concepts.

**Parameters:**
- `query`: Search term for ontology concepts
- `limit`: Maximum results (default: 20, max: 100)

**Returns:** `List[UnifiedConcept]` - OBO ontology concepts

**Example Data Structure:**
```python
{
    'primary_id': 'GO:0008150',
    'primary_label': 'biological_process',
    'concept_type': ConceptType.UNKNOWN,
    'definitions': ['A process that leads to change an organism'],
    'categories': ['Ontology: go'],
    'identifiers': [ConceptIdentifier(
        source='OBOFOUNDRY',
        identifier='GO:0008150',
        label='biological_process',
        url='http://purl.obolibrary.org/obo/GO_0008150'
    )]
}
```

#### `get_concept_details(concept_id)` [async]
Get detailed information for OBO concepts.

**Parameters:**
- `concept_id`: OBO term ID (e.g., 'GO:0008150')

**Returns:** `UnifiedConcept` or `None` - Currently returns None (limited detail support)

## Data Types and Structures

### UnifiedConcept Fields for OBOFoundry
- `primary_id`: OBO term ID (e.g., 'GO:0008150')
- `primary_label`: Term label
- `concept_type`: UNKNOWN (varies by ontology)
- `categories`: Ontology source (e.g., 'Ontology: go')
- `identifiers`: OBO identifiers with IRI URLs
- `source_data`: Raw OLS API response

### OBOFoundry-Specific Data Fields
- `short_form`: Ontology term short form
- `label`: Term label
- `iri`: Full IRI of the term
- `ontology_name`: Source ontology name
- `is_obsolete`: Status flag
- `definition`: Term definition (if available)

## API Information

**Base URL:** `https://www.ebi.ac.uk/ols4/api`

**Endpoints:**
- Search: `/search`

**Authentication:** Not required (public API)

**Rate Limits:** No explicit public rate limits documented

**Parameters:**
- `q`: Search query
- `rows`: Number of results
- `format`: Response format (json)

## Error Handling
- API connectivity validation
- Response structure validation
- IRI parsing errors
- Short form extraction failures
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = OBOFoundryAdapter(config)

# Search for ontology concepts
concepts = await adapter.search_concepts('cell death', limit=10)

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('metabolism')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = OBOFoundryAdapter(config)
```

## Features
- **OBO Foundry Compliance**: Access to ontologies following OBO principles
- **Multiple Ontologies**: Access to GO, HP, SO, CL, and 100+ others
- **Structured Search**: Semantic search across ontologies
- **Ontology Filtering**: Can identify source ontology from results
- **Cross-References**: Links to ontology IRIs
- **Moderate Confidence**: 0.8 confidence score for matches

## Architecture
The adapter queries EBI OLS which indexes OBO Foundry ontologies. It searches across all OBO ontologies and identifies the source ontology from results. Due to OLS API limitations, detailed term information is not always available.
