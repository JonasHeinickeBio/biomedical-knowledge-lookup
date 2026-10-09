import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import OpenFDAEventsAdapter, RxClassAdapter, RxNormAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with (
        RxNormAdapter(cfg) as rxnorm,
        RxClassAdapter(cfg) as rxclass,
        OpenFDAEventsAdapter(cfg) as faers,
    ):
        found = await rxnorm.search_concepts("naltrexone", limit=1)
        if not found:
            print("RxNorm does not know this drug")
            return
        drug = found[0]
        print("RxNorm  ", drug.primary_id, drug.primary_label)

        for m in (await rxclass.get_mappings(drug.primary_id))[:4]:
            print("RxClass ", m["toSource"], m["toId"])

        reports = await faers.search_concepts("naltrexone", limit=1)
        if not reports:
            print("no FAERS reports found")
            return
        hit = reports[0]
        print("FAERS   ", hit.primary_id)
        for e in (await faers.get_relationships(hit.primary_id))[:5]:
            print(
                f"    {e['related_name']:<26} {e['report_count']:>6} of {e['total_reports']} reports"
            )


asyncio.run(main())
