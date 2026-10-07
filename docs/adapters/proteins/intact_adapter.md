---
description: IntAct curated experimental molecular interactions with detection method, score and PubMed evidence.
---

# IntAct adapter

Finds interactors in IntAct (EMBL-EBI) and lists their experimentally observed interaction partners, ranked by the IntAct MI score, with the detection methods and PubMed ids behind each pair.

| | |
|---|---|
| Source | `KnowledgeSource.INTACT` |
| Class | `knowledge_lookup.adapters.IntActAdapter` |
| Requires | none |
| Identifiers | UniProt accession `P38398` (primary), IntAct `EBI-349905`, isoform `P38398-1`, exact gene name `BRCA1` |
| Upstream API | `https://www.ebi.ac.uk/intact/ws` (interactors) and PSICQUIC `https://www.ebi.ac.uk/Tools/webservices/psicquic/intact/webservices/current/search/query` (interactions) |
| Licence | CC BY 4.0 |

## IntAct versus STRING

| | IntAct | [STRING](../families/string_adapter.md) |
|---|---|---|
| Content | interactions a curator extracted from a publication | experimental, database, text-mining, co-expression and prediction channels |
| Evidence | detection method, interaction type, PMID for every row | channel scores only |
| Score | `intact-miscore` 0 to 1 (publications, methods, types) | combined confidence 0 to 1 |
| Coverage | thousands of well-studied proteins, sparse elsewhere | nearly whole proteomes |

Use IntAct when you need to cite the experiment ("BRCA1-BARD1, co-immunoprecipitation, PMID 23680151"); use STRING for broad functional association. The two scores are not comparable.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import IntActAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with IntActAdapter(LookupConfig()) as adapter:
        brca1 = await adapter.get_concept_details("BRCA1")
        print(brca1.primary_id, brca1.primary_label, brca1.definitions[0])

        for edge in await adapter.get_relationships("P38398", limit=3):
            print(edge["related_id"], edge["related_name"], edge["score"],
                  edge["detection_methods"][:2], edge["pmids"][:2])


asyncio.run(main())
```

Output (live, 2026-10):

```
P38398 BRCA1 Breast cancer type 1 susceptibility protein
Q9BX63 BRIP1 0.98 ['anti bait coimmunoprecipitation', 'isothermal titration calorimetry'] ['17525340', '22792074']
Q99728 BARD1 0.96 ['anti bait coimmunoprecipitation', 'anti tag coimmunoprecipitation'] ['23680151', '33961781']
Q99708 RBBP8 0.93 ['anti bait coimmunoprecipitation', 'tandem affinity purification'] ['17525340', '18285836']
```

## Searching and details

`search_concepts(query, limit)` calls `interactor/findInteractor/{query}`. IntAct indexes molecules, not diseases: `fatigue` finds nothing, `IL6` finds interleukin-6 (then IL6ST, IL6R). Hits keep IntAct's relevance order; isoforms (`P38398-1`), chains, mRNA and gene records are dropped and, for gene-name queries, only human (`taxid=9606`) proteins are kept (`IntActAdapter(config, taxid=None)` keeps all species).

`get_concept_details(id)` accepts a UniProt accession, an `EBI-` accession or an exact gene name (the most connected human protein wins).

| Field | Value |
|---|---|
| `primary_id` | UniProt accession (the IntAct `EBI-` id for molecules without one) |
| `primary_label` | gene name (`interactorName`) |
| `synonyms` / `definitions` | protein name |
| `categories` | `taxon:9606`, species name |
| `semantic_types` | IntAct interactor type (`protein`, `gene`, ...) |
| `concept_type` | `PROTEIN` (also peptides), `GENE`, `CHEMICAL` (small molecule), otherwise `MOLECULAR_ENTITY` |
| `identifiers` | `INTACT` (primary and `EBI-` id), `UNIPROT` |
| `source_data[INTACT]` | raw interactor record (includes `interactionCount`) |

## Relationships

`get_relationships(concept_id, limit=25)` returns one `interacts_with` edge per partner, best score first:

| Key | Meaning |
|---|---|
| `related_id` / `related_name` | partner UniProt accession (canonical: isoforms and chains merged, listed in `isoforms`) and gene name |
| `related_id_source` | `UniProt`, or `IntAct` / `Ensembl` for partners without a UniProt entry (probes, genes) |
| `score` | `intact-miscore`, the maximum over the pair's evidence rows |
| `evidence_count` | curated evidence rows for the pair |
| `detection_methods`, `interaction_types` | PSI-MI names, most frequent first |
| `pmids` | up to 10 PubMed ids |
| `species`, `taxid`, `intact_id` | of the partner |

How it works: PSICQUIC cannot sort and would return an arbitrary subset for hub proteins (TP53 has more than 1000 evidence rows), so the adapter asks for rows in score tiers (`intact-miscore >= 0.7`, then `>= 0.4`, then all) of at most 400 rows each and stops at the first tier that holds `limit` partners. Negative interactions (`negative:true`) are excluded and self-interactions skipped. For a hub the cut-off partners are still high scoring, but the list may miss equally good ones beyond the 400-row cap.

The IntAct web service's `interaction/findInteractions` endpoint is not used: each interaction record embeds its full XML/JSON/MITAB renderings (about 190 kB each; two BRCA1 interactions were 460 kB), too heavy for ranking.

## Mappings

`get_mappings` returns the `EBI-` accession as an `exact` mapping and, from one PSICQUIC `tab27` row, Ensembl gene (`exact`) and protein ids, RefSeq, PDB, InterPro, Reactome, DIP, MINT, Orphanet disease xrefs (up to 10 per database, `related`) and up to 5 secondary UniProt accessions. Proteins without interactions only get the `EBI-` mapping.

## Quirks and rate limits

- Counts differ between services (BRCA1: 551 interactions via the interactor endpoint, 155 PSICQUIC rows for `id:P38398`); the adapter reports what PSICQUIC returns.
- The same pair appears in both orientations and once per evidence; the adapter merges them.
- Latency: findInteractor 0.1 to 1 s, PSICQUIC 0.2 to 4 s (hub proteins). The adapter allows 60 s per request.
- Keyless; EBI asks for polite use. Shared retry and circuit breaker apply (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; methods return `[]` or `None`.

## See also

- [STRING adapter](../families/string_adapter.md), [UniProt adapter](../core/uniprot_adapter.md), [Reactome adapter](../pathways/reactome_adapter.md)
- [All adapters](../README.md)
