---
description: Human Protein Atlas gene expression by tissue and blood immune cell type, plasma protein and subcellular location (attribution required).
---

# Human Protein Atlas adapter

Looks up human genes in the [Human Protein Atlas](https://www.proteinatlas.org) (HPA) and summarises where they are expressed: RNA tissue specificity and distribution, the tissues with the highest nTPM, expression in blood immune cell types (monocytes, T, B and NK cells, dendritic cells, granulocytes), whether the protein is a plasma protein, its blood concentration and its subcellular location. Useful for ME/CFS and Long COVID questions such as "which immune cells express this gene" or "is this a tissue-restricted or blood-borne protein".

> **Licence and attribution.** HPA's licence page (`https://www.proteinatlas.org/about/licence`, checked live) states Creative Commons Attribution 4.0 for all copyrightable parts of the database; earlier releases and many references say CC BY-SA 3.0. In either case you must attribute the Human Protein Atlas (cite Uhlen et al., *Tissue-based map of the human proteome*, Science 2015, plus the HPA version you used) and respect any third-party constraints on included sub-data. If your downstream use falls under share-alike terms of an older release, check which release you used.

| | |
|---|---|
| Source | `KnowledgeSource.HUMANPROTEINATLAS` |
| Class | `knowledge_lookup.adapters.HumanProteinAtlasAdapter` |
| Requires | none |
| Identifiers | Ensembl gene id `ENSG00000012048`; approved symbols such as `BRCA1` are accepted wherever an id is |
| Upstream API | `https://www.proteinatlas.org/api/search_download.php` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import HumanProteinAtlasAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


async def main():
    async with HumanProteinAtlasAdapter(LookupConfig()) as adapter:
        il6 = await adapter.get_concept_details("IL6")
        data = il6.source_data[KnowledgeSource.HUMANPROTEINATLAS]
        print(il6.primary_id, data["rna_tissue_specificity"], data["plasma_protein"])
        print(data["top_tissues_ntpm"][:2], data["top_blood_cells_ntpm"][:2])

        for edge in await adapter.get_relationships("CD4", limit=5):
            print(edge["relation_label"], edge["related_name"], edge["ntpm"], edge["enriched"])


asyncio.run(main())
```

Real output for IL6 (HPA, fetched 2026-10-06):

```
ENSG00000136244 Tissue enhanced True
[{'name': 'urinary bladder', 'ntpm': 256.4}, {'name': 'adipose tissue', 'ntpm': 187.7}] [{'name': 'naive B-cell', 'ntpm': 5.2}, {'name': 'memory B-cell', 'ntpm': 4.1}]
```

For CD4 the enriched blood cells are plasmacytoid dendritic cells (264 nTPM), classical and non-classical monocytes, T-reg and CD4 memory/naive T cells.

## Requests used

Everything uses the keyless `search_download.php` endpoint, which returns only the columns you ask for. Latency was 0.2-0.4 s per call.

| Call | Request | Response size |
|---|---|---|
| search / symbol resolution | `search=<text>`, summary columns `g,gs,eg,gd,up,rnats,rnatd,rnatsm,rnabcs,rnabcd,rnabcsm,scl` | ~0.5 KB per gene; free text, so a broad term returns many genes (`IL6`: 20 genes, 10 KB; `CD4`: 84 KB) |
| details, relationships | `search=<ENSG id>` (exactly one hit) with the summary plus `chr,chrp,pc,di,evih,secl,blconcia,blconcms`, 50 `t_RNA_<tissue>` and 19 `blood_RNA_<cell>` columns | ~4 KB |
| mappings | `search=<ENSG id>`, summary columns | ~0.7 KB |

The per-gene `https://www.proteinatlas.org/<ENSG>.json` (10 KB, all fields) and `.xml` (1.7 MB for BRCA1) endpoints work but the JSON only carries nTPM for the enriched tissues and cells (no full per-tissue table) and the XML is far larger, so neither is used. Responses are cached in the shared adapter cache for 6 hours.

## Searching

`search_concepts(query, limit)` is HPA's free-text search over gene symbols, synonyms and descriptions; `limit` is applied client-side. Results are re-ranked so an exact symbol comes first (confidence 1.0), then an exact synonym (0.9), then the rest (0.6). Search concepts carry the summary-column data (specificity categories, enriched tissues and blood cells, subcellular location) but not the full nTPM tables.

## Concept details

`get_concept_details(concept_id)` accepts an Ensembl id (also with a version suffix, `ENSG...` / `HPA:` / `ENSEMBL:` prefixes) or an approved gene symbol or synonym. A symbol costs one extra search request to resolve it, and only an *exact* symbol or synonym match resolves (no guessing among free-text hits).

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | Ensembl gene id / HGNC symbol |
| `concept_type` | `GENE` |
| `synonyms`, `definitions` | symbol and aliases; HPA gene description |
| `categories` | HPA protein classes (e.g. `Plasma proteins`, `CD markers`) |
| `identifiers` | `ENSEMBL`, `UNIPROT` (each accession), `HUMANPROTEINATLAS` |
| `source_data[HUMANPROTEINATLAS]` | compact expression summary, below |

`source_data` keys: `rna_tissue_specificity` (e.g. "Tissue enhanced", "Low tissue specificity"), `rna_tissue_distribution` ("Detected in all"), `rna_tissue_enriched_ntpm` (HPA's enriched/enhanced tissues, can name tissue groups such as "lymphoid tissue"), `top_tissues_ntpm` (top 5 of 50 tissues), `rna_blood_cell_specificity` / `rna_blood_cell_distribution` / `rna_blood_cell_enriched_ntpm`, `top_blood_cells_ntpm` (top 5 of 18 immune cell types; the pooled "total PBMC" sample is excluded), `plasma_protein` (protein class "Plasma proteins"), `blood_concentration_pg_per_l` (immunoassay / mass spectrometry, when measured), `secretome_location`, `subcellular_location`, `protein_class`, `disease_involvement`, `evidence`, `chromosome`, `position`. All expression values are consensus RNA nTPM, a transcript measure, not protein abundance.

## Relationships

`get_relationships(concept_id, limit=10)` returns two edge types, with `limit` applying to each:

- `expressed_in` (gene -> tissue) with `related_type="tissue"`
- `expressed_in_cell_type` (gene -> blood immune cell type) with `related_type="immune cell (blood)"`

Each edge has `related_id` = `related_name` = HPA's name (HPA gives no ontology ids; map names to UBERON / Cell Ontology yourself), `ntpm`, `enriched`, `specificity` (HPA's category for the gene), `evidence` and `source`. Tissues/cells in HPA's enriched/group-enriched/enhanced list come first with `enriched=True`; the remaining slots are filled with the highest-expressed others at `enriched=False` (nTPM >= 1). An enriched entry that is an HPA tissue *group* rather than a single tissue ("lymphoid tissue") carries `scope="tissue group"`. A broadly expressed gene such as BRCA1 has no enriched entries, so its edges are simply the top-expressed tissues.

## Mappings

`get_mappings` returns the Ensembl gene id (exact), every UniProt accession (`xref`) and the HGNC approved symbol (`mappingType="symbol"`, confidence 0.95). HPA does not return numeric HGNC ids; its gene name is the HGNC symbol, so that mapping is by symbol.

## Quirks

- HPA publishes tissues `endometrium`, `skin` and `stomach` with a `_1` suffix in column names; the adapter returns plain names.
- The 50 tissue and 19 blood-cell column lists are HPA's current set, hard-coded in the module. The API silently omits an unknown column, so a renamed tissue would just be missing from results.
- Free-text search: `CD4` also returns genes that merely mention CD4 in their description. Use `ENSG` ids when you need exactly one gene.
- Missing genes return an empty JSON array, which maps to `[]` / `None`.

## Rate limits and errors

No documented limit; the adapter issues one request per call and caches. Retries and the circuit breaker follow the shared policy (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). Errors are logged; search returns `[]`, details return `None`.

## See also

- [HGNC adapter](hgnc_adapter.md), [Ensembl adapter](ensembl_adapter.md), [UniProt adapter](../core/uniprot_adapter.md)
- [All adapters](../README.md)
