"""Graph node: knowledge lookup with parallel expanded term search.

Searches ALL expanded query variants (from preprocess) independently
against ALL configured sources. Results from all variants are merged
and deduplicated in a single pass.

When ``followup_pending`` is set (by the ``followup`` node) the node instead
runs a *focused* pass: it searches only the planned ``followup_probes`` (a
term, optionally with its own sources), merges what they find into the
existing result, and does not count against ``max_iterations``.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

from ...core.central_lookup import CentralKnowledgeLookup
from ...core.term_expansion import merge_concept_results
from ...models import KnowledgeSource, LookupConfig, LookupResult
from ..state import (
    LookupWorkflowState,
    dict_to_lookup_result,
    lookup_result_to_dict,
    make_step,
)
from . import _limits

logger = logging.getLogger(__name__)


def _get_search_terms(state: LookupWorkflowState) -> list[str]:
    """Get the list of search terms to run.

    Uses expanded_search_terms if available (from preprocess),
    otherwise falls back to comma-splitting the query.
    """
    expanded = state.get("expanded_search_terms")
    if expanded:
        return expanded

    # Fallback: split commas
    query = state["query"]
    terms = [t.strip() for t in query.split(",") if t.strip()]
    return terms if terms else [query]


def resolve_probe_sources(names: list[str] | None) -> list[KnowledgeSource]:
    """Map a probe's source names to :class:`KnowledgeSource` members (unknown ones dropped)."""
    return _limits.resolve_sources(names) or []


async def lookup_node(state: LookupWorkflowState) -> dict:
    """Execute knowledge lookup across configured sources.

    Searches ALL expanded search terms (from preprocess) independently
    against all sources. Results are merged and deduplicated.
    """
    query = state["query"]
    iteration = state["iteration"]

    followup = bool(state.get("followup_pending"))
    probes = [p for p in (state.get("followup_probes") or []) if p.get("term")]

    # Get all search terms (expanded from preprocess or comma-split); a
    # follow-up pass searches only its planned probes.
    search_terms = [p["term"] for p in probes] if followup else _get_search_terms(state)

    source_filter = _limits.resolve_sources(state.get("source_filter"))

    # Build config; only the selected sources' adapters are instantiated
    config = LookupConfig(
        enabled_sources=source_filter,
        max_results_per_source=state["max_results"],
        parallel_queries=True,
        enable_deduplication=True,
        enable_source_health_tracking=True,
    )

    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        # Resolve sources
        sources: list[KnowledgeSource] | None = None
        unavailable_error: list[str] = []
        if source_filter is not None:
            sources = [s for s in source_filter if s in lookup.adapters]
            if not sources:
                requested = ", ".join(state.get("source_filter") or [])
                unavailable_error.append(
                    f"None of the requested sources are available: {requested}"
                )

        # Resolve concept types
        concept_types = None
        ct_filter = state.get("concept_type_filter")
        if ct_filter:
            from ...models import ConceptType

            resolved_types: list = []
            for ct in ct_filter:
                try:
                    resolved_types.append(ConceptType(ct.upper()))
                except ValueError:
                    pass
            concept_types = resolved_types if resolved_types else None

        # A probe may name its own sources; those the user did not select (or
        # that failed to initialise) are dropped, falling back to the selection.
        def _probe_sources(probe: dict) -> list[KnowledgeSource] | None:
            wanted = resolve_probe_sources(probe.get("sources"))
            if not wanted:
                return sources
            allowed = [s for s in wanted if s in lookup.adapters]
            if source_filter is not None:
                allowed = [s for s in allowed if s in source_filter]
            return allowed or sources

        term_sources: list[list[KnowledgeSource] | None] = (
            [_probe_sources(p) for p in probes] if followup else [sources] * len(search_terms)
        )

        # Search the expanded terms concurrently, within the node's time budget
        async def _search_term(term: str, term_srcs: list[KnowledgeSource] | None) -> LookupResult:
            return await lookup.search_concepts(
                query=term,
                concept_types=concept_types,
                sources=term_srcs,
                max_results=state["max_results"],
                parallel=True,
            )

        gather_results, _ = await _limits.gather_bounded(
            []
            if unavailable_error
            else [
                functools.partial(_search_term, t, srcs)
                for t, srcs in zip(search_terms, term_sources, strict=True)
            ],
            timeout=_limits.LOOKUP_TIMEOUT,
        )

        # Merge results across all terms (a follow-up pass merges into the
        # concepts found so far)
        all_concepts: list[Any] = []
        exec_time_total = 0.0
        sources_succeeded_union: set[str] = set()
        sources_failed_union: set[str] = set()
        # what *this* pass saw, kept apart from what earlier passes left behind
        pass_succeeded: set[str] = set()
        pass_failed: set[str] = set()
        previous = dict_to_lookup_result(state.get("lookup_result")) if followup else None
        if previous is not None:
            all_concepts = list(previous.concepts or [])
            exec_time_total = previous.execution_time or 0.0
            sources_succeeded_union = {str(s) for s in previous.sources_succeeded or []}
            sources_failed_union = {str(s) for s in previous.sources_failed or []}
        errors_combined: dict[str, str] = {}
        term_report: list[str] = []

        for term_idx, term_result in enumerate(gather_results):
            term_label = (
                search_terms[term_idx] if term_idx < len(search_terms) else f"term_{term_idx}"
            )

            if term_result is None:
                errors_combined[f"lookup_{term_label}"] = (
                    f"Search not finished within {_limits.LOOKUP_TIMEOUT:.0f}s"
                )
                term_report.append(f"{term_label}=TIMEOUT")
                continue
            if isinstance(term_result, BaseException):
                errors_combined[f"lookup_{term_label}"] = str(term_result)
                term_report.append(f"{term_label}=FAIL")
                continue

            # At this point mypy knows term_result is LookupResult
            result: LookupResult = term_result

            exec_time_total += result.execution_time or 0.0

            for s in result.sources_succeeded or []:
                sources_succeeded_union.add(str(s))
                pass_succeeded.add(str(s))
            for s in result.sources_failed or []:
                sources_failed_union.add(str(s))
                pass_failed.add(str(s))

            term_errors = result.errors
            if isinstance(term_errors, dict):
                for err_src, err_msg in term_errors.items():
                    errors_combined[str(err_src)] = str(err_msg)

            # Add concepts, deduplicating by normalized label (shared with
            # core.term_expansion.expand_and_search's parallel-search-and-merge
            # path so both maintain one dedupe implementation, not two).
            n_before = len(all_concepts)
            merge_concept_results(all_concepts, result.concepts or [])
            n_new = len(all_concepts) - n_before

            n_total = len(result.concepts or [])
            term_report.append(f"{term_label}={n_new}/{n_total}")

        # Build merged result
        if previous is not None:
            # A source that failed earlier and answered in this pass is no longer
            # failed (otherwise a successful retry would leave the gap in place);
            # one that failed again, or was not retried, still is.
            earlier_failed = {str(s) for s in previous.sources_failed or []}
            sources_failed_union = (earlier_failed - pass_succeeded) | pass_failed

        query_sources = sources or list(lookup.adapters.keys())
        merged = LookupResult(query=query, sources_queried=query_sources)
        merged.concepts = all_concepts
        merged.total_found = len(all_concepts)
        merged.execution_time = exec_time_total

        for src_name in sources_succeeded_union:
            merged.add_concepts([], KnowledgeSource(src_name.upper()))

        for src_name in sources_failed_union:
            merged.add_error(src_name, "Source failed for some terms")

        # add_error records its key as a failed *source*, so only per-source
        # errors go there; per-term errors ("lookup_<term>") are reported
        # through the state's errors list (an unknown key would make the
        # serialized result fail validation in the next node).
        source_names = {s.value for s in KnowledgeSource}
        for err_src, err_msg in errors_combined.items():
            if err_src.upper() in source_names:
                merged.add_error(err_src, err_msg)

        n_terms = len(search_terms)
        n_concepts = len(all_concepts)
        n_sources = len(sources_succeeded_union)

        if followup:
            step_detail = (
                f"Follow-up round {state.get('auto_round') or 1}: now {n_concepts} concepts "
                f"from {n_sources} sources ({n_terms} focused search(es))"
            )
        else:
            step_detail = (
                f"Found {n_concepts} concepts from {n_sources} sources "
                f"({n_terms} search term(s), iter {iteration + 1})"
            )
        if n_terms > 1:
            term_detail = " | ".join(term_report[:10])
            if len(term_report) > 10:
                term_detail += f" ... (+{len(term_report) - 10} more)"
            step_detail += f" — {term_detail}"

        result_dict = lookup_result_to_dict(merged)

        new_errors = unavailable_error + list(errors_combined.values())
        if followup:
            return {
                "lookup_result": result_dict,
                "status": "searching",
                "followup_pending": False,
                "followup_probes": [],
                "errors": list(state.get("errors") or []) + new_errors,
                "steps": [make_step("LookupAgent", "followup_search", step_detail)],
            }
        return {
            "lookup_result": result_dict,
            "status": "searching",  # Will be evaluated by quality_gate
            "iteration": iteration + 1,
            # The result was rebuilt from scratch, so its concepts have not been
            # cross-referenced yet, whatever detail_gather did to an earlier result
            # (a refinement comes through here).
            "xref_labels": [],
            "errors": new_errors,
            "steps": [make_step("LookupAgent", "search", step_detail)],
        }

    except Exception as e:
        return {
            "status": "failed",
            "errors": [f"Lookup failed: {e}"],
            "steps": [make_step("LookupAgent", "error", str(e))],
        }
    finally:
        await lookup.close()
