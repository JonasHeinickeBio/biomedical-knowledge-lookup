"""
Helpers shared by the omics dataset-discovery adapters (OmicsDI, BioStudies, PRIDE).

These three sources only return *metadata* about public datasets (accession, title,
organism, publication, repository URL). None of the adapters downloads data files; the
helpers here therefore stay small: a polite request throttle, tolerant date parsing,
taxonomy-id extraction and the relationship / mapping dict builders.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any

#: Minimum spacing between two requests of one adapter instance (<= 2 requests/second).
DEFAULT_REQUEST_INTERVAL = 0.5


class RequestThrottle:
    """Keeps consecutive requests of one adapter at least ``interval`` seconds apart.

    The three sources document no rate limit, so this is a courtesy limit that also
    keeps a multi-request call (details + similar datasets + file count) from
    bursting. A lock serialises the bookkeeping so concurrent coroutines queue up.
    """

    def __init__(self, interval: float = DEFAULT_REQUEST_INTERVAL):
        self.interval = interval
        self._last: float | None = None
        self._lock: asyncio.Lock | None = None

    async def wait(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            now = time.monotonic()
            if self._last is not None:
                remaining = self._last + self.interval - now
                if remaining > 0:
                    await asyncio.sleep(remaining)
                    now = time.monotonic()
            self._last = now


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def strip_html(text: Any) -> str:
    """Drop tags (``<br>``, ``<em>``) and collapse whitespace; non-strings give ``""``."""
    if not isinstance(text, str):
        return ""
    return _SPACE_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()


_DATE_FORMATS = (
    "%Y%m%d",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%a %b %d %H:%M:%S %Z %Y",  # java.util.Date.toString(): "Wed Nov 09 17:18:00 GMT 2022"
)
_ISO_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]")


def iso_date(value: Any) -> str | None:
    """Best-effort ``YYYY-MM-DD`` from the date spellings these APIs mix.

    OmicsDI alone returns ``20150608``, ``2015-06-08``, ``2009/05/12``, ``2025-02-24T00:00:00Z``
    and a ``Date.toString()`` rendering for different repositories. Epoch milliseconds
    (BioStudies ``info``) are accepted too. Anything unparseable gives ``None``.
    """
    if value is None or value is False:
        return None
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(value / 1000.0, tz=UTC).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    match = _ISO_PREFIX_RE.match(text)
    if match:
        text = match.group(1)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


_TAXID_RES = (
    re.compile(r"ncbitaxon[:_]\s*(\d+)", re.IGNORECASE),
    re.compile(r"\bNEWT:(\d+)", re.IGNORECASE),
    re.compile(r"\btaxid[:=\s]+(\d+)", re.IGNORECASE),
)
#: Species that dominate omics submissions; used only when the source gives a bare name.
COMMON_TAXA: dict[str, str] = {
    "homo sapiens": "9606",
    "mus musculus": "10090",
    "rattus norvegicus": "10116",
    "macaca mulatta": "9544",
    "sus scrofa": "9823",
    "bos taurus": "9913",
    "danio rerio": "7955",
    "drosophila melanogaster": "7227",
    "caenorhabditis elegans": "6239",
    "saccharomyces cerevisiae": "4932",
    "escherichia coli": "562",
    "arabidopsis thaliana": "3702",
    "severe acute respiratory syndrome coronavirus 2": "2697049",
    # everyday names, so that ``organism="human"`` works as a filter
    "human": "9606",
    "mouse": "10090",
    "rat": "10116",
    "pig": "9823",
    "cow": "9913",
    "zebrafish": "7955",
    "sars-cov-2": "2697049",
}
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def taxon_id(name_or_id: Any) -> str | None:
    """NCBI Taxonomy id from ``"Homo Sapiens (ncbitaxon:9606)"``, ``"NEWT:9606"``, ``"9606"``
    or a common species name (``"Homo sapiens (human)"``); ``None`` when unknown."""
    if name_or_id is None:
        return None
    text = str(name_or_id).strip()
    if text.isdigit():
        return text
    for pattern in _TAXID_RES:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return COMMON_TAXA.get(_PAREN_RE.sub(" ", text).strip().lower())


def dedupe(items: list[str]) -> list[str]:
    """Order-preserving de-duplication that drops empty values."""
    return list(dict.fromkeys(i for i in items if i))


def relationship(
    label: str, related_id: str, related_name: str, source: str, **extra: Any
) -> dict[str, Any]:
    """One ``get_relationships`` item with the keys the interface contract requires."""
    item: dict[str, Any] = {
        "relation_label": label,
        "related_id": related_id,
        "related_name": related_name,
        "source": source,
    }
    item.update({k: v for k, v in extra.items() if v is not None})
    return item


def mapping(
    from_id: str,
    to_id: str,
    from_source: str,
    to_source: str,
    kind: str = "exact",
    confidence: float = 1.0,
) -> dict[str, Any]:
    """One ``get_mappings`` item with the keys the interface contract requires."""
    return {
        "fromId": from_id,
        "toId": to_id,
        "fromSource": from_source,
        "toSource": to_source,
        "mappingType": kind,
        "confidence": confidence,
    }
