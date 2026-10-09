---
description: Enrichr gene-set enrichment: which pathways, GO terms, phenotypes and diseases a list of genes is over-represented in (uploads the list to maayanlab.cloud).
---

# Enrichr adapter

[Enrichr](https://maayanlab.cloud/Enrichr/) is a **tool-like** source: it does not look up a concept, it takes a **list of genes** and reports which gene sets (pathways, GO terms, mouse and human phenotypes, diseases, ...) contain more of them than expected by chance. This adapter runs that enrichment against a small curated set of libraries and returns the best terms as concepts.

> **Privacy: the genes are uploaded to maayanlab.cloud, and Enrichr stores uploaded lists.** Every enrichment call sends your gene list to the Ma'ayan Lab server (Icahn School of Medicine at Mount Sinai) with `POST /Enrichr/addList`; the list stays there, retrievable through the returned `userListId`/`shortId`. Do not send gene lists derived from identifiable or restricted-access cohorts. The adapter caps a list at 500 genes, sends only a constant description (never the genes or the query), reuses an upload for identical lists within one adapter instance, and never logs gene symbols at INFO. Single-gene calls (`get_relationships`) send the symbol in a `GET` URL instead. Contrast with **g:Profiler** (not implemented here), which answers a stateless request without storing a list.

| | |
|---|---|
| Source | `KnowledgeSource.ENRICHR` |
| Class | `knowledge_lookup.adapters.EnrichrAdapter` |
| Requires | none (public, keyless) |
| Identifiers | a gene symbol or a list (`IL6 TNF IL1B`) as the search query; concept ids are `<library>::<term>` (`KEGG_2026::MALARIA`) |
| Upstream API | `https://maayanlab.cloud/Enrichr` |
| Optional env | `ENRICHR_LIBRARIES`: comma-separated library names replacing the default set |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import EnrichrAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with EnrichrAdapter(LookupConfig()) as adapter:
        genes = "IL6 TNF IL1B CXCL8 CRP IFNG IL10"
        for concept in await adapter.search_concepts(genes, limit=4):
            data = concept.source_data[adapter.get_source()]
            print(concept.primary_id, data["adjusted_p_value"], data["overlapping_genes"])

        rows = await adapter.enrich(genes, ["KEGG_2026"], limit=2)
        print([(r["term"], r["odds_ratio"]) for r in rows])


asyncio.run(main())
```

Output (live, 2026-10-09):

```
GO_Biological_Process_2025::Regulation of Membrane Protein Ectodomain Proteolysis (GO:0051043) 3.2e-08 ['IL10', 'IFNG', 'IL1B', 'TNF']
KEGG_2026::MALARIA 1.1e-13 ['IL10', 'IL6', 'CXCL8', 'IFNG', 'IL1B', 'TNF']
Reactome_Pathways_2024::Interleukin-10 Signaling 8.8e-11 ['IL10', 'IL6', 'CXCL8', 'IL1B', 'TNF']
WikiPathways_2024_Human::Post COVID Neuroinflammation WP5485 1.2e-15 ['IL10', 'IL6', 'CXCL8', 'IFNG', 'IL1B', 'TNF']
[('MALARIA', 2720.318181818182), ('AMOEBIASIS', 1270.1489361702127)]
```

## Gene lists

`search_concepts(query)` treats the query as a gene list: it is split on commas, semicolons and whitespace, upper-cased (Enrichr matches case-insensitively) and de-duplicated. A query is **not** sent when it does not look like genes: a token that is not symbol-shaped, or a query made only of plain lower-case words (`long covid`), returns `[]` without any network call. At least one token needs a capital, a digit or a hyphen, so `il6 tnf` is accepted and `tnf crp` is not. Lists longer than 500 genes are truncated. Unknown symbols are ignored by Enrichr; the match is on gene symbols (human; mouse symbols are mapped by upper-casing).

A single gene gives weak statistics (every term containing it, with modest p-values): use two or more genes for enrichment. For a single gene's gene-set memberships use `get_relationships`.

## Libraries

The default set (override with `ENRICHR_LIBRARIES`), all verified in `GET /datasetStatistics` on 2026-10-09:

| Library | Content |
|---|---|
| `GO_Biological_Process_2025` | GO biological process |
| `KEGG_2026` | KEGG pathways |
| `Reactome_Pathways_2024` | Reactome pathways |
| `WikiPathways_2024_Human` | WikiPathways |
| `MGI_Mammalian_Phenotype_Level_4_2024` | mouse knockout phenotypes (MP) |
| `Human_Phenotype_Ontology` | human phenotypes (HPO) |
| `Jensen_DISEASES_Curated_2025` | text-mined/curated gene-disease associations |

Library names carry a year and are retired over time (the catalogue holds 228 libraries, including older `KEGG_2021_Human`, `Reactome_2022`, `WikiPathway_2023_Human`, `GO_Biological_Process_2023`, `MGI_Mammalian_Phenotype_Level_4_2021` and `Jensen_DISEASES`). A name that no longer exists answers `{}` and silently yields no rows, so `await adapter.list_libraries()` returns the live catalogue (`libraryName`, `numTerms`, `genesPerTerm`).

## Enrichment

- `search_concepts(query, limit=20)` takes `ceil(limit / n_libraries)` best terms per library (sorted by adjusted p-value, then p-value), interleaves them library by library so pathways, phenotypes and diseases all appear, and cuts the result to `limit`. Seven libraries cost one upload plus seven `enrich` calls: about 3 - 4 s.
- `enrich(genes, libraries=None, limit=10)` returns the structured rows (top `limit` **per library**): `library`, `rank`, `term`, `term_id` (GO/HP/MP/WikiPathways id parsed from the term name when present), `p_value`, `adjusted_p_value`, `odds_ratio`, `combined_score`, `overlapping_genes`, `n_overlap`, `n_input_genes`. `genes` may be a list or a string in the same format as the search query. A library that errors is skipped; an upload failure returns `[]`.

Concepts: `primary_id = "<library>::<term>"`, `primary_label` the term, `concept_type` `PATHWAY`, `BIOLOGICAL_PROCESS`, `PHENOTYPE` or `DISEASE` by library, `categories = [library]`, `semantic_types = ["gene set"]`, `confidence_score` 0.9 when the adjusted p-value is below 0.05 and 0.4 otherwise, and everything above in `source_data[ENRICHR]` together with an `evidence_note`. The value is over-representation of your gene list, not per-gene evidence, and Enrichr's "odds ratio" column is called "z-score" in the older API documentation (the observed values are large positive odds ratios; for KEGG MALARIA with 6 of 7 input genes and a 50-gene set an odds ratio of about 2,700 matches a ~20,000-gene background).

## Details and relationships

- `get_concept_details("KEGG_2026::MALARIA")` returns the **member genes** of a term in `source_data[ENRICHR]` (`genes`, capped at 500, `n_genes`, `truncated`). Enrichr has no per-term endpoint, so the whole library is downloaded as text once and cached in memory (the last three libraries): KEGG 0.23 MB, WikiPathways 0.25 MB, HPO 0.39 MB, Reactome 0.89 MB, MGI MP 1.3 MB, GO BP 1.4 MB; 0.9 - 6.4 s. Term names are matched case-insensitively.
- `get_relationships("BRCA1")` returns `member_of` edges from `GET /genemap`, which lists the terms of **all 231 libraries** that contain the gene (about 0.9 MB, 1.7 s warm, up to 11 s cold). The result is filtered to the configured libraries, capped at 25 terms per library and cached per gene. This is **membership, not enrichment**. `get_relationships("KEGG_2026::MALARIA")` returns up to 100 `has_member` gene edges from the cached library.
- `get_mappings` is not implemented: Enrichr has no identifier mappings.

## Rate limits, licence, errors

No limit is published, but the front end answers HTTP 429 to bursts (about 6 `addList` uploads in 2 s triggered it). Requests are spaced 0.3 s apart and the shared retry backs off on 429. Errors are logged **without the gene list** (only the exception type) and `[]`/`None` returned.

Enrichr is a Ma'ayan Lab web service; cite Chen et al. 2013 (BMC Bioinformatics), Kuleshov et al. 2016 (NAR) and Xie et al. 2021 (Curr Protoc), and follow the [Enrichr terms](https://maayanlab.cloud/Enrichr/help#terms) (the individual libraries keep the licence terms of their sources, for example KEGG).

## Caveats

- The upload endpoint requires `multipart/form-data` (the default urlencoded form is rejected with HTTP 400), answers with content type `text/html` and an unknown `userListId` with HTTP 400; the adapter handles all three.
- Background is Enrichr's fixed gene universe (~20,000 genes), not your measured genes: for RNA-seq or metabolomics-linked gene sets tested against a custom background, a method with background support is better.
- Libraries differ in size and term specificity; adjusted p-values are only comparable within a library.
- Gene-set libraries are not disease evidence on their own: use them to generate hypotheses, then check the literature.

## Live verification (2026-10-09)

- `knowledge-lookup check ENRICHR` passes (search `BRCA1`, term details, term members).
- Seven-gene cytokine list, seven libraries: 2.9 s; `datasetStatistics` 69 KB, 228 libraries; `enrich` for KEGG 12 KB (89 terms with overlap), HPO 6 KB; `addList` 75 bytes in 0.5 - 1.2 s.
- `genemap` for BRCA1: 0.86 MB; term members for KEGG MALARIA: 50 genes.
- A single-gene search for `BRCA1` once took 31 s because the shared retry backed off after HTTP 429 from earlier test bursts.

## See also

- [Reactome adapter](reactome_adapter.md), [KEGG adapter](kegg_adapter.md), [Gene Ontology adapter](../phenotypes/geneontology_adapter.md)
- [All adapters](../README.md)
