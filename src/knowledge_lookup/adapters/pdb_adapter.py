"""
PDB Knowledge Source Adapter

Adapter for querying the Protein Data Bank (PDB/RCSB), the world's largest
repository of 3D structural data of biological macromolecules.

API documentation: https://data.rcsb.org/
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class PDBAdapter(KnowledgeSourceAdapter):
    """Adapter for RCSB Protein Data Bank (PDB)."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://search.rcsb.org/rcsbsearch/v2"
        self.data_url = "https://data.rcsb.org/rest/v1/core"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.PDB

    def is_available(self) -> bool:
        return True  # PDB is publicly available

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search PDB for protein structures."""
        try:
            url = f"{self.base_url}/query"
            # RCSB full-text search using POST-style JSON
            session = await self._get_session()
            search_payload = {
                "query": {
                    "type": "terminal",
                    "service": "full_text",
                    "parameters": {"value": query},
                },
                "return_type": "entry",
                "request_options": {"paginate": {"start": 0, "rows": min(limit, 25)}},
            }

            concepts = []
            async with session.post(url, json=search_payload) as response:
                response.raise_for_status()
                data = await response.json()

                result_set = data.get("result_set", [])
                for item in result_set[:limit]:
                    entry_id = item.get("identifier", "")
                    if entry_id:
                        concept = await self._fetch_entry_summary(entry_id)
                        if concept:
                            concepts.append(concept)

            logger.info(f"PDB search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"PDB search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information about a specific PDB entry."""
        try:
            pdb_id = concept_id.replace("PDB:", "").strip().upper()
            return await self._fetch_entry_summary(pdb_id)
        except Exception as e:
            logger.error(f"PDB get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _fetch_entry_summary(self, pdb_id: str) -> UnifiedConcept | None:
        """Fetch and convert a PDB entry summary."""
        try:
            url = f"{self.data_url}/entry/{pdb_id}"
            data = await self._make_request(url)
            if not data:
                return None
            return self._convert_result_to_concept(data)
        except Exception as e:
            logger.error(f"PDB entry fetch failed for '{pdb_id}': {e}")
            return None

    def _convert_result_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a PDB entry to a UnifiedConcept."""
        try:
            struct = item.get("struct", {})
            entry_id = item.get("entry", {}).get("id", "")
            title = struct.get("title", "")

            if not entry_id or not title:
                return None

            concept_id = f"PDB:{entry_id}"
            concept = self._create_concept(concept_id, title, ConceptType.PROTEIN)

            # Keywords
            keywords = struct.get("pdbx_descriptor", "")
            if keywords:
                for kw in keywords.split(","):
                    kw = kw.strip()
                    if kw:
                        concept.semantic_types.append(kw)

            # Experimental method
            exptl = item.get("exptl", [{}])
            if isinstance(exptl, list) and exptl:
                method = exptl[0].get("method", "")
                if method:
                    concept.categories.append(f"method:{method}")

            # Resolution
            refine = item.get("refine", [{}])
            if isinstance(refine, list) and refine:
                resolution = refine[0].get("ls_d_res_high", "")
                if resolution:
                    concept.categories.append(f"resolution:{resolution}Å")

            # Release date
            revision = item.get("pdbx_audit_revision_history", [{}])
            if isinstance(revision, list) and revision:
                release_date = revision[0].get("revision_date", "")
                if release_date:
                    concept.last_updated = release_date

            concept.confidence_score = 0.85
            concept.source_data[KnowledgeSource.PDB] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting PDB result: {e}")
            return None
