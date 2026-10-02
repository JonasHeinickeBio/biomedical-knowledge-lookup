"""Graph node: harvest relationship edges for the final concepts.

Runs after ``enrichment``, when concepts carry identifiers from several sources
(OLS IRIs, UMLS CUIs, gene symbols, ...). For the top-ranked concepts it asks
each relationship-capable adapter — KEGG gene<->pathway links, UMLS semantic
relations, STRING interaction partners, DisGeNET / Open Targets associations,
OLS hierarchy, WikiPathways, Ensembl — for the edges keyed on *that* source's
identifier, including sources that only appear on the concept's identifiers.

The edges are reported (``relationship_edges``), shown to the reviewer and
exported; named, not-yet-searched targets are also candidates for the
``followup`` node's focused search. Opt-in via ``include_relationships``
because every concept costs one call per relationship-capable source.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

from ...core.central_lookup import CentralKnowledgeLookup
from ...core.term_expansion import AdapterRelationshipSource, RelatedTerm
from ...models import KnowledgeSource, LookupConfig
from ..state import LookupWorkflowState, dict_to_lookup_result, make_step
from . import _limits
from ._edges import edge_from_related_term, merge_edges

logger = logging.getLogger(__name__)

#: Adapters that implement ``get_relationships``.
RELATIONSHIP_SOURCES: tuple[KnowledgeSource, ...] = (
    KnowledgeSource.OLS,
    KnowledgeSource.UMLS,
    KnowledgeSource.KEGG,
    KnowledgeSource.STRING,
    KnowledgeSource.WIKIPATHWAYS,
    KnowledgeSource.DISGENET,
    KnowledgeSource.OPENTARGETS,
    KnowledgeSource.ENSEMBL,
)

_CONCURRENCY = 3


def concept_sources(concept: Any) -> set[KnowledgeSource]:
    """Every known source named on a concept's ``sources`` or ``identifiers``."""
    found: set[KnowledgeSource] = set()
    names: list[Any] = list(getattr(concept, "sources", None) or [])
    names += [getattr(i, "source", None) for i in getattr(concept, "identifiers", None) or []]
    for name in names:
        if name is None:
            continue
        try:
            found.add(
                name if isinstance(name, KnowledgeSource) else KnowledgeSource(str(name).upper())
            )
        except ValueError:
            continue
    return found


async def relationships_node(state: LookupWorkflowState) -> dict:
    """Collect relationship edges for the leading concepts."""
    if not state.get("include_relationships"):
        return {
            "steps": [
                make_step(
                    "RelationshipAgent",
                    "skip",
                    "Relationship harvesting is off (include_relationships=False)",
                )
            ]
        }

    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None or not result.concepts:
        return {"steps": [make_step("RelationshipAgent", "skip", "No concepts to expand")]}

    top = list(result.concepts)[: _limits.MAX_RELATIONSHIP_CONCEPTS]
    needed = [s for s in RELATIONSHIP_SOURCES if any(s in concept_sources(c) for c in top)]
    if not needed:
        return {
            "steps": [
                make_step(
                    "RelationshipAgent",
                    "skip",
                    "No concept carries an identifier from a relationship-capable source",
                )
            ]
        }

    config = LookupConfig(
        enabled_sources=needed,
        max_results_per_source=5,
        parallel_queries=True,
        enable_deduplication=False,
        enable_source_health_tracking=False,
    )
    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        harvester = AdapterRelationshipSource(
            lookup,
            limit_per_concept=10,
            allowed_sources=set(RELATIONSHIP_SOURCES),
            include_identifier_sources=True,
        )

        async def _expand(concept: Any) -> list[RelatedTerm]:
            return await harvester.expand(concept)

        gathered, unfinished = await _limits.gather_bounded(
            [functools.partial(_expand, c) for c in top],
            timeout=_limits.RELATIONSHIPS_TIMEOUT,
            concurrency=_CONCURRENCY,
        )
    except Exception as exc:
        logger.warning("Relationship harvesting failed: %s", exc)
        return {
            "errors": [f"Relationship harvesting failed: {exc}"],
            "steps": [make_step("RelationshipAgent", "error", str(exc))],
        }
    finally:
        await lookup.close()

    new_edges: list[dict[str, Any]] = []
    for concept, terms in zip(top, gathered, strict=True):
        if not isinstance(terms, list):
            continue  # not finished in time, or failed
        new_edges.extend(edge_from_related_term(concept, t) for t in terms)

    edges = merge_edges(state.get("relationship_edges") or [], new_edges)
    named = sum(1 for e in new_edges if e.get("related_name"))
    detail = (
        f"{len(new_edges)} new edge(s) ({named} with a named target) for "
        f"{len(top)} concept(s) via {', '.join(s.value for s in needed)}"
    )
    if unfinished:
        detail += f"; {unfinished} not finished within {_limits.RELATIONSHIPS_TIMEOUT:.0f}s"
    return {
        "relationship_edges": edges,
        "steps": [make_step("RelationshipAgent", "relationships", detail)],
    }
