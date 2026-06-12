"""
Example: Using the OMIM Adapter for Biomedical Concept Lookup
"""

from knowledge_lookup import LookupConfig, create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource


async def main():
    # Note: OMIM adapter may require an API key
    # Set OMIM_API_KEY environment variable
    # os.environ['OMIM_API_KEY'] = 'your_api_key_here'
    
    # Create lookup instance
    # For adapters requiring API keys, pass the key via api_keys parameter
    lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.OMIM])
    
    print(f"Checking if OMIM adapter is available...")
    if lookup:
        print(f"  ✓ OMIM adapter is available")
    else:
        print(f"  ✗ OMIM adapter is not available")
        return
    
    query = "143100"
    print(f"
Searching for '{query}' concepts in OMIM...")
    results = await lookup.search_concepts(query, sources=[KnowledgeSource.OMIM])
    
    print(f"
Found {results.total_found} results from OMIM:")
    for i, concept in enumerate(results.concepts[:5]):
        print(f"
  Concept {i+1}:")
        print(f"    Label: {concept.primary_label}")
        print(f"    ID: {concept.primary_id}")
        print(f"    Type: {concept.concept_type}")
        print(f"    Confidence: {concept.confidence_score}")
        
        if concept.definitions:
            print(f"    Definitions ({len(concept.definitions)}):")
            for definition in concept.definitions[:2]:
                print(f"      - {definition}")
        
        if concept.mappings:
            print(f"    Mappings ({len(concept.mappings)}):")
            for mapping in concept.mappings[:3]:
                print(f"      - {mapping.source_id}: {mapping.source_label}")
    
    if not results.concepts:
        print("  No results found for '{query}'")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
