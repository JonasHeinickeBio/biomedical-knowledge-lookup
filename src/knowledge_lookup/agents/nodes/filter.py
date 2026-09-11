"""Graph node: clinical concept filtering and type-aware re-ranking.

Post-processes lookup results to:
1. Remove non-clinical concepts (questionnaires, measurement scales, geographic locations)
2. Boost confidence for clinically relevant semantic types (Sign or Symptom, Finding, Phenotype)
3. Re-order results so clinical concepts appear first

This runs after parallel expansion search, before quality gate.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ...models import KnowledgeSource
from ..state import LookupWorkflowState, dict_to_lookup_result, lookup_result_to_dict, make_step

logger = logging.getLogger(__name__)

# ── Patterns that identify non-clinical concepts ─────────────────────

# Questionnaire / survey / measurement scale patterns
_QUESTIONNAIRE_LABEL_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(Frequency|Severity|Duration|Level|Rating)\s+of\s+", re.IGNORECASE),
    re.compile(r"(Question|Questionnaire|PRO-CTCAE|CTCAE|Score|Subscale|Domain)", re.IGNORECASE),
    re.compile(r"^NOC\s*-?\s*", re.IGNORECASE),
    re.compile(r"^Past\s+\w+\s+Days?\s+", re.IGNORECASE),
    re.compile(r"RPQ\s*-?\s*", re.IGNORECASE),
    re.compile(r"DLQI\s*-?\s*", re.IGNORECASE),
    re.compile(r"^Have\s+", re.IGNORECASE),
    re.compile(r"^Need\s+for\s+", re.IGNORECASE),
    re.compile(r"^Use\s+of\s+", re.IGNORECASE),
]

# Ontology ID patterns to blacklist
_ONTOLOGY_BLACKLIST_PREFIXES: list[str] = [
    "GAZ:",  # Gazetteer (geographic locations)
]

# Concepts from these sources are demoted unless they have clinical cross-references
_NON_CLINICAL_SOURCES: set[str] = {
    "GAZ",
    "MP",  # Mouse phenotype (without HPO)
}

# Preferred semantic types for clinical concepts (highest = most clinical)
_CLINICAL_SEMANTIC_TYPES: dict[str, float] = {
    "SIGN_OR_SYMPTOM": 1.5,
    "SYMPTOM": 1.5,
    "SIGN": 1.4,
    "FINDING": 1.4,
    "PHENOTYPE": 1.3,
    "DISEASE_OR_SYNDROME": 1.2,
    "DISEASE": 1.2,
    "PATHOLOGIC_FUNCTION": 1.2,
    "MENTAL_OR_BEHAVIORAL_DYSFUNCTION": 1.1,
    "INJURY_OR_POISONING": 1.1,
    "CLINICAL_ATTRIBUTE": 0.5,
    "ORGANIC_CHEMICAL": 0.3,
    "PHARMACOLOGIC_SUBSTANCE": 0.5,
    "LABORATORY_OR_TEST_RESULT": 0.5,
    "MEDICAL_DEVICE": 0.2,
    "OCCUPATION": 0.1,
    "POPULATION_GROUP": 0.1,
}

# Blacklisted labels containing these are penalized
_LABEL_BLACKLIST_KEYWORDS: list[str] = [
    "dry mouth question",
    "dryness of mouth question",
    "purple toes syndrome",  # MEDDRA drug AE, not symptom
    "fragrance",
    "perfume",
    "sensitivity to chemical",
]


def _is_questionnaire_concept(c: Any) -> bool:
    """Check if a concept looks like a questionnaire/measurement item."""
    label = (c.primary_label or "").strip()
    if not label:
        return False

    for pattern in _QUESTIONNAIRE_LABEL_PATTERNS:
        if pattern.search(label):
            return True

    # Check label for blacklisted keywords
    label_lower = label.lower()
    for kw in _LABEL_BLACKLIST_KEYWORDS:
        if kw in label_lower:
            return True

    return False


def _has_blacklisted_ontology(c: Any) -> bool:
    """Check if the concept's identifiers contain blacklisted ontology prefixes."""
    for ident in c.identifiers or []:
        id_str = ident.identifier or ""
        for prefix in _ONTOLOGY_BLACKLIST_PREFIXES:
            if id_str.startswith(prefix):
                return True
    # Also check primary_id
    if c.primary_id:
        for prefix in _ONTOLOGY_BLACKLIST_PREFIXES:
            if c.primary_id.startswith(prefix):
                return True
    return False


def _is_wikidata_only_noise(c: Any) -> bool:
    """Check if concept is a Wikidata-only entry without UMLS CUI.

    These are usually generic Wikipedia-style entries without clinical value.
    """
    sources = {str(s).upper() for s in (c.sources or [])}
    if sources == {"WIKIDATA"}:
        # If only from Wikidata, check for CUI
        has_cui = False
        if c.identifiers:
            for ident in c.identifiers:
                src = getattr(ident, "source", "")
                if isinstance(src, KnowledgeSource):
                    if src == KnowledgeSource.UMLS:
                        has_cui = True
                        break
                elif isinstance(src, str) and src.upper() == "UMLS":
                    has_cui = True
                    break
        if not has_cui:
            # Also check if primary_id looks like a clinical ID (not generic Q)
            if c.primary_id and c.primary_id.startswith("Q"):
                return True
    return False


def _get_clinical_type_boost(c: Any) -> float:
    """Compute a confidence multiplier based on semantic type.

    Returns a multiplier >1 for clinical types, <1 for non-clinical types.
    """
    # Check concept_type
    ct = str(c.concept_type).upper() if c.concept_type else ""
    if ct in _CLINICAL_SEMANTIC_TYPES:
        return _CLINICAL_SEMANTIC_TYPES[ct]

    # Check semantic_types list
    if c.semantic_types:
        for st in c.semantic_types:
            st_upper = str(st).upper()
            if st_upper in _CLINICAL_SEMANTIC_TYPES:
                return _CLINICAL_SEMANTIC_TYPES[st_upper]

    # No info → neutral
    return 1.0


def _has_non_clinical_source_only(c: Any) -> bool:
    """Check if concept comes ONLY from non-clinical sources."""
    if not c.sources:
        return False
    srcs = {str(s).upper() for s in c.sources}
    # If it has any clinical source, it's OK
    clinical_sources = {"UMLS", "OLS", "BIOPORTAL", "WIKIDATA", "HPO", "SNOMED", "MONDO"}
    if srcs & clinical_sources:
        return False
    for prefix in _NON_CLINICAL_SOURCES:
        if any(s.startswith(prefix) for s in srcs):
            return True
    return False


def _filter_and_rank_concepts(concepts: list[Any]) -> list[Any]:
    """Filter and re-rank concepts for clinical relevance.

    1. Remove questionnaire/measurement items
    2. Remove blacklisted ontology concepts
    3. Boost confidence for clinical types
    4. Sort by boosted confidence (descending)
    """
    if not concepts:
        return []

    filtered: list[Any] = []
    removed_q = 0
    removed_b = 0
    removed_w = 0
    removed_s = 0

    for c in concepts:
        # Skip questionnaire/measurement items
        if _is_questionnaire_concept(c):
            removed_q += 1
            continue

        # Skip blacklisted ontology
        if _has_blacklisted_ontology(c):
            removed_b += 1
            continue

        # Skip Wikidata-only noise (no CUI, Q-prefix IDs)
        if _is_wikidata_only_noise(c):
            removed_w += 1
            continue

        # Skip concepts that come only from non-clinical sources (GAZ, MP, ...)
        if _has_non_clinical_source_only(c):
            removed_s += 1
            continue

        # Apply type boost to confidence
        boost = _get_clinical_type_boost(c)
        if c.confidence_score is not None:
            c.confidence_score = min(round(c.confidence_score * boost, 3), 1.0)

        filtered.append(c)

    if removed_q or removed_b or removed_w or removed_s:
        logger.debug(
            "Clinical filter removed %d questionnaire(s), %d blacklisted, "
            "%d wikidata-only, %d non-clinical-source-only",
            removed_q,
            removed_b,
            removed_w,
            removed_s,
        )

    # Sort by confidence (descending)
    filtered.sort(key=lambda x: x.confidence_score or 0.0, reverse=True)

    return filtered


async def filter_node(state: LookupWorkflowState) -> dict:
    """Filter and re-rank lookup results for clinical relevance.

    Removes questionnaire/measurement items, boosts clinical types,
    and re-orders results so the most clinically relevant come first.
    """
    result = dict_to_lookup_result(state.get("lookup_result"))
    if result is None or not result.concepts:
        return {
            "steps": [make_step("FilterAgent", "skip", "No concepts to filter")],
        }

    original_count = len(result.concepts)
    result.concepts = _filter_and_rank_concepts(result.concepts)
    result.total_found = len(result.concepts)

    removed = original_count - len(result.concepts)
    result_dict = lookup_result_to_dict(result)

    n_boosted = sum(
        1
        for c in result.concepts
        if c.confidence_score
        and (
            (str(c.concept_type) if c.concept_type else "").upper()
            in {k.upper() for k in _CLINICAL_SEMANTIC_TYPES}
            and c.confidence_score > 0.5
        )
    )

    step_parts = [
        f"{original_count}→{len(result.concepts)} concepts",
        f"removed {removed} non-clinical" if removed else "",
        f"{n_boosted} clinical types boosted" if n_boosted else "",
    ]

    return {
        "lookup_result": result_dict,
        "steps": [
            make_step(
                "FilterAgent",
                "filter",
                " | ".join(p for p in step_parts if p),
            )
        ],
    }
