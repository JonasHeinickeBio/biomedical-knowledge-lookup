---
description: What the built-in memory and disk cache does, which components use it, and how to cache lookups in your own code.
---

# Caching

`knowledge_lookup.cache` provides a two-tier cache with a time-to-live (TTL): an in-memory store with least-recently-used eviction, and an optional on-disk store that survives restarts. This page explains what is cached today and how to use the cache for your own lookups.

## What is cached today

| Component | Cache |
| --- | --- |
| UniChem adapter | Global cache, namespace `unichem`: source lists and source info for 24 hours, lookups for 1 hour |
| Other built-in adapters | No response caching; every call reaches the upstream API |
| [MCP server](mcp-server.md) | Its own in-process cache of search pages: 128 queries for 10 minutes |
| UMLS helpers | `knowledge_lookup.umls.UMLSCache`, a separate SQLite concept cache (`~/.cache/knowledge-lookup/umls_cache.db`) |

The [term expansion](term-expansion.md) `ExpansionStore` is a permanent record, not a cache. There are no cache options on `LookupConfig`. The CLI's `search --cache-dir` option sets up a disk tier before the search, but only adapters that use the shared cache (currently UniChem) store entries there.

## The cache API

```python
from knowledge_lookup import get_cache, init_cache

cache = init_cache(
    memory_max_size=1000,          # entries kept in memory
    disk_cache_dir=".kl-cache",    # None (default) disables the disk tier
    disk_max_size=10000,           # entries kept on disk
    default_ttl=3600,              # seconds; None means no expiry
    cleanup_interval=300,          # seconds between background clean-ups
)

cache.set("answer", {"id": "HP:0001250"}, ttl=600, namespace="demo")
print(cache.get("answer", namespace="demo"))  # {'id': 'HP:0001250'}
cache.delete("answer", namespace="demo")
print(cache.get_stats()["combined"])          # hits, misses, sets, evictions, hit_rate
```

| Function or method | Description |
| --- | --- |
| `init_cache(...)` | Create a new global `KnowledgeLookupCache`, replacing any existing one, and return it |
| `get_cache()` | Return the global cache, creating a memory-only one if none exists |
| `ensure_cache()` | Return the global cache, creating it with `init_cache()` defaults only if none exists (import from `knowledge_lookup.cache`) |
| `get(key, namespace="")` | Look in memory, then on disk (a disk hit is copied back to memory) |
| `set(key, value, ttl=None, namespace="")` | Store in both tiers; `ttl=None` uses `default_ttl` |
| `delete(key, namespace="")` | Remove from both tiers |
| `clear(namespace="")` | Remove the entries of one namespace from both tiers, or everything when `namespace` is empty |
| `cleanup()` | Remove expired entries now; returns eviction counts |
| `get_stats()` | Hits, misses, sets, evictions and sizes per tier |

Keys are stored as `"<namespace>:<key>"`. The disk tier writes each entry as a JSON file, so values must be JSON-serialisable; the memory tier accepts any object. `KnowledgeLookupCache`, `MemoryCacheBackend` and `DiskCacheBackend` can also be instantiated directly.

{% hint style="info" %}
`CentralKnowledgeLookup()` keeps a global cache you configured beforehand and only creates one with `init_cache()` defaults when none exists. Each adapter keeps a reference to the cache that was global when the adapter was created, so call `init_cache(...)` *before* creating the lookup: calling it afterwards replaces the global cache, but the lookup's adapters keep using the previous one.
{% endhint %}

## Cache lookups in your application

Search results are pydantic models, so the simplest pattern is to cache their JSON form and validate it back:

{% code title="cached_search.py" %}
```python
import asyncio

from knowledge_lookup import (
    CentralKnowledgeLookup,
    KnowledgeSource,
    LookupConfig,
    LookupResult,
    get_cache,
    init_cache,
)


async def cached_search(
    lookup: CentralKnowledgeLookup, query: str, sources: list[KnowledgeSource]
) -> LookupResult:
    cache = get_cache()
    key = f"{query}|{','.join(sorted(source.value for source in sources))}"
    hit = cache.get(key, namespace="searches")
    if hit is not None:
        return LookupResult.model_validate(hit)
    result = await lookup.search_concepts(query, sources=sources)
    cache.set(key, result.model_dump(mode="json"), ttl=3600, namespace="searches")
    return result


async def main() -> None:
    # Configure the cache before creating the lookup; the lookup keeps it.
    init_cache(disk_cache_dir=".knowledge-lookup-cache", default_ttl=3600)
    lookup = CentralKnowledgeLookup(LookupConfig(enabled_sources=[KnowledgeSource.HPO]))
    try:
        first = await cached_search(lookup, "seizure", [KnowledgeSource.HPO])   # calls HPO
        second = await cached_search(lookup, "seizure", [KnowledgeSource.HPO])  # from cache
        print(first.total_found, second.total_found, get_cache().get_stats()["combined"])
    finally:
        await lookup.close()


asyncio.run(main())
```
{% endcode %}

With `disk_cache_dir` set, cached searches survive restarts until their TTL expires.

## Caching in custom adapters

`KnowledgeSourceAdapter` has helpers that namespace entries by source, for use in your own adapters:

| Helper | Description |
| --- | --- |
| `self._get_cache_key(operation, *params)` | MD5 key from the source, operation name and parameters |
| `self._get_from_cache(key)` | Value or `None` |
| `self._set_in_cache(key, value, ttl=3600)` | Store with a TTL |
| `self._has_in_cache(key)` | `True` if a non-expired value exists |
| `self.clear_cache()` | Remove every entry in this adapter's namespace from both tiers |

```python
async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
    key = self._get_cache_key("search_concepts", query, limit)
    if (cached := self._get_from_cache(key)) is not None:
        return [UnifiedConcept.model_validate(item) for item in cached]
    concepts = await self._search_upstream(query, limit)
    self._set_in_cache(key, [concept.model_dump(mode="json") for concept in concepts])
    return concepts
```

Include every parameter that changes the result in the key, and store JSON-serialisable data if the disk tier may be enabled.

## Next steps

* [Configuration](../getting-started/configuration.md)
* [Architecture](../reference/architecture.md): where the cache sits
