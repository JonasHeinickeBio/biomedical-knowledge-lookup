"""
OpenAIRE Graph Knowledge Source Adapter

The OpenAIRE Graph links research products (publications, datasets, software, other), projects
(with funder, call and grant code), organisations and data sources (repositories, journals).
This adapter exposes *research products* (primary id = the OpenAIRE id, e.g.
``doi_dedup___::3e70f14256ea2d001e1c0b0d23f65ad1``; DOIs, ``PMID:``, ``PMC...`` and ``arXiv:``
ids are accepted and resolved through the ``pid`` filter) and *projects* (primary id
``project:<OpenAIRE id>``).

API (verified live 2026-10-09; the machine-readable spec is ``GET /graph/v3/api-docs``)::

    GET https://api.openaire.eu/graph/v3/research-products?search=<q>&type=<t>&pageSize=<n>
    GET https://api.openaire.eu/graph/v3/research-products?pid=<doi|pmid|pmc|arxiv>
    GET https://api.openaire.eu/graph/v3/research-products/<openaire id>
    GET https://api.openaire.eu/graph/v3/research-products?relProjectId=<project id>
    GET https://api.openaire.eu/graph/v3/research-products/links?sourcePid=<doi>   (Scholix)
    GET https://api.openaire.eu/graph/v3/projects?search=<q> | projects/<id>

Version note: the brief for this adapter named ``v1``, but v1 and v2 are marked *deprecated* in
the live OpenAPI description and, more importantly, v1 omits the ``projects``,
``organizations``, ``links`` and ``collectedFrom`` blocks that the relationships need. v3 is
the current version (v4 is a beta with a different filter grammar); only v3 is used here.

Quirks measured live:

* ``pageSize`` is capped at 100 (HTTP 400 above that). ``page``-based paging stops at 10,000
  records; ``cursor`` paging is not used because ``limit`` is small.
* ``search`` is a full-text query over title and abstract with ``AND``/``OR``/``NOT`` (upper
  case only; lower-case words are search terms). Several words are AND-ed.
* ``pid`` matching is case-insensitive and works for DOI, PMID, PMC id and arXiv number.
* Unknown ids answer HTTP 404 (JSON), an unmatched ``pid`` answers 200 with ``results: []``.
* The same ``type`` of record can come from many sources, so ``type=publication`` also
  returns theses, conference objects and preprints (see ``instances[].type``).
* ``openAccessColor`` is ``null`` for most records; ``bestAccessRight`` is the best right
  among all instances of the product (``OPEN``, ``CLOSED``, ``EMBARGO``, ``RESTRICTED``...),
  while ``instances[].license`` and ``instances[].accessRight`` are per copy and often absent.
  The adapter reports exactly these fields and never infers a licence.

Rate limits and terms: the OpenAIRE terms of use page states 60 requests per hour for
anonymous callers and 7,200 per hour for authenticated callers (sliding one-hour window; the
live ``x-ratelimit-limit`` header currently reports 7,199 for anonymous calls, i.e. the
documented anonymous limit is not enforced today). Optional personal access tokens (valid for
one hour) are read from ``OPENAIRE_ACCESS_TOKEN`` and sent only as ``Authorization: Bearer``;
nothing is sent when it is unset. Requests are spaced by at least one second (<= 3,600/hour).
HTTP 429 makes the adapter return ``[]`` / ``None`` like any other failure.
Graph records are CC-BY 4.0: credit OpenAIRE as the data source.
"""

import logging
import os
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._vocab_common import Spacer

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openaire.eu/graph/v3"
EXPLORE_URL = "https://explore.openaire.eu"
TOKEN_ENV = "OPENAIRE_ACCESS_TOKEN"
MAX_PAGE_SIZE = 100  # hard limit of the API (HTTP 400 above it)
DEFAULT_REL_LIMIT = 25
MIN_INTERVAL = 1.0  # seconds between requests: at most 3,600/hour, well under 7,200
PRODUCT_TYPES = ("publication", "dataset", "software", "other")
MAX_ABSTRACT_CHARS = 4000
MAX_INSTANCES = 10
MAX_AUTHORS = 10
MAX_PROJECT_HITS = 3  # projects mixed into an unfiltered search_concepts call

_OAID_RE = re.compile(r"(?<![0-9a-z_])([a-z0-9_]{12}::[0-9a-f]{32})(?![0-9a-f])", re.IGNORECASE)
_PREFIX_RE = re.compile(r"^(?:openaire:)?(?:\d\d\|)?", re.IGNORECASE)
_DOI_RE = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
_PMID_RE = re.compile(
    r"^(?:PMID:?\s*|https?://pubmed\.ncbi\.nlm\.nih\.gov/)(\d{1,9})/?$", re.IGNORECASE
)
_PMC_RE = re.compile(
    r"^(?:https?://(?:www\.)?ncbi\.nlm\.nih\.gov/pmc/articles/)?(PMC\d{1,9})/?$", re.IGNORECASE
)
_ARXIV_RE = re.compile(
    r"^(?:arxiv:\s*|https?://arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")

#: OpenAIRE pid scheme -> label used in mapping ``toSource``.
PID_LABELS = {
    "doi": "DOI",
    "pmid": "PMID",
    "pmc": "PMCID",
    "arxiv": "ARXIV",
    "handle": "HANDLE",
}


def strip_prefix(value: str | None) -> str:
    """``50|doi_dedup___::abc`` / ``openaire:...`` -> bare OpenAIRE id."""
    return _PREFIX_RE.sub("", (value or "").strip())


def _text(value: Any) -> str:
    """Plain text of a possibly HTML-bearing string (titles contain ``<i>`` markup)."""
    return re.sub(r"\s+", " ", _TAG_RE.sub("", str(value or ""))).strip()


def _snake(name: str | None) -> str:
    """``isSupplementedBy`` -> ``is_supplemented_by`` (Scholix relation names)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name or "related_to").lower()


class OpenAIREAdapter(KnowledgeSourceAdapter):
    """Adapter for OpenAIRE Graph research products and projects (keyless; optional token)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self._spacer = Spacer(MIN_INTERVAL)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OPENAIRE

    def is_available(self) -> bool:
        return True  # public API; the token only raises the hourly request limit

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str, str] | None:
        """Classify an identifier as ``(kind, value)``.

        * ``("project", id)`` for ``project:<OpenAIRE id>``;
        * ``("oaid", id)`` for a bare OpenAIRE id (``50|...``, ``openaire:...`` and explore
          URLs accepted); it may name a product or a project, the caller tries both;
        * ``("pid", value)`` for DOIs (bare, ``doi:``, ``https://doi.org/``), ``PMID:123`` /
          PubMed URLs, ``PMC123`` and ``arXiv:2003.06265``. Bare digits are *not* ids.
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        if text.lower().startswith("project:"):
            match = _OAID_RE.search(text[8:])
            return ("project", strip_prefix(match.group(1))) if match else None
        if text.lower().startswith(("http://", "https://")) and "::" in text:
            match = _OAID_RE.search(text)
            if match:
                return "oaid", match.group(1)
        if match := _OAID_RE.fullmatch(strip_prefix(text)):
            return "oaid", match.group(1)
        if match := _DOI_RE.match(text):
            return "pid", match.group(1)
        if match := _PMID_RE.match(text):
            return "pid", match.group(1)
        if match := _PMC_RE.match(text):
            return "pid", match.group(1).upper()
        if match := _ARXIV_RE.match(text):
            return "pid", match.group(1)
        return None

    def _headers(self) -> dict[str, str]:
        """Bearer header only when ``OPENAIRE_ACCESS_TOKEN`` is set; nothing otherwise."""
        token = os.getenv(TOKEN_ENV)
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Spaced GET ``BASE_URL/path``; ``None`` on any failure (404 included)."""
        try:
            await self._spacer.wait()
            return await self._make_request(
                f"{BASE_URL}/{path}", params=params, headers=self._headers()
            )
        except Exception as e:
            if getattr(e, "status", None) == 404:
                logger.debug(f"OpenAIRE /{path} not found")
            else:
                logger.warning(f"OpenAIRE request /{path} failed: {e}")
            return None

    @staticmethod
    def _results(data: Any) -> list[dict[str, Any]]:
        results = data.get("results") if isinstance(data, dict) else None
        return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_products(
        self,
        query: str,
        limit: int = 20,
        product_type: str | None = None,
        open_access_only: bool = False,
        from_year: int | None = None,
    ) -> list[UnifiedConcept]:
        """Full-text search over research products (``limit`` <= 100).

        ``product_type`` is one of ``publication``, ``dataset``, ``software``, ``other``;
        ``open_access_only`` sets ``accessRightLabel="Open Access"`` (the best right among
        all copies); ``from_year`` sets ``fromPublicationYear``.
        """
        try:
            limit = max(0, min(int(limit), MAX_PAGE_SIZE))
            query = (query or "").strip()
            if limit == 0 or not query:
                return []
            params: dict[str, Any] = {"search": query, "pageSize": limit}
            if product_type:
                if product_type.lower() not in PRODUCT_TYPES:
                    logger.warning(f"OpenAIRE: unknown product type '{product_type}'")
                    return []
                params["type"] = product_type.lower()
            if open_access_only:
                params["accessRightLabel"] = '"Open Access"'
            if from_year:
                params["fromPublicationYear"] = int(from_year)
            data = await self._get("research-products", params)
            return self._convert_list(self._results(data), self._product_to_concept, limit)
        except Exception as e:
            logger.error(f"OpenAIRE search_products failed for '{query}': {e}")
            return []

    async def search_projects(self, query: str, limit: int = 10) -> list[UnifiedConcept]:
        """Full-text search over projects (title, keywords, summary); ``limit`` <= 100."""
        try:
            limit = max(0, min(int(limit), MAX_PAGE_SIZE))
            query = (query or "").strip()
            if limit == 0 or not query:
                return []
            data = await self._get("projects", {"search": query, "pageSize": limit})
            return self._convert_list(self._results(data), self._project_to_concept, limit)
        except Exception as e:
            logger.error(f"OpenAIRE search_projects failed for '{query}': {e}")
            return []

    async def search_concepts(
        self, query: str, limit: int = 20, product_type: str | None = None
    ) -> list[UnifiedConcept]:
        """Search research products; without ``product_type`` up to 3 projects are appended.

        A DOI / PMID / PMC / arXiv / OpenAIRE id as the query resolves to that record.
        ``product_type`` (``publication``, ``dataset``, ``software``, ``other``) restricts the
        search to that kind of product and skips the project lookup.
        """
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.parse_id(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            n_projects = 0 if product_type or limit < 6 else min(MAX_PROJECT_HITS, limit // 4)
            products = await self.search_products(query, limit - n_projects, product_type)
            projects = await self.search_projects(query, n_projects) if n_projects else []
            return (products + projects)[:limit]
        except Exception as e:
            logger.error(f"OpenAIRE search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Product (OpenAIRE id, DOI, PMID, PMC, arXiv) or project (``project:<id>``)."""
        try:
            parsed = self.parse_id(concept_id)
            if parsed is None:
                return None
            kind, value = parsed
            if kind != "project":
                item = await self._product_record(kind, value)
                if item:
                    return self._product_to_concept(item)
            if kind in ("project", "oaid"):
                item = await self._project_record(value)
                return self._project_to_concept(item) if item else None
            return None
        except Exception as e:
            logger.error(f"OpenAIRE get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = DEFAULT_REL_LIMIT
    ) -> list[dict[str, Any]]:
        """Typed edges. ``limit`` caps every group (projects, organisations, ...).

        Product: ``funded_by`` projects (with ``funder``, ``grant_code``, ``funding_stream``),
        ``affiliated_with`` organisations (ROR in ``ror``), ``hosted_by`` repositories/journals
        (the data sources holding a copy, with that copy's ``license`` and ``access_right``),
        ``collected_from`` sources the record was harvested from and, for products with a
        DOI, Scholix links to other products (``cites``, ``is_supplemented_by``, ... as
        reported by OpenAIRE). Project: ``funded_by`` funder, ``has_participant``
        organisations and ``has_output`` products (the first ``limit``; ``total_outputs`` is
        the full count). ``limit=0`` returns ``[]``.
        """
        try:
            limit = max(0, min(int(limit), MAX_PAGE_SIZE))
            parsed = self.parse_id(concept_id)
            if parsed is None or limit == 0:
                return []
            kind, value = parsed
            if kind != "project":
                item = await self._product_record(kind, value)
                if item:
                    return await self._product_edges(item, limit)
            if kind in ("project", "oaid"):
                item = await self._project_record(value)
                if item:
                    return await self._project_edges(item, limit)
            return []
        except Exception as e:
            logger.warning(f"OpenAIRE get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Product -> DOI, PMID, PMCID, arXiv and handle ids; projects have none (``[]``)."""
        try:
            parsed = self.parse_id(concept_id)
            if parsed is None:
                return []
            kind, value = parsed
            if kind != "project":
                item = await self._product_record(kind, value)
                if item:
                    return self._mappings(strip_prefix(item.get("id")), self._all_pids(item))
            return []  # project records carry no persistent ids in the v3 API
        except Exception as e:
            logger.warning(f"OpenAIRE get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_project_outputs(
        self, project_id: str, limit: int = DEFAULT_REL_LIMIT
    ) -> list[UnifiedConcept]:
        """Research products produced by a project (``relProjectId``), at most ``limit``."""
        try:
            limit = max(0, min(int(limit), MAX_PAGE_SIZE))
            parsed = self.parse_id(project_id)
            if parsed is None or parsed[0] == "pid" or limit == 0:
                return []
            data = await self._get(
                "research-products", {"relProjectId": parsed[1], "pageSize": limit}
            )
            return self._convert_list(self._results(data), self._product_to_concept, limit)
        except Exception as e:
            logger.error(f"OpenAIRE get_project_outputs failed for '{project_id}': {e}")
            return []

    # ------------------------------------------------------------------
    # Record fetching
    # ------------------------------------------------------------------

    async def _product_record(self, kind: str, value: str) -> dict[str, Any] | None:
        """Full product record by OpenAIRE id (``oaid``) or by persistent id (``pid``)."""
        if kind == "oaid":
            data = await self._get(f"research-products/{value}")
            return data if isinstance(data, dict) and data.get("id") else None
        data = await self._get("research-products", {"pid": f'"{value}"', "pageSize": 1})
        results = self._results(data)
        return results[0] if results else None

    async def _project_record(self, project_id: str) -> dict[str, Any] | None:
        data = await self._get(f"projects/{project_id}")
        return data if isinstance(data, dict) and data.get("id") else None

    # ------------------------------------------------------------------
    # Relationship helpers
    # ------------------------------------------------------------------

    async def _product_edges(self, item: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        streams = self._project_links(item)
        for proj in (item.get("projects") or [])[:limit]:
            pid = strip_prefix(proj.get("id"))
            if not pid:
                continue
            link = streams.get(pid, {})
            title = _text(proj.get("title"))
            if title.lower() == "unidentified":  # funder-only link without a grant record
                title = f"{proj.get('funder') or 'unknown funder'} (unidentified project)"
            edges.append(
                {
                    "relation_label": "funded_by",
                    "related_id": f"project:{pid}",
                    "related_name": title or pid,
                    "source": "OPENAIRE",
                    "funder": proj.get("funder"),
                    "grant_code": proj.get("code"),
                    "acronym": proj.get("acronym"),
                    "funding_stream": link.get("stream"),
                    "trust": link.get("trust"),
                }
            )
        for org in (item.get("organizations") or [])[:limit]:
            oid = strip_prefix(org.get("id"))
            name = org.get("legalName") or org.get("acronym") or oid
            if oid:
                edges.append(
                    {
                        "relation_label": "affiliated_with",
                        "related_id": oid,
                        "related_name": name,
                        "source": "OPENAIRE",
                        "ror": next(
                            (
                                p.get("value")
                                for p in org.get("pids") or []
                                if str(p.get("scheme")).upper() == "ROR"
                            ),
                            None,
                        ),
                        "country": [c.get("code") for c in org.get("countries") or []],
                    }
                )
        edges += self._hosting_edges(item, limit)
        seen: set[str] = set()
        for src in (item.get("collectedFrom") or [])[:limit]:
            key = src.get("key") if isinstance(src, dict) else None
            if key and key not in seen:
                seen.add(key)
                edges.append(
                    {
                        "relation_label": "collected_from",
                        "related_id": strip_prefix(key),
                        "related_name": src.get("value") or key,
                        "source": "OPENAIRE",
                    }
                )
        doi = next((v for s, v in self._all_pids(item) if s == "doi"), None)
        if doi:
            edges += await self._scholix_edges(doi, limit)
        return edges

    @staticmethod
    def _hosting_edges(item: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        """One ``hosted_by`` edge per data source, merging licence/access of its copies."""
        hosts: dict[str, dict[str, Any]] = {}
        for inst in item.get("instances") or []:
            host = inst.get("hostedBy") or {}
            key = host.get("key")
            if not key:
                continue
            edge = hosts.setdefault(
                key,
                {
                    "relation_label": "hosted_by",
                    "related_id": strip_prefix(key),
                    "related_name": host.get("value") or key,
                    "source": "OPENAIRE",
                    "license": None,
                    "access_right": None,
                    "urls": [],
                },
            )
            edge["license"] = edge["license"] or inst.get("license")
            right = inst.get("accessRight") or {}
            edge["access_right"] = edge["access_right"] or right.get("label")
            edge["urls"] += [u for u in inst.get("urls") or [] if u not in edge["urls"]][:2]
        return list(hosts.values())[:limit]

    async def _scholix_edges(self, doi: str, limit: int) -> list[dict[str, Any]]:
        """Scholix links where this product is the source (``links?sourcePid=``)."""
        data = await self._get(
            "research-products/links", {"sourcePid": doi, "pageSize": min(limit, MAX_PAGE_SIZE)}
        )
        results = self._results(data)
        total = (data.get("header") or {}).get("totalLinks") if isinstance(data, dict) else None
        edges = []
        seen: set[tuple[str, str]] = set()
        for link in results:
            target = link.get("target") or {}
            idents = {
                str(i.get("idScheme")).lower(): i.get("id")
                for i in target.get("identifiers") or []
            }
            related = strip_prefix(idents.get("openaireidentifier")) or (
                f"doi:{idents['doi']}" if idents.get("doi") else None
            )
            label = _snake((link.get("relType") or {}).get("name"))
            if not related or (label, related) in seen:
                continue
            seen.add((label, related))
            edges.append(
                {
                    "relation_label": label,
                    "related_id": related,
                    "related_name": _text(target.get("title")) or related,
                    "source": "OPENAIRE",
                    "doi": idents.get("doi"),
                    "year": str(target.get("publicationDate") or "")[:4] or None,
                    "provenance": [p for p in link.get("provenance") or [] if p],
                    "total_links": total,
                }
            )
        return edges[:limit]

    async def _project_edges(self, item: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        funder = (item.get("funding") or {}).get("funder") or {}
        if funder.get("id") or funder.get("name"):
            edges.append(
                {
                    "relation_label": "funded_by",
                    "related_id": strip_prefix(funder.get("id")) or funder.get("name"),
                    "related_name": funder.get("name") or funder.get("shortname"),
                    "source": "OPENAIRE",
                    "jurisdiction": (funder.get("jurisdiction") or {}).get("code"),
                    "funding_stream": ((item.get("funding") or {}).get("level0") or {}).get(
                        "name"
                    ),
                }
            )
        participants = 0
        for link in item.get("links") or []:
            head = link.get("header") or {}
            if head.get("relationClass") != "hasParticipant" or participants >= limit:
                continue
            oid = strip_prefix(head.get("relatedIdentifier"))
            if oid:
                participants += 1
                edges.append(
                    {
                        "relation_label": "has_participant",
                        "related_id": oid,
                        "related_name": link.get("legalname") or link.get("legalshortname") or oid,
                        "source": "OPENAIRE",
                        "ror": next(
                            (
                                p.get("value")
                                for p in link.get("pid") or []
                                if str(p.get("typeCode")).upper() == "ROR"
                            ),
                            None,
                        ),
                        "country": (link.get("country") or {}).get("code"),
                    }
                )
        data = await self._get(
            "research-products",
            {"relProjectId": strip_prefix(item.get("id")), "pageSize": limit},
        )
        total = (data.get("header") or {}).get("numFound") if isinstance(data, dict) else None
        for prod in self._results(data)[:limit]:
            pid = strip_prefix(prod.get("id"))
            title = _text(prod.get("mainTitle"))
            if pid and title:
                edges.append(
                    {
                        "relation_label": "has_output",
                        "related_id": pid,
                        "related_name": title,
                        "source": "OPENAIRE",
                        "product_type": prod.get("type"),
                        "year": str(prod.get("publicationDate") or "")[:4] or None,
                        "total_outputs": total,
                    }
                )
        return edges

    @staticmethod
    def _project_links(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """``links`` of type resultProject -> {project id: funding stream path, trust}."""
        found: dict[str, dict[str, Any]] = {}
        for link in item.get("links") or []:
            head = link.get("header") or {}
            if head.get("relationType") != "resultProject":
                continue
            funding = link.get("funding") or {}
            levels = [(funding.get(k) or {}).get("name") for k in ("level0", "level1", "level2")]
            found[strip_prefix(head.get("relatedIdentifier"))] = {
                "stream": " / ".join(v for v in levels if v) or None,
                "trust": head.get("trust"),
            }
        return found

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pid_pairs(pids: Any) -> list[tuple[str, str]]:
        return [
            (str(p["scheme"]).lower(), str(p["value"]))
            for p in pids or []
            if isinstance(p, dict) and p.get("scheme") and p.get("value")
        ]

    @classmethod
    def _all_pids(cls, item: dict[str, Any]) -> list[tuple[str, str]]:
        """Persistent ids of a product: record level first, then the per-copy ids (deduped)."""
        pairs = cls._pid_pairs(item.get("pids"))
        for inst in item.get("instances") or []:
            for key in ("pids", "alternateIdentifiers"):
                pairs += cls._pid_pairs(inst.get(key))
        return list(dict.fromkeys(pairs))

    @staticmethod
    def _mappings(from_id: str, pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
        mappings = []
        for scheme, value in dict.fromkeys(pairs):
            value = (
                re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value) if scheme == "doi" else value
            )
            mappings.append(
                {
                    "fromId": from_id,
                    "toId": value.lower() if scheme == "doi" else value,
                    "fromSource": "OPENAIRE",
                    "toSource": PID_LABELS.get(scheme, scheme.upper()),
                    "mappingType": "exact",
                    "confidence": 1.0,
                }
            )
        return mappings

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

    def _product_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a v3 research-product record (type CITATION for publications)."""
        try:
            product_id = strip_prefix(item.get("id"))
            title = _text(item.get("mainTitle"))
            if not product_id or not title:
                return None
            kind = str(item.get("type") or "")
            concept = self._create_concept(
                product_id,
                title,
                ConceptType.CITATION if kind == "publication" else ConceptType.REFERENCE,
            )
            pairs = self._all_pids(item)
            by_scheme: dict[str, str] = {}
            for scheme, value in pairs:
                by_scheme.setdefault(scheme, value)
            doi = (by_scheme.get("doi") or "").lower() or None
            pmid, pmc = by_scheme.get("pmid"), by_scheme.get("pmc")
            descriptions = [_text(d) for d in item.get("descriptions") or [] if _text(d)]
            abstract = descriptions[0][:MAX_ABSTRACT_CHARS] if descriptions else None
            year = str(item.get("publicationDate") or "")[:4] or None
            container = item.get("container") or {}
            journal = container.get("name")
            keywords = [
                s["subject"]["value"]
                for s in item.get("subjects") or []
                if isinstance(s, dict)
                and (s.get("subject") or {}).get("scheme") == "keyword"
                and s["subject"].get("value")
            ]
            best = item.get("bestAccessRight") or {}
            instances = [inst for inst in item.get("instances") or [] if isinstance(inst, dict)]
            licenses = list(dict.fromkeys(i["license"] for i in instances if i.get("license")))
            if abstract and concept.definitions is not None:
                concept.definitions.append(abstract)
            if concept.semantic_types is not None and kind:
                concept.semantic_types.append(kind)
            if concept.categories is not None:
                if year:
                    concept.categories.append(f"year:{year}")
                if journal:
                    concept.categories.append(f"journal:{journal}")
                if best.get("label"):
                    concept.categories.append(f"access:{best['label']}")
                if item.get("openAccessColor"):
                    concept.categories.append(f"oa:{item['openAccessColor']}")
            if concept.synonyms is not None:
                concept.synonyms.extend(dict.fromkeys(keywords))
                concept.synonyms.extend(
                    t for t in (_text(o) for o in item.get("otherTitles") or []) if t
                )
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
            if pmc:
                concept.add_identifier(KnowledgeSource.EUROPEPMC, pmc, title)
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OPENAIRE] = {
                    "id": product_id,
                    "type": kind or None,
                    "doi": doi,
                    "pmid": pmid,
                    "pmcid": pmc,
                    "arxiv": by_scheme.get("arxiv"),
                    "pids": [{"scheme": s, "value": v} for s, v in pairs],
                    "publication_date": item.get("publicationDate"),
                    "year": year,
                    "publisher": item.get("publisher"),
                    "language": (item.get("language") or {}).get("label"),
                    "journal": journal,
                    "issn_print": container.get("issnPrinted"),
                    "issn_online": container.get("issnOnline"),
                    "authors": [
                        {
                            "name": a.get("fullName"),
                            "orcid": (((a.get("pid") or {}).get("id")) or {}).get("value"),
                        }
                        for a in (item.get("authors") or [])[:MAX_AUTHORS]
                        if isinstance(a, dict)
                    ],
                    "open_access": {
                        "best_access_right": best.get("label"),
                        "best_access_right_code": best.get("code"),
                        "color": item.get("openAccessColor"),
                        "is_green": item.get("isGreen"),
                        "is_in_diamond_journal": item.get("isInDiamondJournal"),
                        "publicly_funded": item.get("publiclyFunded"),
                        "embargo_end_date": item.get("embargoEndDate"),
                        "licenses": licenses,
                    },
                    "instances": [self._instance_summary(i) for i in instances[:MAX_INSTANCES]],
                    "n_instances": len(instances),
                    "projects": [
                        {
                            "id": strip_prefix(p.get("id")),
                            "code": p.get("code"),
                            "acronym": p.get("acronym"),
                            "title": _text(p.get("title")),
                            "funder": p.get("funder"),
                        }
                        for p in item.get("projects") or []
                        if isinstance(p, dict)
                    ],
                    "organizations": [
                        {"id": strip_prefix(o.get("id")), "name": o.get("legalName")}
                        for o in item.get("organizations") or []
                        if isinstance(o, dict)
                    ],
                    "collected_from": [
                        c.get("value") for c in item.get("collectedFrom") or [] if c
                    ],
                    "communities": [c.get("label") for c in item.get("communities") or [] if c],
                    "keywords": keywords,
                    "citation_count": (
                        (item.get("indicators") or {}).get("citationImpact") or {}
                    ).get("citationCount"),
                    "citation_class": (
                        (item.get("indicators") or {}).get("citationImpact") or {}
                    ).get("citationClass"),
                    "abstract": abstract,
                    "url": f"{EXPLORE_URL}/search/result?id={product_id}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting OpenAIRE product: {e}")
            return None

    @staticmethod
    def _instance_summary(inst: dict[str, Any]) -> dict[str, Any]:
        right = inst.get("accessRight") or {}
        return {
            "type": inst.get("type"),
            "license": inst.get("license"),
            "access_right": right.get("label"),
            "open_access_route": right.get("openAccessRoute"),
            "refereed": inst.get("refereed"),
            "urls": (inst.get("urls") or [])[:2],
            "hosted_by": (inst.get("hostedBy") or {}).get("value"),
            "collected_from": (inst.get("collectedFrom") or {}).get("value"),
            "publication_date": inst.get("publicationDate"),
        }

    def _project_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a v3 project record (concept id ``project:<OpenAIRE id>``, type UNKNOWN)."""
        try:
            raw_id = strip_prefix(item.get("id"))
            title = _text(item.get("title"))
            if not raw_id or not title:
                return None
            concept = self._create_concept(f"project:{raw_id}", title, ConceptType.UNKNOWN)
            funding = item.get("funding") or {}
            funder = funding.get("funder") or {}
            stream = " / ".join(
                v
                for v in (
                    (funding.get(k) or {}).get("name") for k in ("level0", "level1", "level2")
                )
                if v
            )
            summary = _text(item.get("summary"))
            if summary and concept.definitions is not None:
                concept.definitions.append(summary[:MAX_ABSTRACT_CHARS])
            if concept.synonyms is not None:
                if item.get("acronym"):
                    concept.synonyms.append(item["acronym"])
                concept.synonyms.extend(
                    k.strip() for k in str(item.get("keywords") or "").split(",") if k.strip()
                )
            if concept.categories is not None:
                if funder.get("name"):
                    concept.categories.append(f"funder:{funder['name']}")
                if stream:
                    concept.categories.append(f"stream:{stream}")
            if concept.semantic_types is not None:
                concept.semantic_types.append("project")
            concept.confidence_score = 0.8
            granted = item.get("granted") or {}
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OPENAIRE] = {
                    "id": raw_id,
                    "kind": "project",
                    "code": item.get("code"),
                    "acronym": item.get("acronym"),
                    "call": item.get("callIdentifier"),
                    "funder": funder.get("name"),
                    "funder_short_name": funder.get("shortname"),
                    "jurisdiction": (funder.get("jurisdiction") or {}).get("code"),
                    "funding_stream": stream or None,
                    "start_date": item.get("startDate"),
                    "end_date": item.get("endDate"),
                    "keywords": item.get("keywords"),
                    "website": item.get("websiteUrl"),
                    "oa_mandate_publications": item.get("openAccessMandateForPublications"),
                    "oa_mandate_datasets": item.get("openAccessMandateForDataset"),
                    "funded_amount": granted.get("fundedAmount"),
                    "total_cost": granted.get("totalCost"),
                    "currency": granted.get("currency"),
                    "url": f"{EXPLORE_URL}/search/project?projectId={raw_id}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting OpenAIRE project: {e}")
            return None
