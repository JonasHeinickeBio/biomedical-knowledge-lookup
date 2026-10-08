"""
bioRxiv / medRxiv Knowledge Source Adapter

bioRxiv and medRxiv (operated by openRxiv) are the main preprint servers for biology and for
health science; many Long COVID and ME/CFS papers appear on medRxiv months before the journal
version. **Preprints are not peer reviewed**: every concept carries
``source_data["peer_reviewed"] = False`` and a notice saying so. Metadata are served by the
openRxiv "content detail" API; abstracts and full texts are under the licence chosen by the
authors (``license`` field: ``cc_by``, ``cc0``, ``cc_no`` = all rights reserved ...).

API (verified live, keyless, JSON; ``https://api.biorxiv.org``)::

    GET /details/{server}/{doi}                         all versions of one preprint
    GET /details/{server}/{YYYY-MM-DD}/{YYYY-MM-DD}/{cursor}[?category=infectious_diseases]
    GET /pubs/{server}/{doi}                            journal version of a preprint
    GET /publisher/{prefix}/{start}/{end}/{cursor}      preprints published by a publisher

``server`` is ``biorxiv`` or ``medrxiv``. Quirks worth knowing (verified, several differ from
the official documentation):

* **There is no free-text search.** The API only lists by DOI or by date window. The adapter
  therefore searches through Europe PMC's keyless REST API (``SRC:PPR`` preprint records
  restricted to ``PUBLISHER:bioRxiv|medRxiv``; 0.3 s, relevance ranked, abstracts included),
  which indexes every bioRxiv/medRxiv preprint. If Europe PMC is unreachable the adapter
  falls back to scanning a recent date window of the bioRxiv API and filtering title,
  abstract and category locally (capped; see :data:`SCAN_MAX_PAGES`).
* **New DOI prefix:** since 2026 medRxiv preprints are minted under ``10.64898/`` instead of
  ``10.1101/`` (e.g. ``10.64898/2026.09.22.26363331``). Nothing here assumes a prefix.
* ``details/{server}/{doi}`` returns **one row per version** (oldest first); ``published`` is
  the journal DOI or the string ``"NA"``. A DOI queried against the wrong server answers
  ``{"status": "no posts found"}`` (HTTP 200), so both servers are tried (medRxiv first for
  the 8-digit medRxiv numbering).
* **HTTP 500 is intermittent:** the same URL can fail and then succeed seconds later (a first
  probe of a medRxiv date interval returned 500 and the identical URL later returned 200).
  A few records fail consistently on ``details`` while ``pubs`` still works, so the adapter
  falls back to ``pubs`` for them. The shared retry handles transient 500s.
* **Page size is 30** (the documentation says 100) and the cursor is an *offset* into the
  window; a cursor past ``total`` is a 500. The recent-N forms (``details/medrxiv/10/0``,
  ``.../2d/0``) documented as "last N posts / days" answer
  ``"Both dates must be in yyyy-mm-dd format"`` and are not used.
* ``type`` is normally "new results" / "confirmatory results" but newer rows show odd values
  (``PUBLISHAHEADOFPRINT``); it is passed through.
* No rate limit is documented; requests are spaced by >= 0.35 s (< 3 req/s).
"""

import asyncio
import html
import logging
import re
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.biorxiv.org"
EPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SERVERS: tuple[str, ...] = ("biorxiv", "medrxiv")
SERVER_LABELS = {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}

MAX_RESULTS = 100  # cap for one search (Europe PMC pageSize)
SCAN_DAYS = 7  # default fallback window of the local scan
SCAN_MAX_PAGES = 10  # pages of 30 fetched per server by one local scan (<= 300 rows)
REQUEST_INTERVAL = 0.35  # seconds between requests (<= 3 req/s)

NOT_PEER_REVIEWED = (
    "Preprint: not peer reviewed. Findings are preliminary and may change or be withdrawn."
)
LICENSES = {
    "cc_no": "No Creative Commons licence (all rights reserved by the author)",
    "cc0": "CC0 1.0",
    "cc_by": "CC BY 4.0",
    "cc_by_nd": "CC BY-ND 4.0",
    "cc_by_nc": "CC BY-NC 4.0",
    "cc_by_nc_nd": "CC BY-NC-ND 4.0",
    "cc_by_sa": "CC BY-SA 4.0",
}

_DOI_RE = re.compile(r"(10\.\d{4,9}/[A-Za-z0-9._\-()]+)", re.IGNORECASE)
_URL_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|https?://(?:www\.)?(?:bio|med)rxiv\.org/content/"
    r"(?:early/\d{4}/\d{2}/\d{2}/)?|doi:\s*)",
    re.IGNORECASE,
)
#: ``<doi>[v<n>][.full|.pdf|...]`` as it appears in site URLs
_VERSION_RE = re.compile(
    r"^(.*?)(?:v(\d+))?(?:\.(?:full|abstract|pdf|article-info|supplementary-material))*$"
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()


def _split_authors(text: Any) -> list[str]:
    """bioRxiv ``authors`` is one ``"Last, F.; Last2, G."`` string."""
    return [a.strip() for a in str(text or "").split(";") if a.strip()]


def _version_key(row: dict[str, Any]) -> int:
    try:
        return int(row.get("version") or 0)
    except (TypeError, ValueError):
        return 0


class BioRxivAdapter(KnowledgeSourceAdapter):
    """Adapter for bioRxiv and medRxiv preprints (keyless; preprints are not peer reviewed)."""

    min_request_timeout = 60.0

    def __init__(self, config: Any):
        super().__init__(config)
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.BIORXIV

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str, int | None] | None:
        """Preprint DOI (and optional version) from a DOI, ``doi:`` form or site URL.

        ``10.1101/2020.01.22.914952v2``, ``doi:10.64898/2026.09.22.26363331`` and
        ``https://www.medrxiv.org/content/10.1101/2021.01.27.21250617v1.full`` all work.
        Returns ``(doi, version | None)`` or ``None`` when no DOI is found.
        """
        text = _URL_RE.sub("", (concept_id or "").strip())
        match = _DOI_RE.match(re.split(r"[?#]", text, maxsplit=1)[0])
        if not match:
            return None
        parts = _VERSION_RE.match(match.group(1))
        if parts is None or not parts.group(1):  # pragma: no cover - the pattern always matches
            return None
        return parts.group(1).lower(), int(parts.group(2)) if parts.group(2) else None

    @staticmethod
    def _server_order(doi: str) -> tuple[str, ...]:
        """medRxiv numbers its preprints with 8 digits (``...21250617``); bioRxiv with 6."""
        tail = doi.rsplit(".", 1)[-1]
        return ("medrxiv", "biorxiv") if re.fullmatch(r"\d{8}", tail) else SERVERS

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, bool]:
        """Throttled GET -> ``(json, failed)``. ``failed`` is True on HTTP/network errors."""
        try:
            async with self._lock:
                wait = self._last_request + REQUEST_INTERVAL - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    data = await self._make_request(url, params=params)
                finally:
                    self._last_request = time.monotonic()
        except Exception as e:
            if getattr(e, "status", None) != 404:
                logger.warning(f"bioRxiv request failed for {url}: {e}")
            return None, True
        return (data, False) if isinstance(data, dict) else (None, True)

    @staticmethod
    def _rows(data: dict[str, Any] | None) -> list[dict[str, Any]]:
        """``collection`` rows of a bioRxiv response ("no posts found" -> empty)."""
        rows = (data or {}).get("collection")
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []

    async def _fetch_versions(self, doi: str) -> list[dict[str, Any]]:
        """All versions of a preprint, oldest first; ``[]`` when unknown.

        Falls back to the ``pubs`` endpoint when ``details`` errors for a server (a few
        records fail consistently with HTTP 500); that yields a single partial row.
        """
        errored: list[str] = []
        for server in self._server_order(doi):
            data, failed = await self._get(f"{BASE_URL}/details/{server}/{quote(doi, safe='/')}")
            rows = self._rows(data)
            if rows:
                return sorted(rows, key=_version_key)
            if failed:
                errored.append(server)
        for server in errored:
            data, _ = await self._get(f"{BASE_URL}/pubs/{server}/{quote(doi, safe='/')}")
            for row in self._rows(data):
                if str(row.get("preprint_doi") or "").lower() == doi:
                    return [self._pubs_to_row(row, server)]
        return []

    @staticmethod
    def _pubs_to_row(row: dict[str, Any], server: str) -> dict[str, Any]:
        """Shape a ``pubs`` row like a ``details`` row (flagged ``partial``)."""
        return {
            "doi": str(row.get("preprint_doi") or "").lower(),
            "title": row.get("preprint_title"),
            "authors": row.get("preprint_authors"),
            "author_corresponding": row.get("preprint_author_corresponding"),
            "author_corresponding_institution": row.get(
                "preprint_author_corresponding_institution"
            ),
            "date": row.get("preprint_date"),
            "category": row.get("preprint_category"),
            "abstract": row.get("preprint_abstract"),
            "published": row.get("published_doi") or "NA",
            "server": row.get("preprint_platform") or SERVER_LABELS.get(server, server),
            "version": None,
            "partial": True,
        }

    async def _fetch_published(self, doi: str, server: str) -> dict[str, Any] | None:
        """``pubs`` row (journal name, publication date) of a preprint, if published."""
        data, _ = await self._get(f"{BASE_URL}/pubs/{server}/{quote(doi, safe='/')}")
        for row in self._rows(data):
            if str(row.get("preprint_doi") or "").lower() == doi and row.get("published_doi"):
                return row
        return None

    async def _fetch_europepmc(self, doi: str) -> dict[str, Any] | None:
        """Europe PMC preprint record (``SRC:PPR``) for a DOI: carries the published PMID."""
        data, _ = await self._get(
            EPMC_URL,
            {"query": f'DOI:"{doi}" AND SRC:PPR', "format": "json", "resultType": "core"},
        )
        results = ((data or {}).get("resultList") or {}).get("result")
        return results[0] if isinstance(results, list) and results else None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_preprints(
        self,
        query: str,
        limit: int = 20,
        server: str | None = None,
        sort: str | None = None,
        start: str | None = None,
        end: str | None = None,
        category: str | None = None,
    ) -> list[UnifiedConcept]:
        """Free-text preprint search.

        Default route: Europe PMC (``server`` = ``biorxiv`` / ``medrxiv`` / ``None`` for both;
        ``sort="date"`` for newest first). Passing ``start`` and/or ``end`` (``YYYY-MM-DD``)
        instead scans that date window of the bioRxiv API and filters locally (all query
        words must occur in title, abstract or category; at most
        :data:`SCAN_MAX_PAGES` pages of 30 per server; ``category`` is applied server-side,
        e.g. ``"infectious_diseases"``). The scan is also the fallback when Europe PMC fails.
        """
        try:
            limit = max(0, min(int(limit), MAX_RESULTS))
            query = (query or "").strip()
            if limit == 0 or not query:
                return []
            if server and server.lower() not in SERVERS:
                return []
            servers = (server.lower(),) if server else SERVERS
            if start or end:
                return await self._scan_window(query, limit, servers, start, end, category)
            concepts = await self._search_europepmc(query, limit, servers, sort)
            if concepts is None:
                logger.info("Europe PMC unavailable; scanning recent bioRxiv window instead")
                return await self._scan_window(query, limit, servers, None, None, category)
            return concepts
        except Exception as e:
            logger.error(f"bioRxiv search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search preprints; a DOI or biorxiv.org/medrxiv.org URL resolves to that preprint."""
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.parse_id(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            return await self.search_preprints(query, limit)
        except Exception as e:
            logger.error(f"bioRxiv search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Preprint by DOI (latest version, or ``...v2`` for a specific version).

        ``source_data`` lists every version with its date and carries the journal DOI when
        the preprint has been published.
        """
        try:
            parsed = self.parse_id(concept_id)
            if not parsed:
                return None
            doi, version = parsed
            rows = await self._fetch_versions(doi)
            if not rows:
                return None
            if version is None:
                return self._row_to_concept(rows[-1], rows)
            match = next((r for r in rows if _version_key(r) == version), None)
            return self._row_to_concept(match, rows) if match else None
        except Exception as e:
            logger.error(f"bioRxiv get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Preprint -> journal article (``is_preprint_of``) and earlier versions.

        * ``is_preprint_of``: ``related_id`` is the journal DOI (``published`` field);
          ``related_name`` is the journal title and ``published_date`` the journal date when
          the ``pubs`` endpoint knows them. The published PMID, when Europe PMC links one,
          is added as ``related_pmid``.
        * ``has_earlier_version``: one edge per older version (``<doi>v<n>``) with its date.
        """
        try:
            parsed = self.parse_id(concept_id)
            if not parsed:
                return []
            doi, _ = parsed
            rows = await self._fetch_versions(doi)
            if not rows:
                return []
            latest = rows[-1]
            edges: list[dict[str, Any]] = []
            published = str(latest.get("published") or "").strip()
            if published and published.upper() != "NA":
                server = self._server_key(latest)
                pub_row = await self._fetch_published(doi, server)
                epmc = await self._fetch_europepmc(doi)
                edge: dict[str, Any] = {
                    "relation_label": "is_preprint_of",
                    "related_id": published.lower(),
                    "related_name": str((pub_row or {}).get("published_journal") or published),
                    "source": "BIORXIV",
                    "published_date": (pub_row or {}).get("published_date"),
                }
                pmid = self._published_pmid(epmc)
                if pmid:
                    edge["related_pmid"] = pmid
                edges.append(edge)
            for row in rows[:-1]:
                number = row.get("version")
                if number is None:
                    continue
                edges.append(
                    {
                        "relation_label": "has_earlier_version",
                        "related_id": f"{doi}v{number}",
                        "related_name": f"{_clean(row.get('title'))} (v{number})",
                        "source": "BIORXIV",
                        "version": int(number) if str(number).isdigit() else number,
                        "version_date": row.get("date"),
                    }
                )
            return edges
        except Exception as e:
            logger.warning(f"bioRxiv get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Preprint DOI -> itself (``DOI``), the journal DOI and, when Europe PMC links the
        published article, its PMID. The bioRxiv API itself exposes no PMID.
        """
        try:
            parsed = self.parse_id(concept_id)
            if not parsed:
                return []
            doi, _ = parsed
            rows = await self._fetch_versions(doi)
            if not rows:
                return []
            latest = rows[-1]
            mappings = [self._mapping(doi, "DOI", doi, "exact", 1.0)]
            published = str(latest.get("published") or "").strip()
            if published and published.upper() != "NA":
                mappings.append(
                    self._mapping(doi, "DOI", published.lower(), "published_version", 1.0)
                )
                pmid = self._published_pmid(await self._fetch_europepmc(doi))
                if pmid:
                    mappings.append(self._mapping(doi, "PubMed", pmid, "published_version", 1.0))
            return mappings
        except Exception as e:
            logger.warning(f"bioRxiv get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Search backends
    # ------------------------------------------------------------------

    async def _search_europepmc(
        self, query: str, limit: int, servers: tuple[str, ...], sort: str | None
    ) -> list[UnifiedConcept] | None:
        """Europe PMC preprint search; ``None`` when the request failed (caller falls back)."""
        publishers = " OR ".join(f'PUBLISHER:"{SERVER_LABELS[s]}"' for s in servers)
        params: dict[str, Any] = {
            "query": f"({query}) AND SRC:PPR AND ({publishers})",
            "format": "json",
            "resultType": "core",
            "pageSize": limit,
        }
        if sort == "date":
            params["sort"] = "P_PDATE_D desc"
        data, failed = await self._get(EPMC_URL, params)
        if failed or data is None:
            return None
        results = (data.get("resultList") or {}).get("result")
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for item in results if isinstance(results, list) else []:
            concept = self._epmc_to_concept(item)
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concepts.append(concept)
        logger.info(f"bioRxiv (Europe PMC) search for '{query}' returned {len(concepts)}")
        return concepts[:limit]

    async def _scan_window(
        self,
        query: str,
        limit: int,
        servers: tuple[str, ...],
        start: str | None,
        end: str | None,
        category: str | None,
    ) -> list[UnifiedConcept]:
        """Scan a date window of the bioRxiv API and keep rows matching every query word."""
        today = datetime.now(UTC).date()
        try:
            end_date = date.fromisoformat(end) if end else today
            start_date = (
                date.fromisoformat(start) if start else end_date - timedelta(days=SCAN_DAYS)
            )
        except ValueError:
            logger.warning(f"bioRxiv scan: invalid date window {start!r}..{end!r}")
            return []
        words = [w for w in re.split(r"\s+", query.lower()) if w]
        best: dict[str, dict[str, Any]] = {}
        for server in servers:
            cursor = 0
            for _ in range(SCAN_MAX_PAGES):
                params = {"category": category} if category else None
                url = f"{BASE_URL}/details/{server}/{start_date}/{end_date}/{cursor}"
                data, failed = await self._get(url, params)
                rows = self._rows(data)
                if failed or not rows:
                    break
                for row in rows:
                    haystack = " ".join(
                        _clean(str(row.get(k) or "")) for k in ("title", "abstract", "category")
                    ).lower()
                    doi = str(row.get("doi") or "").lower()
                    if doi and all(w in haystack for w in words):
                        if doi not in best or _version_key(row) >= _version_key(best[doi]):
                            best[doi] = row
                cursor += len(rows)
                total = str(((data or {}).get("messages") or [{}])[0].get("total") or "")
                if (total.isdigit() and cursor >= int(total)) or len(best) >= limit:
                    break
        ordered = sorted(best.values(), key=lambda r: str(r.get("date") or ""), reverse=True)
        return [c for c in (self._row_to_concept(r, [r]) for r in ordered[:limit]) if c]

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mapping(from_id: str, to_source: str, to_id: str, kind: str, conf: float) -> dict:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "BIORXIV",
            "toSource": to_source,
            "mappingType": kind,
            "confidence": conf,
        }

    @staticmethod
    def _server_key(row: dict[str, Any]) -> str:
        server = str(row.get("server") or "").lower()
        return server if server in SERVERS else "biorxiv"

    @staticmethod
    def _published_pmid(record: dict[str, Any] | None) -> str | None:
        """PMID of the journal article that Europe PMC links as "Preprint of"."""
        corrections = ((record or {}).get("commentCorrectionList") or {}).get("commentCorrection")
        for item in corrections if isinstance(corrections, list) else []:
            if (
                isinstance(item, dict)
                and str(item.get("type") or "").lower() == "preprint of"
                and item.get("source") == "MED"
                and item.get("id")
            ):
                return str(item["id"])
        return None

    def _build(
        self,
        doi: str,
        title: str,
        data: dict[str, Any],
        abstract: str,
        category: str,
        date_text: str,
        server_label: str,
    ) -> UnifiedConcept:
        """Common concept skeleton for both row sources."""
        concept = self._create_concept(doi, title or doi, ConceptType.CITATION)
        year = date_text[:4]
        if concept.categories is not None:
            concept.categories.append("preprint")
            concept.categories.append("not_peer_reviewed")
            if server_label:
                concept.categories.append(f"server:{server_label}")
            if category:
                concept.categories.append(f"category:{category}")
            if year:
                concept.categories.append(f"year:{year}")
            if data.get("published_doi"):
                concept.categories.append("published_in_journal")
        if abstract and concept.definitions is not None:
            concept.definitions.append(abstract)
        concept.confidence_score = 0.85
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.BIORXIV] = data
        return concept

    def _row_to_concept(
        self, row: dict[str, Any], versions: list[dict[str, Any]]
    ) -> UnifiedConcept | None:
        """Convert one ``details`` row (plus all version rows) to a ``UnifiedConcept``."""
        try:
            doi = str(row.get("doi") or "").strip().lower()
            if not doi:
                return None
            published = str(row.get("published") or "").strip()
            published = "" if published.upper() == "NA" else published.lower()
            server_label = str(row.get("server") or "")
            license_code = str(row.get("license") or "")
            version = row.get("version")
            version_text = f"v{version}" if version not in (None, "") else ""
            server_site = "medrxiv" if server_label.lower() == "medrxiv" else "biorxiv"
            data = {
                "doi": doi,
                "title": _clean(row.get("title")),
                "authors": _split_authors(row.get("authors")),
                "corresponding_author": _clean(row.get("author_corresponding")),
                "corresponding_institution": _clean(row.get("author_corresponding_institution")),
                "category": row.get("category"),
                "date": row.get("date"),
                "version": int(str(version)) if str(version).isdigit() else version,
                "versions": [
                    {"version": v.get("version"), "date": v.get("date")} for v in versions
                ],
                "server": server_label,
                "type": row.get("type"),
                "license": license_code,
                "license_text": LICENSES.get(license_code, license_code),
                "published_doi": published,
                "jats_xml": row.get("jatsxml"),
                "peer_reviewed": False,
                "notice": NOT_PEER_REVIEWED,
                "url": f"https://www.{server_site}.org/content/{doi}{version_text}",
            }
            if row.get("partial"):
                data["partial"] = True  # built from the pubs endpoint (details failed)
            return self._build(
                doi,
                _clean(row.get("title")),
                data,
                _clean(row.get("abstract")),
                str(row.get("category") or ""),
                str(row.get("date") or ""),
                server_label,
            )
        except Exception as e:
            logger.error(f"Error converting bioRxiv row: {e}")
            return None

    def _epmc_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a Europe PMC ``SRC:PPR`` record (search hit) to a ``UnifiedConcept``."""
        try:
            doi = str(item.get("doi") or "").strip().lower()
            if not doi:
                return None
            details = item.get("bookOrReportDetails")
            server_label = str(details.get("publisher") if isinstance(details, dict) else "")
            date_text = str(item.get("firstPublicationDate") or item.get("pubYear") or "")
            server_site = "medrxiv" if server_label.lower() == "medrxiv" else "biorxiv"
            authors = [
                a.strip() for a in str(item.get("authorString") or "").rstrip(".").split(",")
            ]
            data = {
                "doi": doi,
                "title": _clean(item.get("title")),
                "authors": [a for a in authors if a],
                "date": date_text,
                "server": server_label,
                "published_pmid": self._published_pmid(item),
                "cited_by_count": item.get("citedByCount"),
                "europepmc_id": item.get("id"),
                "peer_reviewed": False,
                "notice": NOT_PEER_REVIEWED,
                "url": f"https://www.{server_site}.org/content/{doi}",
                "from_search_index": True,  # call get_concept_details for versions/licence
            }
            return self._build(
                doi,
                _clean(item.get("title")),
                data,
                _clean(item.get("abstractText")),
                "",
                date_text,
                server_label,
            )
        except Exception as e:
            logger.error(f"Error converting Europe PMC preprint record: {e}")
            return None
