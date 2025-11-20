"""
MONDO Knowledge Source Adapter

Adapter for querying MONDO disease ontology via OLS API.
"""

import logging

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class MondoAdapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.MONDO

    async def search_concepts(self, query: str, limit: int = 20):
        import aiohttp

        url = "https://www.ebi.ac.uk/ols/api/ontologies/mondo/search"
        params = {"q": query, "rows": limit, "format": "json"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                results = []
                for doc in data.get("response", {}).get("docs", []):
                    concept = UnifiedConcept(
                        primary_id=doc.get("iri", ""),
                        primary_label=doc.get("label", ""),
                        concept_type=ConceptType.DISEASE,
                    )
                    results.append(concept)
                return results

    async def get_concept_details(self, concept_id: str):
        # Implement details fetch if needed
        return None
