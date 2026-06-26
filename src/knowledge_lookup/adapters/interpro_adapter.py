"""
InterPro Knowledge Source Adapter

Adapter for querying InterPro, a database of protein families, domains, and
functional sites that integrates multiple protein signature databases.

API documentation: https://www.ebi.ac.uk/interpro/result/download/#
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class InterProAdapter(KnowledgeSourceAdapter):
    """Adapter for InterPro protein families and domains database."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/interpro/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.INTERPRO

    def is_available(self) -> bool:
        return True  # InterPro is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search InterPro for protein families and domains."""
        try:
            url = f"{self.base_url}/entry/interpro/"
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

            logger.info(f"InterPro search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"InterPro search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information about a specific InterPro entry."""
        try:
            ipr_id = concept_id.replace("InterPro:", "").strip()
            if not ipr_id.startswith("IPR"):
                ipr_id = f"IPR{ipr_id}"

            url = f"{self.base_url}/entry/interpro/{ipr_id}"
            data = await self._make_request(url)
            if not data:
                return None

            return self._convert_result_to_concept(data)

        except Exception as e:
            logger.error(f"InterPro get_concept_details failed for '{concept_id}': {e}")
            return None

    def _convert_result_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert an InterPro entry to a UnifiedConcept."""
        try:
            metadata = item.get("metadata", item)
            ipr_id = metadata.get("accession", "")
            name = metadata.get("name", {})
            if isinstance(name, dict):
                label = name.get("name", "") or name.get("short", ipr_id)
            else:
                label = str(name) if name else ipr_id

            if not ipr_id or not label:
                return None

            concept_id = f"InterPro:{ipr_id}"
            entry_type = metadata.get("type", "").lower()

            if entry_type in ("family",):
                concept_type = ConceptType.PROTEIN
            elif entry_type in ("domain", "repeat", "homologous_superfamily"):
                concept_type = ConceptType.MOLECULAR_ENTITY
            else:
                concept_type = ConceptType.PROTEIN

            concept = self._create_concept(concept_id, label, concept_type)

            # Description
            description = metadata.get("description", [])
            if isinstance(description, list):
                for desc in description:
                    if isinstance(desc, dict):
                        text = desc.get("text", "")
                        if text:
                            if concept.definitions is not None:
                                concept.definitions.append(text[:500])
                    elif isinstance(desc, str):
                        if concept.definitions is not None:
                            concept.definitions.append(desc[:500])
            elif isinstance(description, str) and description:
                if concept.definitions is not None:
                    concept.definitions.append(description[:500])

            # Entry type
            if entry_type:
                if concept.semantic_types is not None:
                    concept.semantic_types.append(entry_type)

            # Source databases (integrated signatures)
            integrated_db = metadata.get("integrated", [])
            if isinstance(integrated_db, list):
                for db_entry in integrated_db:
                    if isinstance(db_entry, dict):
                        db_acc = db_entry.get("accession", "")
                        if db_acc:
                            if concept.categories is not None:
                                concept.categories.append(db_acc)

            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.INTERPRO] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting InterPro result: {e}")
            return None
