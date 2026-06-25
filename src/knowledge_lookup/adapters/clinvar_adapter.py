"""
ClinVar Knowledge Source Adapter

Adapter for querying ClinVar, NCBI's database of genomic variation and
its relationship to human health.

API documentation: https://www.ncbi.nlm.nih.gov/clinvar/docs/api_http/
"""

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class ClinVarAdapter(KnowledgeSourceAdapter):
    """Adapter for ClinVar clinical variant database."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.clinvar_url = "https://clinvar.ncbi.nlm.nih.gov/api/rest"

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.CLINVAR

    def is_available(self) -> bool:
        return True  # ClinVar is publicly available via NCBI EUtils

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search ClinVar for clinical variants."""
        try:
            # Use NCBI EUtils esearch to find ClinVar entries
            url = f"{self.base_url}/esearch.fcgi"
            params = {
                "db": "clinvar",
                "term": query,
                "retmax": min(limit, 20),
                "retmode": "json",
            }

            data = await self._make_request(url, params)
            id_list = data.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return []

            # Fetch summaries for found IDs
            concepts = await self._fetch_summaries(id_list[:limit])
            logger.info(f"ClinVar search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"ClinVar search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information about a specific ClinVar variant."""
        try:
            # Strip prefix if present
            ncbi_id = concept_id.replace("ClinVar:", "").replace("VCV", "").strip()

            url = f"{self.base_url}/esummary.fcgi"
            params = {
                "db": "clinvar",
                "id": ncbi_id,
                "retmode": "json",
            }

            data = await self._make_request(url, params)
            result = data.get("result", {})
            uids = result.get("uids", [])

            if not uids:
                return None

            item = result.get(str(uids[0]), {})
            return self._convert_result_to_concept(item)

        except Exception as e:
            logger.error(f"ClinVar get_concept_details failed for '{concept_id}': {e}")
            return None

    async def _fetch_summaries(self, id_list: list[str]) -> list[UnifiedConcept]:
        """Fetch and convert summaries for a list of ClinVar IDs."""
        try:
            url = f"{self.base_url}/esummary.fcgi"
            params = {
                "db": "clinvar",
                "id": ",".join(id_list),
                "retmode": "json",
            }

            data = await self._make_request(url, params)
            result = data.get("result", {})
            uids = result.get("uids", [])

            concepts = []
            for uid in uids:
                item = result.get(str(uid), {})
                if item:
                    concept = self._convert_result_to_concept(item)
                    if concept:
                        concepts.append(concept)
            return concepts

        except Exception as e:
            logger.error(f"ClinVar summary fetch failed: {e}")
            return []

    def _convert_result_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
        """Convert a ClinVar summary item to a UnifiedConcept."""
        try:
            uid = str(item.get("uid", ""))
            title = item.get("title", "") or item.get("variation_name", "")

            if not uid or not title:
                return None

            concept_id = f"ClinVar:{uid}"
            concept = self._create_concept(concept_id, title, ConceptType.MOLECULAR_ENTITY)

            # Clinical significance
            clin_sig = item.get("clinical_significance", {})
            if isinstance(clin_sig, dict):
                sig_desc = clin_sig.get("description", "")
                if sig_desc:
                    if concept.categories is not None:
                        concept.categories.append(f"clinical_significance:{sig_desc}")

            # Gene info
            gene_sort = item.get("gene_sort", "")
            if gene_sort:
                if concept.categories is not None:
                    concept.categories.append(f"gene:{gene_sort}")

            # Variant type
            variation_type = item.get("obj_type", "")
            if variation_type:
                if concept.semantic_types is not None:
                    concept.semantic_types.append(variation_type)

            # Supporting traits / conditions
            trait_set = item.get("trait_set", [])
            if isinstance(trait_set, list):
                for trait in trait_set:
                    trait_name = (
                        trait.get("trait_name", "") if isinstance(trait, dict) else str(trait)
                    )
                    if trait_name:
                        if concept.categories is not None:
                            concept.categories.append(f"condition:{trait_name}")

            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.CLINVAR] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting ClinVar result: {e}")
            return None
