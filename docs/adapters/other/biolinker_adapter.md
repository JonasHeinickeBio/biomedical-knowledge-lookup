# BioLinker AI Adapter Documentation

## Overview
The BioLinker AI adapter provides access to TIB BioLinker AI API for entity and relation extraction from text. It enables automated extraction of biomedical entities (genes, proteins, diseases, drugs) and their relationships from free-text descriptions.

## Key Functions

### `search_concepts(query, limit=20)` [async]
Extract entities and relations from text using BioLinker AI.

**Parameters:**
- `query`: Input text to process
- `limit`: Maximum number of results (default: 20)

**Returns:** `List[UnifiedConcept]` - Extracted concepts from the text

**Example:**
```python
concepts = await adapter.search_concepts("Diabetes is associated with insulin resistance")
```

### `search_concepts_with_depth(query, limit=20, search_depth=50)` [async]
Extract entities with custom search depth for more comprehensive results.

**Parameters:**
- `query`: Input text to process
- `limit`: Maximum number of results (default: 20)
- `search_depth`: Number of concepts to consider (default: 50, max: 100)

**Returns:** `List[UnifiedConcept]` - Extracted concepts with specified depth

### `annotate_sentence(sentence, search_depth=50)` [async]
Annotate a complete sentence with structured entity and relation extraction.

**Parameters:**
- `sentence`: Complete sentence to annotate
- `search_depth`: Number of concepts to consider

**Returns:** `Dict[str, Any]` with structured annotation results including:
- `entities`: List of extracted entities with positions
- `predicates`: List of extracted predicates
- `relations`: Identified relations between entities and predicates

### `annotate_multiple_sentences(sentences, search_depth=50)` [async]
Annotate multiple sentences efficiently.

**Parameters:**
- `sentences`: List of sentences to annotate
- `search_depth`: Number of concepts to consider per sentence

**Returns:** `List[Dict[str, Any]]` - Annotation results for each sentence

## API Information

### Endpoint
- **Base URL**: `https://labs.tib.eu/biolinkerai`
- **Process Endpoint**: `/process-text`
- **Authentication**: Not required (public API)
- **Rate Limits**: None documented

### Request Parameters
- `input_text`: Text to process
- `k`: Search depth (number of concepts to consider)

### Response Structure
```json
{
  "results": [
    {
      "best_candidate": {
        "id": "C0011860",
        "label": "Diabetes Mellitus",
        "description": "A metabolic disorder...",
        "type": ["disease"]
      },
      "surface_form": "Diabetes",
      "category": "entities",
      "start": 0,
      "end": 8
    }
  ]
}
```

## Data Types and Structures

### UnifiedConcept Fields for BioLinker
- `primary_id`: UMLS concept ID (C-code, e.g., 'C0011860')
- `primary_label`: Concept label
- `concept_type`: Mapped from semantic types
- `definitions`: Concept descriptions
- `synonyms`: Surface forms found in text
- `semantic_types`: BioLinker AI semantic categories
- `categories`: Entity category (entities/predicates)
- `confidence_score`: Based on candidate quality
- `source_data`: Raw API response with position info

### Source Data Fields
- `surface_form`: Text substring that matched
- `text_position`: Start and end character positions
- `category`: 'entities' or 'predicates'
- `biolinker_source`: 'TIB BioLinker AI'

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = BioLinkerAdapter(config)
```

## Features
- **Entity Extraction**: Extract genes, proteins, diseases, drugs from text
- **Predicate Extraction**: Identify relations and actions
- **Position Tracking**: Character-level positions in source text
- **Semantic Typing**: Automatic classification of entities
- **Confidence Scoring**: Based on candidate quality and surface forms
- **Sentence Annotation**: Structured annotation of complete sentences
- **Batch Processing**: Efficient multiple sentence processing
- **Flexible Depth**: Configurable search depth for comprehensive results

## Error Handling
- Network connectivity validation
- API timeout handling (2 minute timeout for slow responses)
- Response structure validation
- Entity parsing errors
- Comprehensive logging

## Usage Examples

### Basic Text Processing
```python
from knowledge_lookup.adapters.biolinker_adapter import BioLinkerAdapter

adapter = BioLinkerAdapter(config)

# Extract entities from text
concepts = await adapter.search_concepts(
    "TP53 mutations are associated with increased cancer risk"
)

for concept in concepts:
    print(f"Found: {concept.primary_label} ({concept.concept_type.value})")
```

### Sentence Annotation
```python
# Get structured annotation
annotation = await adapter.annotate_sentence(
    "Insulin resistance leads to type 2 diabetes"
)

print(f"Entities: {len(annotation['entities'])}")
print(f"Predicates: {len(annotation['predicates'])}")
print(f"Relations: {len(annotation['relations'])}")

# Extract entity information
for entity in annotation['entities']:
    print(f"  {entity['surface_form']}: {entity['label']}")
```

### Batch Processing
```python
# Process multiple sentences
sentences = [
    "Diabetes increases cardiovascular risk",
    "Obesity is a risk factor for diabetes"
]

annotations = await adapter.annotate_multiple_sentences(sentences)

for i, annotation in enumerate(annotations):
    print(f"Sentence {i+1}: {len(annotation['entities'])} entities")
```

### Custom Search Depth
```python
# For complex queries, use higher search depth
concepts = await adapter.search_concepts_with_depth(
    "Genetic and environmental factors interact in complex diseases",
    limit=20,
    search_depth=100
)
```

## Architecture
The adapter sends text to BioLinker AI's process-text endpoint, which returns extracted entities and predicates. Results are converted to UnifiedConcept objects with surface forms, positions, and confidence scores based on the quality of extracted candidates.

## Notes
- BioLinker AI may be slow for complex queries (uses 180-second timeout)
- Search depth affects both accuracy and processing time
- Entity positions are useful for text highlighting and navigation
- Confidence scores help prioritize high-quality extractions
