"""Graph node: term preprocessing with German compound decomposition.

Generates a flat list of expanded search terms by applying multiple
transformations to each input term:

1. Original term (as provided)
2. Umlaut-expanded (ä→ae, ö→oe, ü→ue, ß→ss)
3. Normalized (lowercased, stripped, punctuation removed)
4. German compound splitting (e.g., Kieferklemme → Kiefer + Klemme)
5. Partial terms from compounds (each component individually)

All expanded terms are searched IN PARALLEL by the lookup node,
giving maximum coverage in a single pass.
"""

from __future__ import annotations

import logging
import re

from ..state import LookupWorkflowState, make_step

logger = logging.getLogger(__name__)

# ── Unicode-to-ASCII replacements ──────────────────────────────────
UMLAUT_MAP: dict[str, str] = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
    "ß": "ss",
    "é": "e",
    "è": "e",
    "ê": "e",
    "ë": "e",
    "á": "a",
    "à": "a",
    "â": "a",
    "ã": "a",
    "å": "a",
    "í": "i",
    "ì": "i",
    "î": "i",
    "ï": "i",
    "ó": "o",
    "ò": "o",
    "ô": "o",
    "õ": "o",
    "ú": "u",
    "ù": "u",
    "û": "u",
    "ū": "u",
    "ñ": "n",
    "ç": "c",
}

# ── German medical word parts for compound decomposition ────────────
# These are noun stems commonly used as the FIRST part of a compound.
_GERMAN_PREFIXES: list[tuple[str, int]] = [
    # (stem, min_word_len_to_try_split)
    ("Kopf", 6),
    ("Rücken", 7),
    ("Bauch", 6),
    ("Brust", 6),
    ("Muskel", 7),
    ("Muskul", 7),
    ("Gelenk", 7),
    ("Glied", 6),
    ("Haut", 5),
    ("Blut", 5),
    ("Herz", 5),
    ("Lunge", 6),
    ("Magen", 6),
    ("Darm", 5),
    ("Nieren", 7),
    ("Leber", 6),
    ("Kiefer", 7),
    ("Zahn", 5),
    ("Mund", 5),
    ("Hals", 5),
    ("Nase", 5),
    ("Ohr", 5),
    ("Auge", 5),
    ("Finger", 7),
    ("Hand", 5),
    ("Fuß", 5),
    ("Fuss", 5),
    ("Arm", 4),
    ("Bein", 5),
    ("Gesicht", 8),
    ("Zunge", 6),
    ("Rippe", 6),
    ("Wirbel", 7),
    ("Nerv", 5),
    ("Gefäss", 7),
    ("Gefaess", 7),
    ("Drüse", 6),
    ("Druse", 6),
    ("Zelle", 6),
    ("Gewebe", 7),
    ("Schleim", 7),
    ("Eiter", 6),
    ("Atem", 5),
    ("Geruch", 7),
    ("Geschmack", 9),
    ("Schluck", 7),
    ("Seh", 5),
    ("Hör", 5),
    ("Hörsturz", 9),
    ("Ohren", 7),
    ("Augen", 7),
    ("Tag", 4),
    ("Nacht", 6),
    ("Morgen", 6),
    ("Immun", 6),
    ("Nähr", 5),
    ("Stoffwechsel", 12),
    ("Kälte", 6),
    ("Wärme", 6),
    ("Hitze", 6),
    ("Druck", 6),
    ("Zug", 4),
]

# Noun stems commonly used as the LAST part of a compound.
_GERMAN_SUFFIXES: list[str] = [
    "schmerz",
    "schmerzen",
    "schmerzes",
    "schwellung",
    "schwellungen",
    "entzündung",
    "entzündungen",
    "zündung",
    "zündungen",
    "erkrankung",
    "erkrankungen",
    "krankung",
    "krankungen",
    "störung",
    "störungen",
    "stoerung",
    "stoerungen",
    "beschwerden",
    "symptom",
    "symptome",
    "symptomen",
    "syndrom",
    "krampf",
    "krämpfe",
    "krampfe",
    "klemme",
    "klemmung",
    "lähmung",
    "lähmungen",
    "lahmung",
    "lahmungen",
    "schwäche",
    "schwaeche",
    "steifigkeit",
    "steifheit",
    "spannung",
    "spannungen",
    "veränderung",
    "veränderungen",
    "veraenderung",
    "veraenderungen",
    "reizung",
    "reizungen",
    "infektion",
    "infektionen",
    "blutung",
    "blutungen",
    "bluten",
    "bruch",
    "brüche",
    "brueche",
    "verletzung",
    "verletzungen",
    "wunde",
    "wunden",
    "geschwür",
    "geschwüre",
    "geschwuer",
    "geschwuere",
    "knoten",
    "tumor",
    "tumore",
    "tumoren",
    "krebs",
    "zyste",
    "zysten",
    "stein",
    "steine",
    "polyp",
    "polypen",
    "geruch",
    "gerüche",
    "gerueche",
    "geschmack",
    "bildung",
    "mangel",
    "überschuss",
    "ueberschuss",
    "abgang",
    "ausfluss",
    "fluss",
    "flusses",
    "gang",
    "gänge",
    "gaenge",
    "pflicht",
    "sucht",
    "süchtig",
    "suechtig",
    "angst",
    "furcht",
    "druck",
    "drücke",
    "druecke",
    "stich",
    "stiche",
    "zug",
    "züge",
    "zuege",
]


def _expand_umlauts(text: str) -> str:
    """Replace German umlauts and other diacritics with ASCII equivalents."""
    return "".join(UMLAUT_MAP.get(ch, ch) for ch in text)


def _normalize_query(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    normalized = text.lower().strip()
    normalized = re.sub(r"[^\w\s-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _detect_german(term: str) -> bool:
    """Heuristic: does the term look German?"""
    if re.search(r"[äöüßÄÖÜ]", term):
        return True
    german_patterns = [
        r"\b(Schmerz|Schmerzen|Schwellung|Entzündung|Erkrankung)\b",
        r"\b(Fieber|Husten|Schnupfen|Durchfall|Übelkeit|Erbrechen)\b",
        r"\b(Muskel|Gelenk|Haut|Kopf|Bauch|Brust|Rücken)\b",
    ]
    for pattern in german_patterns:
        if re.search(pattern, term, re.IGNORECASE):
            return True
    return False


def _split_german_compound(word: str) -> list[str]:
    """Try to decompose a German compound word into its parts.

    Uses a prefix + Fugen-s + suffix matching strategy:
      Kieferklemme → Kiefer + Klemme
      Muskelschwäche → Muskel + Schwäche  (Fugen-s stripped)
      Kopfschmerz → Kopf + Schmerz

    Returns a list of found parts (may be empty if no split found).
    """
    lower = word.lower()

    # Try all prefixes (sorted longest first for greedy match)
    for prefix, _min_len in sorted(_GERMAN_PREFIXES, key=lambda x: -len(x[0])):
        p_lower = prefix.lower()

        # Check if word starts with the prefix
        if not lower.startswith(p_lower):
            continue

        # What remains after the prefix
        remainder = lower[len(p_lower) :]

        # Handle Fugen-s: "Muskelschwäche" → prefix="Muskel" + "s" + "Schwäche"
        if remainder.startswith("s"):
            # Try stripping the Fugen-s
            remainder_no_s = remainder[1:]
            for suffix in sorted(_GERMAN_SUFFIXES, key=lambda x: -len(x)):
                s_lower = suffix.lower()
                if remainder_no_s == s_lower or remainder_no_s.endswith(s_lower):
                    # Found split: prefix + s + suffix
                    # Reconstruct original casing for the parts
                    prefix_end = len(prefix)
                    suffix_start = len(word) - len(s_lower)
                    return [
                        word[:prefix_end],
                        word[suffix_start:],
                        f"{word[:prefix_end]} {word[suffix_start:]}",
                    ]
                    # Also return the individual parts and combined form

        # Try direct suffix match (no Fugen-s)
        for suffix in sorted(_GERMAN_SUFFIXES, key=lambda x: -len(x)):
            s_lower = suffix.lower()
            if remainder.endswith(s_lower):
                # Check that there's actual content between prefix and suffix
                middle = remainder[: -len(s_lower)]
                if len(middle) <= 2:
                    # Very short middle part — skip (likely not a real compound)
                    continue
                prefix_end = len(prefix)
                suffix_start = len(word) - len(s_lower)
                return [
                    word[:prefix_end],
                    word[suffix_start:],
                    f"{word[:prefix_end]} {word[suffix_start:]}",
                ]

    # No decomposition found
    return []


def _build_expanded_terms(original_terms: list[str]) -> list[str]:
    """Build a flat list of all search term variants.

    For each original term (from comma-split input), generates:
    - The original term
    - Umlaut-expanded version
    - Normalized version
    - German compound split parts (if applicable)
    - Each individual compound part
    """
    expanded: list[str] = []

    for term in original_terms:
        if not term.strip():
            continue
        term = term.strip()
        seen: set[str] = set()

        def _add(t: str, seen: set[str] = seen) -> None:
            t_stripped = t.strip().lower()
            if t_stripped and t_stripped not in seen:
                seen.add(t_stripped)
                expanded.append(t.strip())

        # 1. Always add the original
        _add(term)

        # 2. Umlaut-expanded (if different)
        um_expanded = _expand_umlauts(term)
        if um_expanded.lower() != term.lower():
            _add(um_expanded)

        # 3. Normalized
        normalized = _normalize_query(term)
        if normalized != term.lower().strip():
            _add(normalized)

        # 4. German compound splitting (if the term looks German or has umlauts)
        if _detect_german(term):
            parts = _split_german_compound(term)
            for part in parts:
                _add(part)

            # Also try the umlaut-expanded version as German
            if um_expanded.lower() != term.lower():
                parts_um = _split_german_compound(um_expanded)
                for part in parts_um:
                    if part.lower() not in seen:
                        _add(part)

    # If nothing was generated (shouldn't happen), fall back to original
    if not expanded:
        expanded = original_terms[:]

    # Deduplicate while preserving order
    result: list[str] = []
    seen_final: set[str] = set()
    for t in expanded:
        key = t.strip().lower()
        if key not in seen_final:
            seen_final.add(key)
            result.append(t.strip())

    return result


async def preprocess_node(state: LookupWorkflowState) -> dict:
    """Preprocess the query: split comma terms, generate all search variants.

    Produces `expanded_search_terms` — a flat deduplicated list of query
    strings for the lookup node to search in parallel.
    """
    query = state["query"]
    raw_terms = [t.strip() for t in query.split(",") if t.strip()]
    if not raw_terms:
        raw_terms = [query]

    # Detect if any term looks German
    is_german = any(_detect_german(t) for t in raw_terms)

    # Generate expanded terms (flat list of all variants)
    expanded_terms = _build_expanded_terms(raw_terms)

    step_parts = [
        f"{len(raw_terms)} input term(s)",
        f"→ {len(expanded_terms)} search variant(s)",
        f"German={'yes' if is_german else 'no'}",
    ]

    return {
        "normalized_query": _normalize_query(query),
        "original_query": query,
        "expanded_search_terms": expanded_terms,
        "is_german": is_german,
        "steps": [make_step("PreprocessAgent", "expand", " | ".join(step_parts))],
    }
