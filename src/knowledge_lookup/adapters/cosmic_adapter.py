"""
COSMIC Knowledge Source Adapter

Adapter for querying COSMIC (Catalogue of Somatic Mutations in Cancer),
the world's largest and most comprehensive resource for exploring the impact
of somatic mutations in human cancer.

COSMIC has no public, keyless query API. Programmatic access requires a
registered COSMIC account (HTTP Basic credentials), and COSMIC currently offers
authenticated file downloads rather than a gene/mutation query endpoint. Without
credentials the adapter reports itself unavailable.

API documentation: https://cancer.sanger.ac.uk/cosmic/download/api
"""

import logging
import os
from typing import Any

import aiohttp

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class COSMICAdapter(KnowledgeSourceAdapter):
    """Adapter for COSMIC (Catalogue of Somatic Mutations in Cancer)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.base_url = "https://cancer.sanger.ac.uk/api/rest/cosmic"
        # COSMIC requires authentication: base64("email:password") of a registered account
        self.api_key = config.get_api_key("cosmic") or os.getenv("COSMIC_API_KEY")

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.COSMIC

    def is_available(self) -> bool:
        # COSMIC has no public, keyless query API: all programmatic access requires
        # a registered COSMIC account (credentials sent as HTTP Basic auth). Without
        # credentials the adapter reports itself unavailable, so
        # CentralKnowledgeLookup skips it instead of collecting silent empty results.
        return bool(self.api_key)

    def _credentials_missing(self, operation: str) -> bool:
        """Log and return True when no COSMIC credentials are configured."""
        if self.api_key:
            return False
        logger.warning(
            f"COSMIC {operation} skipped: COSMIC requires a registered account. Set "
            "COSMIC_API_KEY (or api_keys={'cosmic': ...}) to base64('email:password')."
        )
        return True

    @staticmethod
    def _log_http_error(operation: str, error: Exception) -> None:
        """Log a failed COSMIC request, explaining the retired REST endpoint on 404."""
        if isinstance(error, aiohttp.ClientResponseError) and error.status == 404:
            logger.error(
                f"COSMIC {operation} failed: the legacy COSMIC REST endpoint answers 404. "
                "COSMIC currently offers only authenticated file downloads, not a "
                f"gene/mutation query API ({error})"
            )
        else:
            logger.error(f"COSMIC {operation} failed: {error}")

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search COSMIC for cancer genes and somatic mutations."""
        if self._credentials_missing(f"search for '{query}'"):
            return []
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
            self._log_http_error(f"search for '{query}'", e)
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get detailed information about a specific COSMIC gene or mutation."""
        if self._credentials_missing(f"details for '{concept_id}'"):
            return None
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
            self._log_http_error(f"get_concept_details for '{concept_id}'", e)
            return None

    def _convert_gene_to_concept(self, item: dict[str, Any]) -> UnifiedConcept | None:
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
                if concept.categories is not None:
                    concept.categories.append(f"role_in_cancer:{role}")

            # Tier
            tier = item.get("tier", "")
            if tier:
                if concept.categories is not None:
                    concept.categories.append(f"tier:{tier}")

            # Synonyms / aliases
            synonyms = item.get("synonyms", [])
            if isinstance(synonyms, list):
                if concept.synonyms is not None:
                    concept.synonyms.extend(synonyms)
            elif synonyms:
                if concept.synonyms is not None:
                    concept.synonyms.append(str(synonyms))

            # Hallmarks / molecular info
            hallmarks = item.get("hallmarks", [])
            if isinstance(hallmarks, list):
                for h in hallmarks:
                    if isinstance(h, dict):
                        hm = h.get("hallmark", "")
                        if hm:
                            if concept.semantic_types is not None:
                                concept.semantic_types.append(hm)

            concept.confidence_score = 0.85
            if isinstance(concept.source_data, dict):
                concept.source_data[KnowledgeSource.COSMIC] = item
            return concept

        except Exception as e:
            logger.error(f"Error converting COSMIC result: {e}")
            return None
