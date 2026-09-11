"""Conditional routing logic for the workflow graph.

Routes determine which node executes next based on current state.

Since lookup → filter → quality_gate is a simple linear flow with no
strategy loop-back, only review, approval, and refine have conditional routes.
"""

from __future__ import annotations

from .state import LookupWorkflowState


def route_after_review(state: LookupWorkflowState) -> str:
    """Route based on review score, threshold, and iteration count.

    Returns:
        "prune"  → auto-export (score ≥ threshold or max iterations reached)
        "approval" → pause for human review
    """
    score = state.get("review_score")
    threshold = state.get("auto_approve_threshold")
    iteration = state.get("iteration") or 0
    max_iter = state.get("max_iterations") or 3

    if score is None:
        score = 0.0
    if threshold is None:
        threshold = 0.8

    if score >= threshold or iteration >= max_iter:
        return "prune"

    return "approval"


def route_after_approval(state: LookupWorkflowState) -> str:
    """Route after human approval decision.

    Returns:
        "prune"  → approved, go to prune → export
        "refine" → user requested refinement
        END       → rejected, terminate
    """
    from langgraph.graph import END

    status = state.get("status", "")
    if status == "exporting":
        return "prune"
    elif status == "refining":
        return "refine"
    else:
        return END


def route_after_refine(state: LookupWorkflowState) -> str:
    """Route after refinement.

    Returns:
        "lookup" → re-run search with refined query
        "prune"  → max iterations reached, go to export
    """
    status = state.get("status", "")
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)

    if status == "failed" or iteration >= max_iter:
        return "prune"
    return "lookup"
