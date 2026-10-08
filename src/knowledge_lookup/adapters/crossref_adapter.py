"""
Crossref Knowledge Source Adapter

Crossref is the DOI registration agency for most scholarly journals, books and (via the
``10.1101`` / ``10.64898`` prefixes) bioRxiv and medRxiv preprints. Its REST API serves the
metadata publishers deposit: title, container, authors, reference lists and, importantly for
literature mining, *Crossmark / Retraction Watch update notices* (retractions, corrections,
expressions of concern) and *relations* (preprint <-> article). Metadata are facts and are
released without licence restrictions (CC0, see https://www.crossref.org/documentation/);
abstracts and reference lists are only present when the publisher deposited them, and
abstracts remain the publisher's copyright, so do not redistribute them in bulk.

API (verified live, keyless, JSON)::

    GET https://api.crossref.org/works?query=<text>&rows=<n>&select=<fields>&filter=<k:v,..>
    GET https://api.crossref.org/works/<doi>                (404 + text "Resource not found.")
    GET https://api.crossref.org/works/<doi>/agency         (which agency registered the DOI)

Quirks worth knowing:

* **Rate limits** are announced in response headers: single-work lookups answered
  ``x-rate-limit-limit: 5`` per ``1s`` (``x-api-pool: public-single``), list/search queries
  ``1`` per ``1s`` (``public-array``), and ``x-concurrency-limit: 1`` for both. The adapter
  therefore serialises requests and keeps >= 1.1 s between list queries and >= 0.25 s between
  single-work lookups. The headers do not change when a ``mailto`` is sent from this client;
  Crossref documents a faster "polite pool" for requests that carry one.
* ``mailto`` (polite pool) is sent **only** when the optional environment variable
  ``CROSSREF_MAILTO`` is set. Nothing else is ever put in the request that identifies the
  user.
* ``select=`` is validated strictly: an unknown field is a HTTP 400 (``subtype`` and
  ``institution`` are not selectable on the list route even though they exist on a work).
* The ``updated-by`` field of a work lists the notices that *update* it, each with the notice
  DOI, ``type`` (``retraction``, ``correction``, ``expression_of_concern``, ``withdrawal``,
  ``partial_retraction``, ``erratum``, ``addendum`` ...), the notice date and the origin
  (``publisher`` or ``retraction-watch``). Conversely the notice itself carries ``update-to``.
  Example: Wakefield et al. 1998 (``10.1016/s0140-6736(97)11096-0``) has a retraction (2010)
  and a correction (2004). Absence of a notice is **not** proof that a paper stands: only
  notices that were deposited (or imported from Retraction Watch) are visible here.
* ``relation`` holds ``has-preprint`` / ``is-preprint-of`` / ``has-version`` ... lists. A
  published article can have dozens (figshare supplements), so each type is capped.
* Many ``reference`` entries have no ``DOI`` (only ``unstructured`` text or a few fields).
  They are kept as unstructured references, never dropped.
* Titles and abstracts contain markup (``<i>``, ``<jats:p>``); it is stripped.
"""

import asyncio
import html
import logging
import os
import re
import time
from typing import Any
from urllib.parse import quote, unquote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crossref.org"
WORKS_URL = f"{BASE_URL}/works"
MAILTO_ENV = "CROSSREF_MAILTO"

MAX_ROWS = 100  # cap for one search (Crossref allows 1000; this is a lookup tool)
MAX_REFERENCES = 100  # reference edges returned per work
MAX_RELATIONS = 25  # edges per relation type (some articles have 40+ preprint-like links)
MAX_AUTHORS_KEPT = 15  # authors listed in source_data (the count is always exact)
CACHE_SIZE = 32  # works kept so details + relationships + mappings cost one request

#: Seconds between requests (observed limits: 1/s for lists, 5/s for single works).
LIST_INTERVAL = 1.1
WORK_INTERVAL = 0.25

#: Fields requested for search hits (the full record, incl. references, is only for details).
SEARCH_SELECT = (
    "DOI,title,container-title,issued,author,type,publisher,is-referenced-by-count,"
    "abstract,ISSN,references-count,updated-by,score"
)

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*|urn:doi:)", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

#: Crossmark update type -> relation label from the *updated* work's point of view.
UPDATED_BY_LABELS: dict[str, str] = {
    "retraction": "retracted_by",
    "partial_retraction": "partially_retracted_by",
    "withdrawal": "withdrawn_by",
    "removal": "removed_by",
    "expression_of_concern": "expression_of_concern_by",
    "correction": "corrected_by",
    "corrigendum": "corrected_by",
    "erratum": "corrected_by",
    "addendum": "addendum_by",
    "clarification": "clarified_by",
}
#: ... and from the *notice's* point of view (``update-to``).
UPDATE_TO_LABELS: dict[str, str] = {
    "retraction": "retracts",
    "partial_retraction": "partially_retracts",
    "withdrawal": "withdraws",
    "removal": "removes",
    "expression_of_concern": "expresses_concern_about",
    "correction": "corrects",
    "corrigendum": "corrects",
    "erratum": "corrects",
    "addendum": "adds_to",
    "clarification": "clarifies",
}
#: update types that mean "do not rely on this paper"
RETRACTION_TYPES = frozenset({"retraction", "partial_retraction", "withdrawal", "removal"})
CONCERN_TYPES = frozenset({"expression_of_concern"})
CORRECTION_TYPES = frozenset({"correction", "corrigendum", "erratum", "addendum", "clarification"})

#: Crossref ``relation`` type -> relation label
RELATION_LABELS: dict[str, str] = {
    "has-preprint": "has_preprint",
    "is-preprint-of": "is_preprint_of",
    "has-version": "has_version",
    "is-version-of": "is_version_of",
}

#: ``filters`` keys accepted by :meth:`search_works` -> Crossref filter name
FILTER_FIELDS: dict[str, str] = {
    "type": "type",
    "from_year": "from-pub-date",
    "until_year": "until-pub-date",
    "from_date": "from-pub-date",
    "until_date": "until-pub-date",
    "issn": "issn",
    "prefix": "prefix",
    "has_abstract": "has-abstract",
    "has_references": "has-references",
    "has_update": "has-update",
    "is_update": "is-update",
    "update_type": "update-type",
}


def _clean_text(value: Any) -> str:
    """Strip JATS/HTML tags and collapse whitespace (titles and abstracts carry markup)."""
    if not isinstance(value, str):
        return ""
    return _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()


def _first(value: Any) -> str:
    """First non-empty string of a Crossref list field (``title``, ``container-title``)."""
    if isinstance(value, list):
        for item in value:
            text = _clean_text(item)
            if text:
                return text
        return ""
    return _clean_text(value)


def _date(value: Any) -> str:
    """Crossref ``{"date-parts": [[2020, 2, 3]]}`` -> ``2020-02-03`` (partial dates allowed)."""
    try:
        parts = value["date-parts"][0]
        numbers = [int(p) for p in parts if p is not None]
    except (KeyError, IndexError, TypeError, ValueError):
        return ""
    if not numbers:
        return ""
    return "-".join([f"{numbers[0]:04d}"] + [f"{n:02d}" for n in numbers[1:3]])


def _work_date(work: dict[str, Any]) -> str:
    for key in ("issued", "published", "published-online", "published-print", "created"):
        text = _date(work.get(key))
        if text:
            return text
    return ""


class CrossrefAdapter(KnowledgeSourceAdapter):
    """Adapter for the Crossref REST API (works, retraction notices, preprint relations)."""

    #: lists can take several seconds under load; do not cut them off and retry.
    min_request_timeout = 60.0

    def __init__(self, config: Any):
        super().__init__(config)
        self._lock = asyncio.Lock()  # Crossref allows one concurrent request
        self._last_request = 0.0
        self._work_cache: dict[str, dict[str, Any]] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CROSSREF

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_doi(concept_id: str) -> str | None:
        """``doi:10.x/y`` / ``https://doi.org/10.x/y`` / bare ``10.x/y`` -> lower-cased DOI.

        DOIs are case-insensitive (Crossref returns them lower-cased), so the result is
        lower-cased to make ids comparable. ``None`` when the text is not a DOI.
        """
        text = _DOI_PREFIX_RE.sub("", (concept_id or "").strip())
        text = unquote(text) if "%" in text else text
        return text.lower() if _DOI_RE.match(text) else None

    @staticmethod
    def _work_url(doi: str, suffix: str = "") -> str:
        return f"{WORKS_URL}/{quote(doi, safe='/()-._~:;')}{suffix}"

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _mailto(self) -> dict[str, str]:
        """Polite-pool parameter, only from the optional ``CROSSREF_MAILTO`` env var."""
        value = (os.getenv(MAILTO_ENV) or "").strip()
        return {"mailto": value} if value else {}

    async def _get(
        self, url: str, params: dict[str, Any] | None = None, interval: float = LIST_INTERVAL
    ) -> dict[str, Any] | None:
        """Throttled GET returning the parsed ``message`` object; ``None`` on 404/failure.

        Requests are serialised (Crossref's concurrency limit is 1) and spaced by
        ``interval`` seconds, measured from the end of the previous request.
        """
        query = {**(params or {}), **self._mailto()}
        try:
            async with self._lock:
                wait = self._last_request + interval - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    data = await self._make_request(url, params=query or None)
                finally:
                    self._last_request = time.monotonic()
        except Exception as e:
            if getattr(e, "status", None) != 404:
                logger.warning(f"Crossref request failed for {url}: {e}")
            return None
        if not isinstance(data, dict) or data.get("status") != "ok":
            return None
        message = data.get("message")
        return message if isinstance(message, dict) else None

    async def _fetch_work(self, doi: str, fresh: bool = False) -> dict[str, Any] | None:
        """Full work record (``works/{doi}``), kept in a small per-instance cache."""
        if not fresh and doi in self._work_cache:
            return self._work_cache[doi]
        work = await self._get(self._work_url(doi), interval=WORK_INTERVAL)
        if work is not None:
            if len(self._work_cache) >= CACHE_SIZE:
                self._work_cache.pop(next(iter(self._work_cache)))
            self._work_cache[doi] = work
        return work

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_works(
        self,
        query: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
    ) -> list[UnifiedConcept]:
        """Free-text works search (relevance ranked, at most 100 rows).

        ``filters`` accepts the keys of :data:`FILTER_FIELDS` (``type="journal-article"``,
        ``from_year=2020``, ``has_abstract=True``, ``update_type="retraction"`` ...). ``sort``
        may be ``"published"``, ``"is-referenced-by-count"`` or ``"score"`` (descending).
        """
        try:
            limit = max(0, min(int(limit), MAX_ROWS))
            query = (query or "").strip()
            if limit == 0 or not (query or filters):
                return []
            params: dict[str, Any] = {"rows": limit, "select": SEARCH_SELECT}
            if query:
                params["query"] = query
            clauses = []
            for key, value in (filters or {}).items():
                name = FILTER_FIELDS.get(str(key).lower())
                if name is None or value in (None, ""):
                    continue
                text = str(value).lower() if isinstance(value, bool) else str(value)
                clauses.append(f"{name}:{text}")
            if clauses:
                params["filter"] = ",".join(clauses)
            if sort:
                params["sort"] = sort
                params["order"] = "desc"
            message = await self._get(WORKS_URL, params)
            if message is None:
                return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in message.get("items") or []:
                concept = self._work_to_concept(item)
                if concept is not None and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
            logger.info(f"Crossref search for '{query}' returned {len(concepts)} works")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"Crossref search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search works; a DOI (any accepted form) resolves to that one work."""
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.normalize_doi(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            return await self.search_works(query, limit)
        except Exception as e:
            logger.error(f"Crossref search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Work by DOI (``doi:``, ``https://doi.org/`` or bare form); ``None`` if unknown.

        A DOI registered with another agency (DataCite, mEDRA ...) is not served by
        Crossref's ``works`` route; it is logged with its agency instead of failing silently.
        """
        try:
            doi = self.normalize_doi(concept_id)
            if not doi:
                return None
            work = await self._fetch_work(doi)
            if work is None:
                agency = await self.doi_agency(doi)
                if agency and agency != "crossref":
                    logger.info(f"DOI {doi} is registered with '{agency}', not Crossref")
                return None
            return self._work_to_concept(work, detailed=True)
        except Exception as e:
            logger.error(f"Crossref get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Work -> update notices (the main value), preprint/version links and references.

        Edges, in this order:

        * ``retracted_by`` / ``corrected_by`` / ``expression_of_concern_by`` /
          ``withdrawn_by`` ... (the work's ``updated-by``): ``related_id`` is the notice DOI;
          extra keys ``update_type``, ``notice_date`` and ``asserted_by`` (``publisher`` or
          ``retraction-watch``).
        * ``retracts`` / ``corrects`` ... (``update-to``) when the work is itself a notice.
        * ``has_preprint`` / ``is_preprint_of`` / ``has_version`` / ``is_version_of``
          (``relation``, each capped at 25).
        * ``cites``: up to 100 references. References without a DOI are kept: ``related_id``
          is ``<doi>#<reference key>`` and the citation text is in ``related_name`` /
          ``unstructured``; ``total_references`` is the exact count Crossref reports.
        """
        try:
            doi = self.normalize_doi(concept_id)
            if not doi:
                return []
            work = await self._fetch_work(doi)
            if work is None:
                return []
            return (
                self._update_edges(work, "updated-by", UPDATED_BY_LABELS, "_by")
                + self._update_edges(work, "update-to", UPDATE_TO_LABELS, "")
                + self._relation_edges(work)
                + self._reference_edges(doi, work)
            )
        except Exception as e:
            logger.warning(f"Crossref get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Other identifiers the record exposes: ISSN/ISBN of the container and PMID/PMCID/arXiv
        ids that appear as relations. (``alternative-id`` is ignored: it is usually just a
        publisher article number such as ``2012``.)

        Crossref does not index PubMed ids itself; a PMID only shows up when a publisher
        deposited it as a relation, so an empty PMID result is normal.
        """
        try:
            doi = self.normalize_doi(concept_id)
            if not doi:
                return []
            work = await self._fetch_work(doi)
            if work is None:
                return []
            mappings: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()

            def add(to_source: str, to_id: str, kind: str, conf: float) -> None:
                key = (to_source, to_id)
                if to_id and key not in seen:
                    seen.add(key)
                    mappings.append(self._mapping(doi, to_source, to_id, kind, conf))

            for issn in work.get("ISSN") or []:
                add("ISSN", str(issn), "container_id", 1.0)
            for isbn in work.get("ISBN") or []:
                add("ISBN", str(isbn), "container_id", 1.0)
            for entries in (work.get("relation") or {}).values():
                for entry in entries if isinstance(entries, list) else []:
                    id_type = str(entry.get("id-type") or "").lower()
                    if id_type in ("pmid", "pmcid", "arxiv"):
                        add(id_type.upper(), str(entry.get("id") or ""), "exact", 1.0)
            return mappings
        except Exception as e:
            logger.warning(f"Crossref get_mappings failed for '{concept_id}': {e}")
            return []

    async def doi_agency(self, doi: str) -> str | None:
        """Registration agency id of a DOI (``crossref``, ``datacite``, ...); ``None`` if unknown."""
        try:
            normalized = self.normalize_doi(doi)
            if not normalized:
                return None
            message = await self._get(
                self._work_url(normalized, "/agency"), interval=WORK_INTERVAL
            )
            agency = (message or {}).get("agency")
            return str(agency.get("id")) if isinstance(agency, dict) and agency.get("id") else None
        except Exception as e:
            logger.warning(f"Crossref doi_agency failed for '{doi}': {e}")
            return None

    async def check_retraction(self, doi: str) -> dict[str, Any]:
        """Is there a retraction / expression-of-concern / correction notice for ``doi``?

        Always asks Crossref afresh (no cache). Result keys: ``doi``, ``found`` (the DOI is a
        Crossref work), ``retracted`` (retraction, partial retraction, withdrawal or removal
        notice), ``expression_of_concern``, ``corrected``, ``title_flagged`` (title starts
        with RETRACTED/WITHDRAWN), ``notices`` (list of ``{doi, type, label, date, asserted_by}``)
        and ``is_notice_for`` (DOIs this work retracts/corrects, if it is a notice itself).
        ``found=False`` with ``retracted=False`` means *unknown*, not "clean": Crossref only
        holds deposited notices and imported Retraction Watch records.
        """
        result: dict[str, Any] = {
            "doi": doi,
            "found": False,
            "retracted": False,
            "expression_of_concern": False,
            "corrected": False,
            "title_flagged": False,
            "notices": [],
            "is_notice_for": [],
        }
        try:
            normalized = self.normalize_doi(doi)
            if not normalized:
                return result
            result["doi"] = normalized
            work = await self._fetch_work(normalized, fresh=True)
            if work is None:
                return result
            notices = [
                {
                    "doi": str(n.get("DOI") or "").lower(),
                    "type": str(n.get("type") or ""),
                    "label": str(n.get("label") or ""),
                    "date": _date(n.get("updated")),
                    "asserted_by": str(n.get("source") or ""),
                }
                for n in work.get("updated-by") or []
                if isinstance(n, dict)
            ]
            types = {n["type"] for n in notices}
            title = _first(work.get("title"))
            result.update(
                found=True,
                retracted=bool(types & RETRACTION_TYPES),
                expression_of_concern=bool(types & CONCERN_TYPES),
                corrected=bool(types & CORRECTION_TYPES),
                title_flagged=bool(re.match(r"\s*(?:RETRACTED|WITHDRAWN)\b", title, re.I)),
                notices=notices,
                is_notice_for=[
                    str(n.get("DOI") or "").lower()
                    for n in work.get("update-to") or []
                    if isinstance(n, dict) and n.get("DOI")
                ],
            )
            return result
        except Exception as e:
            logger.error(f"Crossref check_retraction failed for '{doi}': {e}")
            return result

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mapping(from_id: str, to_source: str, to_id: str, kind: str, conf: float) -> dict:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "CROSSREF",
            "toSource": to_source,
            "mappingType": kind,
            "confidence": conf,
        }

    @staticmethod
    def _author_name(author: dict[str, Any]) -> str:
        family = _clean_text(author.get("family"))
        given = _clean_text(author.get("given"))
        return (f"{family}, {given}" if given else family) or _clean_text(author.get("name"))

    def _work_to_concept(
        self, work: dict[str, Any], detailed: bool = False
    ) -> UnifiedConcept | None:
        """Convert a Crossref work to a ``UnifiedConcept`` (type CITATION)."""
        try:
            doi = str(work.get("DOI") or "").strip().lower()
            if not doi:
                return None
            title = _first(work.get("title")) or doi
            concept = self._create_concept(doi, title, ConceptType.CITATION)
            container = _first(work.get("container-title"))
            date = _work_date(work)
            year = date[:4]
            work_type = str(work.get("type") or "")
            publisher = _clean_text(work.get("publisher"))
            authors = [a for a in work.get("author") or [] if isinstance(a, dict)]
            abstract = _clean_text(work.get("abstract"))
            notices = [n for n in work.get("updated-by") or [] if isinstance(n, dict)]
            types = {str(n.get("type") or "") for n in notices}
            if concept.categories is not None:
                if work_type:
                    concept.categories.append(f"type:{work_type}")
                if container:
                    concept.categories.append(f"journal:{container}")
                if year:
                    concept.categories.append(f"year:{year}")
                if publisher:
                    concept.categories.append(f"publisher:{publisher}")
                if types & RETRACTION_TYPES:
                    concept.categories.append("retracted")
                if types & CONCERN_TYPES:
                    concept.categories.append("expression_of_concern")
            if abstract and concept.definitions is not None:
                concept.definitions.append(abstract)
            subtitle = _first(work.get("subtitle"))
            if subtitle and concept.synonyms is not None:
                concept.synonyms.append(f"{title}: {subtitle}")
            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.CROSSREF] = {
                    "doi": doi,
                    "title": title,
                    "container": container,
                    "date": date,
                    "year": year,
                    "type": work_type,
                    "publisher": publisher,
                    "issn": list(work.get("ISSN") or []),
                    "author_count": len(authors),
                    "authors": [self._author_name(a) for a in authors[:MAX_AUTHORS_KEPT]],
                    "cited_by_count": work.get("is-referenced-by-count"),
                    "references_count": work.get("references-count"),
                    "abstract_available": bool(abstract),
                    "update_notices": len(notices),
                    "url": f"https://doi.org/{doi}",
                }
                if detailed:
                    concept.source_data[KnowledgeSource.CROSSREF].update(
                        subtype=work.get("subtype"),
                        volume=work.get("volume"),
                        issue=work.get("issue"),
                        page=work.get("page"),
                        language=work.get("language"),
                        license=[lic.get("URL") for lic in work.get("license") or []][:3],
                        retracted=bool(types & RETRACTION_TYPES),
                    )
            return concept
        except Exception as e:
            logger.error(f"Error converting Crossref work: {e}")
            return None

    @staticmethod
    def _update_edges(
        work: dict[str, Any], field: str, labels: dict[str, str], suffix: str
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for notice in work.get(field) or []:
            if not isinstance(notice, dict) or not notice.get("DOI"):
                continue
            update_type = str(notice.get("type") or "").lower()
            related = str(notice["DOI"]).lower()
            if (update_type, related) in seen:
                continue
            seen.add((update_type, related))
            label = labels.get(update_type) or (
                f"{update_type or 'update'}{suffix}" if suffix else f"updates_{update_type}"
            )
            edges.append(
                {
                    "relation_label": label,
                    "related_id": related,
                    "related_name": str(notice.get("label") or update_type),
                    "source": "CROSSREF",
                    "update_type": update_type,
                    "notice_date": _date(notice.get("updated")),
                    "asserted_by": str(notice.get("source") or ""),
                }
            )
        return edges

    @staticmethod
    def _relation_edges(work: dict[str, Any]) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        relation = work.get("relation")
        if not isinstance(relation, dict):
            return edges
        for rel_type, label in RELATION_LABELS.items():
            entries = relation.get(rel_type)
            seen: set[str] = set()
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict) or not entry.get("id"):
                    continue
                related = str(entry["id"]).strip()
                related = related.lower() if entry.get("id-type") == "doi" else related
                if related in seen:
                    continue
                seen.add(related)
                if len(seen) > MAX_RELATIONS:
                    break
                edges.append(
                    {
                        "relation_label": label,
                        "related_id": related,
                        "related_name": related,
                        "source": "CROSSREF",
                        "id_type": str(entry.get("id-type") or ""),
                        "asserted_by": str(entry.get("asserted-by") or ""),
                    }
                )
        return edges

    @staticmethod
    def _reference_edges(doi: str, work: dict[str, Any]) -> list[dict[str, Any]]:
        references = [r for r in work.get("reference") or [] if isinstance(r, dict)]
        total = work.get("references-count")
        total = total if isinstance(total, int) else len(references)
        edges: list[dict[str, Any]] = []
        for ref in references[:MAX_REFERENCES]:
            unstructured = _clean_text(ref.get("unstructured"))
            ref_doi = str(ref.get("DOI") or "").strip().lower()
            text = unstructured or ", ".join(
                p
                for p in (
                    _clean_text(ref.get("author")),
                    _clean_text(ref.get("article-title") or ref.get("series-title")),
                    _clean_text(ref.get("journal-title") or ref.get("volume-title")),
                    _clean_text(ref.get("year")),
                )
                if p
            )
            if not ref_doi and not text:
                continue
            edge: dict[str, Any] = {
                "relation_label": "cites",
                "related_id": ref_doi or f"{doi}#{ref.get('key') or len(edges) + 1}",
                "related_name": text or ref_doi,
                "source": "CROSSREF",
                "has_doi": bool(ref_doi),
                "total_references": total,
            }
            if unstructured:
                edge["unstructured"] = unstructured
            edges.append(edge)
        return edges
