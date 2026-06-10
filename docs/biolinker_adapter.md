# BioLinker Adapter Documentation

## Overview
The BioLinker adapter integrates with the TIB BioLinker AI API for advanced entity and relation extraction from biomedical text. It uses AI to identify entities, predicates, and relationships in natural language text.

## Key Functions

### `search_concepts(query: str, limit: int = 20) -> List[UnifiedConcept]`
Extracts entities and concepts from input text using BioLinker AI.

**Parameters:**
- `query`: Input text to process for entity extraction
- `limit`: Maximum number of concepts to return

**Returns:** List of `UnifiedConcept` objects representing extracted entities

**Example Data Structure:**
```json
[
  {
    "primary_id": "http://identifiers.org/uniprot/P01375",
    "primary_label": "TNF-alpha",
    "concept_type": "PROTEIN",
    "semantic_types": ["cytokine", "inflammatory mediator"],
    "confidence_score": 0.95,
    "source_data": {
      "BIOLINKER": {
        "category": "entities",
        "surface_form": "TNF-alpha",
        "text_position": {"start": 45, "end": 53},
        "entity_type": "Protein",
        "confidence": 0.95,
        "definition": "Tumor necrosis factor alpha"
      }
    }
  }
]
```

### `search_concepts_with_depth(query: str, limit: int = 20, search_depth: int = 50) -> List[UnifiedConcept]`
Extracts entities with configurable search depth parameter.

**Parameters:**
- `query`: Input text to process
- `limit`: Maximum number of results to return
- `search_depth`: Number of concepts for BioLinker AI to consider (k parameter)

**Returns:** List of `UnifiedConcept` objects

### `annotate_sentence(sentence: str, search_depth: int = 50) -> Dict[str, Any]`
Provides structured annotation of a complete sentence with entities, predicates, and relations.

**Parameters:**
- `sentence`: Complete sentence to annotate
- `search_depth`: Number of concepts for BioLinker AI to consider

**Returns:** Dictionary with structured annotation results

**Example Data Structure:**
```json
{
  "sentence": "TNF-alpha inhibits cell proliferation in rheumatoid arthritis.",
  "search_depth": 50,
  "total_concepts": 3,
  "entities": [
    {
      "surface_form": "TNF-alpha",
      "label": "Tumor necrosis factor alpha",
      "id": "http://identifiers.org/uniprot/P01375",
      "type": "PROTEIN",
      "semantic_types": ["cytokine"],
      "position": {"start": 0, "end": 8},
      "confidence": 0.95,
      "definition": "Tumor necrosis factor alpha"
    },
    {
      "surface_form": "cell proliferation",
      "label": "Cell proliferation",
      "id": "GO:0008283",
      "type": "BIOLOGICAL_PROCESS",
      "position": {"start": 18, "end": 35},
      "confidence": 0.88
    }
  ],
  "predicates": [
    {
      "surface_form": "inhibits",
      "label": "inhibits",
      "type": "PREDICATE",
      "position": {"start": 9, "end": 17},
      "confidence": 0.92
    }
  ],
  "relations": [
    {
      "subject": "TNF-alpha",
      "predicate": "inhibits",
      "object": "cell proliferation",
      "confidence": 0.89
    }
  ],
  "concept_map": {
    "TNF-alpha": {...},
    "cell proliferation": {...},
    "inhibits": {...}
  }
}
```

### `annotate_multiple_sentences(sentences: List[str], search_depth: int = 50) -> List[Dict[str, Any]]`
Annotates multiple sentences efficiently in batch.

**Parameters:**
- `sentences`: List of sentences to annotate
- `search_depth`: Number of concepts for BioLinker AI to consider

**Returns:** List of annotation dictionaries

## Data Structures

### Entity Information
- `surface_form`: Text span as it appears in the source
- `label`: Normalized concept label
- `id`: Unique identifier (URI format)
- `type`: Concept type (PROTEIN, DISEASE, etc.)
- `semantic_types`: List of semantic categories
- `position`: Character positions in text (`start`, `end`)
- `confidence`: Confidence score (0-1)
- `definition`: Concept definition/description

### Predicate Information
- `surface_form`: Predicate text
- `label`: Normalized predicate label
- `type`: Always "PREDICATE"
- `position`: Character positions
- `confidence`: Confidence score

### Relation Information
- `subject`: Subject entity surface form
- `predicate`: Predicate surface form
- `object`: Object entity surface form
- `confidence`: Relation confidence score

## Usage Examples

```python
# Basic entity extraction
concepts = await adapter.search_concepts("TNF-alpha causes inflammation", limit=10)

# Sentence annotation with relations
annotation = await adapter.annotate_sentence(
    "TNF-alpha inhibits cell proliferation in rheumatoid arthritis."
)

# Batch processing
sentences = [
    "IL-6 promotes B cell differentiation.",
    "Dexamethasone reduces inflammation."
]
annotations = await adapter.annotate_multiple_sentences(sentences)
```

## Notes
- Publicly available API (no authentication required)
- Uses AI for entity recognition and relation extraction
- Supports configurable search depth for complex queries
- Provides structured output with positions and confidence scores
- Handles both entities (nouns) and predicates (verbs/relations)
- Automatically identifies potential relations based on entity proximity
