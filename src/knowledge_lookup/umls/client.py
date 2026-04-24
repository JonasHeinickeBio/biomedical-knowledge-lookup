"""
UMLS Client - Main Entry Point

This module provides backward compatibility and exports the main UMLS client functionality.
The actual implementation has been unified into a single optimized client for better performance
and maintainability.
"""

# Import all public components from the unified implementation
from .auth import UMLSAuthenticator
from .concepts import UMLSConceptService
from .main_client import (
    OptimizedUMLSClient,
    UMLSAPIClient,  # Also legacy alias
    UMLSApiClient,  # Legacy alias
    create_umls_client,
)
from .metadata import UMLSMetadataService
from .models import UMLSConcept, UMLSSearchResult
from .search import UMLSSearchService

# Export all public interfaces
__all__ = [
    "OptimizedUMLSClient",
    "UMLSApiClient",
    "UMLSAPIClient",
    "create_umls_client",
    "UMLSConcept",
    "UMLSSearchResult",
    "UMLSAuthenticator",
    "UMLSSearchService",
    "UMLSConceptService",
    "UMLSMetadataService",
]

# Maintain backward compatibility by providing the main functionality
# through the original client.py entry point
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
