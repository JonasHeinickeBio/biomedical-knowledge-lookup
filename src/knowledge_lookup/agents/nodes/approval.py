"""Graph node: human-in-the-loop approval gate.

Best practices applied:
- Risk-tiered: only pauses for human review when score is below auto-approve
  threshold. High-confidence results bypass human review to avoid fatigue.
- Rich context: provides reasoning chain, source breakdown, concept preview,
  and confidence signals — not just a score.
- Explicit decision logging: decision, timestamp, and notes are recorded
  for audit trail.
"""

from __future__ import annotations

from langgraph.types import interrupt

from ..state import LookupWorkflowState, dict_to_lookup_result, make_step


def approval_node(state: LookupWorkflowState) -> dict:
    """Pause for human approval via LangGraph interrupt.

    Presents rich context for decision-making:
    - Review score and dimension breakdown
    - LLM reasoning chain
    - Concept preview with UMLS CUI
    - Source success/failure breakdown
    - Strengths, weaknesses, suggestions
    """
    # ── Build rich context for human reviewer ──────────────────────────

    review = {
        "score": state.get("review_score", 0),
        "summary": state.get("review_summary", ""),
        "strengths": state.get("review_strengths", []),
        "weaknesses": state.get("review_weaknesses", []),
        "suggestions": state.get("review_suggestions", []),
        "explanation": state.get("review_llm_explanation", ""),
    }

    result = dict_to_lookup_result(state.get("lookup_result"))
    concept_preview = []
    if result and result.concepts:
        for c in result.concepts[:15]:
            umls_cui = None
            for ident in c.identifiers or []:
                src = (
                    str(ident.source).upper()
                    if hasattr(ident.source, "upper")
                    else str(ident.source).upper()
                )
                if src == "UMLS":
                    umls_cui = ident.identifier
                    break
            concept_preview.append(
                {
                    "label": c.primary_label,
                    "id": c.primary_id,
                    "type": str(c.concept_type) if c.concept_type else None,
                    "umls_cui": umls_cui,
                    "confidence": c.confidence_score,
                    "sources": [str(s) for s in (c.sources or [])],
                }
            )

    # Source health breakdown
    sq = result.sources_queried if result else None
    ss = result.sources_succeeded if result else None
    sf = result.sources_failed if result else None
    source_breakdown = {
        "queried": len(sq) if sq else 0,
        "succeeded": len(ss) if ss else 0,
        "failed": len(sf) if sf else 0,
        "sources_failed": [str(s) for s in (sf or [])],
    }

    # Build the interrupt payload with decision context
    decision = interrupt(
        {
            "action": "approve_lookup_results",
            "query": state["query"],
            "iteration": state["iteration"],
            "max_iterations": state["max_iterations"],
            "review": review,
            "concept_preview": concept_preview,
            "source_breakdown": source_breakdown,
            "total_concepts": len((result.concepts or []) if result else []),
            "instructions": (
                "Respond with:\n"
                "  {'approved': true}  → accept and export\n"
                "  {'approved': false, 'refine': true, 'notes': '...'}  → refine with notes\n"
                "  {'approved': false, 'refine': false}  → reject and stop"
            ),
        }
    )

    # ── Process the decision ──────────────────────────────────────────

    approved = decision.get("approved", False) if isinstance(decision, dict) else bool(decision)
    refine = decision.get("refine", False) if isinstance(decision, dict) else False
    notes = decision.get("notes", "") if isinstance(decision, dict) else ""

    if approved:
        return {
            "status": "exporting",
            "final_result": state.get("lookup_result"),
            "retry_count": 0,  # Reset retry counter on approval
            "steps": [make_step("ApprovalGate", "approved", "User approved results")],
        }
    elif refine:
        return {
            "status": "refining",
            "refinement_notes": [notes] if notes else state.get("refinement_notes", []),
            "retry_count": 0,  # Reset retry counter on new refinement
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
