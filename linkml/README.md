# LinkML Schema for Biomedical Knowledge Lookup

This directory contains the LinkML schema for the biomedical knowledge lookup project.

## Files

- `biomedical_knowledge_schema.yaml` - Main LinkML schema
- `generator_config.yaml` - Generator configuration for Pydantic
- `Makefile` - Build automation for generating code from schema

## Schema Overview

The schema defines:

### Classes
- `UnifiedConcept` - Central concept representation
- `ConceptIdentifier` - Source-specific identifiers
- `ConceptMapping` - Cross-references between concepts
- `LookupResult` - Query results
- `LookupConfig` - Configuration for lookups
- `SourceAnnotation` - Per-source annotations
- `ConceptAgreement` - Consensus analysis
- `MultiSourceAnnotationResult` - Complete annotation results

### Enums
- `KnowledgeSource` - 30+ knowledge sources (UMLS, OLS, BioPortal, etc.)
- `ConceptType` - Biological concept types (diseases, genes, drugs, etc.)
- `ConfidenceLevel` - Confidence levels for concept agreement (high, medium, low, disputed)

## Usage

### Generate Pydantic Models

```bash
# Using Make
cd linkml && make generate-python

# Or directly with linkml (from project root)
poetry run linkml generate pydantic linkml/biomedical_knowledge_schema.yaml > src/knowledge_lookup/generated_models/biomedical_knowledge_models.py
```

### Use in Python

```python
from src.knowledge_lookup.generated_models.biomedical_knowledge_models import (
    UnifiedConcept,
    ConceptIdentifier,
    ConceptMapping,
    LookupResult,
    LookupConfig,
    ConfidenceLevel
)

# Create a concept
concept = UnifiedConcept(
    primary_id="DOID:1234",
    primary_label="Diabetes Mellitus",
    concept_type="DISEASE"
)

# Use confidence level enum
level = ConfidenceLevel.high
```

## Schema Design Principles

1. **Unified Representation**: Single `UnifiedConcept` class combines data from multiple sources
2. **Cross-Reference Support**: `ConceptIdentifier` and `ConceptMapping` for semantic web
3. **Configurable**: `LookupConfig` for flexible query parameters
4. **Consensus Analysis**: Classes for multi-source annotation with agreement tracking

## Links

- LinkML Documentation: https://linkml.io/linkml/
- Pydantic: https://docs.pydantic.dev/
- Project: https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup
