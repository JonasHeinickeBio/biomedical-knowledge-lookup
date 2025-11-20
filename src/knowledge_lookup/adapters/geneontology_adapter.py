"""
Adapter for Gene Ontology (GO).
"""

from ..base import KnowledgeSourceAdapter
from ..models import KnowledgeSource


class GeneOntologyAdapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.GO

    async def search_concepts(self, query: str, limit: int = 20):
        return []

    async def get_concept_details(self, concept_id: str):
        return None
