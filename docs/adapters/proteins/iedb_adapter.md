---
description: Immune Epitope Database (IEDB) epitopes with source antigen, organism, assay counts, MHC alleles and diseases, via the keyless PostgREST query API.
---

# IEDB adapter

Searches the Immune Epitope Database for experimentally characterised B cell, T cell and MHC-ligand epitopes and follows them to their source antigens and organisms. Relevant to Long COVID and ME/CFS work on SARS-CoV-2 and Epstein-Barr virus (EBV) immune responses: `SARS-CoV-2 spike` and `EBV nuclear antigen` return epitope records with the HLA alleles and diseases they were studied in.

| | |
|---|---|
| Source | `KnowledgeSource.IEDB` |
| Class | `knowledge_lookup.adapters.IEDBAdapter` |
| Requires | none (keyless) |
| Identifiers | epitope `IEDB_EPITOPE:1309147` (or bare `1309147`); antigen `UNIPROT:P0DTC2` (or bare `P0DTC2`) |
| Upstream API | `https://query-api.iedb.org` (PostgREST, OpenAPI document at the root) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import IEDBAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with IEDBAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("EBV nuclear antigen", limit=3):
            print(c.primary_id, c.primary_label)

        ep = await adapter.get_concept_details("IEDB_EPITOPE:1309147")
        print(ep.primary_label, ep.source_data["IEDB"]["tcell_assay_count"])

        for rel in await adapter.get_relationships("1309147", limit=8):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])
        for m in (await adapter.get_mappings("1309147"))[:4]:
            print(m["toSource"], m["toId"])


asyncio.run(main())
```

Output (abridged):

```
IEDB_EPITOPE:350 AAPAQPPPGVINDQQLHHLP
IEDB_EPITOPE:130 AAFDRKSDAK
IEDB_EPITOPE:429 AASEDDPQSGPVEEN
YLQPRTFLL 267
has_source_antigen UNIPROT:P0DTC2 Spike glycoprotein
has_source_organism NCBITaxon:2697049 SARS-CoV2
has_source_organism NCBITaxon:9606 Homo sapiens (human)
has_host_organism Homo sapiens (human) Homo sapiens (human)
has_tcell_assays tcell_search?structure_id=eq.1309147 T cell assays
has_mhc_ligand_assays mhc_search?structure_id=eq.1309147 MHC ligand assays
restricted_by_mhc_allele HLA-A*01:01 HLA-A*01:01
restricted_by_mhc_allele HLA-A*02:01 HLA-A*02:01
UniProt P0DTC2
NCBI Protein BCN86353.1
UniProt P0DTC2.1
NCBI Protein QII57161.1
```

## PostgREST syntax used

The IQ-API is a PostgREST service; tables (`epitope_search`, `antigen_search`, `tcell_search`, `bcell_search`, `mhc_search`, `epitope_export`, `epitope_summary`, `parent_proteins`, ...) are queried with URL parameters. The ones this adapter relies on:

| Syntax | Meaning |
|---|---|
| `select=a,b` | return only these columns (essential: see sizes below) |
| `limit=n` | row cap |
| `col=eq.X`, `col=in.(1,2,3)` | equality / membership |
| `col.ilike."*x*"` | case-insensitive substring (text columns only); values are double-quoted so commas and parentheses cannot break the filter |
| `or=(c1.ilike."*x*",c2.ilike."*x*")` | any of several conditions |
| `and=(or(...),or(...))` | every word must match somewhere |

Things that do **not** work, learned the hard way:

- `epitope_search?structure_descriptions=ilike.*spike*` fails with `operator does not exist: character varying[] ~~* unknown`. `structure_descriptions`, `source_organism_names`, `parent_source_antigen_names` and most other `epitope_search`/`antigen_search` columns are arrays, which take `cs.{...}` (whole-element match) rather than `ilike`; the `*_iri_search` arrays only take ontology ids.
- `Prefer: count=exact` took 53 s for the Spike epitope count (9,255), so no counts are requested. Assay counts come from the length of the `tcell_ids` / `bcell_ids` / `elution_ids` arrays of a single epitope.
- The iri and name arrays of one record are **sorted independently** (`source_organism_iris` listed `NCBITaxon:9606` beside the name "SARS-CoV2"), so ids and names are only paired when each list has a single element. Names are used on their own where no safe pairing exists (hosts, MHC alleles, diseases).

## Searching

`search_concepts(query, limit)`:

| Query | Lookup |
|---|---|
| `IEDB_EPITOPE:1309147`, `IEDB:1309147`, `1309147` | `epitope_search?structure_id=eq.1309147` |
| `P0DTC2`, `UNIPROT:P0DTC2` | `antigen_search` (returns the antigen concept) |
| `YLQPRTFLL` (all-caps amino acids, 6 to 60 letters) | exact `linear_sequence=eq.YLQPRTFLL`; on a miss, falls through to text search |
| anything else | text search |

Free text goes through `epitope_export`, a flat table with one row per epitope, source molecule and organism, using `ilike` over `epitope__name`, `epitope__source_molecule`, `epitope__source_organism` and `epitope__species`. Every word (up to four) must match one of those columns, so `SARS-CoV-2 spike` means "SARS-CoV-2 somewhere and spike somewhere". Short names are expanded: `SARS-CoV-2`/`covid` to `SARS-CoV2`, `SARS-CoV-2`, `coronavirus 2`; `EBV`/`HHV-4` to `Epstein-Barr`, `gammaherpesvirus 4`; `CMV`, `HHV-6`, `HSV`, `VZV`, `HIV`, `MERS` likewise. The matching epitope ids (de-duplicated) are then fetched from `epitope_search` with a light `select` and returned in the order the export gave them. Results are not ranked, and one epitope may appear under several organisms, so fewer than `limit` distinct epitopes can come back.

Each result is a `MOLECULAR_ENTITY` concept labelled with the peptide (or the residue list for discontinuous epitopes), with `categories` set to the structure type, `identifiers` for `UNIPROT` and `NCBITAXONOMY`, and a generated one-line definition.

## Concept details

`get_concept_details` returns the same concept with the assay and context fields and the IEDB text summary appended to `definitions` (a separate `epitope_summary` request, skipped if it fails). `source_data[IEDB]` adds `tcell_assay_count`, `bcell_assay_count`, `mhc_ligand_assay_count`, `mhc_classes`, `mhc_alleles`, `diseases`, `hosts`, `pdb_ids`, `pubmed_count` and `epitope_structures_defined`. For an antigen it returns a `PROTEIN` concept with the UniProt id, source organism and alternative names; antigen epitope lists are not fetched because `structure_ids` for Spike is 780 KB.

## Relationships

`get_relationships(concept_id, limit=50)` for an epitope (one request):

| `relation_label` | Content |
|---|---|
| `has_source_antigen` | reference-proteome antigen (`UNIPROT:P0DTC2`), then each curated record (`UNIPROT:` / `GENPEPT:` accession) with `starting_position`, `ending_position`, `source_organism_name`. IEDB files some GenBank proteins under `UNIPROT:`; those are re-labelled `GENPEPT:` |
| `has_source_organism` | NCBITaxon ids of the antigen records (IEDB's internal `taxon:` strain ids are skipped) |
| `has_host_organism` | organisms in which the response was measured |
| `has_tcell_assays` / `has_bcell_assays` / `has_mhc_ligand_assays` | one entry per assay type with `count`; `related_id` is the IQ-API query that lists the assays (`tcell_search?structure_id=eq.N`) |
| `restricted_by_mhc_allele` | MHC allele names (HLA-A*02:01, ...) from T cell and MHC-ligand data; includes IEDB's `human`/`mouse` placeholders |
| `associated_with_disease` | diseases the epitope was studied in (COVID-19, ...) |

For an antigen id only `has_source_organism` is returned.

## Mappings

`get_mappings` returns `UniProt` (accessions, with version suffix for curated records), `NCBI Protein` (GenBank accessions), `NCBITaxon` (`NCBITaxon:2697049`), `PDB` (upper-cased), `ChEBI` and `PubMed` (capped at 25; popular epitopes have 80 or more) for an epitope, and `UniProt` plus `NCBITaxon` for an antigen.

## Rate limits, licence and errors

No limit is published; requests are spaced 0.5 s apart and use the shared retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). A PostgREST error object (for example the array `ilike` error) is raised internally and the interface methods return `[]` / `None`. The per-request timeout is 60 s. IEDB data is free to use with attribution; cite Vita et al., *Nucleic Acids Res.* (the current IEDB paper) and see https://www.iedb.org/terms_of_use_v3.php.

## Caveats

- Text search is a table scan: 1 to 3 s when matches are plentiful (`spike`, `EBV`), 6 to 15 s when few rows match, and 8.5 s for a query with no matches. Narrow queries are slower than broad ones.
- No ranking: the first rows are whatever PostgreSQL returns, not the best-studied epitopes.
- Old strain-specific records and cross-species duplicates make organism counts higher than the number of distinct epitopes.
- `epitope__synonyms` is not searched (it made the filter slower).

## Live verification (2026-10-08)

`knowledge-lookup check IEDB` passes. Measured: `eq`/`in` look-ups 0.4 to 2 s; `search_concepts("YLQPRTFLL")` 0.4 s, `"spike"` 2.7 s, `"EBV nuclear antigen"` 1.6 s, `"SARS-CoV-2 spike"` 1.0 s; `get_concept_details` 5 s (4.5 s of it the summary request); `get_relationships` and `get_mappings` about 0.2 to 1 s each (one 7 KB request). Light epitope rows are about 0.5 KB each; the single-epitope detail row for a popular SARS-CoV-2 epitope is 7 KB.

## See also

- [UniProt adapter](../core/uniprot_adapter.md), [NCBI Taxonomy adapter](../ontologies/ncbitaxonomy_adapter.md)
- [All adapters](../README.md)
