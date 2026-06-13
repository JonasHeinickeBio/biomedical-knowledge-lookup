# Biomedical Knowledge Lookup - Examples

This directory contains examples for using the various adapters in the biomedical-knowledge-lookup package.

## Directory Structure

```
docs/examples/
├── README.md (this file)
├── availability_status.md         # Adapter availability and API key requirements
├── use_cases.md                   # Common use cases and patterns
├── generate_status.py             # Generate availability status
├── generate_all_examples.py       # Generate all example scripts
├── all_adapters_test_results.json # Test results
├── notebooks/                     # Jupyter notebooks
│   ├── 01-getting-started.ipynb
│   ├── 02-api-keys.ipynb
│   ├── 03-rate-limiting.ipynb
│   ├── 04-error-handling.ipynb
│   └── README.md
│
├── core/                          # Core knowledge sources
│   ├── ols/
│   ├── umls/
│   ├── opentargets/
│   ├── chembl/
│   ├── disgenet/
│   └── mondo/
│
├── chemicals/                     # Drug and compound sources
│   ├── drugbank/
│   ├── pubchem/
│   └── unichem/
│
├── phenotypes/                    # Phenotype and disease sources
│   ├── hpo/
│   ├── geneontology/
│   ├── omim/
│   ├── clinvar/
│   └── quickgo/
│
├── proteins/                      # Protein and gene sources
│   ├── uniprot/
│   ├── ensembl/
│   └── hgnc/
│
├── pathways/                      # Pathway databases
│   ├── reactome/
│   └── kegg/
│
├── ontologies/                    # Ontology services
│   ├── bioontology/
│   ├── bioportal/
│   ├── ebiols/
│   ├── obofoundry/
│   └── zooma/
│
├── families/                      # Protein families
│   ├── interpro/
│   ├── pfam/
│   ├── pdb/
│   └── string/
│
├── literature/                    # Literature sources
│   ├── europepmc/
│   └── eutils/
│
└── other/                         # Other/specialized sources
    ├── biolinker/
    ├── cosmic/
    ├── dbpedia/
    ├── oxo/
    ├── tyto/
    └── wikidata/
```

## Quick Start

```bash
# Set up environment (optional, for adapters requiring API keys)
export BIOPORTAL_API_KEY="your_api_key"
export UMLS_API_KEY="your_api_key"
export DISGENET_API_KEY="your_api_key"
export COSMIC_API_KEY="your_api_key"
export OMIM_API_KEY="your_api_key"

# Run a specific example
poetry run python docs/examples/core/ols/ols_example.py
poetry run python docs/examples/phenotypes/hpo/hpo_example.py
poetry run python docs/examples/chemicals/pubchem/pubchem_example.py
```

## Available Examples

| Adapter | Description | Example |
|---------|-------------|---------|
| OLS | Ontology Lookup Service | `core/ols/ols_example.py` |
| UMLS | Unified Medical Language System — search, source/semantic filters, bulk, mappings, relationships, streaming | `core/umls/umls_example.py` |
| OpenTargets | Drug targets and disease associations | `core/opentargets/opentargets_example.py` |
| ChEMBL | Bioactive drug-like molecules | `core/chembl/chembl_example.py` |
| DisGeNET | Gene-disease associations | `core/disgenet/disgenet_example.py` |
| Mondo | Disease ontology | `core/mondo/mondo_example.py` |
| DrugBank | Drug information and targets | `chemicals/drugbank/drugbank_example.py` |
| PubChem | Chemical compounds and structures | `chemicals/pubchem/pubchem_example.py` |
| UniChem | Drug cross-references | `chemicals/unichem/unichem_example.py` |
| HPO | Human phenotype ontology | `phenotypes/hpo/hpo_example.py` |
| GeneOntology | Gene function annotations | `phenotypes/geneontology/geneontology_example.py` |
| OMIM | Online Mendelian Inheritance in Man | `phenotypes/omim/omim_example.py` |
| ClinVar | Genomic variations and clinical significance | `phenotypes/clinvar/clinvar_example.py` |
| QuickGO | Gene Ontology browser | `phenotypes/quickgo/quickgo_example.py` |
| UniProt | Protein sequences and functions | `proteins/uniprot/uniprot_example.py` |
| Ensembl | Genome annotation | `proteins/ensembl/ensembl_example.py` |
| HGNC | Human gene nomenclature | `proteins/hgnc/hgnc_example.py` |
| Reactome | Biological pathways | `pathways/reactome/reactome_example.py` |
| KEGG | Pathways and disease maps | `pathways/kegg/kegg_example.py` |
| Bioontology | BioOntology API | `ontologies/bioontology/bioontology_example.py` |
| BioPortal | NCBI BioPortal ontologies | `ontologies/bioportal/bioportal_example.py` |
| EBIOLS | EBI Ontology Lookup Service | `ontologies/ebiols/ebiols_example.py` |
| OBOFoundry | Interoperable ontologies | `ontologies/obofoundry/obofoundry_example.py` |
| Zooma | Ontology annotation mapping | `ontologies/zooma/zooma_example.py` |
| InterPro | Protein domain classification | `families/interpro/interpro_example.py` |
| Pfam | Protein family database | `families/pfam/pfam_example.py` |
| PDB | Protein 3D structures | `families/pdb/pdb_example.py` |
| STRING | Protein-protein interactions | `families/string/string_example.py` |
| EuropePMC | Europe PMC literature search | `literature/europepmc/europepmc_example.py` |
| EUtils | NCBI E-utilities | `literature/eutils/eutils_example.py` |
| Biolinker | Biomedical concept linking | `other/biolinker/biolinker_example.py` |
| Cosmic | Cancer gene mutations | `other/cosmic/cosmic_example.py` |
| DBpedia | Wikipedia structured data | `other/dbpedia/dbpedia_example.py` |
| OxO | Ontology cross-references | `other/oxo/oxo_example.py` |
| Tyto | Ontology terms lookup | `other/tyto/tyto_example.py` |
| Wikidata | General knowledge from Wikidata | `other/wikidata/wikidata_example.py` |

## Adapter Status

See [availability_status.md](availability_status.md) for:
- Current adapter availability
- API key requirements
- Test results summary

### Summary Statistics
- **36 total adapters** with example scripts
- **29 successfully tested** without API keys
- **6 require API keys** (BioPortal, UMLS, DisGeNET, COSMIC, OMIM, BioOntology)
- **1 timeout** (ChEMBL - may be slow)

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

## Common Patterns

### Basic Search
```python
from knowledge_lookup import LookupConfig, create_knowledge_lookup
from knowledge_lookup.models import KnowledgeSource

lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.OLS])
results = await lookup.search_concepts("cancer", sources=[KnowledgeSource.OLS])

for concept in results.concepts:
    print(f"{concept.primary_label} ({concept.primary_id})")
```

### With API Key
```python
config = LookupConfig(api_keys={"umls": "your_api_key"})
lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.UMLS], api_keys=config.api_keys)
```

### Get Concept Details
```python
details = await lookup.get_concept_details("DOID:9351", source=KnowledgeSource.OLS)
```

## Examples Without API Keys

The following adapters work without any API keys:
OLS, UMLS, OpenTargets, ChEMBL, DisGeNET, Mondo, UniProt, DrugBank, PubChem, UniChem, HPO, GeneOntology, ClinVar, QuickGO, Ensembl, HGNC, Reactome, KEGG, Bioontology, BioPortal, EBIOLS, OBOFoundry, Zooma, InterPro, Pfam, PDB, STRING, EuropePMC, EUtils, Biolinker, DBpedia, OxO, Tyto, Wikidata

## Examples Requiring API Keys

Set environment variables before running these examples:

| Adapter | Environment Variable |
|---------|---------------------|
| Bioontology | `BIOPORTAL_API_KEY` |
| Bioportal | `BIOPORTAL_API_KEY` |
| UMLS | `UMLS_API_KEY` (or `UMLS_API_KEY_TU`) |
| DisGeNET | `DISGENET_API_KEY` |
| Cosmic | `COSMIC_API_KEY` |
| OMIM | `OMIM_API_KEY` |

## Using the Generator Scripts

### Generate All Examples
```bash
poetry run python docs/examples/generate_all_examples.py
```

### Generate Status Report
```bash
poetry run python docs/examples/generate_status.py
```
