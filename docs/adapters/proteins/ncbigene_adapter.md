---
description: NCBI Gene records, summaries and cross-references (Datasets API).
---

# NCBI Gene adapter

Looks up genes of any organism in NCBI Gene through the keyless NCBI Datasets v2 API. A concept is a gene: the Entrez Gene id is the primary id, the official symbol the label, and the record carries the full name, aliases, the RefSeq curated summary, chromosome and map location, genomic annotation, Gene Ontology annotations and cross-references to HGNC (or the organism's own nomenclature authority), Ensembl, OMIM and UniProt. `get_relationships` adds the RefSeq transcripts and proteins, the genomic location on each annotated assembly and mouse orthologs.

| | |
|---|---|
| Source | `KnowledgeSource.NCBIGENE` |
| Class | `knowledge_lookup.adapters.NCBIGeneAdapter` |
| Requires | none (an optional `NCBI_API_KEY` raises the polite request rate) |
| Identifiers | Entrez Gene id `672` (primary), `NCBIGene:672`, `GeneID:672`, `Entrez:672`; an official symbol (`BRCA1`) also works in `get_concept_details` |
| Upstream API | `https://api.ncbi.nlm.nih.gov/datasets/v2/gene` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import NCBIGeneAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with NCBIGeneAdapter(LookupConfig()) as adapter:
        for gene in await adapter.search_concepts("BRCA1", limit=3):
            print(gene.primary_id, gene.primary_label, gene.synonyms[0])

        brca1 = await adapter.get_concept_details("NCBIGene:672")
        print(brca1.categories, [(i.source, i.identifier) for i in brca1.identifiers])

        for m in await adapter.get_mappings("672"):
            print(m["toSource"], m["toId"], m["mappingType"])

        rels = await adapter.get_relationships("672", max_transcripts=2)
        print([(r["relation_label"], r["related_id"]) for r in rels])


asyncio.run(main())
```

Output (live, 2026-10-09):

```
672 BRCA1 BRCA1 DNA repair associated
8314 BAP1 BRCA1 associated deubiquitinase 1
580 BARD1 BRCA1 associated RING domain 1
['taxon:9606', 'chromosome:17', 'locus:17q21.31'] [('NCBIGENE', '672'), ('HGNC', 'HGNC:1100'), ('ENSEMBL', 'ENSG00000012048'), ('OMIM', '113705'), ('UNIPROT', 'P38398')]
NCBIGENE NCBIGene:672 exactMatch
HGNC HGNC:1100 exactMatch
ENSEMBL ENSG00000012048 exactMatch
OMIM OMIM:113705 xref
UNIPROT P38398 encodes_product
[('located_on', 'NC_000017.11'), ('located_on', 'NC_060941.1'), ('has_transcript', 'NM_007294.4'), ('encodes', 'NP_009225.1'), ('has_transcript', 'NM_001407571.1'), ('encodes', 'NP_001394500.1'), ('has_ortholog', 'NCBIGene:12189')]
```

## Searching

`search_concepts(query, limit=20, taxon=None)` accepts three kinds of query, all verified live:

| Query | Request | Notes |
|---|---|---|
| Entrez ids: `672`, `NCBIGene:672`, `672,3105` | `gene/id/{ids}` | several ids in one request |
| Official symbols or aliases: `BRCA1`, `brca1`, `BRCC1`, `IL6, TNF` | `gene/symbol/{symbols}/taxon/{taxon}` | case-insensitive; an alias returns every gene that uses it (`BRCC1` = BRCA1 and ICE2); an unknown symbol answers HTTP 200 `{}` |
| Free text: `breast cancer`, `mitochondrial dysfunction` | `gene/taxon/{taxon}/dataset_report?query=...&page_size=n` | text match over names, aliases and descriptions (`breast cancer` = 63 human genes), in the registry's order, not by relevance score |

Symbol matches come first. When fewer than `limit` genes were found, a symbol-shaped query also runs the text search, so `BRCA1` returns BRCA1 followed by BAP1 and BARD1 (genes whose names mention it); a query with spaces goes to the text search only. `taxon` is a tax id or an organism name (`9606`, `human`, `mouse`, `Mus musculus`) and defaults to human; anything with unusual characters falls back to human. `limit` is capped at 100 (a gene record is 10-20 KB, so 100 genes is about 1.5 MB).

The text search is not a phenotype search: `fatigue` finds no gene (the query field matched nothing), and symptom or disease words usually only hit genes whose name contains them. For symptom-to-gene questions use a gene-disease source such as the [MedGen](../phenotypes/medgen_adapter.md) or [GenCC](../phenotypes/gencc_adapter.md) adapter.

## Concept details

`get_concept_details("672")` fetches `gene/id/672` (a non-numeric id is tried as an official symbol: an exact symbol match wins, an alias shared by several genes returns `None`).

| Field | Value |
|---|---|
| `primary_id` | Entrez Gene id, e.g. `672` |
| `primary_label` | official symbol (`BRCA1`) |
| `concept_type` | `GENE` |
| `synonyms` | full name, symbol synonyms and alternate names (case-insensitive unique, at most 50) |
| `definitions` | the RefSeq summary |
| `categories` | `taxon:<id>`, `chromosome:<n>`, `locus:<cytogenetic band>` |
| `semantic_types` | gene type, e.g. `PROTEIN_CODING` |
| `identifiers` | `NCBIGENE`; `HGNC` (human), `ENSEMBL`, `OMIM`, `UNIPROT` (Swiss-Prot accessions) |
| `source_data["NCBIGENE"]` | symbol, name, taxon, type, orientation, chromosomes, map locations, nomenclature authority and id (HGNC, MGI, RGD, ZFIN, FlyBase ...), annotations per assembly (accession, genomic range), transcript and protein counts, gene groups, a compact Gene Ontology list (up to 50 unique terms per aspect with qualifier), record URL |

## Relationships

`get_relationships(id, max_transcripts=25, ortholog_taxa=None, taxon=None)`:

| Label | Target | Extras |
|---|---|---|
| `located_on` | RefSeq chromosome accession (`NC_000017.11`), one per annotated assembly (GRCh38.p14, T2T-CHM13v2.0) | `begin`, `end`, `orientation` (as the report gives them), `chromosome`, `assembly_name`, `assembly_accession` |
| `has_transcript` | RefSeq transcript (`NM_007294.4`) | `length`, `select_category` (`MANE_SELECT`), `ensembl_transcript` |
| `encodes` | the protein of that transcript (`NP_009225.1`) | `length`, `transcript`, `ensembl_protein`, isoform in the name |
| `has_ortholog` | `NCBIGene:<id>` of the NCBI ortholog | `tax_id`, `taxname`, `description` |

Transcripts are ordered MANE Select first, then by accession, and capped at `max_transcripts`. The full list is large: BRCA1 has 368 transcripts and its `product_report` is **1.4 MB and 1.5-3 s** (the API ignores `page_size` and `table_fields` there), so `max_transcripts=0` skips the request. Orthologs default to mouse (`10090`); pass any tax ids, or `()` for none. Each taxon is one 20 KB request through `taxon_filter`; without the filter the answer is 1.3 MB, which the adapter never requests. A failed product or ortholog request is logged and the other edges are still returned.

## Mappings

`get_mappings(id)`: `NCBIGene:<id>` as the OBO-style id, the nomenclature authority's id (`HGNC:1100`; `MGI:104537` for mouse genes), Ensembl gene ids and the OMIM gene entry (`xref`, 0.95) are `exactMatch`; Swiss-Prot accessions are `encodes_product` (0.9). The record exposes only reviewed Swiss-Prot accessions (`swiss_prot_accessions`), no other UniProt entries.

## When to use NCBI Gene (compared with HGNC, Ensembl and MyGene.info)

| Need | Use |
|---|---|
| Approved human gene names, previous symbols, gene groups | [HGNC](hgnc_adapter.md) |
| Genome-centred data: transcripts and exons with Ensembl ids, variants, regulation, VEP, comparative genomics | [Ensembl](ensembl_adapter.md) |
| Fast aggregated hub for identifiers, pathways and HomoloGene in a single call | [MyGene.info](mygeneinfo_adapter.md) |
| Any organism NCBI annotates by symbol or tax id; the RefSeq curated summary; RefSeq `NM_`/`NP_` accessions with MANE Select; Gene Ontology annotations with evidence qualifiers; every gene sharing an alias | **NCBI Gene** |

NCBI Gene is the source of the Entrez ids the other three use, so it is the reference when ids disagree. It costs more requests than MyGene.info (the transcript list is large and orthologs need extra calls), and its search is by symbol/alias and plain text, not a ranked relevance search.

## Rate limits, licence and errors

The service advertises 5 requests/s without a key (`x-ratelimit-limit`) and 10/s with an NCBI API key. The adapter spaces calls at 3 requests/s keyless and 10/s when `NCBI_API_KEY` (or `ncbi` in the config's `api_keys`) is set; the key is read as in the NCBI Taxonomy and dbSNP adapters and sent in the `api-key` header like the Taxonomy adapter does (the keyed path is covered by mocked tests only; no key was available for a live run). NCBI data are in the public domain; NCBI asks users to cite it. A malformed id answers HTTP 400 (not 404); a well-formed id that does not exist (`999999999`), unknown symbols and empty searches answer 200 with `{}`. Search and details log the error and return `[]` / `None`.

## Live verification (2026-10-09)

`knowledge-lookup check NCBIGENE` passes (search `BRCA1`, details, relationships). Measured: gene report 20 KB in 0.5-0.9 s, three genes by id 73 KB in 3.2 s, text search 48 KB in 0.9-2.9 s, orthologs for one taxon 22 KB in 0.9 s, `product_report` 1.4 MB in 1.1-2.9 s. Symbols, aliases, taxon names, free text, mouse genes (`Brca1`, MGI authority), id errors and the empty answers were each checked against live responses.

## See also

- [HGNC adapter](hgnc_adapter.md), [Ensembl adapter](ensembl_adapter.md), [MyGene.info adapter](mygeneinfo_adapter.md)
- [NCBI Taxonomy adapter](../ontologies/ncbitaxonomy_adapter.md): the same API family and key handling
- [All adapters](../README.md)
