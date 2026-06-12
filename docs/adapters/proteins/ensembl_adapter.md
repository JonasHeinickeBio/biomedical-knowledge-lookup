# Ensembl Adapter Documentation

## Overview
The Ensembl adapter provides access to the Ensembl genome database, offering gene annotation, genomic feature lookup, and comparative genomics data for multiple species.

## Key Functions

### Core Search Methods

#### `search_concepts(query, limit=20)` [async]
Search Ensembl for genes by symbol or name.

**Parameters:**
- `query`: Gene symbol or name (e.g., 'BRCA1', 'TP53')
- `limit`: Maximum results (default: 20)

**Returns:** `List[UnifiedConcept]` - Ensembl gene concepts

**Example Data Structure:**
```python
{
    'primary_id': 'ENSG00000012048',
    'primary_label': 'BRCA1',
    'concept_type': ConceptType.GENE,
    'definitions': ['BRCA1 DNA repair associated gene'],
    'categories': ['Biotype: protein_coding', 'Species: homo_sapiens'],
    'identifiers': [ConceptIdentifier(
        source='ENSEMBL',
        identifier='ENSG00000012048',
        label='BRCA1',
        url='https://www.ensembl.org/id/ENSG00000012048'
    )]
}
```

#### `get_concept_details(concept_id)` [async]
Get detailed gene information from Ensembl.

**Parameters:**
- `concept_id`: Ensembl Gene ID (e.g., 'ENSG00000012048')

**Returns:** `UnifiedConcept` or `None` - Detailed gene information

## Data Types and Structures

### UnifiedConcept Fields for Ensembl
- `primary_id`: Ensembl Gene ID (e.g., 'ENSG00000012048')
- `primary_label`: Gene symbol
- `concept_type`: GENE
- `definitions`: Gene descriptions
- `categories`: Biotype and species information
- `identifiers`: Ensembl identifiers with URL
- `source_data`: Raw Ensembl API response

### Ensembl-Specific Data Fields
- `id`: Ensembl stable ID
- `display_name`: Gene symbol
- `description`: Gene description
- `biotype`: Gene type (protein_coding, miRNA, etc.)
- `species`: Species name
- `seq_region_name`: Chromosome
- `start`: Genomic start position
- `end`: Genomic end position
- `strand`: Strand orientation

## API Information

**Base URL:** `https://rest.ensembl.org`

**Endpoints:**
- XRef Lookup: `/xrefs/symbol/{species}/{symbol}`
- ID Lookup: `/lookup/id/{ensembl_id}`

**Authentication:** Not required (public API)

**Rate Limits:** 15 requests per second (public policy)

**Content-Type Header:** Must include `application/json`

## Error Handling
- Species validation for gene lookups
- Ensembl ID format validation
- Rate limit awareness (15 req/s)
- Connection timeout handling
- Invalid response parsing
- Comprehensive logging

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = EnsemblAdapter(config)

# Search for genes by symbol
genes = await adapter.search_concepts('BRCA1', limit=5)

# Get detailed gene information
concept = await adapter.get_concept_details('ENSG00000012048')

# Check availability
if adapter.is_available():
    results = await adapter.search_concepts('TP53')
```

## Configuration
No special configuration required. The adapter is publicly available.

```python
config = LookupConfig()
adapter = EnsemblAdapter(config)
```

## Features
- **Genome Annotation**: Gene coordinates, biotypes, and descriptions
- **Multiple Species**: Support for 300+ vertebrate and major model organisms
- **Coordinate Mapping**: Genomic position information
- **Cross-References**: Links to NCBI, UniProt, and other databases
- **Strand Information**: Forward/reverse strand orientation
- **High Confidence**: 1.0 confidence score for matches

## Architecture
The adapter uses the Ensembl REST API. It performs gene symbol lookups via xrefs endpoint and retrieves detailed information via the lookup endpoint. Responses are normalized to the unified concept model.
