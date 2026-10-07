"""Helpers shared by the ClinGen and GenCC gene-disease validity adapters.

Both sources publish gene-disease validity classifications (Definitive ... Refuted) per
curator, keyed by HGNC gene and (mostly) MONDO disease. This module holds what they have in
common: the classification vocabulary with a strength ranking, a per-pair consensus summary
and identifier normalisation. Import-light on purpose (stdlib only).
"""

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

# Classification (lower-case, "evidence" suffix stripped) -> (rank, strength in [0, 1]).
# Higher rank = stronger support. ClinGen uses the first six plus "no known disease
# relationship"; GenCC adds "supportive" and "animal model only".
CLASSIFICATIONS: dict[str, tuple[int, float]] = {
    "definitive": (9, 1.0),
    "strong": (8, 0.85),
    "moderate": (7, 0.7),
    "supportive": (6, 0.55),
    "limited": (5, 0.4),
    "animal model only": (4, 0.25),
    "no known disease relationship": (3, 0.1),
    "disputed": (2, 0.05),
    "refuted": (1, 0.0),
}
_POSITIVE = {"definitive", "strong", "moderate", "supportive", "limited"}
_STRONG = {"definitive", "strong", "moderate"}
_CONTRADICTED = {"disputed", "refuted"}

_RELATIONS = {
    "animal model only": "animal_model_association_with",
    "no known disease relationship": "no_known_relationship_with",
    "disputed": "disputed_association_with",
    "refuted": "refuted_association_with",
}

MOI_LABELS = {
    "AD": "Autosomal dominant",
    "AR": "Autosomal recessive",
    "XL": "X-linked",
    "SD": "Semidominant",
    "MT": "Mitochondrial",
    "UD": "Undetermined",
}

_HGNC_RE = re.compile(r"^hgnc:\s*(\d+)$", re.IGNORECASE)
_MONDO_RE = re.compile(r"^mondo:\s*(\d+)$", re.IGNORECASE)
_DISEASE_PREFIXES = {
    "OMIM": "OMIM",
    "ORPHA": "ORPHA",
    "ORPHANET": "ORPHA",
    "DOID": "DOID",
    "MEDGEN": "MEDGEN",
    "MESH": "MESH",
}


def classification_key(label: str | None) -> str:
    """``"Disputed Evidence"`` -> ``"disputed"``; ``"Definitive"`` -> ``"definitive"``."""
    key = (label or "").strip().lower()
    return key.removesuffix(" evidence").strip()


def classification_rank(label: str | None) -> int:
    """Strength rank (higher is stronger); 0 for an unknown classification."""
    return CLASSIFICATIONS.get(classification_key(label), (0, 0.0))[0]


def classification_strength(label: str | None) -> float | None:
    """Numeric strength in [0, 1], ``None`` when the classification is unknown."""
    entry = CLASSIFICATIONS.get(classification_key(label))
    return entry[1] if entry else None


def relation_for_classification(label: str | None) -> str:
    """Typed predicate: ``associated_with`` for Limited or stronger, a negative or
    qualified predicate for Disputed, Refuted, No Known Disease Relationship and Animal
    Model Only (so ``associated_with`` never mixes in contradicted claims)."""
    return _RELATIONS.get(classification_key(label), "associated_with")


def summarize(classifications: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """Consensus summary over ``(submitter, classification)`` pairs of one gene-disease pair.

    - ``best_classification``: the strongest classification given by anyone.
    - ``consensus_classification``: the most frequent one; ties go to the weaker
      (conservative) side.
    - ``n_submitters``: distinct submitters.
    - ``classification_counts``: how many submissions per classification.
    - ``conflicting``: a Moderate-or-stronger assertion coexists with Disputed or Refuted.
    """
    pairs = [(s, c) for s, c in classifications if c]
    if not pairs:
        return {}
    counts = Counter(c for _, c in pairs)
    best = max(counts, key=classification_rank)
    consensus = max(counts, key=lambda c: (counts[c], -classification_rank(c)))
    keys = {classification_key(c) for c in counts}
    return {
        "best_classification": best,
        "consensus_classification": consensus,
        "n_submitters": len({s for s, _ in pairs}),
        "classification_counts": dict(counts),
        "conflicting": bool(keys & _STRONG) and bool(keys & _CONTRADICTED),
        "supported": bool(keys & _POSITIVE),
    }


def normalize_hgnc(text: str | None) -> tuple[str, str] | None:
    """``HGNC:1100`` / ``hgnc:1100`` / ``1100`` -> ``("id", "HGNC:1100")``; anything else
    that looks like a gene symbol -> ``("symbol", "BRCA1")`` (upper-cased)."""
    value = (text or "").strip()
    if not value:
        return None
    match = _HGNC_RE.match(value)
    if match:
        return "id", f"HGNC:{int(match.group(1))}"
    if value.isdigit():
        return "id", f"HGNC:{int(value)}"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.@-]*", value):
        return "symbol", value.upper()
    return None


def normalize_disease_curie(text: str | None) -> str | None:
    """Canonical disease CURIE: ``mondo:7947`` -> ``MONDO:0007947``, ``Orphanet:558`` and
    ``Orphanet_558`` -> ``ORPHA:558``, ``omim:154700`` -> ``OMIM:154700``; else ``None``."""
    value = (text or "").strip().replace("_", ":", 1) if text else ""
    match = _MONDO_RE.match(value)
    if match:
        return f"MONDO:{int(match.group(1)):07d}"
    prefix, sep, local = value.partition(":")
    canonical = _DISEASE_PREFIXES.get(prefix.strip().upper())
    local = local.strip()
    if sep and canonical and local:
        return f"{canonical}:{local}"
    return None
