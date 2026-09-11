"""LangGraph workflow graph construction.

Flow::

    START → preprocess → lookup → filter → quality_gate → detail_gather
    → enrichment → aggregate → review
    → {approval | prune}
    → {prune | refine | END}
    → {prune → export → END}

Key design:
- **preprocess** generates expanded search terms (direct, umlaut-expanded,
  normalized, German compound splits) — searched in parallel
- **filter** removes non-clinical concepts (questionnaires, measurement
  scales, geographic locations) and boosts clinical types
- **quality_gate** scores the filtered results
- **review** (LLM-powered) provides the final quality judgment
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    aggregate_node,
    approval_node,
    detail_gather_node,
    enrichment_node,
    export_node,
    filter_node,
    lookup_node,
    preprocess_node,
    prune_node,
    quality_gate_node,
    refine_node,
    review_node,
)
from .routing import route_after_approval, route_after_refine, route_after_review
from .state import LookupWorkflowState


def build_workflow_graph(checkpointer: InMemorySaver | None = None) -> Any:
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
    builder.add_node("preprocess", preprocess_node)
    builder.add_node("lookup", lookup_node)
    builder.add_node("filter", filter_node)
    builder.add_node("quality_gate", quality_gate_node)
    builder.add_node("detail_gather", detail_gather_node)
    builder.add_node("enrichment", enrichment_node)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("review", review_node)
    builder.add_node("approval", approval_node)
    builder.add_node("refine", refine_node)
    builder.add_node("prune", prune_node)
    builder.add_node("export", export_node)

    # Sequential: preprocess → lookup → filter → quality_gate → detail_gather
    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "lookup")
    builder.add_edge("lookup", "filter")
    builder.add_edge("filter", "quality_gate")
    builder.add_edge("quality_gate", "detail_gather")

    # Sequential: details → UMLS CUI enrichment → aggregate → review
    builder.add_edge("detail_gather", "enrichment")
    builder.add_edge("enrichment", "aggregate")
    builder.add_edge("aggregate", "review")

    # Conditional: review → approval (human) or prune → export (auto)
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {
            "approval": "approval",
            "prune": "prune",
        },
    )

    # Conditional: approval → prune→export, refine, or END
    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "prune": "prune",
            "refine": "refine",
            END: END,
        },
    )

    # Conditional: refine → back to lookup or prune→export
    builder.add_conditional_edges(
        "refine",
        route_after_refine,
        {
            "lookup": "lookup",
            "prune": "prune",
        },
    )

    # Prune → export → END
    builder.add_edge("prune", "export")
    builder.add_edge("export", END)

    return builder.compile(checkpointer=checkpointer)
