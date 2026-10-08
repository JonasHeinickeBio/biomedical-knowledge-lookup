"""
OpenCitations Knowledge Source Adapter

OpenCitations publishes the open citation graph between scholarly works: every row of the
COCI/"Index" is one citation (a citing work, a cited work, the citation's creation date and
timespan, journal and author self-citation flags), identified by an OCI. The citation data
are released under CC0 (public domain); bibliographic metadata come from OpenCitations Meta
(CC0 as well). The index is built from DOI-to-DOI links deposited in Crossref, DataCite,
PubMed, OpenAIRE ... and **lags** behind the publishers: very recent papers and references
without a DOI are missing, so counts are lower bounds and typically below Google Scholar,
Dimensions or OpenAlex.

API (verified live, keyless)::

    https://api.opencitations.net/index/v2/citation-count/{id}   [{"count": "19265"}]
    https://api.opencitations.net/index/v2/reference-count/{id}
    https://api.opencitations.net/index/v2/citations/{id}        citation rows citing {id}
    https://api.opencitations.net/index/v2/references/{id}       citation rows cited by {id}
    https://api.opencitations.net/index/v2/citation/{oci}
    https://api.opencitations.net/meta/v1/metadata/{id}           bibliographic metadata

``{id}`` is prefixed: ``doi:10.1038/s41586-020-2012-7``, ``pmid:32015507`` or
``omid:br/06130344922``. Quirks worth knowing:

* The old base ``https://opencitations.net/index/api/v2/...`` answers **HTTP 301** to the
  ``api.opencitations.net`` host; the redirect is not followed, the new base is used directly.
* **Slow on a cold cache:** a count for a heavily cited paper took 9-13 s (a cached or small
  one takes 0.3-1 s); the request timeout floor is therefore 120 s.
* **No paging or ``limit``.** ``citations``/``references`` always return the whole result
  set (19,265 rows = 8 MB for the first SARS-CoV-2 bat-origin paper). The RAMOSE parameters
  ``sort=desc(creation)``, ``filter=creation:>2024`` (string comparison on the partial
  date) and ``require=<field>`` do work. The adapter sorts newest first and, for works with
  more than :data:`BULK_CAP` citations, only asks for citations created since the
  start of the previous calendar year (approximately); edges are capped at :data:`MAX_EDGES` per direction.
* ``creation`` is the citing paper's date with varying precision (``2026-10``, ``2026-03-09``).
  ``timespan`` is an ISO 8601 duration (``P6Y3M4D``). ``journal_sc`` / ``author_sc`` are
  ``"yes"`` / ``"no"`` self-citation flags.
* Each row carries *all* identifiers the index holds for both works
  (``"omid:br/061... doi:10.. pmid:32015507 openalex:W300.."``), which feeds the mappings.
* An unknown id is HTTP 200 with ``[]``; counts of an unknown id are ``"0"``.
* Optional access token (higher limits, recommended by OpenCitations for applications):
  environment variable ``OPENCITATIONS_ACCESS_TOKEN`` (or the ``opencitations`` entry of the
  config's API keys), sent in the ``authorization`` header, only when set. Without a token
  the documented limit is 180 requests per minute per IP; requests here are spaced >= 0.4 s.
* There is **no free-text search**; ``search_concepts`` accepts identifiers only.
"""

import asyncio
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

INDEX_URL = "https://api.opencitations.net/index/v2"
META_URL = "https://api.opencitations.net/meta/v1/metadata"
TOKEN_ENV = "OPENCITATIONS_ACCESS_TOKEN"

MAX_EDGES = 100  # citation edges returned per direction
BULK_CAP = 3000  # above this many citations only the recent ones are requested
REQUEST_INTERVAL = 0.4  # seconds between requests (<= 2.5 req/s, limit is 3 req/s)

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*|urn:doi:)", re.IGNORECASE)
_PMID_RE = re.compile(r"^(?:pmid:?\s*)?(\d{1,9})$", re.IGNORECASE)
_OMID_RE = re.compile(r"^(?:omid:)?(br/\d+)$", re.IGNORECASE)
_ID_TOKEN_RE = re.compile(r"(\b[a-z]+):(\S+)", re.IGNORECASE)
_VENUE_RE = re.compile(r"^(.*?)\s*\[(.*)\]\s*$")

#: id-prefix -> (``toSource`` of a mapping, mapping type)
MAPPED_IDS: dict[str, tuple[str, str]] = {
    "doi": ("DOI", "exact"),
    "pmid": ("PubMed", "exact"),
    "omid": ("OMID", "exact"),
    "openalex": ("OPENALEX", "exact"),
    "pmcid": ("PMC", "exact"),
}


def _parse_ids(text: Any) -> dict[str, list[str]]:
    """``"omid:br/061 doi:10.1/x pmid:7"`` -> ``{"omid": ["br/061"], "doi": [...], ...}``."""
    ids: dict[str, list[str]] = {}
    for prefix, value in _ID_TOKEN_RE.findall(str(text or "")):
        ids.setdefault(prefix.lower(), []).append(value)
    return ids


def _duration_years(value: str) -> float | None:
    """ISO 8601 ``P6Y3M4D`` -> approximate years (6.3); ``None`` when unparsable."""
    match = re.fullmatch(r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?", value or "")
    if not match or not any(match.groups()):
        return None
    years, months, days = (int(g or 0) for g in match.groups())
    return round(years + months / 12 + days / 365, 2)


class OpenCitationsAdapter(KnowledgeSourceAdapter):
    """Adapter for the OpenCitations Index and Meta APIs (open citation links, CC0)."""

    #: counts for popular works took 9-13 s on a cold cache; never cut them off and retry.
    min_request_timeout = 120.0

    def __init__(self, config: Any):
        super().__init__(config)
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OPENCITATIONS

    def is_available(self) -> bool:
        return True  # public, keyless API (the access token is optional)

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_id(concept_id: str) -> str | None:
        """``10.x/y`` / ``doi:`` / ``https://doi.org/..`` / ``pmid:123`` / ``omid:br/06..``
        -> the prefixed form the API expects (``doi:10.x/y``, ``pmid:123``, ``omid:br/06..``).

        Bare digits are read as a PMID. DOIs are lower-cased (they are case-insensitive and
        the index stores them lower-cased). ``None`` for anything else.
        """
        text = (concept_id or "").strip()
        doi_text = _DOI_PREFIX_RE.sub("", text)
        if _DOI_RE.match(doi_text):
            return f"doi:{doi_text.lower()}"
        match = _PMID_RE.match(text)
        if match:
            return f"pmid:{match.group(1)}"
        match = _OMID_RE.match(text)
        if match:
            return f"omid:{match.group(1).lower()}"
        return None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """``authorization`` header with the optional access token; nothing when unset."""
        token = None
        try:
            token = self.config.get_api_key("opencitations")
        except Exception:  # pragma: no cover - config without api keys
            token = None
        token = token or os.getenv(TOKEN_ENV)
        return {"authorization": token.strip()} if token and token.strip() else {}

    async def _get_rows(
        self, url: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]] | None:
        """Throttled GET returning the JSON array of rows; ``None`` on failure."""
        try:
            async with self._lock:
                wait = self._last_request + REQUEST_INTERVAL - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    data: Any = await self._make_request(
                        url, params=params, headers=self._auth_headers()
                    )
                finally:
                    self._last_request = time.monotonic()
        except Exception as e:
            if getattr(e, "status", None) != 404:
                logger.warning(f"OpenCitations request failed for {url}: {e}")
            return None
        if not isinstance(data, list):
            return None
        return [row for row in data if isinstance(row, dict)]

    async def _count(self, kind: str, oc_id: str) -> int | None:
        """``citation-count`` / ``reference-count``; ``None`` when the request failed."""
        rows = await self._get_rows(f"{INDEX_URL}/{kind}/{quote(oc_id, safe=':/')}")
        if not rows:
            return None
        count = str(rows[0].get("count") or "")
        return int(count) if count.isdigit() else None

    async def _meta(self, oc_id: str) -> dict[str, Any] | None:
        """First OpenCitations Meta record for an id (``None`` when unknown)."""
        rows = await self._get_rows(f"{META_URL}/{quote(oc_id, safe=':/')}")
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Resolve an identifier (DOI, ``pmid:``, ``omid:``) to its work.

        OpenCitations has no text search, so anything that is not an identifier returns ``[]``.
        """
        try:
            if limit <= 0 or not self.normalize_id(query):
                return []
            concept = await self.get_concept_details(query)
            return [concept] if concept else []
        except Exception as e:
            logger.error(f"OpenCitations search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Work with Meta metadata plus citation and reference counts.

        Three requests (Meta, ``citation-count``, ``reference-count``). A work unknown to
        Meta with zero citations and references is reported as ``None``.
        """
        try:
            oc_id = self.normalize_id(concept_id)
            if not oc_id:
                return None
            meta = await self._meta(oc_id)
            citations = await self._count("citation-count", oc_id)
            references = await self._count("reference-count", oc_id)
            if meta is None and not (citations or references):
                return None
            return self._to_concept(oc_id, meta or {}, citations, references)
        except Exception as e:
            logger.error(f"OpenCitations get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Work -> cited works (``cites``) and citing works (``cited_by``).

        Each direction is capped at 100 edges, newest first. Edge keys: ``related_id``
        (DOI when the index has one, else ``pmid:``/``omid:``), ``related_name`` (the same id:
        the index holds no titles), ``oci``, ``creation`` (date of the citing paper),
        ``timespan`` (ISO duration between the two papers), ``timespan_years``,
        ``journal_self_citation`` / ``author_self_citation`` (booleans) and ``other_ids``.
        For works with more than 3,000 citations only citations created since the start of
        the previous calendar year are considered.
        """
        try:
            oc_id = self.normalize_id(concept_id)
            if not oc_id:
                return []
            edges = await self._reference_edges(oc_id)
            edges += await self._citation_edges(oc_id)
            return edges
        except Exception as e:
            logger.warning(f"OpenCitations get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Other identifiers from OpenCitations Meta (DOI, PMID, OMID, OpenAlex, PMC) and the
        ISSNs of the venue. The queried id itself is not repeated.
        """
        try:
            oc_id = self.normalize_id(concept_id)
            if not oc_id:
                return []
            meta = await self._meta(oc_id)
            if not meta:
                return []
            ids = _parse_ids(meta.get("id"))
            from_id = (ids.get("doi") or [oc_id.split(":", 1)[1]])[0]
            own = oc_id.split(":", 1)
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for prefix, values in ids.items():
                if prefix not in MAPPED_IDS:
                    continue
                to_source, kind = MAPPED_IDS[prefix]
                for value in values:
                    if (prefix, value.lower()) == (own[0], own[1].lower()) or (
                        prefix == "doi" and value.lower() == from_id
                    ):
                        continue
                    if (prefix, value) not in seen:
                        seen.add((prefix, value))
                        mappings.append(self._mapping(from_id, to_source, value, kind, 1.0))
            _, issns = self._parse_venue(meta.get("venue"))
            for issn in issns:
                mappings.append(self._mapping(from_id, "ISSN", issn, "container_id", 1.0))
            return mappings
        except Exception as e:
            logger.warning(f"OpenCitations get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_citations(self, concept_id: str, limit: int = MAX_EDGES) -> list[dict[str, Any]]:
        """Newest ``limit`` citation rows that cite this work (``cited_by`` edges)."""
        return await self._citation_edges(self.normalize_id(concept_id) or "", limit)

    async def get_references(
        self, concept_id: str, limit: int = MAX_EDGES
    ) -> list[dict[str, Any]]:
        """First ``limit`` references of this work that are in the index (``cites`` edges)."""
        return await self._reference_edges(self.normalize_id(concept_id) or "", limit)

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    async def _reference_edges(self, oc_id: str, limit: int = MAX_EDGES) -> list[dict[str, Any]]:
        if not oc_id or limit <= 0:
            return []
        rows = await self._get_rows(
            f"{INDEX_URL}/references/{quote(oc_id, safe=':/')}", {"sort": "desc(creation)"}
        )
        return self._rows_to_edges(rows or [], "cites", "cited", limit)

    async def _citation_edges(self, oc_id: str, limit: int = MAX_EDGES) -> list[dict[str, Any]]:
        if not oc_id or limit <= 0:
            return []
        params: dict[str, Any] = {"sort": "desc(creation)"}
        count = await self._count("citation-count", oc_id)
        if count is not None and count > BULK_CAP:
            # no paging in the API: restrict the (otherwise multi-MB) result by date instead
            params["filter"] = f"creation:>{datetime.now(UTC).year - 2}-12"
        rows = await self._get_rows(f"{INDEX_URL}/citations/{quote(oc_id, safe=':/')}", params)
        return self._rows_to_edges(rows or [], "cited_by", "citing", limit)

    def _rows_to_edges(
        self, rows: list[dict[str, Any]], label: str, other_side: str, limit: int
    ) -> list[dict[str, Any]]:
        """Citation rows -> relationship dicts for the id on ``other_side`` of each row."""
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            ids = _parse_ids(row.get(other_side))
            doi = (ids.get("doi") or [""])[0].lower()
            pmid = (ids.get("pmid") or [""])[0]
            omid = (ids.get("omid") or [""])[0]
            related = doi or (f"pmid:{pmid}" if pmid else (f"omid:{omid}" if omid else ""))
            if not related or related in seen:
                continue
            seen.add(related)
            timespan = str(row.get("timespan") or "")
            edges.append(
                {
                    "relation_label": label,
                    "related_id": related,
                    "related_name": related,
                    "source": "OPENCITATIONS",
                    "oci": row.get("oci"),
                    "creation": row.get("creation"),
                    "timespan": timespan,
                    "timespan_years": _duration_years(timespan),
                    "journal_self_citation": str(row.get("journal_sc")).lower() == "yes",
                    "author_self_citation": str(row.get("author_sc")).lower() == "yes",
                    "other_ids": ids,
                }
            )
            if len(edges) >= limit:
                break
        return edges

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mapping(from_id: str, to_source: str, to_id: str, kind: str, conf: float) -> dict:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "OPENCITATIONS",
            "toSource": to_source,
            "mappingType": kind,
            "confidence": conf,
        }

    @staticmethod
    def _parse_venue(text: Any) -> tuple[str, list[str]]:
        """``"Nature [issn:0028-0836 omid:br/06]"`` -> ``("Nature", ["0028-0836"])``."""
        raw = str(text or "").strip()
        match = _VENUE_RE.match(raw)
        if not match:
            return raw, []
        return match.group(1).strip(), _parse_ids(match.group(2)).get("issn", [])

    @staticmethod
    def _parse_people(text: Any) -> list[str]:
        """``"Zhou, Peng [omid:ra/06..]; Yang, X [orcid:..]"`` -> ``["Zhou, Peng", ...]``."""
        names = (re.sub(r"\s*\[[^\]]*\]", "", part).strip() for part in str(text or "").split(";"))
        return [n for n in names if n]

    def _to_concept(
        self,
        oc_id: str,
        meta: dict[str, Any],
        citations: int | None,
        references: int | None,
    ) -> UnifiedConcept:
        """Build the work concept; primary id is the DOI when known, else the queried id."""
        ids = _parse_ids(meta.get("id"))
        doi = (ids.get("doi") or [""])[0].lower()
        primary = doi or (oc_id.split(":", 1)[1] if oc_id.startswith("doi:") else oc_id)
        title = str(meta.get("title") or "").strip() or primary
        concept = self._create_concept(primary, title, ConceptType.CITATION)
        venue, issns = self._parse_venue(meta.get("venue"))
        pub_date = str(meta.get("pub_date") or "")
        work_type = str(meta.get("type") or "")
        publisher = re.sub(r"\s*\[[^\]]*\]", "", str(meta.get("publisher") or "")).strip()
        if concept.categories is not None:
            if work_type:
                concept.categories.append(f"type:{work_type}")
            if venue:
                concept.categories.append(f"venue:{venue}")
            if pub_date[:4]:
                concept.categories.append(f"year:{pub_date[:4]}")
        pmid = (ids.get("pmid") or [""])[0]
        if pmid:
            concept.add_identifier(
                KnowledgeSource.EUROPEPMC, pmid, title, f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            )
        concept.confidence_score = 0.85
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.OPENCITATIONS] = {
                "ids": ids,
                "title": title,
                "authors": self._parse_people(meta.get("author")),
                "pub_date": pub_date,
                "venue": venue,
                "issn": issns,
                "volume": meta.get("volume"),
                "issue": meta.get("issue"),
                "page": meta.get("page"),
                "type": work_type,
                "publisher": publisher,
                "citation_count": citations,
                "reference_count": references,
                "license": "CC0 1.0",
                "note": (
                    "Counts come from the open DOI-to-DOI citation index and lag behind "
                    "publishers; they are lower bounds."
                ),
            }
        return concept
