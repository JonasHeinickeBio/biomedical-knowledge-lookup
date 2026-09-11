"""Graph node: quality gate after clinical filtering.

Evaluates the filtered, re-ranked results and scores their quality.
Since the filter node already removed non-clinical concepts and the
lookup searched all expanded terms in parallel, this is a simple
scoring gate that always routes forward.
"""

from __future__ import annotations

import logging
from typing import Any

from ...models import KnowledgeSource, LookupResult
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step

logger = logging.getLogger(__name__)


def _get_umls_cui(c: Any) -> str | None:
    """Extract UMLS CUI from a concept's identifiers."""
    if not hasattr(c, "identifiers") or not c.identifiers:
        return None
    for ident in c.identifiers:
        src = ident.source
        if isinstance(src, KnowledgeSource) and src == KnowledgeSource.UMLS:
            return ident.identifier
        if isinstance(src, str) and src.upper() == "UMLS":
            return ident.identifier
    return None


def _compute_quality(result: LookupResult) -> tuple[float, dict[str, Any]]:
    """Score filtered lookup results quality on 0-1 scale.

    After clinical filtering, we expect cleaner results, so the threshold
    can be higher. Focus on CUI coverage and source diversity.
    """
    concepts = result.concepts or []
    n = len(concepts)

    if n == 0:
        return 0.0, {"reason": "no_concepts", "concept_count": 0}

    # CUI coverage (0.40 weight)
    n_with_cui = sum(1 for c in concepts if _get_umls_cui(c))
    cui_ratio = n_with_cui / n if n > 0 else 0.0

    # Yield (0.20 weight)
    yield_score = min(n / 5.0, 1.0)

    # Source diversity (0.25 weight)
    sources: set[str] = set()
    for c in concepts:
        for s in c.sources or []:
            sources.add(str(s).upper())
    diversity = min(len(sources) / 2.0, 1.0)

    # Average confidence (0.15 weight)
    avg_conf = sum(c.confidence_score or 0.0 for c in concepts) / n

    score = 0.40 * cui_ratio + 0.20 * yield_score + 0.25 * diversity + 0.15 * avg_conf

    details: dict[str, Any] = {
        "concept_count": n,
        "n_with_cui": n_with_cui,
        "cui_coverage": round(cui_ratio, 3),
        "source_diversity": round(diversity, 3),
        "avg_confidence": round(avg_conf, 3),
    }

    return round(score, 3), details


async def quality_gate_node(state: LookupWorkflowState) -> dict:
    """Score filtered results quality and store for LLM review context."""
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None or not result.concepts:
        return {
            "quality_score": 0.0,
            "quality_details": {"reason": "no_concepts", "concept_count": 0},
            "status": "searching",
            "steps": [make_step("QualityGateAgent", "empty", "No concepts after filtering")],
        }

    score, details = _compute_quality(result)
    step_detail = (
        f"Score {score:.2f}: {details['concept_count']} concepts, "
        f"CUI={details['cui_coverage']:.0%}, "
        f"diversity={details['source_diversity']:.0%}"
    )

    return {
        "quality_score": score,
        "quality_details": details,
        "status": "searching",
        "steps": [make_step("QualityGateAgent", "score", step_detail)],
    }
