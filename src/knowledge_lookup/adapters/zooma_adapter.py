"""
ZOOMA Annotation Service Adapter

Integrates with EBI ZOOMA for mapping text to ontology terms.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class ZoomaAdapter(KnowledgeSourceAdapter):
    """Adapter for EBI ZOOMA."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/spot/zooma/v2/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.ZOOMA

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search ZOOMA for annotations (mappings)."""
        try:
            url = f"{self.base_url}/services/annotate"
            params = {"propertyValue": query}

            data = await self._make_request(url, params)

            concepts: list[UnifiedConcept] = []
            if isinstance(data, list):
                for item in data[:limit]:
                    concept = self._convert_zooma_result_to_concept(item)
                    if concept:
                        concepts.append(concept)

            logger.info(f"ZOOMA search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"ZOOMA search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """ZOOMA is primarily for mapping, use OLS for details."""
        return None

    def _convert_zooma_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert ZOOMA result to unified concept."""
        try:
            semantic_tags = result.get("semanticTags", [])
            if not semantic_tags:
                return None

            # Use the first semantic tag as the ID
            tag_uri = semantic_tags[0]
            label = result.get("annotatedProperty", {}).get("propertyValue", "")

            concept = UnifiedConcept(
                primary_id=tag_uri, primary_label=label, concept_type=ConceptType.UNKNOWN
            )

            concept.add_identifier(KnowledgeSource.ZOOMA, tag_uri, label, tag_uri)

            # Confidence
            confidence = result.get("confidence", "LOW")
            score_map = {"HIGH": 0.9, "GOOD": 0.7, "MEDIUM": 0.5, "LOW": 0.3}
            concept.confidence_score = score_map.get(confidence, 0.3)

            # Source
            if "derivedFrom" in result:
                source = (
                    result["derivedFrom"].get("provenance", {}).get("source", {}).get("name", "")
                )
                if source and concept.categories is not None:
                    concept.categories.append(f"Source: {source}")

            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.ZOOMA] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting ZOOMA result: {e}")
            return None
