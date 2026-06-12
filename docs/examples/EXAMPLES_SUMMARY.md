# Example Scripts Summary

This document provides a summary of the example scripts generated for the biomedical-knowledge-lookup package.

## Overview

Generated **36 example scripts** covering all adapters in the project. Each example demonstrates how to use a specific knowledge source adapter.

## Files Created

### Example Scripts
- **36 files** in `docs/examples/` named `{adapter_name}_example.py`
- Each script demonstrates: adapter initialization, search, and result processing

### Output Files
- **36 output files** in `docs/examples/` named `{adapter_name}_example_output.txt`
- Captures actual output from running the examples

### Documentation
- **availability_status.md** - Current status of all adapters
- **README.md** - Updated with all adapters and usage examples

## Test Results

### Successful Tests: 29 adapters

Working adapters (no API key required):
1. biolinker
2. clinvar
3. dbpedia
4. drugbank
5. ebiols
6. ensembl
7. europepmc
8. eutils
9. geneontology
10. hgnc
11. hpo
12. interpro
13. kegg
14. mondo
15. obofoundry
16. ols
17. opentargets
18. oxo
19. pdb
20. pfam
21. pubchem
22. quickgo
23. reactome
24. string
25. tyto
26. unichem
27. uniprot
28. wikidata
29. zooma

### API Key Required: 6 adapters

These adapters need API keys to function:
1. bioontology (BIOPORTAL_API_KEY)
2. bioportal (BIOPORTAL_API_KEY)
3. cosmic (COSMIC_API_KEY)
4. disgenet (DISGENET_API_KEY)
5. omim (OMIM_API_KEY)
6. umls (UMLS_API_KEY_TU)

### Timeout: 1 adapter

1. chembl - Example runs but exceeds 30-second timeout

## Example Script Structure

Each example follows this pattern:

```python
1. Import required modules
2. Create LookupConfig with enabled sources
3. Create knowledge lookup instance
4. Test adapter availability
5. Search for concepts
6. Display results (label, ID, type, confidence, definitions, mappings)
```

## API Changes Made

- Updated `chembl_adapter.py` import in `adapters/__init__.py`
- Added `ChEMBLAdapter` to `__all__` list
- Fixed example script generation to use correct API:
  - `create_knowledge_lookup(enabled_sources=[...])` instead of `config=config` parameter

## How to Use

### For adapters without API keys:
```bash
poetry run python docs/examples/{adapter_name}_example.py
```

### For adapters requiring API keys:
```bash
export BIOPORTAL_API_KEY="your_api_key"
poetry run python docs/examples/bioportal_example.py
```

## Integration with CI/CD

These examples can be used for:
- Integration testing (verify adapters work)
- Documentation (show users how to use)
- Smoke testing (quick checks after deployments)
