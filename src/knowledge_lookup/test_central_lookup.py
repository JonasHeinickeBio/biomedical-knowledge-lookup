"""
Comprehensive Test Suite for Central Knowledge Lookup

Tests the unified knowledge lookup system across multiple sources.
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# Import the knowledge lookup system
from aid_pais_knowledgegraph.knowledge_lookup import (
    CentralKnowledgeLookup,
    create_knowledge_lookup,
    KnowledgeSource,
    ConceptType,
    LookupConfig
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_search():
    """Test basic concept search across sources."""
    print("\n=== Testing Basic Concept Search ===")
    
    # Create lookup instance with minimal config
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.OLS, KnowledgeSource.WIKIDATA],  # Start with public APIs
        max_results_per_source=5,
        timeout_per_source=15.0
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    try:
        # Test search for a medical term
        result = await lookup.search_concepts("diabetes", max_results=10)
        
        print(f"Query: '{result.query}'")
        print(f"Total concepts found: {result.total_found}")
        print(f"Sources queried: {[s.value for s in result.sources_queried]}")
        print(f"Sources succeeded: {[s.value for s in result.sources_succeeded]}")
        print(f"Sources failed: {[s.value for s in result.sources_failed]}")
        print(f"Execution time: {result.execution_time:.2f}s")
        
        if result.errors:
            print("Errors:")
            for source, error in result.errors.items():
                print(f"  {source.value}: {error}")
        
        print("\nTop 3 concepts:")
        for i, concept in enumerate(result.concepts[:3], 1):
            print(f"{i}. {concept.primary_label} ({concept.primary_id})")
            print(f"   Type: {concept.concept_type.value}")
            print(f"   Sources: {[s.value for s in concept.sources]}")
            print(f"   Confidence: {concept.confidence_score:.2f}")
            if concept.definitions:
                definition = concept.definitions[0][:100] + "..." if len(concept.definitions[0]) > 100 else concept.definitions[0]
                print(f"   Definition: {definition}")
        
        return len(result.concepts) > 0
        
    except Exception as e:
        print(f"❌ Basic search test failed: {e}")
        return False
    finally:
        await lookup.close()


async def test_umls_integration():
    """Test UMLS integration if available."""
    print("\n=== Testing UMLS Integration ===")
    
    # Check if UMLS API key is available
    umls_key = os.getenv("UMLS_API_KEY_TU")
    if not umls_key:
        print("⏭️  UMLS API key not available, skipping UMLS test")
        return True
    
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.UMLS],
        api_keys={"umls": umls_key},
        max_results_per_source=5
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    try:
        # Test UMLS search
        result = await lookup.search_concepts("hypertension", max_results=5)
        
        print(f"UMLS search results: {result.total_found} concepts")
        
        if result.concepts:
            concept = result.concepts[0]
            print(f"Top result: {concept.primary_label} ({concept.primary_id})")
            print(f"Semantic types: {concept.semantic_types}")
            print(f"Sources: {concept.categories}")
            
            # Test concept details
            detailed_concept = await lookup.get_concept_details(concept.primary_id, KnowledgeSource.UMLS)
            if detailed_concept:
                print(f"Detailed concept has {len(detailed_concept.synonyms)} synonyms")
                print(f"Detailed concept has {len(detailed_concept.definitions)} definitions")
        
        return result.total_found > 0
        
    except Exception as e:
        print(f"❌ UMLS integration test failed: {e}")
        return False
    finally:
        await lookup.close()


async def test_concept_types_filtering():
    """Test filtering by concept types."""
    print("\n=== Testing Concept Type Filtering ===")
    
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.OLS, KnowledgeSource.WIKIDATA],
        max_results_per_source=10
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    try:
        # Search for diseases specifically
        result = await lookup.search_concepts(
            "cancer", 
            concept_types=[ConceptType.DISEASE],
            max_results=5
        )
        
        print(f"Disease search results: {result.total_found} concepts")
        
        # Check that all results are diseases (or unknown)
        disease_count = 0
        for concept in result.concepts:
            if concept.concept_type in [ConceptType.DISEASE, ConceptType.UNKNOWN]:
                disease_count += 1
            print(f"- {concept.primary_label}: {concept.concept_type.value}")
        
        success = disease_count == len(result.concepts)
        print(f"✅ Type filtering {'worked' if success else 'failed'}")
        return success
        
    except Exception as e:
        print(f"❌ Concept type filtering test failed: {e}")
        return False
    finally:
        await lookup.close()


async def test_cross_source_integration():
    """Test integration and deduplication across sources."""
    print("\n=== Testing Cross-Source Integration ===")
    
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.OLS, KnowledgeSource.WIKIDATA],
        enable_deduplication=True,
        max_results_per_source=10
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    try:
        # Search for a term that might appear in multiple sources
        result = await lookup.search_concepts("heart", max_results=10)
        
        print(f"Cross-source search results: {result.total_found} concepts")
        
        # Group by source
        source_groups = result.group_by_source()
        for source, concepts in source_groups.items():
            print(f"{source.value}: {len(concepts)} concepts")
        
        # Check for concepts that appear in multiple sources
        multi_source_concepts = 0
        for concept in result.concepts:
            if len(concept.sources) > 1:
                multi_source_concepts += 1
                print(f"Multi-source concept: {concept.primary_label} from {[s.value for s in concept.sources]}")
        
        print(f"Found {multi_source_concepts} concepts from multiple sources")
        return len(result.concepts) > 0
        
    except Exception as e:
        print(f"❌ Cross-source integration test failed: {e}")
        return False
    finally:
        await lookup.close()


async def test_concept_hierarchy():
    """Test concept hierarchy retrieval."""
    print("\n=== Testing Concept Hierarchy ===")
    
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.OLS],
        max_results_per_source=5
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    try:
        # First find a concept
        result = await lookup.search_concepts("pneumonia", max_results=3)
        
        if result.concepts:
            concept = result.concepts[0]
            print(f"Testing hierarchy for: {concept.primary_label}")
            
            # Get hierarchy
            hierarchy = await lookup.get_concept_hierarchy(concept.primary_id)
            
            print(f"Parents: {len(hierarchy['parents'])}")
            print(f"Children: {len(hierarchy['children'])}")
            
            for parent in hierarchy['parents'][:2]:
                print(f"  Parent: {parent.primary_label}")
            
            for child in hierarchy['children'][:2]:
                print(f"  Child: {child.primary_label}")
            
            return True
        else:
            print("No concepts found for hierarchy test")
            return False
        
    except Exception as e:
        print(f"❌ Concept hierarchy test failed: {e}")
        return False
    finally:
        await lookup.close()


async def test_statistics():
    """Test system statistics."""
    print("\n=== Testing System Statistics ===")
    
    lookup = create_knowledge_lookup()
    
    try:
        stats = await lookup.get_statistics()
        
        print("System Statistics:")
        print(f"Available sources: {len(stats['available_sources'])}")
        print(f"Total sources: {stats['total_sources']}")
        print(f"Enabled sources: {stats['enabled_sources']}")
        
        print("\nConfiguration:")
        for key, value in stats['config'].items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Statistics test failed: {e}")
        return False
    finally:
        await lookup.close()


async def run_all_tests():
    """Run all test cases."""
    print("🧪 Central Knowledge Lookup Test Suite")
    print("=" * 50)
    
    tests = [
        ("Basic Search", test_basic_search),
        ("UMLS Integration", test_umls_integration),
        ("Concept Type Filtering", test_concept_types_filtering),
        ("Cross-Source Integration", test_cross_source_integration),
        ("Concept Hierarchy", test_concept_hierarchy),
        ("System Statistics", test_statistics),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {test_name}")
        except Exception as e:
            print(f"💥 CRASHED: {test_name} - {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print(f"{'='*50}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Central knowledge lookup system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
