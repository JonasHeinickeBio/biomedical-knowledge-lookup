"""
Unified UMLS Client Implementation.

This module provides a unified client interface that includes both low-level API
communication and high-level service coordination for all UMLS operations.
"""

import logging
import os
import time
from datetime import datetime
from typing import Any

import requests
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .auth import UMLSAuthenticator
from .concepts import UMLSConceptService
from .metadata import UMLSMetadataService
from .models import UMLSConcept, UMLSSearchResult
from .search import UMLSSearchService

# Load .env file and configure logging
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logger.addHandler(logging.NullHandler())


def umls_retry(max_retries: int = 3):
    """Decorator to apply retry logic for UMLS API requests."""
    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, RuntimeError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


class OptimizedUMLSClient:
    """
    Unified UMLS API client with comprehensive functionality.

    This client combines both low-level API communication and high-level service
    coordination into a single, optimized interface.

    Features:
    - Cached authentication tokens
    - Built-in rate limiting and retry logic
    - Comprehensive search capabilities
    - Concept details and relationships
    - Semantic type filtering
    - Source vocabulary filtering
    - Batch operations
    - Comprehensive error handling
    - Statistics and monitoring
    """

    def __init__(
        self,
        api_key: str | None = None,
        version: str = "current",
        timeout: float = 30.0,
        max_retries: int = 3,
        rate_limit: float = 0.1,  # Seconds between requests
        cache_duration: int = 3600,  # Token cache duration in seconds
        api_url: str = "https://uts-ws.nlm.nih.gov/rest",
    ):
        self.api_key = api_key or os.getenv("UMLS_API_KEY_TU")
        if not self.api_key:
            raise ValueError("UMLS API key must be provided or set in .env as UMLS_API_KEY_TU.")

        self.version = version
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self.cache_duration = cache_duration
        self.api_url = api_url

        # API request tracking
        self.last_request_time = 0.0
        self.request_count = 0

        # Initialize authenticator
        self.authenticator = UMLSAuthenticator(
            api_key=self.api_key, timeout=timeout, cache_duration=cache_duration
        )

        # Initialize services
        self.search_service = UMLSSearchService(self, version)
        self.concept_service = UMLSConceptService(self, version)
        self.metadata_service = UMLSMetadataService(self, version)

    def _rate_limit_check(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    @umls_retry()
    def make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """
        Make an authenticated request to the UMLS API.

        This method combines the functionality of the old UMLSAPIClient.make_request
        with the unified client architecture.

        Args:
            endpoint: API endpoint (e.g., "/content/current/CUI/C0011849")
            params: Query parameters

        Returns:
            API response data as dictionary
        """
        self._rate_limit_check()

        params = params or {}
        params["ticket"] = self.authenticator.get_service_ticket()

        url = f"{self.api_url}{endpoint}"

        response = requests.get(url, params=params, timeout=self.timeout)

        if response.status_code != 200:
            raise RuntimeError(
                f"API request failed: {url} ({response.status_code}) - {response.text}"
            )

        self.request_count += 1

        try:
            result = response.json()

            # Handle case where the entire response is a string (error message)
            if isinstance(result, str):
                raise RuntimeError(f"UMLS API error: {result}")

            # Handle case where result is not a dictionary
            if not isinstance(result, dict):
                raise RuntimeError(f"UMLS API returned unexpected data type: {type(result)}")

            # Get the actual result content
            api_result = result.get("result", {})

            # Handle case where API returns error message as string in result field
            if isinstance(api_result, str):
                # If result is a string (error message), raise an exception
                raise RuntimeError(f"UMLS API error: {api_result}") from None

            return api_result if isinstance(api_result, dict) else {}
        except ValueError as e:
            raise RuntimeError(f"Invalid JSON returned from {url}: {response.text}") from e

    # Legacy property for backward compatibility
    @property
    def api_client(self):
        """Legacy property that returns self for backward compatibility."""
        return self

    # Search operations - delegate to search service
    def search_concepts(
        self,
        query: str,
        search_type: str = "words",
        source: str | None = None,
        semantic_types: list[str] | None = None,
        page_size: int = 25,
        page_number: int = 1,
        return_id_type: str = "concept",
    ) -> list[UMLSSearchResult]:
        """Search for UMLS concepts."""
        return self.search_service.search_concepts(
            query, search_type, source, semantic_types, page_size, page_number, return_id_type
        )

    def batch_search(self, queries: list[str], **kwargs) -> dict[str, list[UMLSSearchResult]]:
        """Perform batch search for multiple queries."""
        return self.search_service.batch_search(queries, **kwargs)

    def find_similar_concepts(
        self, cui: str, similarity_threshold: float = 0.8
    ) -> list[dict[str, Any]]:
        """Find concepts similar to the given CUI."""
        return self.search_service.find_similar_concepts(cui, similarity_threshold)

    # Concept operations - delegate to concept service
    def get_concept_details(self, cui: str) -> UMLSConcept | None:
        """Get detailed information about a specific concept."""
        return self.concept_service.get_concept_details(cui)

    def get_concept_atoms(self, cui: str, source: str | None = None) -> list[dict[str, Any]]:
        """Get all atoms (terms) for a concept."""
        return self.concept_service.get_concept_atoms(cui, source)

    def get_concept_relationships(
        self, cui: str, include_related: bool = True
    ) -> list[dict[str, Any]]:
        """Get all relationships for a concept."""
        return self.concept_service.get_concept_relationships(cui, include_related)

    def get_concept_hierarchy(self, cui: str, levels: int = 1) -> dict[str, Any]:
        """Get concept hierarchy (parents and children)."""
        return self.concept_service.get_concept_hierarchy(cui, levels)

    def get_cui_from_code(self, code: str, source: str) -> str | None:
        """Get CUI from a source-specific code."""
        return self.concept_service.get_cui_from_code(code, source)

    # Metadata operations - delegate to metadata service
    def get_semantic_types(self) -> list[dict[str, Any]]:
        """Get all available semantic types."""
        return self.metadata_service.get_semantic_types()

    def get_sources(self) -> list[dict[str, Any]]:
        """Get all available source vocabularies."""
        return self.metadata_service.get_sources()

    # Management operations
    def get_statistics(self) -> dict[str, Any]:
        """
        Get client usage statistics.

        Returns:
            Dictionary with usage statistics
        """
        auth_stats = self.authenticator.get_statistics()

        return {
            "total_requests": self.request_count,
            "cache_hits": auth_stats["cache_hits"],
            "cache_misses": auth_stats["cache_misses"],
            "cache_hit_ratio": auth_stats["cache_hits"]
            / max(auth_stats["cache_hits"] + auth_stats["cache_misses"], 1),
            "tgt_expires": (
                datetime.fromtimestamp(self.authenticator.tgt_expires)
                if self.authenticator.tgt_expires
                else None
            ),
            "rate_limit": self.rate_limit,
            "timeout": self.timeout,
        }

    def reset_statistics(self):
        """Reset usage statistics."""
        self.authenticator.reset_statistics()
        self.request_count = 0
        logger.info("Statistics reset")

    def clear_cache(self):
        """Clear authentication cache."""
        self.authenticator.clear_cache()


# Legacy aliases for backward compatibility
UMLSApiClient = OptimizedUMLSClient
UMLSAPIClient = OptimizedUMLSClient  # Also support the old UMLSAPIClient name


def create_umls_client(api_key: str | None = None, **kwargs) -> OptimizedUMLSClient:
    """
    Factory function to create a UMLS client.

    Args:
        api_key: UMLS API key (optional, can be set via environment)
        **kwargs: Additional arguments for OptimizedUMLSClient

    Returns:
        OptimizedUMLSClient instance
    """
    return OptimizedUMLSClient(api_key=api_key, **kwargs)


# Example usage and testing
if __name__ == "__main__":
    # Initialize client
    client = create_umls_client()

    # Example searches
    print("=== UMLS Client Testing ===")

    # Test 1: Basic search
    print("\n1. Basic search for 'diabetes':")
    results = client.search_concepts("diabetes", page_size=3)
    for result in results:
        print(f"  - {result.cui}: {result.name} ({result.source})")

    # Test 2: Get concept details
    if results:
        print(f"\n2. Concept details for {results[0].cui}:")
        concept = client.get_concept_details(results[0].cui)
        if concept:
            print(f"  - Name: {concept.name}")
            print(f"  - Semantic Types: {concept.semantic_types}")
            print(f"  - Definitions: {concept.definitions[:1]}")  # First definition only
            print(f"  - Sources: {concept.sources}")

    # Test 3: Statistics
    print("\n3. Client statistics:")
    stats = client.get_statistics()
    for key, value in stats.items():
        print(f"  - {key}: {value}")

    print("\n=== Testing Complete ===")
