"""Graph node: query refinement based on feedback."""

from __future__ import annotations

from ..state import LookupWorkflowState, make_step


async def refine_node(state: LookupWorkflowState) -> dict:
    """Apply refinement based on user feedback and review suggestions.

    Modifies the query or source configuration based on:
    - User-provided notes from the approval gate
    - Review agent suggestions
    """
    notes = state.get("refinement_notes", [])
    suggestions = state.get("review_suggestions", [])
    query = state["query"]

    # Build refined query: append user notes and review suggestions
    refined_query = query
    context_parts = []
    if notes:
        note_text = " ".join(n for n in notes if n)
        if note_text:
            context_parts.append(note_text)
    if suggestions:
        suggestion_text = " ".join(s for s in suggestions[:3] if s)
        if suggestion_text:
            context_parts.append(suggestion_text)
    if context_parts:
        refined_query = f"{query} {' '.join(context_parts)}"

    # Track refinement iteration
    iteration = state["iteration"]
    max_iter = state.get("max_iterations", 3)

    if iteration >= max_iter:
        return {
            "status": "completed",
            "final_result": state.get("lookup_result"),
            "errors": [f"Max refinement iterations ({max_iter}) reached"],
            "steps": [
                make_step(
                    "RefineAgent",
                    "max_iterations",
                    f"Reached max iterations ({max_iter}), using current results",
                )
            ],
        }

    return {
        "query": refined_query,
        "status": "searching",
        "steps": [
            make_step(
                "RefineAgent",
                "refine",
                f"Refined query (iter {iteration + 1}): '{refined_query}'",
            )
        ],
    }
