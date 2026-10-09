import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

SOURCES = [
    KnowledgeSource.MESH,
    KnowledgeSource.MEDGEN,
    KnowledgeSource.NCIEVS,
    KnowledgeSource.CLINICALTABLES,
    KnowledgeSource.NODENORM,
]


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=SOURCES))
    try:
        # 1. Every source that knows the phrase, merged
        result = await lookup.search_concepts("chronic fatigue syndrome", max_results=10)
        for c in result.concepts:
            print(f"{c.primary_id:<18} {c.primary_label[:48]:<48} {c.sources}")

        if not result.concepts:
            print("no source knew this phrase:", result.errors)
            return

        # 2. Follow the top hit to its cross-references in other vocabularies
        top = result.concepts[0]
        maps = await lookup.find_mappings(top.primary_id)
        print(
            top.primary_id,
            "->",
            len(maps),
            "cross-references, e.g.",
            [m.identifier for m in maps[:6]],
        )
    finally:
        await lookup.close()


asyncio.run(main())
