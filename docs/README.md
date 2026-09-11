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
| **CURIE Validation** | CURIE/URI parsing, validation, and normalization using bioregistry |

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
- **Optional**: `curies`, `pyobo`, `bioregistry` for CURIE validation and normalization

### Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

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

# Don't forget to close the lookup
await lookup.close()
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

### Configuration Example

```python
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

# Configure with custom settings
config = LookupConfig(
    cache_enabled=True,           # Enable caching
    cache_ttl=3600,              # Cache for 1 hour
    timeout_per_source=30.0,     # 30 second timeout
    max_results_per_source=50    # Max 50 results per source
)

lookup = CentralKnowledgeLookup(config)
```

### Close the Lookup

Always close the lookup when done to clean up resources:

```python
await lookup.close()
```

---

## Documentation Structure

```
docs/
├── README.md                        # This file - Overview and quick start
├── installation.md                  # Installation guide (4 methods, verification, troubleshooting)
├── architecture.md                  # System architecture, core components, data flow
├── guides/                          # In-depth guides for specific topics
│   ├── api_keys.md                  # API key setup for 7+ sources
│   ├── caching.md                   # Caching configuration and usage
│   ├── rate_limiting.md             # Rate limiting strategies and best practices
│   ├── error_handling.md            # Error handling patterns and examples
│   └── troubleshooting.md           # Common errors, debugging, performance tips
├── examples/                        # Usage examples and notebooks
│   ├── notebooks/                   # Jupyter notebooks (coming soon)
│   └── use_cases.md                 # Real-world use cases
├── adapters/                        # Knowledge source adapters
│   ├── index.md                     # Adapter index and categories
│   ├── core/                        # Core adapters (OpenTargets, ChEMBL, MONDO)
│   ├── chemical/                    # Chemical/compound sources
│   ├── protein/                     # Protein/gene sources
│   ├── disease/                     # Disease/ontology sources
│   ├── additional/                  # Additional supported sources
│   └── images/                      # Architecture diagrams
└── contributing.md                  # Contribution guide with adapter workflow
```

### Documentation Files

| File | Description |
|------|-------------|
| `README.md` | Overview, features, quick start |
| `installation.md` | Installation guide (pip, poetry, source, Docker) |
| `architecture.md` | System architecture and design patterns |
| `guides/api_keys.md` | API key setup for 7+ sources |
| `guides/caching.md` | Caching configuration and usage |
| `guides/rate_limiting.md` | Rate limiting strategies |
| `guides/error_handling.md` | Error handling patterns |
| `curie-management.md` | CURIE/URI parsing, validation, and normalization |
| `examples/use_cases.md` | Real-world use cases |
| `examples/notebooks/` | Jupyter notebooks |
| `adapters/index.md` | All adapters by category |
| `contributing.md` | Contribution guide with adapter workflow |

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
- **UMLS** - Unified Medical Language System
- **DrugBank** - Drug database
- **KEGG** - Kyoto Encyclopedia of Genes and Genomes

See `adapters/index.md` for the complete list with descriptions and implementation status.

### API Key Configuration

Some sources require API keys. Set them as environment variables:

```bash
export UMLS_API_KEY="your-umls-api-key"
export DISGENET_API_KEY="your-disgenet-api-key"
export BIOPORTAL_API_KEY="your-bioportal-api-key"
```

See `guides/api_keys.md` for detailed setup instructions for each source.

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

### Advanced Configuration

```python
config = LookupConfig(
    cache_enabled=True,           # Enable caching
    cache_ttl=3600,              # Cache for 1 hour
    cache_ttl_by_source={        # Per-source TTL overrides
        "BioPortal": 7200,       # 2 hours for BioPortal
        "UMLS": 1800,            # 30 minutes for UMLS
    },
    cache_dir="./cache",         # Cache directory
    cache_max_size=1000,         # Maximum cached items
    timeout_per_source=30.0,     # Timeout per source
    max_results_per_source=50    # Max results per source
)
```

See `guides/api_keys.md` for API key setup and `guides/caching.md` for caching documentation.

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

## Examples and Tutorials

### Use Cases

See `examples/use_cases.md` for real-world examples:

- **Drug Discovery** - Find drug targets and repurposing opportunities
- **Drug Repurposing** - Identify existing drugs for new diseases
- **Gene Discovery** - Find genes associated with diseases
- **Text Mining** - Extract knowledge from literature
- **Clinical Support** - Query disease ontologies for clinical decision support
- **Knowledge Graphs** - Build knowledge graphs from multiple sources
- **CURIE Validation** - CURIE/URI parsing, validation, and normalization using bioregistry

### Python Examples

See `examples/python/` for standalone Python scripts:
- `opentargets_example.py` - Open Targets Platform
- `chembl_example.py` - ChEMBL Database
- `mondo_example.py` - Mondo Disease Ontology
- `curie_validation_example.py` - CURIE/URI validation and parsing
- And more...

### Notebooks

For interactive examples, see `examples/notebooks/`:
- `01-getting-started.ipynb` - Basic usage
- `02-api-keys.ipynb` - API key configuration
- `03-rate-limiting.ipynb` - Rate limiting
- `04-error-handling.ipynb` - Error handling
- `05-curie-validation.ipynb` - CURIE/URI parsing and validation

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

## Changelog

### v1.0.0 (Current)

- Unified API for 29+ biomedical knowledge sources
- Async/await support throughout
- Caching system for performance optimization
- Rate limiting with automatic retry
- Comprehensive error handling
- Full type hints and Pydantic models
- Documentation structure overhaul with guides
- **CURIE validation and normalization** using bioregistry

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## Acknowledgments

---

# Acknowledgments

This framework integrates data from:

- [Open Targets](https://www.opentargets.org/)
- [ChEMBL](https://www.ebi.ac.uk/chembl/)
- [MONDO](https://mondo.monarchinitiative.org/)
- [UniProt](https://www.uniprot.org/)
- [EBI Ontology Lookup Service](https://www.ebi.ac.uk/ols4/)
- [NCBO BioPortal](https://bioportal.bioontology.org/)
- [DisGeNET](https://www.disgenet.org/)
- [Reactome](https://reactome.org/)
- [PubChem](https://pubchem.ncbi.nlm.nih.gov/)
- [KEGG](https://www.genome.jp/kegg/)
- [DrugBank](https://www.drugbank.ca/)
- [WikiData](https://www.wikidata.org/)

---

*For more information, see the [full documentation](https://biomedical-knowledge-lookup.readthedocs.io/).*

*For support, please open an issue on [GitHub](https://github.com/your-org/biomedical-knowledge-lookup/issues).*

*For API documentation, see `docs/guides/api_keys.md` and `docs/examples/use_cases.md`.*