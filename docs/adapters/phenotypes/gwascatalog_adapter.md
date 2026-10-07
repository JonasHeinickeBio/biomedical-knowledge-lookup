---
description: NHGRI-EBI GWAS Catalog traits and variant-trait associations (REST API v2, no key).
---

# GWAS Catalog adapter

Looks up traits (disease and phenotype terms the Catalog maps its studies to) and variants (rsIDs) in the NHGRI-EBI GWAS Catalog. Traits link to their strongest associated variants (p-value, risk allele, mapped genes, study accession and PMID); variants link back to their traits and mapped genes. Catalog data is released under CC0.

| | |
|---|---|
| Source | `KnowledgeSource.GWASCATALOG` |
| Class | `knowledge_lookup.adapters.GWASCatalogAdapter` |
| Requires | none |
| Identifiers | traits `MONDO:0005404`, `EFO:0004540`, `HP:0012378` (also `MONDO_0005404`); variants `rs1801270` |
| Upstream API | `https://www.ebi.ac.uk/gwas/rest/api/v2` |

> **The legacy API is gone in practice.** The "HAL" endpoints (`/gwas/rest/api/efoTraits/...`, `studies/search/findByDiseaseTrait`, `associations/search/findByEfoTrait`, `singleNucleotidePolymorphisms/{rs}/associations`) now answer HTTP 429 with the text "The legacy GWAS Catalog REST API has been deprecated ... and is now intentionally rate limited ahead of retirement". The adapter uses the v2 API instead. v2 is still HAL-flavoured JSON (`_embedded`, `_links`, `page`) but with flat resources, snake_case filters and `page`/`size` paging (`size` up to 500, documented limit 15 requests/s). The newer summary-statistics API is not used.

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import GWASCatalogAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with GWASCatalogAdapter(LookupConfig()) as adapter:
        (trait,) = await adapter.search_concepts("chronic fatigue syndrome")
        print(trait.primary_id, trait.primary_label)

        for edge in await adapter.get_relationships(trait.primary_id, limit=3):
            print(edge["related_id"], edge["p_value"], edge["mapped_genes"], edge["pmid"])

        for edge in await adapter.get_relationships("rs1801270"):
            print(edge["relation_label"], edge["related_id"], edge["related_name"])


asyncio.run(main())
```

Output (live, 2026-10):

```
MONDO:0005404 myalgic encephalomeyelitis/chronic fatigue syndrome
rs141691232 6.000000000000001e-13 ['LINC01419', 'TPM3P3'] 39024449
rs190241717 1e-11 ['HERPUD2', 'TBX20'] 39024449
rs189511601 3e-11 ['LRRC4C'] 39024449
associated_trait EFO:0005763 pulse pressure measurement
mapped_gene CDKN1A CDKN1A
```

## Searching

`search_concepts(query, limit)` calls `efo-traits?efo_trait=<query>` (case-insensitive substring match on the trait label) and ranks exact label matches first, then shorter labels. `chronic fatigue syndrome` finds the ME/CFS trait `MONDO:0005404`; `long covid` finds `MONDO:0100233` ("long COVID-19"); `fatigue` finds `HP:0012378` and `MONDO:0005404`. A query that is itself a trait id or an rsID is resolved directly. Variants are not searchable by free text.

Trait ids can be written `MONDO:0005404` or `MONDO_0005404`; the adapter returns the CURIE form and sends the underscore form to the API. `MONDO`, `DOID`, `Orphanet` and `OMIM` traits are typed `DISEASE`, everything else (`EFO`, `HP`, `OBA`, ...) `PHENOTYPE`.

## Concept details

- **Trait**: `efo-traits/{id}` plus two `size=1` calls for the study and association counts (`19 GWAS Catalog studies and 9 associations` for ME/CFS). The Catalog stores only the label and ontology URI for a trait, so there are no synonyms or definitions beyond that.
- **Variant**: `single-nucleotide-polymorphisms/{rsId}` (lower case rsID required). Type `MOLECULAR_ENTITY`; the definition summarises the consequence, GRCh38 position/cytoband, alleles and mapped genes (`missense_variant; chr6:36684194 (6p21.2); alleles C/A/T (forward); mapped genes CDKN1A`).

`get_concept_details` returns `None` for unknown ids (the API answers 404). Note that ids from the old v1 API may no longer exist: `EFO_0004540` (suggested for chronic fatigue) returns 404 on v2; `MONDO_0005404` is the current ME/CFS trait.

## Relationships

`get_relationships(concept_id, limit=25)` pages through `associations` sorted by p-value (strongest first, up to three pages of up to 500) and de-duplicates client-side.

| Concept | Edges |
|---|---|
| trait | `associated_variant` to each rsID, one edge per rsID (best p-value) |
| variant | `associated_trait` (one per trait, best p-value) and `mapped_gene` from the variant record |

Extra keys on association edges: `p_value`, `risk_allele` (`rs...-A`, `None` when the Catalog stores `?`), `effect_allele`, `risk_frequency`, `beta`, `ci`, `mapped_genes`, `study_accession` (GCST id), `pmid`, `reported_trait`, `related_type`.

## Mappings

`get_mappings` reports only what the Catalog knows: a trait maps to the same id in its home ontology (`toSource` `MONDO`, `HPO`, `EFO`, ...) and a variant to `dbSNP`. The Catalog has no trait cross-reference table; use [OLS](../core/ols_adapter.md) or OxO for real ontology cross-references.

## Rate limits and quirks

Latency measured live: 0.3-0.9 s per call, a trait lookup with counts about 0.8 s, a variant relationship lookup about 1 s. Uses the shared HTTP retry and circuit breaker. Errors are logged; search and relationships return `[]`, details return `None`.

## See also

- [ClinVar adapter](clinvar_adapter.md), [HPO adapter](hpo_adapter.md)
- [All adapters](../README.md)
