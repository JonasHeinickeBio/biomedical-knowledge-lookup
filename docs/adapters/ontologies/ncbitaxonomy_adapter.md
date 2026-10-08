---
description: NCBI Taxonomy organisms and viruses (SARS-CoV-2, EBV, HHV-6, enteroviruses) with lineage, synonyms and cross-references.
---

# NCBI Taxonomy adapter

Searches the NCBI Taxonomy and fetches taxon records through the keyless NCBI Datasets taxonomy API (v2). For Long COVID and ME/CFS work this is the identifier hub for pathogens and host species: SARS-CoV-2 (`2697049`), Epstein-Barr virus (`10376`), human herpesvirus 6A/6B (`32603`, `32604`), the enterovirus genus (`12059`) and *Homo sapiens* (`9606`), together with their lineages and children.

| | |
|---|---|
| Source | `KnowledgeSource.NCBITAXONOMY` |
| Class | `knowledge_lookup.adapters.NCBITaxonomyAdapter` |
| Requires | none (an NCBI key only raises the rate limit) |
| Identifiers | `2697049`, `NCBITaxon:2697049`, `taxid:2697049` |
| Upstream API | `https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import NCBITaxonomyAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with NCBITaxonomyAdapter(LookupConfig()) as adapter:
        hits = await adapter.search_concepts("Epstein-Barr virus", limit=3)
        print([(c.primary_id, c.primary_label) for c in hits])

        ebv = await adapter.get_concept_details("NCBITaxon:10376")
        print(ebv.primary_label, ebv.synonyms[:4])

        for rel in (await adapter.get_relationships("2697049", limit=3))[:4]:
            print(rel["relation_label"], rel["related_id"], rel["related_name"], rel["rank"])

        print([m["toId"] for m in await adapter.get_mappings("10376")])


asyncio.run(main())
```

Output (live, 2026-10-08):

```
[('10376', 'human gammaherpesvirus 4'), ('45455', 'Macacine gammaherpesvirus 4'), ('31525', 'Human herpesvirus 4 strain CAO')]
human gammaherpesvirus 4 ['Epstein-Barr virus', 'HHV-4', 'EBV', 'Epstein Barr virus']
is_a NCBITaxon:3418604 Betacoronavirus pandemicum species
descendant_of NCBITaxon:1 root no rank
descendant_of NCBITaxon:10239 Viruses acellular root
descendant_of NCBITaxon:2559587 Riboviria realm
['NCBITaxon:10376', 'NCBITaxon:47902', 'https://eol.org/pages/46699929']
```

## Searching

`search_concepts(query, limit)` calls `taxon_suggest/{text}?tax_rank_filter=higher_taxon`, which matches scientific names, synonyms, acronyms and common names (`SARS-CoV-2`, `EBV`, `human`). The default `species` filter must not be used: it drops viruses without a species rank (SARS-CoV-2 itself has no rank in NCBI Taxonomy) and returns unrelated species, while `higher_taxon` still returns species. A query that is a taxid (`2697049`, `NCBITaxon:2697049`) goes straight to `get_concept_details`.

Search hits are light: `primary_id` is the taxid, `primary_label` the scientific name, `synonyms` the matched term and common name, `semantic_types` the rank (`species`, `genus`, `no rank` ...), `categories` the BLAST group (`viruses`, `primates`), `concept_type` `ORGANISM`. Results are in NCBI's relevance order with decreasing `confidence_score` (0.9 downwards).

## Concept details

`get_concept_details(concept_id)` makes two requests: `taxon/{id}/dataset_report` and `taxon/{id}/name_report`. A merged (retired) taxid such as `47902` resolves to its current node (`10376`).

| Field | Value |
|---|---|
| `primary_id` | taxid |
| `primary_label` | current scientific name |
| `synonyms` | curator common name, other common names and acronyms (`EBV`, `HHV-4`), informal GenBank names |
| `semantic_types` | `[rank]`, `no rank` where NCBI omits it |
| `categories` | BLAST group and `moltype:<genomic molecule type>` |
| `definitions` | one-line summary with the ICTV/NCBI classification path |
| `identifiers` | `NCBITAXONOMY` `NCBITaxon:<id>` with the NCBI taxonomy browser URL |
| `source_data[NCBITAXONOMY]` | classification, lineage ids (`parents`), child ids, genome and gene counts, secondary taxids, authority |

The `name_report` call is best effort: if it fails, the record is still returned without the extra synonyms.

## Relationships

`get_relationships(concept_id, limit=25)` returns typed edges, each with `rank`:

| `relation_label` | Meaning |
|---|---|
| `is_a` | direct parent (last entry of the lineage) |
| `descendant_of` | every higher ancestor, root first, with `depth` |
| `has_subclass` | child taxa, capped at `limit` (the Enterovirus genus has hundreds) |

The API returns lineage and children as bare taxids, so the names and ranks come from one more `dataset_report` call for all related taxids (reports come back in taxid order and are re-ordered by lineage). Children that the report omits are skipped.

## Mappings

`get_mappings(concept_id)` returns what the record exposes: `NCBITaxon:<id>` in the OBO ontology (`exactMatch`), merged taxids (`merged_id`) and the Wikipedia and Encyclopedia of Life pages from the `links` endpoint (`xref`, confidence 0.9; the links call is best effort). The API does not provide GBIF, ITIS or UniProt taxonomy ids.

## Rate limits, licence and errors

Without a key the service advertises 5 requests/s (`x-ratelimit-limit`); the adapter spaces calls at 3/s, like NCBI E-utilities. With an NCBI key (`NCBI_API_KEY` or `ncbi` in `LookupConfig.api_keys`) it spaces calls at 10/s and sends the key in the `api-key` header (never in the URL; this path is not verified against a real key). NCBI data are public domain; NCBI asks users to cite the database.

Unknown ids and names do not give a 404: the API answers HTTP 200 with an `errors` entry. The adapter treats that as "not found" (`None` / `[]`). Other errors are logged, search returns `[]` and details return `None`; see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers).

## Caveats

- Names are not accepted as concept ids for details (the API would resolve them, but ambiguity is high); search by name instead.
- Many viruses have no rank in NCBI Taxonomy (`no rank`), so rank filtering is unreliable for them; use the lineage edges instead.
- Taxon records carry no free-text description; `definitions` is a generated classification summary.

## Live verification (2026-10-08)

Endpoints and response shapes were checked against the live API. `knowledge-lookup check NCBITAXONOMY` passes (search SARS-CoV-2, details, 12 lineage edges).

| Call | Latency | Size |
|---|---|---|
| `taxon_suggest/SARS-CoV-2` | 0.8 s | about 2 KB |
| `taxon/10376/dataset_report` | 0.7 s | 1.4 KB |
| `taxon/10376/name_report` | 0.7 s | 0.7 KB |
| lineage + 25 children `dataset_report` (33 ids) | 1.0 s | 37 KB |
| `get_concept_details` (2 calls) | 0.8 s | |
| `get_relationships` (2 calls) | 1.2 s | |

Requests above were spaced; no 429 responses were seen.

## See also

- [MedGen adapter](../phenotypes/medgen_adapter.md), [dbSNP adapter](../phenotypes/dbsnp_adapter.md) (same NCBI key and rate-limit handling)
- [All adapters](../README.md)
