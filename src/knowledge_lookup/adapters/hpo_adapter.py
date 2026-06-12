"""
Human Phenotype Ontology (HPO) Adapter

Integrates with HPO for phenotype and clinical finding lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class HPOAdapter(KnowledgeSourceAdapter):
    """Adapter for Human Phenotype Ontology."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://hpo.jax.org/api/ontological"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.HPO

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search HPO for phenotypes."""
        try:
            url = f"{self.base_url}/search"
            params = {"q": query}

            data = await self._make_request(url, params)

            concepts = []
            if "terms" in data:
                for term in data["terms"][:limit]:
                    concept = self._convert_hpo_result_to_concept(term)
                    if concept:
                        concepts.append(concept)

            logger.info(f"HPO search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"HPO search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed phenotype information from HPO."""
        try:
            # concept_id should be HPO ID (e.g., HP:0000118)
            url = f"{self.base_url}/term/{concept_id}"
            data = await self._make_request(url)

            if "details" in data:
                concept = self._convert_hpo_details_to_concept(data["details"])
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get HPO concept details for '{concept_id}': {e}")
            return None

    def _convert_hpo_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert HPO API search result to unified concept."""
        try:
            hpo_id = result.get("id", "")
            label = result.get("name", "")

            if not hpo_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=hpo_id, primary_label=label, concept_type=ConceptType.PHENOTYPE
            )

            concept.add_identifier(
                KnowledgeSource.HPO, hpo_id, label, f"https://hpo.jax.org/app/browse/term/{hpo_id}"
            )

            if "synonyms" in result:
                concept.synonyms.extend(result["synonyms"])

            concept.confidence_score = 0.95
            concept.source_data[KnowledgeSource.HPO] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting HPO result: {e}")
            return None

    def _convert_hpo_details_to_concept(self, details: dict[str, Any]) -> UnifiedConcept | None:
        """Convert HPO API detailed concept to unified concept."""
        try:
            hpo_id = details.get("id", "")
            label = details.get("name", "")

            if not hpo_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=hpo_id, primary_label=label, concept_type=ConceptType.PHENOTYPE
            )

            concept.add_identifier(
                KnowledgeSource.HPO, hpo_id, label, f"https://hpo.jax.org/app/browse/term/{hpo_id}"
            )

            if "synonyms" in details:
                concept.synonyms.extend(details["synonyms"])

            if "definition" in details:
                concept.definitions.append(details["definition"])

            concept.confidence_score = 1.0
            concept.source_data[KnowledgeSource.HPO] = details

            return concept

        except Exception as e:
            logger.error(f"Error converting HPO details: {e}")
            return None
