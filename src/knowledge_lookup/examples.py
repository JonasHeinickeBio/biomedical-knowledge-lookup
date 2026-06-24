#!/usr/bin/env python3
"""
Central Knowledge Lookup Examples

Demonstrates how to use the unified knowledge lookup system for biological concepts.
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from knowledge_lookup import (  # noqa: E402
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    create_knowledge_lookup,
)

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


async def example_basic_search():
    """Example 1: Basic concept search across multiple sources."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Concept Search")
    print("=" * 60)

    # Create a lookup instance with default configuration
    lookup = create_knowledge_lookup()

    try:
        # Search for a medical concept
        query = "diabetes mellitus"
        print(f"Searching for: '{query}'")

        result = await lookup.search_concepts(query, max_results=10)

        print(
            f"\nResults: {result.total_found or 0} concepts found in {result.execution_time or 0:.2f}s"
        )
        print(f"Sources queried: {[str(s) for s in (result.sources_queried or [])]}")
        print(f"Sources succeeded: {[str(s) for s in (result.sources_succeeded or [])]}")

        if result.errors:
            print(f"Sources with errors: {list(result.errors.keys())}")

        print("\nTop 5 results:")
        for i, concept in enumerate(result.concepts[:5], 1):
            print(f"\n{i}. {concept.primary_label}")
            print(f"   ID: {concept.primary_id}")
            print(f"   Type: {concept.concept_type}")
            print(f"   Sources: {[str(s) for s in concept.sources]}")
            print(f"   Confidence: {concept.confidence_score:.2f}")

            if concept.definitions:
                definition = concept.definitions[0]
                if len(definition) > 150:
                    definition = definition[:150] + "..."
                print(f"   Definition: {definition}")

            if concept.synonyms:
                synonyms = ", ".join(concept.synonyms[:3])
                print(f"   Synonyms: {synonyms}")

    finally:
        await lookup.close()


async def example_specific_sources():
    """Example 2: Search specific knowledge sources."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Search Specific Sources")
    print("=" * 60)

    # Configure to use only public sources (no API keys required)
    LookupConfig(
        enabled_sources=[KnowledgeSource.OLS, KnowledgeSource.WIKIDATA], max_results_per_source=5
    )

    lookup = create_knowledge_lookup(
        enabled_sources=[KnowledgeSource.OLS, KnowledgeSource.WIKIDATA]
    )

    try:
        query = "hypertension"
        print(f"Searching '{query}' in OLS and Wikidata only...")

        result = await lookup.search_concepts(
            query, sources=[KnowledgeSource.OLS, KnowledgeSource.WIKIDATA], max_results=8
        )

        print(f"\nFound {result.total_found} concepts")

        # Group results by source
        by_source = result.group_by_source()
        for source, concepts in by_source.items():
            print(f"\n{source} ({len(concepts)} concepts):")
            for concept in concepts[:3]:
                print(f"  - {concept.primary_label} ({concept.primary_id})")

    finally:
        await lookup.close()


async def example_concept_types():
    """Example 3: Filter by concept types."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Filter by Concept Types")
    print("=" * 60)

    lookup = create_knowledge_lookup()

    try:
        query = "aspirin"

        # Search for drugs only
        print(f"Searching for drugs matching '{query}':")
        drug_result = await lookup.search_concepts(
            query, concept_types=[ConceptType.DRUG, ConceptType.CHEMICAL], max_results=5
        )

        print(f"Found {drug_result.total_found} drug/chemical concepts:")
        for concept in drug_result.concepts:
            print(f"  - {concept.primary_label} ({concept.concept_type or 'UNKNOWN'})")

        # Search for diseases
        print("\nSearching for diseases matching 'cancer':")
        disease_result = await lookup.search_concepts(
            "cancer", concept_types=[ConceptType.DISEASE], max_results=5
        )

        print(f"Found {disease_result.total_found} disease concepts:")
        for concept in disease_result.concepts:
            print(f"  - {concept.primary_label} ({concept.concept_type or 'UNKNOWN'})")

    finally:
        await lookup.close()


async def example_concept_details():
    """Example 4: Get detailed concept information."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Get Detailed Concept Information")
    print("=" * 60)

    lookup = create_knowledge_lookup()

    try:
        # First, find a concept
        search_result = await lookup.search_concepts("pneumonia", max_results=3)

        if search_result.concepts:
            concept = search_result.concepts[0]
            print(f"Getting details for: {concept.primary_label}")
            print(f"Primary ID: {concept.primary_id}")

            # Get detailed information
            detailed = await lookup.get_concept_details(concept.primary_id)

            if detailed:
                print("\nDetailed Information:")
                print(f"Label: {detailed.primary_label}")
                print(f"Type: {detailed.concept_type or 'UNKNOWN'}")
                print(f"Sources: {[str(s) for s in detailed.sources]}")

                if detailed.definitions:
                    print(f"\nDefinitions ({len(detailed.definitions)}):")
                    for i, definition in enumerate(detailed.definitions[:2], 1):
                        if len(definition) > 200:
                            definition = definition[:200] + "..."
                        print(f"  {i}. {definition}")

                if detailed.synonyms:
                    print(f"\nSynonyms ({len(detailed.synonyms)}):")
                    print(f"  {', '.join(detailed.synonyms[:10])}")

                if detailed.semantic_types:
                    print(f"\nSemantic Types: {', '.join(detailed.semantic_types[:5])}")

                if detailed.categories:
                    print(f"Categories: {', '.join(detailed.categories[:5])}")
        else:
            print("No concepts found for detailed lookup")

    finally:
        await lookup.close()


async def example_umls_integration():
    """Example 5: UMLS integration (requires API key)."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: UMLS Integration")
    print("=" * 60)

    # Check if UMLS API key is available
    umls_key = os.getenv("UMLS_API_KEY_TU")
    if not umls_key:
        print("⏭️  UMLS API key not found in environment.")
        print("   Set UMLS_API_KEY_TU to enable UMLS integration.")
        return

    # Create lookup with UMLS enabled
    lookup = create_knowledge_lookup(
        api_keys={"umls": umls_key}, enabled_sources=[KnowledgeSource.UMLS]
    )

    try:
        query = "myocardial infarction"
        print(f"Searching UMLS for '{query}'...")

        result = await lookup.search_concepts(query, max_results=5)

        print(f"Found {result.total_found} UMLS concepts:")

        for concept in result.concepts:
            print(f"\n- {concept.primary_label} ({concept.primary_id})")
            print(f"  Semantic Types: {', '.join(concept.semantic_types[:3])}")
            print(f"  Sources: {', '.join(concept.categories[:3])}")

            if concept.definitions:
                definition = concept.definitions[0]
                if len(definition) > 150:
                    definition = definition[:150] + "..."
                print(f"  Definition: {definition}")

    finally:
        await lookup.close()


async def example_cross_reference_mapping():
    """Example 6: Find cross-references and mappings."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Cross-Reference Mapping")
    print("=" * 60)

    lookup = create_knowledge_lookup()

    try:
        # Find a concept first
        result = await lookup.search_concepts("insulin", max_results=3)

        if result.concepts:
            concept = result.concepts[0]
            print(f"Finding mappings for: {concept.primary_label}")
            print(f"Primary source: {list(concept.sources)[0]}")

            # Get mappings to other sources
            mappings = await lookup.find_mappings(concept.primary_id)

            print(f"\nFound {len(mappings)} cross-references:")
            for mapping in mappings:
                print(f"  {mapping.source}: {mapping.identifier}")
                if mapping.label and mapping.label != concept.primary_label:
                    print(f"    Label: {mapping.label}")
                if mapping.url:
                    print(f"    URL: {mapping.url}")
        else:
            print("No concepts found for mapping example")

    finally:
        await lookup.close()


async def example_concept_hierarchy():
    """Example 7: Explore concept hierarchies."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Concept Hierarchy")
    print("=" * 60)

    lookup = create_knowledge_lookup()

    try:
        # Find a concept with hierarchical relationships
        result = await lookup.search_concepts("bacterial pneumonia", max_results=3)

        if result.concepts:
            concept = result.concepts[0]
            print(f"Exploring hierarchy for: {concept.primary_label}")

            # Get hierarchical relationships
            hierarchy = await lookup.get_concept_hierarchy(concept.primary_id)

            print(f"\nParent concepts ({len(hierarchy['parents'])}):")
            for parent in hierarchy["parents"][:5]:
                print(f"  ↑ {parent.primary_label}")

            print(f"\nChild concepts ({len(hierarchy['children'])}):")
            for child in hierarchy["children"][:5]:
                print(f"  ↓ {child.primary_label}")

            if not hierarchy["parents"] and not hierarchy["children"]:
                print("  No hierarchical relationships found in available sources")
        else:
            print("No concepts found for hierarchy example")

    finally:
        await lookup.close()


async def example_similar_concepts():
    """Example 8: Find similar concepts."""
    print("\n" + "=" * 60)
    print("EXAMPLE 8: Find Similar Concepts")
    print("=" * 60)

    lookup = create_knowledge_lookup()

    try:
        # Find a concept first
        result = await lookup.search_concepts("heart failure", max_results=1)

        if result.concepts:
            concept = result.concepts[0]
            print(f"Finding concepts similar to: {concept.primary_label}")

            # Find similar concepts
            similar = await lookup.suggest_similar_concepts(
                concept.primary_id, similarity_threshold=0.6
            )

            print(f"\nFound {len(similar)} similar concepts:")
            for similar_concept in similar[:8]:
                print(f"  - {similar_concept.primary_label}")
                print(f"    ID: {similar_concept.primary_id}")
                print(f"    Confidence: {similar_concept.confidence_score:.2f}")
                print(f"    Sources: {[str(s) for s in similar_concept.sources]}")
                print()
        else:
            print("No concepts found for similarity example")

    finally:
        await lookup.close()


async def main():
    """Run all examples."""
    print("🔍 Central Knowledge Lookup System - Examples")
    print("=" * 60)
    print("This demonstrates querying multiple biological knowledge sources")
    print("through a unified interface.")
    print()

    examples = [
        example_basic_search,
        example_specific_sources,
        example_concept_types,
        example_concept_details,
        example_umls_integration,
        example_cross_reference_mapping,
        example_concept_hierarchy,
        example_similar_concepts,
    ]

    for example_func in examples:
        try:
            await example_func()
        except KeyboardInterrupt:
            print("\n⏹️  Stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Example failed: {e}")
            logger.exception("Example error")

        # Small delay between examples
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("🎯 Examples completed!")
    print("=" * 60)
    print("\nKey features demonstrated:")
    print("✅ Multi-source concept search")
    print("✅ Source-specific queries")
    print("✅ Concept type filtering")
    print("✅ Detailed concept information")
    print("✅ UMLS integration")
    print("✅ Cross-reference mapping")
    print("✅ Hierarchical relationships")
    print("✅ Similar concept discovery")
    print("\nThe central lookup system provides unified access to:")
    print("• UMLS (Unified Medical Language System)")
    print("• OLS (Ontology Lookup Service)")
    print("• BioPortal (NCBI BioPortal)")
    print("• Wikidata")
    print("• DBpedia")
    print("• And more biological knowledge sources")


if __name__ == "__main__":
    asyncio.run(main())
