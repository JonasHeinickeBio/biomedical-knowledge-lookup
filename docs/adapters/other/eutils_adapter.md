# EUtils Adapter Documentation

## Overview
The EUtils adapter provides access to NCBI's Entrez Programming Utilities (EUtils) for querying multiple NCBI databases including PubMed, Gene, Protein, and Taxonomy. It enables comprehensive literature mining and biological database access for ME/CFS and other biomedical research.

## Key Functions

### `search_concepts(query, limit=20)` [async]
Search multiple NCBI databases for biomedical concepts.

**Parameters:**
- `query`: Search term or phrase
- `limit`: Maximum number of results per database (default: 20)

**Returns:** `List[UnifiedConcept]` - Concepts from all queried databases

**Supported Databases:**
- `pubmed`: Literature citations
- `gene`: Gene information
- `protein`: Protein sequences
- `taxonomy`: Organism classification

**Example:**
```python
concepts = await adapter.search_concepts("myalgic encephalomyelitis", limit=20)
```

### `get_concept_details(concept_id)` [async]
Get detailed information about an NCBI database entry.

**Parameters:**
- `concept_id`: Full concept ID with database prefix (e.g., 'PMID:123456', 'GeneID:7157')

**Returns:** `UnifiedConcept` with full database record or `None`

**Supported ID Formats:**
- `PMID:{id}`: PubMed articles
- `GeneID:{id}`: Gene entries
- `TaxID:{id}`: Taxonomy entries
- `{accession}`: Direct accessions (auto-detected)

**Example:**
```python
details = await adapter.get_concept_details("PMID:12345678")
```

## API Information

### Endpoints
- **Base Service**: NCBI EUtils via bioservices library
- **Email Required**: Required by NCBI policy (configure via `ncbi_email` API key)

### Authentication
- **API Key**: Optional (set `ncbi_email` API key for higher rate limits)
- **Email**: Required by NCBI for all API access

### Environment Variables
- None required (email can be configured in config)

### Rate Limits
- Free tier: 3 requests per second
- With API key: 10 requests per second

## Data Types and Structures

### UnifiedConcept Fields by Database

#### PubMed (CITATION type)
- `primary_id`: `PMID:{pmid}`
- `primary_label`: Article title
- `concept_type`: `CITATION`
- `source_data`: Title, authors, database, description

#### Gene (GENE type)
- `primary_id`: `GeneID:{gene_id}`
- `primary_label`: Gene name
- `concept_type`: `GENE`
- `source_data`: Name, description, summary, database

#### Protein (PROTEIN type)
- `primary_id`: `Protein:{protein_id}`
- `primary_label`: Protein title
- `concept_type`: `PROTEIN`
- `source_data`: Title, accession, database

#### Taxonomy (ORGANISM type)
- `primary_id`: `TaxID:{tax_id}`
- `primary_label`: Scientific name
- `concept_type`: `ORGANISM`
- `source_data`: Scientific name, common name, database

### Source Data Fields
- `database`: Name of NCBI database (pubmed, gene, protein, taxonomy)
- `{db}_id`: NCBI identifier within that database
- Full record: Complete database entry

## Configuration
No special configuration required beyond standard LookupConfig.

```python
from knowledge_lookup.adapters.eutils_adapter import EUtilsAdapter
from knowledge_lookup.models import LookupConfig

config = LookupConfig()
config.api_keys['ncbi_email'] = 'your@email.com'  # Required by NCBI
adapter = EUtilsAdapter(config)
```

## Features
- **Multi-Database Search**: Query PubMed, Gene, Protein, Taxonomy simultaneously
- **Automated ID Parsing**: Detect database type from ID format
- **Comprehensive Results**: Full records with titles, descriptions, metadata
- **Email Configuration**: Support for NCBI-required email address
- **Batch Processing**: Efficient result limiting and distribution
- **Error Resilient**: Continues on individual database failures
- **Field Extraction**: Specialized extractors for each database type

## Error Handling
- bioservices import validation
- Email configuration check
- Database type detection failures
- ID parsing errors
- Network connectivity validation
- Comprehensive logging

## Usage Examples

### Basic Literature Search
```python
from knowledge_lookup.adapters.eutils_adapter import EUtilsAdapter

adapter = EUtilsAdapter(config)

# Search for ME/CFS literature
concepts = await adapter.search_concepts("myalgic encephalomyelitis", limit=20)

for concept in concepts:
    print(f"{concept.primary_label} ({concept.primary_id})")
```

### Gene Information
```python
# Search for gene information
concepts = await adapter.search_concepts("TP53", limit=10)

for gene in concepts:
    if gene.concept_type.value == 'gene':
        print(f"Gene: {gene.primary_label}")
        print(f"ID: {gene.primary_id}")
```

### Protein Details
```python
# Get detailed protein information
protein = await adapter.get_concept_details("Protein:NP_000537")

if protein:
    print(protein.primary_label)
    print(protein.source_data.get('title', 'N/A'))
```

### Taxonomy Search
```python
# Search for organism/taxonomy
concepts = await adapter.search_concepts("Homo sapiens", limit=5)

for taxon in concepts:
    print(f"{taxon.primary_label} - {taxon.primary_id}")
```

### Literature with Email
```python
# Configure with NCBI email for better rate limits
config.api_keys['ncbi_email'] = 'researcher@institution.edu'
adapter = EUtilsAdapter(config)

results = await adapter.search_concepts("chronic fatigue syndrome", limit=10)
```

## Architecture
The adapter uses the bioservices library to access NCBI EUtils. It queries multiple databases in parallel and processes results using database-specific extractors. Each result is converted to a UnifiedConcept with appropriate concept type based on the database source.

## Notes
- bioservices library must be installed (`pip install bioservices`)
- NCBI requires email for all API access
- Results are distributed across 4 databases (5 per database with default limit of 20)
- Accession number detection is based on common patterns (NP_, XP_, NM_, XM_, PMID_)
