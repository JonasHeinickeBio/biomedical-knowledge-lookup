# TYTO Adapter Documentation

## Overview
The TYTO adapter provides access to the Tyto library for ontology lookups, enabling term recognition and label retrieval from ontologies.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Tyto doesn't support broad search across all ontologies easily.

**Parameters:**
- `query`: Search query (not fully supported)
- `limit`: Maximum results (default: 20)

**Returns:** `List[UnifiedConcept]` - Empty list (search not supported)

#### `get_concept_details(concept_id)` [async]
Get details for a URI using Tyto.

**Parameters:**
- `concept_id`: Term URI (e.g., 'http://purl.obolibrary.org/obo/GO_0008150')

**Returns:** `UnifiedConcept` or `None` - Concept details

**Example Data Structure:**
```python
{
    'primary_id': 'http://purl.obolibrary.org/obo/GO_0008150',
    'primary_label': 'biological_process',
    'concept_type': ConceptType.UNKNOWN,
    'identifiers': [ConceptIdentifier(
        source='TYTO',
        identifier='http://purl.obolibrary.org/obo/GO_0008150',
        label='biological_process',
        url='http://purl.obolibrary.org/obo/GO_0008150'
    )],
    'confidence_score': 1.0
}
```

## Data Types and Structures

### UnifiedConcept Fields for TYTO
- `primary_id`: Term URI
- `primary_label`: Term label retrieved from Tyto
- `concept_type`: UNKNOWN
- `identifiers`: TYTO identifiers with URI URLs
- `confidence_score`: 1.0 (for successful lookups)
- `source_data`: Raw Tyto response (internal)

## API Information

**Library:** Tyto (Python library)

**Requirements:** Install with `pip install tyto`

**Dependencies:**
- tyto library for ontology term lookups

## Error Handling
- Dependency availability validation
- URI format validation
- Label retrieval errors
- ImportError handling with warning
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = TytoAdapter(config)

# Check if Tyto is available
if adapter.is_available():
    # Get term details from URI
    concept = await adapter.get_concept_details(
        'http://purl.obolibrary.org/obo/GO_0008150'
    )
    
    # Search is not supported
    # results = await adapter.search_concepts('cell')  # Returns []
```

## Configuration
No special configuration required, but Tyto library must be installed.

```bash
# Install Tyto
pip install tyto
```

```python
config = LookupConfig()
adapter = TytoAdapter(config)
```

## Features
- **URI-Based Lookups**: Retrieves labels from ontology URIs
- **Label Resolution**: Converts URIs to human-readable labels
- **Lightweight**: Minimal dependency footprint
- **High Confidence**: 1.0 confidence for successful lookups
- **Availability Check**: Validates Tyto library installation
- **Warning System**: Alerts if Tyto not installed

## Architecture
The adapter uses the Tyto Python library for ontology term lookups. It validates term URIs and retrieves labels using Tyto's `get_label()` function. Search is not implemented as Tyto is primarily designed for URI-to-label conversion.
