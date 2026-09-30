"""
Ensembl Genome Database Adapter

Integrates with the Ensembl REST API (https://rest.ensembl.org) for gene and
genomic feature lookup. Endpoints used (see https://rest.ensembl.org/ for the
full catalog):

- ``lookup/symbol/:species/:symbol`` and ``xrefs/symbol/:species/:symbol``
  ("Lookup" / "Cross References") for :meth:`search_concepts`.
- ``lookup/id/:id`` ("Lookup") for :meth:`get_concept_details`.
- ``homology/id/:species/:id`` ("Comparative Genomics") for
  :meth:`get_relationships` (orthologous genes).
- ``xrefs/id/:id`` ("Cross References") for :meth:`get_mappings`
  (cross-database identifiers).
"""

import asyncio
import logging
from typing import Any

import aiohttp

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)

# Ensembl's REST service has been observed taking well over the shared
# default per-request timeout (``LookupConfig.timeout_per_source``, 30s) to
# answer even successful requests under load. Without a longer budget here, a
# legitimately slow-but-succeeding response is cut off by aiohttp and then
# retried by the shared retry logic, compounding the delay instead of helping.
_MIN_TIMEOUT_SECONDS = 60.0


class EnsemblAdapter(KnowledgeSourceAdapter):
    """Adapter for Ensembl."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.ensembl.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ENSEMBL

    def is_available(self) -> bool:
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """Like the base implementation, but with a longer floor on the
        per-request timeout (see ``_MIN_TIMEOUT_SECONDS``)."""
        if self.session is None or self.session.closed:
            configured = self.config.timeout_per_source or 0.0
            timeout = aiohttp.ClientTimeout(total=max(configured, _MIN_TIMEOUT_SECONDS))
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Ensembl for genes.

        Ensembl has no free-text "search all" endpoint. This tries
        ``lookup/symbol`` first: a single round trip that resolves an exact
        canonical gene symbol (e.g. ``BRCA1``) directly to its record. Only
        when that doesn't match (a synonym, display name, or other external
        cross-reference rather than the canonical symbol) does it fall back
        to ``xrefs/symbol`` + ``lookup/id`` for the broader synonym-aware
        lookup, expanding any resulting hits concurrently rather than
        one-by-one: Ensembl's REST service can take several seconds per
        request under load, and a symbol can resolve to more than one object
        (e.g. a gene plus an LRG record), so running them sequentially
        multiplies that latency.
        """
        try:
            exact = await self._lookup_by_symbol(query)
            if exact is not None:
                logger.info(f"Ensembl search for '{query}' returned 1 concept (exact symbol)")
                return [exact]

            # Fallback: xrefs/symbol resolves synonyms/display names to one or
            # more Ensembl objects, each expanded via lookup/id.
            url = f"{self.base_url}/xrefs/symbol/homo_sapiens/{query}"
            params = {"content-type": "application/json"}

            data = await self._make_request(url, params)

            concepts: list[UnifiedConcept] = []
            if isinstance(data, list) and data:
                ids = [result.get("id", "") for result in data[:limit] if result.get("id")]
                details = await asyncio.gather(
                    *(self.get_concept_details(gene_id) for gene_id in ids),
                    return_exceptions=True,
                )
                for detail in details:
                    if isinstance(detail, BaseException):
                        logger.warning(f"Ensembl detail lookup failed during search: {detail}")
                    elif detail:
                        concepts.append(detail)

            logger.info(f"Ensembl search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Ensembl search failed for '{query}': {e}")
            return []

    async def _lookup_by_symbol(self, symbol: str) -> UnifiedConcept | None:
        """Exact-match gene symbol lookup via ``lookup/symbol`` — one fast
        round trip covering the common case of searching by a canonical gene
        symbol. Returns ``None`` for anything that isn't an exact match
        (including synonyms) or on any request failure, so callers fall back
        to ``xrefs/symbol``."""
        try:
            url = f"{self.base_url}/lookup/symbol/homo_sapiens/{symbol}"
            params = {"content-type": "application/json", "expand": 1}
            data = await self._make_request(url, params)
            if data and "id" in data:
                return self._convert_ensembl_result_to_concept(data)
            return None
        except Exception:
            return None

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed gene information from Ensembl."""
        try:
            # concept_id should be Ensembl ID (e.g., ENSG00000139618)
            url = f"{self.base_url}/lookup/id/{concept_id}"
            params = {"content-type": "application/json", "expand": 1}

            data = await self._make_request(url, params)

            if data and "id" in data:
                concept = self._convert_ensembl_result_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Ensembl concept details for '{concept_id}': {e}")
            return None

    async def get_relationships(self, concept_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return orthologous genes as edges, via the ``homology/id`` endpoint.

        ``concept_id`` must be an Ensembl gene ID (e.g. ``ENSG00000012048``).
        Returns the same ``{relation_label, related_id, related_name, source}``
        shape as the KEGG/STRING/WikiPathways adapters so the shared
        relationship-expansion source can consume it; degrades to ``[]`` on
        any failure. Ensembl's homology records name the target only by its
        own stable ID (no gene symbol), so ``related_name`` falls back to
        that ID.
        """
        gene_id = concept_id.strip()
        if not gene_id:
            return []
        try:
            url = f"{self.base_url}/homology/id/homo_sapiens/{gene_id}"
            params = {"content-type": "application/json", "type": "orthologues"}
            data = await self._make_request(url, params)

            entries = data.get("data") if isinstance(data, dict) else None
            if not entries:
                return []
            homologies = entries[0].get("homologies") or []

            relationships: list[dict[str, Any]] = []
            for homology in homologies[:limit]:
                target = homology.get("target") or {}
                related_id = (target.get("id") or "").strip()
                if not related_id:
                    continue
                relationships.append(
                    {
                        "relation_label": "ortholog",
                        "related_id": related_id,
                        "related_name": related_id,
                        "source": "Ensembl",
                        "species": target.get("species"),
                        "homology_type": homology.get("type"),
                    }
                )
            return relationships
        except Exception as e:
            logger.warning(f"Ensembl get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Return cross-database references for an Ensembl ID via ``xrefs/id``.

        Uses the same ``{fromId, toId, fromSource, toSource, mappingType,
        confidence}`` shape as :meth:`KEGGAdapter.get_mappings`. Degrades to
        ``[]`` on any failure.
        """
        gene_id = concept_id.strip()
        if not gene_id:
            return []
        try:
            url = f"{self.base_url}/xrefs/id/{gene_id}"
            params = {"content-type": "application/json"}
            data = await self._make_request(url, params)
            if not isinstance(data, list):
                return []

            mappings: list[dict[str, Any]] = []
            for xref in data:
                db_name = xref.get("dbname", "")
                primary_id = xref.get("primary_id", "")
                if not db_name or not primary_id:
                    continue
                mappings.append(
                    {
                        "fromId": gene_id,
                        "toId": primary_id,
                        "fromSource": "Ensembl",
                        "toSource": db_name,
                        "mappingType": "xref",
                        "confidence": 0.9,
                    }
                )
            return mappings
        except Exception as e:
            logger.warning(f"Ensembl get_mappings failed for '{concept_id}': {e}")
            return []

    def _convert_ensembl_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Ensembl API result to unified concept."""
        try:
            ensembl_id = result.get("id", "")
            label = result.get("display_name", ensembl_id)

            concept = UnifiedConcept(
                primary_id=ensembl_id, primary_label=label, concept_type=ConceptType.GENE
            )

            concept.add_identifier(
                KnowledgeSource.ENSEMBL,
                ensembl_id,
                label,
                f"https://www.ensembl.org/id/{ensembl_id}",
            )

            if "description" in result:
                if concept.definitions is not None:
                    concept.definitions.append(result["description"])

            if "biotype" in result:
                if concept.categories is not None:
                    concept.categories.append(f"Biotype: {result['biotype']}")

            if "species" in result:
                if concept.categories is not None:
                    concept.categories.append(f"Species: {result['species']}")

            concept.confidence_score = 1.0
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.ENSEMBL] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Ensembl result: {e}")
            return None
