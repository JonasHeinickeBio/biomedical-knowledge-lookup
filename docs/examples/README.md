# Biomedical Knowledge Lookup - Examples

This directory contains examples for using the various adapters in the biomedical-knowledge-lookup package.

## Directory Structure

```
docs/examples/
├── README.md (this file)
├── availability_status.md    # Adapter availability and API key requirements
├── use_cases.md              # Common use cases and patterns
├── generate_status.py        # Generate availability status
├── generate_all_examples.py  # Generate all example scripts
├── all_adapters_test_results.json  # Test results
├── notebooks/                # Jupyter notebooks
│   ├── 01-getting-started.ipynb
│   ├── 02-api-keys.ipynb
│   ├── 03-rate-limiting.ipynb
│   ├── 04-error-handling.ipynb
│   └── README.md
├── python/                   # Standalone Python scripts
│
├── core/                     # Core knowledge sources (8 examples)
│   ├── ols_example.py
│   ├── umls_example.py
│   ├── opentargets_example.py
│   ├── chembl_example.py
│   ├── disgenet_example.py
│   ├── mondo_example.py
│   ├── uniprot_example.py
│   └── ...
│
├── chemicals/                # Drug and compound sources (3 examples)
│   ├── drugbank_example.py
│   ├── pubchem_example.py
│   └── unichem_example.py
│
├── phenotypes/               # Phenotype and disease sources (7 examples)
│   ├── hpo_example.py
│   ├── geneontology_example.py
│   ├── omim_example.py
│   ├── clinvar_example.py
│   ├── dbvar_example.py
│   ├── quickgo_example.py
│   └── ...
│
├── proteins/                 # Protein and gene sources (3 examples)
│   ├── uniprot_example.py
│   ├── ensembl_example.py
│   └── hgnc_example.py
│
├── pathways/                 # Pathway databases (2 examples)
│   ├── reactome_example.py
│   └── kegg_example.py
│
├── ontologies/               # Ontology services (5 examples)
│   ├── bioontology_example.py
│   ├── bioportal_example.py
│   ├── ebiols_example.py
│   ├── obofoundry_example.py
│   └── zooma_example.py
│
├── families/                 # Protein families (4 examples)
│   ├── interpro_example.py
│   ├── pfam_example.py
│   ├── pdb_example.py
│   └── string_example.py
│
├── literature/               # Literature sources (2 examples)
│   ├── europepmc_example.py
│   └── eutils_example.py
│
└── other/                    # Other/specialized sources (6 examples)
    ├── biolinker_example.py
    ├── cosmic_example.py
    ├── dbpedia_example.py
    ├── oxo_example.py
    ├── tyto_example.py
    └── wikidata_example.py
```

## Quick Start

```bash
# Set up environment (optional, for adapters requiring API keys)
export BIOPORTAL_API_KEY="your_api_key"
export UMLS_API_KEY_TU="your_api_key"
export DISGENET_API_KEY="your_api_key"
export COSMIC_API_KEY="your_api_key"
export OMIM_API_KEY="your_api_key"

# Run a specific example
poetry run python docs/examples/core/ols_example.py
poetry run python docs/examples/phenotypes/hpo_example.py
poetry run python docs/examples/chemicals/pubchem_example.py
```

## Available Examples

### Core Knowledge Sources (`core/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| OLS | Ontology Lookup Service | `core/ols_example.py` |
| UMLS | Unified Medical Language System | `core/umls_example.py` |
| OpenTargets | Drug targets and disease associations | `core/opentargets_example.py` |
| ChEMBL | Bioactive drug-like molecules | `core/chembl_example.py` |
| DisGeNET | Gene-disease associations | `core/disgenet_example.py` |
| Mondo | Disease ontology | `core/mondo_example.py` |
| UniProt | Protein sequences and functions | `core/uniprot_example.py` |

### Chemicals (`chemicals/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| DrugBank | Drug information and targets | `chemicals/drugbank_example.py` |
| PubChem | Chemical compounds and structures | `chemicals/pubchem_example.py` |
| UniChem | Drug cross-references | `chemicals/unichem_example.py` |

### Phenotypes (`phenotypes/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| HPO | Human phenotype ontology | `phenotypes/hpo_example.py` |
| GeneOntology | Gene function annotations | `phenotypes/geneontology_example.py` |
| OMIM | Online Mendelian Inheritance in Man | `phenotypes/omim_example.py` |
| ClinVar | Genomic variations and clinical significance | `phenotypes/clinvar_example.py` |
| QuickGO | Gene Ontology browser | `phenotypes/quickgo_example.py` |

### Proteins (`proteins/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| UniProt | Protein sequences and functions | `proteins/uniprot_example.py` |
| Ensembl | Genome annotation | `proteins/ensembl_example.py` |
| HGNC | Human gene nomenclature | `proteins/hgnc_example.py` |

### Pathways (`pathways/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| Reactome | Biological pathways | `pathways/reactome_example.py` |
| KEGG | Pathways and disease maps | `pathways/kegg_example.py` |

### Ontologies (`ontologies/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| Bioontology | BioOntology API | `ontologies/bioontology_example.py` |
| BioPortal | NCBI BioPortal ontologies | `ontologies/bioportal_example.py` |
| EBIOLS | EBI Ontology Lookup Service | `ontologies/ebiols_example.py` |
| OBOFoundry | Interoperable ontologies | `ontologies/obofoundry_example.py` |
| Zooma | Ontology annotation mapping | `ontologies/zooma_example.py` |

### Families (`families/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| InterPro | Protein domain classification | `families/interpro_example.py` |
| Pfam | Protein family database | `families/pfam_example.py` |
| PDB | Protein 3D structures | `families/pdb_example.py` |
| STRING | Protein-protein interactions | `families/string_example.py` |

### Literature (`literature/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| EuropePMC | Europe PMC literature search | `literature/europepmc_example.py` |
| EUtils | NCBI E-utilities | `literature/eutils_example.py` |

### Other (`other/`)
| Adapter | Description | Example |
|---------|-------------|---------|
| Biolinker | Biomedical concept linking | `other/biolinker_example.py` |
| Cosmic | Cancer gene mutations | `other/cosmic_example.py` |
| DBpedia | Wikipedia structured data | `other/dbpedia_example.py` |
| OxO | Ontology cross-references | `other/oxo_example.py` |
| Tyto | Ontology terms lookup | `other/tyto_example.py` |
| Wikidata | General knowledge from Wikidata | `other/wikidata_example.py` |

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

**Core:** OLS, UMLS, OpenTargets, ChEMBL, DisGeNET, Mondo, UniProt
**Chemicals:** DrugBank, PubChem, UniChem
**Phenotypes:** HPO, GeneOntology, ClinVar, QuickGO
**Proteins:** Ensembl, HGNC
**Pathways:** Reactome, KEGG
**Ontologies:** Bioontology, BioPortal, EBIOLS, OBOFoundry, Zooma
**Families:** InterPro, Pfam, PDB, STRING
**Literature:** EuropePMC, EUtils
**Other:** Biolinker, DBpedia, OxO, Tyto, Wikidata

## Examples Requiring API Keys

Set environment variables before running these examples:

| Adapter | Environment Variable |
|---------|---------------------|
| Bioontology | `BIOPORTAL_API_KEY` |
| Bioportal | `BIOPORTAL_API_KEY` |
| UMLS | `UMLS_API_KEY_TU` |
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
