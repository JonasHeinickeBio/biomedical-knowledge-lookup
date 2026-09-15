"""Graph node: query refinement based on feedback."""

from __future__ import annotations

from ..state import LookupWorkflowState, make_step
from .preprocess import _build_expanded_terms, _normalize_query


def _refine_query(query: str, notes: list[str]) -> str:
    """Append the user's *notes* to *query*, skipping notes it already contains.

    Notes are kept from one refinement to the next when the user gives no new
    ones, so a note already in the query is not appended a second time.
    """
    refined = query.strip()
    for note in notes:
        note = (note or "").strip()
        if note and note.lower() not in refined.lower():
            refined = f"{refined} {note}"
    return refined


def _search_terms_for(query: str) -> list[str]:
    """The search variants ``preprocess`` would build for *query*."""
    raw_terms = [t.strip() for t in query.split(",") if t.strip()]
    return _build_expanded_terms(raw_terms or [query])


async def refine_node(state: LookupWorkflowState) -> dict:
    """Apply the user's refinement notes before searching again.

    The notes from the approval gate are appended to the query, and
    ``expanded_search_terms`` is rebuilt from the refined query, because
    ``lookup`` searches those terms rather than ``query``. Without new text the
    query and search terms are left as they are, so the next pass repeats the
    same search (which can recover sources that failed).

    Review suggestions ("Check failed source health ...") are advice for the
    person reviewing, not search text: they are shown in the step detail and
    never added to the query.
    """
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

    query = state["query"]
    notes = [n for n in (state.get("refinement_notes") or []) if n and n.strip()]
    refined_query = _refine_query(query, notes)

    update: dict = {"query": refined_query, "status": "searching"}
    if refined_query != query.strip():
        search_terms = _search_terms_for(refined_query)
        update["expanded_search_terms"] = search_terms
        update["normalized_query"] = _normalize_query(refined_query)
        detail = (
            f"Refined query (iter {iteration + 1}): '{refined_query}' "
            f"-> {len(search_terms)} search term(s)"
        )
    else:
        n_terms = len(state.get("expanded_search_terms") or []) or 1
        detail = (
            f"No new refinement notes (iter {iteration + 1}); "
            f"searching the same {n_terms} term(s) again"
        )

    suggestions = [s for s in (state.get("review_suggestions") or []) if s]
    if suggestions:
        detail += " | review suggestions (not searched): " + "; ".join(suggestions[:3])

    update["steps"] = [make_step("RefineAgent", "refine", detail)]
    return update
