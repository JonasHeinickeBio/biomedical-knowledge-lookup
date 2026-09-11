# Cache Integration in Knowledge Lookup Adapters

## Overview

All knowledge source adapters in `biomedical-knowledge-lookup` have built-in caching support through the `KnowledgeSourceAdapter` base class. This enables automatic caching of API responses with configurable TTL, reducing redundant API calls and improving performance.

## Architecture

The caching system uses a multi-level approach:

1. **Memory Cache** (`MemoryCacheBackend`): Fast, in-memory storage with LRU eviction
2. **Disk Cache** (`DiskCacheBackend`): Persistent storage for long-term caching
3. **KnowledgeLookupCache**: Unified interface managing both backends

## Adapter Cache API

All adapters inherit these cache methods from `KnowledgeSourceAdapter`:

### `_get_cache_key(operation: str, *params: Any) -> str`

Generate a unique cache key for adapter operations.

```python
cache_key = self._get_cache_key("search_concepts", query, limit)
```

### `_get_from_cache(key: str) -> Any | None`

Retrieve a value from cache. Returns `None` if not found or expired.

```python
cached_results = self._get_from_cache(cache_key)
if cached_results:
    return cached_results
```

### `_set_in_cache(key: str, value: Any, ttl: int = 3600) -> None`

Store a value in cache with TTL (default 1 hour).

```python
self._set_in_cache(cache_key, results, ttl=3600)
```

### `_has_in_cache(key: str) -> bool`

Check if a key exists in cache (not expired).

```python
if self._has_in_cache(cache_key):
    # Use cached value
```

### `clear_cache() -> None`

Clear all cached values for this adapter's source.

```python
adapter.clear_cache()  # Clears cache for specific source
```

## Usage Example

```python
from knowledge_lookup.adapters.bioontology import BioontologyAdapter
from knowledge_lookup.models import LookupConfig

async def search_with_cache():
    config = LookupConfig()
    adapter = BioontologyAdapter(config)
    
    query = "cancer"
    cache_key = adapter._get_cache_key("search", query)
    
    # Check cache first
    if cached := adapter._get_from_cache(cache_key):
        return cached
    
    # Perform API call
    results = await adapter.search_concepts(query, limit=20)
    
    # Cache for 1 hour
    adapter._set_in_cache(cache_key, results, ttl=3600)
    
    await adapter.close()
    return results
```

## Global Cache Configuration

The cache is initialized in `CentralKnowledgeLookup` with configurable settings:

```python
from knowledge_lookup.core import CentralKnowledgeLookup
from knowledge_lookup.models import LookupConfig

config = LookupConfig(
    cache_config={
        "memory_max_size": 1000,
        "disk_cache_dir": "/tmp/cache",
        "disk_max_size": 10000,
        "default_ttl": 3600,  # 1 hour
    }
)

lookup = CentralKnowledgeLookup(config)
```

## Cache Namespace

Each adapter's cache is namespaced by its source:

```python
# BioPortal cache uses namespace: "BioPortal"
# OLS cache uses namespace: "OLS"
# UMLS cache uses namespace: "UMLS"
```

This prevents key collisions between different knowledge sources.

## Performance Considerations

1. **TTL Settings**: Use shorter TTL (60-300s) for frequently changing data, longer (3600s+) for static data
2. **Cache Keys**: Include all parameters that affect the result (query, limit, filters)
3. **Disk Cache**: Enable for production to persist cache across restarts
4. **Memory Cache**: Use for short-term, high-frequency access patterns

## Integration with Existing Adapters

All 33+ adapters automatically benefit from caching:

```python
from knowledge_lookup.core import CentralKnowledgeLookup

lookup = CentralKnowledgeLookup()

# All adapters in lookup have cache support
# Cache is automatically used in search_concepts() and get_concept_details()
```

## Troubleshooting

### Cache Not Working

1. Verify `CentralKnowledgeLookup` initializes cache (happens by default)
2. Check adapter has `_cache` attribute
3. Ensure cache key is generated correctly (use `_get_cache_key()`)

### Cache Stale Data

1. Increase cache verbosity: `logging.getLogger("cache").setLevel(logging.DEBUG)`
2. Use shorter TTL for the problematic adapter
3. Manually clear cache: `adapter.clear_cache()`

### Memory Issues

1. Reduce `memory_max_size` in cache config
2. Enable disk cache for overflow
3. Implement TTL-based eviction

## Advanced: Custom Cache Keys

For complex adapters with multiple query parameters:

```python
def _generate_cache_key(self, query: str, filters: dict, limit: int) -> str:
    # Include all parameters that affect the result
    import hashlib
    params = sorted(filters.items())
    key_data = f"{query}:{params}:{limit}"
    return hashlib.md5(key_data.encode()).hexdigest()
```

## Best Practices

1. **Always use `_get_cache_key()`** - ensures consistent key generation
2. **Set appropriate TTL** - balance freshness vs performance
3. **Check cache before expensive operations** - API calls, parsing
4. **Clear cache on updates** - after data modifications
5. **Monitor cache hit rates** - use `get_cache().get_stats()`

## References

- `src/knowledge_lookup/base.py` - Base adapter class with cache helpers
- `src/knowledge_lookup/cache/cache.py` - Core caching implementation
- `src/knowledge_lookup/core/central_lookup.py` - Cache initialization
- `tests/unit/test_cache.py` - Cache integration tests