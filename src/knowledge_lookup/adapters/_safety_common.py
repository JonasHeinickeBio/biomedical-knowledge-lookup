"""Small helpers shared by the SIDER, OFFSIDES and Human Protein Atlas adapters.

Kept private (leading underscore, not exported from ``adapters/__init__``) because the three
adapters only need the same handful of file-reading, ranking and concept-filling utilities.
"""

import gzip
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import IO, Any

from ..models import KnowledgeSource, UnifiedConcept


def open_text(path: Path) -> IO[str]:
    """Open a text file, gunzipping transparently (detected by magic bytes, not extension)."""
    with path.open("rb") as handle:
        magic = handle.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return path.open("rt", encoding="utf-8", errors="replace", newline="")


def tsv_rows(path: Path) -> Iterator[list[str]]:
    """Yield the tab-split, non-empty rows of a (possibly gzipped) TSV file."""
    with open_text(path) as handle:
        for line in handle:
            line = line.rstrip("\r\n")
            if line:
                yield line.split("\t")


def to_float(value: Any) -> float | None:
    """``float(value)`` or ``None`` when it is empty / not numeric."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def match_score(needle: str, haystack: str) -> float | None:
    """Rank a substring match: 1.0 exact, 0.9 prefix, 0.8 whole word, 0.6 substring.

    Both arguments must already be lower-cased. ``None`` means no match.
    """
    if needle == haystack:
        return 1.0
    if haystack.startswith(needle):
        return 0.9
    if needle in haystack:
        return 0.8 if re.search(rf"\b{re.escape(needle)}\b", haystack) else 0.6
    return None


def dedupe_mappings(mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop repeated ``(toSource, toId)`` targets, keeping the first (highest priority)."""
    seen: set[tuple[str, str]] = set()
    unique = []
    for mapping in mappings:
        key = (mapping["toSource"], mapping["toId"])
        if key not in seen:
            seen.add(key)
            unique.append(mapping)
    return unique


def make_mapping(
    from_id: str,
    from_source: str,
    to_id: str,
    to_source: str,
    mapping_type: str,
    confidence: float,
) -> dict[str, Any]:
    """Build a mapping dict in the library-wide ``{fromId, toId, ...}`` shape."""
    return {
        "fromId": from_id,
        "toId": to_id,
        "fromSource": from_source,
        "toSource": to_source,
        "mappingType": mapping_type,
        "confidence": confidence,
    }


def fill_concept(
    concept: UnifiedConcept,
    source: KnowledgeSource,
    data: dict[str, Any],
    *,
    categories: Iterable[str] = (),
    semantic_types: Iterable[str] = (),
    definitions: Iterable[str] = (),
    synonyms: Iterable[str] = (),
) -> None:
    """Populate list fields and ``source_data[source]`` (all ``None``-safe for mypy)."""
    if concept.categories is not None:
        concept.categories.extend(categories)
    if concept.semantic_types is not None:
        concept.semantic_types.extend(semantic_types)
    if concept.definitions is not None:
        concept.definitions.extend(definitions)
    if concept.synonyms is not None:
        concept.synonyms.extend(s for s in synonyms if s not in concept.synonyms)
    if isinstance(concept.source_data, dict):
        concept.source_data[source] = data
