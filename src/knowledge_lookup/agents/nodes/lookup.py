"""Graph node: knowledge lookup with parallel expanded term search.

Searches ALL expanded query variants (from preprocess) independently
against ALL configured sources. Results from all variants are merged
and deduplicated in a single pass.
"""

from __future__ import annotations

import logging
from typing import Any

from ...core.central_lookup import CentralKnowledgeLookup
from ...models import KnowledgeSource, LookupConfig, LookupResult
from ..state import LookupWorkflowState, lookup_result_to_dict, make_step

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


async def lookup_node(state: LookupWorkflowState) -> dict:
    """Execute knowledge lookup across configured sources.

    Searches ALL expanded search terms (from preprocess) independently
    against all sources. Results are merged and deduplicated.
    """
    query = state["query"]
    iteration = state["iteration"]

    # Get all search terms (expanded from preprocess or comma-split)
    search_terms = _get_search_terms(state)

    # Build config
    config = LookupConfig(
        max_results_per_source=state["max_results"],
        parallel_queries=True,
        enable_deduplication=True,
        enable_source_health_tracking=True,
    )

    lookup = CentralKnowledgeLookup(config=config, auto_initialize=True)
    try:
        # Resolve sources
        sources: list[KnowledgeSource] | None = None
        source_filter = state.get("source_filter")
        if source_filter:
            resolved_sources: list[KnowledgeSource] = []
            for name in source_filter:
                try:
                    src = KnowledgeSource(name.upper())
                    if src in lookup.adapters:
                        resolved_sources.append(src)
                except ValueError:
                    pass
            sources = resolved_sources if resolved_sources else None

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

        # Search ALL expanded terms in parallel
        import asyncio

        async def _search_term(term: str) -> LookupResult:
            return await lookup.search_concepts(
                query=term,
                concept_types=concept_types,
                sources=sources,
                max_results=state["max_results"],
                parallel=True,
            )

        gather_results: list[LookupResult | BaseException] = await asyncio.gather(
            *[_search_term(t) for t in search_terms],
            return_exceptions=True,
        )

        # Merge results across all terms
        all_concepts: list[Any] = []
        seen_labels: set[str] = set()
        seen_ids: set[str] = set()
        exec_time_total = 0.0
        sources_succeeded_union: set[str] = set()
        sources_failed_union: set[str] = set()
        errors_combined: dict[str, str] = {}
        term_report: list[str] = []

        for term_idx, term_result in enumerate(gather_results):
            term_label = (
                search_terms[term_idx] if term_idx < len(search_terms) else f"term_{term_idx}"
            )

            if isinstance(term_result, BaseException):
                errors_combined[f"lookup_{term_label}"] = str(term_result)
                term_report.append(f"{term_label}=FAIL")
                continue

            # At this point mypy knows term_result is LookupResult
            result: LookupResult = term_result

            exec_time_total += result.execution_time or 0.0

            for s in result.sources_succeeded or []:
                sources_succeeded_union.add(str(s))
            for s in result.sources_failed or []:
                sources_failed_union.add(str(s))

            term_errors = result.errors
            if isinstance(term_errors, dict):
                for err_src, err_msg in term_errors.items():
                    errors_combined[str(err_src)] = str(err_msg)

            # Add concepts with deduplication by normalized label
            n_new = 0
            for c in result.concepts or []:
                label = (c.primary_label or "").lower().strip()
                cid = c.primary_id or ""

                if label and label not in seen_labels:
                    seen_labels.add(label)
                    all_concepts.append(c)
                    n_new += 1
                elif not label and cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    all_concepts.append(c)
                    n_new += 1
                elif label in seen_labels:
                    # Duplicate by label — still merge identifiers, definitions
                    existing = next(
                        (
                            ec
                            for ec in all_concepts
                            if (ec.primary_label or "").lower().strip() == label
                        ),
                        None,
                    )
                    if existing:
                        _merge_concept_data(existing, c)

            n_total = len(result.concepts or [])
            term_report.append(f"{term_label}={n_new}/{n_total}")

        # Build merged result
        query_sources = sources or list(lookup.adapters.keys())
        merged = LookupResult(query=query, sources_queried=query_sources)
        merged.concepts = all_concepts
        merged.total_found = len(all_concepts)
        merged.execution_time = exec_time_total

        for src_name in sources_succeeded_union:
            merged.add_concepts([], KnowledgeSource(src_name.upper()))

        for src_name in sources_failed_union:
            merged.add_error(src_name, "Source failed for some terms")

        for err_src, err_msg in errors_combined.items():
            merged.add_error(err_src, err_msg)

        n_terms = len(search_terms)
        n_concepts = len(all_concepts)
        n_sources = len(sources_succeeded_union)

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

        return {
            "lookup_result": result_dict,
            "status": "searching",  # Will be evaluated by quality_gate
            "iteration": iteration + 1,
            "errors": list(errors_combined.values()),
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


def _merge_concept_data(target: Any, source: Any) -> None:
    """Merge identifiers, definitions, synonyms from source into target."""
    # Merge identifiers
    for ident in source.identifiers or []:
        if target.identifiers is None:
            target.identifiers = []
        exists = any(
            hasattr(i, "identifier") and i.identifier == ident.identifier
            for i in target.identifiers
        )
        if not exists:
            target.identifiers.append(ident)

    # Merge definitions
    for d in source.definitions or []:
        if target.definitions is None:
            target.definitions = []
        if d not in target.definitions:
            target.definitions.append(d)

    # Merge synonyms
    for s in source.synonyms or []:
        if target.synonyms is None:
            target.synonyms = []
        if s.lower() not in [x.lower() for x in target.synonyms]:
            target.synonyms.append(s)

    # Merge semantic types
    for st in source.semantic_types or []:
        if target.semantic_types is None:
            target.semantic_types = []
        if str(st) not in [str(x) for x in target.semantic_types]:
            target.semantic_types.append(st)

    # Track sources
    for src in source.sources or []:
        if target.sources is None:
            target.sources = []
        if str(src) not in [str(x) for x in target.sources]:
            target.sources.append(src)
