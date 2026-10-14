"""Shared helpers for adapters that surface external identifiers (cross-references)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import KnowledgeSource


@dataclass(frozen=True)
class ExternalId:
    """How one external-identifier property is surfaced on a concept.

    ``source`` set  -> ``concept.add_identifier(source, value)``.
    ``source`` None -> kept as a ``"<label>: <value>"`` category (no KnowledgeSource).
    ``prefix`` is added when the source stores the bare number (e.g. ChEBI ``15377``).
    ``pattern`` (a regex, matched against the whole normalized value) drops values that
    are not of the expected shape, e.g. DBpedia's ATC ``"Combinations:"``.
    ``url`` is a ``str.format`` template (``{id}``, or ``{obo}`` for the OBO IRI form
    ``DOID_8778``) for the identifier's landing page.
    """

    label: str
    source: KnowledgeSource | None = None
    prefix: str = ""
    url: str | None = None
    pattern: str | None = None


def normalize_external_id(spec: ExternalId, value: str) -> str:
    """Strip stray whitespace/trailing dots and add ``spec.prefix`` when it is missing.

    DBpedia stores some ICD codes as ``"E11."``; no identifier here ends in a dot.
    """
    value = value.strip().rstrip(".")
    if spec.prefix and not value.upper().startswith(spec.prefix.upper()):
        return f"{spec.prefix}{value}"
    return value


def identifier_url(spec: ExternalId, value: str) -> str | None:
    """Landing-page URL for *value*, or ``None`` when the spec has no template."""
    if not spec.url:
        return None
    return spec.url.format(id=value, obo=value.replace(":", "_"))


def has_content(value: str) -> bool:
    """False for empty or punctuation-only junk values (DBpedia has e.g. ``","``)."""
    return any(ch.isalnum() for ch in value)


def is_valid_external_id(spec: ExternalId, value: str) -> bool:
    """True when *value* has content and matches ``spec.pattern`` (when it has one)."""
    if not has_content(value):
        return False
    return spec.pattern is None or re.fullmatch(spec.pattern, value) is not None
