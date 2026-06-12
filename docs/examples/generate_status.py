#!/usr/bin/env python3
"""
Generate availability status markdown file.
Each adapter has its own subdirectory under docs/examples/.
"""
import re
from pathlib import Path

project_root = Path("/home/jhe24/AID-PAIS/biomedical-knowledge-lookup")
examples_dir = project_root / "docs" / "examples"

# Read adapter names from __init__.py
init_file = project_root / "src" / "knowledge_lookup" / "adapters" / "__init__.py"
with open(init_file) as f:
    content = f.read()

adapter_names = sorted(set(re.findall(r'from \.([a-z_]+)_adapter import', content)))

# Category mapping
CATEGORY_MAP = {
    "core": ["chembl", "disgenet", "mondo", "ols", "opentargets", "umls"],
    "chemicals": ["drugbank", "pubchem", "unichem"],
    "phenotypes": ["clinvar", "geneontology", "hpo", "omim", "quickgo"],
    "proteins": ["ensembl", "hgnc", "uniprot"],
    "pathways": ["kegg", "reactome"],
    "ontologies": ["bioontology", "bioportal", "ebiols", "obofoundry", "zooma"],
    "families": ["interpro", "pdb", "pfam", "string"],
    "literature": ["europepmc", "eutils"],
    "other": ["biolinker", "cosmic", "dbpedia", "oxo", "tyto", "wikidata"],
}

# Build reverse map: adapter_name → category
ADAPTER_CATEGORY = {}
for cat, adapters in CATEGORY_MAP.items():
    for a in adapters:
        ADAPTER_CATEGORY[a] = cat

# API key requirements
API_KEY_MAP = {
    "bioportal": "BIOPORTAL_API_KEY",
    "bioontology": "BIOPORTAL_API_KEY",
    "umls": "UMLS_API_KEY_TU",
    "disgenet": "DISGENET_API_KEY",
    "cosmic": "COSMIC_API_KEY",
    "omim": "OMIM_API_KEY",
}

# Check which adapters have example outputs (category/adapter/ pattern)
outputs = {}
for adapter in adapter_names:
    category = ADAPTER_CATEGORY.get(adapter, "other")
    example_dir = examples_dir / category / adapter
    output_file = example_dir / f"{adapter}_example_output.txt"
    
    if not output_file.exists():
        outputs[adapter] = "missing"
        continue
    
    if output_file.stat().st_size == 0:
        outputs[adapter] = "timeout"
        continue
    
    with open(output_file) as f:
        content = f.read()
        
        if "API key required but not set" in content or "SKIPPED" in content.upper():
            outputs[adapter] = "skip"
        elif "TIMEOUT" in content or "exceeded" in content:
            outputs[adapter] = "timeout"
        elif "Searching for" in content or "No results found" in content or "Found" in content:
            outputs[adapter] = "success"
        elif "Checking if" in content:
            outputs[adapter] = "success"
        else:
            outputs[adapter] = "missing"

# Generate status markdown
total = len(adapter_names)
with_examples = len([a for a in outputs if outputs[a] in ["success", "timeout", "skip"]])
success = len([a for a in outputs if outputs[a] == "success"])
skip = len([a for a in outputs if outputs[a] == "skip"])
timeout = len([a for a in outputs if outputs[a] == "timeout"])
missing = len([a for a in outputs if outputs[a] == "missing"])

status = f'''# Adapter Availability Status

This document tracks which adapters have example scripts and outputs available.

## Summary

- **Total adapters**: {total}
- **With examples**: {with_examples}
- **Successfully tested**: {success}
- **API key required (not set)**: {skip}
- **Timeout issues**: {timeout}
- **Missing**: {missing}

## API Keys Required

The following adapters require API keys to function. Set the corresponding environment variables:

| Adapter | Environment Variable |
|---------|---------------------|
'''

for adapter, env_var in sorted(API_KEY_MAP.items()):
    status += f"| {adapter.title()} | `{env_var}` |\n"

status += '''
## Adapter Status

| Category | Adapter | Status | Notes |
|----------|---------|--------|-------|
'''

# Sort by category then adapter name
for category, adapters_in_cat in CATEGORY_MAP.items():
    for adapter in sorted(adapters_in_cat):
        if adapter not in adapter_names:
            continue
        status_type = outputs.get(adapter, "missing")
        
        if status_type == "skip":
            env_var = API_KEY_MAP.get(adapter, "unknown")
            status += f"| {category.title()} | {adapter.title()} | ⚠️ Requires API Key | Set `{env_var}` to test |\n"
        elif status_type == "timeout":
            status += f"| {category.title()} | {adapter.title()} | ⏱️ Timeout | Example runs but exceeds timeout |\n"
        elif status_type == "missing":
            status += f"| {category.title()} | {adapter.title()} | ❌ Missing | Example not generated |\n"
        else:
            status += f"| {category.title()} | {adapter.title()} | ✅ Working | Example output available |\n"

status += f'''
## Testing All Adapters

Run the comprehensive test script:

```bash
poetry run python test_all_adapters.py
```

This will:
1. Test each adapter's availability
2. Test `search_concepts(query, sources=[...])`
3. Generate detailed results in `docs/examples/all_adapters_test_results.json`
4. Create summary in `docs/examples/availability_status.md`
'''

# Write status file
status_file = examples_dir / "availability_status.md"
with open(status_file, "w") as f:
    f.write(status)

print(f"Generated: {status_file}")
print(f"  Total adapters: {total}")
print(f"  Success: {success}")
print(f"  Skip (API key): {skip}")
print(f"  Timeout: {timeout}")
print(f"  Missing: {missing}")
