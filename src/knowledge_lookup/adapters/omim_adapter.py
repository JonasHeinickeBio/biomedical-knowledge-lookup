"""
OMIM Knowledge Source Adapter

Adapter for querying OMIM (Online Mendelian Inheritance in Man), a comprehensive
catalog of human genes and genetic disorders.

API documentation: https://www.omim.org/help/api
"""

import logging
import os
from typing import Any, Optional

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class OMIMAdapter(KnowledgeSourceAdapter):
    """Adapter for OMIM (Online Mendelian Inheritance in Man) database."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://api.omim.org/api"
        self.api_key = config.get_api_key("omim") or os.getenv("OMIM_API_KEY")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OMIM

    def is_available(self) -> bool:
        return self.api_key is not None

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search OMIM for genes and genetic disorders."""
        if not self.api_key:
            logger.warning("OMIM API key not available")
            return []

        try:
            url = f"{self.base_url}/entry/search"
            params = {
                "search": query,
                "limit": min(limit, 20),
                "apiKey": self.api_key,
                "format": "json",
            }

            data = await self._make_request(url, params)
            concepts = []

            omim_list = data.get("omim", {}).get("searchResponse", {}).get("entryList", [])

            for item in omim_list[:limit]:
                concept = self._convert_result_to_concept(item.get("entry", item))
                if concept:
                    concepts.append(concept)

            logger.info(f"OMIM search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"OMIM search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed information about a specific OMIM entry."""
        if not self.api_key:
            logger.warning("OMIM API key not available")
            return None

        try:
            # Accept MIM numbers like "OMIM:143100" or "143100"
            mim_number = concept_id.replace("OMIM:", "").replace("MIM:", "").strip()

            url = f"{self.base_url}/entry"
            params = {
                "mimNumber": mim_number,
                "include": "all",
                "apiKey": self.api_key,
                "format": "json",
            }

            data = await self._make_request(url, params)
            entry_list = data.get("omim", {}).get("entryList", [])
            if not entry_list:
                return None

            return self._convert_result_to_concept(entry_list[0].get("entry", entry_list[0]))

        except Exception as e:
            logger.error(f"OMIM get_concept_details failed for '{concept_id}': {e}")
            return None

    def _convert_result_to_concept(self, item: dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert an OMIM entry to a UnifiedConcept."""
        try:
            mim_number = str(item.get("mimNumber", ""))
            titles = item.get("titles", {})
            preferred_title = titles.get("preferredTitle", "")

            if not mim_number or not preferred_title:
                return None

            concept_id = f"OMIM:{mim_number}"
            concept_type = self._determine_omim_type(item)

            concept = self._create_concept(concept_id, preferred_title, concept_type)

            # Alternative titles as synonyms
            for alt_title in titles.get("alternativeTitles", "").split(";;") + titles.get(
                "includedTitles", ""
            ).split(";;"):
                alt = alt_title.strip()
                if alt:
                    concept.synonyms.append(alt)

            # Gene symbols
            gene_map = item.get("geneMap", {})
            gene_symbols = gene_map.get("geneSymbols", "")
            if gene_symbols:
                concept.categories.append(f"gene_symbols:{gene_symbols}")

            concept.confidence_score = 0.9
            concept.source_data[KnowledgeSource.OMIM] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting OMIM result: {e}")
            return None

    def _determine_omim_type(self, item: dict[str, Any]) -> ConceptType:
        """Determine the concept type from OMIM entry type."""
        entry_type = item.get("type", "").lower()
        if entry_type in ("phenotype", "predominantly phenotypes"):
            return ConceptType.DISEASE
        if entry_type in ("gene", "gene/phenotype"):
            return ConceptType.GENE
        return ConceptType.DISEASE
