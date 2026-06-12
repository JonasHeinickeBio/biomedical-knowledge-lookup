# DisGeNET Adapter Documentation

## Overview
The DisGeNET adapter provides access to the DisGeNET REST API for gene-disease association data. It focuses on retrieving associations between genes and diseases with evidence scores and metadata.

## Key Functions

### `get_concept_details(concept_id: str) -> Optional[UnifiedConcept]`
Retrieves detailed information about a specific disease by its DisGeNET ID.

**Parameters:**
- `concept_id`: DisGeNET disease ID (string)

**Returns:** `UnifiedConcept` with disease information or `None` if not found

**Example Data Structure:**
```json
{
  "primary_id": "C0005745",
  "primary_label": "Myocardial Infarction",
  "concept_type": "DISEASE",
  "source_data": {
    "DISGENET": {
      "diseaseid": "C0005745",
      "diseasename": "Myocardial Infarction",
      "diseaseVocabularies": ["UMLS", "MESH", "OMIM"],
      "diseaseUMLSCUI": "C0005745",
      "diseaseClasses_MSH": ["Cardiovascular Diseases"],
      "diseaseClasses_DO": ["cardiovascular system disease"],
      "disease_prevalence_class": "Common",
      "disease_inheritance": "Multifactorial"
    }
  }
}
```

### `get_gene_disease_associations(params: Dict[str, Any], raw: bool = False) -> Optional[Any]`
Queries gene-disease associations with flexible filtering parameters.

**Parameters:**
- `params`: Dictionary of query parameters (see supported parameters below)
- `raw`: If `True`, returns raw API response; if `False`, returns parsed data

**Supported Parameters:**
- `gene_ncbi_id`: NCBI gene ID(s) (string or comma-separated)
- `gene_ensembl_id`: Ensembl gene ID(s)
- `gene_symbol`: Gene symbol(s)
- `uniprot_id`: UniProt ID(s)
- `disease`: Disease ID(s) in various vocabularies
- `chemical_id`: Chemical compound ID(s)
- `source`: List of data sources
- `evidence_level`: Evidence level filter
- `min_score`, `max_score`: Score range filters
- `min_ei`, `max_ei`: Evidence index filters
- `min_dsi`, `max_dsi`: Disease specificity index filters
- `min_dpi`, `max_dpi`: Disease pleiotropy index filters
- `min_pli`, `max_pli`: Probability of loss-of-function intolerance filters
- `min_numCTs`: Minimum number of clinical trials
- `min_yearInitial`, `max_yearInitial`: Publication year range
- `type`: Association type
- `dis_class_list`: Disease class filters
- `page_number`: Pagination (integer)

**Returns:** List of parsed association data or raw API response

**Example Parsed Data Structure:**
```json
[
  {
    "assocID": "GDAA12345",
    "gene_symbol": "TNF",
    "gene_ncbi_id": 7124,
    "gene_ensembl_ids": ["ENSG00000232810"],
    "gene_type": "protein-coding",
    "disease_name": "Rheumatoid Arthritis",
    "disease_vocabularies": ["UMLS", "MESH", "OMIM"],
    "disease_umls_cui": "C0003873",
    "score": 0.85,
    "year_initial": 1980,
    "year_final": 2023,
    "num_pmids": 1250,
    "num_ct_supporting_association": 45,
    "gene_dsi": 0.678,
    "gene_dpi": 0.823,
    "gene_pli": 0.912,
    "gene_protein_str_ids": ["2AZ5", "5MU8"],
    "gene_protein_class_names": ["Cytokine", "Inflammatory mediator"],
    "disease_classes_msh": ["Musculoskeletal Diseases", "Immune System Diseases"],
    "disease_classes_umls_st": ["T047", "T050"],
    "disease_classes_do": ["musculoskeletal system disease", "immune system disease"],
    "disease_classes_hpo": ["HP:0001370", "HP:0002960"],
    "disease_prevalence_class": "Common",
    "disease_prevalence_geo_area": "Worldwide",
    "disease_prevalence_type": "Prevalent",
    "disease_inheritance": "Multifactorial",
    "ei": 0.923,
    "el": "Definitive"
  }
]
```

### `get_gene_disease_associations_evidence(params: Dict[str, Any], raw: bool = False) -> Optional[Any]`
Queries gene-disease associations with evidence-level details. Same parameters and return structure as `get_gene_disease_associations()` but includes more detailed evidence information.

### `search_concepts(query: str, limit: int = 20) -> List[UnifiedConcept]`
Searches for diseases associated with a specific gene.

**Parameters:**
- `query`: NCBI gene ID (string)
- `limit`: Maximum number of results (maps to page limit)

**Returns:** List of `UnifiedConcept` objects representing diseases

**Example Data Structure:**
```json
[
  {
    "primary_id": "C0003873",
    "primary_label": "Rheumatoid Arthritis",
    "concept_type": "UNKNOWN",
    "confidence_score": 0.85,
    "source_data": {
      "DISGENET": {
        "diseaseid": "C0003873",
        "diseasename": "Rheumatoid Arthritis",
        "score": 0.85,
        "geneNcbiID": 7124,
        "symbolOfGene": "TNF"
      }
    }
  }
]
```

## Data Structures

### Gene-Disease Association Fields
- `assocID`: Unique association identifier
- `gene_symbol`: HGNC gene symbol
- `gene_ncbi_id`: NCBI Gene ID
- `gene_ensembl_ids`: List of Ensembl gene IDs
- `gene_type`: Gene type (protein-coding, etc.)
- `disease_name`: Disease name
- `disease_vocabularies`: List of vocabularies used
- `disease_umls_cui`: UMLS CUI
- `score`: Association score (0-1)
- `year_initial`/`year_final`: Publication year range
- `num_pmids`: Number of supporting PubMed articles
- `num_ct_supporting_association`: Number of clinical trials
- `gene_dsi`: Disease specificity index
- `gene_dpi`: Disease pleiotropy index
- `gene_pli`: Loss-of-function intolerance probability
- `ei`: Evidence index
- `el`: Evidence level

### Disease Classification Fields
- `disease_classes_msh`: MeSH disease classes
- `disease_classes_umls_st`: UMLS semantic types
- `disease_classes_do`: Disease Ontology classes
- `disease_classes_hpo`: Human Phenotype Ontology classes
- `disease_prevalence_class`: Prevalence classification
- `disease_prevalence_geo_area`: Geographic prevalence
- `disease_prevalence_type`: Prevalence type
- `disease_inheritance`: Inheritance pattern

## Usage Examples

```python
# Get associations for a specific gene
params = {"gene_ncbi_id": "7124", "min_score": 0.5}
associations = await adapter.get_gene_disease_associations(params)

# Get disease details
disease = await adapter.get_concept_details("C0003873")

# Search diseases for a gene
diseases = await adapter.search_concepts("7124", limit=10)
```

## Notes
- Requires DisGeNET API key for full functionality
- Supports extensive filtering by gene, disease, evidence, and publication criteria
- Returns both summary and evidence-level association data
- Includes comprehensive disease classification and gene annotation metadata
