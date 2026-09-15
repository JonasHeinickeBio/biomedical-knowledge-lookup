"""Graph node: enrich concepts with UMLS CUI mappings."""

from __future__ import annotations

import asyncio
import functools
import logging

from ...core.central_lookup import CentralKnowledgeLookup
from ...models import ConceptIdentifier, KnowledgeSource, LookupConfig, LookupResult
from ..state import LookupWorkflowState, dict_to_lookup_result, lookup_result_to_dict, make_step
from . import _limits

logger = logging.getLogger(__name__)


async def enrichment_node(state: LookupWorkflowState) -> dict:
    """Enrich lookup concepts with UMLS CUIs.

    For each concept found in the initial lookup, searches UMLS for the
    concept's label and attaches the UMLS CUI as an identifier. Searches run
    concurrently (``MAX_CONCURRENCY``), each capped at ``CALL_TIMEOUT``, and
    the node stops waiting after ``ENRICHMENT_TIMEOUT`` seconds.
    """
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None or not result.concepts:
        return {
            "status": state.get("status", "reviewing"),
            "steps": [make_step("EnrichAgent", "skip", "No concepts to enrich")],
        }

    enriched_count = 0
    already_had_count = 0
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.UMLS],  # don't build adapters we never query
        max_results_per_source=5,
        parallel_queries=True,
        enable_deduplication=False,
        enable_source_health_tracking=False,
    )

    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        if KnowledgeSource.UMLS not in lookup.adapters:
            return {
                "steps": [
                    make_step(
                        "EnrichAgent",
                        "skip",
                        "UMLS not available (needs the [umls] extra and UMLS_API_KEY)",
                    )
                ],
            }

        to_enrich = []
        for concept in result.concepts:
            label = concept.primary_label
            if not label:
                continue

            # Skip if already has a UMLS identifier
            existing = next(
                (
                    ident.identifier
                    for ident in (concept.identifiers or [])
                    if ident.source == KnowledgeSource.UMLS
                ),
                None,
            )
            if existing is not None:
                already_had_count += 1
                logger.info("'%s' already has UMLS CUI: %s", label, existing)
                continue
            to_enrich.append(concept)

        async def _search_umls(label: str) -> LookupResult:
            return await asyncio.wait_for(
                lookup.search_concepts(
                    query=label,
                    sources=[KnowledgeSource.UMLS],
                    max_results=3,
                    parallel=False,
                ),
                timeout=_limits.CALL_TIMEOUT,
            )

        searches, unfinished = await _limits.gather_bounded(
            [functools.partial(_search_umls, c.primary_label or "") for c in to_enrich],
            timeout=_limits.ENRICHMENT_TIMEOUT,
        )

        failed = 0
        for concept, umls_result in zip(to_enrich, searches, strict=True):
            if umls_result is None:
                continue
            if isinstance(umls_result, BaseException):
                failed += 1
                logger.debug("UMLS search failed for '%s': %s", concept.primary_label, umls_result)
                continue

            if umls_result.concepts:
                best = umls_result.concepts[0]
                cui = best.primary_id  # e.g. "C0033047"
                if cui:
                    label = concept.primary_label or ""
                    # Directly append identifier (avoid mixin add_identifier for compat)
                    if concept.identifiers is None:
                        concept.identifiers = []
                    concept.identifiers.append(
                        ConceptIdentifier(
                            source=KnowledgeSource.UMLS,
                            identifier=cui,
                            label=best.primary_label or label,
                            url=f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
                        )
                    )
                    # Also add UMLS as a source
                    if concept.sources is not None and KnowledgeSource.UMLS not in concept.sources:
                        concept.sources.append(KnowledgeSource.UMLS)
                    enriched_count += 1
                    logger.info("Enriched '%s' with UMLS CUI: %s", label, cui)

    except Exception as e:
        logger.warning("UMLS enrichment failed: %s", e)
        return {
            "status": state.get("status", "reviewing"),
            "errors": [f"UMLS enrichment failed: {e}"],
            "steps": [make_step("EnrichAgent", "error", f"UMLS enrichment failed: {e}")],
        }
    finally:
        await lookup.close()

    # Re-serialize the enriched result
    enriched_dict = lookup_result_to_dict(result)

    if enriched_count > 0:
        step_detail = f"Enriched {enriched_count} concept(s) with new UMLS CUIs"
    elif already_had_count > 0:
        step_detail = f"All {already_had_count} concept(s) already had UMLS CUIs"
    else:
        step_detail = "No UMLS CUIs found for any concept"
    if failed:
        step_detail += f"; {failed} UMLS search(es) failed"
    if unfinished:
        step_detail += (
            f"; {unfinished} search(es) not finished within {_limits.ENRICHMENT_TIMEOUT:.0f}s"
        )

    return {
        "lookup_result": enriched_dict,
        "steps": [make_step("EnrichAgent", "enrich", step_detail)],
    }
