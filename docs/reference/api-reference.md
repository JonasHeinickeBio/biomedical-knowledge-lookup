---
description: Classes, functions and models exported by knowledge_lookup, with signatures, defaults and return types.
---

# API reference

This page lists the public API with signatures taken from the source. For task-oriented explanations follow the links to the guides. Methods marked *async* must be awaited.

## Package exports

`from knowledge_lookup import ...` provides:

| Group | Names |
| --- | --- |
| Lookup | `CentralKnowledgeLookup`, `create_knowledge_lookup`, `MultiSourceAnnotator` |
| Annotation results | `AnnotationConfidence`, `SourceAnnotation`, `ConceptAgreement`, `MultiSourceAnnotationResult` |
| Models | `KnowledgeSource`, `ConceptType`, `ConceptIdentifier`, `ConceptMapping`, `UnifiedConcept`, `LookupResult`, `LookupConfig` |
| Cache | `KnowledgeLookupCache`, `get_cache`, `init_cache` |
| Adapters | `ADAPTER_CLASSES` and 26 adapter classes (`OLSAdapter`, `MondoAdapter`, `HPOAdapter`, `UMLSAdapter`, ...) |

All 36 adapter classes are importable from `knowledge_lookup.adapters`.

## `CentralKnowledgeLookup`

```python
CentralKnowledgeLookup(config: LookupConfig | None = None, auto_initialize: bool = True)
```

Creates one adapter per enabled source (see [Configuration](../getting-started/configuration.md)). With `auto_initialize=False` no adapters are created. The constructor also creates the global cache with `init_cache()` defaults if none exists; a cache configured beforehand is kept. See [Caching](../guides/caching.md).

Attributes: `config`, `adapters` (`dict[KnowledgeSource, KnowledgeSourceAdapter]`), `health_tracker` (`SourceHealthTracker`).

### Query methods

| Method | Returns | Guide |
| --- | --- | --- |
| *async* `search_concepts(query, concept_types=None, sources=None, max_results=50, parallel=True)` | `LookupResult` | [Searching concepts](../guides/searching-concepts.md) |
| *async* `search_concepts_expanded(query, concept_types=None, sources=None, max_results=50, max_rounds=3, max_terms_per_round=10, abbreviation_sources=None, persist=True)` | `LookupResult` | [Term expansion](../guides/term-expansion.md) |
| *async* `get_concept_details(concept_id, source=None, timeout=None)` | `UnifiedConcept \| None` | [Searching concepts](../guides/searching-concepts.md) |
| *async* `find_mappings(concept_id, target_sources=None)` | `list[ConceptIdentifier]` | [Searching concepts](../guides/searching-concepts.md) |
| *async* `get_concept_hierarchy(concept_id, levels=1, direction="both")` | `dict[str, list[UnifiedConcept]]` with `parents`, `children`, `siblings` | [Searching concepts](../guides/searching-concepts.md) |
| *async* `suggest_similar_concepts(concept_id, similarity_threshold=0.8)` | `list[UnifiedConcept]` (at most 10) | [Searching concepts](../guides/searching-concepts.md) |

### Source management

| Method | Returns | Notes |
| --- | --- | --- |
| `get_available_sources()` | `list[KnowledgeSource]` | Initialised adapters |
| *async* `add_source(source)` | `None` | `ValueError` if no adapter exists, `RuntimeError` if it can't be initialised |
| `remove_source(source)` | `None` | |
| *async* `get_statistics()` | `dict` | Adapter counts, key config values and source health |
| *async* `close()` | `None` | Close all adapters; call when done |

### Output methods

| Method | Returns | Guide |
| --- | --- | --- |
| `format_results_table(result, max_width=120)` | `str` | |
| `format_results_detailed(result)` | `str` | |
| `export_to_json(result, filepath=None)` | `dict` without a path, otherwise the path as `str` | [Exporting results](../guides/exporting-results.md) |
| `export_to_csv(result, filepath)` | `str` | |
| `export_to_ttl(result, filepath, namespace="http://example.org/concepts/")` | `str` | |
| `export_to_dataframe(result)` | `pandas.DataFrame` | |
| `export_to_excel(result, filepath)` | `str` | |
| `export_summary_report(result, filepath)` | `str` | |
| *async* `lookup_and_convert_to_rdf(query, output_path=None, concept_types=None, sources=None, max_results=50, rdf_format="turtle", adapter_hints=None)` | `rdflib.Graph` | [Exporting results](../guides/exporting-results.md) |

### `create_knowledge_lookup`

```python
create_knowledge_lookup(
    api_keys: dict[str, str] | None = None,
    enabled_sources: list[KnowledgeSource] | None = None,
    fast_mode: bool = True,
    **kwargs,
) -> CentralKnowledgeLookup
```

Builds a `LookupConfig(api_keys=..., enabled_sources=..., **kwargs)`, with all sources enabled by default, and returns a lookup. `fast_mode` has no effect.

## `MultiSourceAnnotator`

```python
MultiSourceAnnotator(config: LookupConfig | None = None)
```

| Method | Returns |
| --- | --- |
| *async* `annotate_text(text, sources=None, enable_cross_reference=True, majority_vote_threshold=0.6)` | `MultiSourceAnnotationResult` |
| *async* `annotate_sentence(sentence, sources=None, enable_cross_reference=True, majority_vote_threshold=0.6)` | `MultiSourceAnnotationResult` |
| *async* `annotate_multiple_sentences(sentences, sources=None, enable_cross_reference=True, majority_vote_threshold=0.6, batch_delay=0.5)` | `list[MultiSourceAnnotationResult]` |
| `get_consensus_annotations(result)` | `list[ConceptAgreement]` |
| *async* `close()` | `None` |

Attributes: `central_lookup`, `annotation_sources` (default sources), `similarity_threshold` (`0.8`). The result dataclasses and `AnnotationConfidence` (`HIGH`, `MEDIUM`, `LOW`, `DISPUTED`) are described in [Multi-source annotation](../guides/multi-source-annotation.md).

## Term expansion

Module `knowledge_lookup.core.term_expansion`:

| Name | Description |
| --- | --- |
| *async* `expand_and_search(lookup, query, *, concept_types=None, sources=None, max_results=50, max_rounds=3, max_terms_per_round=10, abbreviation_sources=None, store=None, persist=True)` | Returns `tuple[LookupResult, ExpansionTrace]` |
| `ExpansionTrace` | Dataclass: `run_id`, `rounds_run`, `stop_reason`, `terms_by_round`, property `all_terms_tried` |
| `AbbreviationSource` | Protocol with *async* `expand(term) -> list[tuple[str, str]]` |
| `UMLSAbbreviationSource(config=None)` | Default abbreviation source; *async* `expand(term)`, *async* `close()` |
| `merge_concept_results(target, new_concepts)` | Merge concept lists in place by normalized label |

Module `knowledge_lookup.core.expansion_store`:

| Name | Description |
| --- | --- |
| `ExpansionStore(db_path=None)` | SQLite store; default `~/.cache/knowledge-lookup/expansion_history.db` |
| `start_run(original_query) -> int`, `record_terms(run_id, round_num, terms)`, `finish_run(run_id, rounds_run, stop_reason)` | Write a run |
| `get_run(run_id)`, `get_terms(run_id)`, `find_runs_for_query(original_query, limit=20)` | Read runs as `dict`s |
| `ORIGIN_ORIGINAL`, `ORIGIN_SYNONYM`, `ORIGIN_ABBREVIATION`, `ORIGIN_LONG_FORM` | `"original"`, `"synonym"`, `"abbreviation"`, `"long_form"` |
| `STOP_FIXED_POINT`, `STOP_MAX_ROUNDS` | `"fixed_point"`, `"max_rounds"` |

See [Term expansion](../guides/term-expansion.md).

## Models

The models are pydantic v2 classes generated from the LinkML schema, wrapped for convenience. They forbid unknown fields and store enum fields as their string values.

### `KnowledgeSource`

A `str` enum with 40 members. The 36 with an adapter:

`BIOLINKER`, `BIOONTOLOGY`, `BIOPORTAL`, `CHEMBL`, `CLINVAR`, `COSMIC`, `DBPEDIA`, `DISGENET`, `DRUGBANK`, `EBIOLS`, `ENSEMBL`, `EUROPEPMC`, `EUTILS`, `GENEONTOLOGY`, `HGNC`, `HPO`, `INTERPRO`, `KEGG`, `MONDO`, `OBOFOUNDRY`, `OLS`, `OMIM`, `OPENTARGETS`, `OXO`, `PDB`, `PFAM`, `PUBCHEM`, `QUICKGO`, `REACTOME`, `STRING`, `TYTO`, `UMLS`, `UNICHEM`, `UNIPROT`, `WIKIDATA`, `ZOOMA`

Members without an adapter: `GO`, `NCBI`, `MYGENEINFO`, `DBVAR`. Per-source details are in [Knowledge source adapters](../adapters/README.md).

### `ConceptType`

A `str` enum:

* **Clinical:** `DISEASE`, `SYMPTOM`, `PHENOTYPE`, `TREATMENT`, `DEMOGRAPHIC`, `CASE_DEFINITION`, `PROGNOSIS`, `PROCEDURE`, `OBSERVATION`
* **Molecular:** `MOLECULAR_ENTITY`, `GENE`, `PROTEIN`, `CYTOKINE`, `METABOLITE`, `BIOMARKER`, `GENE_DISEASE_ASSOCIATION`, `CHEMICAL`, `DRUG`
* **Anatomy:** `ANATOMICAL_ENTITY`, `ANATOMY`, `ORGAN_SYSTEM`, `ORGAN`, `TISSUE`, `CELL_TYPE`, `CELLULAR_COMPONENT`
* **Processes:** `BIOLOGICAL_PROCESS`, `PHYSIOLOGICAL_PROCESS`, `PATHOPHYSIOLOGICAL_PROCESS`, `MOLECULAR_FUNCTION`, `PATHWAY`
* **Evidence and studies:** `ASSAY`, `EVIDENCE`, `REFERENCE`, `CITATION`, `STUDY`, `CLINICAL_STUDY`, `LABORATORY_STUDY`, `OBSERVATIONAL_STUDY`, `COHORT_STUDY`, `CASE_STUDY`, `CASE_CONTROL_STUDY`, `RANDOMIZED_CONTROLLED_TRIAL`, `CLINICAL_TRIAL`, `META_ANALYSIS`, `SYSTEMATIC_REVIEW`, `INTERVENTIONAL_STUDY`, `DIAGNOSTIC_TRIAL`, `COMMUNITY_TRIAL`, `RETROSPECTIVE_COHORT_STUDY`, `PROSPECTIVE_COHORT_STUDY`
* **Other:** `PERSON`, `ORGANISM`, `UNKNOWN`

### `UnifiedConcept`

| Field | Type | Default |
| --- | --- | --- |
| `primary_id` | `str` | required |
| `primary_label` | `str` | required (the constructor also accepts `label=`) |
| `concept_type` | `ConceptType` | `None` |
| `confidence_score` | `float` | `0.0` |
| `sources` | `list[KnowledgeSource]` | `[]` (the constructor also accepts `source=`) |
| `identifiers` | `list[ConceptIdentifier]` | `[]` |
| `mappings` | `list[ConceptMapping]` | `[]` |
| `synonyms`, `definitions`, `semantic_types`, `categories` | `list[str]` | `[]` |
| `parents`, `children`, `related` | `list[str]` | `[]` |
| `source_data` | `dict` | `{}` |
| `labels` | `dict` | `{}` |
| `last_updated` | `datetime` | `None` |

Methods:

* `add_identifier(source, identifier, label=None, url=None)`
* `add_mapping(target_source, target_id, target_label=None, mapping_type="exact", confidence=1.0, mapping_source=None)`
* `get_identifier(source) -> ConceptIdentifier | None`
* `has_source(source) -> bool`
* `merge_with(other) -> UnifiedConcept`

### `ConceptIdentifier`

| Field | Type |
| --- | --- |
| `source` | `KnowledgeSource` |
| `identifier` | `str` |
| `label` | `str \| None` |
| `url` | `str \| None` |

`str(identifier)` returns `"<source lower-case>:<identifier>"`. `to_curies_reference()` and the classmethod `from_curies_reference(reference)` convert to and from `curies.Reference`.

### `ConceptMapping`

`from_concept: ConceptIdentifier`, `to_concept: ConceptIdentifier`, `mapping_type: str = "exact"`, `confidence: float = 1.0`, `source: str | None = None`.

### `LookupResult`

| Field | Type | Default |
| --- | --- | --- |
| `query` | `str` | required |
| `concepts` | `list[UnifiedConcept]` | `[]` |
| `total_found` | `int` | `0` |
| `execution_time` | `float` | `0.0` |
| `sources_queried`, `sources_succeeded`, `sources_failed` | `list[KnowledgeSource]` | `[]` |
| `errors` | `dict[str, str]` | `{}` |
| `source_health` | `dict[KnowledgeSource, SourceHealth]` | `{}` |

Methods: `add_concepts(concepts, source)`, `add_error(source, message)`, `get_best_matches(n=5)`, `group_by_source()`. `model_dump()` and `model_dump_json()` include `errors` and `source_health`, so `LookupResult.model_validate(result.model_dump())` round-trips.

### `LookupConfig`

Fields and defaults are documented in [Configuration](../getting-started/configuration.md). Methods: `get_api_key(service) -> str | None`, `is_source_enabled(source) -> bool`, classmethod `with_all_sources()`.

### `SourceHealth`

Module `knowledge_lookup.models.biomedical_knowledge_models`. Fields: `source`, `circuit_state` (`CLOSED`, `OPEN`, `HALF_OPEN`), `failure_count`, `threshold`, `cooldown`, `total_calls`, `total_failures`, `total_successes`, `health_score`, `last_error`, `is_open`. The health tracker does not fill `last_error`. `is_open` is `True` while the breaker rejects requests; once the cooldown has elapsed the snapshot reports `HALF_OPEN`.

## Cache

Module `knowledge_lookup.cache` (the main names are also exported from `knowledge_lookup`):

| Name | Signature |
| --- | --- |
| `KnowledgeLookupCache` | `(memory_max_size=1000, disk_cache_dir=None, disk_max_size=10000, default_ttl=None, cleanup_interval=300)` with `get(key, namespace="")`, `set(key, value, ttl=None, namespace="")`, `delete(key, namespace="")`, `clear(namespace="")`, `cleanup()`, `get_stats()` |
| `init_cache` | `(memory_max_size=1000, disk_cache_dir=None, disk_max_size=10000, default_ttl=3600, cleanup_interval=300) -> KnowledgeLookupCache`; replaces the global cache |
| `get_cache` | `() -> KnowledgeLookupCache` |
| `ensure_cache` | `() -> KnowledgeLookupCache`; creates the global cache with `init_cache()` defaults only if none exists (module `knowledge_lookup.cache`) |
| `MemoryCacheBackend`, `DiskCacheBackend`, `CacheBackend`, `CacheEntry`, `CacheStats` | Building blocks |

See [Caching](../guides/caching.md).

## CURIE utilities

Module `knowledge_lookup.curie_utils`: `parse_curie_or_uri`, `validate_prefix`, `validate_curie_pattern`, `normalize_curie`, `normalize_identifier`, `get_prefix_mapping`, `get_converter`, `get_bioregistry_converter`, `create_local_converter`, `get_source_prefix_mapping`, `concept_identifier_to_reference`, `reference_to_concept_identifier`. See [CURIE management](../guides/curie-management.md).

## RDF services

Module `knowledge_lookup.services`:

| Name | Description |
| --- | --- |
| `UnifiedRDFConverter(adapter_hints=None, use_dynamic_loading=False)` | `convert_concepts_to_graph(concepts) -> Graph`, `save_graph(graph, output_path, format="turtle")`, `convert_and_save(concepts, output_path, format="turtle")`, `merge_with_existing_graph(new_graph, existing_graph_path, ...)`, `add_concept_type_handler(concept_type, handler)`, `get_supported_concept_types()`, classmethod `from_ontology(ontology_dir=None, adapter_hints=None)` |
| `RDFNamespaces` | Namespace constants used by the converter |
| `OntologyConceptLoader` | Loads concept types from ontology files for dynamic handlers |

`knowledge_lookup.export` has module-level `export_to_json(result, filepath=None)` and `export_to_csv(result, filepath=None)`.

## Adapters

### `KnowledgeSourceAdapter`

Module `knowledge_lookup.base`. Abstract base class for all adapters; constructed with a `LookupConfig`.

| Member | Description |
| --- | --- |
| `get_source() -> KnowledgeSource` | Abstract |
| *async* `search_concepts(query, limit=20) -> list[UnifiedConcept]` | Abstract |
| *async* `get_concept_details(concept_id) -> UnifiedConcept \| None` | Abstract |
| *async* `get_mappings(concept_id)`, *async* `get_relationships(concept_id)` | Optional; default `[]` |
| `is_available() -> bool` | Default `True`; adapters return `False` when a key or client is missing |
| `get_rate_limit() -> float` | `config.rate_limits[source]`, default `1.0` |
| *async* `close()` | Close the HTTP session; adapters are also async context managers |
| `set_circuit_breaker(cb)` | Injected by the lookup when health tracking is on |

Protected helpers for implementers: `_make_request(url, params=None, headers=None, json_data=None)`, `_make_request_text(...)`, `_call_with_retry(operation_name, operation, strategies=None)`, `_thread_with_retry(operation_name, func, *args)`, `_notify_circuit_breaker(error=None)`, `_create_concept(concept_id, label, concept_type=ConceptType.UNKNOWN)`, `_determine_concept_type(semantic_types, categories=None)` and the cache helpers described in [Caching](../guides/caching.md).

### `ADAPTER_CLASSES`

`dict[KnowledgeSource, type[KnowledgeSourceAdapter]]` in `knowledge_lookup.adapters`: the registry used by `CentralKnowledgeLookup`. ChEMBL and UMLS are present only when their extras are installed.

## Errors

There is no custom exception hierarchy and no `knowledge_lookup.exceptions` module.

* Failing sources don't raise from `search_concepts()`; see `LookupResult.errors`.
* `get_concept_details()` returns `None` on errors and timeouts.
* `add_source()` raises `ValueError` or `RuntimeError`.
* `LookupConfig` and the other models raise `pydantic.ValidationError` for invalid or unknown fields.
* `knowledge_lookup.utils.retry_utils` defines `CircuitBreaker`, `CircuitBreakerOpen` (raised inside adapters when a breaker is open), `ErrorCategory` and `classify_error()`.
* Optional features raise `ImportError` naming the extra to install.

## Agent workflow

Module `knowledge_lookup.agents` (requires the `agents` extra):

| Name | Description |
| --- | --- |
| *async* `run_workflow(query, *, max_results=50, sources=None, concept_types=None, export_formats=None, export_path=None, max_iterations=3, auto_approve_threshold=0.8)` | Run the graph; returns a `dict` |
| *async* `resume_workflow(thread_id, decision)` | Resume after the approval interrupt; returns a `dict` |
| `build_workflow_graph(checkpointer=None)` | Compiled LangGraph `StateGraph` |
| `LookupWorkflowState` | `TypedDict` of the graph state |
| `lookup_result_to_dict(result)`, `dict_to_lookup_result(data)`, `make_step(agent, action, detail="", **extra)` | State helpers |
| `load_llm_config()`, *async* `call_llm(prompt, *, max_tokens=1024, temperature=0.2)` | LLM backend helpers |

See [Agent workflow](../guides/agent-workflow.md).

## MCP server

Module `knowledge_lookup.mcp_server` (requires the `mcp` extra):

| Name | Description |
| --- | --- |
| `create_server(settings=None, lookup_factory=None, log_level="WARNING")` | Build the `MCPServer` |
| `ServerSettings` | Dataclass: `default_sources`, `enabled_sources=None`, `timeout_per_source=15.0`, `persist_expansions=False`; classmethod `from_env(environ=None)` |
| `main(argv=None)` | Entry point of `knowledge-lookup-mcp` |

See [MCP server](../guides/mcp-server.md).

## UMLS helpers

`knowledge_lookup.umls` contains UMLS-specific tools beyond the adapter: `UMLSCache` and `PartialMatcher` (local SQLite concept cache with full-text search), `BatchProcessor` and `BatchResult` (batch concept extraction from CSV, JSON or text files), `LLMNormalizer` (LLM-assisted concept normalization), `ConceptEmbedder` (embedding similarity), and RDF helpers (`concepts_to_turtle`, `concepts_to_jsonld`, `concepts_to_graph`, `concept_to_graph`, `save_concepts_to_file`, `SparqlEndpoint`, `SPARQL_ENDPOINTS`). Refer to their docstrings for details.
