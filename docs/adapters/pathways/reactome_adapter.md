---
description: Reactome pathways and reactions through the Reactome ContentService.
---

# Reactome adapter

Searches Reactome pathways and reactions by keyword and fetches them by stable ID, with their summaries.

| | |
|---|---|
| Source | `KnowledgeSource.REACTOME` |
| Class | `knowledge_lookup.adapters.ReactomeAdapter` |
| Requires | none |
| Identifiers | stable ID, e.g. `R-HSA-109581` |
| Upstream API | `https://reactome.org/ContentService` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ReactomeAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ReactomeAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("apoptosis", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        pathway = await adapter.get_concept_details("R-HSA-109581")
        print(pathway.primary_id, pathway.primary_label, pathway.definitions[0][:60])


asyncio.run(main())
```

Output:

```
R-HSA-109581 Apoptosis ['Homo sapiens']
R-DRE-109581 Apoptosis ['Danio rerio']
R-MMU-109581 Apoptosis ['Mus musculus']
R-HSA-109581 Apoptosis Apoptosis is a distinct form of cell death that is functiona
```

Search is not limited to human: inferred orthologous events (`R-DRE-...`, `R-MMU-...`) share the human label, so `CentralKnowledgeLookup` may merge them into one concept.

## Searching

`search_concepts(query, limit)` calls `/search/query?query=...&rows=min(limit, 100)`. The ContentService groups hits by type (`results[].entries[]`, with the type on each entry); the adapter keeps the `Pathway` and `Reaction` entries in the order Reactome returns them and stops after `limit` concepts (`rows` applies per group).

| Field | Value |
|---|---|
| `primary_id` | stable ID (`stId`) |
| `primary_label` | name, with Reactome's `<span class="highlighting">` markup removed |
| `definitions` | summation, markup removed |
| `categories` | species |
| `concept_type` | `PATHWAY` for pathways, `BIOLOGICAL_PROCESS` for reactions |
| `identifiers` | one `REACTOME` identifier, URL `https://reactome.org/content/detail/<id>` |
| `confidence_score` | `0.9` |
| `source_data[REACTOME]` | raw search entry |

Reactome answers HTTP 404 when nothing matches; search then returns `[]`. The 404 counts as an answer, not as a failure, so repeated searches without matches do not open the source's circuit breaker.

## Concept details

`get_concept_details(stable_id)` calls `/data/query/{id}`.

| Field | Value |
|---|---|
| `primary_id` | stable ID (`stId`) |
| `primary_label` | `displayName` |
| `definitions` | text of the first summation |
| `concept_type` | from `schemaClass`: `PATHWAY` for pathways, `BIOLOGICAL_PROCESS` for reactions and other events, otherwise `UNKNOWN` |
| `identifiers` | one `REACTOME` identifier, URL `https://reactome.org/content/detail/<id>` |
| `confidence_score` | `1.0` |
| `source_data[REACTOME]` | full database object |

## Relationships

`get_relationships(concept_id, limit=50)` depends on what the id is. `limit` caps each relation kind separately; Reactome's order is kept.

| Input | Edges |
|---|---|
| UniProt accession `P38398`, Ensembl gene `ENSG00000012048`, `HGNC:1100`, `NCBIGene:672` / `672`, gene symbol `BRCA1` | `participates_in`: lowest-level pathways containing the gene's products (`/data/mapping/{UniProt\|ENSEMBL\|HGNC\|NCBI Gene}/{id}/pathways?species=9606`) |
| Pathway or reaction `R-HSA-109581` (version suffix ignored) | `part_of` (parent and further ancestors, `depth` 1 = direct parent), `has_part` (direct child events), `has_participant` (UniProt proteins and ChEBI molecules, `related_id_source` names the database) |
| Physical entity (complex, protein, molecule) `R-HSA-140976` | `participates_in`: pathways it occurs in |

Pathway edges carry `related_id` (stable id), `related_name`, `stId`, `name`, `species`, `schema_class`, `is_in_disease` and `is_inferred`. Participant edges merge UniProt isoforms into the canonical accession (`isoform` keeps the original) and name the containing entity in `participant`.

Species defaults to human (`ReactomeAdapter(config, species="9606")`; `None` searches all species). Symbols that look like UniProt accessions (P2RY12) are tried as UniProt first and then as HGNC symbols. Reactome answers 404 when a gene is in no pathway; that gives `[]`.

Cost: `/data/participants/{id}` returns every physical entity of the pathway, about 160 kB for Apoptosis and much more for top-level pathways; results are capped after parsing.

## Mappings

`get_mappings(concept_id)` (same shape as the other adapters, `fromSource` `Reactome`):

| Input | Mappings |
|---|---|
| UniProt accession | Ensembl gene (`exact`) and protein ids, RefSeq, PDB, Orphanet, OpenTargets, HPA, GeneCards, PRO, Pharos (up to 10 per database, `related`) and secondary UniProt accessions, from `/data/query/uniprot:{acc}` |
| Ensembl gene or gene symbol | the UniProt accession (`exact`) via `/references/mapping/{id}`, then as above. That endpoint takes about 8 s and matches unrelated cross-references, so symbol lookups keep only entities whose gene name equals the symbol |
| Pathway / event | GO biological process (`related`) and inferred orthologous events in other species (`ortholog`, at most 20) |
| Physical entity | reference entity (UniProt, ChEBI, ...) and GO cellular component |

HGNC numeric and NCBI Gene ids return `[]` (no reliable mapping endpoint); use `get_relationships` for pathway edges from those.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]` and details return `None`. The `/data/query/{id}/{attribute}` endpoints answer `text/plain` only (HTTP 406 when JSON is requested), so the adapter reads them as text.

## See also

- [KEGG adapter](kegg_adapter.md), [Gene Ontology adapter](../phenotypes/geneontology_adapter.md)
- [All adapters](../README.md)
