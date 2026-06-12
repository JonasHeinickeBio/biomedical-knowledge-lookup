# DBPedia Adapter Documentation

## Overview
The DBPedia adapter provides access to DBpedia, a community-driven effort to extract structured data from Wikipedia and make it available on the web. It enables querying of structured Wikipedia data through SPARQL endpoints.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search DBpedia for concepts matching the query string.

**Parameters:**
- `query`: Search term for concepts (e.g., 'London', 'Albert Einstein')
- `limit`: Maximum results (default: 20)

**Returns:** `List[UnifiedConcept]` - DBpedia concepts

**Example Data Structure:**
```python
{
    'primary_id': 'London',
    'primary_label': 'London',
    'concept_type': ConceptType.UNKNOWN,
    'definitions': ['London is the capital and largest city of England and the United Kingdom'],
    'categories': ['City', 'Populated place'],
    'identifiers': [ConceptIdentifier(
        source='DBPEDIA',
        identifier='London',
        label='London',
        url='http://dbpedia.org/resource/London'
    )],
    'confidence_score': 0.6
}
```

#### `get_concept_details(concept_id)` [async]
Get details for a specific DBpedia concept/entity.

**Parameters:**
- `concept_id`: DBpedia resource ID or full URI

**Returns:** `UnifiedConcept` or `None` - Detailed entity information

#### `run_sparql_query(sparql_query, limit=None)` [async]
Run a generic SPARQL query against DBpedia.

**Parameters:**
- `sparql_query`: SPARQL query string
- `limit`: Optional result limit

**Returns:** Raw SPARQL JSON results

## Data Types and Structures

### UnifiedConcept Fields for DBPedia
- `primary_id`: DBpedia resource ID (e.g., 'London')
- `primary_label`: Entity label
- `concept_type`: UNKNOWN (inferred from context)
- `definitions`: Abstract/description text
- `categories`: RDF types
- `identifiers`: DBpedia identifiers with URLs
- `confidence_score`: 0.6-0.65
- `source_data`: Raw SPARQL results

### DBPedia-Specific Data Fields
- `resource`: Resource URI
- `label`: Entity label
- `abstract`: Text abstract
- `types`: RDF type URIs
- `properties`: Entity properties

## API Information

**SPARQL Endpoint:** `https://dbpedia.org/sparql`

**Base URL:** `https://dbpedia.org`

**Authentication:** Not required (public SPARQL endpoint)

**Rate Limits:** No explicit public rate limits documented

**SPARQL Example:**
```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbo: <http://dbpedia.org/ontology/>
SELECT DISTINCT ?resource ?label ?abstract ?type WHERE {
  ?resource rdfs:label ?label .
  ?label bif:contains "'query'" .
  FILTER (lang(?label) = 'en')
  OPTIONAL { ?resource dbo:abstract ?abstract . }
  OPTIONAL { ?resource rdf:type ?type }
}
```

## Error Handling
- SPARQL query execution validation
- Response structure validation
- URI parsing errors
- Abstract truncation for long texts
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = DBpediaAdapter(config)

# Search for concepts
concepts = await adapter.search_concepts('Paris', limit=10)

# Get detailed entity information
concept = await adapter.get_concept_details('Paris')

# Run custom SPARQL query
query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label WHERE {
  <http://dbpedia.org/resource/Paris> rdfs:label ?label .
}
"""
results = await adapter.run_sparql_query(query)

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('London')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = DBpediaAdapter(config)
```

## Features
- **Structured Wikipedia Data**: Access to 5 million+ entities
- **SPARQL Support**: Full SPARQL query capability
- **Multilingual Labels**: Support for multiple languages
- **Rich Metadata**: Abstracts, types, and properties
- **Entity Disambiguation**: Best match selection
- **Flexible Queries**: Custom SPARQL support
- **Moderate Confidence**: Scores based on match quality

## Architecture
The adapter uses DBpedia's SPARQL endpoint for querying. It provides specialized search methods for common use cases while also supporting arbitrary SPARQL queries for advanced users. Responses are normalized to the unified concept model.
