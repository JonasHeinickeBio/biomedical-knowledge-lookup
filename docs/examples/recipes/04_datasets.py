import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import GEOAdapter, MetaboLightsAdapter, OmicsDIAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with (
        OmicsDIAdapter(cfg) as omicsdi,
        GEOAdapter(cfg) as geo,
        MetaboLightsAdapter(cfg) as mtbls,
    ):
        for name, adapter in [("OmicsDI", omicsdi), ("GEO", geo), ("MetaboLights", mtbls)]:
            hits = await adapter.search_concepts("chronic fatigue syndrome", limit=3)
            print(f"{name}: {len(hits)} hits")
            for c in hits:
                print(f"   {c.primary_id:<28} {c.primary_label[:70]}")


asyncio.run(main())
