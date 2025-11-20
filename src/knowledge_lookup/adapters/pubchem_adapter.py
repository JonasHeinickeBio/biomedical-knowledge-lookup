"""
Adapter for PubChem drug/compound database.
"""

import aiohttp

from ..base import KnowledgeSourceAdapter
from ..models import KnowledgeSource


class PubChemAdapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.PUBCHEM

    async def search_concepts(self, query: str, limit: int = 20):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/cids/JSON"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                cids = data.get("IdentifierList", {}).get("CID", [])[:limit]
                return cids

    async def get_concept_details(self, concept_id: str):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{concept_id}/JSON"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return data
