# Error Handling Guide

This guide covers error handling patterns for Biomedical Knowledge Lookup.

## Error Types

### SourceUnavailableError

Raised when a knowledge source is unreachable.

```python
from knowledge_lookup.exceptions import SourceUnavailableError

try:
    result = await lookup.search_concepts("diabetes")
except SourceUnavailableError as e:
    print(f"Source unavailable: {e.source}")
    print(f"Error message: {e.message}")
    # Try alternative sources
```

### RateLimitError

Raised when rate limit is exceeded.

```python
from knowledge_lookup.exceptions import RateLimitError

try:
    result = await lookup.search_concepts("diabetes")
except RateLimitError as e:
    print(f"Rate limit exceeded for {e.source}")
    print(f"Retry after: {e.retry_after} seconds")
```

### APIError

Raised for API-specific errors.

```python
from knowledge_lookup.exceptions import APIError

try:
    result = await lookup.search_concepts("diabetes")
except APIError as e:
    print(f"API Error from {e.source}")
    print(f"Status code: {e.status_code}")
    print(f"Response: {e.response}")
```

### ConfigurationError

Raised for configuration issues.

```python
from knowledge_lookup.exceptions import ConfigurationError

try:
    config = LookupConfig(invalid_option=True)
except ConfigurationError as e:
    print(f"Configuration error: {e.message}")
```

### NetworkError

Raised for network-related errors.

```python
from knowledge_lookup.exceptions import NetworkError

try:
    result = await lookup.search_concepts("diabetes")
except NetworkError as e:
    print(f"Network error: {e.message}")
    print(f"URL: {e.url}")
```

## Error Handling Patterns

### Pattern 1: Graceful Degradation

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig
from knowledge_lookup.exceptions import SourceUnavailableError, RateLimitError

async def search_with_degradation(query: str, sources: list):
    """Search with graceful degradation when sources fail."""
    lookup = CentralKnowledgeLookup()
    
    all_results = []
    
    for source in sources:
        try:
            result = await lookup.search_concepts(
                query,
                sources=[source],
                limit=10
            )
            all_results.extend(result.concepts)
        except (SourceUnavailableError, RateLimitError) as e:
            print(f"Source {source} unavailable: {e}")
            # Continue with other sources
            continue
        except Exception as e:
            print(f"Unexpected error from {source}: {e}")
            continue
    
    await lookup.close()
    return all_results

# Usage
results = asyncio.run(search_with_degradation("diabetes", ["BioPortal", "UMLS", "ChEMBL"]))
print(f"Total results: {len(results)}")
```

### Pattern 2: Retry with Fallback

```python
import asyncio
import random
from knowledge_lookup import CentralKnowledgeLookup
from knowledge_lookup.exceptions import RateLimitError, APIError

async def search_with_retry(lookup, query, sources, max_retries=3):
    """Search with automatic retry and fallback."""
    for attempt in range(max_retries):
        try:
            return await lookup.search_concepts(query, sources=sources)
        except (RateLimitError, APIError) as e:
            if attempt < max_retries - 1:
                # Wait and retry
                wait_time = 2 ** attempt + random.uniform(0, 1)
                print(f"Error, retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
            else:
                raise
        except Exception as e:
            # Don't retry for non-rate-limit errors
            raise

async def retry_example():
    lookup = CentralKnowledgeLookup()
    
    result = await search_with_retry(
        lookup,
        "diabetes",
        sources=["BioPortal"],
        max_retries=5
    )
    
    print(f"Results: {len(result.concepts)}")
    await lookup.close()

asyncio.run(retry_example())
```

### Pattern 3: Error Aggregation

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig
from knowledge_lookup.exceptions import SourceUnavailableError

async def search_with_error_aggregation(query: str, sources: list):
    """Search and collect errors for reporting."""
    lookup = CentralKnowledgeLookup()
    
    result = await lookup.search_concepts(query, sources=sources)
    
    # Check for errors in result
    if result.errors:
        print("Errors encountered:")
        for source, error in result.errors.items():
            print(f"  - {source}: {error}")
    
    # Continue with available results
    print(f"Successful results: {len(result.concepts)}")
    
    await lookup.close()
    return result

# Usage
result = asyncio.run(search_with_error_aggregation("diabetes", ["BioPortal", "UMLS", "ChEMBL"]))
```

### Pattern 4: Health Checks

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup

async def check_source_health():
    """Check health of all sources before querying."""
    lookup = CentralKnowledgeLookup()
    
    healthy_sources = []
    unhealthy_sources = []
    
    for source in lookup.available_sources:
        try:
            available = await lookup.is_source_available(source)
            if available:
                healthy_sources.append(source)
            else:
                unhealthy_sources.append(source)
        except Exception as e:
            unhealthy_sources.append(source)
            print(f"Error checking {source}: {e}")
    
    print(f"Healthy sources: {healthy_sources}")
    print(f"Unhealthy sources: {unhealthy_sources}")
    
    await lookup.close()

asyncio.run(check_source_health())
```

### Pattern 5: Timeout Handling

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig
from knowledge_lookup.exceptions import APIError

async def search_with_timeout(query: str, sources: list, timeout: float = 5.0):
    """Search with custom timeout per source."""
    config = LookupConfig(
        timeout_per_source=timeout,
        cache_enabled=True
    )
    lookup = CentralKnowledgeLookup(config)
    
    try:
        # Use asyncio.wait_for to enforce timeout
        result = await asyncio.wait_for(
            lookup.search_concepts(query, sources=sources),
            timeout=timeout * len(sources)  # Total timeout
        )
        return result
    except asyncio.TimeoutError:
        print("Search timed out")
        # Return partial results or empty result
        return await lookup.search_concepts(query, sources=sources[:1])
    finally:
        await lookup.close()

# Usage
result = asyncio.run(search_with_timeout("diabetes", ["BioPortal", "UMLS"], timeout=3.0))
```

## Logging Errors

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Now all errors will be logged
```

### Custom Error Logging

```python
import logging
from knowledge_lookup import CentralKnowledgeLookup
from knowledge_lookup.exceptions import RateLimitError

# Configure custom logger
logger = logging.getLogger('biomedical_lookup')
logger.setLevel(logging.ERROR)
handler = logging.FileHandler('errors.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

async def search_with_logging(query: str):
    lookup = CentralKnowledgeLookup()
    
    try:
        result = await lookup.search_concepts(query)
    except RateLimitError as e:
        logger.error(f"Rate limit exceeded for {e.source}: {e}")
        raise
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}")
        raise
    finally:
        await lookup.close()
    
    return result
```

## Best Practices

### 1. Always Handle Errors

```python
# ❌ BAD - No error handling
result = await lookup.search_concepts("diabetes")

# ✅ GOOD - With error handling
try:
    result = await lookup.search_concepts("diabetes")
except Exception as e:
    print(f"Error: {e}")
    result = None
```

### 2. Use Specific Exception Types

```python
# ❌ BAD - Broad exception
except Exception as e:
    print("Error")

# ✅ GOOD - Specific exceptions
except RateLimitError as e:
    print(f"Rate limit: {e.source}")
except SourceUnavailableError as e:
    print(f"Unavailable: {e.source}")
```

### 3. Provide User-Friendly Messages

```python
# ❌ BAD - Technical error
except RateLimitError as e:
    raise e

# ✅ GOOD - User-friendly message
except RateLimitError as e:
    print(f"Rate limit reached for {e.source}. Please wait {e.retry_after}s and try again.")
```

### 4. Implement Retry Logic

```python
# Always implement retry for transient errors
for attempt in range(3):
    try:
        result = await lookup.search_concepts(query)
        break
    except RateLimitError:
        await asyncio.sleep(2 ** attempt)
else:
    raise Exception("Max retries exceeded")
```
