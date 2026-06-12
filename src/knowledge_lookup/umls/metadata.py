"""
UMLS metadata operations.

This module handles metadata retrieval such as semantic types and source vocabularies.
"""

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class APIClient(Protocol):
    """Protocol for API client interface."""

    def make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an API request."""
        ...


class UMLSMetadataService:
    """Service for UMLS metadata operations."""

    def __init__(self, api_client: APIClient, version: str = "current"):
        self.api_client = api_client
        self.version = version

    def get_semantic_types(self) -> list[dict[str, Any]]:
        """
        Get all available semantic types.

        Returns:
            List of semantic type dictionaries
        """
        endpoint = f"/metadata/{self.version}/semanticTypes"

        try:
            result = self.api_client.make_request(endpoint)
            semantic_types = result.get("results", [])

            logger.info(f"Retrieved {len(semantic_types)} semantic types")
            return semantic_types

        except Exception as e:
            logger.error(f"Failed to get semantic types: {e}")
            return []

    def get_sources(self) -> list[dict[str, Any]]:
        """
        Get all available source vocabularies.

        Returns:
            List of source dictionaries
        """
        endpoint = f"/metadata/{self.version}/sources"

        try:
            result = self.api_client.make_request(endpoint)
            sources = result.get("results", [])

            logger.info(f"Retrieved {len(sources)} source vocabularies")
            return sources

        except Exception as e:
            logger.error(f"Failed to get sources: {e}")
            return []
