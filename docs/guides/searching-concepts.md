---
description: Search across sources, read LookupResult and UnifiedConcept, resolve identifiers, map them to other vocabularies and monitor source health.
---

# Searching concepts

This guide covers the query methods of `CentralKnowledgeLookup`. Complete scripts end with `asyncio.run(...)`; shorter snippets run inside an `async` function that already has a `lookup` object, as in the [Quickstart](../getting-started/quickstart.md).

## Search across sources

{% code title="search.py" %}
```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, ConceptType, KnowledgeSource, LookupConfig


async def main() -> None:
    lookup = CentralKnowledgeLookup(
        LookupConfig(enabled_sources=[KnowledgeSource.HPO, KnowledgeSource.MONDO])
    )
    try:
        result = await lookup.search_concepts(
            "seizure",
            sources=[KnowledgeSource.HPO, KnowledgeSource.MONDO],
            concept_types=[ConceptType.PHENOTYPE],
            max_results=20,
        )
        print(f"{result.total_found} concepts from {list(result.sources_succeeded)}")
        for source, message in result.errors.items():
            print(f"{source} failed: {message}")
        for concept in result.get_best_matches(5):
            print(f"{concept.primary_id:<12} {concept.primary_label} ({concept.concept_type})")
    finally:
        await lookup.close()


asyncio.run(main())
```
{% endcode %}

`search_concepts(query, concept_types=None, sources=None, max_results=50, parallel=True)` returns a `LookupResult`.

| Argument | Meaning |
| --- | --- |
| `query` | Free text: a name, symbol or phrase. It is sent to every source as-is; CURIEs are not parsed. Use `get_concept_details()` for identifiers. |
| `sources` | Sources to query. `None` queries every initialised adapter. Sources that are not initialised are ignored. |
| `concept_types` | Keep only concepts of these `ConceptType`s. Concepts a source leaves as `UNKNOWN` are always kept. |
| `max_results` | Upper bound on the merged result. Each source is asked for `max_results // len(sources)` concepts (at least 1). |
| `parallel` | `True` (default) queries sources concurrently; `False` queries them one after another. Either way each source is bounded by `timeout_per_source`. |

{% hint style="info" %}
Name `sources` whenever you can. Searching all 36 adapters is slow and noisy. Good starting points: HPO for phenotypes, MONDO for diseases, HGNC, UniProt or Ensembl for genes and proteins, PubChem or ChEMBL for chemicals, Reactome for pathways, UMLS or BioPortal for clinical terminologies. The [adapter pages](../adapters/README.md) describe each source.
{% endhint %}

## Read the result

### `LookupResult`

| Attribute | Description |
| --- | --- |
| `query` | The search string |
| `concepts` | `list[UnifiedConcept]`, merged and sorted by `confidence_score` |
| `total_found` | Number of concepts after filtering and de-duplication |
| `execution_time` | Seconds taken by the whole search |
| `sources_queried` | Sources that were asked |
| `sources_succeeded`, `sources_failed` | Names of the sources that answered or failed |
| `errors` | `dict` of source name to error message |
| `source_health` | `dict` of `KnowledgeSource` to `SourceHealth`; filled only when health tracking is enabled |

Methods: `get_best_matches(n=5)` returns the `n` highest-scoring concepts; `group_by_source()` returns a `dict` from source to the concepts it contributed.

### `UnifiedConcept`

| Field | Description |
| --- | --- |
| `primary_id` | Identifier in the source's own format, for example `HP:0001250`, `MONDO_0005148` or `C0011849` |
| `primary_label` | Preferred label |
| `concept_type` | A `ConceptType` value such as `DISEASE`, `PHENOTYPE`, `GENE`, or `UNKNOWN` |
| `confidence_score` | Score between 0 and 1 reported by the source; scores are not comparable across sources |
| `sources` | Sources that contributed the concept |
| `synonyms`, `definitions` | Lists of strings |
| `semantic_types`, `categories` | Source classifications, for example UMLS semantic types |
| `identifiers` | `list[ConceptIdentifier]` with `source`, `identifier`, `label` and `url` |
| `mappings` | `list[ConceptMapping]` |
| `parents`, `children`, `related` | Identifiers of related concepts, when the source provides them |
| `source_data` | Raw per-source payload as a `dict` |

Methods: `get_identifier(source)`, `has_source(source)`, `add_identifier(...)`, `add_mapping(...)` and `merge_with(other)`.

{% hint style="info" %}
Enum fields hold plain string values: `concept.sources` is `["HPO"]` and `concept.concept_type` is `"PHENOTYPE"`. `KnowledgeSource` and `ConceptType` are `str` enums, so `KnowledgeSource.HPO in concept.sources` and `concept.concept_type == ConceptType.PHENOTYPE` both work.
{% endhint %}

### De-duplication and ranking

With `enable_deduplication=True` (the default), concepts whose labels match after lower-casing and trimming whitespace are merged:

* the first concept's `primary_id` is kept,
* the label of the higher-scoring concept wins and `confidence_score` becomes the maximum of the two,
* list fields (sources, synonyms, definitions, identifiers, parents, ...) are combined without duplicates.

The merged list is sorted by `confidence_score` and cut to `max_results`. Labels that differ in any other way ("Seizure" and "Seizures") stay separate; [multi-source annotation](multi-source-annotation.md) groups concepts with fuzzy label matching instead.

### When a source fails

`search_concepts()` never raises because one source failed. Exceptions, timeouts and sources skipped because their circuit breaker is open are recorded in `result.errors` and `result.sources_failed`, and the other sources' results are returned. The library has no custom exception hierarchy; see the [API reference](../reference/api-reference.md) for the few errors that are raised.

## Resolve an identifier

```python
concept = await lookup.get_concept_details("HP:0001250", source=KnowledgeSource.HPO)
if concept is None:
    print("not found")
else:
    print(concept.primary_label, concept.definitions[:1], concept.synonyms[:3])
```

`get_concept_details(concept_id, source=None, timeout=None)` returns a `UnifiedConcept` or `None`.

* With `source`, only that adapter is asked.
* Without `source`, every initialised adapter is asked in parallel. The call waits for all of them (each up to the timeout) and returns the first non-`None` answer in adapter registration order.
* Errors and timeouts return `None` rather than raising.
* With source health tracking on, a source whose circuit breaker is open is not called (asked with `source`, the call returns `None`), and a call cut off by the timeout counts as a failure on that source's breaker, as for searches.

Adapters expect identifiers in different forms: HPO and MONDO take CURIEs (`HP:0001250`), UniProt takes bare accessions (`P38398`), UMLS takes CUIs (`C0011849`). Check the [adapter pages](../adapters/README.md). The [MCP server](mcp-server.md) routes identifiers to the right adapter automatically.

## Map to other vocabularies

```python
mappings = await lookup.find_mappings("HP:0001250")
for mapping in mappings[:5]:
    print(mapping.source, mapping.identifier, mapping.label)

mondo_only = await lookup.find_mappings("HP:0001250", target_sources=[KnowledgeSource.MONDO])
```

`find_mappings(concept_id, target_sources=None)` returns a de-duplicated `list[ConceptIdentifier]` built from:

1. the identifiers already attached to the concept (resolved with `get_concept_details()` without a source), and
2. live cross-references from [EBI OxO](https://www.ebi.ac.uk/spot/oxo/) at distance 2, when `KnowledgeSource.OXO` is enabled.

OxO mappings are attributed to the adapter that owns their prefix (`MONDO:` to MONDO, `HP:` to HPO, `DOID:` to OLS, `UMLS:` to UMLS, and so on). Prefixes without an adapter, such as MeSH, NCIT, SNOMED CT, ICD or OMOP, keep `OXO` as their source, and the identifier is the full CURIE, for example `MESH:D004827`. `target_sources` keeps only mappings whose source is in the list.

## Explore the hierarchy

```python
hierarchy = await lookup.get_concept_hierarchy("C0011849", direction="up")
print([parent.primary_label for parent in hierarchy["parents"]])
```

`get_concept_hierarchy(concept_id, levels=1, direction="both")` returns `{"parents": [...], "children": [...], "siblings": [...]}`. It resolves the concept, then resolves up to 10 of the IDs in its `parents` (`direction` `"up"` or `"both"`) and `children` (`"down"` or `"both"`).

{% hint style="warning" %}
Only immediate relatives are returned (`levels` currently has no effect) and `siblings` is always empty. The method relies on adapters that fill `parents` and `children`; among the built-in adapters that is BioPortal and UMLS. For HPO, MONDO or OLS identifiers the lists come back empty.
{% endhint %}

## Find similar concepts

```python
similar = await lookup.suggest_similar_concepts("HP:0001250", similarity_threshold=0.8)
for concept in similar:
    print(concept.primary_id, concept.primary_label, concept.confidence_score)
```

`suggest_similar_concepts(concept_id, similarity_threshold=0.8)` resolves the concept, searches for its label and first three synonyms (restricted to the same concept type) across all initialised sources, and returns up to 10 other concepts whose `confidence_score` is at least `similarity_threshold`. The threshold applies to the source's search score, not to a semantic similarity measure.

## Manage sources at runtime

| Method | Description |
| --- | --- |
| `get_available_sources()` | `list[KnowledgeSource]` of initialised adapters |
| `await add_source(source)` | Initialise one more adapter. Raises `ValueError` for a source without an adapter and `RuntimeError` if it isn't available (for example a missing API key). |
| `remove_source(source)` | Drop an adapter from this lookup |

## Monitor source health

```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig


async def main() -> None:
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.HPO, KnowledgeSource.MONDO],
        enable_source_health_tracking=True,
        circuit_breaker_threshold=3,
        circuit_breaker_cooldown=60,
    )
    lookup = CentralKnowledgeLookup(config)
    try:
        result = await lookup.search_concepts("seizure", max_results=10)
        for source, health in result.source_health.items():
            print(
                source.value,
                health.circuit_state,
                f"health={health.health_score:.2f}",
                f"calls={health.total_calls}",
            )
        print("open breakers:", lookup.health_tracker.open_sources())
    finally:
        await lookup.close()


asyncio.run(main())
```

Each `SourceHealth` snapshot has `circuit_state` (`CLOSED`, `OPEN` or `HALF_OPEN`), `is_open`, `failure_count`, `threshold`, `cooldown`, `total_calls`, `total_failures`, `total_successes` and `health_score`. `lookup.health_tracker` also offers `get_health(source)`, `all_health()` and `open_sources()` (the sources whose breaker is open).

While a breaker is open (`is_open` is `True`), `search_concepts()` skips the source without calling it and reports it in `result.errors`, and `get_concept_details()` skips it as well. Once `circuit_breaker_cooldown` has elapsed the snapshot shows `HALF_OPEN` and the next request is sent as a probe. Searches and detail lookups cut off by `timeout_per_source` count as failures; HTTP 404 answers do not. See [Configuration](../getting-started/configuration.md) for thresholds, retries and timeouts.

## Print results in the console

`lookup.format_results_table(result, max_width=120)` renders a fixed-width table of the top 20 concepts; `lookup.format_results_detailed(result)` prints definitions, synonyms and semantic types for the top 10.

## Next steps

* [Term expansion](term-expansion.md): search synonyms and long forms automatically
* [Exporting results](exporting-results.md)
* [CURIE management](curie-management.md): normalise the identifiers you get back
