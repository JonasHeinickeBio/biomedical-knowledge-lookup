# UniProt Adapter Documentation

## Overview
The UniProt adapter provides access to the UniProt protein database for protein sequence, function, and annotation information. It focuses on protein identification and basic metadata retrieval.

## Key Functions

### `search_concepts(query: str, limit: int = 20) -> List[UnifiedConcept]`
Searches for proteins by various identifiers or names.

**Parameters:**
- `query`: Search term (protein name, accession, gene name, etc.)
- `limit`: Maximum number of results to return

**Returns:** List of `UnifiedConcept` objects representing proteins

**Example Data Structure:**
```json
[
  {
    "primary_id": "P01375",
    "primary_label": "Tumor necrosis factor",
    "concept_type": "PROTEIN",
    "source_data": {
      "UNIPROT": {
        "primaryAccession": "P01375",
        "uniProtkbId": "TNFA_HUMAN",
        "proteinDescription": {
          "recommendedName": {
            "fullName": {
              "value": "Tumor necrosis factor"
            }
          }
        },
        "genes": [
          {
            "geneName": {
              "value": "TNF"
            }
          }
        ],
        "organism": {
          "scientificName": "Homo sapiens",
          "commonName": "Human"
        }
      }
    }
  }
]
```

### `get_concept_details(concept_id: str) -> None`
Currently not implemented - returns `None`.

**Parameters:**
- `concept_id`: UniProt accession number

**Returns:** `None` (placeholder for future implementation)

## Data Structures

### Protein Information Fields
- `primaryAccession`: UniProt accession number (e.g., "P01375")
- `uniProtkbId`: UniProtKB entry name (e.g., "TNFA_HUMAN")
- `proteinDescription`: Protein naming information
  - `recommendedName`: Preferred protein name
  - `alternativeNames`: Alternative names (if available)
- `genes`: Associated gene information
  - `geneName`: Gene symbol/name
- `organism`: Source organism information
  - `scientificName`: Scientific name
  - `commonName`: Common name
  - `taxonId`: NCBI taxonomy ID

### Additional Fields (in full records)
- `sequence`: Amino acid sequence information
- `features`: Protein features (domains, sites, variants)
- `comments`: Functional annotations and comments
- `keywords`: Associated keywords
- `references`: Literature references
- `databaseCrossReferences`: Cross-references to other databases

## Usage Examples

```python
# Search for proteins by name
proteins = await adapter.search_concepts("TNF-alpha", limit=10)

# Search by accession
proteins = await adapter.search_concepts("P01375")

# Search by gene symbol
proteins = await adapter.search_concepts("TNF")
```

## Notes
- Returns `UnifiedConcept` objects with protein type
- Limited to basic search functionality
- `get_concept_details` is not yet implemented
- Uses UniProt REST API for queries
- No authentication required (public API)
- Focuses on protein identification and naming
