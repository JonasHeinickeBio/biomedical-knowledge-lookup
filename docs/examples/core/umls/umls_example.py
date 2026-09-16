"""
UMLS example: every UMLS adapter feature.

Covers the unified search, concept details, and the UMLS-specific adapter
methods: source-restricted and semantic-type filtered search, bulk search,
mappings to source vocabularies, relationships, and streaming iterators.

Requirements: the [umls] extra and the UMLS_API_KEY environment variable
(a .env file in the working directory or a parent directory also works).

Run from the repository root:

    python docs/examples/core/umls/umls_example.py

Hand-written; docs/examples/scripts/generate_all_examples.py does not overwrite it.
"""

import asyncio
import logging

from knowledge_lookup import KnowledgeSource, create_knowledge_lookup

SOURCE = KnowledgeSource.UMLS
METFORMIN = "C0025598"


def heading(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


async def main() -> None:
    # The key is read from UMLS_API_KEY. To pass it explicitly instead, use
    # create_knowledge_lookup(enabled_sources=[SOURCE], api_keys={"umls": "<key>"}).
    lookup = create_knowledge_lookup(enabled_sources=[SOURCE])
    try:
        adapter = lookup.adapters.get(SOURCE)
        if adapter is None:
            print("SKIPPED: the UMLS adapter is not available.")
            print("It needs the [umls] extra and the UMLS_API_KEY environment variable.")
            print("\nSummary: skipped")
            return
        print("The UMLS adapter is available.")

        heading("1. Search through CentralKnowledgeLookup")
        result = await lookup.search_concepts("diabetes", sources=[SOURCE], max_results=5)
        print(f"'diabetes' -> {result.total_found} concept(s)")
        for concept in result.concepts[:3]:
            print(f"  {concept.primary_id}: {concept.primary_label} [{concept.concept_type}]")

        heading("2. Concept details")
        details = await lookup.get_concept_details("C0011849", source=SOURCE)
        if details is None:
            print("C0011849 not found")
        else:
            print(f"{details.primary_id}: {details.primary_label} [{details.concept_type}]")
            print(f"  {len(details.synonyms)} synonyms, {len(details.definitions)} definitions")
            print(f"  Semantic types: {', '.join(details.semantic_types[:3])}")

        # The remaining features are UMLS-specific keyword arguments and methods,
        # so they are called on the adapter itself.
        heading("3. Source-restricted search (sabs='SNOMEDCT_US')")
        concepts = await adapter.search_concepts("hypertension", limit=5, sabs="SNOMEDCT_US")
        for concept in concepts:
            print(f"  {concept.primary_id}: {concept.primary_label}")

        heading("4. Semantic-type filter (semantic_types='T047', Disease or Syndrome)")
        concepts = await adapter.search_concepts("diabetes", limit=3, semantic_types="T047")
        for concept in concepts:
            print(f"  {concept.primary_id}: {concept.primary_label} [{concept.concept_type}]")

        heading("5. Bulk search")
        bulk = await adapter.bulk_search(["metformin", "atorvastatin", "lisinopril"], limit=2)
        for query, hits in bulk.items():
            print(f"  {query!r} -> {[concept.primary_label for concept in hits]}")

        heading(f"6. Mappings: {METFORMIN} (metformin) -> RXNORM")
        mappings = await adapter.get_mappings(METFORMIN, target_source="RXNORM", limit=5)
        for mapping in mappings:
            print(f"  {mapping['source']}: {mapping['source_id']} - {mapping['source_name']}")

        heading("7. Parent relationships of metformin")
        relations = await adapter.get_relationships(METFORMIN, relation_labels="PAR", limit=5)
        for relation in relations:
            print(
                f"  {relation['relation_label']} -> "
                f"{relation['related_name'] or '?'} ({relation['related_id']})"
            )

        heading("8. Streaming iterators")
        definition_count = 0
        async for _definition in adapter.iter_definitions(METFORMIN):
            definition_count += 1
        relation_count = 0
        async for _relation in adapter.iter_relations(METFORMIN, page_size=200):
            relation_count += 1
        print(f"  Metformin definitions: {definition_count}")
        print(f"  Metformin relations:   {relation_count}")

        found = "found" if details else "not found"
        print(f"\nSummary: search={result.total_found} details={found}")
    finally:
        await lookup.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main())
    except Exception as exc:  # show a readable message instead of a traceback
        raise SystemExit(f"ERROR: {type(exc).__name__}: {exc}") from None
