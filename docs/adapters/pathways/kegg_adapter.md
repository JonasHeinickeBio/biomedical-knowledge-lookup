---
description: KEGG pathways, genes, compounds, diseases and drugs through the public KEGG REST API.
---

# KEGG adapter

Searches the Kyoto Encyclopedia of Genes and Genomes and fetches entries by identifier, with cross-database links as mappings and gene-pathway links as relationships. KEGG is free for academic use; check its licence before commercial use.

| | |
|---|---|
| Source | `KnowledgeSource.KEGG` |
| Class | `knowledge_lookup.adapters.KEGGAdapter` |
| Requires | none |
| Identifiers | `hsa00010` (pathway), `C11378` (compound), `H00409` (disease), `D00109` (drug) |
| Upstream API | `https://rest.kegg.jp` |

## Overview

The KEGG Adapter provides access to the Kyoto Encyclopedia of Genes and Genomes
(KEGG) via the public REST API at `https://rest.kegg.jp`. It supports the `find`,
`get`, and `link` REST operations, covering pathways, genes, compounds, enzymes,
reactions, orthology, networks, glycans, diseases and drugs.

### Purpose
- Search across multiple KEGG databases in a single call
- Retrieve full entry records for any KEGG identifier
- Resolve cross-database references (`DBLINKS`) as concept mappings
- Traverse `gene ⇄ pathway` links as concept relationships
- Support pathway analysis and systems biology workflows

### Scope
- Biological pathways (metabolism, signaling, cellular processes)
- Organism-specific and reference (`map/ko`) pathway identifiers
- Genes (organism-scoped, default human `hsa`), KEGG Orthology (KO) groups
- Compounds, glycans, enzymes (EC numbers) and reactions
- Human diseases and drug information
- BRITE functional hierarchies and disease/drug networks

## Key Features

- **Multi-database search**: query any of 10 KEGG `find` databases
- **Organism-scoped gene search**: `gene` searches respect an organism code
- **Full record retrieval**: `get` parsing of KEGG flat-text entries
- **Cross-references**: `DBLINKS` blocks become concept mappings
- **Relationship traversal**: `link` operation for gene/pathway relations
- **No authentication**: KEGG is a free public service

## API Information

### Endpoint
- **Base URL**: `https://rest.kegg.jp`

### Authentication
- **Required**: No
- **API Key**: Not required (public service)

### Environment Variables
- None required

## Supported Databases

`KEGGAdapter.supported_databases()` returns the databases accepted by the
`databases` argument of `search_concepts`:

| Database     | Concept type        | Notes                              |
|--------------|---------------------|------------------------------------|
| `pathway`    | `PATHWAY`           | reference + organism maps          |
| `gene`       | `GENE`              | organism-scoped (`organism` arg)   |
| `compound`   | `CHEMICAL`          |                                    |
| `glycan`     | `CHEMICAL`          |                                    |
| `enzyme`     | `MOLECULAR_FUNCTION`| EC numbers                         |
| `reaction`   | `BIOLOGICAL_PROCESS`|                                    |
| `orthology`  | `GENE`              | KO groups                          |
| `network`    | `PATHWAY`           | disease/drug networks              |
| `disease`    | `DISEASE`           | default search                     |
| `drug`       | `DRUG`              | default search                     |

`search_concepts` defaults to `("disease", "drug")` to keep orchestrated
lookups precise; pass `databases=[...]` to widen the search.

## Key Methods

### `search_concepts(query, limit=20, *, databases=None, organism="hsa") -> list[UnifiedConcept]`

Search KEGG using the `find` operation across one or more databases.

**Parameters:**
- `query` (str): Search term (name, keyword, or chemical formula). URL-encoded
  automatically, so multi-word queries such as `"Coenzyme Q10"` work.
- `limit` (int): Maximum number of results across all selected databases
  (default: 20).
- `databases` (list[str] | None): Databases to search (see table above).
  Defaults to `("disease", "drug")`. Unknown names are skipped with a warning.
- `organism` (str): Organism code used for organism-scoped databases such as
  `gene` (default `"hsa"`). Note that plain `find/gene` is rejected by KEGG
  (HTTP 400); the organism code is required and applied automatically.

**Returns:**
- List of `UnifiedConcept` objects with `concept_type` set per database.

**Example:**
```python
concepts = await adapter.search_concepts("diabetes", databases=["pathway"])
genes = await adapter.search_concepts("INS", databases=["gene"], organism="hsa")
```

### `get_concept_details(concept_id) -> UnifiedConcept | None`

Retrieve and parse a full KEGG entry via the `get` operation. Accepts bare or
prefixed identifiers and resolves the correct KEGG entry internally.

**Parameters:**
- `concept_id` (str): KEGG ID, e.g. `"H00001"`, `"D00001"`, `"C01405"`,
  `"hsa:1953"`, `"hsa00010"`, `"path:hsa00010"`, `"2.7.1.1"`, `"K00844"`.

**Returns:**
- `UnifiedConcept` with parsed fields, or `None` if the ID cannot be resolved.

**Example:**
```python
entry = await adapter.get_concept_details("hsa00010")
```

### `get_mappings(concept_id) -> list[dict]`

Parse the `DBLINKS` block of an entry into cross-database reference dicts
(KEGG's `conv` operation only supports whole-database conversions).

**Returns:** list of `{fromId, toId, fromSource, toSource, mappingType, confidence}`.

```python
mappings = await adapter.get_mappings("C11378")  # CoQ10 → PubChem, ChEBI, ...
```

### `get_relationships(concept_id) -> list[dict]`

Traverse KEGG `link` relations. Supported entry types:

- **gene** → linked pathways (`relation_label="in_pathway"`, source
  `KEGG_PATHWAY`)
- **pathway** → member genes (`relation_label="has_gene"`, source `KEGG_GENE`)

Other entry types return `[]` without a network call.

```python
rels = await adapter.get_relationships("hsa:3939")  # gene → pathways
```

## Configuration

```python
from knowledge_lookup.adapters.kegg_adapter import KEGGAdapter
from knowledge_lookup.models import LookupConfig

adapter = KEGGAdapter(LookupConfig())
```

## Usage Examples

### Multi-database search
```python
results = await adapter.search_concepts(
    "ubiquinone",
    databases=["compound", "pathway"],
    limit=10,
)
for concept in results:
    print(concept.primary_id, concept.primary_label, concept.concept_type)
```

### Get entry details
```python
entry = await adapter.get_concept_details("C11378")  # Coenzyme Q10
if entry:
    print(entry.primary_label)   # Ubiquinone-10
    print(entry.synonyms)        # ['Ubidecarenone', 'Coenzyme Q10', ...]
```

### Cross-references and relationships
```python
mappings = await adapter.get_mappings("C11378")
pathways = await adapter.get_relationships("hsa:3939")  # LDHA -> pathways
```

## Real-World Example: Coenzyme Q10 (CoQ10)

Coenzyme Q10 is catalogued by KEGG as **Ubiquinone-10** (compound `C11378`).
KEGG's `find` matches the full names (`"ubiquinone-10"`, `"Coenzyme Q10"`) but
**not** the `"CoQ10"` abbreviation — a useful reminder to try synonyms.

```python
# 1. Resolve the compound by synonym
hits = await adapter.search_concepts("Coenzyme Q10", databases=["compound"])
coq10 = next(c for c in hits if c.primary_id == "C11378")

# 2. Full record + synonyms
entry = await adapter.get_concept_details("C11378")
print(entry.synonyms)  # includes 'Coenzyme Q10', 'Ubidecarenone'

# 3. External cross-references
for m in await adapter.get_mappings("C11378"):
    print(m["toSource"], m["toId"])  # PubChem, CAS, ChEBI, LIPIDMAPS, ...
```

Compounds have no `link` relations, so `get_relationships("C11378")` returns
`[]`; use gene/pathway entries for relationship traversal.

## Error Handling

- **Search failures**: return an empty list, error logged.
- **Invalid/unresolvable IDs**: `get_concept_details` returns `None`;
  `get_mappings`/`get_relationships` return `[]` (no network call).
- **Network errors**: caught, logged, and reported via the circuit breaker.
- **Parsing errors**: handled gracefully with `logger.error`.

## Rate Limiting

KEGG is a free service that asks callers to stay under ~10 requests/second.
The adapter enforces per-source rate limiting via the base class
`KnowledgeSourceAdapter` and honours the shared `CircuitBreaker`.

## Data Model Mapping

| KEGG source                | UnifiedConcept mapping                          |
|----------------------------|-------------------------------------------------|
| entry ID                   | `primary_id`                                    |
| `NAME` (first)             | `primary_label`                                 |
| `NAME` (remaining)         | `synonyms`                                      |
| `DESCRIPTION` / `COMMENT`  | `definitions`                                   |
| `ENTRY` type token / ID    | `concept_type` (see database table)             |
| `DBLINKS` block            | `mappings` (via `get_mappings`)                 |
| `link` results             | relationships (via `get_relationships`)         |
| full entry text            | `source_data["KEGG"]`                           |

## Related Adapters

- **Reactome Adapter**: curated human pathway reactions
- **GeneOntology Adapter**: functional annotations
- **UniProt Adapter**: protein–pathway mappings
- **ChEMBL / DrugBank Adapters**: detailed drug chemistry

## References

- [KEGG REST API documentation](https://rest.kegg.jp/info/rest)
- [KEGG website](https://www.kegg.jp/)
