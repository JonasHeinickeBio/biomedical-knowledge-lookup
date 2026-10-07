---
description: NCBI MedGen conditions and phenotypes keyed by UMLS CUI, with cross-references to MeSH, OMIM, Orphanet, MONDO, HPO, SNOMED CT and NCIT, plus associated genes and clinical features.
---

# MedGen adapter

Looks up conditions, phenotypes and findings in NCBI [MedGen](https://www.ncbi.nlm.nih.gov/medgen/) through the E-utilities. MedGen groups the names and identifiers of many vocabularies under one concept identified by a UMLS CUI (`C0015674` for myalgic encephalomyelitis / chronic fatigue syndrome), so the main value of this adapter is **ID linking**: one call returns the MeSH, OMIM, Orphanet, MONDO, HPO, SNOMED CT, NCI Thesaurus, GTR and GeneReviews identifiers of the same condition. For genetic conditions the concept record also names the associated genes, HPO clinical features and mode of inheritance.

| | |
|---|---|
| Source | `KnowledgeSource.MEDGEN` |
| Class | `knowledge_lookup.adapters.MedGenAdapter` |
| Requires | none (optional `NCBI_API_KEY` raises the rate limit from 3 to 10 requests/s) |
| Identifiers | UMLS CUI (`C0015674`, also `UMLS:C0015674`, `MedGen:C0015674`) or MedGen UID (`5130`, `MedGen:5130`) |
| Upstream API | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (`db=medgen`) |
| Licence | NCBI data are public domain; NCBI asks users to cite MedGen and respect the E-utilities usage policy |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import MedGenAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with MedGenAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("diabetes mellitus", limit=3):
            print(c.primary_id, c.primary_label, c.semantic_types)

        cfs = await adapter.get_concept_details("C0015674")
        print(cfs.primary_label, len(cfs.synonyms))

        for m in await adapter.get_mappings("C0015674"):
            print(m["toId"], "-", m["label"])

        for rel in await adapter.get_relationships("C0024796", limit=3):  # Marfan syndrome
            print(rel["relation_label"], rel["related_id"], rel["related_name"])


asyncio.run(main())
```

Output (live, 2026-10-07):

```
C0011849 Diabetes mellitus ['Disease or Syndrome']
C0011860 Type 2 diabetes mellitus ['Disease or Syndrome']
C0011854 Diabetes mellitus type 1 ['Disease or Syndrome']
Myalgic encephalomeyelitis/chronic fatigue syndrome 34
MESH:D015673 - Fatigue Syndrome, Chronic
NCIT:C3037 - Chronic Fatigue Syndrome
SNOMEDCT_US:52702003 - Chronic fatigue syndrome
SNOMEDCT_US:51771007 - Postviral fatigue syndrome
GTR:GTRT000046815 - Myalgic encephalomeyelitis/chronic fatigue syndrome
MONDO:0005404 - myalgic encephalomeyelitis/chronic fatigue syndrome
Orphanet:1983 - NON RARE IN EUROPE: Chronic fatigue syndrome
has_associated_gene NCBIGene:2200 FBN1
has_clinical_feature HP:0001659 Aortic regurgitation
has_clinical_feature HP:0001166 Arachnodactyly
```

(The title "encephalomeyelitis" is MedGen's own spelling.)

## What the E-utilities offer

All shapes below were checked live:

| Endpoint | Used for |
|---|---|
| `esearch.fcgi?db=medgen&term=...&sort=relevance` | MedGen UIDs. A bare CUI is a valid term. **Always pass `sort=relevance`**: the default order is by recency and puts newly added obscure concepts first (`diabetes mellitus` default top hit: "Leukoencephalopathy without lacunae, adult-onset"; with relevance: `C0011849` Diabetes mellitus) |
| `esummary.fcgi?db=medgen&id=...&retmode=json` | one document per UID: `conceptid` (CUI, or a MedGen `CN...` id), `title`, `definition`, `semanticid` (UMLS TUI such as `T047`), `semantictype`, `suppressed`, `merged` and `conceptmeta` |
| `efetch.fcgi` | **not used**: for `db=medgen` it returns only the id list, `rettype=full` is rejected (HTTP 400) |
| `elink.fcgi` | **not used**: it lists links to ClinVar, Gene, GTR, MeSH, OMIM, PubMed (`cmd=acheck`), but the concept record already has the genes and features with names |

`conceptmeta` is a **string containing an XML fragment with several root elements** (`Names`, `Definitions`, `OMIM`, `ClinicalFeatures`, `ModesOfInheritance`, `RelatedDisorders`, `PharmacologicResponse`, `AssociatedGenes`, `SNOMEDCT`, `SemanticTypes`, ...). The adapter wraps it in a synthetic root and parses it with `xml.etree`. Concept records are large: 8 KB for ME/CFS, 66 KB for Marfan syndrome, 170 KB for four diabetes concepts.

## Searching

`search_concepts(query, limit)` runs `esearch` (all fields, relevance order, at most 50 hits) and one `esummary` for the UIDs, i.e. two requests. A query that is a CUI or UID goes straight to details. Results are `DISEASE` concepts, except `Sign or Symptom` (`SYMPTOM`) and findings/abnormalities (`PHENOTYPE`).

## Concept details

`get_concept_details(concept_id)` resolves a CUI with `esearch` and *verifies the hit carries that CUI* (a bare CUI could otherwise match another concept that merely cites it), or reads a UID directly; then one `esummary`.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | CUI / MedGen preferred title |
| `identifiers` | `MEDGEN` identifier `MedGen:<uid>` with the MedGen URL |
| `definitions` | the MedGen definition plus the per-source definitions (NCI, GeneReviews ...); doubled apostrophes of the raw text are collapsed |
| `synonyms` | all names from all vocabularies, de-duplicated, at most 50 |
| `semantic_types` | the UMLS semantic type name |
| `source_data[MEDGEN]` | `uid`, `conceptid`, `semantic_type`, `semantic_type_id`, `definition_sources`, `source_vocabularies` (the `SAB` codes present), `omim`, `associated_genes` (`gene_id`, `symbol`), `suppressed`, `merged` |

`parents` / `children` stay empty: MedGen's hierarchy is not exposed by the E-utilities (use [MONDO](../core/mondo_adapter.md) or [DOID](../ontologies/doid_adapter.md) for that).

## Mappings

`get_mappings(concept_id)` returns one item per (vocabulary, code) found in the concept's names and `OMIM` list: `{fromId: CUI, toId: "<PREFIX>:<code>", fromSource: "MEDGEN", toSource, mappingType: "xref", confidence: 0.9, label, source_vocabulary}`.

| MedGen `SAB` | CURIE prefix | Example (ME/CFS, Marfan) |
|---|---|---|
| `MSH` | `MESH` | `MESH:D015673`, `MESH:D008382` |
| `OMIM` | `OMIM` (numeric ids only; UMLS-internal `MTHU...` pseudo ids are dropped) | `OMIM:154700` |
| `SNOMEDCT_US` | `SNOMEDCT_US` | `SNOMEDCT_US:52702003` |
| `NCI` | `NCIT` | `NCIT:C3037` |
| `HPO` | `HP` | `HP:0012378` (fatigue) |
| `MONDO` | `MONDO` | `MONDO:0005404` |
| `ORDO` | `Orphanet` | `Orphanet:1983`, `Orphanet:558` |
| `GTR` | `GTR` | `GTR:GTRT000046815` |
| `GENEREVIEWS` | `GeneReviews` | `GeneReviews:NBK1335` |

Any other `SAB` would be passed through under its own name. **ICD codes were not present** in any of the concept records examined (ME/CFS, fatigue, diabetes, Marfan, BRCA1 hereditary breast and ovarian cancer): do not rely on MedGen for ICD-10/ICD-11 coding; use [ICD-10-GM](../ontologies/icd10gm_adapter.md), [ICD-11](../ontologies/icd11_adapter.md) or the [DOID adapter](../ontologies/doid_adapter.md) (`ICD10CM`). The vocabularies disagree on granularity, so a mapping means "listed under the same MedGen concept", not strict equivalence (ME/CFS lists two SNOMED CT concepts, "Chronic fatigue syndrome" and "Postviral fatigue syndrome").

## Relationships

`get_relationships(concept_id, limit=50)` reads the concept record:

| `relation_label` | Target |
|---|---|
| `has_associated_gene` | `NCBIGene:<id>` + symbol; extras `chromosome`, `cytogenetic_location` |
| `has_clinical_feature` | HPO id (CUI where MedGen has no HPO id) + name; extras `cui`, `semantic_type`, `medgen_uid` |
| `has_mode_of_inheritance` | CUI + name (e.g. Autosomal dominant inheritance) |
| `related_disorder` | CUI + name |
| `has_pharmacologic_response` | the drug concept of a "... response" finding (Warfarin for `warfarin response`) |

In that order, capped by `limit`; a type-2-diabetes concept lists hundreds of clinical features. ME/CFS (`C0015674`) has no genes or clinical features in MedGen, so it returns `[]`; try Marfan syndrome (`C0024796`: FBN1, HPO features, autosomal dominant) or BRCA1 hereditary breast and ovarian cancer (`C2676676`: `NCBIGene:672`, breast carcinoma, ovarian neoplasm).

## Rate limits and caveats

NCBI allows 3 requests/s without an API key and 10/s with one; the adapter spaces calls at 0.34 s (0.11 s with `NCBI_API_KEY` set in the environment or as `ncbi` in the config's `api_keys`). A contact address is sent as `email` only if `NCBI_EMAIL` / `ncbi_email` is configured; otherwise nothing identifying is sent. Measured latency was 0.5 - 1.0 s per call (search 1.1 - 1.7 s for two calls). Errors and unknown IDs are logged; search returns `[]`, details `None`. `esummary` for an unknown UID returns a document with `error: "cannot get document summary"`, which is dropped.

- MedGen UIDs are not stable cross-release identifiers; use the CUI.
- Concepts without a UMLS CUI (MedGen `CN...` ids, titles such as "Grade 4 Diabetes Mellitus, CTCAE") are returned like any other.
- The [EUtils adapter](../other/eutils_adapter.md) (PubMed, Gene, Protein) is a separate source and needs `bioservices`; this adapter does not.

## See also

- [DOID adapter](../ontologies/doid_adapter.md), [HPO adapter](hpo_adapter.md), [MONDO adapter](../core/mondo_adapter.md)
- [All adapters](../README.md)
