# Unified Clinical Concept Lookup and Validation

This guide explains how to use the `CentralKnowledgeLookup` system to validate and search for clinical concepts (symptoms, signs, and diseases) using authoritative sources like UMLS and BioPortal.

## Overview

The system provides a unified interface to multiple biomedical knowledge sources. For clinical validation, it is specifically optimized to filter results by **UMLS Semantic Types**, ensuring that search results are relevant clinical findings rather than drugs, procedures, or laboratory tests.

### Key Clinical Semantic Types
- **T047**: Disease or Syndrome
- **T184**: Sign or Symptom
- **T033**: Finding
- **T037**: Injury or Poisoning
- **T190**: Anatomical Abnormality
- **T048**: Mental or Behavioral Dysfunction

## Usage Example

### 1. Basic Setup

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

async def setup_lookup():
    config = LookupConfig(
        api_keys={
            "umls": "YOUR_UMLS_API_KEY",
            "bioportal": "YOUR_BIOPORTAL_API_KEY"
        },
        enabled_sources=[KnowledgeSource.UMLS, KnowledgeSource.BIOPORTAL]
    )
    return CentralKnowledgeLookup(config)
```

### 2. Clinical Validation of an Existing CUI

When you have a CUI (Concept Unique Identifier) and want to verify if it represents a clinical symptom:

```python
async def validate_symptom(lookup, cui, expected_label):
    # Get authoritative details from UMLS
    concept = await lookup.get_concept_details(cui, source=KnowledgeSource.UMLS)
    
    if not concept:
        return "Not Found"
        
    # Define clinical types
    clinical_types = ["T047", "T184", "T033", "T037", "T190", "T048"]
    
    # Check if the concept has a clinical semantic type
    is_clinical = any(st in clinical_types for st in concept.semantic_types)
    
    if is_clinical:
        # Check if the label matches (fuzzy check)
        if expected_label.lower() in concept.primary_label.lower():
            return "Valid Clinical Symptom"
        else:
            return f"Type OK, but Label Mismatch (Found: {concept.primary_label})"
    else:
        return f"Invalid Type: {concept.semantic_types}"
```

### 3. Searching for a Better CUI

If a CUI is incorrect or missing, use a filtered search:

```python
async def find_clinical_cui(lookup, term):
    # Search across UMLS and BioPortal
    result = await lookup.search_concepts(term, max_results=5)
    
    clinical_matches = []
    clinical_types = ["T047", "T184", "T033", "T037", "T190", "T048"]
    
    for concept in result.concepts:
        # Filter by semantic type
        if any(st in clinical_types for st in concept.semantic_types):
            clinical_matches.append(concept)
            
    return clinical_matches
```

## Advanced Scoring

For automated pipelines, use a combined scoring approach:

1.  **Fuzzy Score**: String similarity between query and `primary_label` + `synonyms`.
2.  **Source Agreement**: Number of different ontologies (SNOMEDCT, MSH, ICD10) that agree on the CUI.
3.  **Semantic Type Weight**: Reward concepts that match the expected clinical categories.

## Best Practices

- **Always use UMLS for IDs**: Use CUIs as the primary identifier for interoperability.
- **Cross-validate with BioPortal**: BioPortal provides excellent search coverage for terms that might be missed by raw UMLS string matching.
- **Filter Early**: Applying semantic type filters early in your pipeline prevents "concept drift" where clinical symptoms are confused with similar-sounding drugs or procedures.
