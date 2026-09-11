# 🧬 Biomedical Knowledge Lookup

[![PyPI version](https://badge.fury.io/py/biomedical-knowledge-lookup.svg)](https://pypi.org/project/biomedical-knowledge-lookup/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/actions/workflows/tests.yml/badge.svg)](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/codecov/c/github/JonasHeinickeBio/biomedical-knowledge-lookup)](https://codecov.io/gh/JonasHeinickeBio/biomedical-knowledge-lookup)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://jonasheinickeBio.github.io/biomedical-knowledge-lookup/)
[![PyPI downloads](https://img.shields.io/pypi/dm/biomedical-knowledge-lookup?color=blue)](https://pypi.org/project/biomedical-knowledge-lookup/)
[![GitHub last commit](https://img.shields.io/github/last-commit/JonasHeinickeBio/biomedical-knowledge-lookup)](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/commits/main)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1234567.svg)](https://doi.org/10.5281/zenodo.1234567)

A unified Python library for biological concept lookup across **29+ biomedical knowledge sources** including BioPortal, OLS, UMLS, ChEMBL, DisGeNET, and more. Built for bioinformatics researchers, knowledge graph developers, and biomedical data scientists.

## ✨ Features

- **🔍 29+ Knowledge Sources**: Comprehensive coverage of biomedical ontologies and databases
- **✅ CURIE Validation**: Built-in CURIE/URI validation and normalization using bioregistry
- **⚡ Unified API**: Single interface for all sources with consistent results
- **🔄 Multi-source Annotation**: Cross-reference concepts across multiple databases
- **📊 RDF Export**: Convert results to RDF format for knowledge graphs
- **💾 Intelligent Caching**: Built-in caching system for performance optimization
- **🔄 Async Support**: Asynchronous operations for scalable applications
- **🧪 Comprehensive Testing**: Full test suite with unit and integration tests
- **📚 Rich Documentation**: Extensive examples and API documentation

## 🚀 Quick Start

### Installation

```bash
# core — all HTTP-only adapters (OLS, BioPortal, MONDO, HPO, UniProt, DrugBank,
# OxO, Zooma, PubChem, Ensembl, …), CURIE parsing, RDF export
pip install biomedical-knowledge-lookup

# optional feature groups (add one or more)
pip install "biomedical-knowledge-lookup[curie]"        # bioregistry/curies/pyobo CURIE normalization
pip install "biomedical-knowledge-lookup[umls]"         # UMLS adapter (needs a UMLS API key)
pip install "biomedical-knowledge-lookup[chembl]"       # ChEMBL adapter
pip install "biomedical-knowledge-lookup[bioservices]"  # EUtils / QuickGO / UniChem adapters
pip install "biomedical-knowledge-lookup[tyto]"         # Tyto adapter (owlready2)
pip install "biomedical-knowledge-lookup[agents]"       # LangGraph LLM agent workflow
pip install "biomedical-knowledge-lookup[export]"       # pandas DataFrame / Excel export
pip install "biomedical-knowledge-lookup[all]"          # everything

# from source
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
poetry install                          # core + dev
poetry install --all-extras             # everything
poetry install --extras "curie umls"    # selected groups
```

The **core install pulls no heavy dependencies** — every optional dependency
guards its own import, so `import knowledge_lookup` and all HTTP-only adapters
work without any extra, and an adapter/feature that needs a missing extra is
simply disabled (a clear `ImportError` if you instantiate it directly). CURIE
validation via the `curie` extra enables bioregistry-based CURIE/URI parsing,
validation, and normalization using the [bioregistry](https://github.com/bioregistry/bioregistry),
[curies](https://github.com/cthoyt/curies), and [pyobo](https://github.com/pyobo/pyobo) libraries.

### Basic Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

# Initialize the lookup system
lookup = CentralKnowledgeLookup()

# Search for concepts across multiple sources
results = await lookup.search_concepts(
    "diabetes mellitus",
    sources=[KnowledgeSource.BIOPORTAL, KnowledgeSource.OLS, KnowledgeSource.UMLS]
)

# Get detailed information about a specific concept
concept_details = await lookup.get_concept_details("DOID:9351")
```

### Advanced Usage with Multi-source Annotation

```python
from knowledge_lookup import MultiSourceAnnotator

# Annotate text with concepts from multiple sources
annotator = MultiSourceAnnotator()
annotations = await annotator.annotate_text(
    "Type 2 diabetes is associated with insulin resistance",
    confidence_threshold=0.7
)

# Get consensus annotations across sources
consensus = annotator.get_consensus_annotations(annotations)
```

## 📋 Supported Knowledge Sources

| Source | Description | API Key Required |
|--------|-------------|------------------|
| **BioPortal** | NCBI BioPortal ontology repository | Yes |
| **OLS** | Ontology Lookup Service | No |
| **UMLS** | Unified Medical Language System | Yes |
| **ChEMBL** | Chemical database | No |
| **DisGeNET** | Disease-gene associations | No |
| **DrugBank** | Drug information database | No |
| **Ensembl** | Genome annotation database | No |
| **Gene Ontology** | Molecular function/process/component | No |
| **HPO** | Human Phenotype Ontology | No |
| **Mondo** | Mondo Disease Ontology | No |
| **OpenTargets** | Target-disease associations | No |
| **PubChem** | Chemical information | No |
| **Reactome** | Pathway database | No |
| **UniProt** | Protein sequence database | No |
| **WikiData** | Structured knowledge base | No |
| **ZOOMA** | Ontology mapping service | No |
| **And 13+ more...** | See full list in documentation | Varies |

## 🏗️ Architecture

```
knowledge_lookup/
├── adapters/           # Individual source adapters
├── models.py          # Data models and enums
├── central_lookup.py  # Main lookup coordinator
├── multi_source_annotator.py  # Cross-source annotation
├── rdf_converter.py   # RDF export utilities
├── cache.py          # Caching system
└── base.py           # Abstract base classes
```

## 📖 Documentation

- **[Getting Started Guide](docs/getting_started.md)**
- **[API Reference](docs/api_reference.md)**
- **[CURIE Management](docs/curie-management.md)** - CURIE/URI parsing, validation, and normalization
- **[Adapter Documentation](docs/adapters/)**
- **[Examples](examples/)**
- **[Contributing Guide](CONTRIBUTING.md)**

### Additional Resources

- **[Documentation Improvement Summary](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/wiki/Documentation-Improvement-Summary)**
- **[Project Overview](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/wiki/Project-Overview)**

### Example Notebooks

Explore interactive examples in the `examples/` directory:
- Basic concept lookup
- Multi-source annotation
- RDF export and knowledge graph construction
- Performance benchmarking

## 🔧 Configuration

### CURIE Validation

The `curie` extra adds a standalone `curie_utils` toolkit built on
[bioregistry](https://bioregistry.io/) for validating and normalizing CURIEs
and URIs. It is not yet wired into `CentralKnowledgeLookup`'s query
parsing or deduplication — see [CURIE Management](docs/curie-management.md)
for the full picture and for cross-ontology mapping via
`find_mappings()`/OxO.

```python
from knowledge_lookup.curie_utils import normalize_curie, validate_prefix

# Validate prefixes
is_valid = validate_prefix("doid")  # True
is_valid = validate_prefix("invalid_prefix")  # False

# Normalize a CURIE's prefix to bioregistry's canonical form (same ontology,
# not a cross-ontology mapping)
normalized = normalize_curie("DOID:9351")  # "doid:9351"
```

### API Keys

Some sources require API keys. Set them as environment variables:

```bash
export BIOPORTAL_API_KEY="your_key_here"
export UMLS_API_KEY="your_key_here"
# ... etc
```

Or create a `.env` file:

```env
BIOPORTAL_API_KEY=your_key_here
UMLS_API_KEY=your_key_here
```

### Advanced Configuration

```python
from knowledge_lookup import LookupConfig

config = LookupConfig(
    rate_limits={
        KnowledgeSource.BIOPORTAL: 10,  # requests per second
        KnowledgeSource.OLS: 20,
    },
    cache_enabled=True,
    cache_dir="./cache"
)

lookup = CentralKnowledgeLookup(config)
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run specific test categories
poetry run pytest -m "unit"        # Unit tests only
poetry run pytest -m "integration" # Integration tests
poetry run pytest -m "not slow"    # Skip slow tests

# Run with coverage
poetry run pytest --cov=knowledge_lookup
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Adding New Adapters

1. Extend `KnowledgeSourceAdapter` in `base.py`
2. Implement required methods: `search_concepts()`, `get_concept_details()`
3. Add CURIE validation using `curie_utils` module
4. Add to `adapters/__init__.py`
5. Add tests in `tests/unit/test_adapters/`
6. Update documentation

### CURIE Validation in Adapters

When implementing adapters, use the `curie_utils` module for CURIE validation:

```python
from ..curie_utils import validate_prefix, normalize_curie, parse_curie_or_uri

# Validate prefix before queries
if validate_prefix("doid"):
    logger.debug("doid is a known bioregistry prefix")

# Parse query as CURIE/URI
parsed = parse_curie_or_uri(query)
if parsed:
    prefix, identifier = parsed

# Normalize a CURIE's prefix to its canonical bioregistry form
normalized = normalize_curie("DOID:9351")  # "doid:9351"
```

### Development Setup

```bash
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup
poetry install
poetry run pre-commit install
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built upon the AID-PAIS Knowledge Graph project
- Thanks to all contributors and the biomedical research community
- Special thanks to the maintainers of the various knowledge sources

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/issues)
- **Discussions**: [GitHub Discussions](https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/discussions)
- **Email**: jonas.heinicke@helmholtz-hzi.de

## 🔬 Citation

If you use this library in your research, please cite:

```bibtex
@software{heinicke_biomedical_knowledge_lookup_2025,
  author = {Heinicke, Jonas},
  title = {Biomedical Knowledge Lookup: Unified biological concept lookup across 29+ biomedical knowledge sources},
  url = {https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup},
  version = {1.0.0},
  year = {2025}
}
```

---

<p align="center">
  <img src="https://img.shields.io/github/stars/JonasHeinickeBio/biomedical-knowledge-lookup?style=social" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/JonasHeinickeBio/biomedical-knowledge-lookup?style=social" alt="GitHub forks">
</p>

<p align="center">
  <em>⭐ Star this repository if you find it useful!</em>
</p>
