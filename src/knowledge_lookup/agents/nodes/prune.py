"""Graph node: state pruning to reduce checkpoint serialization cost.

Best practice: keep state lean. Everything in state gets serialized to the
checkpoint store on every node transition. Large intermediate data like
aggregated_context and raw lookup_result with full concept details should
be pruned once consumed downstream.

This node runs after review+approval and before export:
- Preserves only what export needs: final_result, concept_map, explanation
- Clears aggregated_context (already consumed by LLM review)
- Clears raw lookup_result concept details (redundant with concept_map)
"""

from __future__ import annotations

from ..state import LookupWorkflowState, make_step


async def prune_node(state: LookupWorkflowState) -> dict:
    """Prune intermediate state to reduce checkpoint serialization cost.

    Strips large data that's no longer needed:
    - aggregated_context (text report, already consumed by review)
    - lookup_result detail (replaced by final_result + concept_map)
    """
    # Ensure final_result is set before dropping the raw lookup_result
    final = state.get("final_result") or state.get("lookup_result")

    return {
        "final_result": final,
        "lookup_result": None,  # superseded by final_result; redundant to keep both
        "aggregated_context": None,  # Already consumed by review node
        "steps": [
            make_step("PruneAgent", "prune", "Cleared intermediate data for compact checkpoint")
        ],
    }
