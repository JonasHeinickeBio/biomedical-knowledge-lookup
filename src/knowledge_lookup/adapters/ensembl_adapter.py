"""
Ensembl Genome Database Adapter

Integrates with the Ensembl REST API (https://rest.ensembl.org) for gene and
genomic feature lookup. Endpoints used: ``xrefs/symbol/:species/:symbol`` and
``lookup/id/:id`` (see the "Cross References" and "Lookup" sections of
https://rest.ensembl.org/).
"""

import asyncio
import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class EnsemblAdapter(KnowledgeSourceAdapter):
    """Adapter for Ensembl."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://rest.ensembl.org"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ENSEMBL

    def is_available(self) -> bool:
        return True

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
