# MONDO Adapter Documentation

## Overview
The MONDO (Mondo Disease Ontology) adapter provides access to the Mondo Disease Ontology through the EBI OLS (Ontology Lookup Service) API. It focuses on disease concept identification and basic metadata retrieval.

## Key Functions

### `search_concepts(query: str, limit: int = 20) -> List[UnifiedConcept]`
Searches for diseases in the Mondo Disease Ontology.

**Parameters:**
- `query`: Disease name or term to search for
- `limit`: Maximum number of results to return

**Returns:** List of `UnifiedConcept` objects representing diseases

**Example Data Structure:**
```json
[
  {
    "primary_id": "http://purl.obolibrary.org/obo/MONDO_0005148",
    "primary_label": "type 2 diabetes mellitus",
    "concept_type": "DISEASE",
    "source_data": {
      "MONDO": {
        "iri": "http://purl.obolibrary.org/obo/MONDO_0005148",
        "label": "type 2 diabetes mellitus",
        "ontology_name": "mondo",
        "ontology_prefix": "MONDO",
        "type": "class"
      }
    }
  },
  {
    "primary_id": "http://purl.obolibrary.org/obo/MONDO_0001252",
    "primary_label": "diabetes mellitus",
    "concept_type": "DISEASE",
    "source_data": {
      "MONDO": {
        "iri": "http://purl.obolibrary.org/obo/MONDO_0001252",
        "label": "diabetes mellitus",
        "ontology_name": "mondo",
        "ontology_prefix": "MONDO",
        "type": "class"
      }
    }
  }
]
```

### `get_concept_details(concept_id: str) -> None`
Currently not implemented - returns `None`.

**Parameters:**
- `concept_id`: MONDO IRI or identifier

**Returns:** `None` (placeholder for future implementation)

## Data Structures

### Disease Concept Fields
- `iri`: Full IRI identifier (e.g., "http://purl.obolibrary.org/obo/MONDO_0005148")
- `label`: Human-readable disease name
- `ontology_name`: Source ontology name ("mondo")
- `ontology_prefix`: Ontology prefix ("MONDO")
- `type`: Ontology term type ("class")
- `short_form`: Short form identifier (e.g., "MONDO_0005148")
- `obo_id`: OBO format identifier (e.g., "MONDO:0005148")

### Additional Fields (in full OLS responses)
- `description`: Disease description/definition
- `synonyms`: Alternative names and synonyms
- `annotations`: Additional annotations and properties
- `parents`: Parent terms in hierarchy
- `children`: Child terms in hierarchy
- `relations`: Related terms and relationships

## Usage Examples

```python
# Search for diabetes-related diseases
diseases = await adapter.search_concepts("diabetes", limit=10)

# Search for specific disease
diseases = await adapter.search_concepts("rheumatoid arthritis")

# Search for rare diseases
diseases = await adapter.search_concepts("cystic fibrosis")
```

## Notes
- Returns `UnifiedConcept` objects with disease type
- Uses EBI OLS API for ontology queries
- Limited to basic search functionality
- `get_concept_details` is not yet implemented
- No authentication required (public API)
- Provides standardized disease identifiers and labels
