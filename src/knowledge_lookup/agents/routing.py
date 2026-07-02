"""Conditional routing logic for the workflow graph."""

from __future__ import annotations

from langgraph.graph import END

from .state import LookupWorkflowState


def route_after_review(state: LookupWorkflowState) -> str:
    """Route based on review score and configuration."""
    score = state.get("review_score")
    threshold = state.get("auto_approve_threshold")
    iteration = state.get("iteration") or 0
    max_iter = state.get("max_iterations") or 3

    # Use explicit None check so 0.0 threshold works correctly
    if score is None:
        score = 0.0
    if threshold is None:
        threshold = 0.8

    # Auto-approve if score exceeds threshold
    if score >= threshold:
        return "export"

    # Auto-approve if max iterations reached
    if iteration >= max_iter:
        return "export"

    # Otherwise, go to human approval
    return "approval"


def route_after_approval(state: LookupWorkflowState) -> str:
    """Route after human approval decision."""
    status = state.get("status", "")
    if status == "exporting":
        return "export"
    elif status == "refining":
        return "refine"
    else:
        return END


def route_after_refine(state: LookupWorkflowState) -> str:
    """Route after refinement."""
    status = state.get("status", "")
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)

    if status == "failed" or iteration >= max_iter:
        return "export"
    return "lookup"
