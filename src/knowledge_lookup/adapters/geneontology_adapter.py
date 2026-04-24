"""
Gene Ontology (GO) Adapter

Integrates with QuickGO API for biological process, molecular function, and cellular component lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class GeneOntologyAdapter(KnowledgeSourceAdapter):
    """Adapter for Gene Ontology."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/QuickGO/services/ontology/go"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.GENEONTOLOGY

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search GO for terms."""
        try:
            url = f"{self.base_url}/search"
            params = {"query": query, "limit": min(limit, 100)}

            data = await self._make_request(url, params)

            concepts = []
            if "results" in data:
                for result in data["results"]:
                    concept = self._convert_go_result_to_concept(result)
                    if concept:
                        concepts.append(concept)

            logger.info(f"GO search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"GO search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed GO term information."""
        try:
            # concept_id should be GO ID (e.g., GO:0008150)
            url = f"{self.base_url}/terms/{concept_id}"
            data = await self._make_request(url)

            if "results" in data and data["results"]:
                concept = self._convert_go_result_to_concept(data["results"][0])
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get GO concept details for '{concept_id}': {e}")
            return None

    def _convert_go_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert QuickGO result to unified concept."""
        try:
            go_id = result.get("id", "")
            label = result.get("name", "")

            if not go_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=go_id,
                primary_label=label,
                concept_type=ConceptType.GENE,  # GO is about gene functions/processes
            )

            concept.add_identifier(
                KnowledgeSource.GENEONTOLOGY,
                go_id,
                label,
                f"https://www.ebi.ac.uk/QuickGO/term/{go_id}",
            )

            if "synonyms" in result:
                for syn in result["synonyms"]:
                    concept.synonyms.append(syn.get("name", ""))

            if "definition" in result:
                concept.definitions.append(result["definition"].get("text", ""))

            # Aspect (BP, MF, CC)
            aspect = result.get("aspect", "")
            if aspect:
                concept.categories.append(f"Aspect: {aspect}")

            concept.confidence_score = 0.95
            concept.source_data[KnowledgeSource.GENEONTOLOGY] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting GO result: {e}")
            return None
