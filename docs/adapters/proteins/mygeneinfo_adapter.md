---
description: MyGene.info gene annotation with Entrez, Ensembl, HGNC, UniProt and OMIM cross-references, pathways and orthologs.
---

# MyGene.info adapter

Looks up human genes in MyGene.info (BioThings v3). One record per NCBI (Entrez) gene bundles the symbol, name, aliases, summary and the identifiers other databases use for it, so this adapter is the cheapest hub for linking gene identifiers. It also lists pathway memberships and HomoloGene orthologs.

| | |
|---|---|
| Source | `KnowledgeSource.MYGENEINFO` |
| Class | `knowledge_lookup.adapters.MyGeneInfoAdapter` |
| Requires | none |
| Identifiers | `NCBIGene:672` (primary), bare Entrez `672`, `ENSG00000012048`, `HGNC:1100`, UniProt `P38398`, symbol/alias `BRCA1` |
| Upstream API | `https://mygene.info/v3` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MyGeneInfoAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MyGeneInfoAdapter(LookupConfig()) as adapter:
        il6 = await adapter.get_concept_details("IL6")
        print(il6.primary_id, il6.primary_label, il6.synonyms[:3])
        print([(i.source, i.identifier) for i in il6.identifiers])

        for m in (await adapter.get_mappings("NCBIGene:3569"))[:3]:
            print(m["toSource"], m["toId"], m["mappingType"])

        rels = await adapter.get_relationships("NCBIGene:3569", limit=3)
        print([(r["relation_label"], r["related_id"], r["pathway_db"]) for r in rels])


asyncio.run(main())
```

Output (live, 2026-10):

```
NCBIGene:3569 IL6 ['interleukin 6', 'BSF-2', 'BSF2']
[('MYGENEINFO', 'NCBIGene:3569'), ('NCBI', '3569'), ('ENSEMBL', 'ENSG00000136244'), ('HGNC', 'HGNC:6018'), ('UNIPROT', 'P05231'), ('OMIM', '147620')]
Ensembl ENSG00000136244 exact
HGNC HGNC:6018 exact
UniProt P05231 exact
(first three participates_in edges: pathway id and database name)
```

## Identifiers

`primary_id` is the NCBI Gene id as a CURIE (`NCBIGene:<entrez>`), because MyGene.info's own `_id` is the Entrez number and the id then round-trips with no lookup. Inputs are resolved as follows:

| Input | How |
|---|---|
| `672`, `NCBIGene:672`, `ENTREZ:672` | `GET /gene/672` |
| `ENSG00000012048` (version suffix ignored) | `GET /gene/ENSG...` (accepted directly by `/gene`) |
| `HGNC:1100` | `/query?q=HGNC:1100` |
| `P38398` | `/query?q=uniprot:P38398` |
| `BRCA1`, `il6`, alias | `/query?q=symbol:"X" OR alias:"X"`; an exact symbol match wins over alias hits |

Queries are restricted to `species=human`; pass `MyGeneInfoAdapter(config, species="mouse")` (or `"all"`) for other organisms.

## Searching

`search_concepts(query, limit)` resolves identifier-shaped queries exactly and sends everything else as a MyGene.info free-text query, which ranks exact symbol hits first (`BRCA1` returns BRCA1, then BRAP). Free text also matches gene summaries, so a phenotype such as `fatigue` returns loosely related genes (SLCO1C1, DMGDH, ...); use it for gene names, not for diseases.

## Concept details

| Field | Value |
|---|---|
| `primary_label` | gene symbol |
| `synonyms` | full name, aliases, other names |
| `definitions` | NCBI RefSeq summary |
| `categories` | `locus:17q21.31`, `taxon:9606` |
| `semantic_types` | `type_of_gene` (e.g. `protein-coding`) |
| `identifiers` | `MYGENEINFO`, `NCBI`, `ENSEMBL` (all loci), `HGNC`, `UNIPROT` (Swiss-Prot), `OMIM` |
| `concept_type` | `GENE`, `confidence_score` `0.9` (search) / `1.0` (details) |
| `source_data[MYGENEINFO]` | raw record |

## Mappings

`get_mappings` returns one entry per cross-reference (`fromSource` `MyGeneInfo`, `fromId` the `NCBIGene:` CURIE):

| `toSource` | `toId` | `mappingType` |
|---|---|---|
| `Ensembl` | `ENSG...` (every locus) | `exact` |
| `HGNC` | `HGNC:1100` | `exact` |
| `UniProt` | Swiss-Prot accession | `exact` |
| `UniProt` | up to 10 TrEMBL accessions | `related` |
| `OMIM` | `OMIM:113705` | `exact` |
| `PharmGKB` | `PA25411` | `exact` |
| `PDB` | up to 10 structure ids | `related` |

## Relationships

`get_relationships(concept_id, limit=50)`:

- `participates_in`: one edge per pathway (`related_id` the pathway id, `related_name` its name, `pathway_db` the database, plus `url` where one is known). Databases, in output order: Reactome, WikiPathways, KEGG, BioCarta, PID, NetPath, SMPDB, PharmGKB, HumanCyc. `limit` caps these edges.
- `ortholog`: HomoloGene orthologs (`related_id` `NCBIGene:<id>`, `species`, `taxid`), at most 20. Symbols come from one extra batched `/query`; if that call fails the edge keeps the id as its name.

## Quirks

- Many fields are a single value for one gene and a list for another (`alias`, `ensembl`, `uniprot.TrEMBL`, each `pathway.<db>`); the adapter normalises them (checked on BRCA1, IL6, CRP, TNF, HLA-DRB1).
- Reactome pathways exist for only about 2,800 human genes in MyGene.info. Use the [Reactome adapter](../pathways/reactome_adapter.md) for full coverage.
- MyGene.info stores the OMIM gene number in `MIM`.
- HomoloGene lists gene ids by taxon only; it can include several ids for one species (paralogs).
- Latency: 60 to 100 ms per request; a failed ortholog symbol lookup is logged, not raised.

## Rate limits and errors

Keyless; the service asks for about 10 requests per second per IP. Uses the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). A 404 from `/gene` means "unknown gene" and does not count against the breaker. Errors are logged; search and relationships return `[]`, details return `None`.

## See also

- [HGNC adapter](hgnc_adapter.md), [Ensembl adapter](ensembl_adapter.md), [UniProt adapter](../core/uniprot_adapter.md)
- [All adapters](../README.md)
