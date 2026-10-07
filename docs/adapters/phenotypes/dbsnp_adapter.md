---
description: NCBI dbSNP reference SNPs (rsIDs) with placements, allele frequencies, genes and ClinVar clinical significance via the Variation Services API.
---

# dbSNP adapter

Looks up reference SNP ids (rsIDs) in NCBI dbSNP through the Variation Services REST API. One document per rsID carries the alleles on GRCh38 and GRCh37, per-study allele frequencies (gnomAD, TOPMed, 1000 Genomes, ALFA, ...), the genes and transcript consequences, and the ClinVar records attached to the variant. That makes the rsID the natural join key between GWAS hits, ClinVar entries, pharmacogenomic annotations and the gnomAD adapter.

| | |
|---|---|
| Source | `KnowledgeSource.DBSNP` |
| Class | `knowledge_lookup.adapters.DbSNPAdapter` |
| Requires | none; an optional NCBI key (`NCBI_API_KEY`) shortens the request spacing |
| Identifiers | `rs1801133`, bare `1801133`, `dbSNP:rs1801133`; also SPDI (`NC_000001.11:11796320:G:A`) and genomic HGVS (`NC_000001.11:g.11796321G>A`), which are first resolved to an rsID |
| Upstream API | `https://api.ncbi.nlm.nih.gov/variation/v0` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DbSNPAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


async def main():
    async with DbSNPAdapter(LookupConfig()) as adapter:
        snp = await adapter.get_concept_details("rs1801133")
        print(snp.primary_id, "-", snp.definitions[0])
        data = snp.source_data[KnowledgeSource.DBSNP]
        print(data["placements"][0]["alleles"][1]["hgvs"])
        print(data["allele_frequencies"][1])

        for edge in (await adapter.get_relationships("rs1801133", limit=3)):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

Output (live, October 2026):

```
rs1801133 - SNV rs1801133 in MTHFR (coding_sequence_variant, missense_variant) ClinVar: benign, conflicting-interpretations-of-pathogenicity, drug-response, likely-benign
NC_000001.11:g.11796321G>A
{'study': 'GnomAD_exomes', 'total': 1401372, 'alleles': {'G': 0.676655, 'A': 0.323345}}
located_in 4524 MTHFR
has_clinical_association C1856059 MTHFR THERMOLABILE POLYMORPHISM
has_clinical_association C0238198 Gastrointestinal stromal tumor
```

## Searching

dbSNP has no free-text or gene search in this API, so `search_concepts(query, limit)` only resolves identifiers and returns at most one concept: an rsID in any of the accepted spellings, a SPDI string (`GET /spdi/{spdi}/rsids`) or a genomic HGVS string (`GET /hgvs/{hgvs}/contextuals`, then the SPDI route). Words such as `fatigue` return `[]`. To go from a gene to its variants use the [gnomAD adapter](gnomad_adapter.md) or ClinVar.

Malformed input is rejected locally: the service answers a non-numeric id with HTTP 500 and an unknown id with HTTP 404 (`RefSNP not found`).

## Merged and withdrawn ids

dbSNP merges duplicate rsIDs. A merged id returns a stub with `merged_snapshot_data.merged_into`; the adapter follows it (at most 3 hops, one extra request per hop) and returns the surviving rsID as `primary_id`. The id you asked for stays in `source_data["DBSNP"]["requested_id"]`, the ids passed through in `merged_from`, and the ids merged *into* the survivor in `merged_rsids` (also `synonyms`). Example: `rs4134713` -> `rs1801133`.

Documents with `withdrawn_snapshot_data` or `unsupported_snapshot_data` become a bare concept with `source_data["DBSNP"]["status"]` set to `withdrawn` / `unsupported`. **Not live-verified**: no withdrawn rsID could be found to test against (rs1 is simply 404); the handling follows the documented field names and is covered by synthetic unit tests only.

## Concept details

`ConceptType.MOLECULAR_ENTITY`; label and `primary_id` are the rsID; `definitions` is a one-line summary (type, gene, consequences, ClinVar significances). Identifiers: `DBSNP` (with the dbSNP URL) and `NCBI` (Entrez Gene id and symbol, for each gene the variant lies in). `categories` lists the assemblies, `synonyms` the merged rsIDs plus the GRCh38 genomic HGVS of each alternate allele.

`source_data["DBSNP"]` keeps a compact version of the (200-440 KB) document:

| Field | Content |
|---|---|
| `variant_type`, `anchor`, `created`, `last_updated`, `build`, `citation_count` | provenance (`citation_count` = linked PubMed ids) |
| `placements` | chromosome placements, GRCh38 first then GRCh37: `assembly`, `seq_id`, `chrom`, and per allele the SPDI string and HGVS (the first allele is the reference) |
| `genes` | `gene_id` (Entrez), `symbol`, `name`, `orientation` |
| `consequences`, `mane_select_ids` | Sequence Ontology terms of the MANE Select transcript(s) |
| `allele_frequencies` | up to 8 studies (GnomAD, TOPMed, 1000 Genomes, ... first): `study`, `total` chromosomes, `alleles` {sequence: frequency}. Indels use the inserted sequence, `-` for a deletion |
| `clinvar`, `clinvar_significances` | up to 25 RCV records: `rcv`, `variation_id`, `significance`, `review_status`, `conditions`, `condition_ids` (MedGen / MONDO / OMIM / Orphanet / MeSH), `last_evaluated` |

Positions are SPDI (0-based, deletion/insertion form) as returned by NCBI; the HGVS strings are 1-based.

## Relationships and mappings

| Call | Result |
|---|---|
| `get_relationships(rsid, limit=10)` | `located_in`: Entrez gene id, symbol (`id_namespace: "NCBI Gene"`). `has_clinical_association`: one per distinct (condition, significance) with `related_id` the MedGen/MONDO/OMIM/Orphanet id (else the condition name), `clinical_significance`, `review_status`, `rcv`, `last_evaluated`. "not provided", "not specified" and "see cases" conditions are skipped. ClinVar interpretations are submitter-supplied and often conflicting: read the review status |
| `get_mappings(rsid)` | `ClinVar` variation id (`kind: "variation"`), `VCV000003520` style accession (`kind: "VCV"`), every RCV (`kind: "RCV"`, with significance); `HGVS` genomic strings of the alternate alleles (GRCh38 and GRCh37, `assembly`); `dbSNP` merged rsIDs (`mappingType: "merged_from"`); `NCBI` gene ids (`mappingType: "located_in"`) |

## Rate limits, latency, licence

NCBI asks for **at most one request per second** to the Variation Services (the service is still labelled beta). The adapter enforces a one-second gap between its own calls; with an NCBI key (`NCBI_API_KEY`, the E-utilities key, read like the other NCBI settings through `config.get_api_key("ncbi")`) it sends `api_key` and reduces the gap to 0.15 s. The Variation Services documentation does not state a higher keyed limit, so the benefit of the key is **not verified**; set the key only if you have one anyway.

Latency is dominated by document size: rs1801133 (200 KB) took 3-7 s on first fetch and about 1 s afterwards; rs80357906 (BRCA1, 440 KB) about 1 s; SPDI/HGVS resolution adds 2-5 s per extra call. The adapter sets a 60 s timeout floor. A merged id costs one additional request.

NCBI data are public domain; cite dbSNP (Sherry et al. 2001) as usual.

## See also

- [gnomAD adapter](gnomad_adapter.md), [ClinVar adapter](clinvar_adapter.md), [GWAS Catalog adapter](gwascatalog_adapter.md)
