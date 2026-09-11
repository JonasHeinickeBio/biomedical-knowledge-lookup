"""Graph node: quality review (LLM-powered with rule-based fallback).

Uses the aggregated context from AggregateAgent (which contains full concept
details, definitions, hierarchy, mappings) for a comprehensive LLM review.

The LLM produces:
1. A per-concept mapping: term → UMLS CUI → ontology IDs → type
2. An overall explanation of results quality
3. Scores, strengths, weaknesses, suggestions

Best practices applied:
- Rubric format with explicit criteria weights
- Reasoning-before-score: LLM must analyze before committing to a number
- Short, focused prompt (not multi-page)
- Calibrated scoring instructions (use full 0-1 range)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from ...models import LookupResult
from ..config import call_llm
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step

logger = logging.getLogger(__name__)


def _rule_based_concept_map(result: LookupResult) -> tuple[list[dict], str]:
    """Build a concept map from result data (non-LLM fallback)."""
    concept_map: list[dict] = []
    for c in result.concepts or []:
        umls_cui = None
        ontology_ids: list[str] = []
        for ident in c.identifiers or []:
            src = (
                str(ident.source).upper()
                if hasattr(ident.source, "upper")
                else (
                    str(getattr(ident.source, "value", "")).upper()
                    if hasattr(ident.source, "value")
                    else str(ident.source).upper()
                )
            )
            id_str = f"{src}:{ident.identifier}"
            if src == "UMLS":
                umls_cui = ident.identifier
            else:
                ontology_ids.append(id_str)
        if c.primary_id:
            pid = c.primary_id
            if not any(pid.endswith(id.split(":")[-1]) for id in ontology_ids):
                ontology_ids.append(pid)

        concept_map.append(
            {
                "term": c.primary_label or "",
                "umls_cui": umls_cui or "",
                "ontology_ids": sorted(set(ontology_ids)),
                "primary_type": str(c.concept_type) if c.concept_type else "",
            }
        )

    n = len(concept_map)
    explanation = (
        f"Rule-based review: Found {n} concept(s). "
        f"{sum(1 for m in concept_map if m['umls_cui'])} have UMLS CUI mappings. "
        f"Average ontology IDs per concept: "
        f"{sum(len(m['ontology_ids']) for m in concept_map) / max(n, 1):.1f}."
    )
    return concept_map, explanation


def _rule_based_review(result: LookupResult, max_results: int) -> dict:
    """Rule-based quality review (fallback when no LLM available)."""
    concepts = result.concepts or []
    n_concepts = len(concepts)
    n_queried = len(result.sources_queried or [])
    n_succeeded = len(result.sources_succeeded or [])
    n_failed = len(result.sources_failed or [])

    yield_score = min(n_concepts / max(max_results, 1), 1.0)
    source_score = (n_succeeded / n_queried) if n_queried > 0 else 0.0
    avg_conf = sum(c.confidence_score or 0.0 for c in concepts) / n_concepts if concepts else 0.0
    contributing_sources = set()
    for c in concepts:
        for s in c.sources or []:
            contributing_sources.add(str(s))
    diversity_score = min(len(contributing_sources) / max(n_succeeded, 1), 1.0)

    score = 0.30 * yield_score + 0.25 * source_score + 0.25 * avg_conf + 0.20 * diversity_score

    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []

    if n_concepts > 0:
        strengths.append(f"Found {n_concepts} matching concepts")
    else:
        weaknesses.append("No concepts returned")

    if source_score >= 0.8:
        strengths.append(f"All {n_succeeded}/{n_queried} sources responded successfully")
    elif source_score > 0:
        weaknesses.append(f"Only {n_succeeded}/{n_queried} sources responded")
        suggestions.append("Check failed source health and consider retrying")
    else:
        weaknesses.append("No sources responded successfully")

    if avg_conf >= 0.7:
        strengths.append(f"High average confidence: {avg_conf:.2f}")
    elif avg_conf < 0.3:
        weaknesses.append(f"Low average confidence: {avg_conf:.2f}")
        suggestions.append("Try a more specific query or add concept type filters")

    if diversity_score >= 0.7:
        strengths.append(
            f"Good source diversity ({len(contributing_sources)} sources contributed)"
        )
    elif n_concepts > 0 and diversity_score < 0.5:
        suggestions.append("Results come from few sources; try enabling more sources")

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

    concept_map, explanation = _rule_based_concept_map(result)

    return {
        "review_score": round(score, 3),
        "review_summary": " | ".join(summary_parts),
        "review_strengths": strengths,
        "review_weaknesses": weaknesses,
        "review_suggestions": suggestions,
        "review_concept_map": concept_map,
        "review_llm_explanation": explanation,
    }


# ── LLM Judge Prompt (rubric-based, reasoning-before-score) ─────────────

_REVIEW_PROMPT_TEMPLATE = """You are a biomedical ontology retrieval evaluator. Evaluate how well the search results cover the query.

QUERY: "{query}"
MAX RESULTS: {max_results}

Below is the aggregated search report.

{context}

Rate 6 dimensions (0.0-1.0, use full scale):
1. Yield (wt 0.20): Enough concepts found vs requested? Gaps?
2. Source Reliability (wt 0.15): Sources succeeded? Authoritative?
3. Concept Quality (wt 0.20): Clinically relevant? Good definitions/types?
4. Source Diversity (wt 0.15): Multiple sources or just one?
5. Metadata Richness (wt 0.15): UMLS CUIs, cross-refs, hierarchy present?
6. Specificity (wt 0.15): Specific to query or too generic?

Output JSON ONLY:
{{
  "reasoning": "2-3 sentence overall analysis",
  "dimension_scores": {{"yield": 0.0, "source_reliability": 0.0, "concept_quality": 0.0, "source_diversity": 0.0, "metadata_richness": 0.0, "specificity": 0.0}},
  "composite_score": <weighted>,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "suggestions": ["..."],
  "refined_query": "improved query text",
  "summary": "one line",
  "overall_explanation": "detailed explanation of quality, coverage, and gaps"
}}"""


# ── JSON Extraction ─────────────────────────────────────────────────────

_MAX_OUTPUT_LEN = 1500


def _extract_json(text: str) -> dict | None:
    """Try multiple strategies to extract valid JSON from LLM response.

    Strategies (in order):
    1. Direct json.loads()
    2. Content between ```json code fences
    3. Brace-depth matching for first valid JSON object
    4. First { to last } span
    """
    text = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: content between ```json and ``` markers
    json_fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if json_fence:
        candidate = json_fence.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Strategy 3: find ALL complete { ... } blocks (not just the first one)
    # Accounts for preamble text before the JSON object
    search_start = 0
    while True:
        brace_start = text.find("{", search_start)
        if brace_start < 0:
            break
        depth = 0
        matched = False
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    matched = True
                    candidate = text[brace_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # Invalid JSON — try next { position
                        search_start = brace_start + 1
                        break
        if not matched:
            # No matching } found for this { — avoid infinite loop
            search_start = brace_start + 1

    # Strategy 4: first { to last } span
    try:
        first_brace = text.index("{")
        last_brace = text.rindex("}")
        candidate = text[first_brace : last_brace + 1]
        return json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        pass

    return None


# ── LLM Review Call ─────────────────────────────────────────────────────


async def _llm_review(context: str, query: str, max_results: int) -> dict | None:
    """LLM-powered quality review using the aggregated context.

    Uses a rubric-based prompt with reasoning-before-score pattern.
    Falls back to rule-based heuristic if LLM is unavailable.

    Returns:
        Dict with review fields (concept_map, explanation, scores),
        or None if LLM unavailable.
    """
    prompt = _REVIEW_PROMPT_TEMPLATE.format(
        query=query,
        max_results=max_results,
        context=context,
    )

    llm_output = await call_llm(prompt, max_tokens=_MAX_OUTPUT_LEN, temperature=0.2)
    if llm_output is None:
        return None

    review = _extract_json(llm_output)
    if review is None:
        logger.warning(
            "Failed to parse LLM response as JSON (len=%d, preview=%s…)",
            len(llm_output),
            llm_output[:200],
        )
        return None

    # Normalise composite score
    raw_score = review.get("composite_score") or review.get("score") or 0.5
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.5
    score = max(0.0, min(1.0, score))

    explanation = str(review.get("overall_explanation") or review.get("reasoning") or "")

    return {
        "review_score": round(score, 3),
        "review_summary": review.get("summary", f"Score: {score:.2f}"),
        "review_strengths": review.get("strengths", []) or [],
        "review_weaknesses": review.get("weaknesses", []) or [],
        "review_suggestions": review.get("suggestions", []) or [],
        "review_concept_map": [],  # Populated from rule-based in review_node
        "review_llm_explanation": explanation,
    }


# ── Review Node ─────────────────────────────────────────────────────────


async def review_node(state: LookupWorkflowState) -> dict:
    """Evaluate lookup results quality using aggregated context.

    Design (separates extraction from evaluation):
    1. **Rule-based**: Always builds concept_map (term → CUI → IDs → type)
       deterministically from the data — accurate, reliable.
    2. **LLM**: Provides quality assessment (score, explanation, suggestions)
       based on the aggregated context. Retries 3× with exponential backoff.

    If LLM is unavailable, falls back to full rule-based review.
    """
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None:
        return {
            "review_score": 0.0,
            "review_summary": "No lookup results to review.",
            "review_strengths": [],
            "review_weaknesses": ["No results available"],
            "review_suggestions": ["Re-run the lookup with different parameters"],
            "review_concept_map": [],
            "review_llm_explanation": "No lookup results were produced.",
            "status": "reviewing",
            "steps": [make_step("ReviewAgent", "no_results", "No results to review")],
        }

    # Step 1: Always build concept map from data (deterministic)
    concept_map, _ = _rule_based_concept_map(result)

    # Step 2: Try LLM for quality assessment
    context = state.get("aggregated_context", "") or ""
    llm_review = None
    max_llm_retries = 3
    for attempt in range(max_llm_retries):
        llm_review = await _llm_review(context, state["query"], state["max_results"])
        if llm_review is not None:
            break
        if attempt < max_llm_retries - 1:
            wait = 1.5**attempt
            logger.info("LLM review attempt %d failed; retrying in %.1fs", attempt + 1, wait)
            await asyncio.sleep(wait)

    if llm_review is not None:
        # Merge: LLM provides score/explanations, rule-based provides concept_map
        step_detail = (
            f"LLM score {llm_review['review_score']:.2f}, "
            f"{len(llm_review['review_strengths'])} strengths, "
            f"{len(llm_review['review_weaknesses'])} weaknesses, "
            f"{len(concept_map)} concepts mapped"
        )
        return {
            **llm_review,
            "review_concept_map": concept_map,  # Always use rule-based extraction
            "status": "reviewing",
            "steps": [make_step("ReviewAgent(LLM)", "review", step_detail)],
        }

    # Fallback to full rule-based (no LLM available)
    review = _rule_based_review(result, state["max_results"])
    return {
        **review,
        "review_concept_map": concept_map,
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
