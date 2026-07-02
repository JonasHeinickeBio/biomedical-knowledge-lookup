"""Graph node: quality review (LLM-powered with rule-based fallback)."""

from __future__ import annotations

import json
import logging

from ...models import LookupResult
from ..config import call_llm
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step

logger = logging.getLogger(__name__)


def _rule_based_review(result: LookupResult, max_results: int) -> dict:
    """Rule-based quality review (fallback when no LLM available)."""
    concepts = result.concepts or []
    n_concepts = len(concepts)
    n_queried = len(result.sources_queried or [])
    n_succeeded = len(result.sources_succeeded or [])
    n_failed = len(result.sources_failed or [])

    # Scoring dimensions
    yield_score = min(n_concepts / max(max_results, 1), 1.0)
    source_score = (n_succeeded / n_queried) if n_queried > 0 else 0.0
    avg_conf = (
        sum(c.confidence_score or 0.0 for c in concepts) / n_concepts
        if concepts
        else 0.0
    )
    contributing_sources = set()
    for c in concepts:
        for s in c.sources or []:
            contributing_sources.add(str(s))
    diversity_score = min(
        len(contributing_sources) / max(n_succeeded, 1), 1.0
    )

    score = (
        0.30 * yield_score
        + 0.25 * source_score
        + 0.25 * avg_conf
        + 0.20 * diversity_score
    )

    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []

    if n_concepts > 0:
        strengths.append(f"Found {n_concepts} matching concepts")
    else:
        weaknesses.append("No concepts returned")

    if source_score >= 0.8:
        strengths.append(
            f"All {n_succeeded}/{n_queried} sources responded successfully"
        )
    elif source_score > 0:
        weaknesses.append(f"Only {n_succeeded}/{n_queried} sources responded")
        suggestions.append("Check failed source health and consider retrying")
    else:
        weaknesses.append("No sources responded successfully")

    if avg_conf >= 0.7:
        strengths.append(f"High average confidence: {avg_conf:.2f}")
    elif avg_conf < 0.3:
        weaknesses.append(f"Low average confidence: {avg_conf:.2f}")
        suggestions.append(
            "Try a more specific query or add concept type filters"
        )

    if diversity_score >= 0.7:
        strengths.append(
            f"Good source diversity ({len(contributing_sources)} sources contributed)"
        )
    elif n_concepts > 0 and diversity_score < 0.5:
        suggestions.append(
            "Results come from few sources; try enabling more sources"
        )

    if n_failed > 0:
        suggestions.append(f"{n_failed} source(s) failed; retry may recover results")

    type_counts: dict[str, int] = {}
    for c in concepts:
        t = str(c.concept_type) if c.concept_type else "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts:
        top_type = max(type_counts, key=type_counts.get)  # type: ignore
        if type_counts[top_type] > n_concepts * 0.8:
            suggestions.append(
                f"Results heavily skewed toward '{top_type}'; "
                "consider broadening concept type filter"
            )

    summary_parts = [
        f"Score: {score:.2f}/1.00",
        f"{n_concepts} concepts from {n_succeeded}/{n_queried} sources",
        f"Avg confidence: {avg_conf:.2f}",
        f"Diversity: {len(contributing_sources)} contributing sources",
    ]
    if weaknesses:
        summary_parts.append(f"Issues: {'; '.join(weaknesses)}")

    return {
        "review_score": round(score, 3),
        "review_summary": " | ".join(summary_parts),
        "review_strengths": strengths,
        "review_weaknesses": weaknesses,
        "review_suggestions": suggestions,
    }


async def _llm_review(
    result: LookupResult, query: str, max_results: int
) -> dict | None:
    """LLM-powered quality review using Blablador/OpenAI-compatible API.

    Sends the lookup results to the LLM for nuanced quality assessment
    and returns structured feedback. Falls back to None if LLM unavailable.
    """
    concepts = result.concepts or []
    n_concepts = len(concepts)
    n_queried = len(result.sources_queried or [])
    n_succeeded = len(result.sources_succeeded or [])

    # Build a concise concept summary for the LLM
    concept_lines = []
    for i, c in enumerate(concepts[:20]):  # Limit to top 20 for token efficiency
        concept_lines.append(
            f"  {i+1}. [{c.primary_id}] {c.primary_label or 'N/A'} "
            f"(type={c.concept_type}, confidence={c.confidence_score or 0:.2f}, "
            f"sources={[str(s) for s in (c.sources or [])]})"
        )
    concepts_text = (
        "\n".join(concept_lines) if concept_lines else "  (no concepts found)"
    )

    # Compute basic stats for context
    contributing = set()
    for c in concepts:
        for s in c.sources or []:
            contributing.add(str(s))

    prompt = f"""You are a biomedical knowledge retrieval quality reviewer.

TASK: Evaluate the quality of search results for a biomedical knowledge lookup.

QUERY: "{query}"

SEARCH STATISTICS:
- Concepts found: {n_concepts} (max requested: {max_results})
- Sources queried: {n_queried}
- Sources succeeded: {n_succeeded}
- Sources failed: {len(result.sources_failed or [])}
- Contributing sources: {list(contributing)}

TOP CONCEPTS:
{concepts_text}

REVIEW DIMENSIONS (score each 0.0-1.0):
1. **Yield** (0.30 weight): Did we get enough relevant results?
2. **Source Reliability** (0.25 weight): What fraction of sources succeeded?
3. **Concept Quality** (0.25 weight): Are the results high-confidence and relevant?
4. **Diversity** (0.20 weight): Do results come from multiple independent sources?

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no extra text):
{{
  "score": <weighted_composite_score_0_to_1>,
  "yield_score": <0_to_1>,
  "source_score": <0_to_1>,
  "quality_score": <0_to_1>,
  "diversity_score": <0_to_1>,
  "strengths": ["<strength1>", "<strength2>", ...],
  "weaknesses": ["<weakness1>", "<weakness2>", ...],
  "suggestions": ["<suggestion1>", "<suggestion2>", ...],
  "summary": "<one_line_summary>"
}}"""

    llm_output = await call_llm(prompt, max_tokens=1000, temperature=0.2)
    if llm_output is None:
        return None

    # Parse LLM response
    try:
        # Strip markdown code fences if present
        cleaned = llm_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        review = json.loads(cleaned)

        # Validate and normalize
        score = float(review.get("score", 0.5))
        score = max(0.0, min(1.0, score))

        return {
            "review_score": round(score, 3),
            "review_summary": review.get(
                "summary", f"LLM review: score {score:.2f}"
            ),
            "review_strengths": review.get("strengths", []),
            "review_weaknesses": review.get("weaknesses", []),
            "review_suggestions": review.get("suggestions", []),
        }

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse LLM review response: %s", exc)
        logger.debug("Raw LLM output: %s", llm_output)
        return None


async def review_node(state: LookupWorkflowState) -> dict:
    """Evaluate lookup results quality.

    Uses LLM-powered review (Blablador/OpenAI-compatible API) when available,
    falls back to rule-based heuristics otherwise.
    """
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None:
        return {
            "review_score": 0.0,
            "review_summary": "No lookup results to review.",
            "review_strengths": [],
            "review_weaknesses": ["No results available"],
            "review_suggestions": ["Re-run the lookup with different parameters"],
            "status": "reviewing",
            "steps": [make_step("ReviewAgent", "no_results", "No results to review")],
        }

    # Try LLM-powered review first
    llm_review = await _llm_review(result, state["query"], state["max_results"])
    if llm_review is not None:
        return {
            **llm_review,
            "status": "reviewing",
            "steps": [
                make_step(
                    "ReviewAgent(LLM)",
                    "review",
                    f"LLM score {llm_review['review_score']:.2f}, "
                    f"{len(llm_review['review_strengths'])} strengths, "
                    f"{len(llm_review['review_weaknesses'])} weaknesses",
                )
            ],
        }

    # Fallback to rule-based review
    review = _rule_based_review(result, state["max_results"])
    return {
        **review,
        "status": "reviewing",
        "steps": [
            make_step(
                "ReviewAgent(Rule)",
                "review",
                f"Rule-based score {review['review_score']:.2f}, "
                f"{len(review['review_strengths'])} strengths, "
                f"{len(review['review_weaknesses'])} weaknesses",
            )
        ],
    }
