# ZOOMA Adapter Documentation

## Overview
The ZOOMA adapter provides access to EBI's ZOOMA (ZOMEO Object Mapping Service), an automated ontology mapping service that links free-text annotations to ontology terms.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search ZOOMA for ontology mappings based on text annotations.

**Parameters:**
- `query`: Free-text term to map to ontologies (e.g., 'heart disease', 'tumor')
- `limit`: Maximum results (default: 20)

**Returns:** `List[UnifiedConcept]` - Mapped ontology concepts

**Example Data Structure:**
```python
{
    'primary_id': 'http://purl.obolibrary.org/obo/DOID_9352',
    'primary_label': 'heart disease',
    'concept_type': ConceptType.UNKNOWN,
    'definitions': [],
    'categories': ['Source: DOID'],
    'identifiers': [ConceptIdentifier(
        source='ZOOMA',
        identifier='http://purl.obolibrary.org/obo/DOID_9352',
        label='heart disease',
        url='http://purl.obolibrary.org/obo/DOID_9352'
    )],
    'confidence_score': 0.9
}
```

#### `get_concept_details(concept_id)` [async]
ZOOMA is primarily for mapping; use OLS for details.

**Parameters:**
- `concept_id`: Ontology term URI

**Returns:** `None` (ZOOMA doesn't provide detailed concept info)

## Data Types and Structures

### UnifiedConcept Fields for ZOOMA
- `primary_id`: Ontology term URI (e.g., 'http://purl.obolibrary.org/obo/DOID_9352')
- `primary_label`: Mapped term label
- `concept_type`: UNKNOWN (varies by mapped ontology)
- `categories`: Source ontology name
- `identifiers`: ZOOMA mappings with ontology URIs
- `confidence_score`: Mapping confidence (0.3-0.9)
- `source_data`: Raw ZOOMA API response

### ZOOMA-Specific Data Fields
- `semanticTags`: List of ontology term URIs
- `annotatedProperty`: Original annotated text
- `confidence`: Mapping confidence level (HIGH/GOOD/MEDIUM/LOW)
- `derivedFrom`: Source database (e.g., DOID, EFO, MONDO)
- `provenance`: Mapping source information

## API Information

**Base URL:** `https://www.ebi.ac.uk/spot/zooma/v2/api`

**Endpoints:**
- Annotation: `/services/annotate`

**Authentication:** Not required (public API)

**Rate Limits:** No explicit public rate limits documented

**Parameters:**
- `propertyValue`: Text to annotate/map

## Error Handling
- API connectivity validation
- Response structure validation
- Confidence score parsing
- Source extraction errors
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = ZoomaAdapter(config)

# Map free-text to ontologies
mappings = await adapter.search_concepts('myocardial infarction', limit=10)

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('cancer')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = ZoomaAdapter(config)
```

## Features
- **Automated Mapping**: Connects free-text to ontology terms
- **Multiple Ontology Support**: DOID, EFO, MONDO, HPO, and others
- **Confidence Scoring**: HIGH (0.9), GOOD (0.7), MEDIUM (0.5), LOW (0.3)
- **Provenance Tracking**: Source database identification
- **Flexible Search**: Accepts various text formats
- **Moderate Confidence**: Scores based on mapping quality

## Architecture
The adapter uses ZOOMA's annotation service which automatically maps free-text to ontology terms. It retrieves the mapped ontology terms and converts them to the unified concept model with confidence scores based on mapping quality indicators.
