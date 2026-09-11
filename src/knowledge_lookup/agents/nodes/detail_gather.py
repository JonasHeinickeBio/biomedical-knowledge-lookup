"""Graph node: cross-source detail gathering for each concept.

For each unique concept label found in the initial search, this node runs
independent searches against ALL configured sources (OLS, UMLS, BioPortal,
Wikidata, etc.) to collect:

- Cross-references / ontology IDs from multiple sources
- Definitions and synonyms from each source
- Semantic types and categories

This gives the LLM rich, multi-perspective data about every concept.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ...core.central_lookup import CentralKnowledgeLookup
from ...models import ConceptIdentifier, KnowledgeSource, LookupConfig
from ..state import LookupWorkflowState, dict_to_lookup_result, lookup_result_to_dict, make_step

logger = logging.getLogger(__name__)

_PER_LABEL_TIMEOUT = 20.0

# Sources to query per label for cross-referencing
# Ordered by likely relevance for biomedical concept lookup
_CROSS_SOURCES = [
    KnowledgeSource.OLS,
    KnowledgeSource.UMLS,
    KnowledgeSource.BIOPORTAL,
    KnowledgeSource.WIKIDATA,
    KnowledgeSource.MONDO,
    KnowledgeSource.HPO,
]


async def _search_label(
    lookup: CentralKnowledgeLookup,
    label: str,
    source: KnowledgeSource,
    timeout: float = _PER_LABEL_TIMEOUT,
) -> list[Any]:
    """Search a single source by concept label.

    Returns a list of UnifiedConcept results (or empty).
    """
    try:
        result = await asyncio.wait_for(
            lookup.search_concepts(
                query=label,
                sources=[source],
                max_results=3,
                parallel=False,
            ),
            timeout=timeout,
        )
        return result.concepts or []
    except asyncio.TimeoutError:
        logger.debug("Timeout searching '%s' in %s", label, source)
        return []
    except Exception as exc:
        logger.debug("Error searching '%s' in %s: %s", label, source, exc)
        return []


def _collect_ontology_ids(concepts: list[Any]) -> dict[str, set[str]]:
    """Collect all ontology IDs from a list of concepts, grouped by source."""
    ids: dict[str, set[str]] = {}
    for c in concepts:
        # Primary ID
        src_names = [str(s) for s in (c.sources or [])]
        for src in src_names:
            if src not in ids:
                ids[src] = set()
            if c.primary_id:
                ids[src].add(c.primary_id)
        # Identifiers
        for ident in c.identifiers or []:
            src = str(ident.source) if hasattr(ident.source, "value") else str(ident.source)
            if src not in ids:
                ids[src] = set()
            if ident.identifier:
                ids[src].add(ident.identifier)
    return ids


def _collect_text_fields(concepts: list[Any], field: str, max_per_source: int = 3) -> list[str]:
    """Collect unique text values for a field (definitions, synonyms) across concepts."""
    seen: set[str] = set()
    results: list[str] = []
    for c in concepts:
        vals = getattr(c, field, None) or []
        for v in vals:
            key = str(v).strip().lower()[:200]
            if key and key not in seen:
                seen.add(key)
                results.append(str(v))
                if len(results) >= max_per_source:
                    break
        if len(results) >= max_per_source:
            break
    return results


def _collect_types(concepts: list[Any]) -> list[str]:
    """Collect unique concept types across concepts."""
    seen: set[str] = set()
    results: list[str] = []
    for c in concepts:
        t = str(c.concept_type) if c.concept_type else None
        if t and t not in seen:
            seen.add(t)
            results.append(t)
    return results


async def detail_gather_node(state: LookupWorkflowState) -> dict:
    """Cross-source detail gathering: search every concept label against
    ALL configured sources independently.

    For each unique concept label found in the search results, this node
    runs parallel searches against OLS, UMLS, BioPortal, Wikidata, and
    other relevant sources. All discovered identifiers, definitions,
    synonyms, and types are merged back into the concept.
    """
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None or not result.concepts:
        return {
            "status": state.get("status", "reviewing"),
            "steps": [make_step("DetailGatherAgent", "skip", "No concepts to process")],
        }

    config = LookupConfig(
        max_results_per_source=5,
        parallel_queries=True,
        enable_deduplication=False,
        enable_source_health_tracking=False,
    )

    # Only load the sources we actually need for cross-referencing
    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)

    # Identify which cross-sources are actually available
    available_cross_sources = [s for s in _CROSS_SOURCES if s in lookup.adapters]

    try:
        concepts = result.concepts

        # Get unique labels (case-insensitive dedup)
        seen_labels: dict[str, int] = {}  # label_lower -> index in concepts
        for i, c in enumerate(concepts):
            label = (c.primary_label or "").strip().lower()
            if label and label not in seen_labels:
                seen_labels[label] = i

        unique_labels = [(concepts[idx].primary_label, idx) for label, idx in seen_labels.items()]

        total_cross_refs = 0
        total_defs = 0

        # For each unique label, search across all sources independently
        for label_text, concept_idx in unique_labels:
            if not label_text:
                continue

            concept = concepts[concept_idx]

            # Run independent searches for this label against all cross-sources
            search_tasks = [
                _search_label(lookup, label_text, src) for src in available_cross_sources
            ]
            per_source_results: list[list[Any]] = await asyncio.gather(*search_tasks)

            # Collect all cross-source findings
            all_found: list[Any] = []
            seen_ids: set[str] = set()
            for src_results in per_source_results:
                for c in src_results:
                    cid = c.primary_id or ""
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        all_found.append(c)

            if not all_found:
                logger.debug("No cross-source results for '%s'", label_text)
                continue

            # --- Merge cross-source data into the concept ---

            # 1. Collect all ontology IDs
            cross_ids = _collect_ontology_ids(all_found)
            for src_name, ids in cross_ids.items():
                for cid in ids:
                    # Add as identifier if not already present
                    exists = any(
                        str(getattr(i, "source", "")).upper() == src_name.upper()
                        and i.identifier == cid
                        for i in (concept.identifiers or [])
                    )
                    if not exists:
                        try:
                            ks = KnowledgeSource(src_name.upper())
                        except ValueError:
                            continue
                        if concept.identifiers is None:
                            concept.identifiers = []
                        concept.identifiers.append(
                            ConceptIdentifier(
                                source=ks,
                                identifier=cid,
                                label=label_text,
                            )
                        )
                        total_cross_refs += 1

            # 2. Merge definitions (from any source)
            new_defs = _collect_text_fields(all_found, "definitions")
            for d in new_defs:
                if d and (not concept.definitions or d not in concept.definitions):
                    if concept.definitions is None:
                        concept.definitions = []
                    concept.definitions.append(d)
                    total_defs += 1

            # 3. Merge synonyms
            new_syns = _collect_text_fields(all_found, "synonyms")
            existing_syns = {s.lower() for s in (concept.synonyms or [])}
            for syn in new_syns:
                if syn and syn.lower() not in existing_syns:
                    if concept.synonyms is None:
                        concept.synonyms = []
                    concept.synonyms.append(syn)
                    existing_syns.add(syn.lower())

            # 4. Merge semantic types
            new_types = _collect_types(all_found)
            existing_types = {str(t) for t in (concept.semantic_types or [])}
            for t in new_types:
                if t not in existing_types:
                    if concept.semantic_types is None:
                        concept.semantic_types = []
                    concept.semantic_types.append(t)
                    existing_types.add(t)

            # 5. Track all contributing sources
            for src_results in per_source_results:
                if src_results:
                    src_name = (
                        str(src_results[0].sources[0]).upper() if src_results[0].sources else ""
                    )
                    if src_name and not any(
                        str(s).upper() == src_name for s in (concept.sources or [])
                    ):
                        if concept.sources is None:
                            concept.sources = []
                        concept.sources.append(src_name)  # type: ignore[arg-type]
                    break

        # Re-serialize the enriched result
        enriched_dict = lookup_result_to_dict(result)

        step_parts = []
        if total_cross_refs:
            step_parts.append(f"{total_cross_refs} cross-refs")
        if total_defs:
            step_parts.append(f"{total_defs} definitions")
        step_detail = (
            "Cross-source gathered " + ", ".join(step_parts)
            if step_parts
            else "Processed concepts"
        )

        return {
            "lookup_result": enriched_dict,
            "steps": [make_step("DetailGatherAgent", "cross_search", step_detail)],
        }

    except Exception as exc:
        logger.warning("Detail gathering failed: %s", exc)
        return {
            "errors": [f"Detail gathering failed: {exc}"],
            "steps": [make_step("DetailGatherAgent", "error", str(exc))],
        }
    finally:
        await lookup.close()
