"""
Adapter for DrugBank drug database.
"""

from ..base import KnowledgeSourceAdapter
from ..models import KnowledgeSource


class DrugBankAdapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.DRUGBANK

    async def search_concepts(self, query: str, limit: int = 20):
        return []

    async def get_concept_details(self, concept_id: str):
        return None
