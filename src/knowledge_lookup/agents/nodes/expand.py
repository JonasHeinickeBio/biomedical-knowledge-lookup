"""Graph node: iterative synonym + abbreviation/long-form term expansion.

Runs between ``preprocess`` and ``lookup``. ``preprocess`` already produces
deterministic query variants (umlaut expansion, normalization, German
compound splitting); this node adds terms *discovered from actual search
results* — synonyms already present on returned concepts, plus
abbreviation/long-form pairs from UMLS (when available) — feeding them into
the same ``expanded_search_terms`` list ``lookup_node`` searches.

The discovery itself requires real search calls (you can't harvest a
concept's synonyms without finding the concept first), so this node runs
its own bounded expansion pass via
:func:`knowledge_lookup.core.term_expansion.expand_and_search` against the
original query — not against every preprocess-generated variant, which
would multiply the number of expansion passes for little benefit.
``lookup_node`` still performs the "official" search afterward across the
combined term list; this node's own search results are used only to
discover terms; a full expansion trail is durably persisted regardless of
what the rest of the workflow does with them (see
:class:`~knowledge_lookup.core.expansion_store.ExpansionStore`).

This runs as a single summarized workflow step (one ``steps`` entry), not
one step per expansion round — see the core module's docstring for the
per-round vs summarized-step tradeoff.
"""

from __future__ import annotations

from ...core.central_lookup import CentralKnowledgeLookup
from ...core.term_expansion import expand_and_search
from ...models import LookupConfig
from ..state import LookupWorkflowState, make_step

# Kept intentionally small: this is a bounded quality-improvement pass, not
# the workflow's main search — lookup_node still searches every term found
# here (plus preprocess's own variants) for the "official" results.
_MAX_ROUNDS = 2
_MAX_TERMS_PER_ROUND = 8


async def expand_node(state: LookupWorkflowState) -> dict:
    """Discover synonym/abbreviation variants of the query and add them to
    ``expanded_search_terms`` for ``lookup_node`` to search."""
    query = state["query"]
    existing_terms = state.get("expanded_search_terms") or [query]

    config = LookupConfig(
        max_results_per_source=state["max_results"],
        parallel_queries=True,
        enable_deduplication=True,
    )
    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        _, trace = await expand_and_search(
            lookup,
            query,
            max_rounds=_MAX_ROUNDS,
            max_terms_per_round=_MAX_TERMS_PER_ROUND,
        )
    except Exception as e:
        return {
            "steps": [make_step("ExpandAgent", "error", f"Term expansion failed: {e}")],
        }
    finally:
        await lookup.close()

    query_lower = query.strip().lower()
    seen = {t.strip().lower() for t in existing_terms}
    merged_terms = list(existing_terms)
    added: list[str] = []
    for term in trace.all_terms_tried:
        key = term.strip().lower()
        if key and key != query_lower and key not in seen:
            seen.add(key)
            merged_terms.append(term)
            added.append(term)

    detail = f"{trace.rounds_run} round(s) (stop: {trace.stop_reason}), {len(added)} new term(s)"
    if added:
        shown = ", ".join(added[:8])
        detail += f": {shown}" + (" ..." if len(added) > 8 else "")

    return {
        "expanded_search_terms": merged_terms,
        "steps": [make_step("ExpandAgent", "expand", detail)],
    }
