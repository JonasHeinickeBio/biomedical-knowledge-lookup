from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curies import Reference

__all__ = ["reference_to_concept_identifier", "concept_identifier_to_reference"]


def reference_to_concept_identifier(reference: Reference) -> dict:
    """Convert curies Reference to ConceptIdentifier dict.

    A bare ``Reference`` only carries prefix/identifier, not a resolvable URI
    (that requires a ``Converter``), so ``url`` is left unset here.
    """
    return {
        "source": reference.prefix.upper(),
        "identifier": reference.identifier,
        "label": None,
        "url": None,
    }


def concept_identifier_to_reference(
    concept_identifier: dict,
) -> Reference | None:
    """Convert ConceptIdentifier dict to curies Reference."""
    try:
        from curies import Reference

        source = concept_identifier.get("source", "")
        identifier = concept_identifier.get("identifier", "")
        if source and identifier:
            return Reference(prefix=source.lower(), identifier=identifier)
    except Exception:
        pass
    return None
