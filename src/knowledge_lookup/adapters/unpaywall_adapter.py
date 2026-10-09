"""
Unpaywall Knowledge Source Adapter

Unpaywall (OurResearch) tells, for a DOI, whether a free legal full-text copy exists and where:
open access status (``gold``, ``hybrid``, ``bronze``, ``green`` or ``closed``), the best copy
and every other copy found, with its version, licence and host (publisher or repository).
Concepts are *works* identified by DOI (bare, ``doi:`` and ``https://doi.org/`` forms).

API (https://unpaywall.org/products/api; DOI object schema: https://unpaywall.org/data-format)::

    GET https://api.unpaywall.org/v2/<doi>?email=<contact address>
    GET https://api.unpaywall.org/v2/search?query=<q>&is_oa=<bool>&page=<n>&email=<...>

NOT LIVE-VERIFIED against a successful response. The API demands an ``email`` parameter and
answers HTTP 422 ``Email address required in API call`` without it (verified live
2026-10-09, for the DOI and the search endpoint alike). The address must be a contact address
the *user* chooses; this adapter was written without one, so the response parsing below
follows the documented DOI-object schema and is tested with fixtures built from it. To check
it against the live service, run ``UNPAYWALL_EMAIL=you@your.org knowledge-lookup check
UNPAYWALL``. Unverified points: the exact search response envelope (parsed defensively: a
list ``results`` whose entries hold the DOI object under ``response``, or are DOI objects),
the page size of the search endpoint, and the 404 body for unknown DOIs.

The e-mail address:

* is read **only** from the environment variable ``UNPAYWALL_EMAIL`` (or, as a fallback,
  ``config.get_api_key("unpaywall")``, i.e. ``UNPAYWALL_API_KEY`` / the ``api_keys`` setting);
  it is never defaulted, never taken from git, system or application settings, and
  ``is_available()`` is ``False`` while none is set;
* is sent only as the ``email`` query parameter of the request, and is never logged: HTTP
  client errors quote the full request URL, so failures are logged by exception type and
  status code only.

Usage terms: free; "please limit use to 100,000 calls per day" (a request, not a hard
quota; for more, download the data snapshot). The adapter counts its own calls per UTC day
and refuses further requests after 100,000, spaces requests by 0.2 s, and caches the DOI
record per adapter instance so that details, relationships and mappings of one DOI cost a
single call. The data are CC0; coverage is Crossref DOIs. ``license`` is the licence found
on that particular copy and is often missing even for open copies; ``oa_status`` and
``is_oa`` describe the work, not a particular copy.
"""

import logging
import os
import re
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._vocab_common import Spacer

logger = logging.getLogger(__name__)

BASE_URL = "https://api.unpaywall.org/v2"
EMAIL_ENV = "UNPAYWALL_EMAIL"
DAILY_LIMIT = 100_000  # documented request: "limit use to 100,000 calls per day"
MIN_INTERVAL = 0.2
DEFAULT_REL_LIMIT = 25
MAX_LOCATIONS = 10
MAX_AUTHORS = 10
CACHE_SIZE = 64
OA_STATUSES = ("gold", "hybrid", "bronze", "green", "closed")

_DOI_RE = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _utc_today():
    return datetime.now(UTC).date()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _describe(error: BaseException) -> str:
    """Log text for *error* that cannot contain the request URL (and so the e-mail)."""
    status = getattr(error, "status", None)
    return f"{type(error).__name__}" + (f" (HTTP {status})" if status else "")


class UnpaywallAdapter(KnowledgeSourceAdapter):
    """Adapter for Unpaywall open access locations (needs ``UNPAYWALL_EMAIL``; CC0 data)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self._spacer = Spacer(MIN_INTERVAL)
        self._day = _utc_today()
        self._calls_today = 0
        self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.UNPAYWALL

    def _email(self) -> str | None:
        """The user's contact address from ``UNPAYWALL_EMAIL`` / the api-key setting, or None."""
        value = (os.getenv(EMAIL_ENV) or self.config.get_api_key("unpaywall") or "").strip()
        return value if _EMAIL_RE.match(value) else None

    def is_available(self) -> bool:
        return self._email() is not None

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> str | None:
        """The lower-case DOI in *concept_id* (bare, ``doi:`` or ``https://doi.org/``), or None."""
        match = _DOI_RE.match((concept_id or "").strip())
        return match.group(1).lower().rstrip("/") if match else None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _budget_left(self) -> bool:
        today = _utc_today()
        if today != self._day:
            self._day, self._calls_today = today, 0
        if self._calls_today >= DAILY_LIMIT:
            logger.warning("Unpaywall: the 100,000 calls/day request limit is used up")
            return False
        self._calls_today += 1
        return True

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Spaced GET with the e-mail parameter; ``None`` on any failure (never logs the URL)."""
        email = self._email()
        if email is None:
            logger.warning(f"Unpaywall needs a contact e-mail: set {EMAIL_ENV}")
            return None
        if not self._budget_left():
            return None
        try:
            await self._spacer.wait()
            return await self._make_request(
                f"{BASE_URL}/{path}", params={**(params or {}), "email": email}
            )
        except Exception as e:
            # str(e) of an aiohttp error contains the request URL, i.e. the e-mail address
            if getattr(e, "status", None) == 404:
                logger.debug("Unpaywall: DOI not found")
            else:
                logger.warning(f"Unpaywall request failed: {_describe(e)}")
            return None

    async def _record(self, doi: str) -> dict[str, Any] | None:
        """DOI object for *doi*, cached per adapter instance (misses are not cached)."""
        if doi in self._records:
            self._records.move_to_end(doi)
            return self._records[doi]
        data = await self._get(quote(doi, safe="/"))
        if not (isinstance(data, dict) and not data.get("error") and data.get("doi")):
            return None
        self._records[doi] = data
        while len(self._records) > CACHE_SIZE:
            self._records.popitem(last=False)
        return data

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_concepts(
        self, query: str, limit: int = 20, open_access_only: bool | None = None
    ) -> list[UnifiedConcept]:
        """Title search through ``/v2/search`` (not live-verified; see module doc).

        A DOI as the query resolves directly to that work. ``open_access_only`` maps to the
        endpoint's ``is_oa`` filter (``True``: only OA works, ``False``: only closed ones).
        """
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            doi = self.parse_id(query)
            if doi:
                concept = await self.get_concept_details(doi)
                return [concept] if concept else []
            params: dict[str, Any] = {"query": query}
            if open_access_only is not None:
                params["is_oa"] = str(bool(open_access_only)).lower()
            data = await self._get("search", params)
            entries = data.get("results") if isinstance(data, dict) else None
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for entry in entries if isinstance(entries, list) else []:
                item = entry.get("response") if isinstance(entry, dict) else None
                if not isinstance(item, dict):
                    item = entry if isinstance(entry, dict) and entry.get("doi") else None
                concept = self._work_to_concept(item) if item else None
                if concept is not None and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
            return concepts[:limit]
        except Exception as e:
            logger.error(f"Unpaywall search_concepts failed: {_describe(e)}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """The work with this DOI, with OA status, best location and (capped) all locations."""
        try:
            doi = self.parse_id(concept_id)
            if doi is None:
                return None
            record = await self._record(doi)
            return self._work_to_concept(record) if record else None
        except Exception as e:
            logger.error(f"Unpaywall get_concept_details failed: {_describe(e)}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = DEFAULT_REL_LIMIT
    ) -> list[dict[str, Any]]:
        """``available_at`` each OA copy (best first, at most ``limit``), ``published_in`` the
        journal and ``published_by`` the publisher.

        An ``available_at`` edge's ``related_id`` is the copy's URL; ``version``
        (``submittedVersion`` / ``acceptedVersion`` / ``publishedVersion``), ``license`` (as
        found on that copy, often ``None``), ``host_type`` (``publisher`` / ``repository``),
        ``repository_institution`` and ``is_best`` are reported verbatim. ``limit=0`` -> ``[]``.
        """
        try:
            limit = max(0, int(limit))
            doi = self.parse_id(concept_id)
            if doi is None or limit == 0:
                return []
            record = await self._record(doi)
            if not record:
                return []
            edges: list[dict[str, Any]] = []
            seen: set[str] = set()
            for loc in self._locations(record):
                url = loc.get("url_for_landing_page") or loc.get("url") or loc.get("url_for_pdf")
                if not url or url in seen or len(seen) >= limit:
                    continue
                seen.add(url)
                edges.append(
                    {
                        "relation_label": "available_at",
                        "related_id": url,
                        "related_name": loc.get("repository_institution")
                        or f"{loc.get('host_type') or 'unknown'} copy",
                        "source": "UNPAYWALL",
                        **self._location_summary(loc),
                    }
                )
            issns = self._issns(record)
            journal = _clean(record.get("journal_name"))
            if journal or issns:
                issn_l = record.get("journal_issn_l") or (issns[0] if issns else None)
                edges.append(
                    {
                        "relation_label": "published_in",
                        "related_id": f"ISSN:{issn_l}" if issn_l else journal,
                        "related_name": journal or f"ISSN:{issn_l}",
                        "source": "UNPAYWALL",
                        "issns": issns,
                        "journal_is_oa": record.get("journal_is_oa"),
                        "journal_is_in_doaj": record.get("journal_is_in_doaj"),
                    }
                )
            publisher = _clean(record.get("publisher"))
            if publisher:
                edges.append(
                    {
                        "relation_label": "published_by",
                        "related_id": publisher,
                        "related_name": publisher,
                        "source": "UNPAYWALL",
                    }
                )
            return edges
        except Exception as e:
            logger.warning(f"Unpaywall get_relationships failed: {_describe(e)}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """The DOI itself plus the journal's ISSN-L and ISSNs."""
        try:
            doi = self.parse_id(concept_id)
            if doi is None:
                return []
            record = await self._record(doi)
            if not record:
                return []
            pairs = [("DOI", str(record.get("doi") or doi).lower())]
            if record.get("journal_issn_l"):
                pairs.append(("ISSN-L", record["journal_issn_l"]))
            pairs += [("ISSN", i) for i in self._issns(record)]
            return [
                {
                    "fromId": doi,
                    "toId": value,
                    "fromSource": "UNPAYWALL",
                    "toSource": label,
                    "mappingType": "exact",
                    "confidence": 1.0,
                }
                for label, value in dict.fromkeys(pairs)
            ]
        except Exception as e:
            logger.warning(f"Unpaywall get_mappings failed: {_describe(e)}")
            return []

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _issns(record: dict[str, Any]) -> list[str]:
        """``journal_issns`` is a comma-separated string in the documented schema."""
        raw = record.get("journal_issns")
        parts = raw if isinstance(raw, list) else str(raw or "").split(",")
        return [p.strip() for p in parts if str(p).strip()]

    @staticmethod
    def _locations(record: dict[str, Any]) -> list[dict[str, Any]]:
        """All OA locations, the best one first, without duplicates."""
        best = record.get("best_oa_location")
        locations = [loc for loc in record.get("oa_locations") or [] if isinstance(loc, dict)]
        ordered = ([best] if isinstance(best, dict) else []) + locations
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for loc in ordered:
            key = loc.get("url") or loc.get("url_for_landing_page") or loc.get("url_for_pdf")
            if key and key not in seen:
                seen.add(key)
                out.append(loc)
        return out

    @staticmethod
    def _location_summary(loc: dict[str, Any]) -> dict[str, Any]:
        return {
            "url": loc.get("url"),
            "url_for_pdf": loc.get("url_for_pdf"),
            "url_for_landing_page": loc.get("url_for_landing_page"),
            "version": loc.get("version"),
            "license": loc.get("license"),
            "host_type": loc.get("host_type"),
            "is_best": loc.get("is_best"),
            "repository_institution": loc.get("repository_institution"),
            "oa_date": loc.get("oa_date"),
            "evidence": loc.get("evidence"),
        }

    def _work_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a DOI object (type CITATION)."""
        try:
            doi = _clean(item.get("doi")).lower()
            if not doi:
                return None
            title = _clean(item.get("title")) or doi
            concept = self._create_concept(doi, title, ConceptType.CITATION)
            status = item.get("oa_status")
            locations = self._locations(item)
            best = item.get("best_oa_location")
            journal = _clean(item.get("journal_name")) or None
            if concept.semantic_types is not None and item.get("genre"):
                concept.semantic_types.append(str(item["genre"]))
            if concept.categories is not None:
                if item.get("year"):
                    concept.categories.append(f"year:{item['year']}")
                if journal:
                    concept.categories.append(f"journal:{journal}")
                if status:
                    concept.categories.append(f"oa_status:{status}")
            concept.add_identifier(
                KnowledgeSource.EUROPEPMC, f"DOI:{doi}", title, f"https://doi.org/{doi}"
            )
            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.UNPAYWALL] = {
                    "doi": doi,
                    "title": title,
                    "genre": item.get("genre"),
                    "year": item.get("year"),
                    "published_date": item.get("published_date"),
                    "journal": journal,
                    "journal_issns": self._issns(item),
                    "journal_issn_l": item.get("journal_issn_l"),
                    "journal_is_oa": item.get("journal_is_oa"),
                    "journal_is_in_doaj": item.get("journal_is_in_doaj"),
                    "publisher": item.get("publisher"),
                    "is_oa": item.get("is_oa"),
                    "oa_status": status,
                    "has_repository_copy": item.get("has_repository_copy"),
                    "is_paratext": item.get("is_paratext"),
                    "data_standard": item.get("data_standard"),
                    "best_oa_location": (
                        self._location_summary(best) if isinstance(best, dict) else None
                    ),
                    "oa_locations": [
                        self._location_summary(loc) for loc in locations[:MAX_LOCATIONS]
                    ],
                    "n_oa_locations": len(locations),
                    "n_embargoed_locations": len(item.get("oa_locations_embargoed") or []),
                    "authors": [
                        {
                            "name": _clean(f"{a.get('given') or ''} {a.get('family') or ''}")
                            or a.get("name"),
                            "orcid": a.get("ORCID"),
                        }
                        for a in (item.get("z_authors") or [])[:MAX_AUTHORS]
                        if isinstance(a, dict)
                    ],
                    "updated": item.get("updated"),
                    "url": f"https://doi.org/{doi}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting Unpaywall record: {_describe(e)}")
            return None
