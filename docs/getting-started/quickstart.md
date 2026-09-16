---
description: Search two sources, resolve an identifier, map it to other vocabularies and save the results, all in one script.
---

# Quickstart

This page walks through one short script that uses the most common parts of the library. It needs only the core install and no API keys.

{% hint style="info" %}
Every lookup method is a coroutine. In a script, wrap your code in an `async def` and start it with `asyncio.run(...)`. In Jupyter or IPython you can `await` directly in a cell instead.
{% endhint %}

## The complete script

{% code title="quickstart.py" %}
```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig


async def main() -> None:
    # Only initialise the adapters this script needs.
    config = LookupConfig(
        enabled_sources=[KnowledgeSource.MONDO, KnowledgeSource.HPO, KnowledgeSource.OXO],
    )
    lookup = CentralKnowledgeLookup(config)
    try:
        # 1. Search two sources in parallel.
        result = await lookup.search_concepts(
            "type 2 diabetes",
            sources=[KnowledgeSource.MONDO, KnowledgeSource.HPO],
            max_results=10,
        )
        print(f"{result.total_found} concepts in {result.execution_time:.1f}s")
        for concept in result.concepts[:5]:
            print(f"  {concept.primary_id:<15} {concept.primary_label} {concept.sources}")

        # 2. Resolve one identifier in a specific source.
        seizure = await lookup.get_concept_details("HP:0001250", source=KnowledgeSource.HPO)
        if seizure is not None:
            print(seizure.primary_label, "-", seizure.definitions[0])

        # 3. Map the identifier to other vocabularies (xrefs plus EBI OxO).
        mappings = await lookup.find_mappings("HP:0001250")
        print([f"{m.source}:{m.identifier}" for m in mappings[:5]])

        # 4. Save the search results.
        lookup.export_to_json(result, "results/diabetes.json")
        lookup.export_to_csv(result, "results/diabetes.csv")
    finally:
        await lookup.close()


asyncio.run(main())
```
{% endcode %}

Run it with `python quickstart.py`. Live APIs change, so your exact output will differ.

## What each step does

### 1. Configure and create the lookup

`CentralKnowledgeLookup` initialises one adapter per enabled source. Without `enabled_sources` it tries all 36 adapters, which takes a few seconds and means `search_concepts()` without `sources=` queries every one of them. Limiting `enabled_sources` keeps scripts fast.

Always call `await lookup.close()` when you are done (a `try`/`finally` block is the easiest way). It closes the HTTP sessions of all adapters.

### 2. Search

`search_concepts()` queries the given sources concurrently and returns a `LookupResult`:

* `result.concepts`: a list of `UnifiedConcept`, merged by label and sorted by confidence
* `result.total_found`, `result.execution_time`
* `result.sources_succeeded`, `result.sources_failed` and `result.errors` (source name to error message)

A failing source never raises. Check `result.errors` to see what went wrong.

### 3. Resolve an identifier

`get_concept_details(concept_id, source=...)` returns a single `UnifiedConcept` with definitions, synonyms and cross-references, or `None` if the source doesn't know the identifier. Pass `source=` whenever you know which source owns the identifier; without it every enabled adapter is asked.

### 4. Map to other vocabularies

`find_mappings()` combines the cross-references already attached to the concept with live mappings from EBI OxO (when the OxO adapter is enabled). Each mapping is a `ConceptIdentifier` with `source`, `identifier`, `label` and `url`.

### 5. Export

`export_to_json()` and `export_to_csv()` create parent directories as needed and return the file path. See [Exporting results](../guides/exporting-results.md) for Turtle, pandas, Excel, reports and RDF graphs.

## Notebook version

In Jupyter the same calls work with top-level `await`:

```python
# Jupyter / IPython only: top-level await is not valid in a .py script
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig

lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.HPO]))
result = await lookup.search_concepts("seizure", max_results=5)
print(lookup.format_results_table(result))
await lookup.close()
```

## Next steps

* [Configuration](configuration.md): API keys, timeouts, rate limits and source selection
* [Searching concepts](../guides/searching-concepts.md): filters, ranking, hierarchy and source health
* [Knowledge source adapters](../adapters/README.md): what each source offers
* [Example notebooks](../examples/notebooks/README.md)
