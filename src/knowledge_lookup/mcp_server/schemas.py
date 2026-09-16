"""
Response models for the MCP server's tools.

Every tool is annotated to return one of these models, so the SDK publishes an
``outputSchema`` for it and each result carries ``structuredContent`` plus a
JSON text mirror for clients that only read ``content``. Optional fields that
are ``None`` or empty are omitted when serialized, so a response only costs the
model tokens for data that is actually there.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer

ResponseFormat = Literal["concise", "detailed"]

# Per-field caps keep one verbose concept from dominating a response.
_CONCISE_DEFINITION_CHARS = 300
_DETAILED_DEFINITION_CHARS = 1500
_DETAILED_MAX_DEFINITIONS = 10
_CONCISE_SYNONYMS = 5
_DETAILED_LIST_ITEMS = 50


class _CompactModel(BaseModel):
    """Omits optional fields whose value is ``None`` or an empty container."""

    @model_serializer(mode="wrap")
    def _omit_empty(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        required = {name for name, field in type(self).model_fields.items() if field.is_required()}
        return {k: v for k, v in data.items() if k in required or v not in (None, [], {})}


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


_OBO_UNDERSCORE_ID = re.compile(r"^([A-Za-z][A-Za-z0-9]*)_(\d+)$")
_OBO_TERM_IRI = re.compile(
    r"(?:purl\.obolibrary\.org/obo|ebi\.ac\.uk/efo|orpha\.net/ORDO)/([A-Za-z][A-Za-z0-9]*)_(\d+)$"
)


def display_id(identifier: str) -> str:
    """Show OBO-style IDs as CURIEs so they can be passed straight to another tool.

    OLS-backed adapters report them as 'MONDO_0005148' or as a term IRI such as
    'http://www.ebi.ac.uk/efo/EFO_0000400'; those become 'MONDO:0005148' and
    'EFO:0000400'. Anything else is returned unchanged.
    """
    identifier = identifier.strip()
    match = (_OBO_TERM_IRI.search if "://" in identifier else _OBO_UNDERSCORE_ID.match)(identifier)
    return f"{match.group(1)}:{match.group(2)}" if match else identifier


def _unique(items: Iterable[Any] | None, limit: int | None = None) -> list[str]:
    """Stringify, strip and case-insensitively de-duplicate, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
            if limit is not None and len(out) >= limit:
                break
    return out


class CrossReference(_CompactModel):
    """An identifier for the same (or a closely related) concept in another vocabulary."""

    id: str = Field(description="Identifier, usually a CURIE such as 'MESH:D003924'.")
    source: str = Field(description="Knowledge source or vocabulary prefix, e.g. 'UMLS', 'MESH'.")
    label: str | None = Field(default=None, description="Label in that vocabulary, when known.")
    distance: int | None = Field(
        default=None, description="OxO mapping hops; 1 is a direct cross-reference."
    )


class Concept(_CompactModel):
    """A biomedical concept as returned by one or more knowledge sources."""

    id: str = Field(
        description="Primary identifier, usually a CURIE, e.g. 'HP:0001250' or 'MONDO:0005148'."
    )
    label: str = Field(description="Preferred label.")
    type: str | None = Field(
        default=None,
        description=(
            "Concept type, e.g. DISEASE, PHENOTYPE, GENE, PROTEIN, CHEMICAL. "
            "UNKNOWN when the source does not classify its concepts."
        ),
    )
    sources: list[str] = Field(
        default_factory=list, description="Knowledge sources that returned this concept."
    )
    score: float | None = Field(
        default=None,
        description=(
            "Source-reported match confidence in [0, 1]. Useful for ranking hits from one "
            "source; not calibrated across sources."
        ),
    )
    definition: str | None = Field(
        default=None, description="First definition, truncated (concise format)."
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Alternative labels (only the first few when concise)."
    )
    definitions: list[str] = Field(
        default_factory=list, description="All definitions (detailed format)."
    )
    semantic_types: list[str] = Field(
        default_factory=list, description="Semantic types, e.g. UMLS semantic types (detailed)."
    )
    categories: list[str] = Field(
        default_factory=list, description="Source-specific categories (detailed)."
    )
    xrefs: list[CrossReference] = Field(
        default_factory=list,
        description="Identifiers of this concept in other sources (detailed).",
    )
    parents: list[str] = Field(default_factory=list, description="Parent concept IDs (detailed).")
    children: list[str] = Field(default_factory=list, description="Child concept IDs (detailed).")

    @classmethod
    def from_unified(
        cls, concept: Any, response_format: ResponseFormat = "concise", **extra: Any
    ) -> Any:
        """Build from a library ``UnifiedConcept``; *extra* sets subclass-only fields."""
        label = concept.primary_label or concept.primary_id
        definitions = _unique(concept.definitions)
        synonyms = [s for s in _unique(concept.synonyms) if s.lower() != label.lower()]
        primary_id = display_id(concept.primary_id)
        fields: dict[str, Any] = {
            "id": primary_id,
            "label": label,
            "type": _enum_value(concept.concept_type)
            if concept.concept_type is not None
            else None,
            "sources": _unique(_enum_value(s) for s in concept.sources or []),
            "score": (
                round(concept.confidence_score, 3)
                if concept.confidence_score is not None
                else None
            ),
            **extra,
        }

        if response_format == "concise":
            return cls(
                **fields,
                definition=(
                    _clip(definitions[0], _CONCISE_DEFINITION_CHARS) if definitions else None
                ),
                synonyms=synonyms[:_CONCISE_SYNONYMS],
            )

        xrefs: list[CrossReference] = []
        seen_ids = {primary_id}
        for ident in concept.identifiers or []:
            ident_id = display_id(getattr(ident, "identifier", None) or "")
            if not ident_id or ident_id in seen_ids:
                continue
            seen_ids.add(ident_id)
            xrefs.append(
                CrossReference(
                    id=ident_id,
                    source=_enum_value(ident.source),
                    label=getattr(ident, "label", None) or None,
                )
            )

        return cls(
            **fields,
            definitions=[
                _clip(d, _DETAILED_DEFINITION_CHARS)
                for d in definitions[:_DETAILED_MAX_DEFINITIONS]
            ],
            synonyms=synonyms[:_DETAILED_LIST_ITEMS],
            semantic_types=_unique(concept.semantic_types, _DETAILED_LIST_ITEMS),
            categories=_unique(concept.categories, _DETAILED_LIST_ITEMS),
            xrefs=xrefs[:_DETAILED_LIST_ITEMS],
            parents=[display_id(p) for p in _unique(concept.parents, _DETAILED_LIST_ITEMS)],
            children=[display_id(c) for c in _unique(concept.children, _DETAILED_LIST_ITEMS)],
        )


class ConceptDetail(Concept):
    """A single resolved concept."""

    resolved_via: str = Field(description="Knowledge source that resolved the identifier.")


class SearchResponse(_CompactModel):
    """One page of concept search results."""

    query: str
    total: int = Field(
        description=(
            "Distinct concepts found across the searched sources (after de-duplication), "
            "before pagination."
        )
    )
    count: int = Field(description="Concepts in this page.")
    offset: int
    has_more: bool
    next_offset: int | None = Field(
        default=None, description="Pass as `offset` to fetch the next page."
    )
    concepts: list[Concept]
    sources_searched: list[str]
    source_errors: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Sources that failed or timed out, with the reason. Results from the other "
            "sources are still returned."
        ),
    )
    expanded_terms: list[str] = Field(
        default_factory=list,
        description="Additional synonym / long-form terms that were also searched.",
    )
    warnings: list[str] = Field(default_factory=list)


class MappingsResponse(_CompactModel):
    """Cross-references for one concept."""

    concept_id: str
    label: str | None = None
    count: int
    mappings: list[CrossReference]
    warnings: list[str] = Field(default_factory=list)


class SourceInfo(_CompactModel):
    """Status of one knowledge source."""

    name: str
    description: str
    available: bool
    in_default_search: bool = Field(
        description="Searched when biomed_search_concepts is called without `sources`."
    )
    requires: str | None = Field(
        default=None, description="What is needed to enable this source when it is unavailable."
    )
    circuit_state: str | None = Field(
        default=None,
        description="'open' means the source kept failing and is skipped until it cools down.",
    )


class SourcesResponse(_CompactModel):
    """Catalog of knowledge sources."""

    available_count: int
    default_search_sources: list[str]
    sources: list[SourceInfo]


class CurieValidation(_CompactModel):
    """Validation and normalization result for one identifier."""

    input: str
    valid: bool = Field(
        description=(
            "True when the prefix is registered in Bioregistry and the local ID matches the "
            "prefix's pattern (or the prefix defines no pattern)."
        )
    )
    curie: str | None = Field(default=None, description="Normalized CURIE, e.g. 'HP:0001250'.")
    prefix: str | None = None
    local_id: str | None = None
    uri: str | None = Field(default=None, description="Expanded URI (IRI).")
    pattern: str | None = Field(
        default=None, description="Regular expression that local IDs for this prefix must match."
    )
    resolvable_via: str | None = Field(
        default=None, description="Knowledge source biomed_get_concept routes this identifier to."
    )
    message: str | None = None
