# BioPortal Adapter Documentation

## Overview
The BioPortal adapter provides access to NCBI BioPortal for ontology-based concept lookup. It enables searching and retrieving concepts from hundreds of biomedical ontologies including SNOMED CT, LOINC, MeSH, and many specialized ontologies.

## Key Functions

### `search_concepts(query, limit=20)` [async]
Search BioPortal for concepts matching the query across all ontologies.

**Parameters:**
- `query`: Search term or concept ID
- `limit`: Maximum number of results (default: 20, max: 50)

**Returns:** `List[UnifiedConcept]` - Matching concepts from ontologies

**Example:**
```python
concepts = await adapter.search_concepts("diabetes", limit=10)
```

### `get_concept_details(concept_id)` [async]
Get detailed information about a specific BioPortal concept.

**Parameters:**
- `concept_id`: Full concept URI or CURIE (e.g., 'MONDO:0004992' or 'http://purl.obolibrary.org/obo/MONDO_0004992')

**Returns:** `UnifiedConcept` with full concept details or `None`

**Example:**
```python
concept = await adapter.get_concept_details('MONDO:0004992')
```

## API Information

### Endpoint
- **Base URL**: `https://data.bioontology.org`
- **Search Endpoint**: `/search`
- **Concept Endpoint**: `/ontologies/{ontology}/classes/{concept_uri}`

### Authentication
- **Required**: API key (optional but recommended)
- **API Key Header**: `apikey` parameter in requests
- **Environment Variable**: `BIOPORTAL_API_KEY`

### Rate Limits
- **Free tier**: Limited requests per day
- **Authenticated**: Higher limits with API key

### Request Parameters
- `q`: Search query
- `pagesize`: Results per page (default: 20)
- `apikey`: API key
- `format`: Response format (json)

## Data Types and Structures

### UnifiedConcept Fields for BioPortal
- `primary_id`: Full concept URI (e.g., 'http://purl.obolibrary.org/obo/MONDO_0004992')
- `primary_label`: Preferred label from ontology
- `concept_type`: Determined from ontology type
- `identifiers`: List including BioPortal identifier
- `synonyms`: List of alternative terms
- `definitions`: List of ontology definitions
- `categories`: Ontology name
- `confidence_score`: Fixed at 0.8
- `source_data`: Raw API response

### Ontology-Specific Concept Types
- Disease ontologies (MONDO, DOID, ORDO) → `DISEASE`
- Drug ontologies (CHEBI, DrugBank) → `DRUG`
- Gene ontologies (GO, SO) → `GENE`
- Anatomy ontologies (UBERON, FMA) → `ANATOMY`
- Phenotype ontologies (HP, MP) → `PHENOTYPE`
- Chemical ontologies (CHEBI) → `CHEMICAL`

## Configuration
API key is recommended for higher rate limits.

```python
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
config.api_keys['bioportal'] = 'your-api-key-here'
adapter = BioPortalAdapter(config)

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts("cancer")
```

### Environment Variable
```bash
export BIOPORTAL_API_KEY="your-api-key-here"
```

## Features
- **Multi-Ontology Search**: Search across 1000+ ontologies
- **Automatic Type Detection**: Map ontology to ConceptType
- **Synonym Support**: Retrieve alternative terms
- **Definition Access**: Get ontology definitions
- **Hierarchical Relationships**:Parents and children via details endpoint
- **API Key Support**: Higher rate limits with authentication
- **Flexible ID Format**: Support for full URIs or CURIEs

## Error Handling
- API key validation
- Network connectivity checks
- Response structure validation
- Concept ID parsing errors
- Ontology extraction failures
- Comprehensive logging

## Usage Examples

### Basic Search
```python
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter

adapter = BioPortalAdapter(config)

# Search for disease concepts
concepts = await adapter.search_concepts("diabetes mellitus", limit=10)

for concept in concepts:
    print(f"{concept.primary_label} ({concept.concept_type.value})")
```

### Get Concept Details
```python
# Get detailed information
concept = await adapter.get_concept_details('MONDO:0004992')

if concept:
    print(f"Label: {concept.primary_label}")
    print(f"Type: {concept.concept_type.value}")
    print(f"Definitions: {concept.definitions}")
    print(f"Synonyms: {concept.synonyms}")
```

### Search by Ontology Type
```python
# The adapter automatically searches all ontologies
# Results are categorized by ontology type in source_data

concepts = await adapter.search_concepts("insulin", limit=20)

for concept in concepts:
    source_data = concept.source_data.get('BIOPORTAL', {})
    print(f"Ontology: {source_data.get('links', {}).get('ontology', 'Unknown')}")
```

### With API Key
```python
# Configure with BioPortal API key
config.api_keys['bioportal'] = 'your-api-key'
adapter = BioPortalAdapter(config)

# Check if available before querying
if adapter.is_available():
    results = await adapter.search_concepts("cancer")
else:
    print("BioPortal API key not configured")
```

### Search with Synonyms
```python
concepts = await adapter.search_concepts("cancer", limit=10)

for concept in concepts:
    if concept.synonyms:
        print(f"Synonyms: {', '.join(concept.synonyms[:3])}")
```

## Architecture
The adapter uses BioPortal's search API to find matching concepts across all ontologies. It extracts concept metadata including labels, definitions, and synonyms, then maps ontologies to ConceptType enums based on ontology names. The details endpoint provides additional hierarchical information.

## Notes
- API key is optional but recommended for higher rate limits
- Without key, requests may be rate-limited or rejected
- Results include concepts from all BioPortal ontologies
- Concept URIs can be used directly for details lookup
- Ontology type mapping is based on name pattern matching
