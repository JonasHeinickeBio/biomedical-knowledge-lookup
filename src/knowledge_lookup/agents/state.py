"""Workflow state schema and serialization helpers.

Follows best practice of separating control state (infrastructure fields
for routing, error handling, retry) from business state (data produced
by workflow nodes). Accumulator fields use `Annotated[list, operator.add]`
to avoid overwrites across parallel branches and re-invocations.
"""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any, TypedDict

from ..models import LookupResult


class LookupWorkflowState(TypedDict):
    """State that flows through the LangGraph workflow.

    Fields are grouped by purpose:
    - Input: User-provided configuration (immutable during run)
    - Control: Infrastructure for graph routing, retry, error handling
    - Business: Data produced by workflow nodes
    """

    # ── Input (user-provided, immutable during run) ──────────────────────
    query: str
    max_results: int
    source_filter: list[str] | None
    concept_type_filter: list[str] | None
    export_formats: list[str]
    export_path: str | None

    # ── Control (infrastructure for routing, retry, errors) ──────────────
    iteration: int  # Current refinement round
    max_iterations: int  # Maximum refinement rounds allowed
    retry_count: int  # Consecutive retries for failed nodes
    auto_approve_threshold: float  # Score ≥ this → auto-approve
    status: str  # pending | searching | reviewing | awaiting_approval | refining | exporting | retrying | completed | failed
    errors: list[str]  # Non-fatal warnings / errors

    # ── Search Strategy (expanded parallel search terms) ─────────────────
    normalized_query: str  # Cleaned/normalized version of the query
    original_query: str  # Original query as provided
    expanded_search_terms: list[str]  # Flat list of ALL search variants (searched in parallel)
    is_german: bool  # Whether the query appears to be German
    quality_score: float | None  # Quality gate score (0-1)
    quality_details: dict | None  # Quality breakdown

    # ── Business (produced by workflow nodes) ────────────────────────────
    # Lookup & enrichment
    lookup_result: dict | None  # Serialized LookupResult (Pydantic)
    aggregated_context: str | None  # Text summary built by AggregateAgent

    # Review
    review_score: float | None
    review_summary: str | None
    review_strengths: list[str]
    review_weaknesses: list[str]
    review_suggestions: list[str]
    review_concept_map: list[dict]  # [{term, umls_cui, ontology_ids, primary_type}]
    review_llm_explanation: str | None  # Overall explanation from LLM

    # Refinement
    refinement_notes: list[str]  # User notes from approval interrupt

    # Final output
    final_result: dict | None
    export_paths: list[str]
    steps: Annotated[list[dict], operator.add]  # Accumulated step history


def lookup_result_to_dict(result: LookupResult) -> dict:
    """Serialize a LookupResult to a plain dict for LangGraph state."""
    return result.model_dump(mode="json")


def dict_to_lookup_result(d: dict | None) -> LookupResult | None:
    """Deserialize a dict back to a LookupResult."""
    if d is None:
        return None
    return LookupResult.model_validate(d)


def make_step(agent: str, action: str, detail: str = "", **extra: Any) -> dict:
    """Create a workflow step record."""
    return {
        "agent": agent,
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "detail": detail,
        **extra,
    }
