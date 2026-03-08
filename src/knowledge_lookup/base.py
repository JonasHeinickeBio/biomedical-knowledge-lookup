"""
Base classes for knowledge source adapters.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import aiohttp

from .models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class KnowledgeSourceAdapter(ABC):
    """
    Abstract base class for knowledge source adapters.
    Each adapter implements the interface to a specific knowledge source.
    """

    def __init__(self, config: LookupConfig):
        self.config = config
        self.source = self.get_source()
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        # Optionally initialize session here if needed
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @abstractmethod
    def get_source(self) -> KnowledgeSource:
        """Return the knowledge source this adapter handles."""
        pass

    @abstractmethod
    async def search_concepts(self, query: str, limit: int = 20) -> List[UnifiedConcept]:
        """
        Search for concepts matching the query.

        Args:
            query: Search term
            limit: Maximum number of results

        Returns:
            List of unified concepts
        """
        pass

    @abstractmethod
    async def get_concept_details(self, concept_id: str) -> Optional[UnifiedConcept]:
        """
        Get detailed information about a specific concept.

        Args:
            concept_id: Identifier of the concept

        Returns:
            Unified concept with details or None if not found
        """
        pass

    async def get_mappings(self, concept_id: str) -> List[Dict[str, Any]]:
        """
        Get mappings/cross-references for a concept.
        Default implementation returns empty list.

        Args:
            concept_id: Identifier of the concept

        Returns:
            List of mapping dictionaries
        """
        return []

    async def get_relationships(self, concept_id: str) -> List[Dict[str, Any]]:
        """
        Get relationships for a concept.
        Default implementation returns empty list.

        Args:
            concept_id: Identifier of the concept

        Returns:
            List of relationship dictionaries
        """
        return []

    def is_available(self) -> bool:
        """
        Check if this knowledge source is available.
        Default implementation returns True.
        """
        return True

    def get_rate_limit(self) -> float:
        """Get rate limit for this source (requests per second)."""
        return self.config.rate_limits.get(self.source, 1.0)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_per_source)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        session = await self._get_session()

        # Add default User-Agent if not present
        request_headers = headers or {}
        if "User-Agent" not in request_headers:
            request_headers["User-Agent"] = "AID-PAIS-Knowledge-Lookup/1.0"

        try:
            if json_data:
                # Use POST for JSON data
                async with session.post(
                    url, params=params, headers=request_headers, json=json_data
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                # Use GET for params
                async with session.get(url, params=params, headers=request_headers) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Request failed for {self.source.value}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {self.source.value}: {e}")
            raise

    async def _make_request_text(
        self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None
    ) -> str:
        """Make HTTP request and return text response."""
        session = await self._get_session()

        try:
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"Request failed for {self.source.value}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {self.source.value}: {e}")
            raise

    async def close(self):
        """Close the adapter and cleanup resources."""
        if self.session and not self.session.closed:
            await self.session.close()

    def _create_concept(
        self, concept_id: str, label: str, concept_type: ConceptType = ConceptType.UNKNOWN
    ) -> UnifiedConcept:
        """Create a unified concept with this source as primary."""
        concept = UnifiedConcept(
            primary_id=concept_id, primary_label=label, concept_type=concept_type
        )
        concept.add_identifier(self.source, concept_id, label)
        return concept

    def _determine_concept_type(
        self, semantic_types: List[str], categories: List[str] = None
    ) -> ConceptType:
        """
        Determine concept type from semantic types and categories.
        Override in subclasses for source-specific logic.
        """
        semantic_types = [st.lower() for st in semantic_types]
        categories = [cat.lower() for cat in (categories or [])]

        # Disease detection
        if any(
            term in semantic_types for term in ["disease", "disorder", "syndrome", "condition"]
        ):
            return ConceptType.DISEASE

        # Symptom detection
        if any(term in semantic_types for term in ["symptom", "sign", "finding"]):
            return ConceptType.SYMPTOM

        # Drug detection
        if any(
            term in semantic_types for term in ["drug", "medication", "pharmaceutical", "compound"]
        ):
            return ConceptType.DRUG

        # Gene detection
        if any(term in semantic_types for term in ["gene", "genetic"]):
            return ConceptType.GENE

        # Protein detection
        if any(term in semantic_types for term in ["protein", "enzyme"]):
            return ConceptType.PROTEIN

        # Anatomy detection
        if any(term in semantic_types for term in ["anatomy", "anatomical", "body part", "organ"]):
            return ConceptType.ANATOMY

        # Procedure detection
        if any(term in semantic_types for term in ["procedure", "therapy", "treatment"]):
            return ConceptType.PROCEDURE

        # Chemical detection
        if any(term in semantic_types for term in ["chemical", "substance", "compound"]):
            return ConceptType.CHEMICAL

        # Organism detection
        if any(term in semantic_types for term in ["organism", "species", "bacteria", "virus"]):
            return ConceptType.ORGANISM

        return ConceptType.UNKNOWN
