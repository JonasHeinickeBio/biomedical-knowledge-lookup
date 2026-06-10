# ChEMBL Adapter Documentation

## Overview
The ChEMBL adapter provides access to the ChEMBL database, a comprehensive resource of bioactive molecules with drug-like properties. It uses the `chembl_webresource_client` library for API access.

## Key Functions

### Core Query Methods

#### `query(endpoint, filters=None, fields=None, limit=100)`
Generic query interface with built-in retry logic for ChEMBL endpoints.

**Parameters:**
- `endpoint`: ChEMBL endpoint name ('molecule', 'drug', 'target', 'activity')
- `filters`: Dict of query filters
- `fields`: List of specific fields to return
- `limit`: Maximum results (default: 100)

**Returns:** `List[dict]` - Raw ChEMBL data records

**Example:**
```python
# Get molecules with specific filters
results = adapter.query('molecule',
                       filters={'molecular_weight__lte': 500},
                       fields=['molecule_chembl_id', 'pref_name'],
                       limit=50)
```

### Entity-Specific Lookup Methods

#### `lookup_molecule(filters=None, fields=None, limit=100)`
Search for chemical compounds/molecules.

**Returns:** `List[UnifiedConcept]` with molecule data including:
- Chemical properties (MW, LogP, PSA, HBD/HBA counts)
- Structural information (SMILES, InChI)
- Therapeutic flags and categories
- Cross-references and identifiers

**Example Data Structure:**
```python
{
    'primary_id': 'CHEMBL25',
    'primary_label': 'ASPIRIN',
    'concept_type': ConceptType.CHEMICAL,
    'definitions': ['Non-steroidal anti-inflammatory drug (NSAID)'],
    'categories': ['Small Molecule', 'Therapeutic'],
    'identifiers': [ConceptIdentifier(source='ChEMBL', identifier='CHEMBL25', ...)]
}
```

#### `lookup_drug(filters=None, fields=None, limit=100)`
Search for approved drugs and clinical candidates.

**Returns:** `List[UnifiedConcept]` with drug information including:
- Drug names and synonyms
- Therapeutic indications
- Development phase and status
- Associated molecules and targets

#### `lookup_target(filters=None, fields=None, limit=100)`
Search for biological targets (proteins, genes, etc.).

**Returns:** `List[UnifiedConcept]` with target data including:
- Target names and synonyms
- Organism information
- Target type classification
- Sequence and structural data

#### `lookup_activity(filters=None, fields=None, limit=100)`
Search for bioactivity data (compound-target interactions).

**Returns:** `List[dict]` with activity measurements including:
- `molecule_chembl_id`: Compound identifier
- `target_chembl_id`: Target identifier
- `standard_type`: Activity type (IC50, EC50, Kd, etc.)
- `standard_value`: Numerical value
- `standard_units`: Units (nM, μM, etc.)
- `assay_chembl_id`: Assay identifier

### Specialized Query Methods

#### `get_activities_for_molecule(molecule_id, limit=50)`
Get all bioactivity data for a specific compound.

**Parameters:**
- `molecule_id`: ChEMBL molecule ID (e.g., 'CHEMBL25')

**Returns:** `List[dict]` - Activity records with 46+ fields each

#### `get_activities_for_target(target_id, limit=50)`
Get all bioactivity data for a specific target.

**Parameters:**
- `target_id`: ChEMBL target ID (e.g., 'CHEMBL1806')

**Returns:** `List[dict]` - Activity records with comprehensive assay data

### Search and Discovery Methods

#### `search_concepts(query, limit=20)` [async]
Search across molecules, drugs, and targets.

**Returns:** `List[UnifiedConcept]` - Unified concepts matching the query

#### `get_concept_details(concept_id)` [async]
Get detailed information for a specific ChEMBL entity.

**Returns:** `UnifiedConcept` or `None`

## Data Types and Structures

### UnifiedConcept Fields
- `primary_id`: ChEMBL identifier (e.g., 'CHEMBL25')
- `primary_label`: Preferred name
- `concept_type`: CHEMICAL, DRUG, PROTEIN, etc.
- `identifiers`: List of ConceptIdentifier objects
- `synonyms`: Alternative names
- `definitions`: Descriptions and properties
- `categories`: Classification terms
- `sources`: Set of knowledge sources
- `source_data`: Raw data from ChEMBL API

### Raw ChEMBL Data Fields
Molecules include: `molecule_chembl_id`, `pref_name`, `molecule_type`, `molecular_weight`, `alogp`, `canonical_smiles`

Drugs include: `drug_chembl_id`, `pref_name`, `drug_type`, `indication`, `phase`

Targets include: `target_chembl_id`, `pref_name`, `target_type`, `organism`, `tax_id`

Activities include: 46+ fields covering assay conditions, measurements, and metadata

## Error Handling
- Automatic retry with exponential backoff for transient API errors
- ChEMBL-specific error detection (HTML error pages, 5xx responses)
- Comprehensive logging of retry attempts and failures
- Graceful degradation with empty results on persistent failures

## Usage Examples

```python
# Initialize adapter
config = LookupConfig()
adapter = ChEMBLAdapter(config)

# Search for aspirin
molecules = adapter.lookup_molecule(filters={'pref_name__icontains': 'aspirin'})

# Get bioactivity data for aspirin
activities = adapter.get_activities_for_molecule('CHEMBL25')

# Search across all entities
results = await adapter.search_concepts('cancer')
```
