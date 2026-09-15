---
description: Widen a search iteratively with synonyms and abbreviation/long-form variants, and keep a durable record of every term tried.
---

# Term expansion

A single search often misses concepts that a source only knows under a synonym or a long form. Term expansion searches the query, harvests synonyms and abbreviation/long-form variants from what it finds, searches those too, and repeats until no new terms appear or a round limit is reached. Every term it tries is written to a local SQLite store, so you can later check what was searched for a query and why.

Expansion is part of the core package; it does not need the `agents` extra.

## How it works

1. **Round 0** searches the original query.
2. From every concept found so far, the expansion collects:
   * the concept's **synonyms**, and
   * **long forms** and **abbreviations** offered by the abbreviation sources for the concept's label. By default this is UMLS, which reports abbreviation atoms (term types `AB`, `AA`) and full forms (`PT`, `PN`, `FN`) that share a CUI. Each label is asked about once per run. A round asks about at most `max_abbreviation_lookups` new labels (default 10, in result order; the rest wait for a later round), with up to 3 lookups at a time.
3. The next round searches new synonyms and long forms, at most `max_terms_per_round` of them. **Abbreviations are recorded but never searched**: a bare abbreviation such as "PEM" matches unrelated concepts as readily as the intended one and would drag the expansion off-topic.
4. Expansion stops when a round finds no new searchable terms (`fixed_point`) or after `max_rounds` rounds, counting round 0 (`max_rounds`).

Results from all rounds are merged by label, like a normal search.

{% hint style="info" %}
UMLS-based discovery needs the `umls` extra and a `UMLS_API_KEY`. Without them it silently falls back to synonym-only expansion. It issues several UMLS requests for each concept label it asks about (at most `max_abbreviation_lookups` labels per round), so it still adds time to a search. Pass `abbreviation_sources=[]` to skip it.
{% endhint %}

## Expanded search in one call

`CentralKnowledgeLookup.search_concepts_expanded()` has the same arguments as `search_concepts()` plus the expansion controls, and returns the merged `LookupResult`:

```python
result = await lookup.search_concepts_expanded(
    "COPD",
    sources=[KnowledgeSource.UMLS, KnowledgeSource.MONDO],
    max_rounds=3,
    max_terms_per_round=10,
    persist=True,
)
```

| Argument | Default | Meaning |
| --- | --- | --- |
| `query`, `concept_types`, `sources`, `max_results` | | As for `search_concepts()`; applied to every term |
| `max_rounds` | `3` | Maximum rounds including round 0; `1` means no expansion |
| `max_terms_per_round` | `10` | Cap on newly discovered terms searched per round |
| `abbreviation_sources` | `None` | `None` uses UMLS; `[]` disables abbreviation discovery; or pass your own sources |
| `persist` | `True` | Record the run in the default `ExpansionStore` |

## Get the trail as well

`expand_and_search()` in `knowledge_lookup.core.term_expansion` does the same work and also returns an `ExpansionTrace`:

{% code title="expand.py" %}
```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.core.term_expansion import expand_and_search


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.HPO]))
    try:
        result, trace = await expand_and_search(
            lookup,
            "seizure",
            sources=[KnowledgeSource.HPO],
            max_rounds=2,
            max_terms_per_round=5,
            abbreviation_sources=[],  # synonyms only, skips the slower UMLS lookups
            persist=False,
        )
        print(f"{result.total_found} concepts, {trace.rounds_run} rounds, stop: {trace.stop_reason}")
        for round_num, terms in enumerate(trace.terms_by_round):
            print(round_num, terms)
    finally:
        await lookup.close()


asyncio.run(main())
```
{% endcode %}

The output looks like this (live data varies):

```
141 concepts, 2 rounds, stop: max_rounds
0 ['seizure']
1 ['Epileptic seizure', 'Seizures', 'Epilepsy', 'Acute repetitive seizures', 'Crescendo seizures']
```

`expand_and_search(lookup, query, *, concept_types=None, sources=None, max_results=50, max_rounds=3, max_terms_per_round=10, abbreviation_sources=None, max_abbreviation_lookups=10, store=None, persist=True)` returns `(LookupResult, ExpansionTrace)`. Pass `store=` to write to a specific `ExpansionStore`. `max_abbreviation_lookups` caps how many new concept labels the abbreviation sources are asked about per round; `search_concepts_expanded()` uses the default.

| `ExpansionTrace` attribute | Description |
| --- | --- |
| `run_id` | Row id in the store, or `None` when not persisted |
| `rounds_run` | Number of rounds executed |
| `stop_reason` | `"fixed_point"` or `"max_rounds"` |
| `terms_by_round` | Searched terms per round |
| `all_terms_tried` | All searched terms, flattened |

In the merged result, `execution_time` is the sum over all searches, and a term whose search raised shows up in `errors` under the key `expand_<term>`.

## Query the expansion history

`ExpansionStore` is a SQLite database that never evicts entries. Its default location is `~/.cache/knowledge-lookup/expansion_history.db`.

```python
from knowledge_lookup.core.expansion_store import ExpansionStore

store = ExpansionStore()  # or ExpansionStore("path/to/expansions.db")
for run in store.find_runs_for_query("seizure", limit=5):
    print(run["id"], run["started_at"], run["rounds_run"], run["stop_reason"])
    for row in store.get_terms(run["id"]):
        print("   ", row["round"], row["origin"], row["term"], row["origin_concept_id"])
```

| Method | Returns |
| --- | --- |
| `find_runs_for_query(original_query, limit=20)` | Runs for an exact query string, newest first |
| `get_run(run_id)` | `id`, `original_query`, `started_at`, `completed_at`, `rounds_run`, `stop_reason` |
| `get_terms(run_id)` | Rows with `round`, `term`, `origin`, `origin_concept_id`, `discovered_at` |
| `start_run()`, `record_terms()`, `finish_run()` | Used by `expand_and_search()` to write runs |

`origin` is `original`, `synonym`, `long_form` or `abbreviation`; `origin_concept_id` is the concept the term was harvested from. Abbreviations are stored under the round after the one in which they were found.

## Plug in your own abbreviation source

Any object with an async `expand(term)` method can act as an abbreviation source. `expand()` receives the label of each concept found and returns `(candidate, origin)` pairs, where `origin` is `ORIGIN_LONG_FORM` (the candidate gets searched) or `ORIGIN_ABBREVIATION` (recorded only). Return `[]` instead of raising when you have nothing.

{% code title="dictionary_source.py" %}
```python
import asyncio

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.core.expansion_store import (
    ORIGIN_ABBREVIATION,
    ORIGIN_LONG_FORM,
    ExpansionStore,
)
from knowledge_lookup.core.term_expansion import expand_and_search


class DictionaryAbbreviations:
    """Abbreviation/long-form pairs from an in-house dictionary."""

    def __init__(self, pairs: dict[str, str]) -> None:
        self._long_forms = {abbr.lower(): long for abbr, long in pairs.items()}
        self._abbreviations = {long.lower(): abbr for abbr, long in pairs.items()}

    async def expand(self, term: str) -> list[tuple[str, str]]:
        key = term.strip().lower()
        if key in self._long_forms:
            return [(self._long_forms[key], ORIGIN_LONG_FORM)]
        if key in self._abbreviations:
            return [(self._abbreviations[key], ORIGIN_ABBREVIATION)]
        return []


async def main() -> None:
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.HPO]))
    store = ExpansionStore("expansions.db")
    try:
        _, trace = await expand_and_search(
            lookup,
            "seizure",
            sources=[KnowledgeSource.HPO],
            max_rounds=1,
            abbreviation_sources=[DictionaryAbbreviations({"SZ": "Seizure"})],
            store=store,
        )
        for row in store.get_terms(trace.run_id):
            print(row["round"], row["origin"], row["term"])
    finally:
        await lookup.close()


asyncio.run(main())
```
{% endcode %}

The built-in UMLS source is `UMLSAbbreviationSource(config=None)`; combine it with your own by passing both in the list.

## Where expansion is used

* The [agent workflow](agent-workflow.md) runs an expansion pass (2 rounds, up to 8 terms per round) before its main lookup and persists it to the default store.
* The [MCP server](mcp-server.md) tool `biomed_search_concepts` expands when called with `expand_synonyms=true`. It records runs only when started with `--persist-expansions`.

## Next steps

* [Searching concepts](searching-concepts.md)
* [Configuration](../getting-started/configuration.md): UMLS API key
