# Rate Limiting Guide

This guide explains how to handle rate limits when using Biomedical Knowledge Lookup.

## Overview

Rate limiting is a technique used by API providers to:
- Prevent server overload
- Ensure fair usage
- Maintain service availability

The library handles rate limiting automatically, but understanding it helps optimize usage.

## How Rate Limiting Works

### Per-Source Rate Limits

Each knowledge source has its own rate limit:

| Source | Requests/Second | Requests/Day | Notes |
|--------|-----------------|--------------|-------|
| BioPortal | 5-100 | 10,000 | Depends on API key |
| UMLS | 1000 | 10,000 | Requires license |
| ChEMBL | 5-100 | 100,000 | With API key |
| DisGeNET | 10 | 1,000 | Free tier |
| MONDO | 10 | 100 | Limited |
| others | Varies | Varies | See source docs |

### Rate Limit Headers

API responses include headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Time until reset

## Automatic Rate Limiting

The library includes automatic rate limiting:

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup

async def automatic_rate_limiting():
    lookup = CentralKnowledgeLookup()
    
    # Library automatically handles rate limits
    # Multiple queries are queued and executed with appropriate delays
    
    results = await lookup.search_concepts(
        "diabetes",
        sources=["BioPortal", "UMLS", "ChEMBL"],
        limit=20
    )
    
    await lookup.close()

asyncio.run(automatic_rate_limiting())
```

## Manual Rate Limiting

### Control Concurrency

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def manual_rate_limiting():
    config = LookupConfig(
        timeout_per_source=10.0,
        max_results_per_source=10  # Reduce results per source
    )
    
    lookup = CentralKnowledgeLookup(config)
    
    # Query sources sequentially instead of concurrently
    for source in ["BioPortal", "UMLS", "ChEMBL"]:
        try:
            result = await lookup.search_concepts(
                "diabetes",
                sources=[source],
                limit=10
            )
            print(f"{source}: {len(result.concepts)} results")
            
            # Add delay between requests
            await asyncio.sleep(1)
        except Exception as e:
            print(f"{source} error: {e}")
    
    await lookup.close()

asyncio.run(manual_rate_limiting())
```

## Retry with Backoff

### Exponential Backoff

```python
import asyncio
import random
from knowledge_lookup import CentralKnowledgeLookup
from knowledge_lookup.exceptions import RateLimitError

async def search_with_backoff(lookup, query, sources, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await lookup.search_concepts(query, sources=sources)
        except RateLimitError:
            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt seconds + jitter
                wait_time = 2 ** attempt + random.uniform(0, 1)
                print(f"Rate limited. Waiting {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
            else:
                raise

async def retry_example():
    lookup = CentralKnowledgeLookup()
    
    result = await search_with_backoff(
        lookup,
        "diabetes",
        sources=["BioPortal"],
        max_retries=5
    )
    
    print(f"Results: {len(result.concepts)}")
    await lookup.close()

asyncio.run(retry_example())
```

### Custom Backoff Strategy

```python
async def custom_backoff(lookup, query, sources, max_retries=5):
    """Custom backoff with jitter."""
    for attempt in range(max_retries):
        try:
            return await lookup.search_concepts(query, sources=sources)
        except RateLimitError as e:
            if attempt < max_retries - 1:
                # Fibonacci backoff + jitter
                wait_times = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
                wait_time = wait_times[attempt] + random.uniform(0, 2)
                print(f"Retry {attempt + 1} after {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            else:
                raise

asyncio.run(retry_example())
```

## Best Practices

### 1. Use API Keys

API keys typically provide higher rate limits:

```bash
# Set API keys
export BIOPORTAL_API_KEY="your-key"
export UMLS_API_KEY="your-key"
```

### 2. Implement Caching

```python
from knowledge_lookup import LookupConfig

config = LookupConfig(
    cache_enabled=True,
    cache_ttl=3600  # Cache for 1 hour
)
```

### 3. Batch Queries

```python
# Instead of multiple single queries
for term in ["diabetes", "cancer", "Alzheimer"]:
    result = await lookup.search_concepts(term)

# Use a single query with multiple sources
result = await lookup.search_concepts(
    "diabetes OR cancer OR Alzheimer",
    sources=["BioPortal", "UMLS"]
)
```

### 4. Use Appropriate Limits

```python
# Use small limits first, then paginate
result = await lookup.search_concepts(
    "diabetes",
    sources=["BioPortal"],
    limit=10  # Start with small limit
)
```

### 5. Monitor Rate Limits

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup

async def monitor_rate_limits():
    lookup = CentralKnowledgeLookup()
    
    # Check source availability and rate limits
    for source in ["BioPortal", "UMLS", "ChEMBL"]:
        available = await lookup.is_source_available(source)
        print(f"{source}: {'Available' if available else 'Not available'}")
    
    await lookup.close()

asyncio.run(monitor_rate_limits())
```

## Rate Limiting by Source

### BioPortal

```python
# BioPortal has different limits with/without API key
# With API key: ~100 requests/minute
# Without API key: ~5 requests/minute

config = LookupConfig(
    timeout_per_source=10.0,
    max_results_per_source=20
)
```

### UMLS

```python
# UMLS has daily limits
# With API key: ~10,000 requests/day

config = LookupConfig(
    cache_enabled=True,
    cache_ttl=7200  # 2 hours for UMLS results
)
```

### ChEMBL

```python
# ChEMBL has high limits with API key
# Without: ~5 requests/minute
# With: ~100 requests/minute

config = LookupConfig(
    max_results_per_source=100  # Can request more
)
```

## Handling Rate Limit Errors

### Catch RateLimitError

```python
from knowledge_lookup.exceptions import RateLimitError

try:
    result = await lookup.search_concepts("diabetes")
except RateLimitError as e:
    print(f"Rate limit exceeded for {e.source}")
    print(f"Retry after: {e.retry_after} seconds")
    
    # Implement fallback
    await asyncio.sleep(e.retry_after or 60)
    # Retry with backoff
```

### Fallback Sources

```python
async def search_with_fallback(lookup, query, primary_source, fallback_source):
    try:
        return await lookup.search_concepts(query, sources=[primary_source])
    except RateLimitError:
        print(f"{primary_source} rate limited, trying {fallback_source}...")
        return await lookup.search_concepts(query, sources=[fallback_source])
