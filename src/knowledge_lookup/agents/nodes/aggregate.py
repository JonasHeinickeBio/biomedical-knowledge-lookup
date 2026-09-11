"""Graph node: aggregate all concept details into comprehensive LLM context.

Takes the enriched lookup result (with full details, hierarchy, mappings)
and builds a structured text report that the LLM review node uses for
in-depth quality assessment.
"""

from __future__ import annotations

import logging
from typing import Any

from ..state import LookupWorkflowState, dict_to_lookup_result, make_step

logger = logging.getLogger(__name__)


def _format_source_list(sources: list[Any] | None) -> str:
    """Format a list of sources for display."""
    if not sources:
        return "—"
    return ", ".join(str(s) for s in sources if s)


def _build_concept_report(concept: Any, idx: int) -> str:
    """Build a detailed text block for a single concept."""
    lines: list[str] = []
    lines.append(f"--- Concept {idx} ---")
    lines.append(f"  Label:       {concept.primary_label or 'N/A'}")
    lines.append(f"  ID:          {concept.primary_id or 'N/A'}")
    lines.append(f"  Type:        {concept.concept_type or 'N/A'}")
    lines.append(f"  Confidence:  {concept.confidence_score or 0:.2f}")
    lines.append(f"  Sources:     {_format_source_list(getattr(concept, 'sources', None))}")

    # Definitions
    defs = concept.definitions
    if defs:
        for i, d in enumerate(defs[:3]):
            lines.append(f"  Definition {i+1}: {d[:300]}")
        if len(defs) > 3:
            lines.append(f"  ... ({len(defs) - 3} more definitions)")

    # Synonyms
    syns = concept.synonyms
    if syns:
        syn_text = "; ".join(str(s) for s in syns[:10])
        if len(syns) > 10:
            syn_text += f" ... (+{len(syns) - 10} more)"
        lines.append(f"  Synonyms:    {syn_text}")

    # Semantic types
    sem_types = concept.semantic_types
    if sem_types:
        st_text = "; ".join(str(s) for s in sem_types[:5])
        if len(sem_types) > 5:
            st_text += f" ... (+{len(sem_types) - 5} more)"
        lines.append(f"  Sem. Types:  {st_text}")

    # Categories
    cats = concept.categories
    if cats:
        lines.append(f"  Categories:  {'; '.join(str(c) for c in cats[:5])}")

    # UMLS CUI
    umls_cui = None
    for ident in concept.identifiers or []:
        if str(ident.source).upper() in ("UMLS",):
            umls_cui = ident.identifier
            break
    if umls_cui:
        lines.append(f"  UMLS CUI:    {umls_cui}")
    else:
        lines.append("  UMLS CUI:    —")

    # Parent concepts
    parents = concept.parents
    if parents:
        lines.append(f"  Parents:     {'; '.join(str(p) for p in parents[:5])}")
        if len(parents) > 5:
            lines.append(f"               ... (+{len(parents) - 5} more)")

    # Child concepts
    children = concept.children
    if children:
        lines.append(f"  Children:    {'; '.join(str(c) for c in children[:5])}")
        if len(children) > 5:
            lines.append(f"               ... (+{len(children) - 5} more)")

    # Mappings / cross-references
    mappings = concept.mappings
    if mappings:
        lines.append(f"  Mappings:    {len(mappings)} cross-reference(s)")
        for m in mappings[:8]:
            lines.append(f"    - {m.source}: {m.identifier} ({m.label or 'N/A'})")
        if len(mappings) > 8:
            lines.append(f"    ... (+{len(mappings) - 8} more)")

    # All identifiers
    identifiers = concept.identifiers
    if identifiers:
        all_ids = set()
        id_lines = []
        for ident in identifiers:
            key = f"{ident.source}:{ident.identifier}"
            if key not in all_ids:
                all_ids.add(key)
                id_lines.append(f"    - {key}")
        if id_lines:
            lines.append(f"  Identifiers: ({len(all_ids)} total)")
            lines.extend(id_lines[:12])
            if len(id_lines) > 12:
                lines.append(f"    ... (+{len(id_lines) - 12} more)")

    return "\n".join(lines)


def _build_cross_concept_analysis(concepts: list[Any]) -> str:
    """Build cross-concept analysis showing relationships and overlaps."""
    lines: list[str] = []
    lines.append("--- Cross-Concept Analysis ---")

    # Source coverage
    source_counts: dict[str, int] = {}
    for c in concepts:
        for s in c.sources or []:
            source_counts[str(s)] = source_counts.get(str(s), 0) + 1
    lines.append(f"  Sources contributing: {', '.join(sorted(source_counts.keys()))}")
    lines.append(f"  Total concepts: {len(concepts)}")

    # Type distribution
    type_counts: dict[str, int] = {}
    for c in concepts:
        t = str(c.concept_type) if c.concept_type else "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts:
        lines.append("  Type distribution:")
        for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    - {t}: {cnt}")

    # Overlapping concepts (same label from multiple sources)
    labels_seen: dict[str, list[str]] = {}
    for c in concepts:
        label = (c.primary_label or "").lower().strip()
        if label:
            if label not in labels_seen:
                labels_seen[label] = []
            for s in c.sources or []:
                if str(s) not in labels_seen[label]:
                    labels_seen[label].append(str(s))
    overlaps = {k: v for k, v in labels_seen.items() if len(v) > 1}
    if overlaps:
        lines.append("  Overlaps (concept found in multiple sources):")
        for label, sources in sorted(overlaps.items()):
            lines.append(f"    - \"{label}\" found in: {', '.join(sources)}")

    # UMLS CUI coverage
    umls_count = sum(
        1
        for c in concepts
        for ident in (c.identifiers or [])
        if str(ident.source).upper() in ("UMLS",)
    )
    lines.append(f"  UMLS CUI coverage: {umls_count}/{len(concepts)} concepts")

    return "\n".join(lines)


def _build_summary_statistics(concepts: list[Any], query: str) -> str:
    """Build summary statistics block."""
    lines: list[str] = []
    lines.append("--- Summary Statistics ---")
    lines.append(f'  Query: "{query}"')
    lines.append(f"  Total concepts: {len(concepts)}")

    # Average confidence
    confs = [c.confidence_score or 0.0 for c in concepts]
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    lines.append(f"  Average confidence: {avg_conf:.3f}")

    # Definitions coverage
    with_defs = sum(1 for c in concepts if c.definitions)
    lines.append(f"  Concepts with definitions: {with_defs}/{len(concepts)}")

    # Synonyms coverage
    with_syns = sum(1 for c in concepts if c.synonyms)
    lines.append(f"  Concepts with synonyms: {with_syns}/{len(concepts)}")

    # Hierarchy coverage
    with_parents = sum(1 for c in concepts if c.parents)
    with_children = sum(1 for c in concepts if c.children)
    lines.append(f"  Concepts with parents: {with_parents}/{len(concepts)}")
    lines.append(f"  Concepts with children: {with_children}/{len(concepts)}")

    # Mapping coverage
    with_mappings = sum(1 for c in concepts if c.mappings)
    lines.append(f"  Concepts with cross-mappings: {with_mappings}/{len(concepts)}")

    return "\n".join(lines)


async def aggregate_node(state: LookupWorkflowState) -> dict:
    """Aggregate all concept details into a comprehensive text report.

    Takes the enriched lookup result, extracts full details for each
    concept, and builds a structured text context for the LLM review.
    """
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None or not result.concepts:
        return {
            "aggregated_context": "",
            "steps": [make_step("AggregateAgent", "skip", "No concepts to aggregate")],
        }

    concepts = result.concepts
    query = state["query"]

    # Build the three sections
    summary_stats = _build_summary_statistics(concepts, query)

    concept_reports: list[str] = []
    for i, concept in enumerate(concepts, 1):
        concept_reports.append(_build_concept_report(concept, i))
    concepts_section = "\n\n".join(concept_reports)

    cross_analysis = _build_cross_concept_analysis(concepts)

    # Combine into final context
    context = (
        f"# Biomedical Knowledge Lookup Report\n\n"
        f"{summary_stats}\n\n"
        f"{concepts_section}\n\n"
        f"{cross_analysis}\n"
    )

    return {
        "aggregated_context": context,
        "steps": [
            make_step(
                "AggregateAgent",
                "aggregate",
                f"Built context with {len(concepts)} concepts, "
                f"{sum(1 for c in concepts if c.definitions)} definitions, "
                f"{sum(1 for c in concepts if c.parents)} with hierarchy",
            )
        ],
    }
