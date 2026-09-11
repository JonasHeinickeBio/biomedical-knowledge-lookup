from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curies import Converter

__all__ = [
    "normalize_curie",
    "parse_curie_or_uri",
    "validate_prefix",
    "get_prefix_mapping",
    "normalize_identifier",
    "get_converter",
]


def get_converter() -> Converter | None:
    """Get the shared bioregistry Converter for CURIE normalization."""
    try:
        from curies import get_bioregistry_converter

        return get_bioregistry_converter()
    except Exception:
        return None


def normalize_identifier(prefix: str, identifier: str) -> str | None:
    """Normalize an identifier's local part to its canonical bioregistry form."""
    converter = get_converter()
    if converter is None:
        return None
    try:
        return converter.standardize_identifier(prefix, identifier)
    except Exception:
        return None


def normalize_curie(curie: str) -> str | None:
    """Normalize a CURIE string (prefix + identifier) using bioregistry via curies."""
    converter = get_converter()
    if converter is None:
        return None
    try:
        return converter.standardize_curie(curie) or curie
    except Exception:
        return None


def parse_curie_or_uri(identifier: str) -> tuple[str, str] | None:
    """Parse a CURIE or a URI into a ``(prefix, identifier)`` tuple."""
    converter = get_converter()
    if converter is None:
        return None
    try:
        result = converter.parse(identifier)
    except Exception:
        return None
    if result is None or not result.prefix or not result.identifier:
        return None
    return (result.prefix, result.identifier)


def validate_prefix(prefix: str) -> bool:
    """Validate whether a prefix (or one of its synonyms) is known to bioregistry."""
    converter = get_converter()
    if converter is None:
        return False
    try:
        return converter.has_prefix(prefix)
    except Exception:
        return False


def get_prefix_mapping() -> dict[str, str]:
    """Map every registered prefix (and its synonyms) to its canonical bioregistry prefix."""
    converter = get_converter()
    if converter is None:
        return {}
    try:
        mapping: dict[str, str] = {}
        for record in converter.records:
            mapping[record.prefix] = record.prefix
            for synonym in record.prefix_synonyms or []:
                mapping[synonym] = record.prefix
        return mapping
    except Exception:
        return {}
