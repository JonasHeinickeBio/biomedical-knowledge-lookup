#!/usr/bin/env python3
"""
Generate example scripts for all adapters.
"""
import re
from pathlib import Path

project_root = Path("/home/jhe24/AID-PAIS/biomedical-knowledge-lookup")

# Read adapter names from __init__.py
init_file = project_root / "src" / "knowledge_lookup" / "adapters" / "__init__.py"
with open(init_file) as f:
    content = f.read()

adapter_names = sorted(set(re.findall(r'from \.([a-z_]+)_adapter import', content)))
print(f"Found {len(adapter_names)} adapters")

# API key requirements
API_KEY_MAP = {
    "bioportal": "BIOPORTAL_API_KEY",
    "bioontology": "BIOPORTAL_API_KEY",
    "umls": "UMLS_API_KEY_TU",
    "disgenet": "DISGENET_API_KEY",
    "cosmic": "COSMIC_API_KEY",
    "omim": "OMIM_API_KEY",
}

# Query suggestions per adapter
QUERY_MAP = {
    "opentargets": "cancer",
    "ols": "cancer",
    "bioportal": "cancer",
    "umls": "cancer",
    "drugbank": "aspirin",
    "chembl": "cancer",
    "reactome": "signaling",
    "uniprot": "p53",
    "ensembl": "BRCA1",
    "pubchem": "aspirin",
    "disgenet": "cancer",
    "kegg": "cancer",
    "geneontology": "apoptosis",
    "hgnc": "TP53",
    "hpo": "fever",
    "mondo": "cancer",
    "ebiols": "cancer",
    "quickgo": "apoptosis",
    "eutils": "cancer",
    "wikidata": "cancer",
    "dbpedia": "cancer",
    "biolinker": "cancer",
    "zooma": "cancer",
    "tyto": "cancer",
    "oxo": "MONDO:0004992",
    "obofoundry": "cancer",
    "interpro": "BRCA1",
    "string": "TP53",
    "pfam": "BRCA1",
    "pdb": "6vxx",
    "cosmic": "BRAF",
    "clinvar": "BRCA1",
    "omim": "143100",
    "bioontology": "cancer",
    "unichem": "CHEMBL1201",
    "europepmc": "cancer",
}

def generate_example_script(adapter_name: str, api_key_env: str, search_query: str) -> str:
    """Generate example script for an adapter."""
    
    special_names = {
        "uniprot": "UniProt", "hgnc": "HGNC", "hpo": "HPO", "kegg": "KEGG",
        "pdb": "PDB", "omim": "OMIM", "bioontology": "BioOntology",
        "ebiols": "EBIOLS", "quickgo": "QuickGO", "obofoundry": "OBOFoundry",
        "biolinker": "BioLinker", "zooma": "Zooma", "oxo": "OxO",
        "interpro": "InterPro", "string": "STRING", "pfam": "Pfam",
        "cosmic": "COSMIC", "disgenet": "DisGeNET", "unichem": "UniChem",
        "europepmc": "EuropePMC",
    }
    import_name = special_names.get(adapter_name, adapter_name.title().replace("_", ""))
    
    # Build source name
    if adapter_name == "biolinker":
        source_name = "BIOLINKER"
    elif adapter_name == "chembl":
        source_name = "CHEMBL"
    elif adapter_name == "unichem":
        source_name = "UNICHEM"
    else:
        source_name = adapter_name.upper().replace("_", "")
    
    model_source = f"KnowledgeSource.{source_name}"
    
    script = f'''"""
Example: Using the {import_name} Adapter for Biomedical Concept Lookup
"""

from knowledge_lookup import LookupConfig, create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource


async def main():
'''
    
    if api_key_env:
        script += f'''    # Note: {import_name} adapter may require an API key
    # Set {api_key_env} environment variable
    # os.environ['{api_key_env}'] = 'your_api_key_here'
    
'''
    
    script += f'''    # Create lookup instance
    # For adapters requiring API keys, pass the key via api_keys parameter
    lookup = create_knowledge_lookup(enabled_sources=[{model_source}])
    
    print(f"Checking if {import_name} adapter is available...")
    if lookup:
        print(f"  ✓ {import_name} adapter is available")
    else:
        print(f"  ✗ {import_name} adapter is not available")
        return
    
    query = "{search_query}"
    print(f"\\\\nSearching for '{{query}}' concepts in {import_name}...")
    results = await lookup.search_concepts(query, sources=[{model_source}])
    
    print(f"\\\\nFound {{results.total_found}} results from {import_name}:")
    for i, concept in enumerate(results.concepts[:5]):
        print(f"\\\\n  Concept {{i+1}}:")
        print(f"    Label: {{concept.primary_label}}")
        print(f"    ID: {{concept.primary_id}}")
        print(f"    Type: {{concept.concept_type}}")
        print(f"    Confidence: {{concept.confidence_score}}")
        
        if concept.definitions:
            print(f"    Definitions ({{len(concept.definitions)}}):")
            for definition in concept.definitions[:2]:
                print(f"      - {{definition}}")
        
        if concept.mappings:
            print(f"    Mappings ({{len(concept.mappings)}}):")
            for mapping in concept.mappings[:3]:
                print(f"      - {{mapping.source_id}}: {{mapping.source_label}}")
    
    if not results.concepts:
        print("  No results found for '{{query}}'")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''
    
    return script

examples_dir = project_root / "docs" / "examples"
examples_dir.mkdir(parents=True, exist_ok=True)

for adapter_name in adapter_names:
    api_key_env = API_KEY_MAP.get(adapter_name)
    search_query = QUERY_MAP.get(adapter_name, "cancer")
    
    script_content = generate_example_script(adapter_name, api_key_env, search_query)
    
    example_file = examples_dir / f"{adapter_name}_example.py"
    with open(example_file, "w") as f:
        f.write(script_content)
    
    print(f"Generated: {example_file.name}")
    print(f"  API Key: {api_key_env or 'None'}")
    print(f"  Query: {search_query}")

print(f"\n✓ Generated {len(adapter_names)} example scripts")
print(f"  Location: {examples_dir}")
