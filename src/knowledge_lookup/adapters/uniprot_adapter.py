"""
UniProt Knowledge Source Adapter

Adapter for querying UniProt protein database.
"""

import logging

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class UniProtAdapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.UNIPROT

    async def search_concepts(self, query: str, limit: int = 20):
        import aiohttp

        try:
            url = "https://rest.uniprot.org/uniprotkb/search"
            params = {"query": query, "size": limit}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    results = []
                    for entry in data.get("results", []):
                        concept = UnifiedConcept(
                            primary_id=entry.get("primaryAccession", ""),
                            primary_label=entry.get("proteinDescription", {})
                            .get("recommendedName", {})
                            .get("fullName", {})
                            .get("value", ""),
                            concept_type=ConceptType.PROTEIN,
                        )
                        results.append(concept)
                    return results
        except Exception as e:
            logger.error(f"Error searching UniProt concepts: {e}")
            return []

    async def get_concept_details(self, concept_id: str):
        # Implement details fetch if needed
        return None
