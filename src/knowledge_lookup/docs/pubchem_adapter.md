# PubChem Adapter Documentation

## Overview
The PubChem adapter provides access to the PubChem database for chemical compounds, drugs, and small molecules. It focuses on compound identification and basic property retrieval.

## Key Functions

### `search_concepts(query: str, limit: int = 20) -> List[str]`
Searches for compounds by name and returns PubChem Compound IDs (CIDs).

**Parameters:**
- `query`: Compound name to search for
- `limit`: Maximum number of CIDs to return

**Returns:** List of PubChem Compound IDs (strings)

**Example Data Structure:**
```json
["2244", "1983", "3672", "444795", "11954396"]
```

### `get_concept_details(concept_id: str) -> Dict[str, Any]`
Retrieves detailed information about a compound by its PubChem CID.

**Parameters:**
- `concept_id`: PubChem Compound ID (string)

**Returns:** Raw PubChem JSON data structure

**Example Data Structure:**
```json
{
  "PC_Compounds": [
    {
      "id": {
        "id": {
          "cid": 2244
        }
      },
      "atoms": {
        "aid": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        "element": [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6]
      },
      "bonds": {
        "aid1": [1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18, 19, 19, 20],
        "aid2": [2, 15, 16, 3, 17, 4, 18, 5, 19, 6, 20, 7, 21, 8, 22, 9, 23, 10, 24, 11, 25, 12, 26, 13, 27, 14, 28, 15, 29, 16, 30, 17, 31, 18, 32, 19, 33, 20, 34, 21],
        "order": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
      },
      "props": [
        {
          "urn": {
            "label": "IUPAC Name",
            "name": "Preferred"
          },
          "value": {
            "sval": "2-(4-(2-methylpropyl)phenyl)propanoic acid"
          }
        },
        {
          "urn": {
            "label": "Molecular Formula"
          },
          "value": {
            "sval": "C13H18O2"
          }
        },
        {
          "urn": {
            "label": "Molecular Weight"
          },
          "value": {
            "fval": 206.28
          }
        },
        {
          "urn": {
            "label": "InChI"
          },
          "value": {
            "sval": "InChI=1S/C13H18O2/c1-9(2)8-11-3-5-12(6-4-11)10(7)13(14)15/h3-7,9-10H,8H2,1-2H3,(H,14,15)"
          }
        },
        {
          "urn": {
            "label": "InChIKey"
          },
          "value": {
            "sval": "HEFNNWSXXWATRW-UHFFFAOYSA-N"
          }
        },
        {
          "urn": {
            "label": "SMILES"
          },
          "value": {
            "sval": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
          }
        }
      ]
    }
  ]
}
```

## Data Structures

### Compound Properties
- `IUPAC Name`: Systematic chemical name
- `Molecular Formula`: Chemical formula (e.g., "C13H18O2")
- `Molecular Weight`: Molecular mass in g/mol
- `InChI`: IUPAC International Chemical Identifier
- `InChIKey`: Hashed InChI for database lookups
- `SMILES`: Simplified Molecular Input Line Entry System notation

### Structural Information
- `atoms`: Atomic information with element types and positions
- `bonds`: Bond connectivity between atoms
- `stereo`: Stereochemical information (when available)

## Usage Examples

```python
# Search for compounds by name
cids = await adapter.search_concepts("ibuprofen", limit=5)
# Returns: ["3672"]

# Get detailed compound information
details = await adapter.get_concept_details("3672")
# Returns full PubChem compound record
```

## Notes
- Returns raw PubChem JSON structures
- Focuses on compound identification and basic properties
- Does not implement UnifiedConcept conversion
- Limited to compound search and detail retrieval
- No authentication required (public API)
