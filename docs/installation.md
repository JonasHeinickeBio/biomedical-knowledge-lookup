# Installation Guide

The Biomedical Knowledge Lookup library can be installed in multiple ways depending on your needs.

## System Requirements

### Python Version
- **Minimum**: Python 3.10
- **Recommended**: Python 3.11 or 3.12
- **Unsupported**: Python < 3.10

### Dependencies
The library requires:
- `aiohttp >= 3.9.0` - Async HTTP client
- `pydantic >= 2.0.0` - Data validation
- `rdflib >= 7.0.0` - RDF graph handling
- `pandas >= 2.0.0` - Data manipulation
- `typer >= 0.9.0` - CLI interface

## Installation Methods

### Using pip

```bash
pip install biomedical-knowledge-lookup
```

### Using Poetry

```bash
poetry add biomedical-knowledge-lookup
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup.git
cd biomedical-knowledge-lookup

# Install with Poetry
poetry install

# Verify installation
poetry run python -m knowledge_lookup --help
```

### Using Docker

```bash
# Pull the latest image
docker pull jheinicke/biomedical-knowledge-lookup:latest

# Run with API key
docker run -it --rm \
  -e BIOPORTAL_API_KEY="your-bioportal-key" \
  jheinicke/biomedical-knowledge-lookup:latest \
  search "diabetes"

# Or use docker-compose
docker-compose up
```

## Verification

Test your installation with this quick script:

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup

async def test_installation():
    # Create lookup instance
    lookup = CentralKnowledgeLookup()
    
    # Check available sources
    print(f"Available knowledge sources: {len(lookup.available_sources)}")
    
    # Test a simple search
    result = await lookup.search_concepts(
        query="diabetes",
        sources=["BioPortal"],
        limit=3
    )
    
    print(f"\nSearch results: {len(result.concepts)} concepts found")
    for concept in result.concepts[:3]:
        print(f"  - {concept.primary_label} ({concept.primary_id})")
    
    await lookup.close()

# Run the test
asyncio.run(test_installation())
```

Expected output:
```
Available knowledge sources: 29+

Search results: 3 concepts found
  - Diabetes Mellitus (C0011849)
  - Diabetes Insipidus (C0013421)
  - Gestational Diabetes (C0017635)
```

## Development Setup

For contributors who want to modify the library:

```bash
# Install with development dependencies
poetry install --with dev

# Install pre-commit hooks
pre-commit install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=knowledge_lookup --cov-report=html
```

## Configuration

After installation, you may want to configure API keys for sources that require them.

### Setting Up API Keys

Create a `.env` file in your project root:

```bash
# .env file
BIOPORTAL_API_KEY=your_bioportal_key_here
UMLS_API_KEY=your_umls_key_here
DISGENET_API_KEY=your_disgenet_key_here
```

Then load it in your Python code:

```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env file

# Now use the library
from knowledge_lookup import CentralKnowledgeLookup
lookup = CentralKnowledgeLookup()
```

### Optional Configuration

The library supports various configuration options:

```python
from knowledge_lookup import LookupConfig

config = LookupConfig(
    cache_enabled=True,          # Enable result caching
    cache_ttl=3600,              # Cache TTL in seconds (1 hour)
    cache_dir="./cache",         # Cache directory
    timeout_per_source=10.0,     # Timeout per source in seconds
    max_results_per_source=20,   # Maximum results per source
    log_level="INFO"             # Logging level
)
```

## Troubleshooting

### Issue: Module not found

**Error**: `ModuleNotFoundError: No module named 'knowledge_lookup'`

**Solution**: Ensure you're using the correct Python environment:
```bash
# If using poetry
poetry run python -c "import knowledge_lookup"

# If using pip
pip show biomedical-knowledge-lookup
```

### Issue: Import errors

**Error**: `ImportError: cannot import name 'CentralKnowledgeLookup'`

**Solution**: The library uses async-first design. Make sure you're using it correctly:
```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup

async def main():
    lookup = CentralKnowledgeLookup()
    # ... use lookup

asyncio.run(main())
```

### Issue: No API key errors

**Error**: Sources return empty results or errors

**Solution**: Set up API keys for sources that require them. See the [API Keys Guide](guides/api_keys.md).

### Issue: Rate limiting

**Error**: `RateLimitError` or API returns HTTP 429

**Solution**: Implement exponential backoff and reduce query frequency. See [Rate Limiting Guide](guides/rate_limiting.md).

## Next Steps

After installation:
1. Set up API keys for required sources
2. Read the [Getting Started Guide](getting_started/overview.md)
3. Try the [Tutorials](tutorials/01-basics.md)
4. Explore [Example Notebooks](examples/notebooks/)
