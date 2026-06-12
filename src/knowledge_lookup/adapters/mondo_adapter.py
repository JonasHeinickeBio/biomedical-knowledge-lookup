"""
Mondo Disease Ontology Adapter

Integrates with Mondo via OLS or direct API for disease lookup.
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class MondoAdapter(KnowledgeSourceAdapter):
    """Adapter for Mondo Disease Ontology."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        # We can use OLS API filtered for Mondo
        self.base_url = "https://www.ebi.ac.uk/ols4/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.MONDO

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Mondo for diseases."""
        try:
            url = f"{self.base_url}/search"
            params = {"q": query, "ontology": "mondo", "rows": min(limit, 100), "format": "json"}

            data = await self._make_request(url, params)

            concepts = []
            if "response" in data and "docs" in data["response"]:
                for doc in data["response"]["docs"]:
                    concept = self._convert_mondo_result_to_concept(doc)
                    if concept:
                        concepts.append(concept)

            logger.info(f"Mondo search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Mondo search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed disease information from Mondo."""
        try:
            # concept_id should be Mondo ID (e.g., MONDO:0005148)
            # If it's just the numeric part, add the prefix
            if concept_id.isdigit():
                concept_id = f"MONDO:{concept_id.zfill(7)}"

            # Use OLS terms endpoint  # noqa: E501
            encoded_id = concept_id.replace(":", "_")
            url = f"{self.base_url}/ontologies/mondo/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252F{encoded_id}"  # noqa: E501

            data = await self._make_request(url)

            if data:
                concept = self._convert_mondo_details_to_concept(data)
                return concept

            return None

        except Exception as e:
            logger.error(f"Failed to get Mondo concept details for '{concept_id}': {e}")
            return None

    def _convert_mondo_result_to_concept(self, result: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Mondo OLS search result to unified concept."""
        try:
            mondo_id = result.get("short_form", "")
            label = result.get("label", "")

            if not mondo_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=mondo_id, primary_label=label, concept_type=ConceptType.DISEASE
            )

            concept.add_identifier(KnowledgeSource.MONDO, mondo_id, label, result.get("iri", ""))

            if "synonym" in result:
                concept.synonyms.extend(result["synonym"])

            if "description" in result:
                concept.definitions.extend(result["description"])

            concept.confidence_score = 0.95
            concept.source_data[KnowledgeSource.MONDO] = result

            return concept

        except Exception as e:
            logger.error(f"Error converting Mondo result: {e}")
            return None

    def _convert_mondo_details_to_concept(self, data: dict[str, Any]) -> UnifiedConcept | None:
        """Convert Mondo OLS detailed concept to unified concept."""
        try:
            mondo_id = data.get("short_form", "")
            label = data.get("label", "")

            if not mondo_id or not label:
                return None

            concept = UnifiedConcept(
                primary_id=mondo_id, primary_label=label, concept_type=ConceptType.DISEASE
            )

            concept.add_identifier(KnowledgeSource.MONDO, mondo_id, label, data.get("iri", ""))

            if "synonyms" in data:
                concept.synonyms.extend(data["synonyms"])

            if "description" in data:
                concept.definitions.extend(data["description"])

            # Extract cross-references (like UMLS, MESH, etc.)
            if "annotation" in data:
                xrefs = data["annotation"].get("database_cross_reference", [])
                for xref in xrefs:
                    # xref might be like "UMLS:C0005745"
                    concept.categories.append(f"Xref: {xref}")

            concept.confidence_score = 1.0
            concept.source_data[KnowledgeSource.MONDO] = data

            return concept

        except Exception as e:
            logger.error(f"Error converting Mondo details: {e}")
            return None
