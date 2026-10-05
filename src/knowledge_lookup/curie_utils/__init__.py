"""
Curies integration utilities for CURIE validation and normalization.

This module provides utilities for integrating `curies` and `bioregistry` for:
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


def __getattr__(name: str):
    """``curies.Converter`` is re-exported lazily: ``curies`` is a sizeable import
    and optional, so it is only loaded if someone actually asks for ``Converter``."""
    if name == "Converter":
        try:
            from curies import Converter
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
        globals()["Converter"] = Converter
        return Converter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
