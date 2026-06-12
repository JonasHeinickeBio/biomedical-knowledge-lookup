# Caching Guide

This guide explains how to use the built-in caching system to optimize performance.

## Overview

The Biomedical Knowledge Lookup library includes an intelligent caching system that:

- Reduces API calls to external services
- Speeds up repeated queries
- Helps manage rate limits
- Stores results locally for offline access

## Cache Configuration

### Basic Configuration

```python
from knowledge_lookup import LookupConfig

config = LookupConfig(
    cache_enabled=True,       # Enable caching
    cache_ttl=3600,           # Time-to-live in seconds (1 hour)
    cache_dir="./cache"       # Directory for cache files
)
```

### Advanced Configuration

```python
config = LookupConfig(
    cache_enabled=True,
    cache_ttl=3600,           # Default TTL
    cache_ttl_by_source={     # Per-source TTL overrides
        "BioPortal": 7200,    # 2 hours for BioPortal
        "UMLS": 1800,         # 30 minutes for UMLS
    },
    cache_dir="./cache",
    cache_max_size=1000,      # Maximum number of cached items
)
```

## Usage Examples

### Simple Caching

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def search_with_caching():
    config = LookupConfig(
        cache_enabled=True,
        cache_ttl=3600,  # 1 hour
        cache_dir="./cache"
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    # First search - hits API
    result1 = await lookup.search_concepts("diabetes", sources=["BioPortal"])
    print(f"First search: {len(result1.concepts)} concepts")
    
    # Second search with same parameters - uses cache
    result2 = await lookup.search_concepts("diabetes", sources=["BioPortal"])
    print(f"Second search (cached): {len(result2.concepts)} concepts")
    
    await lookup.close()

asyncio.run(search_with_caching())
```

### Checking Cache Status

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def check_cache_status():
    config = LookupConfig(cache_enabled=True)
    lookup = CentralKnowledgeLookup(config)
    
    # Check if cache is enabled
    print(f"Cache enabled: {config.cache_enabled}")
    print(f"Cache directory: {config.cache_dir}")
    print(f"Default TTL: {config.cache_ttl} seconds")
    
    # Search
    result = await lookup.search_concepts("insulin", sources=["BioPortal"])
    print(f"Results: {len(result.concepts)}")
    
    await lookup.close()

asyncio.run(check_cache_status())
```

## Cache Management

### Clear Cache

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def clear_cache():
    config = LookupConfig(cache_enabled=True)
    lookup = CentralKnowledgeLookup(config)
    
    # Clear all cached results
    await lookup.clear_cache()
    print("Cache cleared")
    
    await lookup.close()

asyncio.run(clear_cache())
```

### Cache Statistics

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def get_cache_stats():
    config = LookupConfig(cache_enabled=True)
    lookup = CentralKnowledgeLookup(config)
    
    # Get cache directory info
    import os
    cache_dir = config.cache_dir
    
    if os.path.exists(cache_dir):
        files = os.listdir(cache_dir)
        print(f"Cache files: {len(files)}")
        
        total_size = sum(
            os.path.getsize(os.path.join(cache_dir, f))
            for f in files
        )
        print(f"Total cache size: {total_size} bytes")
    else:
        print("Cache directory does not exist")
    
    await lookup.close()

asyncio.run(get_cache_stats())
```

## Cache Behavior

### Cache Keys

Cache keys are generated based on:
- Source name
- Query parameters
- Search type (search_concepts vs get_concept_details)
- Result limit

### Cache Expiration

Cache entries expire based on:
- `cache_ttl` setting (default: 1 hour)
- Per-source TTL overrides
- Manual cache clearing

### Cache Hit/Miss

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def analyze_cache_hits():
    config = LookupConfig(cache_enabled=True)
    lookup = CentralKnowledgeLookup(config)
    
    # First query - cache miss
    result1 = await lookup.search_concepts("diabetes")
    print(f"First query: cache miss (hit count: 0)")
    
    # Second query - cache hit
    result2 = await lookup.search_concepts("diabetes")
    print(f"Second query: cache hit")
    
    await lookup.close()

asyncio.run(analyze_cache_hits())
```

## Best Practices

### 1. Use Appropriate TTL

```python
# Short TTL for frequently changing data
config = LookupConfig(
    cache_ttl=300,  # 5 minutes for real-time data
)

# Long TTL for static data
config = LookupConfig(
    cache_ttl=86400,  # 24 hours for static ontologies
)
```

### 2. Clear Cache After Updates

```python
# After data updates, clear cache
await lookup.clear_cache()
```

### 3. Use Cache in Production

```python
# In production, always use caching
config = LookupConfig(
    cache_enabled=True,
    cache_ttl=3600,
    cache_dir="/var/cache/biomedical-lookup"
)
```

### 4. Monitor Cache Size

```python
# Set maximum cache size
config = LookupConfig(
    cache_max_size=1000,  # Limit cache entries
)
```

## Advanced Topics

### Custom Cache Backend

You can implement a custom cache backend by extending the cache interface.

### Cache Invalidation

```python
# Invalidate specific cache entry
await lookup.clear_cache(entry="search:diabetes:BioPortal")
```

### Cache Warming

```python
# Pre-populate cache
async def warm_cache():
    lookup = CentralKnowledgeLookup(LookupConfig(cache_enabled=True))
    
    # Pre-cache common queries
    queries = ["diabetes", "cancer", "Alzheimer", "insulin"]
    for query in queries:
        await lookup.search_concepts(query)
    
    await lookup.close()

asyncio.run(warm_cache())
```

## Troubleshooting

### Cache Not Working

1. Verify `cache_enabled=True`
2. Check `cache_dir` is writable
3. Look for cache files in cache directory

### Cache Too Large

1. Reduce `cache_ttl`
2. Set `cache_max_size`
3. Clear cache periodically
