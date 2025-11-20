"""
Adapter for OxO (Ontology Cross-reference Service).
"""

import logging
from typing import Any, Dict, List

from ..base import KnowledgeSourceAdapter
from ..models import KnowledgeSource, LookupConfig

logger = logging.getLogger(__name__)


class OxOAdapter(KnowledgeSourceAdapter):
    """
    Adapter for OxO (Ontology Cross-reference Service).
    OxO provides mappings between ontology terms.
    """

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/spot/oxo/api"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.OXO

    def is_available(self) -> bool:
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> List:
        logger.info("OxO adapter is primarily for mappings, not direct concept search")
        return []

    async def get_concept_details(self, concept_id: str):
        return None

    async def get_mappings(self, concept_id: str) -> List[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/mappings"
            params = {"fromId": concept_id, "size": 100}
            data = await self._make_request(url, params)
            mappings = []
            if "_embedded" in data and "mappings" in data["_embedded"]:
                for mapping in data["_embedded"]["mappings"]:
                    mappings.append(
                        {
                            "fromId": mapping.get("fromTerm", {}).get("curie", ""),
                            "toId": mapping.get("toTerm", {}).get("curie", ""),
                            "fromSource": mapping.get("fromTerm", {})
                            .get("datasource", {})
                            .get("name", ""),
                            "toSource": mapping.get("toTerm", {})
                            .get("datasource", {})
                            .get("name", ""),
                            "mappingType": mapping.get("scope", "related"),
                            "confidence": 1.0,
                        }
                    )
            logger.info(f"OxO found {len(mappings)} mappings for '{concept_id}'")
            return mappings
        except Exception as e:
            logger.error(f"OxO mapping lookup failed for '{concept_id}': {e}")
            return []
