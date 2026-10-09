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

        # 2. Follow one hit to its cross-references in other vocabularies
        maps = await lookup.find_mappings("MONDO:0005404")
        print(len(maps), "cross-references, e.g.", [m.identifier for m in maps[:6]])
    finally:
        await lookup.close()


asyncio.run(main())
