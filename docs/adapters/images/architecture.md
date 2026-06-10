# OpenTargets Adapter Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTargetsAdapter                       │
│          (src/knowledge_lookup/adapters/)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ search_concepts│  │get_concept_details│  │is_available  │ │
│  └────────┬───────┘  └────────┬─────────┘  └──────────────┘ │
│           │                   │                               │
│           ▼                   ▼                               ▼
│    ┌──────────────┐    ┌──────────────┐              ┌────────┐ │
│    │ GraphQL      │    │ GraphQL      │              │ HTTP   │ │
│    │ Query        │    │ Query        │              │ GET    │ │
│    │ Construction │    │ Construction │              │ /health│ │
│    └───────┬──────┘    └───────┬──────┘              └────────┘ │
│            │                   │                               │
│            ▼                   ▼                               ▼
│    ┌──────────────┐    ┌──────────────┐              ┌────────┐ │
│    │ HTTP Request │    │ HTTP Request │              │ Status │ │
│    │ (POST)       │    │ (POST)       │              │ Check  │ │
│    └───────┬──────┘    └───────┬──────┘              └────────┘ │
│            │                   │                               │
│            ▼                   ▼                               ▼
│    ┌──────────────┐    ┌──────────────┐              ┌────────┐ │
│    │ Open Targets │    │ Open Targets │              │ API    │ │
│    │ GraphQL API  │    │ GraphQL API  │              │ URL:   │ │
│    │              │    │              │              │ https://│ │
│    └──────────────┘    └──────────────┘              │api.opent │ │
│                                                      │argets.or │ │
│                                                      │g/api/v4/ │ │
│                                                      │graphql   │ │
└────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │Data         │
                    │Conversion   │
                    │to           │
                    │UnifiedConcep│
                    │t           │
                    └──────────────┘
```

## Data Flow

1. **Input**: Query string or concept ID
2. **GraphQL Construction**: Build appropriate query based on method
3. **API Request**: POST to Open Targets GraphQL endpoint
4. **Response Parsing**: Extract data from GraphQL response
5. **Conversion**: Map to `UnifiedConcept` structure
6. **Output**: Return concepts with standardized format

## Entity Type Detection

### Target Detection (Ensembl Gene IDs)
- **Pattern**: `ENSG*` (e.g., ENSG00000141510)
- **Query**: Target-specific GraphQL query
- **Fields**: id, approvedSymbol, biotype

### Disease Detection (Ontology IDs)
- **Patterns**: 
  - `EFO_*` (EBI Functional Ontology)
  - `MONDO_*` (Mondo Disease Ontology)
  - `ORPHA*` (Orphanet)
- **Query**: Disease-specific GraphQL query
- **Fields**: id, name, definition

## GraphQL Queries

### Search Query
```graphql
query Search($queryString: String!) {
  search(queryString: $queryString, entityNames: ["target", "disease"]) {
    hits {
      id
      name
      entity
      description
    }
  }
}
```

### Target Details Query
```graphql
query Details($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    biotype
  }
}
```

### Disease Details Query
```graphql
query Details($id: String!) {
  disease(id: $id) {
    id
    name
    definition
  }
}
```

## Rate Limiting

```
┌─────────────────────────────────────────────────────────────┐
│                    Request Flow                             │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Client  │→ │Rate Limiter  │→ │  Adapter     │          │
│  └──────────┘  └──────────────┘  └──────┬───────┘          │
│                                          │                  │
│                                          ▼                  │
│                                   ┌──────────────┐          │
│                                   │  Open Targets│          │
│                                   │  GraphQL API │          │
│                                   └──────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Integration with CentralKnowledgeLookup

```
┌─────────────────────────────────────────────────────────────┐
│              CentralKnowledgeLookup                         │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │OpenTargets │  │  MONDO     │  │  DisGeNET  │            │
│  │  Adapter   │  │  Adapter   │  │  Adapter   │            │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘            │
└─────────┼───────────────┼──────────────┼────────────────────┘
          │               │              │
          ▼               ▼              ▼
    ┌───────────────────────────────────────┐
    │     UnifiedConcept Merging            │
    │  - Deduplication                      │
    │  - Confidence Scoring                 │
    │  - Cross-referencing                  │
    └───────────────────────────────────────┘
```
