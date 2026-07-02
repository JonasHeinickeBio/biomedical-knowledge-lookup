"""Graph node: human-in-the-loop approval gate."""

from __future__ import annotations

from langgraph.types import interrupt

from ..state import LookupWorkflowState, dict_to_lookup_result, make_step


def approval_node(state: LookupWorkflowState) -> dict:
    """Pause for human approval via LangGraph interrupt.

    Presents the review summary and results for the user to approve,
    request refinement, or reject entirely.
    """
    review = {
        "score": state.get("review_score", 0),
        "summary": state.get("review_summary", ""),
        "strengths": state.get("review_strengths", []),
        "weaknesses": state.get("review_weaknesses", []),
        "suggestions": state.get("review_suggestions", []),
    }

    result = dict_to_lookup_result(state.get("lookup_result"))
    concept_preview = []
    if result and result.concepts:
        for c in result.concepts[:10]:
            concept_preview.append(
                {
                    "id": c.primary_id,
                    "label": c.primary_label,
                    "type": str(c.concept_type) if c.concept_type else None,
                    "confidence": c.confidence_score,
                    "sources": [str(s) for s in (c.sources or [])],
                }
            )

    decision = interrupt(
        {
            "action": "approve_lookup_results",
            "query": state["query"],
            "iteration": state["iteration"],
            "review": review,
            "concept_preview": concept_preview,
            "total_concepts": len((result.concepts or []) if result else []),
            "instructions": (
                "Respond with:\n"
                "  {'approved': true}  — to accept and export results\n"
                "  {'approved': false, 'refine': true, 'notes': '...'}  — to request refinement\n"
                "  {'approved': false, 'refine': false}  — to reject and stop"
            ),
        }
    )

    # Process the decision
    approved = (
        decision.get("approved", False) if isinstance(decision, dict) else bool(decision)
    )
    refine = (
        decision.get("refine", False) if isinstance(decision, dict) else False
    )
    notes = decision.get("notes", "") if isinstance(decision, dict) else ""

    if approved:
        return {
            "status": "exporting",
            "final_result": state.get("lookup_result"),
            "steps": [make_step("ApprovalGate", "approved", "User approved results")],
        }
    elif refine:
        return {
            "status": "refining",
            "refinement_notes": [notes] if notes else state.get("refinement_notes", []),
            "steps": [
                make_step(
                    "ApprovalGate",
                    "refine_requested",
                    notes or "User requested refinement",
                )
            ],
        }
    else:
        return {
            "status": "completed",
            "final_result": None,
            "steps": [make_step("ApprovalGate", "rejected", "User rejected results")],
        }
