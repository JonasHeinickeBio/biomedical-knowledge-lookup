"""
Curies integration utilities for CURIE validation and normalization.

This module provides utilities for integrating `curies` and `pyobo` for:
- CURIE validation and normalization
- Reference model conversion
- Prefix validation via bioregistry
"""

from __future__ import annotations

from .normalization import (
    get_converter,
    get_prefix_mapping,
    normalize_curie,
    normalize_identifier,
    parse_curie_or_uri,
    validate_prefix,
)
from .reference import concept_identifier_to_reference, reference_to_concept_identifier
from .validation import (
    create_local_converter,
    get_bioregistry_converter,
    get_source_prefix_mapping,
    validate_curie_pattern,
)

__all__ = [
    "normalize_curie",
    "normalize_identifier",
    "parse_curie_or_uri",
    "validate_prefix",
    "get_prefix_mapping",
    "get_converter",
    "reference_to_concept_identifier",
    "concept_identifier_to_reference",
    "get_bioregistry_converter",
    "create_local_converter",
    "validate_curie_pattern",
    "get_source_prefix_mapping",
]

try:
    from curies import Converter  # noqa: F401 - re-exported below

    __all__.append("Converter")
except ImportError:
    pass
