# CURIE Management Guide

A comprehensive guide to CURIE/URI parsing, validation, and normalization in the biomedical knowledge lookup library.

## Overview

The library uses [bioregistry](https://bioregistry.io/), [curies](https://github.com/cthoyt/curies), and [pyobo](https://github.com/pyobo/pyobo) for CURIE management:

- **CURIE**: Compact URI like `DOID:9351`
- **URI**: Full URL like `http://purl.obolibrary.org/obo/DOID_9351`

## Features

- ✅ CURIE/URI parsing and normalization (via `curies`)
- ✅ Prefix validation against bioregistry
- ✅ Identifier normalization (via `curies`)
- ✅ Automatic prefix mapping
- ✅ Pattern validation for specific prefixes
- ✅ `ConceptIdentifier` ↔ `curies.Reference` conversion
- ⬜ Not yet wired into `CentralKnowledgeLookup` query parsing or dedup (see below)

## Quick Start

### Import Utilities

```python
from knowledge_lookup.curie_utils import (
    validate_prefix,
    normalize_curie,
    parse_curie_or_uri,
    concept_identifier_to_reference,
)
```

### Parse CURIE or URI

```python
from knowledge_lookup.curie_utils import parse_curie_or_uri

# Parse CURIE
result = parse_curie_or_uri("DOID:9351")
# → ("doid", "9351")

# Parse URI
result = parse_curie_or_uri("http://purl.obolibrary.org/obo/DOID_9351")
# → ("doid", "9351")

# Returns None for unparsable strings
result = parse_curie_or_uri("not-a-valid-identifier")
# → None
```

### Validate Prefix

```python
from knowledge_lookup.curie_utils import validate_prefix

# Valid prefix
validate_prefix("doid")  # → True

# Invalid prefix
validate_prefix("invalid_prefix")  # → False
```

### Normalize CURIE

```python
from knowledge_lookup.curie_utils import normalize_curie

# Standardizes the prefix to bioregistry's canonical (lowercase) form.
# This does NOT cross-map to a different ontology — for that, use OxO
# (see CentralKnowledgeLookup.find_mappings, or the OxO adapter directly).
normalize_curie("DOID:9351")  # → "doid:9351"
normalize_curie("GO:0008150")  # → "go:0008150"

# Unregistered prefixes are returned unchanged rather than raising
normalize_curie("NOT-A-PREFIX:1")  # → "NOT-A-PREFIX:1"
```

## Advanced Usage

### Using ConceptIdentifier with CURIEs

`source` must be a registered `KnowledgeSource` value (`"DOID"` isn't one —
DOID terms come from the OLS adapter in this library). A `ConceptIdentifier`
model converts to/from a `curies.Reference` directly:

```python
from knowledge_lookup import ConceptIdentifier, KnowledgeSource

identifier = ConceptIdentifier(
    source=KnowledgeSource.MONDO,
    identifier="0005015",
    label="diabetes mellitus",
)

# Convert to curies Reference
reference = identifier.to_curies_reference()  # Reference(prefix='mondo', identifier='0005015')

# ... and back
round_tripped = ConceptIdentifier.from_curies_reference(reference)
```

`knowledge_lookup.curie_utils.concept_identifier_to_reference()` /
`reference_to_concept_identifier()` do the same conversion for plain
`{"source": ..., "identifier": ...}` dicts, when you don't have a full
`ConceptIdentifier` model instance:

```python
from knowledge_lookup.curie_utils import concept_identifier_to_reference

reference = concept_identifier_to_reference({"source": "MONDO", "identifier": "0005015"})
```

### Getting Prefix Mappings

```python
from knowledge_lookup.curie_utils import get_prefix_mapping

# Maps every registered prefix (and its synonyms) to its canonical
# bioregistry prefix — not to a URI. ~7000 entries.
prefixes = get_prefix_mapping()
# → {"doid": "doid", "DOID": "doid", "3dmet": "3dmet", ...}
prefixes["DOID"]  # → "doid"
```

### Pattern Validation

```python
from knowledge_lookup.curie_utils import validate_curie_pattern

# Check if identifier matches prefix pattern
validate_curie_pattern("doid", "9351")  # → True
validate_curie_pattern("doid", "invalid!")  # → False
```

## Integration with CentralKnowledgeLookup

`curie_utils` is currently a standalone toolkit: `CentralKnowledgeLookup`
computes a per-source prefix map at startup
(`get_source_prefix_mapping()`, cached as `self._prefix_map`) but does not
yet parse free-text queries as CURIEs, normalize identifiers on results, or
use CURIE-aware deduplication — `search_concepts("DOID:9351")` is passed to
each adapter as a literal search string, not parsed into `(prefix,
identifier)` first. Cross-ontology mapping between identifiers (e.g. going
from a DOID to its MONDO/UMLS/NCIT equivalents) is handled separately, via
`CentralKnowledgeLookup.find_mappings()` (backed by the OxO adapter), not by
`curie_utils`.

If you need CURIE-aware query handling today, parse the query yourself with
`parse_curie_or_uri()` before calling `search_concepts()`, or call
`get_concept_details(curie)` directly when you already have a CURIE.

### Example: Validate Before Query

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource
from knowledge_lookup.curie_utils import validate_prefix

lookup = CentralKnowledgeLookup()

# Validate source prefix
if validate_prefix("bioportal"):
    # Safe to query BioPortal
    results = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.BIOPORTAL])
```

## CURIE Utility Functions Reference

### validate_prefix(prefix: str) → bool

Check if prefix exists in bioregistry.

**Parameters:**
- `prefix`: Prefix to validate (case-insensitive)

**Returns:**
- `True` if prefix exists in bioregistry
- `False` otherwise

**Example:**
```python
validate_prefix("doid")  # True
validate_prefix("DOID")  # True (case-insensitive)
validate_prefix("xyz123")  # False
```

### normalize_curie(curie: str) → str | None

Normalize a CURIE using bioregistry mappings.

**Parameters:**
- `curie`: CURIE string like "DOID:9351"

**Returns:**
- Normalized CURIE string, or None if normalization fails

**Example:**
```python
normalize_curie("DOID:9351")  # "MONDO:0007254"
normalize_curie("GO:0008150")  # "GO:0008150"
```

### parse_curie_or_uri(identifier: str) → tuple[str, str] | None

Parse identifier as CURIE or URI.

**Parameters:**
- `identifier`: CURIE ("DOID:9351") or URI ("http://purl.obolibrary.org/obo/DOID_9351")

**Returns:**
- Tuple of (prefix, identifier) if parseable
- None if unparsable

**Example:**
```python
parse_curie_or_uri("DOID:9351")  # ("doid", "9351")
parse_curie_or_uri("http://purl.obolibrary.org/obo/DOID_9351")  # ("doid", "9351")
parse_curie_or_uri("not-valid")  # None
```

### normalize_identifier(prefix: str, identifier: str) → str | None

Normalize an identifier's local part to its canonical bioregistry form
(e.g. stripping a redundant prefix like `"DOID:9351"` → `"9351"`) using
`curies`' `Converter.standardize_identifier()`. Returns `None` if bioregistry
is unavailable; an unregistered `prefix` still returns the identifier
unchanged, since only the identifier — not the prefix — is validated here.

**Parameters:**
- `prefix`: Prefix (e.g., "doid")
- `identifier`: Identifier (e.g., "9351")

**Returns:**
- Normalized identifier string

**Example:**
```python
normalize_identifier("doid", "9351")  # "9351"
normalize_identifier("go", "0008150")  # "0008150"
```

### validate_curie_pattern(prefix: str, identifier: str) → bool

Check if identifier matches prefix's regex pattern.

**Parameters:**
- `prefix`: Prefix (e.g., "doid")
- `identifier`: Identifier to validate

**Returns:**
- `True` if identifier matches pattern
- `False` otherwise

**Example:**
```python
validate_curie_pattern("doid", "9351")  # True
validate_curie_pattern("doid", "invalid!")  # False
```

### get_prefix_mapping() → dict[str, str]

Get the bioregistry prefix map.

**Returns:**
- Dictionary mapping every registered prefix (and its synonyms) to its
  canonical bioregistry prefix (not a URL — use `get_converter()` and its
  `.prefix_map` / `.expand()` for URI expansion).

**Example:**
```python
mappings = get_prefix_mapping()
mappings["DOID"]  # "doid"
```

## Adapter Implementation Guide

When implementing new adapters, use these utilities:

### 1. Import Required Functions

```python
from ..curie_utils import validate_prefix, normalize_curie, parse_curie_or_uri
```

### 2. Validate Prefix Before Queries

```python
async def search_concepts(self, query: str, limit: int = 20):
    # Validate source prefix
    if not validate_prefix(self.source.value.lower()):
        logger.warning(f"Invalid prefix for {self.source}")
        return []
```

### 3. Parse Query as CURIE/URI

```python
async def search_concepts(self, query: str, limit: int = 20):
    # Try to parse query as CURIE/URI
    parsed = parse_curie_or_uri(query)
    if parsed:
        prefix, identifier = parsed
        # Use normalized identifier for direct lookup
        ...
```

### 4. Normalize Identifiers in Results

```python
def _convert_result_to_concept(self, raw_result: dict) -> UnifiedConcept:
    identifier = raw_result.get("identifier", "")
    normalized = normalize_curie(f"{self.source}:{identifier}")
    # Use normalized CURIE in ConceptIdentifier
```

### 5. Validate Concept IDs

```python
async def get_concept_details(self, concept_id: str):
    # Validate concept_id
    parsed = parse_curie_or_uri(concept_id)
    if parsed:
        prefix, identifier = parsed
        if not validate_prefix(prefix):
            raise ValueError(f"Invalid prefix in concept_id: {concept_id}")
```

## Error Handling

### Graceful Degradation

```python
from ..curie_utils import parse_curie_or_uri, validate_prefix

def safe_parse(query: str):
    """Parse with fallback if utilities unavailable."""
    try:
        result = parse_curie_or_uri(query)
        return result
    except Exception:
        return None

def safe_validate(prefix: str) -> bool:
    """Validate with fallback if utilities unavailable."""
    try:
        return validate_prefix(prefix)
    except Exception:
        return False  # Assume valid if utilities unavailable
```

### Logging Warnings

```python
from ..curie_utils import validate_prefix
import logging

logger = logging.getLogger(__name__)

async def search_concepts(self, query: str):
    if not validate_prefix(self.source.value.lower()):
        logger.warning(f"Unknown prefix: {self.source}")
        # Continue anyway or return empty results
```

## Performance Considerations

### Cache Prefix Maps

```python
# Cache prefix mapping at module level
_PREFIX_MAP = None

def get_cached_prefix_map():
    global _PREFIX_MAP
    if _PREFIX_MAP is None:
        _PREFIX_MAP = get_prefix_mapping()
    return _PREFIX_MAP
```

### Batch Validation

```python
# Validate multiple prefixes efficiently
prefixes = ["doid", "go", "chebi"]
valid_prefixes = [p for p in prefixes if validate_prefix(p)]
```

## Troubleshooting

### Issue: validate_prefix() returns False for known prefix

**Solution:** Check if prefix is registered in bioregistry:
```python
# Use lowercase
validate_prefix("doid")  # Not "DOID"
```

### Issue: normalize_curie() returns original CURIE

**Solution:** This is expected for prefixes without bioregistry mappings. The function only normalizes if a mapping exists.

### Issue: parse_curie_or_uri() returns None

**Solution:** The identifier may not be in CURIE or URI format. Check the input:
```python
result = parse_curie_or_uri("DOID:9351")  # CURIE format
result = parse_curie_or_uri("http://purl.obolibrary.org/obo/DOID_9351")  # URI format
```

## See Also

- [Bioregistry Documentation](https://bioregistry.io/)
- [Curies Library](https://github.com/cthoyt/curies)
- [Pyobo Documentation](https://github.com/pyobo/pyobo)
