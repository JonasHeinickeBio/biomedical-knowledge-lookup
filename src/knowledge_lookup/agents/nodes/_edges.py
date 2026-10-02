"""Helpers for relationship-edge records shared by the expansion nodes.

An edge record is the dict shape :func:`knowledge_lookup.core.term_expansion.expand_and_search`
persists: ``source_concept_id``, ``source_concept_label``, ``relation_label``,
``related_id``, ``related_name``, ``related_source``, ``concept_type`` and ``searched``.
"""

from __future__ import annotations

from typing import Any

from ...core.term_expansion import RelatedTerm


def edge_key(edge: dict[str, Any]) -> tuple[str, str, str]:
    """Identity of an edge: source concept, relation and target."""
    return (
        str(edge.get("source_concept_id") or ""),
        str(edge.get("relation_label") or "").lower(),
        str(edge.get("related_id") or ""),
    )


def merge_edges(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """*existing* followed by the edges of *new* it does not already hold.

    When both lists hold the same edge the ``searched`` flag is OR-ed, so an
    edge already searched in one place stays marked as searched.
    """
    merged = [dict(e) for e in existing]
    index = {edge_key(e): i for i, e in enumerate(merged)}
    for edge in new:
        key = edge_key(edge)
        if key in index:
            if edge.get("searched"):
                merged[index[key]]["searched"] = True
            continue
        index[key] = len(merged)
        merged.append(dict(edge))
    return merged


def edge_from_related_term(
    concept: Any, term: RelatedTerm, *, searched: bool = False
) -> dict[str, Any]:
    """Build an edge record for *term*, harvested from *concept*."""
    name = (term.term or "").strip()
    return {
        "source_concept_id": getattr(concept, "primary_id", "") or "",
        "source_concept_label": (getattr(concept, "primary_label", "") or "").strip(),
        "relation_label": term.relation_label,
        "related_id": term.related_id,
        "related_name": name or None,
        "related_source": term.source,
        "concept_type": getattr(term.concept_type, "value", term.concept_type),
        "searched": searched,
    }
