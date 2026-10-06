---
description: Comparative Toxicogenomics Database chemical-gene-disease links from CTD bulk files (non-commercial use, citation required).
---

# CTD adapter

Reads the Comparative Toxicogenomics Database (CTD) bulk reports to link chemicals, genes and diseases: curated chemical-gene interactions (with the interaction action such as `increases_expression`), chemical-disease relations split into therapeutic and marker/mechanism evidence, and gene-disease relations. Every edge carries PubMed ids where CTD lists them.

| | |
|---|---|
| Source | `KnowledgeSource.CTD` |
| Class | `knowledge_lookup.adapters.CTDAdapter` |
| Requires | none (downloads CTD report files on first use; set `CTD_DATA_DIR` to use your own copy) |
| Identifiers | chemicals `MESH:D001241` (or a CAS number); diseases `MESH:D003920`, `OMIM:264300`; genes `NCBIGene:672` |
| Upstream | `https://ctdbase.org/reports/` |

## Licence and citation (read this before using results)

CTD is free for research use but subject to <https://ctdbase.org/about/legal.jsp>. The header of every report states these terms:

1. Publications, databases and software that use or rely on CTD data must **cite CTD** (<https://ctdbase.org/about/publications/#citing>).
2. Online applications must **hyperlink** from the contexts that use CTD data to the CTD data pages (<https://ctdbase.org/help/linking.jsp>). Concepts from this adapter carry such a link in their `MESH`/`NCBI` identifier URLs.
3. You must **notify CTD** and describe your use of the data (<https://ctdbase.org/help/contact.go>).
4. CTD must be given periodic access to your publication of its data.

Use for commercial purposes needs a separate licence from CTD. The adapter does not enforce any of this; it is the user's responsibility.

## Why bulk files and not the web query

CTD's batch query service (`https://ctdbase.org/tools/batchQuery.go?inputType=chem&inputTerms=aspirin&report=...&format=json`) is not usable from scripts: as of 2026-10 it answers HTTP 302 with an interstitial HTML page that loads an ALTCHA proof-of-work widget (a bot challenge). The adapter does not try to defeat the challenge. The bulk reports are served normally (HEAD and `Range` requests verified, release of 2026-09-29), so the adapter streams those.

| File | Size | Used for |
|---|---|---|
| `CTD_chemicals.csv.gz` | 10.5 MB | chemical concepts, search, mappings |
| `CTD_diseases.csv.gz` | 1.8 MB | disease concepts, search, mappings |
| `CTD_chem_gene_ixns.csv.gz` | 43.4 MB | chemical-gene interactions; gene ids and symbols |
| `CTD_chemicals_diseases.csv.gz` | 163.6 MB | chemical-disease relations |
| `CTD_genes.csv.gz` (optional) | 122.9 MB | gene names and synonyms |
| `CTD_genes_diseases.csv.gz` (optional) | 3.2 GB | gene-disease relations |

Nothing is downloaded at import or construction. The first call that needs a file fetches it through `knowledge_lookup.utils.dataset_cache.ensure_dataset` (kept gzipped, refreshed after 60 days, never partially cached) into `$CTD_DATA_DIR` or `~/.cache/knowledge_lookup/datasets/ctd`. The two optional files are only used when they are already in that directory or when `CTD_DOWNLOAD_GENES=1` / `CTD_DOWNLOAD_GENES_DISEASES=1` is set; without `CTD_genes_diseases.csv.gz` gene-disease edges are simply absent. To work offline, place the files in `CTD_DATA_DIR`.

Each lookup streams the needed file once with a cheap substring pre-filter (a few seconds for the 164 MB file; results are memoised per adapter instance). A first search therefore costs about 12 MB of downloads (chemicals and diseases); the first relationship lookup for a chemical adds 207 MB (interactions plus chemical-disease), for a gene 43 MB, for a disease 164 MB.

> Verification status: format and parser were verified against real excerpts of every file (first 40 KB via HTTP Range) and the adapter was run end to end on gzip files built from them; the full files were not downloaded.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import CTDAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with CTDAdapter(LookupConfig()) as adapter:
        (chem,) = await adapter.search_concepts("10074-G5", limit=1)
        print(chem.primary_id, chem.primary_label)
        for edge in await adapter.get_relationships(chem.primary_id, limit=3):
            print(edge["relation_label"], edge["related_name"], edge["organism"], edge["pmids"])


asyncio.run(main())
```

Output (built from the real file excerpts):

```
MESH:C534883 10074-G5
decreases_expression MYC Homo sapiens ['26036281', '32184358']
affects_reaction AR Homo sapiens ['32184358']
increases_expression AR Homo sapiens ['32184358']
```

## Searching and details

`search_concepts` scans the chemical and disease files for names and synonyms and ranks exact name, exact synonym, prefix, substring, synonym substring. Ids resolve directly (`MESH:`, bare `D001241`, `OMIM:`, `NCBIGene:`, CAS numbers). A gene-symbol-like query (upper case or containing a digit, e.g. `IL6`) additionally looks for an exact symbol: in `CTD_genes.csv.gz` if present, else in the interaction file (id and symbol only, no gene name or synonyms).

A `MESH:` id is looked up among diseases first, then chemicals. An `OMIM:` id resolves through the disease table to CTD's MeSH-keyed record (`OMIM:264300` returns `MESH:C537805`).

| Type | Fields filled |
|---|---|
| chemical (`CHEMICAL`) | synonyms (MeSH and curated), definition, parent MeSH ids in `parents`, MeSH and PubChem identifiers |
| disease (`DISEASE`) | synonyms, definition, parents, MeSH and OMIM identifiers, slim mappings as categories |
| gene (`GENE`) | symbol (label), gene name, synonyms, UniProt identifiers (full file only) |

## Relationships

`get_relationships(concept_id, limit=25)` interleaves the edge families so one large family cannot hide the others.

| Concept | Edges |
|---|---|
| chemical | gene interactions, labelled by the CTD action (`increases_expression`, `decreases_activity`, `affects_binding`, ...; `interacts_with` without an action), one per gene, action and organism; `therapeutic_for` and `marker_mechanism_for` diseases |
| disease | chemicals as `treated_by` and `marker_mechanism_chemical`; with `CTD_genes_diseases.csv.gz`, genes as `has_therapeutic_target_gene` and `has_marker_mechanism_gene` |
| gene | chemical interactions (action labels stated from the chemical's side) and, with `CTD_genes_diseases.csv.gz`, `therapeutic_target_for` / `marker_mechanism_for` diseases |

Only rows with direct curated evidence become disease edges; CTD's inferred associations (no `DirectEvidence`, inferred through a gene or chemical) are skipped. Every edge has `pmids` (at most 25 of `n_pmids`); interaction edges add `organism`, `organism_id` (human edges first), an example `interaction` sentence and `n_interactions`; disease edges add `direct_evidence` and `omim_ids`.

## Mappings

Chemicals: MeSH, CAS, PubChem CID, DSSTox (`DTXSID`), InChIKey. Diseases: MeSH and every alternate id CTD lists (OMIM, ...). Genes: NCBI Gene, UniProt, PharmGKB, BioGRID (the last three need the full genes file).

## Caveats

- CTD's chemical ids carry no `MESH:` prefix in the relation files; the adapter adds it. A MeSH id that is both a chemical and a disease resolves as the disease.
- Interaction and relation files use human, rodent and other organisms; edges keep the `organism` so you can filter.
- Errors (including a failed download) are logged; search and relationships return `[]`, details return `None`.

## See also

- [DGIdb adapter](dgidb_adapter.md), [ChEMBL adapter](../core/chembl_adapter.md)
- [All adapters](../README.md)
