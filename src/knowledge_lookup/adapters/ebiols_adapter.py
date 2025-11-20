"""
Adapter for EBI Ontology Lookup Service (OLS).
"""

from ..base import KnowledgeSourceAdapter
from ..models import KnowledgeSource


class EBIOLSAdapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.EBIOLS

    async def search_concepts(self, query: str, limit: int = 20):
        return []

    async def get_concept_details(self, concept_id: str):
        return None
