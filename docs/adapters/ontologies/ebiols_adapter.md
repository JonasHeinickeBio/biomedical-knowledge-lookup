# EBI OLS Adapter Documentation

## Overview
The EBI OLS adapter provides access to the EMBL-EBI Ontology Lookup Service, a comprehensive repository of ontologies with search and browsing capabilities.

## Key Functions

### Core Search Methods

The EBIOLSAdapter inherits from OLSAdapter, which implements the following methods:

#### `search_concepts(query, limit=20)` [async]
Search OLS for ontologies and concepts.

**Parameters:**
- `query`: Search term for ontologies/concepts
- `limit`: Maximum results (default: 20)

**Returns:** `List[UnifiedConcept]` - Ontology concepts

#### `get_concept_details(concept_id)` [async]
Get detailed information about a specific concept.

**Parameters:**
- `concept_id`: Ontology term ID

**Returns:** `UnifiedConcept` or `None` - Detailed concept information

## Data Types and Structures

### UnifiedConcept Fields for EBIOLS
- `primary_id`: Ontology term ID (e.g., 'GO:0008150')
- `primary_label`: Term label
- `concept_type`: Varies by ontology
- `definitions`: Term definitions
- `categories`: Ontology source
- `identifiers`: Ontology term identifiers with URLs
- `source_data`: Raw OLS API response

## API Information

**Base URL:** `https://www.ebi.ac.uk/ols4/api`

**Endpoints:**
- Search: `/search`
- Term Details: `/ontologies/{ontology}/terms/{term}`

**Authentication:** Not required (public API)

**Rate Limits:** No explicit public rate limits documented

## Error Handling
- API connectivity validation
- Response structure validation
- Ontology term resolution
- URL generation errors
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = EBIOLSAdapter(config)

# Search for ontology terms
terms = await adapter.search_concepts('cell proliferation', limit=10)

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('metabolism')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = EBIOLSAdapter(config)
```

## Features
- **Comprehensive Ontology Repository**: Access to 100+ ontologies
- **Hierarchical Search**: Ontology term browsing
- **Multiple Format Support**: OBO, OWL, RDF formats
- **Cross-References**: Links between ontologies
- **Ontology Metadata**: Source information and versioning
- **Moderate Confidence**: 0.8 confidence score for matches

## Architecture
The EBIOLSAdapter inherits from OLSAdapter and specializes in EMBL-EBI's Ontology Lookup Service. It provides the same functionality as OLSAdapter but with a distinct KnowledgeSource identifier for EBI OLS specifically.
