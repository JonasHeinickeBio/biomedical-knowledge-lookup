"""
Semantic Scholar Knowledge Source Adapter

Semantic Scholar (Allen Institute for AI) indexes ~200M papers across all fields and adds
machine-generated features on top of the metadata: a one-sentence ``tldr`` summary, an
"influential citation" classification and fields of study. This adapter uses the Academic
Graph API (``https://api.semanticscholar.org/graph/v1``)::

    GET /paper/search?query=<text>&fields=<csv>&limit=<n>         (n <= 100)
    GET /paper/<id>?fields=<csv>                                  (404 when unknown)
    GET /paper/<id>/references?fields=<csv>&limit=<n>             (payload key ``citedPaper``)
    GET /paper/<id>/citations?fields=<csv>&limit=<n>              (payload key ``citingPaper``)

``<id>`` is the 40-hex ``paperId`` or ``DOI:...``, ``PMID:...``, ``PMCID:...``, ``ARXIV:...``,
``CorpusId:...``, ``MAG:...``, ``ACL:...`` or ``URL:...``.

Rate limits and keys (the part that matters in practice)
    * **Keyless** access works but all keyless users share one pool ("1000 requests per second
      shared among all unauthenticated users", per the product page), so a request is often
      answered with HTTP 429 *immediately*, at any time of day, no matter how polite the client
      is. This adapter therefore never hammers: a 429 is retried at most twice, waiting for the
      ``Retry-After`` header when sent (otherwise 2 s, then 4 s, never more than 30 s), and then
      the call degrades to ``[]`` / ``None`` with a warning in the log. A 429 is not counted as
      a failure of the source by the circuit breaker.
    * A free API key (request form on the product page) gets a dedicated pool; its
      introductory limit is **1 request per second on all endpoints**. Set ``SEMANTIC_SCHOLAR_API_KEY``
      (or ``config.api_keys["semanticscholar"]``); it is sent only as the ``x-api-key`` header
      and never written to logs. This adapter spaces its requests at least ~1 s apart (per
      adapter instance) whether or not a key is set. ``is_available()`` is always True so the
      source is still tried keyless.

Licence: use is governed by the Semantic Scholar API License Agreement (accepted when requesting
a key; attribution of Semantic Scholar is requested, and the agreement restricts redistribution of
the data at scale and certain commercial uses). Abstracts are omitted by the API for papers where
the publisher forbids redistribution (``abstract`` is then null), TLDRs exist only for part of
the corpus. This adapter keeps responses small (it asks for a fixed field list, never for
author profiles).
"""

import asyncio
import logging
import os
import re
import time
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1"
API_KEY_ENV = "SEMANTIC_SCHOLAR_API_KEY"
MIN_REQUEST_INTERVAL = 1.0  # seconds between requests of one adapter (key limit: 1 rps)
MAX_RATE_LIMIT_RETRIES = 2  # extra attempts after an HTTP 429 (so at most 3 requests)
RATE_LIMIT_BACKOFF = 2.0  # first wait when no Retry-After header is sent (doubles)
MAX_RATE_LIMIT_WAIT = 30.0  # never wait longer than this for a single 429
MAX_SEARCH_LIMIT = 100  # API maximum for ``paper/search``
MAX_EDGE_LIMIT = 100  # cap for references / citations per direction
DEFAULT_EDGE_LIMIT = 25

#: Fields requested for paper concepts; ``abstract``/``tldr`` can be null.
PAPER_FIELDS = (
    "paperId,corpusId,externalIds,url,title,abstract,venue,year,publicationDate,"
    "publicationTypes,referenceCount,citationCount,influentialCitationCount,isOpenAccess,"
    "openAccessPdf,fieldsOfStudy,tldr,authors.name"
)
MAPPING_FIELDS = "paperId,corpusId,externalIds"
EDGE_FIELDS = "paperId,title,year,externalIds,isInfluential"

_PAPER_ID_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_DOI_URL_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/(10\.\S+)$", re.IGNORECASE)
_PMID_RE = re.compile(r"^(?:PMID:?)?\s*(\d{1,9})$", re.IGNORECASE)
_PMCID_RE = re.compile(r"^(?:PMCID:)?\s*(?:PMC)?(\d+)$", re.IGNORECASE)
_ARXIV_RE = re.compile(r"^(?:ARXIV:)\s*(\S+)$", re.IGNORECASE)
_CORPUS_RE = re.compile(r"^(?:CORPUSID|CORPUS):?\s*(\d+)$", re.IGNORECASE)
_PREFIXED_RE = re.compile(r"^(MAG|ACL|DBLP|URL):\s*(\S.*)$", re.IGNORECASE)

#: externalIds key -> (label used as ``toSource`` in mappings, identifier prefix)
EXTERNAL_ID_LABELS: dict[str, str] = {
    "DOI": "DOI",
    "PubMed": "PMID",
    "PubMedCentral": "PMCID",
    "ArXiv": "ArXiv",
    "MAG": "MAG",
    "ACL": "ACL",
    "DBLP": "DBLP",
    "CorpusId": "CorpusId",
}


class _RateLimited:
    """Returned (not raised) by :meth:`SemanticScholarAdapter._send` for HTTP 429.

    Not an exception on purpose: raising would send it through the base class' retry loop
    and circuit breaker, which treat it as an outage and retry immediately.
    """

    def __init__(self, retry_after: float | None):
        self.retry_after = retry_after


class SemanticScholarAdapter(KnowledgeSourceAdapter):
    """Adapter for the Semantic Scholar Academic Graph API (papers, citations, TLDRs)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.api_key = config.get_api_key("semanticscholar") or os.getenv(API_KEY_ENV)
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.SEMANTICSCHOLAR

    def is_available(self) -> bool:
        return True  # keyless works (heavily shared, see module docstring); a key is optional

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_paper_id(concept_id: str) -> str | None:
        """Turn any supported paper identifier into the API's ``<id>`` path form.

        ``paperId`` (40 hex), ``DOI:10.x/y`` / bare ``10.x/y`` / ``https://doi.org/10.x/y``,
        ``PMID:n`` or bare digits (read as a PMID, like the other literature adapters),
        ``PMCID:PMC123`` / ``PMC123``, ``ARXIV:2106.15928``, ``CorpusId:n`` and the
        ``MAG:``, ``ACL:``, ``DBLP:`` and ``URL:`` forms. Returns ``None`` for anything else.
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        if _PAPER_ID_RE.match(text):
            return text.lower()
        for pattern, template in (
            (_DOI_URL_RE, "DOI:{}"),
            (_CORPUS_RE, "CorpusId:{}"),
            (_ARXIV_RE, "ARXIV:{}"),
        ):
            match = pattern.match(text)
            if match:
                return template.format(match.group(1))
        if text.upper().startswith("DOI:"):
            doi = text[4:].strip()
            return f"DOI:{doi}" if _DOI_RE.match(doi) else None
        if _DOI_RE.match(text):
            return f"DOI:{text}"
        if text.upper().startswith("PMC"):  # before the PMCID/PMID digit patterns
            match = _PMCID_RE.match(text)
            return f"PMCID:{match.group(1)}" if match else None
        match = _PMID_RE.match(text)
        if match:
            return f"PMID:{match.group(1)}"
        match = _PREFIXED_RE.match(text)
        if match:
            return f"{match.group(1).upper()}:{match.group(2).strip()}"
        return None

    # ------------------------------------------------------------------
    # HTTP with throttle and bounded 429 handling
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key} if self.api_key else {}

    async def _throttle(self) -> None:
        """Keep requests of this adapter at least ``MIN_REQUEST_INTERVAL`` apart."""
        async with self._lock:
            wait = MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _send(
        self, url: str, params: dict[str, Any] | None
    ) -> dict[str, Any] | _RateLimited | None:
        """One GET. ``None`` for 400/404 (unknown or malformed id); ``_RateLimited`` for 429.

        The 429 is handled here rather than by the base class' backoff (which would retry
        four times in 14 s) so that the shared keyless pool is not hammered; 400/404 mean
        "no such paper" and must not count as source failures.
        """

        async def _do() -> dict[str, Any] | _RateLimited | None:
            session = await self._get_session()
            headers = {"User-Agent": "AID-PAIS-Knowledge-Lookup/1.0", **self._headers()}
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 429:
                    raw = response.headers.get("Retry-After")
                    try:
                        retry_after = float(raw) if raw is not None else None
                    except ValueError:
                        retry_after = None
                    return _RateLimited(retry_after)
                if response.status in (400, 404):
                    return None
                response.raise_for_status()
                return await response.json()

        return await self._call_with_retry("semanticscholar", _do)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """GET ``BASE_URL/path`` with throttle and at most ``MAX_RATE_LIMIT_RETRIES`` 429 retries.

        Returns ``None`` when the paper is unknown, when the API keeps answering 429 (logged
        with a hint about the key) or on any other failure.
        """
        url = f"{BASE_URL}/{path}"
        backoff = RATE_LIMIT_BACKOFF
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            await self._throttle()
            try:
                result = await self._send(url, params)
            except Exception as e:
                logger.warning(f"Semantic Scholar request to '{path}' failed: {e}")
                return None
            if not isinstance(result, _RateLimited):
                return result
            if attempt >= MAX_RATE_LIMIT_RETRIES:
                break
            wait = result.retry_after if result.retry_after is not None else backoff
            wait = max(0.0, min(wait, MAX_RATE_LIMIT_WAIT))
            backoff *= 2
            logger.info(f"Semantic Scholar answered 429; waiting {wait:.0f}s before retrying")
            await asyncio.sleep(wait)
        hint = "" if self.api_key else f" (keyless pool is shared; set {API_KEY_ENV} for a key)"
        logger.warning(f"Semantic Scholar rate limit (HTTP 429) persists for '{path}'{hint}")
        return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Relevance-ranked paper search (``paper/search``, up to 100 results in one request).

        A query that is itself a paper identifier (DOI, PMID, arXiv id, ...) resolves to that
        paper instead of being searched as text.
        """
        try:
            query = (query or "").strip()
            limit = int(limit)
            if not query or limit <= 0:
                return []
            if self._looks_like_id(query):
                concept = await self.get_concept_details(query)
                if concept is not None:
                    return [concept]
            data = await self._get(
                "paper/search",
                {"query": query, "fields": PAPER_FIELDS, "limit": min(limit, MAX_SEARCH_LIMIT)},
            )
            if not data or not isinstance(data.get("data"), list):
                return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            for item in data["data"]:
                concept = self._paper_to_concept(item) if isinstance(item, dict) else None
                if concept is not None and concept.primary_id not in seen:
                    seen.add(concept.primary_id)
                    concepts.append(concept)
            logger.info(f"Semantic Scholar search for '{query}' returned {len(concepts)} papers")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"Semantic Scholar search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Paper by ``paperId``, DOI, PMID, PMCID, arXiv id or CorpusId (see :meth:`normalize_paper_id`)."""
        try:
            paper_id = self.normalize_paper_id(concept_id)
            if paper_id is None:
                return None
            record = await self._get(f"paper/{self._path(paper_id)}", {"fields": PAPER_FIELDS})
            return self._paper_to_concept(record) if record else None
        except Exception as e:
            logger.error(f"Semantic Scholar get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = DEFAULT_EDGE_LIMIT
    ) -> list[dict[str, Any]]:
        """Paper -> papers it cites (``cites``) and papers citing it (``cited_by``).

        Each direction costs one request and is capped at ``limit`` (default 25, at most 100);
        the API returns them in its own order, not by importance. Edges carry
        ``is_influential`` (Semantic Scholar's classifier; absent when not provided), ``year``
        and, where known, ``doi`` / ``pmid``. References without a Semantic Scholar record are
        skipped. If one direction fails (e.g. 429) the other is still returned.
        """
        try:
            paper_id = self.normalize_paper_id(concept_id)
            limit = max(0, min(int(limit), MAX_EDGE_LIMIT))
            if paper_id is None or limit == 0:
                return []
            path = self._path(paper_id)
            relationships: list[dict[str, Any]] = []
            for suffix, key, label in (
                ("references", "citedPaper", "cites"),
                ("citations", "citingPaper", "cited_by"),
            ):
                data = await self._get(
                    f"paper/{path}/{suffix}", {"fields": EDGE_FIELDS, "limit": limit}
                )
                relationships.extend(self._edges(data, key, label, limit))
            return relationships
        except Exception as e:
            logger.warning(f"Semantic Scholar get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Paper -> its external ids (DOI, PMID, PMCID, ArXiv, MAG, ACL, DBLP, CorpusId)."""
        try:
            paper_id = self.normalize_paper_id(concept_id)
            if paper_id is None:
                return []
            record = await self._get(f"paper/{self._path(paper_id)}", {"fields": MAPPING_FIELDS})
            if not record or not record.get("paperId"):
                return []
            external = dict(record.get("externalIds") or {})
            if record.get("corpusId") is not None:
                external.setdefault("CorpusId", record["corpusId"])
            mappings = []
            for key, label in EXTERNAL_ID_LABELS.items():
                value = external.get(key)
                if value not in (None, ""):
                    if label == "PMCID":
                        value = self._pmc(value)
                    mappings.append(
                        {
                            "fromId": record["paperId"],
                            "toId": str(value),
                            "fromSource": "SEMANTICSCHOLAR",
                            "toSource": label,
                            "mappingType": "exact",
                            "confidence": 1.0,
                        }
                    )
            return mappings
        except Exception as e:
            logger.warning(f"Semantic Scholar get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_id(query: str) -> bool:
        """True for a clearly identifier-shaped query (a bare number is treated as text)."""
        if _PAPER_ID_RE.match(query) or _DOI_RE.match(query) or _DOI_URL_RE.match(query):
            return True
        return bool(
            re.match(r"^(?:DOI|PMID|PMCID|ARXIV|CORPUSID|CORPUS|MAG|ACL|DBLP):", query, re.I)
        ) or bool(re.match(r"^PMC\d+$", query, re.I))

    @staticmethod
    def _pmc(value: Any) -> str:
        """``8195534`` / ``PMC8195534`` -> ``PMC8195534`` (externalIds omit the prefix)."""
        text = str(value).strip()
        return text if text.upper().startswith("PMC") else f"PMC{text}"

    @staticmethod
    def _path(paper_id: str) -> str:
        """Percent-encode an ``<id>`` for the URL path (DOIs may contain odd characters)."""
        return quote(paper_id, safe=":/()._-~")

    @staticmethod
    def _edges(
        data: dict[str, Any] | None, key: str, label: str, limit: int
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        if not data or not isinstance(data.get("data"), list):
            return edges
        seen: set[str] = set()
        for row in data["data"]:
            paper = row.get(key) if isinstance(row, dict) else None
            if not isinstance(paper, dict) or not paper.get("paperId"):
                continue
            related_id = str(paper["paperId"])
            if related_id in seen:
                continue
            seen.add(related_id)
            external = paper.get("externalIds") or {}
            edge: dict[str, Any] = {
                "relation_label": label,
                "related_id": related_id,
                "related_name": paper.get("title") or related_id,
                "source": "SEMANTICSCHOLAR",
                "year": paper.get("year"),
            }
            if row.get("isInfluential") is not None:
                edge["is_influential"] = bool(row["isInfluential"])
            if external.get("DOI"):
                edge["doi"] = external["DOI"]
            if external.get("PubMed"):
                edge["pmid"] = external["PubMed"]
            edges.append(edge)
            if len(edges) >= limit:
                break
        return edges

    def _paper_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a Graph API paper record to a ``UnifiedConcept`` (type CITATION)."""
        try:
            paper_id = item.get("paperId")
            title = (item.get("title") or "").strip()
            if not paper_id or not title:
                return None
            concept = self._create_concept(str(paper_id), title, ConceptType.CITATION)
            external = item.get("externalIds") or {}
            doi = external.get("DOI")
            pmid = external.get("PubMed")
            pmcid = external.get("PubMedCentral")
            year = item.get("year")
            venue = (item.get("venue") or "").strip()
            fields = [f for f in item.get("fieldsOfStudy") or [] if f]
            types = [t for t in item.get("publicationTypes") or [] if t]
            abstract = (item.get("abstract") or "").strip()
            tldr = (
                (item.get("tldr") or {}).get("text")
                if isinstance(item.get("tldr"), dict)
                else None
            )
            pdf = item.get("openAccessPdf") if isinstance(item.get("openAccessPdf"), dict) else {}
            if abstract and concept.definitions is not None:
                concept.definitions.append(abstract)
            if concept.semantic_types is not None:
                concept.semantic_types.extend(types)
            if concept.categories is not None:
                if year:
                    concept.categories.append(f"year:{year}")
                if venue:
                    concept.categories.append(f"venue:{venue}")
                if item.get("isOpenAccess"):
                    concept.categories.append("open_access")
                concept.categories.extend(f"field:{f}" for f in fields)
            if doi:
                concept.add_identifier(
                    KnowledgeSource.EUROPEPMC, f"DOI:{doi}", title, f"https://doi.org/{doi}"
                )
            if pmid:
                concept.add_identifier(
                    KnowledgeSource.EUROPEPMC,
                    f"PMID:{pmid}",
                    title,
                    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                )
            if pmcid:
                concept.add_identifier(KnowledgeSource.EUROPEPMC, self._pmc(pmcid), title)
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.SEMANTICSCHOLAR] = {
                    "paperId": str(paper_id),
                    "corpusId": item.get("corpusId"),
                    "title": title,
                    "year": year,
                    "venue": venue or None,
                    "publication_date": item.get("publicationDate"),
                    "publication_types": types,
                    "fields_of_study": fields,
                    "authors": [
                        a["name"]
                        for a in item.get("authors") or []
                        if isinstance(a, dict) and a.get("name")
                    ],
                    "tldr": tldr,
                    "citation_count": item.get("citationCount"),
                    "influential_citation_count": item.get("influentialCitationCount"),
                    "reference_count": item.get("referenceCount"),
                    "is_open_access": item.get("isOpenAccess"),
                    "open_access_pdf": pdf.get("url") if pdf else None,
                    "external_ids": external,
                    "url": item.get("url"),
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting Semantic Scholar paper: {e}")
            return None
