"""Graph node: autonomous gap analysis and follow-up planning.

``quality_gate`` only scores the results. This node closes the loop: when the
results have a *gap* it plans a focused second search by itself, instead of
waiting for a human to type refinement notes.

Gaps it recognises (:func:`diagnose`):

``empty``
    nothing was found.
``thin``
    fewer than :data:`THIN_CONCEPT_COUNT` concepts survived filtering.
``failed_sources``
    some queried sources failed (rate limit, outage); they are retried.
``single_source``
    every concept came from one source although several were queried.

The plan (:func:`plan_probes`) is a list of *probes* — a search term, with
optional sources — drawn, in priority order, from what the run already knows:
synonyms and hierarchy labels of the leading concepts, named relationship
targets that the per-round term cap left unsearched, and (only when the
results are empty or thin and an LLM is configured) the model's suggestions.
Nothing is invented from string transforms, and a term that was already
searched is never repeated.

``lookup`` then runs the probes as a focused pass without using up
``max_iterations``; ``max_auto_rounds`` bounds how often this can happen.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...models import LookupResult
from ..config import call_llm
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step
from ._limits import resolve_sources

logger = logging.getLogger(__name__)

#: Fewer filtered concepts than this counts as a thin result.
THIN_CONCEPT_COUNT = 3
#: Most terms one follow-up round searches.
MAX_FOLLOWUP_TERMS = 6
#: Leading concepts whose synonyms / hierarchy labels are harvested.
LEADING_CONCEPTS = 5
SYNONYMS_PER_CONCEPT = 3
_MAX_TERM_WORDS = 6


def diagnose(state: LookupWorkflowState) -> list[str]:
    """Name the gaps in the current results (empty list = nothing to follow up)."""
    result = dict_to_lookup_result(state.get("lookup_result"))
    concepts = (result.concepts if result else None) or []
    if not concepts:
        return ["empty"]

    gaps: list[str] = []
    if len(concepts) < min(THIN_CONCEPT_COUNT, max(1, state.get("max_results") or 1)):
        gaps.append("thin")
    if result is not None and result.sources_failed:
        gaps.append("failed_sources")

    queried = {str(s).upper() for s in (result.sources_queried or [])} if result else set()
    if len(queried) > 1 and len(state.get("source_filter") or []) != 1:
        concept_sources = {str(s).upper() for c in concepts for s in (c.sources or [])}
        if len(concept_sources) == 1:
            gaps.append("single_source")
    return gaps


def needs_followup(state: LookupWorkflowState) -> bool:
    """Whether the workflow should plan a follow-up round now."""
    if state.get("status") == "failed":
        return False
    if (state.get("auto_round") or 0) >= (state.get("max_auto_rounds") or 0):
        return False
    return bool(diagnose(state))


def _usable(term: str, tried: set[str]) -> bool:
    cleaned = term.strip()
    if not cleaned or cleaned.startswith("http"):
        return False
    if len(cleaned.split()) > _MAX_TERM_WORDS or len(cleaned) > 80:
        return False
    return cleaned.lower() not in tried


def _harvest_terms(
    state: LookupWorkflowState, result: LookupResult | None, tried: set[str]
) -> list[tuple[str, str]]:
    """``(term, reason)`` candidates from the concepts and edges already in hand."""
    out: list[tuple[str, str]] = []
    seen = set(tried)

    def _offer(term: str, reason: str) -> None:
        if _usable(term, seen):
            seen.add(term.strip().lower())
            out.append((term.strip(), reason))

    leading = list((result.concepts if result else None) or [])[:LEADING_CONCEPTS]
    for concept in leading:
        for syn in (concept.synonyms or [])[:SYNONYMS_PER_CONCEPT]:
            _offer(str(syn), f"synonym of {concept.primary_label}")
    for concept in leading:
        for attr, reason in (("children", "narrower than"), ("parents", "broader than")):
            for name in getattr(concept, attr, None) or []:
                _offer(str(name), f"{reason} {concept.primary_label}")
    for edge in state.get("relationship_edges") or []:
        name = edge.get("related_name") or ""
        if name and not edge.get("searched"):
            label = edge.get("relation_label") or "related"
            _offer(name, f"{label} of {edge.get('source_concept_label') or 'a concept'}")
    return out


def _parse_term_list(text: str | None) -> list[str]:
    """Parse an LLM reply holding a JSON list of strings."""
    if not text:
        return []
    match = re.search(r"\[.*?\]", text, re.S)
    if not match:
        return []
    try:
        raw = json.loads(match.group(0))
    except (ValueError, TypeError):
        return []
    return [str(x).strip() for x in raw if isinstance(x, str) and x.strip()]


async def _llm_terms(query: str, labels: list[str], gaps: list[str]) -> list[str]:
    found = ", ".join(labels[:8]) or "nothing"
    prompt = (
        "A biomedical concept search needs better search terms.\n"
        f"Query: {query!r}\nProblem: {', '.join(gaps)}\nConcepts found so far: {found}\n"
        "Suggest up to 5 alternative search terms (synonyms, spelled-out abbreviations, "
        "closely related clinical terms). Reply with only a JSON list of strings."
    )
    return _parse_term_list(await call_llm(prompt, max_tokens=200, temperature=0.2))


async def plan_probes(state: LookupWorkflowState, gaps: list[str]) -> list[dict[str, Any]]:
    """Plan the focused searches that address *gaps*."""
    query = state.get("original_query") or state["query"]
    result = dict_to_lookup_result(state.get("lookup_result"))
    tried = {t.strip().lower() for t in (state.get("expanded_search_terms") or [])}
    tried.add(query.strip().lower())

    probes: list[dict[str, Any]] = []

    # Retry sources that failed for the original query.
    if "failed_sources" in gaps and result is not None:
        failed = [str(s) for s in result.sources_failed or []]
        wanted = resolve_sources(state.get("source_filter"))
        if wanted is not None:
            allowed = {s.value for s in wanted}
            failed = [s for s in failed if s.upper() in allowed]
        if failed:
            probes.append(
                {
                    "term": query,
                    "sources": failed,
                    "reason": f"retry failed source(s) {', '.join(failed)}",
                }
            )

    # Terms already known from the concepts and relationship edges.
    candidates = _harvest_terms(state, result, tried)
    # The model only gets a say when the results are empty or thin.
    if len(candidates) < MAX_FOLLOWUP_TERMS and ({"empty", "thin"} & set(gaps)):
        seen = tried | {t.lower() for t, _ in candidates}
        labels = [c.primary_label or "" for c in (result.concepts if result else None) or []]
        for term in await _llm_terms(query, labels, gaps):
            if _usable(term, seen):
                seen.add(term.lower())
                candidates.append((term, "LLM suggestion"))

    for term, reason in candidates[:MAX_FOLLOWUP_TERMS]:
        probes.append({"term": term, "sources": None, "reason": reason})
    return probes


async def followup_node(state: LookupWorkflowState) -> dict:
    """Plan the next focused search, or give up when there is nothing new to try."""
    auto_round = (state.get("auto_round") or 0) + 1
    gaps = diagnose(state)
    probes = await plan_probes(state, gaps) if gaps else []

    if not probes:
        return {
            "auto_round": auto_round,
            "followup_pending": False,
            "followup_probes": [],
            "steps": [
                make_step(
                    "FollowupAgent",
                    "no_action",
                    f"Gaps ({', '.join(gaps) or 'none'}) but no new term or source to try",
                )
            ],
        }

    tried = list(state.get("expanded_search_terms") or [])
    seen = {t.strip().lower() for t in tried}
    for probe in probes:
        key = probe["term"].strip().lower()
        if key not in seen:
            seen.add(key)
            tried.append(probe["term"])

    shown = "; ".join(f"{p['term']} ({p['reason']})" for p in probes[:4])
    more = f" ... (+{len(probes) - 4} more)" if len(probes) > 4 else ""
    return {
        "auto_round": auto_round,
        "followup_pending": True,
        "followup_probes": probes,
        "expanded_search_terms": tried,
        "steps": [
            make_step(
                "FollowupAgent",
                "plan",
                f"Round {auto_round}: gaps [{', '.join(gaps)}] -> {len(probes)} probe(s): "
                f"{shown}{more}",
            )
        ],
    }
