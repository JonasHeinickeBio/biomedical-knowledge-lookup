"""Workflow state schema and serialization helpers."""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any, TypedDict

from ..models import LookupResult


class LookupWorkflowState(TypedDict):
    """State that flows through the LangGraph workflow."""

    # Input
    query: str
    max_results: int
    source_filter: list[str] | None
    concept_type_filter: list[str] | None
    export_formats: list[str]
    export_path: str | None

    # Intermediate results
    lookup_result: dict | None  # LookupResult serialized (Pydantic models aren't hashable)
    review_score: float | None
    review_summary: str | None
    review_strengths: list[str]
    review_weaknesses: list[str]
    review_suggestions: list[str]
    refinement_notes: list[str]

    # Control flow
    iteration: int
    max_iterations: int
    auto_approve_threshold: float
    status: str  # pending | searching | reviewing | awaiting_approval | refining | exporting | completed | failed
    errors: list[str]

    # Output
    final_result: dict | None
    export_paths: list[str]
    steps: Annotated[list[dict], operator.add]


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
