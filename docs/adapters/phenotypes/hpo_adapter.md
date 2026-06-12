# HPO (Human Phenotype Ontology) Adapter Documentation

## Overview
The HPO adapter provides access to the Human Phenotype Ontology, a standardized vocabulary of phenotypic abnormalities encountered in human disease. It enables phenotype-based querying and analysis for clinical and research applications.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search HPO for phenotypes matching the query.

**Parameters:**
- `query`: Search term for phenotypes (e.g., 'abnormality', 'fever', 'seizure')
- `limit`: Maximum results (default: 20)

**Returns:** `List[UnifiedConcept]` - HPO phenotype concepts

**Example Data Structure:**
```python
{
    'primary_id': 'HP:0000118',
    'primary_label': 'Abnormality of body height',
    'concept_type': ConceptType.PHENOTYPE,
    'definitions': ['Deviation from the normal height or growth'],
    'categories': ['Phenotypic abnormality'],
    'identifiers': [ConceptIdentifier(
        source='HPO',
        identifier='HP:0000118',
        label='Abnormality of body height',
        url='https://hpo.jax.org/app/browse/term/HP:0000118'
    )],
    'synonyms': ['Short stature', 'Abnormal height']
}
```

#### `get_concept_details(concept_id)` [async]
Get detailed information about a specific HPO concept.

**Parameters:**
- `concept_id`: HPO ID (e.g., 'HP:0000118')

**Returns:** `UnifiedConcept` or `None` - Detailed phenotype information

## Data Types and Structures

### UnifiedConcept Fields for HPO
- `primary_id`: HPO ID (e.g., 'HP:0000118')
- `primary_label`: Standardized phenotype term
- `concept_type`: PHENOTYPE
- `definitions`: Phenotype definitions
- `categories`: Phenotype categories
- `identifiers`: HPO identifiers with JAX URLs
- `synonyms`: Alternative phenotype terms
- `source_data`: Raw HPO API response

### HPO-Specific Data Fields
- `id`: HPO term identifier
- `name`: Phenotype term name
- `definition`: Formal definition
- `synonyms`: Alternative terms
- `xrefs`: Cross-references to other ontologies
- `parents`: Parent terms in ontology hierarchy

## API Information

**Base URL:** `https://hpo.jax.org/api/ontological`

**Endpoints:**
- Search: `/search`
- Term Details: `/term/{concept_id}`

**Authentication:** Not required (public API)

**Rate Limits:** No explicit public rate limits documented

## Error Handling
- API connectivity validation
- Response parsing validation
- Invalid HPO ID handling
- Graceful degradation on timeout or error
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = HPOAdapter(config)

# Search for phenotypes
phenotypes = await adapter.search_concepts('seizure', limit=10)

# Get detailed phenotype information
concept = await adapter.get_concept_details('HP:0001250')

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('abnormality')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = HPOAdapter(config)
```

## Features
- **Standardized Vocabulary**: 17,000+ standardized phenotype terms
- **Clinical Applications**: Diagnosis support and phenotypic profiling
- **Ontology Hierarchy**: Parent-child relationships for phenotypes
- **Cross-References**: Links to OMIM, Orphanet, and other databases
- **Synonym Support**: Multiple terms for same phenotype
- **High Confidence**: 0.95 confidence score for matches

## Architecture
The adapter uses the HPO REST API for ontological searches. It converts HPO-specific responses to the unified concept model for consistent processing across knowledge sources.
