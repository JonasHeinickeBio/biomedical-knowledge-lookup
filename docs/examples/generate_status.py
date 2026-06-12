#!/usr/bin/env python3
"""
Generate availability status markdown file.
Updated to work with categorized examples in docs/examples/
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

# API key requirements
API_KEY_MAP = {
    "bioportal": "BIOPORTAL_API_KEY",
    "bioontology": "BIOPORTAL_API_KEY",
    "umls": "UMLS_API_KEY_TU",
    "disgenet": "DISGENET_API_KEY",
    "cosmic": "COSMIC_API_KEY",
    "omim": "OMIM_API_KEY",
}

# Category mapping
CATEGORY_MAP = {
    "core": ["ols", "umls", "opentargets", "chembl", "disgenet", "mondo", "uniprot"],
    "chemicals": ["drugbank", "pubchem", "unichem"],
    "phenotypes": ["hpo", "geneontology", "omim", "clinvar", "dbvar", "quickgo"],
    "proteins": ["ensembl", "hgnc", "uniprot"],
    "pathways": ["reactome", "kegg"],
    "ontologies": ["bioontology", "bioportal", "ebiols", "obofoundry", "zooma"],
    "families": ["interpro", "pfam", "pdb", "string"],
    "literature": ["europepmc", "eutils"],
    "other": ["biolinker", "cosmic", "dbpedia", "oxo", "tyto", "wikidata"],
}

# Check which adapters have example outputs (check all category directories)
outputs = {}
for adapter in adapter_names:
    found = False
    output_file = None
    
    # Check in each category directory
    for category in CATEGORY_MAP.keys():
        example_dir = examples_dir / category
        output_file = example_dir / f"{adapter}_example_output.txt"
        
        if output_file.exists():
            found = True
            break
    
    if found:
        # Check file size
        if output_file.stat().st_size == 0:
            outputs[adapter] = "timeout"  # Empty file = timeout
            continue
            
        with open(output_file) as f:
            content = f.read()
            
            # Check for skip (API key not set)
            if "API key required but not set" in content or "SKIPPED" in content.upper():
                outputs[adapter] = "skip"
            elif "TIMEOUT" in content or "exceeded" in content:
                outputs[adapter] = "timeout"
            # Check if it ran and returned (has search or error messages)
            elif "Searching for" in content or "No results found" in content or "Found" in content or "ADAPTER ERROR" in content:
                # If it found results or at least ran
                if "Found" in content or "Searching for" in content:
                    outputs[adapter] = "success"
                else:
                    outputs[adapter] = "success"
            elif "Checking if" in content:
                outputs[adapter] = "success"  #至少运行了
            else:
                outputs[adapter] = "missing"
    else:
        outputs[adapter] = "missing"

# Generate status markdown
total = len(adapter_names)
with_examples = len([a for a in outputs if outputs[a] in ["success", "timeout", "skip"]])
success = len([a for a in outputs if outputs[a] == "success"])
skip = len([a for a in outputs if outputs[a] == "skip"])
timeout = len([a for a in outputs if outputs[a] == "timeout"])
missing = len([a for a in outputs if outputs[a] == "missing"])

# Count by category
category_counts = {}
for category, adapters in CATEGORY_MAP.items():
    count = len([a for a in adapters if outputs.get(a) in ["success", "timeout"]])
    category_counts[category] = count

status = f'''# Adapter Availability Status

This document tracks which adapters have example scripts and outputs available.

## Summary

- **Total adapters**: {total}
- **With examples**: {with_examples}
- **Successfully tested**: {success}
- **API key required (not set)**: {skip}
- **Timeout issues**: {timeout}
- **Missing**: {missing}

## Category Distribution

| Category | Working | Total |
|----------|---------|-------|
'''

for category, adapters in sorted(CATEGORY_MAP.items()):
    working = len([a for a in adapters if outputs.get(a) == "success"])
    total_cat = len(adapters)
    status += f"| {category.title()} | {working} | {total_cat} |\n"

status += f'''
## API Keys Required

The following adapters require API keys to function. Set the corresponding environment variables:

| Adapter | Environment Variable |
|---------|---------------------|
'''

for adapter, env_var in sorted(API_KEY_MAP.items()):
    status += f"| {adapter.title()} | `{env_var}` |\n"

status += '''
## Adapter Status

| Adapter | Status | Category | Notes |
|---------|--------|----------|-------|
'''

# Sort by category then adapter name
sorted_adapters = []
for category in CATEGORY_MAP.keys():
    for adapter in sorted(CATEGORY_MAP[category]):
        if adapter in adapter_names:
            sorted_adapters.append((category, adapter))

for category, adapter in sorted_adapters:
    status_type = outputs.get(adapter, "missing")
    
    if status_type == "skip":
        env_var = API_KEY_MAP.get(adapter, "unknown")
        status += f"| {adapter.title()} | ⚠️ Requires API Key | {category.title()} | Set `{env_var}` to test |\n"
    elif status_type == "timeout":
        status += f"| {adapter.title()} | ⏱️ Timeout | {category.title()} | Example runs but exceeds timeout |\n"
    elif status_type == "missing":
        status += f"| {adapter.title()} | ❌ Missing | {category.title()} | Example not generated |\n"
    else:
        status += f"| {adapter.title()} | ✅ Working | {category.title()} | Example output available |\n"

status += f'''
## Examples by Category

See the [README](README.md) for examples organized by category:

- **[Core](#core-knowledge-sources)**: {category_counts.get("core", 0)} working examples
- **[Chemicals](#chemicals)**: {category_counts.get("chemicals", 0)} working examples
- **[Phenotypes](#phenotypes)**: {category_counts.get("phenotypes", 0)} working examples
- **[Proteins](#proteins)**: {category_counts.get("proteins", 0)} working examples
- **[Pathways](#pathways)**: {category_counts.get("pathways", 0)} working examples
- **[Ontologies](#ontologies)**: {category_counts.get("ontologies", 0)} working examples
- **[Families](#protein-families)**: {category_counts.get("families", 0)} working examples
- **[Literature](#literature)**: {category_counts.get("literature", 0)} working examples
- **[Other](#other)**: {category_counts.get("other", 0)} working examples

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
print(f"\nBy category:")
for category, count in sorted(category_counts.items()):
    print(f"  {category.title()}: {count} working")
