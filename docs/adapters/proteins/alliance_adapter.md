---
description: Alliance of Genome Resources genes of eight model organisms and human, with orthologs, disease annotations, phenotypes and molecular interactions.
---

# Alliance of Genome Resources adapter

Looks up genes in the [Alliance of Genome Resources](https://www.alliancegenome.org), which integrates the curated data of HGNC/RGD (human), MGI (mouse), RGD (rat), ZFIN (zebrafish), FlyBase, WormBase, SGD (yeast) and Xenbase. A gene concept carries symbol, full name, species, a description (the MOD-provided one when it exists, otherwise the automated one) and cross-references; relationships give the cross-species picture: orthologs, disease annotations, phenotypes and molecular interactions.

| | |
|---|---|
| Source | `KnowledgeSource.ALLIANCE` |
| Class | `knowledge_lookup.adapters.AllianceGenomeAdapter` |
| Requires | none (public, keyless) |
| Identifiers | `HGNC:1100`, `MGI:104537`, `RGD:2218`, `ZFIN:ZDB-GENE-990415-72`, `SGD:S000003865`, `WB:WBGene00004930`, `FB:FBgn0003462`, `Xenbase:XB-GENE-1006488`; a bare symbol (`TNF`) is resolved through search, human first |
| Upstream API | `https://www.alliancegenome.org/api` (Swagger: `https://www.alliancegenome.org/openapi`) |
| Optional env | `ALLIANCE_SPECIES`: default species filter for search (`Homo sapiens` or an alias such as `mouse`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import AllianceGenomeAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with AllianceGenomeAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("BRCA1", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        edges = await adapter.get_relationships("HGNC:1100")
        for edge in edges:
            if edge["relation_label"] == "ortholog_of":
                print(edge["related_id"], edge["related_name"], edge["related_species"], edge["best"])

        print([(m["toSource"], m["toId"]) for m in (await adapter.get_mappings("HGNC:1100"))[:4]])


asyncio.run(main())
```

Output (live, 2026-10-09, Alliance release 9.1.0):

```
HGNC:1100 BRCA1 ['Homo sapiens']
MGI:104537 Brca1 ['Mus musculus']
RGD:2218 Brca1 ['Rattus norvegicus']
Xenbase:XB-GENE-6254021 brca1.L Xenopus laevis True
WB:WBGene00000264 brc-1 Caenorhabditis elegans True
MGI:104537 Brca1 Mus musculus True
RGD:2218 Brca1 Rattus norvegicus True
Xenbase:XB-GENE-490624 brca1 Xenopus tropicalis True
[('UniProt', 'UniProtKB:P38398'), ('RGD', 'RGD:69132'), ('Ensembl', 'ENSEMBL:ENSG00000012048'), ('NCBI Gene', 'NCBI_Gene:672')]
```

## Searching

`search_concepts(query, limit, species=None)` calls `GET /search?category=gene_search_result` and builds concepts from the hits without a second request (about 3 KB per hit plus ~4 KB of facet counts).

- Searches symbol, name and synonyms; the hit's `synonyms` also contain gene names and descriptions.
- `species` (or `ALLIANCE_SPECIES`) filters to **one** species, given as a full name (`Mus musculus`) or an alias (`human`, `mouse`, `rat`, `zebrafish`, `fly`, `worm`, `yeast`, `frog`). The Alliance combines repeated `species` parameters with AND, so several species cannot be requested at once.
- The Alliance ranks by relevance only (a `BRCA1` search lists the rat gene before the human one), so results are re-ranked: exact symbol first, then human, mouse, rat, zebrafish, fly, worm, yeast, Xenopus.
- The server is asked for at least 20 and at most 50 hits so that re-ranking sees a useful window; `limit` then trims the list.

## Concept details

`get_concept_details(concept_id)` reads `GET /gene/{id}` (17 - 46 KB: genes list every UniProt isoform and the genomic location, BRCA1 has over 100 UniProt entries). Only a few cross-references are kept.

| Field | Value |
|---|---|
| `primary_label` | gene symbol |
| `synonyms` | full gene name and synonyms |
| `definitions` | MOD-provided gene description, else the automated description |
| `categories` / `semantic_types` | species name / gene type (`protein_coding_gene`) |
| `source_data[ALLIANCE]` | `name`, `species`, `taxon`, `gene_type`, `cross_references` (CURIEs), `location` (chromosome, start, end, strand) |

An unknown id makes the Alliance answer HTTP 400 (not 404); the adapter returns `None`.

## Relationships

`get_relationships(concept_id)` makes four requests, spaced 0.3 s apart, and returns at most 25 + 10 + 10 + 15 edges (the caps are the class attributes `max_orthologs`, `max_diseases`, `max_phenotypes` and `max_interaction_rows`). A section that fails is skipped without losing the others.

| Predicate | Source | Extra keys |
|---|---|---|
| `ortholog_of` | `GET /gene/{id}/orthologs` | `related_species`, `best`, `best_reverse`, `confidence`, `methods_matched`, `methods_total`, `methods`, `stringency`, `total_orthologs` |
| `associated_with_disease` | `POST /disease?geneID={id}` with body `["{id}"]` | `related_id` is a DOID, `association` (`is_implicated_in`, `is_marker_for`), `evidence_codes` (ECO abbreviations such as `IMP`, `IEP`, `TAS`), `total_annotations` |
| `has_phenotype` | `GET /gene/{id}/phenotypes` | `related_id` is the phenotype term (HP, MP, ZP, WBPhenotype ...; empty if the annotation is free text), `phenotype_statement`, `n_annotations`, `publications`, `total_phenotypes` |
| `interacts_with` | `GET /gene/{id}/molecular-interactions` | `interaction_type`, `detection_method`, `interaction_source`, `total_interaction_records` |

Things to know:

- **Orthologs** are the Alliance's "stringent" set (BRCA1 gives 5: mouse, rat, two Xenopus, worm). Orthology is computational (DIOPT: many prediction methods); `best`/`best_reverse` flag reciprocal best hits and `methods_matched` of `methods_total` is the support.
- **Diseases**: there is no `/gene/{id}/diseases` endpoint. The disease list comes from `POST /disease`, whose `geneID` query parameter is ignored (it returns all 55k annotations); the JSON body filters. De-duplicated by (DOID, association). An Alliance annotation may be implied through an ortholog, not measured in that species.
- **Phenotypes** come in alphabetical order of the statement, so a capped list is a sample and not a ranking. Each record is about 33 KB because it embeds all primary annotations.
- **Interactions** are one row per *experiment* (BRCA1: 2,499 records) in alphabetical order of the partner; the adapter de-duplicates partners, so 15 rows give about 8 partners. `total_interaction_records` is the real count. Only molecular interactions are queried; genetic interactions (`/genetic-interactions`) are not.

## Mappings

`get_mappings(concept_id)` returns the cross-references of the gene: Ensembl, NCBI Gene, UniProt (the canonical entry first, then up to four more), OMIM (human), PANTHER and the species database ids. `toId` keeps the CURIE form (`NCBI_Gene:672`, `ENSEMBL:ENSG00000012048`), `mappingType` is `xref`, `confidence` 0.95. The gene's own id is not repeated.

## Rate limits, licence, errors

No rate limit is published; requests are spaced 0.3 s apart with the shared retry and circuit breaker. Errors are logged and `[]`/`None` returned. Note that a run of invalid ids (HTTP 400) counts towards the circuit breaker; ids with unknown prefixes (`NCBIGene:672`) are rejected locally for that reason.

The Alliance states that most of its data are CC0 1.0 and some CC BY 4.0 ([terms of use](https://www.alliancegenome.org/terms-of-use)); cite the Alliance (Nucleic Acids Res 2023, doi:10.1093/nar/gkac1003).

## Caveats

- Model-organism curation, not human evidence: a mouse phenotype or a yeast interaction is translational at best.
- Payloads are large for a gene API (see sizes above); keep `limit` low and call `get_relationships` for the genes you need.
- The API is marked "1.0 Beta" in its OpenAPI document and changes between releases (the Alliance publishes breaking changes on its API mailing list); the live shapes described here were verified on release 9.1.0.
- Human phenotype annotations use HPO terms from OMIM/Orphanet; model organism genes use their own ontologies.

## Live verification (2026-10-09)

- `knowledge-lookup check ALLIANCE` passes (search `BRCA1` 5 results, details `HGNC:1100`, relationships 32 edges).
- Latency: search 0.3 - 2 s, details 0.15 - 2.2 s, `get_relationships` about 1.2 s for four sections. Payloads: gene 46 KB (human) / 17 KB (zebrafish), orthologs 4.5 KB for 3 rows, diseases 9 KB per annotation, phenotypes 33 KB per statement, interactions 10 KB per row, search 16 KB for 2 hits and 67 KB for 21.
- Unknown id: HTTP 400 `No gene found with ID`. A `species` parameter, a `stringency` parameter on `/orthologs` and a `geneID` parameter on `POST /disease` were tested and found respectively working (single value), ignored, and ignored.

## See also

- [HGNC adapter](hgnc_adapter.md), [Ensembl adapter](ensembl_adapter.md), [IMPC adapter](../phenotypes/impc_adapter.md)
- [All adapters](../README.md)
