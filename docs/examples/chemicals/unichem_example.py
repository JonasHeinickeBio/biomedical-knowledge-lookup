"""
Example: Using the UniChem Adapter for Biomedical Concept Lookup
"""

from knowledge_lookup import LookupConfig, create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource


async def main():
    # Create lookup instance
    # For adapters requiring API keys, pass the key via api_keys parameter
    lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.UNICHEM])
    
    print(f"Checking if UniChem adapter is available...")
    if lookup:
        print(f"  ✓ UniChem adapter is available")
    else:
        print(f"  ✗ UniChem adapter is not available")
        return
    
    query = "CHEMBL1201"
    print(f"\\nSearching for '{query}' concepts in UniChem...")
    results = await lookup.search_concepts(query, sources=[KnowledgeSource.UNICHEM])
    
    print(f"\\nFound {results.total_found} results from UniChem:")
    for i, concept in enumerate(results.concepts[:5]):
        print(f"\\n  Concept {i+1}:")
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
