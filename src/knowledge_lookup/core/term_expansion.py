"""
Iterative term expansion: synonyms + abbreviation/long-form discovery.

``expand_and_search`` takes a single search term and, instead of searching
it once, searches it, harvests synonyms and abbreviation/long-form variants
from what it finds (e.g. "COPD" -> "chronic obstructive pulmonary disease"),
searches those too, and repeats — stopping when a round finds no genuinely
new terms, or a round cap is hit. Every term tried is recorded durably via
:class:`~knowledge_lookup.core.expansion_store.ExpansionStore`.

This is a core-level capability, usable directly through
``CentralKnowledgeLookup`` without the optional ``[agents]`` (LangGraph)
extra — it's a lookup-quality improvement, not an LLM-orchestration
feature. The agent workflow's ``expand`` node (``agents/nodes/expand.py``)
is a thin wrapper calling the same function.

Synonym harvesting needs no new adapter work: most adapters already
populate ``UnifiedConcept.synonyms`` (see ``CentralKnowledgeLookup
.suggest_similar_concepts`` for the existing "search using the concept's
label and synonyms" precedent this reuses the same idea for). Abbreviation
expansion is new: :class:`UMLSAbbreviationSource` reads UMLS Metathesaurus
atom term-types (TTY) for a concept's CUI — ``AB``/``AA`` atoms are
abbreviation forms, ``PT``/``PN``/``FN`` atoms are full/preferred forms
sharing the same CUI — and degrades to "no expansion" (never an error)
when the ``[umls]`` extra isn't installed or no API key is configured.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from .expansion_store import (
    ORIGIN_ABBREVIATION,
    ORIGIN_LONG_FORM,
    ORIGIN_ORIGINAL,
    ORIGIN_SYNONYM,
    STOP_FIXED_POINT,
    STOP_MAX_ROUNDS,
    ExpansionStore,
)

if TYPE_CHECKING:
    from ..models import ConceptType, KnowledgeSource, LookupConfig, LookupResult
    from .central_lookup import CentralKnowledgeLookup

logger = logging.getLogger(__name__)


class AbbreviationSource(Protocol):
    """A pluggable source of abbreviation <-> long-form candidates.

    Implementations must never raise for a "no data" case — return ``[]``
    instead, so a missing extra/API key/network failure degrades to "no
    expansion from this source" rather than aborting the whole search.
    """

    async def expand(self, term: str) -> list[tuple[str, str]]:
        """Return ``(candidate_term, origin)`` pairs for *term*.

        *origin* is :data:`ORIGIN_ABBREVIATION` (candidate is a shorter
        abbreviation of *term*) or :data:`ORIGIN_LONG_FORM` (candidate is
        a longer/expanded form of *term*).
        """
        ...


class UMLSAbbreviationSource:
    """Abbreviation/long-form pairs via UMLS Metathesaurus atom term-types.

    Looks up *term* in UMLS, then inspects every atom sharing that
    concept's CUI: atoms whose term-type (TTY) is ``AB``/``AA``
    (abbreviation / auxiliary abbreviation) are abbreviation candidates;
    atoms whose TTY is ``PT``/``PN``/``FN`` (preferred term / preferred
    name / full form) are long-form candidates. Requires the ``[umls]``
    extra and a configured UMLS API key — with neither, :meth:`expand`
    always returns ``[]`` rather than raising.
    """

    _ABBREVIATION_TTYS = frozenset({"AB", "AA"})
    _FULL_FORM_TTYS = frozenset({"PT", "PN", "FN"})

    def __init__(self, config: LookupConfig | None = None) -> None:
        self._config = config
        self._adapter: Any | None = None
        self._unavailable = False

    def _get_adapter(self) -> Any | None:
        if self._unavailable:
            return None
        if self._adapter is not None:
            return self._adapter
        try:
            from ..adapters.umls_adapter import UMLSAdapter
            from ..models import LookupConfig
        except ImportError:
            self._unavailable = True
            return None

        adapter = UMLSAdapter(self._config or LookupConfig())
        if not adapter.is_available():
            self._unavailable = True
            return None
        self._adapter = adapter
        return adapter

    async def expand(self, term: str) -> list[tuple[str, str]]:
        adapter = self._get_adapter()
        if adapter is None or not term.strip():
            return []

        try:
            concepts = await adapter.search_concepts(term, limit=3)
        except Exception as exc:  # noqa: BLE001 - best-effort, never abort the caller
            logger.debug("UMLSAbbreviationSource: search failed for %r: %s", term, exc)
            return []

        term_lower = term.strip().lower()
        candidates: list[tuple[str, str]] = []
        seen = {term_lower}

        for concept in concepts:
            cui = getattr(concept, "primary_id", None)
            if not cui:
                continue
            try:
                resp = await adapter.client.cui_api.get_atoms(cui, page_size=200)
                atoms = resp.result or []
            except Exception as exc:  # noqa: BLE001 - a single concept's atoms failing shouldn't abort the rest
                logger.debug("UMLSAbbreviationSource: get_atoms failed for %s: %s", cui, exc)
                continue

            abbr_names: set[str] = set()
            full_names: set[str] = set()
            for atom in atoms:
                tty = (getattr(atom, "term_type", None) or "").upper()
                name = (getattr(atom, "name", None) or "").strip()
                if not name:
                    continue
                if tty in self._ABBREVIATION_TTYS:
                    abbr_names.add(name)
                elif tty in self._FULL_FORM_TTYS:
                    full_names.add(name)

            # A concept with both kinds of atom is exactly an abbreviation <->
            # long-form pair sharing a CUI — offer whichever side wasn't the
            # search term itself.
            for name in full_names:
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    candidates.append((name, ORIGIN_LONG_FORM))
            for name in abbr_names:
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    candidates.append((name, ORIGIN_ABBREVIATION))

        return candidates

    async def close(self) -> None:
        if self._adapter is not None:
            await self._adapter.close()


@dataclass
class ExpansionTrace:
    """A summary of one :func:`expand_and_search` call, for callers that
    want the trail without querying :class:`ExpansionStore` directly."""

    run_id: int | None
    rounds_run: int
    stop_reason: str
    terms_by_round: list[list[str]] = field(default_factory=list)

    @property
    def all_terms_tried(self) -> list[str]:
        return [t for round_terms in self.terms_by_round for t in round_terms]


def merge_concept_results(target: list[Any], new_concepts: list[Any]) -> None:
    """Append *new_concepts* into *target*, deduplicating by normalized
    label (falling back to ``primary_id`` when a concept has no label) and
    merging fields — identifiers, definitions, synonyms, semantic types,
    sources — into the kept concept for anything already present.

    Shared by :func:`expand_and_search` and
    ``agents.nodes.lookup.lookup_node`` so both parallel-search-and-merge
    paths behave identically instead of maintaining two copies of the same
    dedupe logic.
    """
    seen_labels = {(c.primary_label or "").lower().strip() for c in target if c.primary_label}
    seen_ids = {c.primary_id for c in target if not c.primary_label and c.primary_id}

    for c in new_concepts:
        label = (c.primary_label or "").lower().strip()
        cid = c.primary_id or ""

        if label and label not in seen_labels:
            seen_labels.add(label)
            target.append(c)
        elif not label and cid and cid not in seen_ids:
            seen_ids.add(cid)
            target.append(c)
        elif label in seen_labels:
            existing = next(
                (ec for ec in target if (ec.primary_label or "").lower().strip() == label),
                None,
            )
            if existing is not None:
                merge_concept_fields(existing, c)


def merge_concept_fields(target: Any, source: Any) -> None:
    """Merge identifiers/definitions/synonyms/semantic_types/sources from
    *source* into *target* (the concept being kept for a duplicate label)."""
    for ident in source.identifiers or []:
        if target.identifiers is None:
            target.identifiers = []
        exists = any(
            hasattr(i, "identifier") and i.identifier == ident.identifier
            for i in target.identifiers
        )
        if not exists:
            target.identifiers.append(ident)

    for d in source.definitions or []:
        if target.definitions is None:
            target.definitions = []
        if d not in target.definitions:
            target.definitions.append(d)

    for s in source.synonyms or []:
        if target.synonyms is None:
            target.synonyms = []
        if s.lower() not in [x.lower() for x in target.synonyms]:
            target.synonyms.append(s)

    for st in source.semantic_types or []:
        if target.semantic_types is None:
            target.semantic_types = []
        if str(st) not in [str(x) for x in target.semantic_types]:
            target.semantic_types.append(st)

    for src in source.sources or []:
        if target.sources is None:
            target.sources = []
        if str(src) not in [str(x) for x in target.sources]:
            target.sources.append(src)


async def expand_and_search(
    lookup: CentralKnowledgeLookup,
    query: str,
    *,
    concept_types: list[ConceptType] | None = None,
    sources: list[KnowledgeSource] | None = None,
    max_results: int = 50,
    max_rounds: int = 3,
    max_terms_per_round: int = 10,
    abbreviation_sources: list[AbbreviationSource] | None = None,
    store: ExpansionStore | None = None,
    persist: bool = True,
) -> tuple[LookupResult, ExpansionTrace]:
    """Search *query*, then iteratively expand via synonyms and
    abbreviation/long-form matches discovered in the results so far.

    Round 0 searches *query* itself. Each subsequent round searches every
    new term discovered from the previous round's concepts (synonyms
    already on the concept, plus whatever *abbreviation_sources* offer for
    its label) that hasn't been tried yet, capped at *max_terms_per_round*.
    Stops when a round discovers no new terms (a fixed point — the
    expansion has converged) or *max_rounds* is reached, whichever first.

    Every term tried, which round it was tried in, and why (original /
    synonym / abbreviation / long-form, plus which concept produced it) is
    recorded via *store* (an :class:`ExpansionStore`, created automatically
    unless one is passed in) when *persist* is true — this is the durable
    record; the returned :class:`ExpansionTrace` is a lightweight summary
    of the same run for callers that don't want to query the store.

    Parameters mirror :meth:`CentralKnowledgeLookup.search_concepts` where
    they overlap (*concept_types*, *sources*, *max_results*).
    """
    from ..models import LookupResult

    if abbreviation_sources is None:
        abbreviation_sources = [UMLSAbbreviationSource(lookup.config)]

    if persist and store is None:
        store = ExpansionStore()
    run_id = store.start_run(query) if store else None

    tried: set[str] = set()
    term_origin: dict[str, tuple[str, str | None]] = {
        query.strip().lower(): (ORIGIN_ORIGINAL, None)
    }
    terms_by_round: list[list[str]] = []
    all_concepts: list[Any] = []
    exec_time_total = 0.0
    sources_succeeded: set[str] = set()
    sources_failed: set[str] = set()
    errors: dict[str, str] = {}

    round_terms = [query]
    round_num = 0
    stop_reason = STOP_MAX_ROUNDS

    while round_terms and round_num < max_rounds:

        async def _search(term: str) -> Any:
            return await lookup.search_concepts(
                term,
                concept_types=concept_types,
                sources=sources,
                max_results=max_results,
            )

        results = await asyncio.gather(*[_search(t) for t in round_terms], return_exceptions=True)

        terms_by_round.append(list(round_terms))
        if store and run_id is not None:
            store.record_terms(
                run_id,
                round_num,
                [
                    (t, *term_origin.get(t.strip().lower(), (ORIGIN_ORIGINAL, None)))
                    for t in round_terms
                ],
            )

        for term in round_terms:
            tried.add(term.strip().lower())

        for term, result in zip(round_terms, results, strict=True):
            if isinstance(result, BaseException):
                errors[f"expand_{term}"] = str(result)
                logger.debug("expand_and_search: search failed for %r: %s", term, result)
                continue
            exec_time_total += result.execution_time or 0.0
            for s in result.sources_succeeded or []:
                sources_succeeded.add(str(s))
            for s in result.sources_failed or []:
                sources_failed.add(str(s))
            merge_concept_results(all_concepts, result.concepts or [])

        # Harvest next round's candidate terms from everything found so far.
        next_terms: dict[str, tuple[str, str, str | None]] = {}
        for concept in all_concepts:
            concept_id = getattr(concept, "primary_id", None)
            for syn in concept.synonyms or []:
                syn = (syn or "").strip()
                key = syn.lower()
                if syn and key not in tried and key not in next_terms:
                    next_terms[key] = (syn, ORIGIN_SYNONYM, concept_id)

            label = (concept.primary_label or "").strip()
            if not label:
                continue
            for source in abbreviation_sources:
                try:
                    pairs = await source.expand(label)
                except Exception as exc:  # noqa: BLE001 - one bad source shouldn't stop expansion
                    logger.debug(
                        "expand_and_search: abbreviation source failed for %r: %s", label, exc
                    )
                    pairs = []
                for candidate, origin in pairs:
                    candidate = candidate.strip()
                    key = candidate.lower()
                    if candidate and key not in tried and key not in next_terms:
                        next_terms[key] = (candidate, origin, concept_id)

        if not next_terms:
            stop_reason = STOP_FIXED_POINT
            break

        capped = list(next_terms.values())[:max_terms_per_round]
        for term, origin, concept_id in capped:
            term_origin[term.lower()] = (origin, concept_id)
        round_terms = [t for t, _, _ in capped]
        round_num += 1

    if store and run_id is not None:
        store.finish_run(run_id, rounds_run=len(terms_by_round), stop_reason=stop_reason)

    merged = LookupResult(query=query, sources_queried=sources or list(lookup.adapters.keys()))
    merged.concepts = all_concepts
    merged.total_found = len(all_concepts)
    merged.execution_time = exec_time_total
    for src_name in sources_succeeded:
        from ..models import KnowledgeSource

        merged.add_concepts([], KnowledgeSource(src_name.upper()))
    for src_name in sources_failed:
        merged.add_error(src_name, "Source failed for some expanded terms")
    for err_key, err_msg in errors.items():
        merged.add_error(err_key, err_msg)

    trace = ExpansionTrace(
        run_id=run_id,
        rounds_run=len(terms_by_round),
        stop_reason=stop_reason,
        terms_by_round=terms_by_round,
    )
    return merged, trace
