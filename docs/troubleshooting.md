# Troubleshooting Guide

Common issues and their solutions when using Biomedical Knowledge Lookup.

## Common Errors

### Network Connectivity Issues

#### Error: "Connection refused" or "Connection timeout"

**Symptoms**:
- `aiohttp.ClientConnectorError`
- Request hangs and times out
- Intermittent failures

**Solutions**:

1. Check your internet connection:
```bash
ping bioportal.bioontology.org
curl https://uts.nlm.nih.gov
```

2. Verify firewall settings allow outbound HTTPS (port 443)

3. Use a VPN if behind restrictive network

4. Increase timeout for slow connections:
```python
from knowledge_lookup import LookupConfig

config = LookupConfig(
    timeout_per_source=30.0,  # Increase from default 10.0
)
```

#### Error: "SSL certificate verify failed"

**Solutions**:
```python
import ssl
import asyncio
from aiohttp import ClientSession

async def test_with_ssl():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Use with caution in production
    # Consider installing proper CA certificates instead
```

### API Rate Limiting

#### Error: "HTTP 429 Too Many Requests"

**Symptoms**:
- API returns HTTP 429 status
- "Rate limit exceeded" message

**Solutions**:

1. Implement exponential backoff:
```python
import asyncio
import random
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
```

2. Reduce concurrent requests:
```python
# Limit concurrent sources
result = await lookup.search_concepts(
    query,
    sources=["BioPortal"],  # Single source instead of all
    limit=10
)
```

3. Use caching to reduce API calls:
```python
config = LookupConfig(
    cache_enabled=True,
    cache_ttl=3600,  # Cache for 1 hour
)
```

### Authentication Failures

#### Error: "401 Unauthorized" or "Invalid API key"

**Solutions**:

1. Verify API key format:
```python
import os

api_key = os.environ.get("BIOPORTAL_API_KEY")
print(f"Key length: {len(api_key) if api_key else 0}")
print(f"Key starts with: {api_key[:8] if api_key else 'None'}...")
```

2. Check environment variable name:
```python
import os
print("BIOPORTAL_API_KEY:", os.environ.get("BIOPORTAL_API_KEY"))
print("BIOPORTAL_API_KEY (env):", os.getenv("BIOPORTAL_API_KEY"))
```

3. Test with a simple curl request:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://data.bioontology.org/ontologies/MONDO/classes/http%3A%2F%2Fpurl.obolibrary.org%2Fobo%2FMONDO_0005148"
```

### Response Parsing Errors

#### Error: "JSON decode failed" or "Unexpected response format"

**Symptoms**:
- `json.JSONDecodeError`
- `KeyError` when accessing response fields
- Adapter-specific parsing errors

**Solutions**:

1. Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. Check source availability:
```python
if not await lookup.is_source_available("BioPortal"):
    print("BioPortal may be down or experiencing issues")
```

3. Handle errors gracefully:
```python
from knowledge_lookup.exceptions import APIError

try:
    result = await lookup.search_concepts("query")
except APIError as e:
    print(f"API Error: {e}")
    print(f"Source: {e.source}")
    print(f"Status code: {e.status_code}")
```

## Debugging Guide

### Enabling Verbose Logging

```python
import logging

# Enable debug logging for the library
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or for specific components
logging.getLogger('knowledge_lookup.adapters').setLevel(logging.DEBUG)
logging.getLogger('knowledge_lookup.cache').setLevel(logging.DEBUG)
```

### Inspecting HTTP Requests

```python
from aiohttp import ClientSession
import logging

logging.basicConfig(level=logging.DEBUG)

# The library uses aiohttp internally
# All HTTP requests will be logged at DEBUG level
```

### Using Python Debugger

```python
import asyncio
import pdb
from knowledge_lookup import CentralKnowledgeLookup

async def debug_search():
    lookup = CentralKnowledgeLookup()
    
    # Set breakpoint
    pdb.set_trace()
    
    result = await lookup.search_concepts("diabetes")
    print(result)

asyncio.run(debug_search())
```

## Performance Troubleshooting

### Slow Queries

**Symptoms**:
- Queries take longer than expected
- High latency for multi-source searches

**Solutions**:

1. Check network latency:
```python
import asyncio
import time
from knowledge_lookup import CentralKnowledgeLookup

async def measure_latency():
    lookup = CentralKnowledgeLookup()
    
    start = time.time()
    result = await lookup.search_concepts("diabetes", sources=["BioPortal"])
    elapsed = time.time() - start
    
    print(f"Query took {elapsed:.2f} seconds")
    print(f"Results: {len(result.concepts)}")

asyncio.run(measure_latency())
```

2. Use caching:
```python
config = LookupConfig(
    cache_enabled=True,
    cache_ttl=3600
)
```

3. Limit concurrent sources:
```python
# Instead of querying all sources
result = await lookup.search_concepts("query", sources=["BioPortal", "ChEMBL"])
```

### High Memory Usage

**Symptoms**:
- Memory usage grows with repeated queries
- Out of memory errors

**Solutions**:

1. Properly close the lookup instance:
```python
lookup = CentralKnowledgeLookup()
try:
    # ... use lookup
finally:
    await lookup.close()  # Always close!
```

2. Process results incrementally:
```python
# Use generators instead of loading all results
async for concept in lookup.search_concepts_generator("query"):
    process(concept)
```

3. Clear cache periodically:
```python
await lookup.clear_cache()
```

## Known Issues

### Issue: UMLS adapter returns empty results

**Cause**: UMLS requires authentication and may have license restrictions

**Workaround**:
- Verify UMLS API key is set correctly
- Check UMLS account status at https://uts.nlm.nih.gov
- Consider using BioPortal as alternative for UMLS content

### Issue: Some adapters timeout frequently

**Cause**: Some APIs have high latency or reliability issues

**Workaround**:
- Increase timeout for specific sources
- Implement retry logic with exponential backoff
- Use caching to reduce API calls

### Issue: Results vary between runs

**Cause**: External API responses may change or be inconsistent

**Workaround**:
- Use caching for reproducible results
- Check response timestamps
- Combine multiple sources for consensus
