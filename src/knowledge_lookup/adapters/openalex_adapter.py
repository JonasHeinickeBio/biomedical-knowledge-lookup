"""
OpenAlex Knowledge Source Adapter

OpenAlex (OurResearch) is an open catalogue of scholarly works, authors, venues and research
topics with a citation graph. This adapter exposes *works* (primary id ``W...``; DOI and PMID
forms are accepted) and *topics* (``T...``).

API (verified live 2026-10-07)::

    GET https://api.openalex.org/works?search=<q>&per-page=<n>&select=<fields>
    GET https://api.openalex.org/works/W4316014106 | pmid:36639608 | doi:10.1038/s41579-022-00846-2
    GET https://api.openalex.org/works?filter=cites:W...        (works citing W...)
    GET https://api.openalex.org/works?filter=openalex:W1|W2     (batch lookup, <= 100 ids)
    GET https://api.openalex.org/topics?search=<q> | topics/T11368

Rate limits and cost (changed from the old "10 req/s polite pool" policy; measured from the
``X-RateLimit-*`` response headers, which :meth:`_make_request` does not expose):

* Keyless use gets a daily budget of 1000 credits (USD 0.10). A singleton lookup
  (``works/W...``, ``works/pmid:...``, ``topics/T...``) costs **0** credits, a ``filter``
  list costs 1 credit, a ``search`` list costs **10** credits (so about 100 searches per day).
  A free API key (``OPENALEX_API_KEY``, sent as ``api_key``) raises the budget tenfold.
  HTTP 429 means the budget is spent or more than 100 req/s were made; the adapter then
  returns ``[]`` / ``None`` like for any other failure.
* The optional "polite" ``mailto`` parameter is sent **only** when the environment variable
  ``OPENALEX_MAILTO`` is set; it is never read from anywhere else and nothing is sent
  otherwise (it had no measurable effect on the cost headers).
* ``search`` is matched against full text as well as title/abstract and is therefore broad
  (335k hits for "chronic fatigue syndrome"); results are relevance ranked.
* ``abstract_inverted_index`` is ``null`` for many works (publisher restrictions, e.g. most
  Nature/Elsevier reviews); the abstract is rebuilt from it when present.
* Unknown ids answer HTTP 404 with an HTML body; PMCID is returned in ``ids`` but
  ``works/pmcid:...`` is not a usable lookup form.

Data is CC0. Citation counts are OpenAlex's own and differ from PubMed/Scopus/WoS.
"""

import asyncio
import logging
import os
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"
MAX_PER_PAGE = 100  # OpenAlex hard limit for per-page
DEFAULT_REL_LIMIT = 25
MAILTO_ENV = "OPENALEX_MAILTO"
API_KEY_ENV = "OPENALEX_API_KEY"

#: Fields requested for work records (keeps list responses small; the full record is ~25 KB).
WORK_FIELDS = ",".join(
    [
        "id",
        "doi",
        "title",
        "display_name",
        "publication_year",
        "publication_date",
        "type",
        "language",
        "ids",
        "primary_location",
        "open_access",
        "authorships",
        "biblio",
        "cited_by_count",
        "referenced_works_count",
        "fwci",
        "is_retracted",
        "primary_topic",
        "topics",
        "keywords",
        "concepts",
        "abstract_inverted_index",
    ]
)
BRIEF_FIELDS = "id,doi,display_name,publication_year,cited_by_count"
TOPIC_FIELDS = (
    "id,display_name,description,keywords,ids,subfield,field,domain,works_count,siblings"
)

_WORK_RE = re.compile(r"^(?:OPENALEX:)?(?:https?://openalex\.org/)?(W\d+)$", re.IGNORECASE)
_TOPIC_RE = re.compile(
    r"^(?:OPENALEX:)?(?:https?://openalex\.org/(?:topics/)?)?(T\d+)$", re.IGNORECASE
)
_DOI_RE = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
_PMID_RE = re.compile(
    r"^(?:PMID:?\s*|pmid:|https?://pubmed\.ncbi\.nlm\.nih\.gov/)?(\d{1,9})/?$", re.I
)
_MAG_RE = re.compile(r"^mag:(\d+)$", re.IGNORECASE)
_FILTER_VALUE_RE = re.compile(r"^[\w.:|<>,\- /()]+$")

#: Friendly ``filters`` keys for :meth:`search_works` -> OpenAlex filter names.
FILTER_ALIASES = {
    "year": "publication_year",
    "type": "type",
    "open_access": "open_access.is_oa",
    "oa": "open_access.is_oa",
    "topic": "topics.id",
    "primary_topic": "primary_topic.id",
    "from_date": "from_publication_date",
    "to_date": "to_publication_date",
    "cites": "cites",
    "has_abstract": "has_abstract",
    "language": "language",
}


def short_id(value: str | None) -> str:
    """``https://openalex.org/W123`` -> ``W123`` (other URLs: last path component)."""
    return (value or "").rstrip("/").rsplit("/", 1)[-1]


def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Rebuild abstract text from OpenAlex's ``abstract_inverted_index`` ({word: [positions]})."""
    if not isinstance(inverted, dict) or not inverted:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted.items():
        if isinstance(positions, list):
            for pos in positions:
                if isinstance(pos, int):
                    words[pos] = word
    return " ".join(words[p] for p in sorted(words))


class OpenAlexAdapter(KnowledgeSourceAdapter):
    """Adapter for OpenAlex works and topics (keyless; optional key and polite-pool mailto)."""

    min_request_timeout = 30.0

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get_api_key("openalex") or os.getenv(API_KEY_ENV)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OPENALEX

    def is_available(self) -> bool:
        return True  # public API; the key only raises the daily budget

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_id(concept_id: str) -> tuple[str, str] | None:
        """Classify an identifier: ``("work", path)`` or ``("topic", "T123")``.

        ``path`` is what follows ``/works/``: ``W123``, ``pmid:123``, ``doi:10.x/y`` or
        ``mag:123``. Accepted: ``W123``, ``OPENALEX:W123``, ``https://openalex.org/W123``,
        DOIs (bare, ``doi:``, ``https://doi.org/...``), ``PMID:123`` / bare digits (PMID),
        PubMed URLs, ``mag:123`` and topic ids ``T123``.
        """
        text = (concept_id or "").strip()
        if not text:
            return None
        if match := _WORK_RE.match(text):
            return "work", match.group(1).upper()
        if match := _TOPIC_RE.match(text):
            return "topic", match.group(1).upper()
        if match := _DOI_RE.match(text):
            return "work", f"doi:{match.group(1).lower()}"
        if match := _MAG_RE.match(text):
            return "work", f"mag:{match.group(1)}"
        if match := _PMID_RE.match(text):
            return "work", f"pmid:{match.group(1)}"
        return None

    def _params(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Add the optional key / polite-pool mailto (the latter only from ``OPENALEX_MAILTO``)."""
        merged = dict(params or {})
        if self.api_key:
            merged["api_key"] = self.api_key
        mailto = os.getenv(MAILTO_ENV)
        if mailto:
            merged["mailto"] = mailto
        return merged

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """GET ``BASE_URL/path``; ``None`` on any failure (404 included) or non-object body."""
        try:
            data = await self._make_request(f"{BASE_URL}/{path}", params=self._params(params))
        except Exception as e:
            logger.warning(f"OpenAlex request /{path} failed: {e}")
            return None
        return data if isinstance(data, dict) else None

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
        """Search works (10 credits per call). ``limit`` <= 100.

        ``filters`` maps friendly names (``year``, ``type``, ``open_access``, ``topic``,
        ``from_date``, ``to_date``, ``cites``, ``has_abstract``, ``language``) or raw OpenAlex
        filter names to values; list values are OR-ed. ``sort`` is e.g.
        ``cited_by_count:desc`` or ``publication_date:desc`` (default: relevance).
        """
        try:
            limit = max(0, min(int(limit), MAX_PER_PAGE))
            if limit == 0 or not (query or "").strip():
                return []
            params: dict[str, Any] = {
                "search": query.strip(),
                "per-page": limit,
                "select": WORK_FIELDS,
            }
            filter_text = self._filter_text(filters)
            if filter_text:
                params["filter"] = filter_text
            if sort:
                params["sort"] = sort
            data = await self._get("works", params)
            return self._convert_list(data, self._work_to_concept, limit)
        except Exception as e:
            logger.error(f"OpenAlex search_works failed for '{query}': {e}")
            return []

    async def search_topics(self, query: str, limit: int = 5) -> list[UnifiedConcept]:
        """Search OpenAlex research topics (10 credits per call)."""
        try:
            limit = max(0, min(int(limit), MAX_PER_PAGE))
            if limit == 0 or not (query or "").strip():
                return []
            params = {"search": query.strip(), "per-page": limit, "select": TOPIC_FIELDS}
            data = await self._get("topics", params)
            return self._convert_list(data, self._topic_to_concept, limit)
        except Exception as e:
            logger.error(f"OpenAlex search_topics failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search works plus the best 3 matching topics (two searches = 20 credits).

        A DOI / PMID / OpenAlex id as the query resolves directly to that record (free).
        """
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            parsed = self.parse_id(query)
            # bare digits are ordinary search text (e.g. "2019"); only "PMID:..." / URLs are ids
            if parsed and (
                not parsed[1].startswith("pmid:") or query.lower().startswith(("pmid", "http"))
            ):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            n_topics = min(3, limit)
            works, topics = await asyncio.gather(
                self.search_works(query, limit), self.search_topics(query, n_topics)
            )
            return (works[: max(limit - len(topics), 1)] + topics)[:limit]
        except Exception as e:
            logger.error(f"OpenAlex search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Work (W-id, DOI, PMID, ``mag:``) or topic (``T...``) by singleton lookup (free)."""
        try:
            parsed = self.parse_id(concept_id)
            if parsed is None:
                return None
            kind, ident = parsed
            if kind == "topic":
                data = await self._get(f"topics/{ident}", {"select": TOPIC_FIELDS})
                return self._topic_to_concept(data) if data else None
            data = await self._get(f"works/{ident}", {"select": WORK_FIELDS})
            return self._work_to_concept(data) if data else None
        except Exception as e:
            logger.error(f"OpenAlex get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self, concept_id: str, limit: int = DEFAULT_REL_LIMIT
    ) -> list[dict[str, Any]]:
        """Typed edges for a work or topic. ``limit`` caps each citation direction.

        Work: ``has_topic`` (with OpenAlex's score), ``cites`` (referenced works, first
        ``limit`` in the record's order), ``cited_by`` (the ``limit`` most-cited citing works).
        ``cited_by`` edges carry ``total_citing`` (the full count from the response meta) and
        the work's ``cited_by_count`` is also in :meth:`get_concept_details`; ``limit=0`` skips
        both citation lookups. Costs 1 credit per citation direction (singletons are free).
        Topic: ``part_of`` subfield/field/domain and ``sibling_topic``.
        """
        try:
            limit = max(0, min(int(limit), MAX_PER_PAGE))
            parsed = self.parse_id(concept_id)
            if parsed is None:
                return []
            kind, ident = parsed
            if kind == "topic":
                return await self._topic_relationships(ident, limit)
            fields = "id,referenced_works,topics"
            record = await self._get(f"works/{ident}", {"select": fields})
            if not record:
                return []
            work_id = short_id(record.get("id"))
            relationships = self._topic_edges(record)
            if limit:
                cited, citing = await asyncio.gather(
                    self._referenced_edges(record, limit), self._citing_edges(work_id, limit)
                )
                relationships += cited + citing
            return relationships
        except Exception as e:
            logger.warning(f"OpenAlex get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Work -> DOI, PMID, PMCID and MAG ids (from ``ids``); topic -> Wikipedia page."""
        try:
            parsed = self.parse_id(concept_id)
            if parsed is None:
                return []
            kind, ident = parsed
            path = f"topics/{ident}" if kind == "topic" else f"works/{ident}"
            record = await self._get(path, {"select": "id,ids"})
            if not record:
                return []
            from_id = short_id(record.get("id")) or ident
            mappings = []
            for key, label in (
                ("doi", "DOI"),
                ("pmid", "PMID"),
                ("pmcid", "PMCID"),
                ("mag", "MAG"),
                ("wikipedia", "Wikipedia"),
                ("wikidata", "Wikidata"),
            ):
                value = (record.get("ids") or {}).get(key)
                if value:
                    mappings.append(
                        {
                            "fromId": from_id,
                            "toId": self._clean_external(key, str(value)),
                            "fromSource": "OPENALEX",
                            "toSource": label,
                            "mappingType": "exact",
                            "confidence": 1.0,
                        }
                    )
            return mappings
        except Exception as e:
            logger.warning(f"OpenAlex get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_referenced_works(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Works cited by this work (``cites`` edges only)."""
        rels = await self.get_relationships(concept_id, limit)
        return [r for r in rels if r["relation_label"] == "cites"]

    async def get_citing_works(self, concept_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Most-cited works that cite this work (``cited_by`` edges only)."""
        rels = await self.get_relationships(concept_id, limit)
        return [r for r in rels if r["relation_label"] == "cited_by"]

    # ------------------------------------------------------------------
    # Relationship helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_external(key: str, value: str) -> str:
        """Strip the URL prefix of PMID / DOI values (``https://doi.org/10.x`` -> ``10.x``)."""
        if key == "doi":
            return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
        if key == "pmid":
            return value.rstrip("/").rsplit("/", 1)[-1]
        if key == "pmcid":
            return value.rstrip("/").rsplit("/", 1)[-1]
        return value

    @staticmethod
    def _topic_edges(record: dict[str, Any]) -> list[dict[str, Any]]:
        edges = []
        for topic in record.get("topics") or []:
            tid = short_id(topic.get("id"))
            if tid:
                edges.append(
                    {
                        "relation_label": "has_topic",
                        "related_id": tid,
                        "related_name": topic.get("display_name") or tid,
                        "source": "OPENALEX",
                        "score": topic.get("score"),
                        "field": (topic.get("field") or {}).get("display_name"),
                    }
                )
        return edges

    async def _brief_works(self, ids: list[str], per_page: int) -> dict[str, dict[str, Any]]:
        """Batch title lookup: one ``filter=openalex:W1|W2`` list call (1 credit)."""
        if not ids:
            return {}
        params = {
            "filter": "openalex:" + "|".join(ids),
            "per-page": min(per_page, MAX_PER_PAGE),
            "select": BRIEF_FIELDS,
        }
        data = await self._get("works", params)
        results = data.get("results") if data else None
        if not isinstance(results, list):
            return {}
        return {short_id(w.get("id")): w for w in results if isinstance(w, dict)}

    async def _referenced_edges(self, record: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        refs = [short_id(r) for r in record.get("referenced_works") or [] if r]
        refs = list(dict.fromkeys(refs))[:limit]
        briefs = await self._brief_works(refs, limit)
        return [
            {
                "relation_label": "cites",
                "related_id": ref,
                "related_name": (briefs.get(ref) or {}).get("display_name") or ref,
                "source": "OPENALEX",
                "year": (briefs.get(ref) or {}).get("publication_year"),
            }
            for ref in refs
        ]

    async def _citing_edges(self, work_id: str, limit: int) -> list[dict[str, Any]]:
        params = {
            "filter": f"cites:{work_id}",
            "sort": "cited_by_count:desc",
            "per-page": limit,
            "select": BRIEF_FIELDS,
        }
        data = await self._get("works", params)
        if not data or not isinstance(data.get("results"), list):
            return []
        total = (data.get("meta") or {}).get("count")
        edges = []
        for work in data["results"]:
            wid = short_id(work.get("id"))
            if wid:
                edges.append(
                    {
                        "relation_label": "cited_by",
                        "related_id": wid,
                        "related_name": work.get("display_name") or wid,
                        "source": "OPENALEX",
                        "year": work.get("publication_year"),
                        "cited_by_count": work.get("cited_by_count"),
                        "total_citing": total,
                    }
                )
        return edges

    async def _topic_relationships(self, topic_id: str, limit: int) -> list[dict[str, Any]]:
        record = await self._get(f"topics/{topic_id}", {"select": TOPIC_FIELDS})
        if not record:
            return []
        edges = []
        for level in ("subfield", "field", "domain"):
            node = record.get(level) or {}
            if node.get("id"):
                edges.append(
                    {
                        "relation_label": "part_of",
                        "related_id": f"{level}:{short_id(node['id'])}",
                        "related_name": node.get("display_name") or short_id(node["id"]),
                        "source": "OPENALEX",
                        "level": level,
                    }
                )
        for sibling in (record.get("siblings") or [])[:limit]:
            sid = short_id(sibling.get("id"))
            if sid:
                edges.append(
                    {
                        "relation_label": "sibling_topic",
                        "related_id": sid,
                        "related_name": sibling.get("display_name") or sid,
                        "source": "OPENALEX",
                    }
                )
        return edges

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_text(filters: dict[str, Any] | None) -> str:
        """Build the ``filter`` parameter; values with unexpected characters are dropped."""
        clauses = []
        for key, value in (filters or {}).items():
            name = FILTER_ALIASES.get(str(key).lower(), str(key))
            if not re.fullmatch(r"[a-z_.]+", name) or value in (None, "", []):
                continue
            values = [value] if not isinstance(value, list | tuple) else list(value)
            texts = [str(v).lower() if isinstance(v, bool) else str(v) for v in values]
            if not all(_FILTER_VALUE_RE.match(t) and "," not in t for t in texts):
                continue
            clauses.append(f"{name}:{'|'.join(texts)}")
        return ",".join(clauses)

    @staticmethod
    def _convert_list(
        data: dict[str, Any] | None, convert: Any, limit: int
    ) -> list[UnifiedConcept]:
        results = data.get("results") if data else None
        if not isinstance(results, list):
            return []
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for item in results:
            concept = convert(item) if isinstance(item, dict) else None
            if concept is not None and concept.primary_id not in seen:
                seen.add(concept.primary_id)
                concepts.append(concept)
        return concepts[:limit]

    def _work_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert an OpenAlex work record to a ``UnifiedConcept`` (type CITATION)."""
        try:
            work_id = short_id(item.get("id"))
            title = (item.get("display_name") or item.get("title") or "").strip()
            if not work_id or not title:
                return None
            concept = self._create_concept(work_id, title, ConceptType.CITATION)
            ids = item.get("ids") or {}
            doi = self._clean_external("doi", item.get("doi") or ids.get("doi") or "")
            pmid = self._clean_external("pmid", ids.get("pmid") or "")
            pmcid = self._clean_external("pmcid", ids.get("pmcid") or "")
            mag = ids.get("mag")
            year = item.get("publication_year")
            source = ((item.get("primary_location") or {}).get("source") or {}).get("display_name")
            oa = item.get("open_access") or {}
            topics = [
                {
                    "id": short_id(t.get("id")),
                    "name": t.get("display_name"),
                    "score": t.get("score"),
                    "subfield": (t.get("subfield") or {}).get("display_name"),
                    "field": (t.get("field") or {}).get("display_name"),
                    "domain": (t.get("domain") or {}).get("display_name"),
                }
                for t in item.get("topics") or []
                if isinstance(t, dict)
            ]
            keywords = [k.get("display_name") for k in item.get("keywords") or [] if k]
            concepts_scored = [
                {
                    "id": short_id(c.get("id")),
                    "name": c.get("display_name"),
                    "score": c.get("score"),
                    "wikidata": c.get("wikidata"),
                }
                for c in item.get("concepts") or []
                if isinstance(c, dict)
            ]
            abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
            if abstract and concept.definitions is not None:
                concept.definitions.append(abstract)
            if concept.semantic_types is not None and item.get("type"):
                concept.semantic_types.append(str(item["type"]))
            if concept.categories is not None:
                if year:
                    concept.categories.append(f"year:{year}")
                if source:
                    concept.categories.append(f"journal:{source}")
                if oa.get("oa_status"):
                    concept.categories.append(f"oa:{oa['oa_status']}")
                concept.categories.extend(f"topic:{t['name']}" for t in topics if t["name"])
            if concept.synonyms is not None:
                concept.synonyms.extend(k for k in keywords if k)
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
                concept.add_identifier(KnowledgeSource.EUROPEPMC, pmcid, title)
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OPENALEX] = {
                    "id": work_id,
                    "doi": doi or None,
                    "pmid": pmid or None,
                    "pmcid": pmcid or None,
                    "mag": mag,
                    "year": year,
                    "publication_date": item.get("publication_date"),
                    "type": item.get("type"),
                    "language": item.get("language"),
                    "journal": source,
                    "authors": [
                        {
                            "name": (a.get("author") or {}).get("display_name"),
                            "orcid": (a.get("author") or {}).get("orcid"),
                        }
                        for a in (item.get("authorships") or [])[:10]
                        if isinstance(a, dict)
                    ],
                    "cited_by_count": item.get("cited_by_count"),
                    "referenced_works_count": item.get("referenced_works_count"),
                    "fwci": item.get("fwci"),
                    "is_retracted": item.get("is_retracted"),
                    "open_access": {
                        "is_oa": oa.get("is_oa"),
                        "status": oa.get("oa_status"),
                        "url": oa.get("oa_url"),
                    },
                    "topics": topics,
                    "keywords": keywords,
                    "concepts": concepts_scored,
                    "abstract": abstract or None,
                    "relevance_score": item.get("relevance_score"),
                    "url": f"https://openalex.org/{work_id}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting OpenAlex work: {e}")
            return None

    def _topic_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert an OpenAlex topic record (type UNKNOWN; there is no research-topic type)."""
        try:
            topic_id = short_id(item.get("id"))
            name = (item.get("display_name") or "").strip()
            if not topic_id or not name:
                return None
            concept = self._create_concept(topic_id, name, ConceptType.UNKNOWN)
            if concept.definitions is not None and item.get("description"):
                concept.definitions.append(str(item["description"]))
            if concept.synonyms is not None:
                kws = item.get("keywords") or []
                concept.synonyms.extend(
                    str(k.get("display_name") if isinstance(k, dict) else k) for k in kws if k
                )
            hierarchy = {
                level: (item.get(level) or {}).get("display_name")
                for level in ("subfield", "field", "domain")
            }
            if concept.categories is not None:
                concept.categories.extend(f"{k}:{v}" for k, v in hierarchy.items() if v)
            concept.confidence_score = 0.8
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.OPENALEX] = {
                    "id": topic_id,
                    **hierarchy,
                    "works_count": item.get("works_count"),
                    "wikipedia": (item.get("ids") or {}).get("wikipedia"),
                    "url": f"https://openalex.org/topics/{topic_id}",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting OpenAlex topic: {e}")
            return None
