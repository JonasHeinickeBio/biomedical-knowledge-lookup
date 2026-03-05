"""
STRING Knowledge Source Adapter

Adapter for querying STRING, a database of known and predicted protein-protein
interactions, including direct (physical) and indirect (functional) associations.

API documentation: https://string-db.org/cgi/help?sessionId=
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)

_STRING_BASE_URL = "https://string-db.org/api"


class STRINGAdapter(KnowledgeSourceAdapter):
    """Adapter for STRING protein-protein interaction database."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = _STRING_BASE_URL

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.STRING

    def is_available(self) -> bool:
        return True  # STRING is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search STRING for proteins and protein-protein interactions."""
        try:
            # Resolve protein identifiers
            url = f"{self.base_url}/json/resolve"
            params = {
                "identifier": query,
                "species": 9606,  # Homo sapiens
                "limit": min(limit, 5),
            }

            data = await self._make_request(url, params)
            concepts = []

            if isinstance(data, list):
                for item in data[:limit]:
                    concept = self._convert_resolve_to_concept(item)
                    if concept:
                        concepts.append(concept)

            logger.info(f"STRING search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"STRING search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get protein details and interaction partners from STRING."""
        try:
            protein_id = concept_id.replace("STRING:", "").strip()

            url = f"{self.base_url}/json/resolve"
            params = {
                "identifier": protein_id,
                "species": 9606,
                "limit": 1,
            }

            data = await self._make_request(url, params)
            if not isinstance(data, list) or not data:
                return None

            concept = self._convert_resolve_to_concept(data[0])
            if concept:
                # Enrich with interaction partners
                await self._add_interaction_partners(concept, data[0].get("stringId", protein_id))

            return concept

        except Exception as e:
            logger.error(f"STRING get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _add_interaction_partners(self, concept: UnifiedConcept, string_id: str) -> None:
        """Fetch top interaction partners and attach them to the concept."""
        try:
            url = f"{self.base_url}/json/network"
            params = {
                "identifiers": string_id,
                "species": 9606,
                "limit": 5,
            }
            data = await self._make_request(url, params)
            if isinstance(data, list):
                for interaction in data[:5]:
                    partner_a = interaction.get("preferredName_A", "")
                    partner_b = interaction.get("preferredName_B", "")
                    score = interaction.get("score", 0)
                    for partner in (partner_a, partner_b):
                        if partner and partner != concept.primary_label:
                            concept.related.append(f"{partner}(score={score})")
        except Exception as e:
            logger.warning(f"STRING interaction fetch failed: {e}")

    def _convert_resolve_to_concept(self, item: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert a STRING resolve result to a UnifiedConcept."""
        try:
            string_id = item.get("stringId", "")
            preferred_name = item.get("preferredName", "")
            annotation = item.get("annotation", "")

            if not string_id or not preferred_name:
                return None

            concept_id = f"STRING:{string_id}"
            concept = self._create_concept(concept_id, preferred_name, ConceptType.PROTEIN)

            if annotation:
                concept.definitions.append(annotation[:500])

            # Taxon
            taxon_id = item.get("taxonId", "")
            if taxon_id:
                concept.categories.append(f"taxon:{taxon_id}")

            concept.confidence_score = 0.8
            concept.source_data[KnowledgeSource.STRING] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting STRING result: {e}")
            return None
