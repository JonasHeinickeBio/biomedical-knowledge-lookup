"""Graph node: knowledge lookup."""

from __future__ import annotations

import logging

from ...core.central_lookup import CentralKnowledgeLookup
from ...models import KnowledgeSource, LookupConfig
from ..state import LookupWorkflowState, lookup_result_to_dict, make_step

logger = logging.getLogger(__name__)


async def lookup_node(state: LookupWorkflowState) -> dict:
    """Execute knowledge lookup across configured sources."""
    query = state["query"]
    iteration = state["iteration"]

    # Build config
    config = LookupConfig(
        max_results_per_source=state["max_results"],
        parallel_queries=True,
        enable_deduplication=True,
        enable_source_health_tracking=True,
    )

    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        # Resolve sources
        sources: list[KnowledgeSource] | None = None
        source_filter = state.get("source_filter")
        if source_filter:
            resolved_sources: list[KnowledgeSource] = []
            for name in source_filter:
                try:
                    src = KnowledgeSource(name.upper())
                    if src in lookup.adapters:
                        resolved_sources.append(src)
                except ValueError:
                    pass
            sources = resolved_sources if resolved_sources else None

        # Resolve concept types
        concept_types = None
        ct_filter = state.get("concept_type_filter")
        if ct_filter:
            from ...models import ConceptType

            resolved_types: list = []
            for ct in ct_filter:
                try:
                    resolved_types.append(ConceptType(ct.upper()))
                except ValueError:
                    pass
            concept_types = resolved_types if resolved_types else None

        result = await lookup.search_concepts(
            query=query,
            concept_types=concept_types,
            sources=sources,
            max_results=state["max_results"],
            parallel=True,
        )

        result_dict = lookup_result_to_dict(result)
        n_concepts = len(result.concepts or [])
        n_sources = len(result.sources_succeeded or [])

        return {
            "lookup_result": result_dict,
            "status": "reviewing",
            "iteration": iteration + 1,
            "errors": [],
            "steps": [
                make_step(
                    "LookupAgent",
                    "search",
                    f"Found {n_concepts} concepts from {n_sources} sources (iter {iteration + 1})",
                )
            ],
        }

    except Exception as e:
        return {
            "status": "failed",
            "errors": [f"Lookup failed: {e}"],
            "steps": [make_step("LookupAgent", "error", str(e))],
        }
    finally:
        await lookup.close()
