import asyncio

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import CellOntologyAdapter, CellxGeneAdapter


async def main() -> None:
    cfg = LookupConfig()
    async with CellOntologyAdapter(cfg) as cl, CellxGeneAdapter(cfg) as cxg:
        found = await cl.search_concepts("natural killer cell", limit=1)
        if not found:
            print("Cell Ontology returned nothing")
            return
        nk = found[0]
        print(nk.primary_id, nk.primary_label)
        for e in (await cl.get_relationships(nk.primary_id))[:5]:
            print("  ", e["relation_label"], e["related_id"], e["related_name"])
        for e in (await cxg.get_relationships(nk.primary_id))[:3]:
            print("CELLxGENE", e["relation_label"], e["related_id"], e["related_name"])


asyncio.run(main())
