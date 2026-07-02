"""LangGraph workflow graph construction."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    approval_node,
    enrichment_node,
    export_node,
    lookup_node,
    refine_node,
    review_node,
)
from .routing import route_after_approval, route_after_refine, route_after_review
from .state import LookupWorkflowState


def build_workflow_graph(
    checkpointer: InMemorySaver | None = None,
) -> Any:
    """Build and compile the LangGraph workflow.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                      If None, creates an InMemorySaver.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(LookupWorkflowState)

    # Add nodes
    builder.add_node("lookup", lookup_node)
    builder.add_node("enrichment", enrichment_node)
    builder.add_node("review", review_node)
    builder.add_node("approval", approval_node)
    builder.add_node("refine", refine_node)
    builder.add_node("export", export_node)

    # Edges
    builder.add_edge(START, "lookup")
    builder.add_edge("lookup", "enrichment")
    builder.add_edge("enrichment", "review")

    # Conditional: review -> approval or auto-export
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {
            "approval": "approval",
            "export": "export",
        },
    )

    # Conditional: approval -> export, refine, or end
    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "export": "export",
            "refine": "refine",
            END: END,
        },
    )

    # Conditional: refine -> back to lookup or export (max iterations)
    builder.add_conditional_edges(
        "refine",
        route_after_refine,
        {
            "lookup": "lookup",
            "export": "export",
        },
    )

    builder.add_edge("export", END)

    return builder.compile(checkpointer=checkpointer)
