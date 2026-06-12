# UMLS Adapter Improvements

## Date
2026-06-12

## Bugs Fixed

### 1. Confidence score compared result to itself instead of to query
- `_convert_search_result_to_concept` now takes `query` parameter
- Compares `result.name.strip().lower() == query.strip().lower()`
- Scoring: exact→0.95, substring→0.85, no-match→0.75

### 2. Source type mapping ordering bug
- `icd10` matched before `icd10pcs` (substring ordering issue)
- Fixed by sorting SOURCE_TYPE_MAP keys by length descending

## Improvements

### Expanded source mapping (7 → 35 entries)
Added UMLS source vocabularies: SNOMEDCT, ICD10CM, ICD9CM, OMIM, ORDO, NCI, MEDDRA, NDDF, DrugBank, ChEMBL, PubChem, MeSH+MSH, HGNC, UniProt, Ensembl, RefSeq, GenBank, HPO, FMA, UBERON, GO, KEGG, Reactome, CPT, ICD10PCS, LOINC

### Tests expanded (13 → 52)
Parametrized source mapping, confidence scoring tests, limit validation, client=None edge case, real UMLSSearchResult conversion tests

## Verification
All 865 unit tests pass
