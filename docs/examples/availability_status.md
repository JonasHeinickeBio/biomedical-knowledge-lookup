# Adapter Availability Status

This document tracks which adapters have example scripts and outputs available.

## Summary

- **Total adapters**: 36
- **With examples**: 36
- **Successfully tested**: 30
- **API key required (not set)**: 5
- **Timeout issues**: 1
- **Missing**: 0

## Category Distribution

| Category | Working | Total |
|----------|---------|-------|
| Chemicals | 3 | 3 |
| Core | 5 | 7 |
| Families | 4 | 4 |
| Literature | 2 | 2 |
| Ontologies | 3 | 5 |
| Other | 5 | 6 |
| Pathways | 2 | 2 |
| Phenotypes | 4 | 6 |
| Proteins | 3 | 3 |

## API Keys Required

The following adapters require API keys to function. Set the corresponding environment variables:

| Adapter | Environment Variable |
|---------|---------------------|
| Bioontology | `BIOPORTAL_API_KEY` |
| Bioportal | `BIOPORTAL_API_KEY` |
| Cosmic | `COSMIC_API_KEY` |
| Disgenet | `DISGENET_API_KEY` |
| Omim | `OMIM_API_KEY` |
| Umls | `UMLS_API_KEY` |

## Adapter Status

| Adapter | Status | Category | Notes |
|---------|--------|----------|-------|
| Chembl | ⏱️ Timeout | Core | Example runs but exceeds timeout |
| Disgenet | ⚠️ Requires API Key | Core | Set `DISGENET_API_KEY` to test |
| Mondo | ✅ Working | Core | Example output available |
| Ols | ✅ Working | Core | Example output available |
| Opentargets | ✅ Working | Core | Example output available |
| Umls | ✅ Working | Core | Example output available |
| Uniprot | ✅ Working | Core | Example output available |
| Drugbank | ✅ Working | Chemicals | Example output available |
| Pubchem | ✅ Working | Chemicals | Example output available |
| Unichem | ✅ Working | Chemicals | Example output available |
| Clinvar | ✅ Working | Phenotypes | Example output available |
| Geneontology | ✅ Working | Phenotypes | Example output available |
| Hpo | ✅ Working | Phenotypes | Example output available |
| Omim | ⚠️ Requires API Key | Phenotypes | Set `OMIM_API_KEY` to test |
| Quickgo | ✅ Working | Phenotypes | Example output available |
| Ensembl | ✅ Working | Proteins | Example output available |
| Hgnc | ✅ Working | Proteins | Example output available |
| Uniprot | ✅ Working | Proteins | Example output available |
| Kegg | ✅ Working | Pathways | Example output available |
| Reactome | ✅ Working | Pathways | Example output available |
| Bioontology | ⚠️ Requires API Key | Ontologies | Set `BIOPORTAL_API_KEY` to test |
| Bioportal | ⚠️ Requires API Key | Ontologies | Set `BIOPORTAL_API_KEY` to test |
| Ebiols | ✅ Working | Ontologies | Example output available |
| Obofoundry | ✅ Working | Ontologies | Example output available |
| Zooma | ✅ Working | Ontologies | Example output available |
| Interpro | ✅ Working | Families | Example output available |
| Pdb | ✅ Working | Families | Example output available |
| Pfam | ✅ Working | Families | Example output available |
| String | ✅ Working | Families | Example output available |
| Europepmc | ✅ Working | Literature | Example output available |
| Eutils | ✅ Working | Literature | Example output available |
| Biolinker | ✅ Working | Other | Example output available |
| Cosmic | ⚠️ Requires API Key | Other | Set `COSMIC_API_KEY` to test |
| Dbpedia | ✅ Working | Other | Example output available |
| Oxo | ✅ Working | Other | Example output available |
| Tyto | ✅ Working | Other | Example output available |
| Wikidata | ✅ Working | Other | Example output available |

## Examples by Category

See the [README](README.md) for examples organized by category:

- **[Core](#core-knowledge-sources)**: 6 working examples
- **[Chemicals](#chemicals)**: 3 working examples
- **[Phenotypes](#phenotypes)**: 4 working examples
- **[Proteins](#proteins)**: 3 working examples
- **[Pathways](#pathways)**: 2 working examples
- **[Ontologies](#ontologies)**: 3 working examples
- **[Families](#protein-families)**: 4 working examples
- **[Literature](#literature)**: 2 working examples
- **[Other](#other)**: 5 working examples

## Testing All Adapters

Run the comprehensive test script:

```bash
poetry run python test_all_adapters.py
```

This will:
1. Test each adapter's availability
2. Test `search_concepts(query, sources=[...])`
3. Generate detailed results in `docs/examples/scripts/all_adapters_test_results.json`
4. Create summary in `docs/examples/availability_status.md`
