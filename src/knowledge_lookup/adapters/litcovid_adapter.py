"""
LitCovid Knowledge Source Adapter

NCBI LitCovid (Chen, Allot & Lu) is a curated literature hub for COVID-19 / SARS-CoV-2 and,
via its ``LongCovid`` condition tag, for Long COVID. Every PubMed article matching the
coronavirus query is classified into eight topic categories (General Info, Mechanism,
Transmission, Diagnosis, Treatment, Prevention, Case Report, Epidemic Forecasting) and
tagged with a few named entities. Data is a US Government work with no use restrictions;
cite Chen et al., Nature 579:193 (2020) and Nucleic Acids Res. (2020) (this is the
request printed in the file header of the official ``export/tsv`` download).

API (verified live, keyless, JSON; the ``/research/coronavirus-api/`` root answers
``{"healthcheck": "OK"}``)::

    GET /research/coronavirus-api/search/?text=<query>&page=<n>&sort=date%20desc

Quirks worth knowing (they differ from what the page name suggests):

* The query parameter is ``text``. ``query=``, ``q=``, ``page_size=``, ``limit=``, ``size=``
  and ``fq=`` are **silently ignored**: ``query=long covid`` returns all ~490k LitCovid
  articles. The page size is fixed at 10; ask for ``page=2``, ``3``... for more.
* ``text`` takes a Lucene-like syntax: quoted phrases, ``AND``/``OR``, parentheses and
  ``field:value`` terms (``topics:Diagnosis``, ``e_condition:LongCovid``,
  ``countries:Germany``, ``journal:"Sci Rep"``, ``pmid:34316076``, ``pmcid:PMC9878254``).
  An unquoted ``long covid`` means ``long OR covid`` (428k hits); ``"long covid"`` is a
  phrase (8k hits). Wildcards (``e_drugs:*``) do not work. Invalid syntax yields an empty
  result (or HTTP 500 for the unrelated ``filters=`` parameter), never a parse error.
* Per-article entity annotations are only partially exposed: ``e_condition``, ``e_variants``,
  ``e_vaccines`` and ``e_strains`` are on each result, ``e_drugs`` is **only** available in the
  ``facets`` block of the response (so it is read from a one-article ``pmid:`` query, which is
  what :meth:`get_concept_details` does). There are no gene or disease entities.
* ``export/tsv`` ignores ``limit`` and returns the whole result set with only
  pmid/title/journal columns (1 MB for 8k hits), so it is not used.
* No abstracts are returned. The search is relevance ranked; ``sort=date desc`` is honoured.
* Latency 0.4-3 s, occasionally 10+ s for the very large topic queries; a 60 s timeout floor is
  set. No rate limit is documented; the adapter stays well below 2 requests per second.
"""

import asyncio
import logging
import re
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ncbi.nlm.nih.gov/research/coronavirus-api"
SEARCH_URL = f"{BASE_URL}/search/"
PAGE_SIZE = 10  # fixed by the server; ``page_size`` is ignored
MAX_RESULTS = 100  # cap for one search_articles() call (10 requests)
PAGE_PAUSE = 0.35  # seconds between consecutive requests of one call (<= 3 req/s)

#: The eight LitCovid topic categories as they appear in ``topics`` / ``topics:<name>``.
TOPICS: tuple[str, ...] = (
    "Case Report",
    "Diagnosis",
    "Epidemic Forecasting",
    "General Info",
    "Mechanism",
    "Prevention",
    "Transmission",
    "Treatment",
)
TOPICS_CANON = {t.lower(): t for t in TOPICS}  # for the ``topic`` filter
_TOPIC_BY_KEY = {re.sub(r"[\s_-]+", "", t).lower(): t for t in TOPICS}

TOPIC_PREFIX = "LITCOVID:TOPIC:"
_PMID_RE = re.compile(r"^(?:LITCOVID:)?(?:PMID:?)?\s*(\d{1,9})$", re.IGNORECASE)
_PMCID_RE = re.compile(r"^(?:PMCID:)?(PMC\d+)$", re.IGNORECASE)

#: ``filters`` keys accepted by :meth:`search_articles` -> LitCovid field name.
FILTER_FIELDS: dict[str, str] = {
    "topic": "topics",
    "topics": "topics",
    "journal": "journal",
    "country": "countries",
    "countries": "countries",
    "condition": "e_condition",
    "drug": "e_drugs",
    "variant": "e_variants",
    "vaccine": "e_vaccines",
    "strain": "e_strains",
}
#: result field -> (relation label, related-id prefix, entity kind)
ENTITY_FIELDS: dict[str, tuple[str, str, str]] = {
    "e_condition": ("annotated_with_condition", "LITCOVID:CONDITION:", "condition"),
    "e_drugs": ("mentions_drug", "LITCOVID:DRUG:", "drug"),
    "e_variants": ("mentions_variant", "LITCOVID:VARIANT:", "variant"),
    "e_vaccines": ("mentions_vaccine", "LITCOVID:VACCINE:", "vaccine"),
    "e_strains": ("mentions_strain", "LITCOVID:STRAIN:", "strain"),
}
_ENTITY_CAP = 50  # some variant lists run to hundreds of rs/p. identifiers


def _quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


class LitCovidAdapter(KnowledgeSourceAdapter):
    """Adapter for NCBI LitCovid (COVID-19 / Long COVID literature, keyless)."""

    #: topic queries are occasionally slow (13 s seen); do not cut them off and retry.
    min_request_timeout = 60.0

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.LITCOVID

    def is_available(self) -> bool:
        return True  # public, keyless API

    # ------------------------------------------------------------------
    # Identifier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_pmid(concept_id: str) -> str | None:
        """``PMID:34316076`` / ``34316076`` / ``LITCOVID:PMID:34316076`` -> ``"34316076"``."""
        match = _PMID_RE.match((concept_id or "").strip())
        return match.group(1) if match else None

    @staticmethod
    def normalize_topic(concept_id: str) -> str | None:
        """``LITCOVID:TOPIC:Case Report`` / ``case_report`` / ``Treatment`` -> canonical name."""
        text = (concept_id or "").strip()
        if text.upper().startswith(TOPIC_PREFIX):
            text = text[len(TOPIC_PREFIX) :]
        elif text.upper().startswith("TOPIC:"):
            text = text[len("TOPIC:") :]
        return _TOPIC_BY_KEY.get(re.sub(r"[\s_-]+", "", text).lower())

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------

    @staticmethod
    def build_query(query: str, filters: dict[str, Any] | None = None) -> str:
        """Turn free text plus ``filters`` into LitCovid's ``text`` syntax.

        Plain multi-word text is sent as an exact phrase, because the server otherwise
        ORs the words (``long covid`` matches every COVID paper). Text that already uses
        quotes, ``AND``/``OR``/``NOT``, parentheses or ``field:value`` is passed through.
        Filter values may be a string or a list (OR-ed); keys are listed in
        :data:`FILTER_FIELDS`, anything else is ignored.
        """
        text = (query or "").strip()
        if text and not re.search(r'["():]|\b(?:AND|OR|NOT)\b', text):
            text = _quote(text) if " " in text else text
        parts = [text] if text else []
        for key, value in (filters or {}).items():
            field = FILTER_FIELDS.get(str(key).lower())
            if field is None or value in (None, "", []):
                continue
            values = [value] if isinstance(value, str) else list(value)
            if field == "topics":
                values = [TOPICS_CANON.get(str(v).lower(), str(v)) for v in values]
            clause = " OR ".join(f"{field}:{_quote(str(v))}" for v in values)
            parts.append(f"({clause})" if len(values) > 1 else clause)
        return " AND ".join(parts)

    async def _fetch_page(
        self, text: str, page: int = 1, sort: str | None = None
    ) -> dict[str, Any] | None:
        """One page of ``/search/``; ``None`` on failure or an unexpected payload."""
        params: dict[str, Any] = {"text": text}
        if page > 1:
            params["page"] = page
        if sort == "date":
            params["sort"] = "date desc"
        try:
            data = await self._make_request(SEARCH_URL, params=params)
        except Exception as e:
            logger.warning(f"LitCovid request failed for '{text}': {e}")
            return None
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return None
        return data

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search_articles(
        self,
        query: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
    ) -> list[UnifiedConcept]:
        """Free-text article search (paged 10 at a time, at most 100 results).

        ``filters`` accepts ``topic``, ``journal``, ``country``, ``condition`` (e.g.
        ``"LongCovid"``), ``drug``, ``variant``, ``vaccine`` and ``strain``. ``sort="date"``
        returns the newest first; the default is server relevance order.
        """
        try:
            limit = max(0, min(int(limit), MAX_RESULTS))
            text = self.build_query(query, filters)
            if not text or limit == 0:
                return []
            concepts: list[UnifiedConcept] = []
            seen: set[str] = set()
            page = 1
            while len(concepts) < limit:
                if page > 1:
                    await asyncio.sleep(PAGE_PAUSE)
                data = await self._fetch_page(text, page, sort)
                if data is None or not data["results"]:
                    break
                added = 0
                for item in data["results"]:
                    concept = self._article_to_concept(item)
                    if concept is not None and concept.primary_id not in seen:
                        seen.add(concept.primary_id)
                        concepts.append(concept)
                        added += 1
                total_pages = data.get("total_pages")
                # also stop on a page without new articles (guards against a server that
                # ignores ``page`` and would otherwise keep returning the same ten records)
                if not added or (isinstance(total_pages, int) and page >= total_pages):
                    break
                page += 1
            logger.info(f"LitCovid search for '{text}' returned {len(concepts[:limit])} articles")
            return concepts[:limit]
        except Exception as e:
            logger.error(f"LitCovid search failed for '{query}': {e}")
            return []

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search articles (and the eight topic categories by name) for ``query``.

        A bare PMID / ``PMID:n`` query resolves to that one article. When a multi-word
        phrase finds nothing, the words are retried joined with AND.
        """
        try:
            query = (query or "").strip()
            if not query or limit <= 0:
                return []
            if self.normalize_pmid(query):
                concept = await self.get_concept_details(query)
                return [concept] if concept else []
            topics = [self._topic_concept(t) for t in TOPICS if query.lower() in t.lower()]
            articles = await self.search_articles(query, limit)
            if not articles and " " in query and not re.search(r'["():]', query):
                relaxed = " AND ".join(query.split())
                articles = await self.search_articles(relaxed, limit)
            return (articles + topics)[:limit]
        except Exception as e:
            logger.error(f"LitCovid search_concepts failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Article by PMID (``PMID:34316076``, bare digits or PMCID) or a topic category.

        The article lookup is ``text=pmid:<n>``; the response's facet block is used to
        recover the ``e_drugs`` entities that the result record itself does not carry.
        """
        try:
            topic = (
                self.normalize_topic(concept_id) if not self.normalize_pmid(concept_id) else None
            )
            if topic:
                counts = await self.get_topic_counts(topic=topic)
                return self._topic_concept(topic, counts.get(topic))
            record, facets = await self._fetch_article(concept_id)
            if record is None:
                return None
            return self._article_to_concept(record, facets)
        except Exception as e:
            logger.error(f"LitCovid get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Article -> topics (``has_topic``) and annotated entities; topic -> recent articles.

        Article edges: ``has_topic`` (to ``LITCOVID:TOPIC:<name>``),
        ``annotated_with_condition`` (the ``LongCovid`` tag), ``mentions_drug``,
        ``mentions_variant``, ``mentions_vaccine`` and ``mentions_strain`` (each capped at
        50; variants may be rs numbers or HGVS protein changes). Topic edges: up to ten
        newest ``has_article`` edges (use :meth:`search_articles` for more).
        """
        try:
            topic = (
                self.normalize_topic(concept_id) if not self.normalize_pmid(concept_id) else None
            )
            if topic:
                articles = await self.search_articles("", 10, {"topic": topic}, sort="date")
                return [
                    {
                        "relation_label": "has_article",
                        "related_id": a.primary_id,
                        "related_name": a.primary_label,
                        "source": "LITCOVID",
                    }
                    for a in articles
                ]
            record, facets = await self._fetch_article(concept_id)
            if record is None:
                return []
            return self._article_relationships(record, facets)
        except Exception as e:
            logger.warning(f"LitCovid get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Article PMID -> PubMed record and (when present) PMC identifier."""
        try:
            pmid = self.normalize_pmid(concept_id)
            if not pmid:
                return []
            record, _ = await self._fetch_article(pmid)
            if record is None:
                return []
            from_id = f"PMID:{pmid}"
            mappings = [self._mapping(from_id, "PubMed", pmid, "exact", 1.0)]
            pmcid = record.get("pmcid")
            if pmcid:
                mappings.append(self._mapping(from_id, "PMC", str(pmcid), "exact", 1.0))
            return mappings
        except Exception as e:
            logger.warning(f"LitCovid get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_topic_counts(
        self, query: str | None = None, topic: str | None = None
    ) -> dict[str, int]:
        """Number of LitCovid articles per topic category (one request per topic).

        Pass ``query`` to count only articles matching it (e.g. ``"long covid"``), or
        ``topic`` to look up a single category. Topics whose request failed are omitted.
        The unfiltered totals overlap: an article may carry several topics.
        """
        names = [topic] if topic else list(TOPICS)
        semaphore = asyncio.Semaphore(2)

        async def one(name: str) -> tuple[str, int | None]:
            async with semaphore:
                await asyncio.sleep(PAGE_PAUSE)
                data = await self._fetch_page(self.build_query(query or "", {"topic": name}))
            count = data.get("count") if data else None
            return name, count if isinstance(count, int) else None

        try:
            pairs = await asyncio.gather(*(one(n) for n in names))
        except Exception as e:  # pragma: no cover - gather of non-raising coroutines
            logger.error(f"LitCovid get_topic_counts failed: {e}")
            return {}
        return {name: count for name, count in pairs if count is not None}

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    async def _fetch_article(
        self, concept_id: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Return ``(record, facet_fields)`` for a PMID or PMCID, ``(None, {})`` if absent."""
        text_id = (concept_id or "").strip()
        pmid = self.normalize_pmid(text_id)
        pmcid = _PMCID_RE.match(text_id)
        if pmid:
            text = f"pmid:{pmid}"
        elif pmcid:
            text = f"pmcid:{pmcid.group(1).upper()}"
        else:
            return None, {}
        data = await self._fetch_page(text)
        if data is None or not data["results"]:
            return None, {}
        facets = data.get("facets")
        fields = facets.get("facet_fields") if isinstance(facets, dict) else None
        return data["results"][0], fields if isinstance(fields, dict) else {}

    @staticmethod
    def _mapping(from_id: str, to_source: str, to_id: str, kind: str, conf: float) -> dict:
        return {
            "fromId": from_id,
            "toId": to_id,
            "fromSource": "LITCOVID",
            "toSource": to_source,
            "mappingType": kind,
            "confidence": conf,
        }

    @staticmethod
    def _year(item: dict[str, Any]) -> str:
        for key in ("meta_date_publication", "date"):
            match = re.match(r"\s*(\d{4})", str(item.get(key) or ""))
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _entities(item: dict[str, Any], facets: dict[str, Any] | None) -> dict[str, list[str]]:
        """Entity annotations by kind; ``e_drugs`` comes from the facet block."""
        entities: dict[str, list[str]] = {}
        for field, (_, _, kind) in ENTITY_FIELDS.items():
            values = item.get(field)
            if values is None and facets and field == "e_drugs":
                values = [
                    f.get("name")
                    for f in facets.get(field, [])
                    if isinstance(f, dict) and f.get("name")
                ]
            if isinstance(values, list):
                unique = list(dict.fromkeys(str(v) for v in values if v))
                if unique:
                    entities[kind] = unique
        return entities

    def _article_to_concept(
        self, item: dict[str, Any], facets: dict[str, Any] | None = None
    ) -> UnifiedConcept | None:
        """Convert one LitCovid result record to a ``UnifiedConcept`` (type CITATION)."""
        try:
            pmid = item.get("pmid") or item.get("_id")
            title = (item.get("title") or "").strip()
            if not pmid or not title:
                return None
            pmid = str(pmid)
            concept = self._create_concept(f"PMID:{pmid}", title, ConceptType.CITATION)
            journal = item.get("journal") or ""
            year = self._year(item)
            topics = [t for t in item.get("topics") or [] if t]
            countries = [c for c in item.get("countries") or [] if c]
            entities = self._entities(item, facets)
            if concept.categories is not None:
                if journal:
                    concept.categories.append(f"journal:{journal}")
                if year:
                    concept.categories.append(f"year:{year}")
                concept.categories.extend(f"topic:{t}" for t in topics)
                concept.categories.extend(f"country:{c}" for c in countries)
                if "LongCovid" in entities.get("condition", []):
                    concept.categories.append("condition:LongCovid")
            pmcid = item.get("pmcid")
            if pmcid:
                concept.add_identifier(
                    KnowledgeSource.EUROPEPMC,
                    str(pmcid),
                    title,
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
                )
            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.LITCOVID] = {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "title": title,
                    "journal": journal,
                    "year": year,
                    "date_publication": item.get("meta_date_publication"),
                    "authors": item.get("authors") or [],
                    "volume": item.get("meta_volume"),
                    "issue": item.get("meta_issue"),
                    "pages": item.get("meta_pages"),
                    "topics": topics,
                    "countries": countries,
                    "entities": entities,
                    "citation": (item.get("citations") or {}).get("NLM"),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            return concept
        except Exception as e:
            logger.error(f"Error converting LitCovid result: {e}")
            return None

    def _topic_concept(self, topic: str, count: int | None = None) -> UnifiedConcept:
        concept = self._create_concept(f"{TOPIC_PREFIX}{topic}", topic, ConceptType.UNKNOWN)
        if concept.categories is not None:
            concept.categories.append("LitCovid topic")
        if concept.definitions is not None:
            concept.definitions.append(
                f"LitCovid article topic category '{topic}' (assigned by LitCovid's "
                "text-classification pipeline; the API publishes no definition text)."
            )
        concept.confidence_score = 0.8
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.LITCOVID] = {
                "topic": topic,
                "article_count": count,
            }
        return concept

    def _article_relationships(
        self, record: dict[str, Any], facets: dict[str, Any]
    ) -> list[dict[str, Any]]:
        relationships: list[dict[str, Any]] = []
        for topic in dict.fromkeys(t for t in record.get("topics") or [] if t):
            relationships.append(
                {
                    "relation_label": "has_topic",
                    "related_id": f"{TOPIC_PREFIX}{topic}",
                    "related_name": topic,
                    "source": "LITCOVID",
                }
            )
        entities = self._entities(record, facets)
        for _, (label, prefix, kind) in ENTITY_FIELDS.items():
            for name in entities.get(kind, [])[:_ENTITY_CAP]:
                relationships.append(
                    {
                        "relation_label": label,
                        "related_id": f"{prefix}{name}",
                        "related_name": name,
                        "source": "LITCOVID",
                        "entity_type": kind,
                    }
                )
        return relationships
