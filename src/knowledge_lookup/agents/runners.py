"""High-level workflow runners.

``run_workflow`` and ``resume_workflow`` share one checkpointer so that a run
paused at the approval gate can be resumed later with its ``thread_id``. By
default this is a process-wide :class:`~langgraph.checkpoint.memory.InMemorySaver`
(paused runs live as long as the Python process); pass your own
``checkpointer`` to both calls to persist paused runs elsewhere.
"""

from __future__ import annotations

import uuid

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .graph import build_workflow_graph
from .state import LookupWorkflowState, dict_to_lookup_result

#: Status reported while a run is paused at the approval gate.
STATUS_AWAITING_APPROVAL = "awaiting_approval"

# Shared by every run/resume in this process that doesn't pass its own
# checkpointer — a fresh saver per call would lose the paused thread's state.
_DEFAULT_CHECKPOINTER = InMemorySaver()


def get_default_checkpointer() -> InMemorySaver:
    """Return the process-wide checkpointer used when none is passed."""
    return _DEFAULT_CHECKPOINTER


def _initial_state(
    query: str,
    *,
    max_results: int,
    sources: list[str] | None,
    concept_types: list[str] | None,
    export_formats: list[str] | None,
    export_path: str | None,
    max_iterations: int,
    auto_approve_threshold: float,
) -> LookupWorkflowState:
    return {
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
        "review_concept_map": [],
        "review_llm_explanation": None,
        "aggregated_context": None,
        "refinement_notes": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "retry_count": 0,
        "auto_approve_threshold": auto_approve_threshold,
        "status": "pending",
        "errors": [],
        "normalized_query": "",
        "original_query": query,
        "expanded_search_terms": [],
        "is_german": False,
        "quality_score": None,
        "quality_details": None,
        "final_result": None,
        "export_paths": [],
        "steps": [],
    }


async def _finish(
    checkpointer: BaseCheckpointSaver,
    thread_id: str,
    result: dict,
) -> dict:
    """Build the runner response and report a pause as ``awaiting_approval``."""
    interrupts = result.get("__interrupt__") or []
    approval_request = interrupts[0].value if interrupts else None

    if interrupts:
        status = STATUS_AWAITING_APPROVAL
    else:
        status = result.get("status", "unknown")
        # Finished runs can't be resumed; don't let the shared in-memory saver
        # accumulate their checkpoints in long-lived processes.
        if checkpointer is _DEFAULT_CHECKPOINTER:
            await checkpointer.adelete_thread(thread_id)

    return {
        "thread_id": thread_id,
        "status": status,
        "approval_request": approval_request,
        "result": dict_to_lookup_result(result.get("final_result") or result.get("lookup_result")),
        "review_score": result.get("review_score"),
        "review_summary": result.get("review_summary"),
        "review_strengths": result.get("review_strengths", []),
        "review_weaknesses": result.get("review_weaknesses", []),
        "review_suggestions": result.get("review_suggestions", []),
        "concept_map": result.get("review_concept_map", []),
        "llm_explanation": result.get("review_llm_explanation", ""),
        "aggregated_context": result.get("aggregated_context", ""),
        "export_paths": result.get("export_paths", []),
        "errors": result.get("errors", []),
        "steps": result.get("steps", []),
        "iteration": result.get("iteration", 0),
    }


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
    checkpointer: BaseCheckpointSaver | None = None,
) -> dict:
    """Run the full lookup-review-approval-export workflow.

    Args:
        query: Search query.
        max_results: Maximum results per search.
        sources: Optional list of source names to query.
        concept_types: Optional concept type filter.
        export_formats: Formats to export (default: ["json"]).
        export_path: Directory for export files.
        max_iterations: Maximum lookup passes (initial search + refinements).
        auto_approve_threshold: Score above which auto-approval triggers.
        checkpointer: Checkpointer holding paused runs. Defaults to a
            process-wide in-memory saver; pass the same one to
            :func:`resume_workflow`.

    Returns:
        Dict with final state including results, review, and export paths.
        ``status`` is ``"awaiting_approval"`` when the run paused at the
        approval gate; ``approval_request`` then holds the interrupt payload
        and ``thread_id`` identifies the run for :func:`resume_workflow`.
    """
    saver = checkpointer if checkpointer is not None else _DEFAULT_CHECKPOINTER
    graph = build_workflow_graph(saver)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = _initial_state(
        query,
        max_results=max_results,
        sources=sources,
        concept_types=concept_types,
        export_formats=export_formats,
        export_path=export_path,
        max_iterations=max_iterations,
        auto_approve_threshold=auto_approve_threshold,
    )

    # Run the graph to completion (or interrupt)
    result = await graph.ainvoke(initial_state, config)
    return await _finish(saver, thread_id, result)


async def resume_workflow(
    thread_id: str,
    decision: dict,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> dict:
    """Resume a workflow that was paused at the approval interrupt.

    Args:
        thread_id: The thread ID from the initial run.
        decision: User decision dict, e.g.:
            {"approved": True}
            {"approved": False, "refine": True, "notes": "Try different sources"}
            {"approved": False, "refine": False}
        checkpointer: The checkpointer passed to :func:`run_workflow`, if any.

    Returns:
        Updated state dict (same shape as :func:`run_workflow`). A refinement
        can pause again, in which case ``status`` is ``"awaiting_approval"``.

    Raises:
        ValueError: If no run with this ``thread_id`` is paused for approval
            in the checkpointer.
    """
    saver = checkpointer if checkpointer is not None else _DEFAULT_CHECKPOINTER
    graph = build_workflow_graph(saver)
    config = {"configurable": {"thread_id": thread_id}}

    snapshot = await graph.aget_state(config)
    if not snapshot.next or not snapshot.interrupts:
        raise ValueError(
            f"No workflow paused for approval with thread_id {thread_id!r}. "
            "Resume with the same checkpointer (and process, for the default "
            "in-memory one) that run_workflow() used."
        )

    result = await graph.ainvoke(Command(resume=decision), config)
    return await _finish(saver, thread_id, result)
