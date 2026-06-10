# Additional Knowledge Source Adapters

This document provides documentation for additional adapters available in the Biomedical Knowledge Lookup package. These adapters extend the core functionality to support a wide range of biomedical knowledge sources.

## 📋 Quick Reference

| Adapter | Category | Description | API |
|---------|----------|-------------|-----|
| [DrugBank](#drugbank-adapter) | Chemicals | Drug and pharmaceutical information | OLS |
| [Ensembl](#ensembl-adapter) | Genes | Genome annotation and sequences | REST |
| [HPO](#hpo-human-phenotype-ontology-adapter) | Phenotypes | Human disease phenotypes | OLS/BioPortal |
| [GO](#gene-ontology-go-adapter) | Ontologies | Molecular functions and processes | OLS |
| [Reactome](#reactome-adapter) | Pathways | Biological pathways and reactions | REST |
| [WikiData](#wikidata-adapter) | Knowledge Base | Structured knowledge | SPARQL |
| [DBPedia](#dbpedia-adapter) | Knowledge Base | Wikipedia structured data | SPARQL |
| [OBO Foundry](#obo-foundry-adapter) | Ontologies | OBO Foundry collection | REST |
| [ZOOMA](#zooma-adapter) | Mappings | Ontology mapping service | REST |
| [TYTO](#tyto-adapter) | Recognition | Ontology term recognition | REST |
| [OxO](#oxo-adapter) | Cross-references | Ontology cross-references | REST |

---

## 💊 DrugBank Adapter

Provides access to DrugBank for comprehensive drug and pharmaceutical information through OLS.

### Overview

The DrugBank adapter enables querying DrugBank data (via OLS) to retrieve detailed information about:
- **Approved drugs**: FDA-approved medications
- **Investigational drugs**: Drugs in clinical trials
- **Drug targets**: Protein targets for drugs
- **Drug interactions**: Drug-drug interactions and food interactions
- **Dosage forms**: Pharmaceutical formulations

### Key Features

- Comprehensive drug database with over 13,000 drug entries
- Detailed pharmacological information
- Drug mechanism of action data
- Pharmacodynamic and pharmacokinetic properties
- FDA approval status and regulatory information

### Key Functions

- `search_concepts(query, limit=20)`: Search for drugs in DrugBank via OLS.
- `get_concept_details(concept_id)`: Get detailed drug information including indications, mechanisms, and interactions.

### Configuration

No special configuration required. Uses OLS endpoint.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a drug
results = await lookup.search_concepts(
    query="aspirin",
    sources=[KnowledgeSource.DRUGBANK]
)

# Get detailed drug information
for concept in results.concepts:
    details = await lookup.get_concept_details(
        concept_id=concept.primary_id,
        sources=[KnowledgeSource.DRUGBANK]
    )
    print(f"Drug: {details.primary_label}")
    print(f"Type: {details.concept_type.value}")
```

### Data Structure

```json
{
  "primary_id": "DB00001",
  "primary_label": "Aspirin",
  "concept_type": "CHEMICAL",
  "definitions": [
    "A salicylate that is the acetyl derivative of salicylic acid.",
    "ANALGESIC; ANTI-INFLAMMATORY; ANTIPLATELET"
  ],
  "identifiers": [
    {
      "source": "DRUGBANK",
      "identifier": "DB00001",
      "label": "Aspirin",
      "url": "https://www.drugbank.ca/drugs/DB00001"
    }
  ]
}
```

---

## 🧬 Ensembl Adapter

Integrates with Ensembl for comprehensive genome annotation and sequence data.

### Overview

The Ensembl adapter provides access to:
- **Genes**: Gene locations, transcripts, and products
- **Transcripts**: Alternative splice variants
- **Proteins**: Protein sequences and features
- **Variations**: SNPs and structural variations
- **Comparative genomics**: Orthologs and paralogs

### Key Features

- Genome annotation for 100+ species
- Gene tree and orthology data
- Regulatory region annotations
- Variation data including clinical significance
- Comparative genomics across species

### Key Functions

- `search_concepts(query, limit=20)`: Search for genes, transcripts, and proteins.
- `get_concept_details(concept_id)`: Get detailed genomic information including sequences and annotations.

### Configuration

```python
# Ensembl uses public REST API
# No API key required for basic usage
config.rate_limits[KnowledgeSource.ENSEMBL] = 5.0  # 5 requests/sec
```

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a gene
results = await lookup.search_concepts(
    query="BRCA1",
    sources=[KnowledgeSource.ENSEMBL]
)

# Get gene details with sequence
for concept in results.concepts:
    details = await lookup.get_concept_details(
        concept_id=concept.primary_id,
        sources=[KnowledgeSource.ENSEMBL]
    )
    print(f"Gene: {details.primary_label}")
    print(f"Location: {details.definitions}")
```

---

## 🎭 HPO (Human Phenotype Ontology) Adapter

Provides access to human disease phenotypes through OLS/BioPortal.

### Overview

The HPO adapter enables querying:
- **Phenotypic abnormalities**: Standardized phenotype terms
- **Phenotype-disease associations**: Links between phenotypes and diseases
- **Clinical features**: Symptom and sign descriptions
- **Phenotype ontologies**: Hierarchical phenotype relationships

### Key Features

- Standardized phenotype vocabulary
- Phenotype-disease association scores
- Hierarchical phenotype relationships (is-a, part-of)
- Cross-references to other ontologies (OMIM, MONDO)

### Key Functions

- `search_concepts(query, limit=20)`: Search for phenotype terms.
- `get_concept_details(concept_id)`: Get detailed phenotype information including definitions and relationships.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a phenotype
results = await lookup.search_concepts(
    query=" intellectual disability",
    sources=[KnowledgeSource.HPO]
)

# Get phenotype details
for concept in results.concepts:
    print(f"Phenotype: {concept.primary_label}")
    print(f"Definition: {concept.definitions}")
```

---

## 🏷️ Gene Ontology (GO) Adapter

Provides access to molecular functions, biological processes, and cellular components.

### Overview

The GO adapter enables querying:
- **Molecular Function**: Molecular activities of gene products
- **Biological Process**: Larger biological objectives
- **Cellular Component**: Locations within the cell

### Key Features

- Three independent ontologies (MF, BP, CC)
- Hierarchical structure with is-a and part-of relationships
- Gene product annotations
- GO term enrichment analysis support

### Key Functions

- `search_concepts(query, limit=20)`: Search for GO terms.
- `get_concept_details(concept_id)`: Get detailed GO term information including definitions and relationships.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a GO term
results = await lookup.search_concepts(
    query="kinase activity",
    sources=[KnowledgeSource.GO]
)

# Get GO term details
for concept in results.concepts:
    print(f"GO Term: {concept.primary_label}")
    print(f"Ontology: {concept.concept_type.value}")
```

---

## 🔄 Reactome Adapter

Integrates with Reactome for comprehensive biological pathways and reactions.

### Overview

The Reactome adapter enables querying:
- **Pathways**: Biological process hierarchies
- **Reactions**: Molecular events and transformations
- **Entities**: Proteins, small molecules, nucleic acids
- **Disease associations**: Pathway-disease links

### Key Features

- Manually curated pathways
- Pathway hierarchy (process > sub-process > reaction)
- Species-specific pathway data
- Literature references for each reaction

### Key Functions

- `search_concepts(query, limit=20)`: Search for pathways and reactions.
- `get_concept_details(concept_id)`: Get detailed pathway information including reactions and entities.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a pathway
results = await lookup.search_concepts(
    query="apoptosis",
    sources=[KnowledgeSource.REACTOME]
)

# Get pathway details
for concept in results.concepts:
    print(f"Pathway: {concept.primary_label}")
    print(f"Species: {concept.identifiers}")
```

---

## 🌐 WikiData Adapter

Accesses structured knowledge from WikiData's SPARQL endpoint.

### Overview

The WikiData adapter enables querying:
- **Biomedical entities**: Drugs, diseases, genes, proteins
- **Properties and relationships**: Structured knowledge
- **References and identifiers**: Cross-database links
- **Evidence and statements**: Claim support

### Key Features

- Large-scale structured knowledge
- Community-curated data
- SPARQL endpoint for complex queries
- Cross-references to multiple databases

### Key Functions

- `search_concepts(query, limit=20)`: Search for any biomedical entity.
- `get_concept_details(concept_id)`: Get detailed WikiData entity information including claims and references.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for an entity
results = await lookup.search_concepts(
    query="Alzheimer disease",
    sources=[KnowledgeSource.WIKIDATA]
)

# Get entity details
for concept in results.concepts:
    print(f"Entity: {concept.primary_label}")
    print(f"WikiData ID: {concept.identifiers}")
```

---

## 📚 DBPedia Adapter

Accesses structured data extracted from Wikipedia via SPARQL.

### Overview

The DBPedia adapter enables querying:
- **Entities**: People, places, concepts
- **Properties**:Structured attribute-value pairs
- **Categories**: Entity classifications
- **Abstracts**: Wikipedia-style summaries

### Key Features

- Structured extraction from Wikipedia
- SPARQL endpoint for querying
- English and multilingual versions
- Links to external databases

### Key Functions

- `search_concepts(query, limit=20)`: Search for Wikipedia-based entities.
- `get_concept_details(concept_id)`: Get detailed DBPedia resource information including properties and abstract.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for an entity
results = await lookup.search_concepts(
    query="Penicillin",
    sources=[KnowledgeSource.DBPEDIA]
)

# Get entity details
for concept in results.concepts:
    print(f"Entity: {concept.primary_label}")
    print(f"Abstract: {concept.definitions}")
```

---

## 🏗️ OBO Foundry Adapter

Provides access to the collection of OBO Foundry ontologies.

### Overview

The OBO Foundry adapter enables querying:
- **OBO Foundry ontologies**: GO, SO, PO, etc.
- **Cross-ontology relationships**: Links between ontologies
- **Ontology metadata**: Version, funding, maintainers

### Key Features

- Open Biological and Biomedical Ontologies
- Principles-compliant ontologies
- Ontology metadata and statistics
- Cross-reference support

### Key Functions

- `search_concepts(query, limit=20)`: Search across OBO ontologies.
- `get_concept_details(concept_id)`: Get detailed term information including definitions and relationships.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search across OBO ontologies
results = await lookup.search_concepts(
    query="enzyme",
    sources=[KnowledgeSource.OBO_FOUNDARY]
)

# Get term details
for concept in results.concepts:
    print(f"Term: {concept.primary_label}")
    print(f"Ontology: {concept.identifiers}")
```

---

## 🗺️ ZOOMA Adapter

Ontology mapping and annotation service from EBI.

### Overview

The ZOOMA adapter enables querying:
- **Ontology mappings**: Text-to-ontology mappings
- **Curated annotations**: Manually curated mappings
- **Automated annotations**: Algorithmic mappings
- **Mapping evidence**: Confidence scores and sources

### Key Features

- Automated ontology mapping
- Curated mapping database
- Evidence scores for mappings
- Support for multiple ontologies

### Key Functions

- `search_concepts(query, limit=20)`: Search for ontology mappings for text strings.
- `get_concept_details(concept_id)`: Get detailed mapping information including confidence and source.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for ontology mappings
results = await lookup.search_concepts(
    query="heart disease",
    sources=[KnowledgeSource.ZOOMA]
)

# Get mapping details
for concept in results.concepts:
    print(f"Text: {concept.primary_label}")
    print(f"Mapped to: {concept.identifiers}")
```

---

## 🦉 TYTO Adapter

Ontology term recognition and lookup.

### Overview

The TYTO adapter enables querying:
- **Ontology terms**: Terms from multiple ontologies
- **Term metadata**: Definitions, synonyms, relationships
- **Ontology information**: Source ontology details

### Key Features

- Multi-ontology term lookup
- Term recognition from text
- Ontology metadata
- Term relationships

### Key Functions

- `search_concepts(query, limit=20)`: Search for terms.
- `get_concept_details(concept_id)`: Get term details including definitions and relationships.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a term
results = await lookup.search_concepts(
    query="kinase",
    sources=[KnowledgeSource.TYTO]
)

# Get term details
for concept in results.concepts:
    print(f"Term: {concept.primary_label}")
    print(f"Ontology: {concept.identifiers}")
```

---

## 🔗 OxO Adapter

Ontology cross-reference service for finding mappings between terms.

### Overview

The OxO adapter enables querying:
- **Cross-references**: Term mappings between ontologies
- **Mapping evidence**: Sources and confidence scores
- **Path information**: Mapping paths through ontologies

### Key Features

- Term-level cross-references
- Evidence for mappings
- Multiple mapping paths
- Support for OBO Foundry ontologies

### Key Functions

- `get_mappings(concept_id)`: Find cross-references for a specific term.
- `search_concepts(query, limit=20)`: Search for terms with mappings.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Get cross-references for a term
results = await lookup.search_concepts(
    query="MONDO:0007254",
    sources=[KnowledgeSource.OXO]
)

# Get mapping details
for concept in results.concepts:
    print(f"Source term: {concept.primary_label}")
    print(f"Cross-references: {concept.identifiers}")
```

---

## 🔍 EBI OLS (Alternative) Adapter

Alternative implementation for EBI's Ontology Lookup Service.

### Overview

The EBI OLS adapter provides access to:
- **Ontologies**: All ontologies in OLS
- **Terms**: Terms within ontologies
- **Search**: Text-based search across all ontologies
- **Hierarchies**: Parent-child relationships

### Key Features

- EBI's Ontology Lookup Service
- Multi-ontology support
- Hierarchical term queries
- Ontology metadata

### Key Functions

- `search_concepts(query, limit=20)`: Search EBI OLS.
- `get_concept_details(concept_id)`: Get OLS term details including hierarchy and definitions.

### Example Usage

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource

lookup = CentralKnowledgeLookup()

# Search for a term
results = await lookup.search_concepts(
    query="cancer",
    sources=[KnowledgeSource.OLS]
)

# Get term details
for concept in results.concepts:
    print(f"Term: {concept.primary_label}")
    print(f"Ontology: {concept.identifiers}")
```

---

## Additional Resources

- [Main Documentation](../README.md) - Overview of all adapters
- [Adapter Index](index.md) - Complete adapter listing
- [API Reference](../api_reference.md) - API specifications
- [Getting Started](../getting_started.md) - Installation and setup
