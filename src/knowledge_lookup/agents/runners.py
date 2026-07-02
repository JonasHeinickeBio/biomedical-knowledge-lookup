"""High-level workflow runners."""

from __future__ import annotations

import uuid

from langgraph.types import Command

from .graph import build_workflow_graph
from .state import LookupWorkflowState, dict_to_lookup_result


async def run_workflow(
    query: str,
    *,
    max_results: int = 50,
    sources: list[str] | None = None,
    concept_types: list[str] | None = None,
    export_formats: list[str] | None = None,
    export_path: str | None = None,
    max_iterations: int = 3,
    auto_approve_threshold: float = 0.8,
) -> dict:
    """Run the full lookup-review-approval-export workflow.

    Args:
        query: Search query.
        max_results: Maximum results per search.
        sources: Optional list of source names to query.
        concept_types: Optional concept type filter.
        export_formats: Formats to export (default: ["json"]).
        export_path: Directory for export files.
        max_iterations: Maximum refinement rounds.
        auto_approve_threshold: Score above which auto-approval triggers.

    Returns:
        Dict with final state including results, review, and export paths.
    """
    graph = build_workflow_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: LookupWorkflowState = {
        "query": query,
        "max_results": max_results,
        "source_filter": sources,
        "concept_type_filter": concept_types,
        "export_formats": export_formats or ["json"],
        "export_path": export_path,
        "lookup_result": None,
        "review_score": None,
        "review_summary": None,
        "review_strengths": [],
        "review_weaknesses": [],
        "review_suggestions": [],
        "refinement_notes": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "auto_approve_threshold": auto_approve_threshold,
        "status": "pending",
        "errors": [],
        "final_result": None,
        "export_paths": [],
        "steps": [],
    }

    # Run the graph to completion (or interrupt)
    result = await graph.ainvoke(initial_state, config)

    return {
        "thread_id": thread_id,
        "status": result.get("status", "unknown"),
        "result": dict_to_lookup_result(
            result.get("final_result") or result.get("lookup_result")
        ),
        "review_score": result.get("review_score"),
        "review_summary": result.get("review_summary"),
        "export_paths": result.get("export_paths", []),
        "errors": result.get("errors", []),
        "steps": result.get("steps", []),
        "iteration": result.get("iteration", 0),
    }


async def resume_workflow(
    thread_id: str,
    decision: dict,
) -> dict:
    """Resume a workflow that was paused at the approval interrupt.

    Args:
        thread_id: The thread ID from the initial run.
        decision: User decision dict, e.g.:
            {"approved": True}
            {"approved": False, "refine": True, "notes": "Try different sources"}
            {"approved": False, "refine": False}

    Returns:
        Updated state dict.
    """
    graph = build_workflow_graph()
    config = {"configurable": {"thread_id": thread_id}}

    result = await graph.ainvoke(Command(resume=decision), config)

    return {
        "thread_id": thread_id,
        "status": result.get("status", "unknown"),
        "result": dict_to_lookup_result(
            result.get("final_result") or result.get("lookup_result")
        ),
        "review_score": result.get("review_score"),
        "review_summary": result.get("review_summary"),
        "export_paths": result.get("export_paths", []),
        "errors": result.get("errors", []),
        "steps": result.get("steps", []),
        "iteration": result.get("iteration", 0),
    }
