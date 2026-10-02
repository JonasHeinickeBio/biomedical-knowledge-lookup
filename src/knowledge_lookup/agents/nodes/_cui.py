"""Choosing and ordering a concept's UMLS CUI.

A concept can carry several UMLS identifiers: its own record when it was found in
UMLS, the hit a label search in UMLS returned, and the many CUIs that OLS,
BioPortal or Wikidata cross-references list for loosely related concepts. Every
node that reports "the" CUI takes the *first* UMLS identifier, so what matters is
which one comes first — and that it does not depend on set or dict iteration
order, which changes from run to run.

:func:`rank_umls_identifiers` fixes the order once, where identifiers are added;
:func:`preferred_umls_cui` is the single reader.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...adapters.umls_adapter import normalize_cui
from ...models import ConceptIdentifier, KnowledgeSource


def _is_umls(source: Any) -> bool:
    return str(getattr(source, "value", source)).upper() == "UMLS"


def _field(ident: Any, name: str) -> Any:
    return ident.get(name) if isinstance(ident, dict) else getattr(ident, name, None)


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def preferred_umls_cui(identifiers: Iterable[Any] | None) -> str | None:
    """The bare CUI of the first UMLS identifier (objects or serialized dicts)."""
    for ident in identifiers or []:
        if _is_umls(_field(ident, "source")):
            cui = normalize_cui(str(_field(ident, "identifier") or ""))
            if cui:
                return cui
    return None


def rank_umls_identifiers(
    concept: Any, hit_cui: str | None = None, hit_label: str | None = None
) -> None:
    """Reorder *concept*'s UMLS identifiers so the most trustworthy comes first.

    Order of trust:

    1. an identifier labelled with the concept's own label — the concept's own
       UMLS record (it came from a UMLS search for that very name);
    2. *hit_cui*, the top UMLS hit for the concept's label (added with
       *hit_label* when the concept does not carry it yet);
    3. everything else, sorted by CUI so the result is the same on every run.

    Identifiers are stored as bare CUIs and de-duplicated; non-UMLS identifiers
    keep their order and precede the UMLS ones.
    """
    own_label = _norm(getattr(concept, "primary_label", None))
    others: list[Any] = []
    umls: dict[str, Any] = {}
    for ident in getattr(concept, "identifiers", None) or []:
        if not _is_umls(_field(ident, "source")):
            others.append(ident)
            continue
        cui = normalize_cui(str(_field(ident, "identifier") or ""))
        if not cui:
            continue
        ident.identifier = cui
        kept = umls.get(cui)
        # keep the copy whose label says more (the concept's own label wins)
        if kept is None or (
            _norm(getattr(ident, "label", None)) == own_label
            and _norm(getattr(kept, "label", None)) != own_label
        ):
            umls[cui] = ident

    hit = normalize_cui(hit_cui) if hit_cui else None
    if hit and hit not in umls:
        umls[hit] = ConceptIdentifier(
            source=KnowledgeSource.UMLS,
            identifier=hit,
            label=hit_label or None,
            url=f"https://uts.nlm.nih.gov/uts/umls/concept/{hit}",
        )

    def _rank(cui: str) -> tuple[int, int, str]:
        own = bool(own_label) and _norm(getattr(umls[cui], "label", None)) == own_label
        return (0 if own else 1, 0 if cui == hit else 1, cui)

    concept.identifiers = [*others, *(umls[c] for c in sorted(umls, key=_rank))]
