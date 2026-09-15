---
description: ClinVar variant records from NCBI, searched with Entrez query syntax.
---

# ClinVar adapter

Searches ClinVar through NCBI E-utilities and returns variant summaries: HGVS title, gene, variant type, clinical significance and conditions. Queries use Entrez syntax, so you can filter by gene, clinical significance and more.

| | |
|---|---|
| Source | `KnowledgeSource.CLINVAR` |
| Class | `knowledge_lookup.adapters.ClinVarAdapter` |
| Requires | none |
| Identifiers | ClinVar variation ID, e.g. `17661` (also `ClinVar:17661`, `VCV000017661`) |
| Upstream API | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (`db=clinvar`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import ClinVarAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with ClinVarAdapter(LookupConfig()) as adapter:
        # Entrez query syntax is passed through unchanged
        for concept in await adapter.search_concepts("BRCA1[gene] AND pathogenic[clinsig]", limit=3):
            print(concept.primary_id, concept.primary_label, concept.categories)

        variant = await adapter.get_concept_details("17661")
        print(variant.primary_label, variant.semantic_types)
        print(variant.categories)


asyncio.run(main())
```

Output:

```
ClinVar:4887763 NC_000017.10:g.(41234593_41242960)_(41243050_41243451)del ['clinical_significance:Pathogenic', 'review_status:criteria provided, single submitter', 'gene:BRCA1', 'condition:Hereditary breast ovarian cancer syndrome']
ClinVar:4887537 NC_000017.10:g.(41243050_41243451)_(41251898_41256138)del ['clinical_significance:Pathogenic', 'review_status:criteria provided, single submitter', 'gene:BRCA1', 'condition:Hereditary breast ovarian cancer syndrome']
ClinVar:4886868 GRCh38/hg38 17q21.31(chr17:43057598-43068066)x1 ['clinical_significance:Likely pathogenic', 'review_status:no assertion criteria provided', 'gene:BRCA1', 'condition:Breast-ovarian cancer, familial, susceptibility to, 1']
NM_007294.4(BRCA1):c.181T>G (p.Cys61Gly) ['single nucleotide variant', 'missense variant', 'non-coding transcript variant']
['clinical_significance:Pathogenic', 'review_status:reviewed by expert panel', 'gene:BRCA1', 'condition:Breast-ovarian cancer, familial, susceptibility to, 1']
```

## Searching

`search_concepts(query, limit)` runs `esearch.fcgi` with `retmax=min(limit, 20)`, then a single `esummary.fcgi` call for all IDs. A search returns at most 20 variants, newest IDs first. A plain term such as `BRCA1` matches all fields (other genes' variants can appear); use `BRCA1[gene]` to restrict to the gene.

| Field | Value |
|---|---|
| `primary_id` | `ClinVar:<uid>` |
| `primary_label` | summary title (HGVS expression) |
| `concept_type` | `MOLECULAR_ENTITY` |
| `semantic_types` | `obj_type` followed by the molecular consequences, e.g. `single nucleotide variant`, `missense variant` |
| `categories` | `clinical_significance:<classification>`, `review_status:<status>`, `gene:<symbol>`, `condition:<trait name>` (when present) |
| `identifiers` | one `CLINVAR` identifier (no URL) |
| `sources` | `['CLINVAR']` |
| `confidence_score` | `0.85` |
| `source_data[CLINVAR]` | full esummary record |

Classifications and conditions are read from `germline_classification`, the current esummary format. Somatic records add `oncogenicity:<classification>` and `clinical_impact:<classification>` categories when those classifications are filled. The legacy `clinical_significance` and top-level `trait_set` fields are still read for older payloads.

## Concept details

`get_concept_details(concept_id)` strips `ClinVar:` and `VCV` from the ID and calls `esummary.fcgi`, returning the same fields as search. Unknown IDs return `None`.

## Rate limits and errors

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)). No NCBI API key is sent, so NCBI's limit of 3 requests per second applies; a search uses two requests. Errors are logged; search returns `[]` and details return `None`.

## See also

- [OMIM adapter](omim_adapter.md), [HPO adapter](hpo_adapter.md)
- [COSMIC adapter](../other/cosmic_adapter.md)
- [All adapters](../README.md)
