# UMLS Adapter Documentation

## Overview
The UMLS adapter provides access to the Unified Medical Language System, a comprehensive biomedical terminology resource integrating multiple controlled vocabularies and classification systems.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search for concepts across UMLS vocabularies.

**Parameters:**
- `query`: Search term for biomedical concepts
- `limit`: Maximum results (default: 20, max: 100)

**Returns:** `List[UnifiedConcept]` - UMLS concepts matching the query

**Example Data Structure:**
```python
{
    'primary_id': 'C0006826',
    'primary_label': 'Malignant Neoplasms',
    'concept_type': ConceptType.DISEASE,
    'definitions': ['A term for diseases in which abnormal cells...'],
    'categories': ['Neoplasms'],
    'identifiers': [ConceptIdentifier(
        source='UMLS',
        identifier='C0006826',
        label='Malignant Neoplasms',
        url='https://uts.nlm.nih.gov/uts/umls/concept/C0006826'
    )]
}
```

#### `get_concept_details(concept_id)` [async]
Get detailed information about a specific UMLS concept.

**Parameters:**
- `concept_id`: UMLS CUI (e.g., 'C0006826')

**Returns:** `UnifiedConcept` or `None` - Detailed concept information

## Data Types and Structures

### UnifiedConcept Fields for UMLS
- `primary_id`: UMLS CUI (e.g., 'C0006826')
- `primary_label`: Preferred term name
- `concept_type`: DISEASE, PROCEDURE, ANATOMY, etc. (auto-detected)
- `definitions`: Concept definitions from source vocabularies
- `categories`: Semantic types and categories
- `identifiers`: UMLS identifiers with NLM URLs
- `synonyms`: Alternative terms from different vocabularies

### UMLS-Specific Data Fields
- `cui`: Concept Unique Identifier
- `preferred_name`: Preferred term
- `definitions`: List of definitions from source vocabularies
- `semantic_types`: UMLS semantic type assignments
- `source_vocabularies`: Original source vocabularies (SNOMED, ICD-10, etc.)
- `atoms`: Individual terms from different vocabularies

## Supported Vocabularies
UMLS integrates 200+ biomedical vocabularies including:
- **SNOMED CT**: Systematized Nomenclature of Medicine
- **ICD-10**: International Classification of Diseases
- **MeSH**: Medical Subject Headings
- **RxNorm**: Clinical drugs and drug delivery devices
- **LOINC**: Logical Observation Identifiers Names and Codes
- **CPT**: Current Procedural Terminology
- **HCPCS**: Healthcare Common Procedure Coding System

## Error Handling
- API key validation and client initialization
- UMLS client error handling
- Graceful degradation when service unavailable
- Comprehensive logging of search operations

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
config.api_keys['umls'] = 'your_umls_api_key'
adapter = UMLSAdapter(config)

# Search for disease concepts
diseases = await adapter.search_concepts('diabetes', limit=10)

# Get detailed concept information
concept = await adapter.get_concept_details('C0006826')

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('cancer')
```

## Configuration
Requires UMLS API key in configuration:
```python
config = LookupConfig()
config.api_keys['umls'] = 'your_api_key_here'
# or
config.api_keys['UMLS_API_KEY_TU'] = 'your_api_key_here'
```

## Features
- **Comprehensive Coverage**: 200+ integrated vocabularies
- **Semantic Types**: Rich categorization system
- **Cross-References**: Links between equivalent concepts
- **Multilingual Support**: Terms in multiple languages
- **Historical Data**: Versioned concept information
- **Advanced Search**: Boolean queries and filters
