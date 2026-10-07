---
description: Human Disease Ontology (DOID) diseases with definitions, synonyms, typed relations and cross-references to MeSH, OMIM, UMLS, ICD, SNOMED CT and Orphanet, via EBI OLS4.
---

# Disease Ontology adapter

Looks up diseases in the Human Disease Ontology (DOID) through the EBI OLS4 API, scoped to `ontology=doid`. DOID is a good bridge from a disease name (`chronic fatigue syndrome`, `long COVID`, `type 2 diabetes mellitus`) to a stable ID, its place in the disease hierarchy and the identifiers other systems use for the same disease (UMLS CUI, MeSH, ICD-10-CM, SNOMED CT, OMIM, Orphanet). It is the same design as the [Cell Ontology adapter](cellontology_adapter.md) and deliberately separate from the generic [OLS adapter](ebiols_adapter.md).

| | |
|---|---|
| Source | `KnowledgeSource.DOID` |
| Class | `knowledge_lookup.adapters.DiseaseOntologyAdapter` |
| Requires | none |
| Identifiers | `DOID:9351`, `DOID_9351`, bare `9351` or the full IRI `http://purl.obolibrary.org/obo/DOID_9351` |
| Upstream API | `https://www.ebi.ac.uk/ols4/api` |
| Licence | the Disease Ontology is CC0 1.0; OLS4 is an EMBL-EBI service |

## Quick example

```python
import asyncio

from knowledge_lookup.adapters import DiseaseOntologyAdapter
from knowledge_lookup.models import LookupConfig


async def main():
    async with DiseaseOntologyAdapter(LookupConfig()) as adapter:
        for c in await adapter.search_concepts("chronic fatigue syndrome", limit=3):
            print(c.primary_id, c.primary_label)

        lc = await adapter.get_concept_details("DOID:0080848")
        print(lc.primary_label, lc.synonyms, lc.parents)

        for rel in await adapter.get_relationships("DOID:0080848", limit=4):
            print(rel["relation_label"], rel["related_id"], rel["related_name"])

        print([m["toId"] for m in await adapter.get_mappings("DOID:8544")])


asyncio.run(main())
```

Output (live, 2026-10-07):

```
DOID:8544 chronic fatigue syndrome
DOID:631 fibromyalgia
DOID:0080848 long COVID
long COVID ['chronic COVID-19', 'post-COVID syndrome', 'post-acute sequelae of SARS-CoV-2 infection', 'PASC'] ['Coronavirus infectious disease']
is_a DOID:0080599 Coronavirus infectious disease
has_symptom SYMP:0000016 confusion
has_symptom SYMP:0000504 headache
has_symptom SYMP:0000529 tachycardia
['GARD:7121', 'ICD10CM:G93.32', 'ICD9CM:780.71', 'MESH:D015673', 'NCIT:C3037', 'SNOMEDCT_US:193054000', 'UMLS:C0015674']
```

(`has_symptom` targets are `SYMP:` ids; the long COVID term lists ten symptoms including fatigue, headache, dizziness, memory loss, concentration difficulty, chest pain, tachycardia, breathing problems, ageusia and confusion.)

## Searching

`search_concepts(query, limit)` calls `/search?q=...&ontology=doid&type=class&obsoletes=false`. Obsolete terms are excluded and only `DOID:` classes are returned. If `query` is itself a DOID identifier (`DOID:9351`, an IRI) the term is fetched directly; a bare number is treated as search text, not as an id. Results carry label, definition(s), synonyms and `DISEASE` as concept type; `confidence_score` decreases with rank. `chronic fatigue syndrome` finds `DOID:8544` (synonyms `Myalgic encephalomyelitis`, `Postviral fatigue syndrome`, `CFS`) first, and `long COVID` is `DOID:0080848` (synonym `PASC`).

## Concept details

`get_concept_details(concept_id)` fetches `/ontologies/doid/terms/{double-URL-encoded IRI}` and the `parents` (and, for terms with children, `children`) pages, at most 25 labels each; failures there degrade to empty lists.

| Field | Value |
|---|---|
| `primary_id` / `primary_label` | `DOID:8544` / `chronic fatigue syndrome` |
| `definitions` | the DOID definition. Curator notes DOID mixes into `description` ("Xref MGI. OMIM mapping confirmed by DO. [SN].", "No OMIM mapping, confirmed by DO.") are dropped |
| `synonyms` | exact, narrow and related synonyms |
| `categories` | `Xref: <DB>:<id>` for every cross-reference; `obsolete` for obsolete terms |
| `parents` / `children` | direct `is_a` neighbours (labels) |
| `identifiers` | the DOID IRI as `DOID` identifier |
| `source_data[DOID]` | `iri`, `obo_id`, `label`, `in_subset`, `is_obsolete`, `term_replaced_by` |

## Relationships

`get_relationships(concept_id, limit=25)` uses one `/terms/{iri}/graph` request which returns typed edges in both directions:

| `relation_label` | Meaning |
|---|---|
| `is_a` | direct parent (outgoing `subClassOf`) |
| `has_symptom`, `has_phenotype`, `has_material_basis_in`, `disease_has_location`, `has_major_susceptibility_factor`, ... | the disease's own relations, name from the edge label in snake_case; targets can be `SYMP:`, `HP:`, `MIM:`, `GENO:`, `UBERON:` ... terms |
| `has_subclass` | direct child (incoming `subClassOf`) |
| `inverse_<relation>` | relations other terms hold towards this one (`inverse_contributes_to_condition` for OMIM susceptibility entries, `inverse_disease_has_feature` for diseases that list this one as a feature) |

Every item also carries `direction` (`outgoing`/`incoming`) and `relation_iri`. Order: parents, own relations, children, inverse relations, then cut to `limit`. For a broad term such as `DOID:1612` (breast cancer, ~19 children) the graph already contains every child, so raise `limit` if you need them all. Chronic fatigue syndrome has a single edge (`is_a` `DOID:225` syndrome) and no symptom or gene links in DOID.

The per-relation links on the term object (`_links.has_material_basis_in` ...) are not used: they mix targets of several relations.

## Mappings

`get_mappings(concept_id)` converts the term's cross-references into `{fromId, toId, fromSource: "DOID", toSource, mappingType: "xref", confidence: 0.9}`. Database names are normalised so they match the other adapters:

| DOID xref | `toSource` / CURIE prefix |
|---|---|
| `MESH`, `ICD10CM`, `ICD9CM`, `GARD` | unchanged |
| `SNOMEDCT_US_2025_09_01` (versioned) | `SNOMEDCT_US` |
| `UMLS_CUI` | `UMLS` |
| `MIM` | `OMIM` |
| `ORDO` | `Orphanet` |
| `NCI` | `NCIT` |

Verified live for chronic fatigue syndrome (`UMLS:C0015674`, `MESH:D015673`, `ICD10CM:G93.32`, `ICD9CM:780.71`, `SNOMEDCT_US:193054000`, `NCIT:C3037`, `GARD:7121`) and malignant hyperthermia (adds `OMIM:PS145600`, `Orphanet:423`).

## Rate limits and caveats

Uses the shared HTTP retry and circuit breaker (see [Rate limits, retries and circuit breakers](../README.md#rate-limits-retries-and-circuit-breakers)); `min_request_timeout` is 30 s. Measured latency: 0.4 - 1.2 s typical, the first search after a pause took 6.4 s. Errors and unknown IDs are logged; search returns `[]`, details `None`.

- Use the ontology-scoped term URL: `/terms?iri=` returns the same IRI once per ontology that imports it.
- DOID is a human-disease classification, not a clinical coding system: one DOID term can cover several ICD codes and vice versa, so treat the cross-references as links, not as exact equivalences.
- ME/CFS is a *syndrome* under DOID (`DOID:8544`, labelled "chronic fatigue syndrome"); newer MONDO/ICD-11 terms (`myalgic encephalomyelitis`) appear only as synonyms.

## See also

- [Cell Ontology adapter](cellontology_adapter.md), [OLS adapter](ebiols_adapter.md), [MedGen adapter](../phenotypes/medgen_adapter.md)
- [All adapters](../README.md)
