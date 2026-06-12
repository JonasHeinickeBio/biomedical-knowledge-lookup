# OxO (Ontology Cross-reference Service) Adapter Documentation

## Overview
The OxO adapter provides access to EBI's Ontology Cross-reference Service, enabling mapping and cross-referencing between terms across different ontologies, vocabularies, and coding standards.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=10)` [async]
Search for concepts with cross-references.

**Parameters:**
- `query`: Search term or concept ID (e.g., 'DOID:162', 'MONDO:0004992')
- `limit`: Maximum results (default: 10)

**Returns:** `List[UnifiedConcept]` - Concepts with cross-references

**Example Data Structure:**
```python
{
    'primary_id': 'DOID:162',
    'primary_label': 'Alzheimer disease',
    'concept_type': ConceptType.DISEASE,
    'identifiers': [ConceptIdentifier(
        source='OXO',
        identifier='DOID:162',
        label='Alzheimer disease',
        url='https://www.ebi.ac.uk/spot/oxo/diseasome/Disease_162'
    )],
    'mappings': [
        {
            'target_source': KnowledgeSource.MONDO,
            'target_id': 'MONDO:0004992',
            'confidence': 0.9
        }
    ],
    'confidence_score': 0.9
}
```

#### `get_concept_details(concept_id)` [async]
Get detailed information about a concept including all its mappings.

**Parameters:**
- `concept_id`: Concept identifier

**Returns:** `UnifiedConcept` or `None` - Concept with complete mappings

#### `get_concept_by_id(concept_id, **kwargs)` [async]
Get cross-references for a specific concept ID.

**Parameters:**
- `concept_id`: Concept identifier
- `distance`: Maximum mapping distance (default: 1)
- `mapping_target`: List of target ontologies
- `mapping_source`: List of source ontologies

**Returns:** `UnifiedConcept` or `None`

#### `get_mappings_for_concepts(concept_ids, **kwargs)` [async]
Get cross-reference mappings for multiple concepts.

**Parameters:**
- `concept_ids`: List of concept identifiers
- `distance`: Maximum mapping distance (default: 1)
- `mapping_target`: Target ontologies
- `mapping_source`: Source ontologies

**Returns:** `Dict[str, List[Dict]]` - Concept ID to mappings mapping

#### `get_datasources()` [async]
Get available data sources in OxO.

**Returns:** `List[Dict]` - Available data sources with metadata

## Data Types and Structures

### UnifiedConcept Fields for OxO
- `primary_id`: Concept CURIE (e.g., 'DOID:162')
- `primary_label`: Concept label
- `concept_type`: Varies by source ontology
- `identifiers`: OxO identifiers with URLs
- `mappings`: List of cross-reference mappings
- `confidence_score`: Based on mapping distance and sources
- `source_data`: Raw OxO API response

### OxO-Specific Data Fields
- `mappingResponseList`: List of mapping responses
- `curie`: Concept CURIE
- `label`: Concept label
- `targetPrefix`: Target ontology prefix
- `sourcePrefixes`: Source ontology prefixes
- `distance`: Mapping distance (1=direct, 2=one hop, etc.)

## API Information

**Base URL:** `https://www.ebi.ac.uk/spot/oxo`

**API URL:** `https://www.ebi.ac.uk/spot/oxo/api`

**Endpoints:**
- Search: `/api/search` (POST)
- Datasources: `/api/datasources`

**Authentication:** Not required (public API)

**Rate Limits:** No explicit public rate limits documented

**POST Parameters:**
- `ids`: List of concept IDs
- `distance`: Maximum mapping distance
- `mappingTarget`: Target ontologies
- `mappingSource`: Source ontologies

## Error Handling
- API connectivity validation
- POST request handling
- Response structure validation
- CURIE parsing errors
- Mapping distance calculation
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = OxOAdapter(config)

# Search for concept with cross-references
concepts = await adapter.search_concepts('DOID:162', limit=5)

# Get detailed mappings for a concept
concept = await adapter.get_concept_details('DOID:162')

# Get mappings for multiple concepts
mappings = await adapter.get_mappings_for_concepts(
    ['DOID:162', 'MONDO:0004992'],
    distance=2
)

# Check available data sources
sources = await adapter.get_datasources()

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('MONDO:0005015')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = OxOAdapter(config)
```

## Features
- **Cross-Reference Mapping**: Maps between ontology terms
- **Multiple Distance Levels**: Direct (1) and indirect (2+) mappings
- **Source Tracking**: Identifies mapping sources
- **Confidence Scoring**: Based on distance and source count
- **Batch Processing**: Support for multiple concept lookups
- **Data Source Listing**: Available ontologies query
- **Flexible Configuration**: Distance and ontology filtering

## Architecture
The adapter uses OxO's search API with POST requests to submit concept IDs and retrieve cross-references. It calculates confidence scores based on mapping distance and source information, and converts mappings to the unified concept model.
