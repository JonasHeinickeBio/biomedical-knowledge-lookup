"""
Validation utilities using bioregistry for prefix and CURIE validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curies import Converter

__all__ = [
    "validate_prefix",
    "get_prefix_mapping",
    "get_bioregistry_converter",
    "create_local_converter",
    "validate_curie_pattern",
]

# Cache for prefix mapping to avoid repeated API calls
_PREFIX_MAP_CACHE: dict[str, str] | None = None


def get_bioregistry_converter() -> Converter | None:
    """Get bioregistry Converter for CURIE normalization and validation.

    Returns:
        bioregistry Converter instance, or None if bioregistry not available
    """
    try:
        from curies import get_bioregistry_converter as get_converter

        return get_converter()
    except Exception:
        return None


def validate_prefix(prefix: str) -> bool:
    """Validate if prefix exists in bioregistry.

    Args:
        prefix: Prefix to validate (case-insensitive)

    Returns:
        True if prefix is valid, False otherwise
    """
    converter = get_bioregistry_converter()
    if converter is None:
        return False

    prefix_lower = prefix.lower()
    return any(entry.prefix.lower() == prefix_lower for entry in converter.records)


def get_prefix_mapping() -> dict[str, str]:
    """Get mapping of prefixes to normalized forms from bioregistry.

    Returns:
        Dictionary mapping prefixes to their canonical forms
    """
    global _PREFIX_MAP_CACHE
    if _PREFIX_MAP_CACHE is not None:
        return _PREFIX_MAP_CACHE

    converter = get_bioregistry_converter()
    if converter is None:
        _PREFIX_MAP_CACHE = {}
        return _PREFIX_MAP_CACHE

    mapping = {entry.prefix: entry.prefix for entry in converter.records}
    _PREFIX_MAP_CACHE = mapping
    return mapping


def validate_curie_pattern(prefix: str, identifier: str) -> bool:
    """Validate if CURIE matches expected pattern from bioregistry.

    Args:
        prefix: CURIE prefix
        identifier: CURIE identifier

    Returns:
        True if CURIE pattern is valid, False otherwise
    """
    converter = get_bioregistry_converter()
    if converter is None:
        return False

    try:
        for record in converter.records:
            if record.prefix.lower() == prefix.lower():
                if record.pattern:
                    import re

                    pattern = record.pattern.lstrip("^").rstrip("$")
                    if re.match(pattern, identifier):
                        return True
                break
    except Exception:
        pass

    return False


def create_local_converter(prefix_map: dict[str, str]) -> Converter:
    """Create a local Converter from a prefix -> URI-prefix mapping.

    Args:
        prefix_map: Dictionary mapping CURIE prefixes to their URI prefixes,
            e.g. ``{"doid": "http://purl.obolibrary.org/obo/DOID_"}``. The
            value is used verbatim — callers are responsible for including
            any trailing separator their vocabulary expects (OBO ontologies
            typically use ``_``, not ``/``).

    Returns:
        Configured curies Converter instance
    """
    from curies import Converter, Record

    records = [Record(prefix=k, uri_prefix=v) for k, v in prefix_map.items()]
    return Converter(records=records, delimiter=":")


def get_source_prefix_mapping() -> dict[str, str]:
    """Get prefix mapping for all configured knowledge sources.

    Returns:
        Dictionary mapping source names to their CURIE prefixes
    """
    from ..models import KnowledgeSource

    mapping: dict[str, str] = {}
    converter = get_bioregistry_converter()
    for source in KnowledgeSource:
        source_name = source.value.lower()
        # Bioregistry prefix if registered, else the lowercased source name.
        try:
            standardized = converter.standardize_prefix(source_name) if converter else None
        except Exception:
            standardized = None
        mapping[source.value] = standardized or source_name

    return mapping
