"""
DOAJ (Directory of Open Access Journals) Knowledge Source Adapter

DOAJ is a curated index of fully open access journals and of the articles in them. The adapter
exposes *journals* (concept id ``journal:<DOAJ id>``) and *articles* (``article:<DOAJ id>``);
a bare 32-character DOAJ id is tried as a journal first, then as an article. ISSNs
(``1932-6203``, ``ISSN:...``) resolve to the journal, DOIs to the article.

API (verified live 2026-10-09; spec: ``GET https://doaj.org/api/v4/swagger.json``,
human docs: https://doaj.org/api/v4/docs)::

    GET https://doaj.org/api/v4/search/journals/<query>?page=<n>&pageSize=<n>
    GET https://doaj.org/api/v4/search/articles/<query>?page=<n>&pageSize=<n>
    GET https://doaj.org/api/v4/journals/<id>      GET https://doaj.org/api/v4/articles/<id>

Query grammar (learned from live responses, the docs only say "Elasticsearch query string"):

* the query is a *path segment* (URL-encoded by the adapter), not a ``q=`` parameter;
* several words are **AND-ed over all indexed fields**: ``long covid`` finds 22,601 articles
  but 0 journals, ``chronic fatigue`` finds no journal at all. ``long OR covid`` gives 46
  journals (any journal mentioning either word), which is mostly noise, so the adapter does
  not rewrite queries: an empty journal result means "no journal about all of these words";
* field syntax works: ``title:medicine``, ``bibjson.title:"lancet"``, ``issn:1897-4252`` (matches
  print *and* electronic ISSN), ``publisher:dove``, ``license:CC-BY`` (journals) and
  ``doi:10.1371/journal.pone.0326790``, ``abstract:...`` (articles). ``eissn:`` is *not* a
  shorthand (0 hits); use ``issn:``. ``doi:`` matching is **case-sensitive** against the DOI
  as the publisher supplied it (``10.7554/eLife.40553``), so DOI lookups try the given
  spelling first and the lower-case one second; wildcards are rejected (HTTP 400, quickly);
* **a malformed query (unbalanced quote or parenthesis, a lone ``AND``, a leading ``(``) makes
  the server think for about 27 seconds before it answers HTTP 400.** :func:`sanitize_query`
  therefore only passes through well-formed field/phrase/operator queries and otherwise turns
  every reserved character into a space, so free text such as ``COVID-19: long (review``
  can never trigger that stall;
* ``pageSize`` above 100 is silently capped at 100; ``x-total-count`` carries the hit count.

Rate limit (docs): two requests per second on every route, bursts of up to five queued
requests are served so long as they average two per second; requests are spaced by 0.6 s.
Metadata is CC0 (https://doaj.org/terms/); the site, name and logo are not.

What DOAJ inclusion means: a journal is in the index after DOAJ's editorial review against its
published criteria for fully open access publishing (no subscription or hybrid titles),
including transparent editorial, peer-review, licensing and fee information. It is not an
impact ranking, and absence does not make a journal predatory (hybrid titles such as Nature
Reviews Microbiology are simply out of scope). DOAJ also removes titles that stop meeting the
criteria, so ``in_doaj`` refers to the moment of the lookup. The old "Seal" badge is not
exposed by the public API (``admin.seal:true`` finds nothing); ``admin.ticked`` is DOAJ's
internal review flag and is reported verbatim as ``ticked``.
"""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._vocab_common import Spacer

logger = logging.getLogger(__name__)

BASE_URL = "https://doaj.org/api/v4"
SITE_URL = "https://doaj.org"
MAX_PAGE_SIZE = 100
DEFAULT_REL_LIMIT = 25
MIN_INTERVAL = 0.6  # docs: 2 requests/second; 0.6 s keeps clear of the queue limit
MAX_AUTHORS = 10

_HEX_ID_RE = re.compile(r"[0-9a-f]{32}", re.IGNORECASE)
_ISSN_RE = re.compile(r"^(?:e?issn:?\s*)?(\d{4}-?\d{3}[\dXx])$", re.IGNORECASE)
_DOI_RE = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
_URL_ID_RE = re.compile(r"^https?://(?:www\.)?doaj\.org/(toc|article)/([0-9a-f]{32})/?$", re.I)
_FIELD_RE = re.compile(r"(?:^|[\s(])[A-Za-z_][\w.]*:(?=[^\s:])")
_RESERVED_RE = re.compile(r'[+\-=&|><!(){}\[\]^"~*?:\\/]')
_STRUCTURED_OK_RE = re.compile(r'^[\w\s.\-:"()/À-￿]+$')
_OPERATORS = ("AND", "OR", "NOT")


def sanitize_query(query: str) -> str:
    """Make *query* safe for DOAJ's Elasticsearch query-string endpoint.

    Well-formed structured queries (``field:value``, quoted phrases, upper-case ``AND`` /
    ``OR`` / ``NOT``) pass through unchanged. Anything else is treated as plain text: reserved
    characters become spaces and stray upper-case operators become ordinary words. The point is
    to never send a query that DOAJ rejects, because it needs ~27 s to say so (see module doc).
    """
    text = re.sub(r"\s+", " ", query or "").strip()
    if not text:
        return ""
    tokens = text.split()
    structured = (
        bool(_FIELD_RE.search(text)) or '"' in text or any(t in _OPERATORS for t in tokens)
    )
    if structured and _well_formed(text, tokens):
        return text
    plain = _RESERVED_RE.sub(" ", text)
    plain = " ".join(t.lower() if t in _OPERATORS else t for t in plain.split())
    return plain


def _well_formed(text: str, tokens: list[str]) -> bool:
    if not _STRUCTURED_OK_RE.match(text) or text.count('"') % 2:
        return False
    depth = 0
    for char in text:
        depth += (char == "(") - (char == ")")
        if depth < 0:
            return False
    if depth:
        return False
    if tokens[0] in _OPERATORS and tokens[0] != "NOT" or tokens[-1] in _OPERATORS:
        return False
    for first, second in zip(tokens, tokens[1:], strict=False):
        if first in _OPERATORS and second in _OPERATORS and second != "NOT":
            return False
    # a field with an empty parenthesis/quote group, e.g. ``title:()`` or ``title:""``
    return not re.search(r'\(\s*\)|""', text)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class DOAJAdapter(KnowledgeSourceAdapter):
    """Adapter for DOAJ journals and articles (keyless; metadata CC0; 2 requests/second)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self._spacer = Spacer(MIN_INTERVAL)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.DOAJ

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str, str] | None:
        """Classify an identifier as ``(kind, value)``.

        * ``("journal", id)`` / ``("article", id)`` for ``journal:<id>`` / ``article:<id>``
          and ``https://doaj.org/toc/<id>`` / ``https://doaj.org/article/<id>``;
        * ``("any", id)`` for a bare DOAJ id (journal first, then article);
        * ``("issn", "1932-6203")`` for ISSNs (``ISSN:``/``eISSN:`` prefix optional);
        * ``("doi", "10.x/y")`` for DOIs (bare, ``doi:``, ``https://doi.org/``).
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        if match := _URL_ID_RE.match(text):
            return ("journal" if match.group(1).lower() == "toc" else "article"), match.group(
                2
            ).lower()
        head, _, tail = text.partition(":")
        if head.lower() in ("journal", "article", "doaj") and _HEX_ID_RE.fullmatch(tail.strip()):
            kind = {"journal": "journal", "article": "article"}.get(head.lower(), "any")
            return kind, tail.strip().lower()
        if _HEX_ID_RE.fullmatch(text):
            return "any", text.lower()
        if match := _ISSN_RE.match(text):
            digits = match.group(1).upper().replace("-", "")
            return "issn", f"{digits[:4]}-{digits[4:]}"
        if match := _DOI_RE.match(text):
            return "doi", match.group(1)
        return None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Spaced GET ``BASE_URL/path``; ``None`` on any failure (404 included)."""
        try:
            await self._spacer.wait()
            return await self._make_request(f"{BASE_URL}/{path}", params=params)
        except Exception as e:
            if getattr(e, "status", None) == 404:
                logger.debug(f"DOAJ /{path} not found")
            else:
                logger.warning(f"DOAJ request failed: {e}")
            return None

    async def _search(
        self, kind: str, query: str, limit: int, page: int = 1
    ) -> list[dict[str, Any]]:
        """Raw result records of ``search/<kind>/<query>`` (``kind``: journals | articles)."""
        text = sanitize_query(query)
        limit = max(0, min(int(limit), MAX_PAGE_SIZE))
        if not text or limit == 0:
            return []
        data = await self._get(
            f"search/{kind}/{quote(text, safe='')}", {"page": max(1, page), "pageSize": limit}
        )
        results = data.get("results") if isinstance(data, dict) else None
        return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_journals(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Journals matching *query* (see the module doc for the AND-everywhere grammar)."""
        try:
            records = await self._search("journals", query, limit)
            return self._convert_list(records, self._journal_to_concept, limit)
        except Exception as e:
            logger.error(f"DOAJ search_journals failed for '{query}': {e}")
            return []

    async def search_articles(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Articles matching *query* (title, abstract, keywords, DOI, ... all AND-ed)."""
        try:
            records = await self._search("articles", query, limit)
            return self._convert_list(records, self._article_to_concept, limit)
        except Exception as e:
            logger.error(f"DOAJ search_articles failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Journals first (about a quarter of ``limit``, at least one), then articles.

        An ISSN or DOI as the query resolves to that journal / article. Two requests otherwise.
        """
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            parsed = self.parse_id(query)
            if parsed and parsed[0] in ("issn", "doi", "journal", "article"):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            n_journals = max(1, limit // 4)
            journals, articles = await asyncio.gather(
                self.search_journals(query, n_journals), self.search_articles(query, limit)
            )
            return (journals + articles)[:limit]
        except Exception as e:
            logger.error(f"DOAJ search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Journal or article by DOAJ id, journal by ISSN, article by DOI."""
        try:
            record = await self._record(concept_id)
            if record is None:
                return None
            kind, item = record
            convert = self._journal_to_concept if kind == "journal" else self._article_to_concept
            return convert(item)
        except Exception as e:
            logger.error(f"DOAJ get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = DEFAULT_REL_LIMIT
    ) -> list[dict[str, Any]]:
        """Typed edges. ``limit`` caps each group (``limit=0`` returns ``[]``).

        Journal: ``has_subject`` (LCC subject, ``LCC:<code>``), ``has_license`` (``related_id``
        is the licence type, e.g. ``CC BY-NC-SA``, with the BY/NC/ND/SA flags and URL),
        ``published_by`` (publisher, with country). Article: ``published_in`` its journal
        (``journal:<DOAJ id>`` when the ISSN resolves to a journal still in DOAJ, otherwise
        ``ISSN:<issn>`` with ``journal_in_doaj=False``) and ``has_subject``.
        """
        try:
            limit = max(0, min(int(limit), MAX_PAGE_SIZE))
            if limit == 0:
                return []
            record = await self._record(concept_id)
            if record is None:
                return []
            kind, item = record
            if kind == "journal":
                return self._journal_edges(item, limit)
            return await self._article_edges(item, limit)
        except Exception as e:
            logger.warning(f"DOAJ get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Journal -> ISSN (print) and EISSN; article -> DOI plus its journal's ISSNs."""
        try:
            record = await self._record(concept_id)
            if record is None:
                return []
            kind, item = record
            bib = item.get("bibjson") or {}
            from_id = f"{kind}:{item.get('id')}"
            if kind == "journal":
                pairs = [("ISSN", bib.get("pissn")), ("EISSN", bib.get("eissn"))]
            else:
                ids = {
                    str(i.get("type")).lower(): i.get("id")
                    for i in bib.get("identifier") or []
                    if isinstance(i, dict)
                }
                pairs = [("DOI", ids.get("doi"))]
                pairs += [("ISSN", v) for v in ((bib.get("journal") or {}).get("issns") or [])]
            return [
                {
                    "fromId": from_id,
                    "toId": str(value).lower() if label == "DOI" else str(value),
                    "fromSource": "DOAJ",
                    "toSource": label,
                    "mappingType": "exact",
                    "confidence": 1.0,
                }
                for label, value in pairs
                if value
            ]
        except Exception as e:
            logger.warning(f"DOAJ get_mappings failed for '{concept_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Record fetching
    # ------------------------------------------------------------------

    async def _record(self, concept_id: str) -> tuple[str, dict[str, Any]] | None:
        """Resolve any accepted identifier to ``("journal" | "article", raw record)``."""
        parsed = self.parse_id(concept_id)
        if parsed is None:
            return None
        kind, value = parsed
        if kind == "issn":
            results = await self._search("journals", f"issn:{value}", 1)
            return ("journal", results[0]) if results else None
        if kind == "doi":
            doi = value.replace('"', "")
            # DOAJ stores the DOI exactly as the publisher supplied it (e.g.
            # ``10.7554/eLife.40553``) and matches it case-sensitively, so try the spelling
            # we were given first and the lower-case form second.
            for spelling in dict.fromkeys((doi, doi.lower())):
                results = await self._search("articles", f'doi:"{spelling}"', 1)
                if results:
                    return "article", results[0]
            return None
        for candidate in ("journal", "article") if kind == "any" else (kind,):
            data = await self._get(f"{candidate}s/{value}")
            if isinstance(data, dict) and data.get("id"):
                return candidate, data
        return None

    # ------------------------------------------------------------------
    # Relationship helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _journal_edges(item: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        bib = item.get("bibjson") or {}
        edges: list[dict[str, Any]] = []
        for subject in (bib.get("subject") or [])[:limit]:
            if subject.get("term"):
                edges.append(
                    {
                        "relation_label": "has_subject",
                        "related_id": f"{subject.get('scheme') or 'LCC'}:{subject.get('code')}",
                        "related_name": subject["term"],
                        "source": "DOAJ",
                        "scheme": subject.get("scheme"),
                    }
                )
        for lic in (bib.get("license") or [])[:limit]:
            if lic.get("type"):
                edges.append(
                    {
                        "relation_label": "has_license",
                        "related_id": lic["type"],
                        "related_name": lic["type"],
                        "source": "DOAJ",
                        "url": lic.get("url"),
                        "attribution": lic.get("BY"),
                        "non_commercial": lic.get("NC"),
                        "no_derivatives": lic.get("ND"),
                        "share_alike": lic.get("SA"),
                    }
                )
        publisher = bib.get("publisher") or {}
        if publisher.get("name"):
            edges.append(
                {
                    "relation_label": "published_by",
                    "related_id": publisher["name"],
                    "related_name": publisher["name"],
                    "source": "DOAJ",
                    "country": publisher.get("country"),
                }
            )
        return edges

    async def _article_edges(self, item: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        bib = item.get("bibjson") or {}
        journal = bib.get("journal") or {}
        edges: list[dict[str, Any]] = []
        issns = [i for i in journal.get("issns") or [] if i]
        if issns or journal.get("title"):
            found = await self._search("journals", f"issn:{issns[0]}", 1) if issns else []
            if found:
                target = f"journal:{found[0].get('id')}"
                title = (found[0].get("bibjson") or {}).get("title")
            else:
                target = f"ISSN:{issns[0]}" if issns else _clean(journal.get("title"))
                title = None
            edges.append(
                {
                    "relation_label": "published_in",
                    "related_id": target,
                    "related_name": title or journal.get("title") or target,
                    "source": "DOAJ",
                    "journal_in_doaj": bool(found),
                    "issns": issns,
                    "publisher": journal.get("publisher"),
                }
            )
        for subject in (bib.get("subject") or [])[:limit]:
            if subject.get("term"):
                edges.append(
                    {
                        "relation_label": "has_subject",
                        "related_id": f"{subject.get('scheme') or 'LCC'}:{subject.get('code')}",
                        "related_name": subject["term"],
                        "source": "DOAJ",
                        "scheme": subject.get("scheme"),
                    }
                )
        return edges

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_list(items: list[dict[str, Any]], convert: Any, limit: int) -> list[Any]:
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for item in items:
            concept = convert(item)
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concepts.append(concept)
        return concepts[:limit]

    def _journal_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a journal record (type UNKNOWN: there is no journal concept type)."""
        try:
            bib = item.get("bibjson") or {}
            journal_id = item.get("id")
            title = _clean(bib.get("title"))
            if not journal_id or not title:
                return None
            concept = self._create_concept(f"journal:{journal_id}", title, ConceptType.UNKNOWN)
            pissn, eissn = bib.get("pissn"), bib.get("eissn")
            licenses = [lic for lic in bib.get("license") or [] if isinstance(lic, dict)]
            subjects = [s for s in bib.get("subject") or [] if isinstance(s, dict)]
            apc = bib.get("apc") or {}
            admin = item.get("admin") or {}
            if concept.synonyms is not None:
                if bib.get("alternative_title"):
                    concept.synonyms.append(_clean(bib["alternative_title"]))
                concept.synonyms.extend(k for k in bib.get("keywords") or [] if k)
            if concept.categories is not None:
                concept.categories.extend(
                    f"subject:{s['term']}" for s in subjects if s.get("term")
                )
                concept.categories.extend(f"license:{lic['type']}" for lic in licenses)
                concept.categories.append("apc:yes" if apc.get("has_apc") else "apc:no")
            if concept.semantic_types is not None:
                concept.semantic_types.append("journal")
            for issn in (pissn, eissn):
                if issn:
                    concept.add_identifier(KnowledgeSource.CROSSREF, f"ISSN:{issn}", title)
            concept.confidence_score = 0.9
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.DOAJ] = {
                    "id": journal_id,
                    "title": title,
                    "alternative_title": bib.get("alternative_title"),
                    "pissn": pissn,
                    "eissn": eissn,
                    "publisher": (bib.get("publisher") or {}).get("name"),
                    "publisher_country": (bib.get("publisher") or {}).get("country"),
                    "institution": (bib.get("institution") or {}).get("name"),
                    "languages": bib.get("language") or [],
                    "subjects": [
                        {"scheme": s.get("scheme"), "code": s.get("code"), "term": s.get("term")}
                        for s in subjects
                    ],
                    "keywords": bib.get("keywords") or [],
                    "licenses": [
                        {
                            "type": lic.get("type"),
                            "url": lic.get("url"),
                            "BY": lic.get("BY"),
                            "NC": lic.get("NC"),
                            "ND": lic.get("ND"),
                            "SA": lic.get("SA"),
                        }
                        for lic in licenses
                    ],
                    "apc": {
                        "has_apc": apc.get("has_apc"),
                        "max": apc.get("max") or [],
                        "url": apc.get("url"),
                    },
                    "other_charges": (bib.get("other_charges") or {}).get("has_other_charges"),
                    "waiver": (bib.get("waiver") or {}).get("has_waiver"),
                    "peer_review": (bib.get("editorial") or {}).get("review_process") or [],
                    "review_url": (bib.get("editorial") or {}).get("review_url"),
                    "publication_time_weeks": bib.get("publication_time_weeks"),
                    "oa_start": bib.get("oa_start"),
                    "boai": bib.get("boai"),
                    "author_retains_copyright": (bib.get("copyright") or {}).get("author_retains"),
                    "plagiarism_detection": (bib.get("plagiarism") or {}).get("detection"),
                    "preservation": (bib.get("preservation") or {}).get("service") or [],
                    "pid_scheme": (bib.get("pid_scheme") or {}).get("scheme") or [],
                    "ticked": admin.get("ticked"),
                    "seal": admin.get("seal"),
                    "in_doaj": admin.get("in_doaj", True),
                    "created": item.get("created_date"),
                    "last_updated": item.get("last_updated"),
                    "url": f"{SITE_URL}/toc/{journal_id}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting DOAJ journal: {e}")
            return None

    def _article_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert an article record (type CITATION)."""
        try:
            bib = item.get("bibjson") or {}
            article_id = item.get("id")
            title = _clean(bib.get("title"))
            if not article_id or not title:
                return None
            concept = self._create_concept(f"article:{article_id}", title, ConceptType.CITATION)
            ids = {
                str(i.get("type")).lower(): i.get("id")
                for i in bib.get("identifier") or []
                if isinstance(i, dict)
            }
            doi = (ids.get("doi") or "").lower() or None
            journal = bib.get("journal") or {}
            subjects = [s for s in bib.get("subject") or [] if isinstance(s, dict)]
            abstract = _clean(bib.get("abstract")) or None
            year = _clean(bib.get("year")) or None
            if abstract and concept.definitions is not None:
                concept.definitions.append(abstract)
            if concept.synonyms is not None:
                concept.synonyms.extend(k for k in bib.get("keywords") or [] if k)
            if concept.categories is not None:
                if year:
                    concept.categories.append(f"year:{year}")
                if journal.get("title"):
                    concept.categories.append(f"journal:{_clean(journal['title'])}")
                concept.categories.extend(
                    f"subject:{s['term']}" for s in subjects if s.get("term")
                )
            if concept.semantic_types is not None:
                concept.semantic_types.append("article")
            if doi:
                concept.add_identifier(
                    KnowledgeSource.EUROPEPMC, f"DOI:{doi}", title, f"https://doi.org/{doi}"
                )
            concept.confidence_score = 0.85
            links = [lk for lk in bib.get("link") or [] if isinstance(lk, dict)]
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.DOAJ] = {
                    "id": article_id,
                    "doi": doi,
                    "year": year,
                    "month": bib.get("month"),
                    "journal": _clean(journal.get("title")) or None,
                    "journal_issns": journal.get("issns") or [],
                    "publisher": journal.get("publisher"),
                    "journal_country": journal.get("country"),
                    "languages": journal.get("language") or [],
                    "volume": journal.get("volume"),
                    "number": journal.get("number"),
                    "start_page": bib.get("start_page"),
                    "end_page": bib.get("end_page"),
                    "authors": [
                        {"name": a.get("name"), "orcid": a.get("orcid_id")}
                        for a in (bib.get("author") or [])[:MAX_AUTHORS]
                        if isinstance(a, dict)
                    ],
                    "keywords": bib.get("keywords") or [],
                    "subjects": [
                        {"scheme": s.get("scheme"), "code": s.get("code"), "term": s.get("term")}
                        for s in subjects
                    ],
                    "fulltext_urls": [lk.get("url") for lk in links if lk.get("url")],
                    "abstract": abstract,
                    "created": item.get("created_date"),
                    "last_updated": item.get("last_updated"),
                    "url": f"{SITE_URL}/article/{article_id}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting DOAJ article: {e}")
            return None
