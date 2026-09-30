"""
Iterative term expansion: synonyms + abbreviation/long-form discovery.

``expand_and_search`` takes a single search term and, instead of searching
it once, searches it, harvests synonyms and abbreviation/long-form variants
from what it finds (e.g. "COPD" -> "chronic obstructive pulmonary disease"),
searches the long-form/synonym variants too, and repeats — stopping when a
round finds no genuinely new *searchable* terms, or a round cap is hit.
Discovered abbreviations (e.g. "chronic obstructive pulmonary disease" ->
"COPD") are recorded but deliberately never searched: a bare abbreviation is
short and often overloaded across unrelated domains (searching "PEM" is as
likely to surface "pemphigoid" as "post-exertional malaise"), so feeding one
back into a search risks dragging the whole expansion off-topic. Every term
tried — and every abbreviation found but not searched — is recorded durably
via :class:`~knowledge_lookup.core.expansion_store.ExpansionStore`.

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
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from .expansion_store import (
    ORIGIN_ABBREVIATION,
    ORIGIN_LONG_FORM,
    ORIGIN_ORIGINAL,
    ORIGIN_RELATIONSHIP,
    ORIGIN_SYNONYM,
    STOP_FIXED_POINT,
    STOP_MAX_ROUNDS,
    ExpansionStore,
)
from .source_routing import options_for_concept_type, route_sources

if TYPE_CHECKING:
    from ..models import ConceptType, KnowledgeSource, LookupConfig, LookupResult
    from .central_lookup import CentralKnowledgeLookup

logger = logging.getLogger(__name__)


def _as_concept_type(value: object) -> ConceptType | None:
    """Best-effort coerce a concept's ``concept_type`` (enum member or raw
    string after model regen) to a :class:`ConceptType`, or ``None`` when it
    is empty/unrecognised — routing then treats the term as unclassified."""
    from ..models import ConceptType

    if value is None or value == "":
        return None
    if isinstance(value, ConceptType):
        return value
    try:
        return ConceptType(str(value).upper())
    except ValueError:
        return None


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
class RelatedTerm:
    """One relationship target harvested from a concept.

    ``term`` is a human-readable name that can be fed back into a later
    search round (empty when the source only yields an accession, e.g. KEGG's
    ``link`` output); ``concept_type`` is the inferred type of the *target* so
    routing can send it to the right sources; the remaining fields describe the
    edge itself and are persisted verbatim.
    """

    term: str
    concept_type: ConceptType | None
    relation_label: str
    related_id: str
    source: str | None = None


class RelationshipSource(Protocol):
    """A pluggable source of relationship edges for a concept.

    Mirrors :class:`AbbreviationSource`: implementations must never raise for
    a "no data" case — return ``[]`` — so a missing extra/API key/network
    failure degrades to "no expansion from this source" rather than aborting
    the whole search. Takes the whole *concept* (not just a label) because
    relationship lookups are keyed by the concept's identifier.
    """

    async def expand(self, concept: Any) -> list[RelatedTerm]:
        """Return :class:`RelatedTerm` edges discovered for *concept*."""
        ...


def _infer_related_concept_type(
    rel: dict[str, Any], source_ct: ConceptType | None
) -> ConceptType | None:
    """Infer the :class:`ConceptType` of a relationship *target*.

    Uses the relation label and target source hint first (KEGG's gene<->pathway
    links carry an unambiguous ``source``/``relation_label``), then falls back
    to the source concept's own type (a reasonable default for ontological
    relations such as UMLS parent/child).
    """
    from ..models import ConceptType

    label = (rel.get("relation_label") or "").lower()
    hint = (rel.get("source") or "").upper()
    if "pathway" in label or "PATHWAY" in hint:
        return ConceptType.PATHWAY
    if "gene" in label or hint.endswith("_GENE"):
        return ConceptType.GENE
    if "interaction" in label or "protein" in label or hint == "STRING":
        return ConceptType.PROTEIN
    if "phenotype" in label:
        return ConceptType.PHENOTYPE
    if "disease" in label:
        return ConceptType.DISEASE
    if "drug" in label or "molecule" in label:
        return ConceptType.DRUG
    if "chemical" in label or "compound" in label:
        return ConceptType.CHEMICAL
    return source_ct


#: Relation labels expressing a *taxonomic* (is-a / subclass) link between a
#: broader class and a narrower member of that class — a "cytokine"->"interleukin
#: 6" class/member edge. OLS contributes ``has_narrower``/``has_broader``;
#: UMLS semantic relations contribute the parent/child and tree-number labels.
TAXONOMIC_RELATION_LABELS: frozenset[str] = frozenset(
    {
        "has_narrower",
        "has_broader",
        "narrower",
        "broader",
        "narrower_than",
        "broader_than",
        "narrower_term",
        "wider",
        "parent",
        "child",
        "parents",
        "children",
        "has_parent",
        "has_child",
        "parent_tree_number",
        "child_tree_number",
        "isa",
        "is_a",
        "subclass_of",
        "superclass_of",
        "has_subclass",
        "has_superclass",
    }
)

#: Relation labels expressing an *associative* link — a gene's pathway, a
#: protein's interaction partner, a disease's associated gene — i.e. a
#: co-occurrence edge rather than a class/member one.
ASSOCIATIVE_RELATION_LABELS: frozenset[str] = frozenset(
    {
        "interaction",
        "interacts_with",
        "partner",
        "pathway",
        "has_pathway",
        "has_gene",
        "gene",
        "associated_with",
        "association",
        "disease",
        "target",
        "enzyme",
        "compound",
        "membership",
        "member",
    }
)


def is_taxonomic_relation(relation_label: str | None) -> bool:
    """Whether *relation_label* denotes a class<->member (is-a) edge rather
    than an associative one."""
    return (relation_label or "").strip().lower() in TAXONOMIC_RELATION_LABELS


def _native_id_for_source(concept: Any, source: Any) -> str | None:
    """Return the identifier on *concept* that *source* keys on, if any.

    Searches ``concept.identifiers`` for one whose ``source`` matches and, when
    several exist (e.g. OLS stores both an IRI and a short form), prefers a
    URL-shaped one — ontology/hierarchy adapters resolve IRIs, whereas gene-
    and CUI-keyed adapters store a single id so the preference is a no-op for
    them. Returns ``None`` when the concept carries no identifier for *source*.
    """
    candidates = [
        str(ident.identifier)
        for ident in (getattr(concept, "identifiers", None) or [])
        if getattr(ident, "source", None) == source and getattr(ident, "identifier", None)
    ]
    for cand in candidates:
        if cand.startswith("http"):
            return cand
    return candidates[0] if candidates else None


def _hierarchy_edges_from_concept(
    concept: Any, source_ct: ConceptType | None
) -> list[RelatedTerm]:
    """Turn a concept's pre-resolved ``children``/``parents`` label lists into
    :class:`RelatedTerm` edges (skipping blanks and bare IRIs we cannot name)."""
    edges: list[RelatedTerm] = []
    for attr, label in (("children", "has_narrower"), ("parents", "has_broader")):
        for value in getattr(concept, attr, None) or []:
            name = (str(value) or "").strip()
            if not name or name.startswith("http"):
                continue
            edges.append(
                RelatedTerm(
                    term=name,
                    concept_type=source_ct,
                    relation_label=label,
                    related_id=name,
                    source="OLS",
                )
            )
    return edges


class AdapterRelationshipSource:
    """Harvest relationship edges by delegating to a concept's own adapter.

    For each concept, looks up the adapter(s) named in its ``sources`` and, for
    any that implement a ``get_relationships(concept_id)`` method (currently
    KEGG's gene<->pathway ``link``, UMLS semantic relations, STRING's
    interaction partners, DisGeNET disease->gene associations and Open Targets
    target<->disease associations), calls it with the concept's primary id and
    normalises the returned dicts into :class:`RelatedTerm`. Adapters without
    the method, or a concept with no matching adapter, contribute nothing. All
    failures degrade to ``[]`` — this never raises.
    """

    def __init__(
        self,
        lookup: CentralKnowledgeLookup,
        limit_per_concept: int = 10,
        relation_labels: set[str] | None = None,
        allowed_sources: set[Any] | None = None,
    ) -> None:
        self._lookup = lookup
        self._limit_per_concept = limit_per_concept
        # When set, keep only edges whose relation_label is in this set
        # (lower-cased). None keeps every edge.
        self._relation_labels = (
            {label.lower() for label in relation_labels} if relation_labels is not None else None
        )
        # When set, only *call* adapters whose source is in this set. This avoids
        # firing (and paying for / erroring on) adapters that cannot contribute
        # the requested edge type — e.g. hierarchy-only expansion need not query
        # STRING/KEGG/Open Targets at all. None calls every available adapter.
        self._allowed_sources = set(allowed_sources) if allowed_sources is not None else None

    async def expand(self, concept: Any) -> list[RelatedTerm]:
        from ..models import KnowledgeSource

        primary_id = getattr(concept, "primary_id", None)
        source_ct = _as_concept_type(getattr(concept, "concept_type", None))

        sources = getattr(concept, "sources", None) or []
        targets: list[KnowledgeSource] = []
        for s in sources:
            try:
                targets.append(s if isinstance(s, KnowledgeSource) else KnowledgeSource(str(s)))
            except ValueError:
                continue

        results: list[RelatedTerm] = []
        for source in targets:
            if self._allowed_sources is not None and source not in self._allowed_sources:
                continue
            adapter = self._lookup.adapters.get(source)
            get_relationships = getattr(adapter, "get_relationships", None)
            if get_relationships is None:
                continue
            # Query the adapter with the identifier *it* understands, not the
            # merged concept's primary id: a merged concept's ``primary_id`` is
            # whichever source happened to win the merge (e.g. a SNOMED URI),
            # while STRING keys on a gene symbol, UMLS on a CUI and OLS on an
            # IRI. Resolve a native id from ``concept.identifiers`` for this
            # source and fall back to ``primary_id`` only when none is present.
            native_id = _native_id_for_source(concept, source) or primary_id
            if not native_id:
                continue
            try:
                rels = await get_relationships(native_id)
            except Exception as exc:  # noqa: BLE001 - best-effort, never abort the caller
                logger.debug(
                    "AdapterRelationshipSource: get_relationships failed for %s (%s): %s",
                    native_id,
                    source,
                    exc,
                )
                continue
            for rel in (rels or [])[: self._limit_per_concept]:
                related_id = str(rel.get("related_id") or "").strip()
                if not related_id:
                    continue
                results.append(
                    RelatedTerm(
                        term=(rel.get("related_name") or "").strip(),
                        concept_type=_infer_related_concept_type(rel, source_ct),
                        relation_label=rel.get("relation_label") or "",
                        related_id=related_id,
                        source=rel.get("source"),
                    )
                )

        # Ontology adapters that already resolved a hierarchy populate
        # ``children``/``parents`` (a list of labels) on the concept itself;
        # harvest those as edges too so a hierarchy obtained during a detail
        # lookup expands even without a second ``get_relationships`` call.
        results.extend(_hierarchy_edges_from_concept(concept, source_ct))
        if self._relation_labels is not None:
            results = [
                r
                for r in results
                if (r.relation_label or "").strip().lower() in self._relation_labels
            ]
        return results


def hierarchy_relationship_sources(
    lookup: CentralKnowledgeLookup,
) -> list[RelationshipSource]:
    """Relationship sources restricted to *taxonomic* class<->member edges — OLS
    narrower/broader and UMLS parent/child — dropping associative links such as
    STRING interaction partners or KEGG gene/pathway memberships. Used for a
    hierarchy-only expansion (a class term surfacing its members and super/sub
    classes) as opposed to the full associative network."""
    from ..models import KnowledgeSource

    return [
        AdapterRelationshipSource(
            lookup,
            relation_labels=set(TAXONOMIC_RELATION_LABELS),
            allowed_sources={KnowledgeSource.OLS, KnowledgeSource.UMLS},
        )
    ]


def associative_relationship_sources(
    lookup: CentralKnowledgeLookup,
) -> list[RelationshipSource]:
    """Relationship sources restricted to *associative* edges (interactions,
    pathway memberships, disease/gene associations), dropping taxonomic
    class/member edges. The complement of :func:`hierarchy_relationship_sources`."""
    from ..models import KnowledgeSource

    return [
        AdapterRelationshipSource(
            lookup,
            relation_labels=set(ASSOCIATIVE_RELATION_LABELS),
            allowed_sources={
                KnowledgeSource.STRING,
                KnowledgeSource.KEGG,
                KnowledgeSource.WIKIPATHWAYS,
                KnowledgeSource.DISGENET,
                KnowledgeSource.OPENTARGETS,
            },
        )
    ]


def default_relationship_sources(
    lookup: CentralKnowledgeLookup,
) -> list[RelationshipSource]:
    """The default relationship sources: KEGG/UMLS/STRING/DisGeNET/Open Targets via their adapters."""
    return [AdapterRelationshipSource(lookup)]


@dataclass
class ExpansionTrace:
    """A summary of one :func:`expand_and_search` call, for callers that
    want the trail without querying :class:`ExpansionStore` directly."""

    run_id: int | None
    rounds_run: int
    stop_reason: str
    terms_by_round: list[list[str]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)

    @property
    def all_terms_tried(self) -> list[str]:
        return [t for round_terms in self.terms_by_round for t in round_terms]


def _concrete_concept_type(concept: Any) -> str | None:
    """Return *concept*'s concept type as an upper-cased string, or ``None``
    when it is unset or the placeholder ``UNKNOWN``."""
    ct = getattr(concept, "concept_type", None)
    value = getattr(ct, "value", ct)
    if value is None:
        return None
    text = str(value).upper()
    return None if text == "UNKNOWN" else text


def _same_concept_type(a: Any, b: Any) -> bool:
    """Whether two same-label concepts describe the same kind of thing, so they
    are safe to merge. Concepts whose type is unset/UNKNOWN merge with anything;
    two concepts with *different* concrete types (e.g. a physical entity vs a
    physiological process sharing a label) are treated as homonyms."""
    ta = _concrete_concept_type(a)
    tb = _concrete_concept_type(b)
    if ta is None or tb is None:
        return True
    return ta == tb


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
                (
                    ec
                    for ec in target
                    if (ec.primary_label or "").lower().strip() == label
                    and _same_concept_type(ec, c)
                ),
                None,
            )
            if existing is not None:
                merge_concept_fields(existing, c)
            else:
                # Same label, different concrete concept type: a homonym (e.g. a
                # physical entity vs a process). Keep both rather than merging
                # two unrelated meanings into one concept.
                target.append(c)


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

    # Preserve a concrete concept type across the merge: a concept that came
    # back as UNKNOWN (common for merged ontology terms) adopts the other's
    # concrete type so downstream typing and routing are not lost.
    if _concrete_concept_type(target) is None:
        source_ct = _concrete_concept_type(source)
        if source_ct is not None:
            target.concept_type = source.concept_type


#: Default number of concept labels the abbreviation sources are asked about in
#: one expansion round. Labels are taken in result order; the rest wait for a
#: later round.
DEFAULT_MAX_ABBREVIATION_LOOKUPS = 10

#: Abbreviation-source calls running at the same time.
ABBREVIATION_LOOKUP_CONCURRENCY = 3


def _unasked_labels(concepts: list[Any], answers: dict[str, list[tuple[str, str]]]) -> list[str]:
    """Distinct non-empty labels of *concepts*, in order, that have no entry in *answers*."""
    labels: list[str] = []
    for concept in concepts:
        label = (concept.primary_label or "").strip()
        if label and label not in answers and label not in labels:
            labels.append(label)
    return labels


async def _ask_abbreviation_sources(
    sources: list[AbbreviationSource],
    labels: list[str],
    answers: dict[str, list[tuple[str, str]]],
) -> None:
    """Ask every source about each of *labels* and store the pairs in *answers*.

    At most :data:`ABBREVIATION_LOOKUP_CONCURRENCY` calls run at a time. Pairs
    keep label and source order; a failing source contributes no pairs.
    """
    semaphore = asyncio.Semaphore(ABBREVIATION_LOOKUP_CONCURRENCY)

    async def _ask(source: AbbreviationSource, label: str) -> list[tuple[str, str]]:
        async with semaphore:
            try:
                return list(await source.expand(label))
            except Exception as exc:  # noqa: BLE001 - one bad source shouldn't stop expansion
                logger.debug(
                    "expand_and_search: abbreviation source failed for %r: %s", label, exc
                )
                return []

    calls = [(label, source) for label in labels for source in sources]
    results = await asyncio.gather(*(_ask(source, label) for label, source in calls))
    for label in labels:
        answers.setdefault(label, [])
    for (label, _source), pairs in zip(calls, results, strict=True):
        answers[label].extend(pairs)


#: Default number of concepts the relationship sources are asked about in one
#: expansion round. Concepts are taken in result order; the rest wait for a
#: later round. Relationship calls are the most expensive part of expansion
#: (a network round-trip per concept per relationship-capable adapter), so this
#: is deliberately modest and only active when relationship sources are passed.
DEFAULT_MAX_RELATIONSHIP_CONCEPTS = 10

#: Relationship-source calls running at the same time.
RELATIONSHIP_LOOKUP_CONCURRENCY = 3


def _unqueried_relationship_concepts(
    concepts: list[Any], answers: dict[str, list[RelatedTerm]]
) -> list[Any]:
    """Distinct concepts (by ``primary_id``) not yet asked about, in order."""
    out: list[Any] = []
    seen: set[str] = set()
    for concept in concepts:
        pid = getattr(concept, "primary_id", None)
        if pid and pid not in answers and pid not in seen:
            seen.add(pid)
            out.append(concept)
    return out


async def _ask_relationship_sources(
    sources: list[RelationshipSource],
    concepts: list[Any],
    answers: dict[str, list[RelatedTerm]],
) -> None:
    """Ask every relationship source about each of *concepts*.

    At most :data:`RELATIONSHIP_LOOKUP_CONCURRENCY` calls run at a time; a
    failing source contributes nothing. Results are stored in *answers* keyed by
    the concept's ``primary_id``.
    """
    semaphore = asyncio.Semaphore(RELATIONSHIP_LOOKUP_CONCURRENCY)

    async def _ask(source: RelationshipSource, concept: Any) -> list[RelatedTerm]:
        async with semaphore:
            try:
                return list(await source.expand(concept))
            except Exception as exc:  # noqa: BLE001 - one bad source shouldn't stop expansion
                logger.debug(
                    "expand_and_search: relationship source failed for %r: %s",
                    getattr(concept, "primary_id", None),
                    exc,
                )
                return []

    calls = [(concept, source) for concept in concepts for source in sources]
    results = await asyncio.gather(*(_ask(source, concept) for concept, source in calls))
    for concept in concepts:
        answers.setdefault(getattr(concept, "primary_id", ""), [])
    for (concept, _source), rels in zip(calls, results, strict=True):
        answers[getattr(concept, "primary_id", "")].extend(rels)


_EXPANSION_STOPWORDS = frozenset(
    {
        "the",
        "of",
        "and",
        "a",
        "an",
        "to",
        "in",
        "for",
        "on",
        "or",
        "is",
        "with",
        "by",
        "from",
        "at",
        "as",
        "that",
        "this",
        "its",
        "via",
        "not",
    }
)


def _normalize_term(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (text or "").lower())).strip()


def _expansion_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(tok) > 2 and tok not in _EXPANSION_STOPWORDS
    }


def relevance_rank(
    concepts: list[Any],
    query: str,
    terms_by_round: list[list[str]],
    member_ids: set[str] | None = None,
    member_labels: set[str] | None = None,
) -> list[Any]:
    """Order expanded concepts by relevance to what the search actually used.

    Concepts are bucketed into tiers, earliest first: (1) the concept that equals
    the query, (2) concepts reached through a harvested relationship edge — the
    class->members a hierarchy search surfaces (e.g. interleukins for a "cytokine"
    query), which carry no token overlap with the class name yet are the whole
    point of the expansion, (3) concepts equal to one of the searched terms
    (synonyms, long forms), and (4) everything else ordered by how much of their
    label is covered by the tokens of the query and searched terms. Loose full-text
    matches (for example "Cancer Survivors" for a "cancer" query) sink to the
    bottom. Nothing is dropped and ties keep their original order, so
    ``--limit``/``max_results`` truncate the noisiest results instead of the most
    relevant members.
    """
    if len(concepts) < 2:
        return concepts
    anchors: set[str] = set()
    exact: set[str] = set()
    for text in [query, *(t for round_terms in terms_by_round for t in round_terms)]:
        anchors |= _expansion_tokens(text)
        normalized = _normalize_term(text)
        if normalized:
            exact.add(normalized)
    if not anchors:
        return concepts
    member_ids = member_ids or set()
    member_labels = member_labels or set()
    query_norm = _normalize_term(query)

    def rank_key(item: tuple[int, Any]) -> tuple[int, int, int, float, int]:
        index, concept = item
        label = str(getattr(concept, "primary_label", "") or "").strip().lower()
        normalized = _normalize_term(label)
        pid = str(getattr(concept, "primary_id", "") or "").strip()
        tokens = _expansion_tokens(label)
        coverage = (len(tokens & anchors) / len(tokens)) if tokens else 0.0
        query_tier = 0 if normalized and normalized == query_norm else 1
        member_tier = 0 if (normalized in member_labels or pid in member_ids) else 1
        exact_tier = 0 if normalized in exact else 1
        return (query_tier, member_tier, exact_tier, -coverage, index)

    return [concept for _, concept in sorted(enumerate(concepts), key=rank_key)]


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
    max_abbreviation_lookups: int = DEFAULT_MAX_ABBREVIATION_LOOKUPS,
    relationship_sources: list[RelationshipSource] | None = None,
    max_relationship_concepts: int = DEFAULT_MAX_RELATIONSHIP_CONCEPTS,
    store: ExpansionStore | None = None,
    persist: bool = True,
    route: bool = True,
) -> tuple[LookupResult, ExpansionTrace]:
    """Search *query*, then iteratively expand via synonyms and
    long-form matches discovered in the results so far.

    Round 0 searches *query* itself. Each subsequent round searches every
    new synonym/long-form term discovered from the previous round's concepts
    that hasn't been tried yet, capped at *max_terms_per_round*. Stops when
    a round discovers no new searchable terms (a fixed point — the
    expansion has converged) or *max_rounds* is reached, whichever first.

    Abbreviations offered by *abbreviation_sources* (candidates with origin
    ``ORIGIN_ABBREVIATION``) are recorded but never searched — see the
    module docstring for why. Only long-form candidates
    (``ORIGIN_LONG_FORM``) from an abbreviation source feed back into
    searching, the same as harvested synonyms.

    Every term tried — plus every abbreviation found but not searched —
    which round it was found in, and why (original / synonym / abbreviation
    / long-form, plus which concept produced it) is recorded via *store*
    (an :class:`ExpansionStore`, created automatically unless one is passed
    in) when *persist* is true — this is the durable record; the returned
    :class:`ExpansionTrace` is a lightweight summary of the same run for
    callers that don't want to query the store.

    Parameters mirror :meth:`CentralKnowledgeLookup.search_concepts` where
    they overlap (*concept_types*, *sources*, *max_results*).

    Abbreviation sources are asked about each concept label at most once per
    call, and about at most *max_abbreviation_lookups* not-yet-asked labels per
    round (in result order), with up to :data:`ABBREVIATION_LOOKUP_CONCURRENCY`
    calls at a time. Answers are reused in later rounds.

    When *relationship_sources* is provided (it is ``None`` — i.e. off — by
    default, so released behaviour is unchanged), each not-yet-asked concept is
    queried for relationship edges and the *named* targets (e.g. a gene's
    pathways, a protein's interaction partners, a disease's parent/child terms)
    are fed back into later rounds as new search terms with origin
    ``ORIGIN_RELATIONSHIP``, growing a real relationship network rather than
    just a synonym set. Edges without a searchable name (e.g. KEGG's bare
    accessions) are still recorded in *store* but never searched. At most
    *max_relationship_concepts* not-yet-asked concepts are queried per round,
    with up to :data:`RELATIONSHIP_LOOKUP_CONCURRENCY` calls at a time; every
    edge is written to *store* and summarised in the returned trace. Pass
    :func:`default_relationship_sources` to enable the KEGG/UMLS/STRING
    relationship adapters.
    """
    from ..models import LookupResult

    # label -> (candidate, origin) pairs from the abbreviation sources
    abbreviation_answers: dict[str, list[tuple[str, str]]] = {}

    # primary_id -> harvested relationship edges (RelatedTerm) for concepts the
    # relationship sources have already been asked about this run.
    relationship_answers: dict[str, list[RelatedTerm]] = {}
    all_relationship_edges: list[dict[str, Any]] = []

    if abbreviation_sources is None:
        abbreviation_sources = [UMLSAbbreviationSource(lookup.config)]

    if persist and store is None:
        store = ExpansionStore()
    run_id = store.start_run(query) if store else None

    tried: set[str] = set()
    term_origin: dict[str, tuple[str, str | None]] = {
        query.strip().lower(): (ORIGIN_ORIGINAL, None)
    }

    # Source-aware routing: send each term only to the sources suited to its
    # concept type. Only narrows an *unpinned* fan-out — a caller that passed
    # an explicit ``sources`` list keeps full control, so routing stands down.
    # The seed's type is only knowable when exactly one was requested.
    available_sources = list(lookup.adapters.keys())
    apply_routing = route and sources is None
    seed_type = concept_types[0] if concept_types and len(concept_types) == 1 else None
    term_type: dict[str, ConceptType | None] = {query.strip().lower(): seed_type}

    terms_by_round: list[list[str]] = []
    all_concepts: list[Any] = []
    exec_time_total = 0.0
    sources_succeeded: set[str] = set()
    sources_failed: set[str] = set()
    errors: dict[str, str] = {}
    member_ids: set[str] = set()
    member_labels: set[str] = set()

    round_terms = [query]
    round_num = 0
    stop_reason = STOP_MAX_ROUNDS

    while round_terms and round_num < max_rounds:

        async def _search(term: str) -> Any:
            term_sources: list[KnowledgeSource] | None
            term_options: dict[KnowledgeSource, dict[str, Any]] | None
            if apply_routing:
                ct = term_type.get(term.strip().lower())
                term_sources = route_sources(ct, available_sources)
                term_options = options_for_concept_type(ct)
            else:
                term_sources = sources
                term_options = None
            return await lookup.search_concepts(
                term,
                concept_types=concept_types,
                sources=term_sources,
                max_results=max_results,
                source_options=term_options,
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
            concepts = result.concepts or []
            merge_concept_results(all_concepts, concepts)
            origin = term_origin.get(term.strip().lower(), (ORIGIN_ORIGINAL, None))[0]
            if origin == ORIGIN_RELATIONSHIP:
                for concept in concepts:
                    pid = str(getattr(concept, "primary_id", "") or "").strip()
                    if pid:
                        member_ids.add(pid)
                    normalized = _normalize_term(getattr(concept, "primary_label", "") or "")
                    if normalized:
                        member_labels.add(normalized)

        # Harvest next round's candidate terms from everything found so far.
        # Abbreviations are recorded but never searched: a bare abbreviation
        # is short and often overloaded across unrelated domains (e.g. "PEM"
        # matches "pemphigoid" just as readily as "post-exertional malaise"),
        # so feeding one back into a search risks dragging the whole
        # expansion off-topic. Long-form/synonym candidates don't carry that
        # risk to nearly the same degree and are searched as before.
        next_terms: dict[str, tuple[str, str, str | None, ConceptType | None]] = {}
        abbreviations_found: dict[str, tuple[str, str, str | None]] = {}

        # Ask the abbreviation sources about concept labels not asked yet in this
        # run: at most max_abbreviation_lookups labels per round (in result
        # order), a few at a time. Answers are kept for later rounds.
        if abbreviation_sources:
            labels_to_ask = _unasked_labels(all_concepts, abbreviation_answers)
            await _ask_abbreviation_sources(
                abbreviation_sources,
                labels_to_ask[: max(0, max_abbreviation_lookups)],
                abbreviation_answers,
            )

        # Reserve part of the capped round for relationship targets. When
        # relationship sources are active, synonyms are held to the complement
        # so a synonym-rich round can no longer leave zero slots for
        # relationship edges (which is what stopped a class term like
        # "cytokine" from ever searching the members its relations pointed to).
        rel_reserve = max(1, max_terms_per_round // 2) if relationship_sources else 0
        synonym_cap = max(1, max_terms_per_round - rel_reserve)

        for concept in all_concepts:
            concept_id = getattr(concept, "primary_id", None)
            concept_ct = _as_concept_type(getattr(concept, "concept_type", None))
            for syn in concept.synonyms or []:
                syn = (syn or "").strip()
                key = syn.lower()
                if (
                    syn
                    and key not in tried
                    and key not in next_terms
                    and len(next_terms) < synonym_cap
                ):
                    next_terms[key] = (syn, ORIGIN_SYNONYM, concept_id, concept_ct)

            label = (concept.primary_label or "").strip()
            if not label:
                continue
            for candidate, origin in abbreviation_answers.get(label, []):
                candidate = candidate.strip()
                key = candidate.lower()
                if not candidate or key in tried:
                    continue
                if origin == ORIGIN_ABBREVIATION:
                    if key not in abbreviations_found:
                        abbreviations_found[key] = (candidate, origin, concept_id)
                elif key not in next_terms and len(next_terms) < synonym_cap:
                    next_terms[key] = (candidate, origin, concept_id, concept_ct)

        if abbreviations_found:
            for key in abbreviations_found:
                tried.add(key)
            if store and run_id is not None:
                store.record_terms(run_id, round_num + 1, list(abbreviations_found.values()))

        # Harvest relationship edges from concepts not yet asked about. Named
        # targets become next-round search terms (origin relationship), so the
        # run grows a real network instead of only a synonym set; every edge is
        # recorded whether or not its target is searchable. Targets are
        # collected first and ranked, then fill the round's reserved slots:
        # edges whose target carries a type *different* from its source concept
        # (a class->member or gene->protein link) are the informative ones and
        # outrank same-type siblings.
        relationship_records: list[dict[str, Any]] = []
        if relationship_sources:
            to_ask = _unqueried_relationship_concepts(all_concepts, relationship_answers)
            asked = to_ask[: max(0, max_relationship_concepts)]
            if asked:
                await _ask_relationship_sources(relationship_sources, asked, relationship_answers)
            ranked: list[tuple[int, str, str, str, ConceptType | None, dict[str, Any]]] = []
            for concept in asked:
                pid = getattr(concept, "primary_id", "") or ""
                if not pid:
                    continue
                src_label = (getattr(concept, "primary_label", "") or "").strip()
                src_ct = _as_concept_type(getattr(concept, "concept_type", None))
                for edge in relationship_answers.get(pid, []):
                    name = edge.term.strip()
                    key = name.lower()
                    record: dict[str, Any] = {
                        "source_concept_id": pid,
                        "source_concept_label": src_label,
                        "relation_label": edge.relation_label,
                        "related_id": edge.related_id,
                        "related_name": name or None,
                        "related_source": edge.source,
                        "concept_type": getattr(edge.concept_type, "value", edge.concept_type),
                        "searched": False,
                    }
                    relationship_records.append(record)
                    if not name or key in tried or key in next_terms:
                        continue
                    if edge.concept_type is None:
                        rank = 2
                    elif edge.concept_type != src_ct:
                        rank = 0
                    else:
                        rank = 1
                    ranked.append((rank, key, name, pid, edge.concept_type, record))
            ranked.sort(key=lambda item: item[0])
            for _rank, key, name, pid, ct, record in ranked:
                if len(next_terms) >= max_terms_per_round:
                    break
                if key in next_terms:
                    continue
                next_terms[key] = (name, ORIGIN_RELATIONSHIP, pid, ct)
                record["searched"] = True
            if store and run_id is not None:
                store.record_relationship_edges(run_id, round_num, relationship_records)
            all_relationship_edges.extend(relationship_records)

        if not next_terms:
            stop_reason = STOP_FIXED_POINT
            break

        capped = list(next_terms.values())[:max_terms_per_round]
        for term, origin, concept_id, ct in capped:
            term_origin[term.lower()] = (origin, concept_id)
            term_type[term.lower()] = ct
        round_terms = [t for t, _, _, _ in capped]
        round_num += 1

    if store and run_id is not None:
        store.finish_run(run_id, rounds_run=len(terms_by_round), stop_reason=stop_reason)

    all_concepts = relevance_rank(all_concepts, query, terms_by_round, member_ids, member_labels)
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
        relationships=all_relationship_edges,
    )
    return merged, trace
