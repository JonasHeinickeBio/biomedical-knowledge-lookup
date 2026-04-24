"""
Reactome Pathway Database Adapter

Integrates with Reactome Analysis Service for biological pathway lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class ReactomeAdapter(KnowledgeSourceAdapter):
    """Adapter for Reactome."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://reactome.org/ContentService"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.REACTOME

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Reactome for pathways."""
        try:
            url = f"{self.base_url}/search/query"
            params = {"query": query, "rows": min(limit, 100)}

            data = await self._make_request(url, params)

            concepts = []
            if "results" in data:
                for result in data["results"]:
                    # Only include pathways and entries with relevant types
                    if result.get("type") in ["Pathway", "Reaction"]:
                        concept = self._convert_reactome_result_to_concept(result)
                        if concept:
                            concepts.append(concept)

            logger.info(f"Reactome search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Reactome search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed pathway information from Reactome."""
        try:
            # concept_id should be Reactome ID (e.g., R-HSA-1640170)
            url = f"{self.base_url}/data/query/{concept_id}"
            data = await self._make_request(url)

            if data and "dbId" in data:
                concept = self._convert_reactome_details_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Reactome concept details for '{concept_id}': {e}")
            return None

    def _convert_reactome_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Reactome search result to unified concept."""
        try:
            st_id = result.get("stId", "")
            label = result.get("name", "")

            if not st_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=st_id,
                primary_label=label,
                concept_type=ConceptType.UNKNOWN,  # Pathways are not exactly one of our ConceptTypes
            )

            concept.add_identifier(
                KnowledgeSource.REACTOME,
                st_id,
                label,
                f"https://reactome.org/content/detail/{st_id}",
            )

            if "summation" in result:
                concept.definitions.append(result["summation"])

            if "species" in result:
                concept.categories.extend(result["species"])

            concept.confidence_score = 0.9
            concept.source_data[KnowledgeSource.REACTOME] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Reactome result: {e}")
            return None

    def _convert_reactome_details_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Reactome detailed concept to unified concept."""
        try:
            st_id = data.get("stId", "")
            label = data.get("displayName", "")

            if not st_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=st_id, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            concept.add_identifier(
                KnowledgeSource.REACTOME,
                st_id,
                label,
                f"https://reactome.org/content/detail/{st_id}",
            )

            if "summation" in data and data["summation"]:
                concept.definitions.append(data["summation"][0].get("text", ""))

            concept.confidence_score = 1.0
            concept.source_data[KnowledgeSource.REACTOME] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting Reactome details: {e}")
            return None
