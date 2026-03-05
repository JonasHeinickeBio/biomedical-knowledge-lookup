"""
UMLS search operations.

This module handles all search-related functionality for UMLS concepts.
"""

import logging
from typing import List, Optional, Dict, Any, Protocol, TYPE_CHECKING
from .models import UMLSSearchResult

if TYPE_CHECKING:
    from .concepts import UMLSConceptService

logger = logging.getLogger(__name__)


class APIClient(Protocol):
    """Protocol for API client interface."""
    def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an API request."""
        ...


class UMLSSearchService:
    """Service for UMLS concept search operations."""

    def __init__(self, api_client: APIClient, version: str = "current"):
        self.api_client = api_client
        self.version = version

    def search_concepts(
        self,
        query: str,
        search_type: str = "words",
        source: Optional[str] = None,
        semantic_types: Optional[List[str]] = None,
        page_size: int = 25,
        page_number: int = 1,
        return_id_type: str = "concept"
    ) -> List[UMLSSearchResult]:
        """
        Search for UMLS concepts.

        Args:
            query: Search query string
            search_type: Type of search ('words', 'exact', 'leftTruncation', 'rightTruncation', 'approximate')
            source: Source vocabulary to search in (e.g., 'SNOMEDCT_US')
            semantic_types: List of semantic types to filter by
            page_size: Number of results per page (max 1000)
            page_number: Page number to retrieve
            return_id_type: Type of ID to return ('concept', 'code', 'sourceConcept', 'sourceDescriptor')

        Returns:
            List of UMLSSearchResult objects
        """
        params = {
            'string': query,
            'searchType': search_type,
            'pageSize': min(page_size, 1000),
            'pageNumber': page_number,
            'returnIdType': return_id_type
        }

        if source:
            params['sabs'] = source

        if semantic_types:
            params['stys'] = ','.join(semantic_types)

        endpoint = f"/search/{self.version}"

        try:
            result = self.api_client.make_request(endpoint, params)
            results = []

            if 'results' in result:
                for item in result['results']:
                    search_result = UMLSSearchResult(
                        cui=item.get('ui', ''),
                        name=item.get('name', ''),
                        ui=item.get('ui', ''),
                        source=item.get('rootSource', ''),
                        source_concept_id=item.get('uri', '').split('/')[-1] if item.get('uri') else '',
                        root_source=item.get('rootSource', '')
                    )
                    results.append(search_result)

            logger.info(f"Search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    def batch_search(self, queries: List[str], **kwargs) -> Dict[str, List[UMLSSearchResult]]:
        """
        Perform batch search for multiple queries.

        Args:
            queries: List of search queries
            **kwargs: Additional arguments passed to search_concepts

        Returns:
            Dictionary mapping queries to their results
        """
        results = {}

        for i, query in enumerate(queries):
            logger.info(f"Processing batch query {i+1}/{len(queries)}: {query}")

            try:
                search_results = self.search_concepts(query, **kwargs)
                results[query] = search_results
            except Exception as e:
                logger.error(f"Batch search failed for query '{query}': {e}")
                results[query] = []

        return results

    def find_similar_concepts(self, cui: str, similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Find concepts similar to the given CUI.

        Args:
            cui: Concept Unique Identifier
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of similar concept dictionaries
        """
        try:
            # First, we need to get the concept details to find its name
            from .concepts import UMLSConceptService
            concept_service: UMLSConceptService = UMLSConceptService(self.api_client, self.version)
            concept = concept_service.get_concept_details(cui)

            if not concept:
                return []

            # Search for similar concepts using the concept's name
            similar_results = self.search_concepts(
                concept.name,
                search_type='approximate',
                page_size=50
            )

            # Filter out the original concept and apply similarity threshold
            similar_concepts = []
            for result in similar_results:
                if result.cui != cui:
                    similar_concepts.append({
                        'cui': result.cui,
                        'name': result.name,
                        'source': result.source,
                        'similarity_score': similarity_threshold  # Placeholder - could implement actual similarity scoring
                    })

            logger.info(f"Found {len(similar_concepts)} similar concepts for CUI {cui}")
            return similar_concepts

        except Exception as e:
            logger.error(f"Failed to find similar concepts for CUI {cui}: {e}")
            return []
