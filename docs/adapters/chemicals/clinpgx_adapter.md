---
description: ClinPGx/PharmGKB pharmacogenomic genes, drugs, variants and haplotypes with clinical annotations, CPIC/DPWG guidelines and drug labels (CC BY-SA 4.0, citation required).
---

# ClinPGx (PharmGKB) adapter

Queries the ClinPGx API (the successor of PharmGKB) for pharmacogenes, drugs, variants and star-allele haplotypes, and links genes and drugs through clinical annotations, CPIC / DPWG dosing guidelines and annotated drug labels. Typical questions: which drugs have pharmacogenomic evidence for CYP2D6, which genes matter for codeine, is there a CPIC guideline, does the FDA label require testing.

> **Licence and citation.** ClinPGx data is licensed **CC BY-SA 4.0**. You must give appropriate credit to ClinPGx/PharmGKB, link the licence and indicate changes; anything derived that you distribute must carry the same licence; the data may not be sold. See the [data usage policy](https://www.clinpgx.org/page/dataUsagePolicy) and the [licence summary](https://blog.clinpgx.org/changes-to-pharmgkb-data-licensing/). Cite e.g. Whirl-Carrillo M et al., *Pharmacogenomics knowledge for personalized medicine*, Clin Pharmacol Ther 2012;92(4):414-417, and https://www.clinpgx.org/. Every concept carries a `license` note in `source_data`. ClinPGx also asks heavy users to contact api@clinpgx.org.

| | |
|---|---|
| Source | `KnowledgeSource.CLINPGX` |
| Class | `knowledge_lookup.adapters.ClinPGxAdapter` |
| Requires | none |
| Identifiers | PA ids: `PA128` (gene CYP2D6), `PA449088` (drug codeine), `PA166156104` (variant rs3892097), `PA165816579` (haplotype CYP2D6*4); `CLINPGX:PA128` and `PHARMGKB:PA128` accepted |
| Upstream API | `https://api.clinpgx.org/v1/data` |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ClinPGxAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ClinPGxAdapter(LookupConfig()) as adapter:
        gene = (await adapter.search_concepts("CYP2D6"))[0]
        print(gene.primary_id, gene.primary_label, gene.concept_type)   # PA128 CYP2D6 GENE

        for rel in (await adapter.get_relationships("PA449088", limit=2)):   # codeine
            print(rel["relation_label"], rel["related_name"], rel.get("level_of_evidence"),
                  rel.get("guideline_source"), rel.get("testing_level"))

        print([(m["toSource"], m["toId"]) for m in await adapter.get_mappings("PA449088")][:6])


asyncio.run(main())
```

Output (live, October 2026):

```
PA128 CYP2D6 GENE
has_clinical_annotation CYP2D6 1A None None
has_clinical_annotation ABCB1 3 None None
has_guideline COMT None CPIC None
has_guideline CYP2D6 None CPIC None
has_label Annotation of FDA Drug Label for codeine and CYP2D6 None None Actionable PGx
has_label Annotation of Swissmedic Drug Label for codeine and CYP2D6 None None Actionable PGx
[('ATC', 'N02AA59'), ('ATC', 'N02AA79'), ('ATC', 'R05DA04'), ('CHEBI', 'CHEBI:16714'), ('ChemSpider', '4447447'), ('DRUGBANK', 'DB00318')]
```

## Searching

The API has **no free-text search**. Lookups are exact and **case sensitive** (`cyp2d6` and `CODEINE` return 404), so `search_concepts(query, limit)` decides what the text is and retries spellings:

| Query looks like | Request |
|---|---|
| `rs3892097` | `variant?symbol=rs3892097` (lower-cased) |
| contains `*` (`CYP2D6*4`) | `haplotype?symbol=CYP2D6*4` (upper-cased) |
| a PA id | fetch that object |
| anything else | `gene?symbol=` upper case, then as typed; if no gene, `chemical?name=` lower case, then as typed |

At most four requests per query. Drug names are ClinPGx's generic names: `acetaminophen` matches, `paracetamol` and trade names do not. Search results come from the default view (no cross-references); `get_concept_details` returns the full record.

## Concepts

`get_concept_details("PA128")` fetches `<type>/<id>?view=max`. The type of a PA id is not encoded, so an unseen id is probed against gene, chemical, variant and haplotype (cheapest guess first, remembered afterwards; an unknown id costs four requests).

| Object | `concept_type` | `primary_label` | Also set |
|---|---|---|---|
| gene | `GENE` | symbol | `synonyms` (name, aliases), `categories` (`CPIC gene`, `VIP Tier 1`), `definitions` (VIP summary, tags stripped, 600 characters) |
| chemical | `DRUG` | name | `synonyms` (generic and trade names), `categories` (`Prodrug`, ...) |
| variant, haplotype | `MOLECULAR_ENTITY` | rs number / star allele | `synonyms` |

`identifiers` combine the ClinPGx id (with link) with the cross-references that have a `KnowledgeSource` equivalent (HGNC, ENSEMBL, NCBI, UNIPROT, OMIM, CTD, DRUGBANK, PUBCHEM, CHEBI, MESH, RXNORM, UMLS, KEGG, DBSNP, CLINVAR). `source_data[CLINPGX]` holds the scalar fields of the record plus `kind` and `license`.

## Relationships

`get_relationships(concept_id, limit=25)`; `limit` caps each relation label.

| From | Label | To | Extra keys |
|---|---|---|---|
| gene, drug | `has_clinical_annotation` | drug / gene | `level_of_evidence` (best of 1A, 1B, 2A, 2B, 3, 4 across annotations), `phenotype_categories` (`Dosage`, `Efficacy`, `Toxicity`, `Metabolism/PK`, ...), `annotation_count`, `annotation_ids` (first five) |
| gene, drug | `has_guideline` | drug / gene | `guideline_source` (`CPIC`, `DPWG`, `CPNDS`, `RNPGx`), `guideline_name`, `guideline_id`, `dosing_information` |
| drug | `has_label` | label annotation | `label_source` (FDA, EMA, Swissmedic, PMDA, ...), `testing_level` (e.g. `Actionable PGx`), `biomarker_status`, `prescribing_genes` |
| gene | `has_haplotype` | star allele | `reference_allele` |
| haplotype | `haplotype_of` | gene | |
| variant | `located_in_gene` | gene | |

Clinical annotations are aggregated per gene-drug pair and sorted by evidence level; guideline edges list CPIC before DPWG. A multi-drug guideline (for example the CPIC beta-blocker guideline) yields one edge per drug.

Cost of a gene's relationships (CYP2D6, measured): 4 requests, about 2.6 s. The API has no paging or field selection, so the clinical annotation call returns all 122 CYP2D6 annotations (223 KB with `view=min`) and the guideline call all 71 guidelines (about 0.9 MB, because guidelines carry their full text). Cache results on your side if you loop over many genes.

## Mappings

`get_mappings(concept_id)` converts `crossReferences` (genes, variants) and `linkOuts` (drugs) to mapping rows with `fromSource` `ClinPGx`:

- gene: HGNC, Ensembl, NCBI Gene, UniProt, OMIM, CTD, GeneCards, PharmVar
- drug: DrugBank, PubChem Compound, ChEBI, MeSH, RxNorm, UMLS, KEGG, ChemSpider, IUPHAR/Guide to Pharmacology, NDF-RT and **ATC codes** (`mappingType` `atc_code`; codeine lists N02AA59, N02AA79, R05DA04)
- variant: dbSNP, ClinVar

GenBank/RefSeq entries, ClinicalTrials.gov ids, tags and URLs are not identifiers of the same entity and are skipped.

## Rate limits and quirks

- **2 requests per second** (the API answers 429 above that); requests are spaced at about 1.8/s and the shared retry layer backs off on 429.
- The API page states that parameters and responses "may change at any time" until the final release: re-check after upgrades. `api.pharmgkb.org` no longer resolves; use `api.clinpgx.org`.
- Cloudflare blocks the default `Python-urllib` User-Agent (error 1010); the adapter's own User-Agent works, but a quick `urllib` test script will get a 403.
- Not found is HTTP 404 `{"status": "fail", ...}`; the adapter treats it as "no results". `view=min` / `view=max` are supported on every endpoint.
- `check CLINPGX` (default query `CYP2D6`) passes.

## See also

- [HGNC adapter](../proteins/hgnc_adapter.md), [DrugBank adapter](drugbank_adapter.md), [RxNorm adapter](rxnorm_adapter.md), [DGIdb adapter](dgidb_adapter.md)
- [All adapters](../README.md)
