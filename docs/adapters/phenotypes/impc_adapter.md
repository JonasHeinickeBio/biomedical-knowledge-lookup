---
description: International Mouse Phenotyping Consortium knockout-mouse genes and significant phenotype calls (MP terms), with human ortholog symbols.
---

# IMPC adapter

Looks up genes and phenotypes of the International Mouse Phenotyping Consortium (IMPC), which knocks out one gene at a time in mice and runs a standardised phenotyping pipeline. Genes carry their MGI id, mouse symbol and the human ortholog symbol; phenotypes are Mammalian Phenotype (MP) ontology terms. Relationships list the **significant** phenotype calls of a gene (p-value, effect size, zygosity, sex, life stage) and, the other way round, the genes whose knockout produced a phenotype.

> **These are knockout-mouse phenotypes.** They are translational evidence about what a gene does in a mammal, not human clinical findings. Orthology to human is by gene symbol only, and mouse phenotypes (for example a viability call) do not translate one to one into human disease.

| | |
|---|---|
| Source | `KnowledgeSource.IMPC` |
| Class | `knowledge_lookup.adapters.IMPCAdapter` |
| Requires | none (public, keyless) |
| Identifiers | `MGI:95489` (gene), `MP:0004952` (phenotype); gene symbols (mouse `Fbn1` or human `FBN1`) are accepted by `get_concept_details`, `get_mappings` and `get_relationships` |
| Upstream API | `https://www.ebi.ac.uk/mi/impc/solr/<core>/select` (Solr cores `gene`, `genotype-phenotype`, `mp`) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import IMPCAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with IMPCAdapter(LookupConfig()) as adapter:
        for concept in await adapter.search_concepts("FBN1", limit=3):  # human symbol
            print(concept.primary_id, concept.primary_label, concept.synonyms[:2])

        for edge in (await adapter.get_relationships("MGI:95489"))[:4]:
            print(edge["relation_label"], edge["related_id"], edge["related_name"], edge.get("p_value"))

        print(await adapter.get_mappings("Fbn1"))


asyncio.run(main())
```

Output (live, 2026-10-09):

```
MGI:95489 Fbn1 ['fibrillin 1', 'FBN1']
ortholog_of FBN1 FBN1 None
has_phenotype MP:0011110 preweaning lethality, incomplete penetrance 0.0
has_phenotype MP:0004952 increased spleen weight 1.45602538533913e-30
has_phenotype MP:0000219 increased neutrophil cell number 6.92901328666457e-07
[{'fromId': 'MGI:95489', 'toId': 'FBN1', 'fromSource': 'MGI', 'toSource': 'HGNC', 'mappingType': 'ortholog', 'confidence': 0.9}]
```

## Searching

`search_concepts(query, limit)` returns genes first and fills the remaining slots with phenotypes.

- **Genes**: the query is matched case-insensitively against the mouse symbol, the human ortholog symbol, and the mouse and human synonyms (the Solr `*_lowercase` fields). This is how a **human symbol maps to a mouse gene**: `BRCA1` finds `Brca1` (MGI:104537), `FBN1` finds `Fbn1`. If no symbol matches, and for multi-word queries, the gene name is searched as a phrase (`fibrillin` finds `Fbn1` and `Fbn2`). An `MGI:` id is looked up directly. Exact mouse-symbol matches rank first, then exact human-ortholog matches.
- **Phenotypes**: free text is searched in the MP label and synonyms (`increased spleen weight`, `lethargy`); an `MP:` id is looked up directly. MP ids are accepted with or without zero padding (`MP:4952`).
- A paralog family can match several mouse genes for one human symbol (`INS` matches `Ins1` and `Ins2`).

Gene concepts use the mouse symbol as `primary_label`; `synonyms` hold the gene name, human ortholog symbol(s) and mouse synonyms; `categories` is `["knockout mouse model"]`; `source_data[IMPC]` holds chromosome, production and phenotyping status, the human ortholog symbols, and the significant and non-significant top-level MP systems.

## Concept details

`get_concept_details(concept_id)` accepts `MGI:`/`MP:` ids or a gene symbol and returns the same concept shape as search. Phenotype concepts carry the MP definition, synonyms, parent ids (`parents`) and the top-level system names (`categories`).

## Relationships

`get_relationships(concept_id)`

| Input | Edges |
|---|---|
| gene | `ortholog_of` to each human ortholog symbol, then up to 25 `has_phenotype` edges |
| phenotype | `is_a` to the parent MP terms, then up to 25 `phenotype_of` edges to genes |

Phenotype edges are significant IMPC calls, **one per distinct MP term** (gene to terms) or **per distinct gene** (term to genes), ranked by ascending p-value. Each carries `p_value`, `effect_size`, `zygosity`/`zygosities`, `sex`/`sexes`, `life_stage`, `parameter_name`, `allele_symbol` and `n_calls`; gene-to-term edges also have `top_level_mp_terms` and `total_phenotypes`, term-to-gene edges `annotated_term_id`/`annotated_term_name` and `total_genes`.

- A phenotype lookup **includes descendant terms**: genes annotated to `increased spleen weight` appear under `abnormal spleen morphology` (858 genes versus 611 for the exact term), and `annotated_term_*` names the term that was actually annotated.
- A `p_value` of exactly `0.0` is an underflow (or the viability screen) and is the strongest possible call; it sorts first.
- Some genes legitimately have no phenotypes: `Brca1` is in the gene core with `phenotyping_data_available: false`, so only its `ortholog_of` edge is returned.

## Mappings

`get_mappings(concept_id)` returns the mouse gene to **human ortholog symbol** mapping (`fromSource` `MGI`, `toSource` `HGNC`, `mappingType` `ortholog`, `toId` is the **symbol**). The IMPC cores expose no HGNC id and no Ensembl id, and no MP-to-HP (human phenotype) mapping, so none of those are offered. Use the [HGNC](../proteins/hgnc_adapter.md) or [Monarch](monarch_adapter.md) adapters to go from the symbol or MP term to human identifiers.

## Rate limits, licence, errors

There is no published rate limit; requests are spaced 0.3 s apart and share the retry and circuit breaker of the base class. Interface methods never raise: errors are logged and `[]` or `None` is returned. IMPC data are released openly (Creative Commons Attribution 4.0 per the IMPC data release terms; cite the IMPC and the data release, and check [the IMPC site](https://www.mousephenotype.org/about-impc/) for the current wording).

## Caveats

- The Solr endpoint answers JSON with content type `text/plain`, which the shared `_make_request` helper refuses, so the adapter fetches the text and parses it itself.
- Symbol fields are case-sensitive strings; only the `*_lowercase` twins make lookups case-insensitive. A query on `marker_symbol:brca1` finds nothing.
- Gene documents contain a large base64 blob (`datasets_raw_data`, ~18 KB for Fbn1); the adapter restricts the returned fields and never requests it.
- The IMPC portal and Solr schema change between data releases; the field names here were verified on 2026-10-09 (67,350 genotype-phenotype documents, 1,857 MP terms).
- Non-significant results are not returned: absence of a phenotype in IMPC does not mean the knockout is normal (the gene document lists non-significant top-level systems separately).

## Live verification (2026-10-09)

- `knowledge-lookup check IMPC` passes (search `Brca1`, details, relationships).
- Latency: gene search 0.5 - 0.9 s, details 0.3 - 0.8 s, `get_relationships` 0.4 - 3 s (1 - 2 requests). Responses: gene document with restricted fields 0.5 - 1 KB, `Fbn1` phenotype groups 4.4 KB, a 25-gene page for a broad term (up to five calls per gene) about 46 KB.
- The legacy probe `genotype-phenotype/select?q=marker_symbol:Brca1` returns 200 with 193 bytes because Brca1 has no significant calls; `Fbn1` (6 calls, 5 terms) and `Ins1` (3 terms) have data.

## See also

- [Monarch adapter](monarch_adapter.md), [HPO adapter](hpo_adapter.md), [Alliance adapter](../proteins/alliance_adapter.md)
- [All adapters](../README.md)
