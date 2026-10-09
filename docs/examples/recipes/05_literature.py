import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import OpenAlexAdapter, UnpaywallAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with OpenAlexAdapter(cfg) as openalex, UnpaywallAdapter(cfg) as unpaywall:
        papers = await openalex.search_concepts("long covid post-exertional malaise", limit=4)
        papers = [p for p in papers if p.concept_type == "CITATION"]
        for p in papers:
            print(p.primary_id, p.primary_label[:80])

        doi = next(
            (
                i.identifier.removeprefix("DOI:")
                for p in papers
                for i in p.identifiers or []
                if i.identifier.startswith("DOI:")
            ),
            None,
        )
        print("DOI:", doi)
        if doi:
            oa = await unpaywall.get_concept_details(doi)
            print("open access:", oa.primary_label[:60] if oa else None)
            for e in (await unpaywall.get_relationships(doi))[:3]:
                print("   ", e["relation_label"], e["related_id"])


asyncio.run(main())
