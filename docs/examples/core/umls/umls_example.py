"""
UMLS Adapter Example — All Features

Demonstrates search, filtering, bulk search, mappings, relationships,
and streaming iterators using the UMLS knowledge source.

Prerequisites:
    Set UMLS_API_KEY in your environment or .env file.
"""

import asyncio
import os

from knowledge_lookup import LookupConfig, create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource


async def main():
    # ------------------------------------------------------------------
    # 1. Initialisation
    # ------------------------------------------------------------------
    api_key = os.environ.get("UMLS_API_KEY", "")
    config = LookupConfig(
        api_keys={"umls": api_key},
    )
    lookup = create_knowledge_lookup(
        enabled_sources=[KnowledgeSource.UMLS],
        api_keys=config.api_keys,
    )

    if lookup is None:
        print("✗ UMLS adapter unavailable (check UMLS_API_KEY)")
        return
    print("✓ UMLS adapter initialised\n")

    # Get the adapter directly for advanced features requiring keyword-only params
    adapter = lookup.adapters.get(KnowledgeSource.UMLS)

    # ------------------------------------------------------------------
    # 2. Basic search (via CentralKnowledgeLookup unified API)
    # ------------------------------------------------------------------
    print("═" * 50)
    print("1. BASIC SEARCH  (via CentralKnowledgeLookup)")
    print("═" * 50)
    results = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.UMLS])
    print(f"   Query: 'diabetes' → {len(results.concepts)} results\n")
    for c in results.concepts[:3]:
        print(f"   • {c.primary_id}: {c.primary_label}  [{c.concept_type.value}]")
    print()

    # ------------------------------------------------------------------
    # 3. Source-restricted search (sabs)
    # ------------------------------------------------------------------
    print("═" * 50)
    print("2. SOURCE-RESTRICTED SEARCH  (sabs='SNOMEDCT_US')")
    print("═" * 50)
    if adapter:
        concepts = await adapter.search_concepts(
            "hypertension", limit=5, sabs="SNOMEDCT_US"
        )
        print(f"   Query: 'hypertension' (SNOMEDCT_US only) → {len(concepts)} results\n")
        for c in concepts:
            print(f"   • {c.primary_id}: {c.primary_label}")
    print()

    # ------------------------------------------------------------------
    # 4. Semantic-type filtered search (semantic_types)
    # ------------------------------------------------------------------
    print("═" * 50)
    print("3. SEMANTIC-TYPE FILTER  (semantic_types='T047' = Disease)")
    print("═" * 50)
    if adapter:
        concepts = await adapter.search_concepts(
            "diabetes", limit=3, semantic_types="T047"
        )
        print(f"   Filtered to disease type → {len(concepts)} results\n")
        for c in concepts:
            print(f"   • {c.primary_id}: {c.primary_label}  [{c.concept_type.value}]")
    print()

    # ------------------------------------------------------------------
    # 5. Bulk search
    # ------------------------------------------------------------------
    print("═" * 50)
    print("4. BULK SEARCH")
    print("═" * 50)
    if adapter:
        bulk = await adapter.bulk_search(
            ["metformin", "atorvastatin", "lisinopril"], limit=2
        )
        for query, hits in bulk.items():
            labels = [c.primary_label for c in hits]
            print(f"   '{query}' → {labels}")
    print()

    # ------------------------------------------------------------------
    # 6. Mappings (CUI → source-specific IDs)
    # ------------------------------------------------------------------
    print("═" * 50)
    print("5. MAPPINGS  (CUI → source-specific identifiers)")
    print("═" * 50)
    if adapter:
        mappings = await adapter.get_mappings(
            "C0025598", target_source="RXNORM", limit=5
        )
        print(f"   RXNORM mappings for C0025598 (metformin):\n")
        for m in mappings:
            print(f"   • {m['source']}: {m['source_id']}  —  {m.get('source_name', '')}")
    print()

    # ------------------------------------------------------------------
    # 7. Relationships
    # ------------------------------------------------------------------
    print("═" * 50)
    print("6. RELATIONSHIPS  (parent / child relations)")
    print("═" * 50)
    if adapter:
        rels = await adapter.get_relationships(
            "C0025598", relation_labels="PAR", limit=5
        )
        print(f"   Parent relations for metformin:\n")
        for r in rels:
            print(
                f"   • {r['relation_label']} → "
                f"{r.get('related_name', '?'):40s}  ({r['related_id']})"
            )
    print()

    # ------------------------------------------------------------------
    # 8. Streaming iterators
    # ------------------------------------------------------------------
    print("═" * 50)
    print("7. STREAMING ITERATORS")
    print("═" * 50)
    if adapter:
        def_count = 0
        async for _ in adapter.iter_definitions("C0025598"):
            def_count += 1
        rel_count = 0
        async for _ in adapter.iter_relations("C0025598", page_size=200):
            rel_count += 1
        print(f"   Definitions for metformin: {def_count}")
        print(f"   Relations for metformin:   {rel_count}")
    print()

    # ------------------------------------------------------------------
    # 9. Cleanup
    # ------------------------------------------------------------------
    await lookup.close()
    print("✓ Adapter closed — done.")


if __name__ == "__main__":
    asyncio.run(main())
