---
description: Orphanet rare-disease nosology (ORPHAcodes), genes, HPO phenotypes with frequency, prevalence and cross-references via the keyless Orphadata API.
---

# Orphanet adapter

Looks up rare diseases by ORPHAcode or name and returns their definition, synonyms, cross-references (OMIM, ICD-10, ICD-11, MONDO, MeSH, UMLS, MedDRA, GARD), associated genes, HPO phenotype annotations with frequency, prevalence, natural history and the Orphanet classification hierarchy. It uses the keyless **Orphadata API**; the official ORPHAcode API (`api.orphacode.org`) answers `401 No authorization token provided` and needs a registration token, so it is not used.

| | |
|---|---|
| Source | `KnowledgeSource.ORPHANET` |
| Class | `knowledge_lookup.adapters.OrphanetAdapter` |
| Requires | none (keyless) |
| Identifiers | `ORPHA:558`; also `Orphanet_558`, `orphanet:558`, `ORPHAcode 558`, bare `558` |
| Upstream API | `https://api.orphadata.com` (OpenAPI spec: `/openapi.json`) |
| Licence | CC BY 4.0 (credit Orphanet / Orphadata and the release date) |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import OrphanetAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with OrphanetAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("marfan", limit=3):
            print(c.primary_id, c.primary_label)

        marfan = await adapter.get_concept_details("ORPHA:558")
        print(marfan.synonyms, marfan.parents[:2])

        for edge in (await adapter.get_relationships("ORPHA:558"))[:3]:
            print(edge["relation_label"], edge["related_id"], edge["related_name"],
                  edge.get("frequency_label"))

        for m in (await adapter.get_mappings("ORPHA:558"))[:3]:
            print(m["toId"], m["mappingType"])


asyncio.run(main())
```

Output (release 2026-06):

```
ORPHA:558 Marfan syndrome
ORPHA:284963 Marfan syndrome type 1
ORPHA:284973 Marfan syndrome type 2
['MFS'] ['ORPHA:519292', 'ORPHA:498448']
has_phenotype HP:0000768 Pectus carinatum Very frequent
has_phenotype HP:0001065 Striae distensae Very frequent
has_phenotype HP:0001166 Arachnodactyly Very frequent
ICD10:Q87.4 exactMatch
ICD11:LD28.01 exactMatch
MONDO:0007947 exactMatch
```

## What each method returns

- `search_concepts(query, limit)`: loads the list of all 11,645 disorders once per adapter (`/rd-cross-referencing/orphacodes`, 200 kB gzip, 1.3 MB JSON, 0.5 s) and matches names locally: every word must occur, any order. Ranking: exact 1.0, prefix 0.9, whole-phrase substring 0.8, words anywhere 0.7. Orphadata's own single best fuzzy match (`/names/{name}`, which never returns more than one hit) is appended with 0.85 when the list did not already contain it. An id-like query returns that disease with full details. Hits from the list are thin (id, label, type `DISEASE`).
- `get_concept_details(id)`: label, `synonyms`, `definitions`, `categories` (typology such as `Disease` / `Clinical group` / `Category`, disorder group, flags such as `obsolete entity`, `non-rare disease in europe`), `identifiers` for MONDO, OMIM, UMLS and MeSH, and `parents` / `children` (union over all Orphanet classifications). `source_data["ORPHANET"]` adds the Orphanet URL, release date, `prevalence` (class, geography, type, validation status, mean value), `type_of_inheritance`, `average_age_of_onset` and `average_age_of_death`. Four requests, made concurrently.
- `get_relationships(id, limit=50)` (limit applies per kind):
  - `associated_with` to `HGNC:n` genes with `association_type` (e.g. "Disease-causing germline mutation(s) in", "Major susceptibility factor in"), `association_status` (Assessed / Not yet assessed), `references` (PMIDs), `gene_symbol`, `gene_type`, `locus`, `ensembl`, `omim_gene`, `uniprot`.
  - `has_phenotype` (or `not_has_phenotype` for "Excluded (0%)") to `HP:` terms with `frequency` (midpoint of the HPO range from `_pheno_common`, so it compares with the HPOA and Monarch adapters), `frequency_label`, `frequency_term` (`HP:0040281`), `frequency_raw` (Orphanet's wording, `Very frequent (99-80%)`), `diagnostic_criteria` and `references`; most frequent first.
  - `subclass_of` to parents and `has_subclass` to children, labelled, with the Orphanet classifications containing the link in `classifications`.
- `get_mappings(id)`: OMIM, ICD-10, ICD-11, MONDO, MeSH, UMLS, MedDRA and GARD references as `ICD10:Q87.4`, `MONDO:0007947`, ... `mappingType` is the SKOS type seen from the ORPHAcode: `exactMatch`, `narrowMatch` (ORPHAcode is broader than the target, Orphanet code `BTNT`), `broadMatch` (`NTBT`), `relatedMatch` (not decided); `confidence` 1.0 for exact, 0.8 for broader/narrower, at most 0.6 if the mapping is "Not yet validated". The raw Orphanet relation and validation status are in `relation` and `validation_status`. ICD-11 rows carry the WHO URI in the raw record only.

## Verified live (2026-10-07, release 2026-06-23)

`knowledge_lookup check ORPHANET` passes (search "marfan", details ORPHA:558, 60 relationship edges). Latencies: record/phenotype/classification endpoints 0.2-0.5 s, gene endpoint up to 1.1 s, class list 1.5 s.

## Caveats

- **404 means "no data"**, not "unknown disease". ORPHA:558 (Marfan syndrome) has no gene entries: the genes are attached to its subtypes (`ORPHA:284963` type 1, `ORPHA:284973` type 2, listed as `has_subclass`). Gene lookups for a group or umbrella disease should be repeated on its children.
- Search is name-based. Orphadata's name endpoint did not match abbreviations (`mfs` gave 404) although the record lists `MFS` as a synonym; synonyms are not searched.
- Non-rare, inactive or obsolete entries keep their prefix in the preferred term, e.g. ORPHA:1983 is `NON RARE IN EUROPE: Chronic fatigue syndrome` and ORPHA:206610 `OBSOLETE: Chronic muscular fatigue and/or chronic muscle pain`. ME/CFS is therefore present as a non-rare disease with no genes or phenotype annotations.
- Only English (`lang=en`) is used; the API supports cs, de, es, fr, it, nl, pl, pt, tr, uk, zh (`lang` query parameter).
- Data are released twice a year (July, December); Orphanet's own website may be newer.
- Coverage (release 2026-06): 4,357 diseases have HPO phenotype annotations, 4,245 have gene associations; the cross-referencing product lists 11,645 disorders and the classification product 29,023 nodes (including group and category nodes).

## Rate limits and errors

No documented rate limit; the adapter issues at most four concurrent requests per details call and uses the shared retry and circuit breaker. Errors are logged and `[]` / `None` returned.

## See also

- [HPO annotations adapter](hpoa_adapter.md) (OMIM/ORPHA phenotype annotations offline), [Monarch adapter](monarch_adapter.md), [ClinGen](clingen_adapter.md), [GenCC](gencc_adapter.md)
- [All adapters](../README.md)
