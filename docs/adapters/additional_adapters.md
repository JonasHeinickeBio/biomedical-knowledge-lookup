# Additional Knowledge Source Adapters

This document covers documentation for additional adapters available in the Biomedical Knowledge Lookup package.

## 💊 DrugBank Adapter
Provides access to DrugBank for drug and pharmaceutical information (via OLS).

### Key Functions
- `search_concepts(query, limit=20)`: Search for drugs in DrugBank via OLS.
- `get_concept_details(concept_id)`: Get detailed drug information.

---

## 🧬 Ensembl Adapter
Integrates with Ensembl for genome annotation and sequence data.

### Key Functions
- `search_concepts(query, limit=20)`: Search for genes, transcripts, and proteins.
- `get_concept_details(concept_id)`: Get detailed genomic information.

---

## 🎯 OpenTargets Adapter
Provides access to Open Targets for drug target identification and validation.

### Key Functions
- `search_concepts(query, limit=20)`: Search for targets and diseases.
- `get_concept_details(concept_id)`: Get detailed target-disease associations.

---

## 🎭 HPO (Human Phenotype Ontology) Adapter
Provides access to human disease phenotypes (via OLS/BioPortal).

### Key Functions
- `search_concepts(query, limit=20)`: Search for phenotype terms.
- `get_concept_details(concept_id)`: Get detailed phenotype information.

---

## 🏷️ Gene Ontology (GO) Adapter
Provides access to molecular functions, biological processes, and cellular components.

### Key Functions
- `search_concepts(query, limit=20)`: Search for GO terms.
- `get_concept_details(concept_id)`: Get detailed GO term information.

---

## 🔄 Reactome Adapter
Integrates with Reactome for biological pathways and reactions.

### Key Functions
- `search_concepts(query, limit=20)`: Search for pathways and reactions.
- `get_concept_details(concept_id)`: Get detailed pathway information.

---

## 🌐 WikiData Adapter
Accesses structured knowledge from WikiData's SPARQL endpoint.

### Key Functions
- `search_concepts(query, limit=20)`: Search for any biomedical entity.
- `get_concept_details(concept_id)`: Get detailed WikiData entity information.

---

## 📚 DBPedia Adapter
Accesses structured data extracted from Wikipedia via SPARQL.

### Key Functions
- `search_concepts(query, limit=20)`: Search for Wikipedia-based entities.
- `get_concept_details(concept_id)`: Get detailed DBPedia resource information.

---

## 🏗️ OBO Foundry Adapter
Provides access to the collection of OBO Foundry ontologies.

### Key Functions
- `search_concepts(query, limit=20)`: Search across OBO ontologies.
- `get_concept_details(concept_id)`: Get detailed term information.

---

## 🗺️ ZOOMA Adapter
Ontology mapping and annotation service from EBI.

### Key Functions
- `search_concepts(query, limit=20)`: Search for ontology mappings for text strings.
- `get_concept_details(concept_id)`: Get detailed mapping information.

---

## 🦉 TYTO Adapter
Ontology term recognition and lookup.

### Key Functions
- `search_concepts(query, limit=20)`: Search for terms.
- `get_concept_details(concept_id)`: Get term details.

---

## 🔗 OxO Adapter
Ontology cross-reference service for finding mappings between terms.

### Key Functions
- `get_mappings(concept_id)`: Find cross-references for a specific term.
- `search_concepts(query, limit=20)`: Search for terms with mappings.

---

## 🔍 EBI OLS (Alternative) Adapter
Alternative implementation for EBI's Ontology Lookup Service.

### Key Functions
- `search_concepts(query, limit=20)`: Search EBI OLS.
- `get_concept_details(concept_id)`: Get OLS term details.
