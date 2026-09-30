"""
WikiPathways Knowledge Source Adapter

Integrates with the WikiPathways JSON API (https://www.wikipathways.org/json/)
for community-curated biological pathways.

WikiPathways retired its per-query REST webservice (``webservice.wikipathways.org``)
in favour of a small set of bulk JSON files covering *every* pathway at once
(https://www.wikipathways.org/json/index.html) — there is no live "search" or
"get one pathway" endpoint any more. This adapter downloads the relevant bulk
file on first use, indexes it in memory, and serves every subsequent call from
that index; the parsed index is also written through the adapter cache so a
configured disk cache avoids re-downloading between CLI invocations.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

_WIKIPATHWAYS_JSON_BASE_URL = "https://www.wikipathways.org/json"

# How long a downloaded bulk file is kept before being re-fetched. The files
# are regenerated "in real time" on WikiPathways' side but change slowly
# enough that a long TTL is appropriate for a knowledge-lookup client.
_BULK_CACHE_TTL = 6 * 60 * 60  # 6 hours

# Bulk file name -> the fields (in priority order) searched by search_concepts.
_SEARCH_FIELDS: tuple[str, ...] = ("name", "annotations", "datanodes", "description")


class WikiPathwaysAdapter(KnowledgeSourceAdapter):
    """Adapter for the WikiPathways bulk JSON API."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = _WIKIPATHWAYS_JSON_BASE_URL
        # In-process indexes, keyed by bulk file name. Populated lazily so a
        # multi-source lookup that never touches WikiPathways never pays the
        # download cost.
        self._bulk: dict[str, list[dict[str, Any]]] = {}
        self._by_id: dict[str, dict[str, dict[str, Any]]] = {}

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.WIKIPATHWAYS

    def is_available(self) -> bool:
        return True  # WikiPathways is publicly available, no key required

    async def _load_bulk(self, name: str) -> list[dict[str, Any]]:
        """Return the parsed ``pathwayInfo`` list for bulk file *name*, downloading
        and caching it on first use (see module docstring)."""
        if name in self._bulk:
            return self._bulk[name]

        cache_key = self._get_cache_key("bulk", name)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            self._bulk[name] = cached
            return cached

        data = await self._make_request(f"{self.base_url}/{name}.json")
        items = data.get("pathwayInfo") if isinstance(data, dict) else None
        items = items if isinstance(items, list) else []
        self._set_in_cache(cache_key, items, ttl=_BULK_CACHE_TTL)
        self._bulk[name] = items
        return items

    async def _index_by_id(self, name: str) -> dict[str, dict[str, Any]]:
        """Return {pathway id -> entry} for bulk file *name*, built once per file."""
        if name in self._by_id:
            return self._by_id[name]
        items = await self._load_bulk(name)
        index = {item["id"]: item for item in items if item.get("id")}
        self._by_id[name] = index
        return index

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search WikiPathways for pathways matching *query*.

        WikiPathways no longer offers a server-side search endpoint, so this
        scans the ``findPathwaysByText`` bulk file client-side, matching
        *query* case-insensitively against the pathway name, annotations,
        participating gene/metabolite names ("datanodes") and description —
        in that priority order, which also determines the ranking.
        """
        try:
            items = await self._load_bulk("findPathwaysByText")
            needle = query.strip().lower()
            if not needle:
                return []

            scored: list[tuple[int, dict[str, Any]]] = []
            for item in items:
                for rank, field in enumerate(_SEARCH_FIELDS):
                    if needle in str(item.get(field, "")).lower():
                        scored.append((rank, item))
                        break

            scored.sort(key=lambda pair: pair[0])

            concepts: list[UnifiedConcept] = []
            for rank, item in scored[:limit]:
                concept = self._convert_entry_to_concept(item)
                if concept:
                    concept.confidence_score = 1.0 - (rank / len(_SEARCH_FIELDS)) * 0.4
                    concepts.append(concept)

            logger.info(f"WikiPathways search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"WikiPathways search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed pathway information from the ``getPathwayInfo`` bulk index."""
        try:
            pathway_id = _strip_prefix(concept_id)
            index = await self._index_by_id("getPathwayInfo")
            entry = index.get(pathway_id)
            if entry is None:
                return None

            concept = self._convert_entry_to_concept(entry)
            if concept is not None:
                concept.confidence_score = 1.0
            return concept

        except Exception as e:
            logger.error(f"WikiPathways get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return a pathway's participating genes as edges.

        Reads the ``hgnc`` field (``hgnc.symbol:<SYMBOL>, ...``) of the
        ``findPathwaysByXref`` bulk index for *concept_id*. Returns the same
        ``{relation_label, related_id, related_name, source}`` shape as the
        KEGG/STRING adapters so the shared relationship-expansion source can
        consume it; degrades to ``[]`` on any failure (including non-human
        pathways, which carry no HGNC symbols).
        """
        pathway_id = _strip_prefix(concept_id)
        if not pathway_id:
            return []
        try:
            index = await self._index_by_id("findPathwaysByXref")
            entry = index.get(pathway_id)
            if entry is None:
                return []

            symbols = _parse_xref_field(entry.get("hgnc", ""), prefix="hgnc.symbol:")
            relationships: list[dict[str, Any]] = []
            for symbol in symbols[:limit]:
                relationships.append(
                    {
                        "relation_label": "has_gene",
                        "related_id": symbol,
                        "related_name": symbol,
                        "source": "WIKIPATHWAYS_GENE",
                    }
                )
            return relationships
        except Exception as e:
            logger.warning(f"WikiPathways get_relationships failed for '{concept_id}': {e}")
            return []

    def _convert_entry_to_concept(self, entry: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a bulk-file pathway entry (any of the three files share this
        shape for id/url/name/species/description) to a UnifiedConcept."""
        try:
            wp_id = entry.get("id", "")
            label = entry.get("name", "")

            if not wp_id or not label:
                return None

            concept = self._create_concept(wp_id, label, ConceptType.PATHWAY)

            species = entry.get("species")
            if species and concept.categories is not None:
                concept.categories.append(species)

            url = entry.get("url") or f"https://www.wikipathways.org/instance/{wp_id}"
            concept.add_identifier(KnowledgeSource.WIKIPATHWAYS, wp_id, label, url)

            description = entry.get("description")
            if description and concept.definitions is not None:
                concept.definitions.append(description[:500])

            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.WIKIPATHWAYS] = entry

            return concept

        except Exception as e:
            logger.error(f"Error converting WikiPathways entry: {e}")
            return None


def _strip_prefix(concept_id: str) -> str:
    """Strip a leading ``WIKIPATHWAYS:`` prefix (if any) from *concept_id*."""
    return concept_id.replace("WIKIPATHWAYS:", "").strip()


def _parse_xref_field(raw: Any, prefix: str) -> list[str]:
    """Parse a comma-separated bulk xref field (e.g. ``"hgnc.symbol:A, hgnc.symbol:B"``,
    with a cell sometimes chaining several prefixed IDs as ``"hgnc.symbol:A;hgnc.symbol:B"``
    for one datanode) into a de-duplicated, order-preserving list of bare values."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    seen: set[str] = set()
    values: list[str] = []
    for token in raw.split(","):
        for sub in token.split(";"):
            sub = sub.strip()
            if sub.startswith(prefix):
                sub = sub[len(prefix) :]
            if sub and sub not in seen:
                seen.add(sub)
                values.append(sub)
    return values
