"""
OxO (Ontology Cross-reference Service) Adapter

This module provides integration with EBI's OxO service for ontology cross-references and mappings.  # noqa: E501
OxO provides access to cross-references between terms from ontologies, vocabularies and coding standards.  # noqa: E501

API Documentation: https://www.ebi.ac.uk/spot/oxo/docs/api
"""  # noqa: E501

import logging
from typing import Any

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

logger = logging.getLogger(__name__)


class OxOAdapter(KnowledgeSourceAdapter):
    """
    Adapter for EBI OxO (Ontology Cross-reference Service) API

    OxO provides mappings and cross-references between terms from different ontologies,
    vocabularies and coding standards.
    """

    def __init__(self, config: LookupConfig):
        """
        Initialize OxO adapter

        Args:
            config: Configuration for the knowledge lookup system
        """
        super().__init__(config)
        self.base_url = "https://www.ebi.ac.uk/spot/oxo"
        self.api_url = f"{self.base_url}/api"

    def get_source(self) -> KnowledgeSource:
        """Return the knowledge source this adapter handles."""
        return KnowledgeSource.OXO

    async def get_concept_by_id(self, concept_id: str, **kwargs) -> UnifiedConcept | None:
        """
        Get cross-references for a specific concept ID

        Args:
            concept_id: The concept identifier (e.g., "DOID:162", "MONDO:0004992")
            **kwargs: Additional parameters:
                - distance: Maximum mapping distance (default: 1)
                - mapping_target: List of target ontologies to restrict mappings
                - mapping_source: List of source ontologies to restrict mappings

        Returns:
            UnifiedConcept with cross-references or None if not found
        """
        try:
            # Extract parameters
            distance = kwargs.get("distance", 1)
            mapping_target = kwargs.get("mapping_target", [])
            mapping_source = kwargs.get("mapping_source", [])

            # Prepare search request
            search_data: dict[str, Any] = {"ids": [concept_id], "distance": distance}

            if mapping_target:
                search_data["mappingTarget"] = mapping_target
            if mapping_source:
                search_data["mappingSource"] = mapping_source

            # Make API request using POST with JSON data through _make_request
            # (gets retry + circuit-breaker protection automatically)
            response_data = await self._make_request(
                f"{self.api_url}/search",
                json_data=search_data,
                headers={"Content-Type": "application/json"},
            )

            # Parse response
            if (
                response_data
                and "_embedded" in response_data
                and "searchResults" in response_data["_embedded"]
            ):
                results = response_data["_embedded"]["searchResults"]
                if results:
                    result = results[0]
                    return self._parse_search_result(result, concept_id)

            return None

        except Exception as e:
            logger.error(f"Error retrieving concept {concept_id} from OxO: {e}")
            return None

    async def search_concepts(self, query: str, limit: int = 10) -> list[UnifiedConcept]:
        """
        Search for concepts with cross-references

        Args:
            query: Search term or concept ID
            limit: Maximum number of results

        Returns:
            List of UnifiedConcept objects with cross-references
        """
        try:
            # Prepare search request
            search_data: dict[str, Any] = {
                "ids": [query],
                "distance": 2,  # Default to distance 2 for broader search
            }

            # Make API request using POST with JSON data through _make_request
            # (gets retry + circuit-breaker protection automatically)
            response_data = await self._make_request(
                f"{self.api_url}/search",
                json_data=search_data,
                headers={"Content-Type": "application/json"},
            )

            # Parse results
            concepts = []
            if (
                response_data
                and "_embedded" in response_data
                and "searchResults" in response_data["_embedded"]
            ):
                results = response_data["_embedded"]["searchResults"]

                for result in results[:limit]:
                    concept = self._parse_search_result(result)
                    if concept:
                        concepts.append(concept)

            return concepts

        except Exception as e:
            logger.error(f"Error searching OxO for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """
        Get detailed information about a concept including all its mappings

        Args:
            concept_id: Concept identifier

        Returns:
            UnifiedConcept with detailed mappings or None
        """
        return await self.get_concept_by_id(
            concept_id, distance=3
        )  # Use distance 3 for detailed search

    async def get_mappings_for_concepts(
        self, concept_ids: list[str], **kwargs
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get cross-reference mappings for multiple concepts

        Args:
            concept_ids: List of concept identifiers
            **kwargs: Additional parameters:
                - distance: Maximum mapping distance (default: 1)
                - mapping_target: Target ontologies
                - mapping_source: Source ontologies

        Returns:
            Dictionary mapping concept IDs to their cross-references
        """
        try:
            # Extract parameters
            distance = kwargs.get("distance", 1)
            mapping_target = kwargs.get("mapping_target", [])
            mapping_source = kwargs.get("mapping_source", [])

            # Prepare batch search request
            search_data: dict[str, Any] = {"ids": concept_ids, "distance": distance}

            if mapping_target:
                search_data["mappingTarget"] = mapping_target
            if mapping_source:
                search_data["mappingSource"] = mapping_source

            # Make API request using POST with JSON data through _make_request
            # (gets retry + circuit-breaker protection automatically)
            response_data = await self._make_request(
                f"{self.api_url}/search",
                json_data=search_data,
                headers={"Content-Type": "application/json"},
            )

            # Parse results
            mappings: dict[str, list[dict[str, Any]]] = {}
            if (
                response_data
                and "_embedded" in response_data
                and "searchResults" in response_data["_embedded"]
            ):
                results = response_data["_embedded"]["searchResults"]

                for result in results:
                    concept_id = result.get("queryId", result.get("curie"))
                    if concept_id:
                        mappings[concept_id] = self._extract_mappings(result)

            return mappings

        except Exception as e:
            logger.error(f"Error getting mappings for concepts from OxO: {e}")
            return {}

    async def get_datasources(self) -> list[dict[str, Any]]:
        """
        Get available data sources in OxO

        Returns:
            List of available data sources with metadata
        """
        try:
            response_data = await self._make_request(
                f"{self.api_url}/datasources", params={"size": "1000"}
            )

            if "_embedded" in response_data and "datasources" in response_data["_embedded"]:
                return response_data["_embedded"]["datasources"]

            return []

        except Exception as e:
            logger.error(f"Error retrieving OxO datasources: {e}")
            return []

    def _parse_search_result(
        self, result: dict[str, Any], original_query: str | None = None
    ) -> UnifiedConcept | None:
        """
        Parse OxO search result into UnifiedConcept

        Args:
            result: OxO search result
            original_query: Original query term

        Returns:
            UnifiedConcept or None
        """
        try:
            # Extract basic information
            concept_id = result.get("curie") or result.get("queryId")
            label = result.get("label")

            if not concept_id:
                return None

            # Create unified concept using the correct constructor
            concept = self._create_concept(
                concept_id=concept_id, label=label or concept_id, concept_type=ConceptType.UNKNOWN
            )

            # Add OxO as a source
            concept.add_identifier(KnowledgeSource.OXO, concept_id, label)

            # Add cross-references from mappings
            mappings = self._extract_mappings(result)
            for mapping in mappings:
                target_source = self._get_knowledge_source_from_prefix(
                    mapping.get("targetPrefix", "")
                )
                if target_source:
                    concept.add_mapping(
                        target_source=target_source,
                        target_id=mapping.get("curie", ""),
                        mapping_type="related",
                        confidence=self._calculate_mapping_confidence(mapping),
                        mapping_source="oxo",
                    )

            # Store raw data
            concept.source_data[KnowledgeSource.OXO] = result
            concept.confidence_score = max(concept.confidence_score or 0, 0.8)

            return concept

        except Exception as e:
            logger.error(f"Error parsing OxO search result: {e}")
            return None

    def _extract_mappings(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract mapping information from OxO result

        Args:
            result: OxO search result

        Returns:
            List of mapping dictionaries
        """
        mappings = []

        if "mappingResponseList" in result:
            for mapping in result["mappingResponseList"]:
                mapping_info = {
                    "curie": mapping.get("curie"),
                    "label": mapping.get("label"),
                    "targetPrefix": mapping.get("targetPrefix"),
                    "sourcePrefixes": mapping.get("sourcePrefixes", []),
                    "distance": mapping.get("distance", 1),
                }
                mappings.append(mapping_info)

        return mappings

    def _calculate_mapping_confidence(self, mapping: dict[str, Any]) -> float:
        """
        Calculate confidence score for a mapping

        Args:
            mapping: Mapping information

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence
        confidence = 0.8

        # Adjust based on distance (closer mappings are more confident)
        distance = mapping.get("distance", 1)
        if distance == 1:
            confidence = 0.9  # Direct mapping
        elif distance == 2:
            confidence = 0.7  # One hop
        elif distance >= 3:
            confidence = 0.5  # Multiple hops

        # Adjust based on number of source prefixes (more sources = higher confidence)
        source_count = len(mapping.get("sourcePrefixes", []))
        if source_count > 1:
            confidence = min(1.0, confidence + 0.1)

        return confidence

    def _get_knowledge_source_from_prefix(self, prefix: str) -> KnowledgeSource | None:
        """
        Map ontology prefix to KnowledgeSource enum

        Args:
            prefix: Ontology prefix (e.g., "MONDO", "DOID")

        Returns:
            Corresponding KnowledgeSource or None
        """
        prefix_mapping = {
            "UMLS": KnowledgeSource.UMLS,
            "OLS": KnowledgeSource.OLS,
            "BIOPORTAL": KnowledgeSource.BIOPORTAL,
            "BIOONTOLOGY": KnowledgeSource.BIOONTOLOGY,
            "WIKIDATA": KnowledgeSource.WIKIDATA,
            "DBPEDIA": KnowledgeSource.DBPEDIA,
            "NCBI": KnowledgeSource.NCBI,
            "UNIPROT": KnowledgeSource.UNIPROT,
            "ENSEMBL": KnowledgeSource.ENSEMBL,
            "PUBCHEM": KnowledgeSource.PUBCHEM,
            "CHEMBL": KnowledgeSource.CHEMBL,
            # Add more mappings as needed
        }

        # Try direct mapping first
        if prefix.upper() in prefix_mapping:
            return prefix_mapping[prefix.upper()]

        # For unknown prefixes, we can still create mappings but won't have a specific source
        # Return None to indicate unknown source
        return None

    async def validate_connection(self) -> bool:
        """
        Validate connection to OxO API

        Returns:
            True if connection is successful
        """
        try:
            response_data = await self._make_request(
                f"{self.api_url}/datasources", params={"size": "1"}
            )
            return response_data is not None
        except Exception as e:
            logger.error(f"OxO connection validation failed: {e}")
            return False
