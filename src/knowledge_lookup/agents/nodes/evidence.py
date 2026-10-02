"""Graph node: literature evidence for the leading concepts.

Adds a source category the other nodes never touch — the literature. For the
top-ranked concepts it searches Europe PMC by label and keeps the first few
papers (id, title, year, journal) as ``literature_evidence``, shown to the
reviewer and exported. Opt-in via ``include_evidence``.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any

from ...core.central_lookup import CentralKnowledgeLookup
from ...models import KnowledgeSource, LookupConfig
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step
from . import _limits

logger = logging.getLogger(__name__)

PAPERS_PER_CONCEPT = 3


def _category(concept: Any, prefix: str) -> str | None:
    """Value of a ``"<prefix>:<value>"`` entry in a concept's categories."""
    for cat in getattr(concept, "categories", None) or []:
        text = str(cat)
        if text.startswith(prefix + ":"):
            return text[len(prefix) + 1 :].strip() or None
    return None


def _paper(concept: Any) -> dict[str, Any]:
    return {
        "id": concept.primary_id,
        "title": concept.primary_label,
        "year": _category(concept, "year"),
        "journal": _category(concept, "journal"),
    }


async def evidence_node(state: LookupWorkflowState) -> dict:
    """Attach top Europe PMC papers to the leading concepts."""
    if not state.get("include_evidence"):
        return {
            "steps": [
                make_step(
                    "EvidenceAgent", "skip", "Literature evidence is off (include_evidence=False)"
                )
            ]
        }

    result = dict_to_lookup_result(state.get("lookup_result"))
    concepts = [c for c in ((result.concepts if result else None) or []) if c.primary_label]
    if not concepts:
        return {"steps": [make_step("EvidenceAgent", "skip", "No concepts to look up")]}
    top = concepts[: _limits.MAX_EVIDENCE_CONCEPTS]

    config = LookupConfig(
        enabled_sources=[KnowledgeSource.EUROPEPMC],
        max_results_per_source=PAPERS_PER_CONCEPT,
        parallel_queries=True,
        enable_deduplication=False,
        enable_source_health_tracking=False,
    )
    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        if KnowledgeSource.EUROPEPMC not in lookup.adapters:
            return {"steps": [make_step("EvidenceAgent", "skip", "Europe PMC not available")]}

        async def _papers(label: str) -> list[Any]:
            found = await asyncio.wait_for(
                lookup.search_concepts(
                    query=f'"{label}"',
                    sources=[KnowledgeSource.EUROPEPMC],
                    max_results=PAPERS_PER_CONCEPT,
                    parallel=False,
                ),
                timeout=_limits.CALL_TIMEOUT,
            )
            papers: list[Any] = list(found.concepts or [])
            return papers[:PAPERS_PER_CONCEPT]

        gathered, unfinished = await _limits.gather_bounded(
            [functools.partial(_papers, c.primary_label or "") for c in top],
            timeout=_limits.EVIDENCE_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Evidence gathering failed: %s", exc)
        return {
            "errors": [f"Evidence gathering failed: {exc}"],
            "steps": [make_step("EvidenceAgent", "error", str(exc))],
        }
    finally:
        await lookup.close()

    evidence: list[dict[str, Any]] = []
    for concept, papers in zip(top, gathered, strict=True):
        if isinstance(papers, list) and papers:
            evidence.append(
                {
                    "concept": concept.primary_label,
                    "concept_id": concept.primary_id,
                    "papers": [_paper(p) for p in papers],
                }
            )

    detail = (
        f"{sum(len(e['papers']) for e in evidence)} paper(s) for "
        f"{len(evidence)}/{len(top)} concept(s) from Europe PMC"
    )
    if unfinished:
        detail += f"; {unfinished} not finished within {_limits.EVIDENCE_TIMEOUT:.0f}s"
    return {
        "literature_evidence": evidence,
        "steps": [make_step("EvidenceAgent", "evidence", detail)],
    }
