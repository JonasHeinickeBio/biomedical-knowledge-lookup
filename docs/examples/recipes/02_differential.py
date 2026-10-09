import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import MonarchAdapter


async def main() -> None:
    async with MonarchAdapter(LookupConfig()) as monarch:
        for term in ["postural orthostatic tachycardia syndrome", "fibromyalgia"]:
            hits = await monarch.search_concepts(term, limit=1)
            if not hits:
                print(term, "-> no hit")
                continue
            d = hits[0]
            edges = await monarch.get_relationships(d.primary_id)
            kinds = sorted({e["relation_label"] for e in edges})
            print(f"{term}: {d.primary_id} {d.primary_label}  ({len(edges)} edges: {kinds})")
            for e in edges[:3]:
                print("   ", e["relation_label"], e["related_id"], e["related_name"])


asyncio.run(main())
