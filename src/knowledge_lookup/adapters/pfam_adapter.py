"""
Pfam Knowledge Source Adapter

Adapter for querying Pfam (now part of InterPro), a large collection of
protein families, each represented by multiple sequence alignments and HMMs.

API documentation: https://www.ebi.ac.uk/interpro/api/ (Pfam data is served via InterPro)
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class PfamAdapter(KnowledgeSourceAdapter):
    """Adapter for Pfam protein families database (served via InterPro API)."""

    def __init__(self, config):
        super().__init__(config)
        # Pfam data is now served via the InterPro API using member_db=pfam
        self.base_url = "https://www.ebi.ac.uk/interpro/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.PFAM

    def is_available(self) -> bool:
        return True  # Pfam/InterPro is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search Pfam for protein families."""
        try:
            url = f"{self.base_url}/entry/pfam/"
            params = {
                "search": query,
                "page_size": min(limit, 20),
                "format": "json",
            }

            data = await self._make_request(url, params)
            concepts = []

            results = data.get("results", [])
            for item in results[:limit]:
                concept = self._convert_result_to_concept(item)
                if concept:
                    concepts.append(concept)

            logger.info(f"Pfam search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"Pfam search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information about a specific Pfam entry."""
        try:
            pfam_id = concept_id.replace("Pfam:", "").strip()
            if not pfam_id.startswith("PF"):
                pfam_id = f"PF{pfam_id}"

            url = f"{self.base_url}/entry/pfam/{pfam_id}"
            data = await self._make_request(url)
            if not data:
                return None

            return self._convert_result_to_concept(data)

        except Exception as e:
            logger.error(f"Pfam get_concept_details failed for '{concept_id}': {e}")
            return None

    def _convert_result_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a Pfam entry to a UnifiedConcept."""
        try:
            metadata = item.get("metadata", item)
            pfam_id = metadata.get("accession", "")
            name = metadata.get("name", {})
            if isinstance(name, dict):
                label = name.get("name", "") or name.get("short", pfam_id)
            else:
                label = str(name) if name else pfam_id

            if not pfam_id or not label:
                return None

            concept_id = f"Pfam:{pfam_id}"
            entry_type = metadata.get("type", "").lower()

            concept_type = (
                ConceptType.PROTEIN if entry_type == "family" else ConceptType.MOLECULAR_ENTITY
            )
            concept = self._create_concept(concept_id, label, concept_type)

            # Description
            description = metadata.get("description", "")
            if isinstance(description, str) and description:
                concept.definitions.append(description[:500])
            elif isinstance(description, list):
                for desc in description:
                    text = desc.get("text", "") if isinstance(desc, dict) else str(desc)
                    if text:
                        concept.definitions.append(text[:500])

            # Entry type
            if entry_type:
                concept.semantic_types.append(entry_type)

            # Clan info
            clan = metadata.get("clan", "")
            if clan:
                concept.categories.append(f"clan:{clan}")

            concept.confidence_score = 0.85
            concept.source_data[KnowledgeSource.PFAM] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting Pfam result: {e}")
            return None
