# Biomedical Knowledge Lookup

A unified Python framework for accessing multiple biomedical knowledge sources through a consistent API. This library provides seamless integration with major databases including Open Targets, ChEMBL, MONDO, UniProt, and many others.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/Documentation-API-blue.svg)](https://biomedical-knowledge-lookup.readthedocs.io/)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Documentation Structure](#documentation-structure)
- [Available Knowledge Sources](#available-knowledge-sources)
- [Adapter Architecture](#adapter-architecture)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The Biomedical Knowledge Lookup framework provides a unified interface to query multiple biomedical knowledge sources through a consistent `UnifiedConcept` data structure. Whether you need drug targets from Open Targets, compound data from ChEMBL, disease ontologies from MONDO, or protein sequences from UniProt — all sources are accessible through the same simple API.

### Designed For

- **Bioinformaticians** - Integrate multiple data sources into analysis pipelines
- **Drug Discovery Researchers** - Access target-disease associations and compound data
- **Clinical Researchers** - Query disease ontologies and phenotypic data
- **Computational Biologists** - Build knowledge graphs and network analyses

---

## Key Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Unified API** | Single interface for all knowledge sources |
| **Async First** | Native async/await support for concurrent queries |
| **Type Safe** | Full type hints with Pydantic models |
| **Rate Limited** | Built-in rate limiting for responsible API usage |
| **Error Handling** | Graceful degradation on partial failures |
| **Caching** | Optional caching for repeated queries |

### Data Integration

The framework supports multiple biomedical data categories:

| Category | Sources |
|----------|---------|
| **Diseases & Phenotypes** | MONDO, HPO, DisGeNET, Mondo |
| **Targets & Genes** | Open Targets, UniProt, Ensembl |
| **Chemicals & Drugs** | ChEMBL, PubChem, DrugBank, UniChem |
| **Ontologies** | OLS, BioPortal, OBO Foundry |
| **Proteins** | UniProt, Ensembl |
| **Pathways** | Reactome, KEGG |

---

## Installation

```bash
# Using pip
pip install biomedical-knowledge-lookup

# Using Poetry
poetry add biomedical-knowledge-lookup

# From source
git clone https://github.com/your-org/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
poetry install
```

### Requirements

- Python 3.10+
- AIOHTTP (async HTTP client)
- Pydantic (data validation)

---

## Quick Start

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

# Initialize the lookup engine
lookup = CentralKnowledgeLookup()

# Search for diabetes across multiple sources
result = await lookup.search_concepts(
    query="diabetes",
    sources=[
        KnowledgeSource.OPENTARGETS,
        KnowledgeSource.MONDO,
        KnowledgeSource.DISGENET
    ]
)

# Process results
for concept in result.concepts:
    print(f"{concept.primary_label}: {concept.concept_type.value}")
    print(f"  ID: {concept.primary_id}")
    print(f"  URL: {concept.get_identifier(KnowledgeSource.OPENTARGETS).url}")
```

### Search by Entity Type

```python
# Search for a specific gene
results = await lookup.search_concepts(
    query="BRCA1",
    sources=[KnowledgeSource.OPENTARGETS]
)

# Get detailed information
for concept in results.concepts:
    details = await lookup.get_concept_details(
        concept_id=concept.primary_id,
        sources=[KnowledgeSource.OPENTARGETS]
    )
    print(f"Biotype: {details.definitions}")
```

---

## Documentation Structure

```
docs/
├── README.md                  # This file - Overview and quick start
├── getting_started.md         # Installation and basic usage
├── api_reference.md           # Complete API documentation
├── architecture.md            # System architecture and design
├── adapters/
│   ├── index.md               # Adapter index and category listing
│   ├── opentargets_adapter.md # Open Targets Platform
│   ├── chembl_adapter.md      # ChEMBL Database
│   ├── disgenet_adapter.md    # Gene-Disease Associations
│   ├── uniprot_adapter.md     # UniProt Proteins
│   ├── mondo_adapter.md       # Mondo Disease Ontology
│   ├── ols_adapter.md         # Ontology Lookup Service
│   ├── additional_adapters.md # Additional supported sources
│   └── images/
│       └── architecture.md    # Architecture diagrams
└── examples/
    ├── basic_usage.ipynb      # Basic usage examples
    └── advanced_usage.ipynb   # Advanced integration patterns
```

### Documentation Files

| File | Description |
|------|-------------|
| `README.md` | Overview, features, quick start |
| `getting_started.md` | Installation and first steps |
| `api_reference.md` | Complete API specifications |
| `adapters/index.md` | All adapters by category |
| `adapters/opentargets_adapter.md` | Open Targets detailed docs |
| `adapters/additional_adapters.md` | Additional supported sources |
| `examples/` | Jupyter notebook examples |

---

## Available Knowledge Sources

### Core Sources (Fully Implemented)

| Source | API | Type | Auth | Description |
|--------|-----|------|------|-------------|
| **Open Targets** | GraphQL | Targets + Diseases | None | Drug target-disease evidence |
| **ChEMBL** | REST | Compounds + Targets | Optional | Bioactivities, drug properties |
| **MONDO** | REST | Diseases | None | Standardized disease ontology |
| **UniProt** | REST | Proteins | None | Protein sequences and functions |
| **DisGeNET** | REST | Gene-Disease | Required | Gene-disease associations |
| **OLS** | REST | Ontologies | None | EBI Ontology Lookup Service |
| **BioPortal** | REST | Ontologies | Required | NCBO BioPortal |
| **Ensembl** | REST | Genomes | None | Genome annotation |
| **Reactome** | REST | Pathways | None | Biological pathways |
| **PubChem** | REST | Compounds | None | Chemical compounds |

### Additional Sources

- **UniChem** - Compound cross-references
- **HGNC** - Human gene nomenclature
- **OBO Foundry** - OBO ontologies collection
- **WikiData** - Knowledge base
- **DBPedia** - Structured data
- **OxO** - Ontology cross-references

See `adapters/index.md` for the complete list with descriptions.

---

## Adapter Architecture

### Design Principles

```
┌─────────────────────────────────────────────────────────────┐
│                  CentralKnowledgeLookup                     │
│                    (Orchestrator)                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Adapter    │  │  Adapter    │  │  Adapter    │         │
│  │  OpenTargets│  │   ChEMBL    │  │   MONDO     │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                 │                │                │
│         ▼                 ▼                ▼                │
│  ┌──────────────────────────────────────────────┐         │
│  │          UnifiedConcept                      │         │
│  │  - Standardized data structure               │         │
│  │  - Type hints for safety                     │         │
│  │  - Cross-source deduplication                │         │
│  └──────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Adapter Interface

Each adapter implements the `KnowledgeSourceAdapter` interface:

```python
class KnowledgeSourceAdapter:
    """Base interface for all knowledge source adapters."""
    
    async def search_concepts(
        query: str, 
        limit: int = 20
    ) -> List[UnifiedConcept]:
        """Search for concepts matching the query."""
    
    async def get_concept_details(
        concept_id: str
    ) -> Optional[UnifiedConcept]:
        """Get detailed information for a specific concept."""
    
    def is_available() -> bool:
        """Check if the source is accessible."""
    
    def get_rate_limit() -> float:
        """Get the rate limit for this source."""
```

### Data Flow

1. **Query Construction** - Build source-specific query
2. **API Request** - Execute HTTP request with rate limiting
3. **Response Parsing** - Extract data from API response
4. **Normalization** - Map to `UnifiedConcept` structure
5. **Return** - Provide consistent interface to caller

---

## Configuration

### Basic Configuration

```python
from knowledge_lookup import LookupConfig, KnowledgeSource

# Create configuration
config = LookupConfig()

# Set rate limits (requests per second)
config.rate_limits[KnowledgeSource.OPENTARGETS] = 2.0
config.rate_limits[KnowledgeSource.CHEMBL] = 1.0

# Set per-source timeout (seconds)
config.timeout_per_source = 30.0
```

### API Key Configuration

```python
import os

# Set required API keys as environment variables
os.environ["UMLS_API_KEY"] = "your-umls-api-key"
os.environ["DISGENET_API_KEY"] = "your-disgenet-api-key"
os.environ["BIOPORTAL_API_KEY"] = "your-bioportal-api-key"
```

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run linters
poetry run pre-commit run --all-files
```

### Contribution Guidelines

- All code should have type hints
- New adapters must include comprehensive tests
- Documentation should be updated for new features
- Follow the existing code style

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Citation

If you use this framework in your research, please cite:

```bibtex
@software{biomedical-knowledge-lookup,
  title={Biomedical Knowledge Lookup: A unified framework for accessing multiple biomedical knowledge sources},
  author={Your Name},
  year={2024},
  url={https://github.com/your-org/biomedical-knowledge-lookup}
}
```

---

## Acknowledgments

This framework integrates data from:

- [Open Targets](https://www.opentargets.org/)
- [ChEMBL](https://www.ebi.ac.uk/chembl/)
- [MONDO](https://mondo.monarchinitiative.org/)
- [UniProt](https://www.uniprot.org/)
- [EBI Ontology Lookup Service](https://www.ebi.ac.uk/ols4/)
- [NCBO BioPortal](https://bioportal.bioontology.org/)

---

*For more information, see the [full documentation](https://biomedical-knowledge-lookup.readthedocs.io/).*