"""
COSMIC Knowledge Source Adapter

Adapter for querying COSMIC (Catalogue of Somatic Mutations in Cancer),
the world's largest and most comprehensive resource for exploring the impact
of somatic mutations in human cancer.

API documentation: https://cancer.sanger.ac.uk/cosmic/download/api
"""

import logging
import os
from typing import Any, Dict, List, Optional

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class COSMICAdapter(KnowledgeSourceAdapter):
    """Adapter for COSMIC (Catalogue of Somatic Mutations in Cancer)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://cancer.sanger.ac.uk/api/rest/cosmic"
        # COSMIC requires authentication for full data access
        self.api_key = config.get_api_key("cosmic") or os.getenv("COSMIC_API_KEY")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.COSMIC

    def is_available(self) -> bool:
        # Basic gene/mutation search is available without auth via COSMIC website
        return True

    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """Search COSMIC for cancer genes and somatic mutations."""
        try:
            url = f"{self.base_url}/genes"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Basic {self.api_key}"

            params = {
                "gene_name": query,
                "limit": min(limit, 25),
            }

            data = await self._make_request(url, params, headers=headers if headers else None)
            concepts = []

            if isinstance(data, list):
                items = data
            else:
                items = data.get("genes", data.get("results", []))

            for item in items[:limit]:
                concept = self._convert_gene_to_concept(item)
                if concept:
                    concepts.append(concept)

            logger.info(f"COSMIC search for '{query}' returned {len(concepts)} concepts")
            return concepts

        except Exception as e:
            logger.error(f"COSMIC search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """Get detailed information about a specific COSMIC gene or mutation."""
        try:
            gene_id = concept_id.replace("COSMIC:", "").strip()

            url = f"{self.base_url}/genes/{gene_id}"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Basic {self.api_key}"

            data = await self._make_request(url, headers=headers if headers else None)
            if not data:
                return None

            return self._convert_gene_to_concept(data)

        except Exception as e:
            logger.error(f"COSMIC get_concept_details failed for '{concept_id}': {e}")
            return None

    def _convert_gene_to_concept(self, item: Dict[str, Any]) -> Optional[UnifiedConcept]:
        """Convert a COSMIC gene/mutation entry to a UnifiedConcept."""
        try:
            gene_name = item.get("gene_name", "") or item.get("name", "")
            gene_id = item.get("id", "") or item.get("cosmic_id", gene_name)

            if not gene_id or not gene_name:
                return None

            concept_id = f"COSMIC:{gene_id}"
            concept = self._create_concept(concept_id, gene_name, ConceptType.GENE)

            # Role in cancer
            role = item.get("role_in_cancer", "") or item.get("role", "")
            if role:
                concept.categories.append(f"role_in_cancer:{role}")

            # Tier
            tier = item.get("tier", "")
            if tier:
                concept.categories.append(f"tier:{tier}")

            # Synonyms / aliases
            synonyms = item.get("synonyms", [])
            if isinstance(synonyms, list):
                concept.synonyms.extend(synonyms)
            elif synonyms:
                concept.synonyms.append(str(synonyms))

            # Hallmarks / molecular info
            hallmarks = item.get("hallmarks", [])
            if isinstance(hallmarks, list):
                for h in hallmarks:
                    if isinstance(h, dict):
                        hm = h.get("hallmark", "")
                        if hm:
                            concept.semantic_types.append(hm)

            concept.confidence_score = 0.85
            concept.source_data[KnowledgeSource.COSMIC] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting COSMIC result: {e}")
            return None
