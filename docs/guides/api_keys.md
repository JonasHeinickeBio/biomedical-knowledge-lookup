# API Keys Configuration Guide

Many knowledge sources require or benefit from API keys. This guide covers setup for all sources.

## Overview

| Source | Required | Free Tier | Registration | Environment Variable |
|--------|----------|-----------|--------------|---------------------|
| BioPortal | Optional | Yes | Yes | `BIOPORTAL_API_KEY` |
| UMLS | Yes | No | Yes (license) | `UMLS_API_KEY` or `UMLS_API_KEY_TU` |
| DisGeNET | Optional | Limited | Yes | `DISGENET_API_KEY` |
| ChEMBL | Optional | Yes | Yes (for higher limits) | `CHEMBL_API_KEY` |
| OMIM | Yes | Limited | Yes | `OMIM_API_KEY` |
| DrugBank | Yes | Limited | Yes | `DRUGBANK_API_KEY` |
| others | No | N/A | N/A | N/A |

## Setting Up API Keys

### Step 1: Register for API Access

#### BioPortal (Free)
1. Visit https://bioportal.bioontology.org/
2. Click "Register" in top right
3. Verify email
4. Go to "Settings" → "API Keys"
5. Copy your API key

#### UMLS (License Required)
1. Visit https://uts.nlm.nlm.gov/
2. Create an account
3. Submit license request
4. Wait for approval (typically 1-2 business days)
5. Generate API key from UTS account settings

#### DisGeNET (Registration Required)
1. Visit https://www.disgenet.org/
2. Register for a free account
3. Navigate to API section
4. Request API access
5. Copy your API key

### Step 2: Configure Environment Variables

#### Method 1: Direct Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export BIOPORTAL_API_KEY="your-bioportal-key"
export UMLS_API_KEY="your-umls-key"
export DISGENET_API_KEY="your-disgenet-key"
```

#### Method 2: Using .env File

```bash
# Create .env file in project root
cat > .env << EOF
BIOPORTAL_API_KEY="your-bioportal-key"
UMLS_API_KEY="your-umls-key"
DISGENET_API_KEY="your-disgenet-key"
CHEMBL_API_KEY="your-chembl-key"
EOF

# Load in Python
from dotenv import load_dotenv
load_dotenv()
```

#### Method 3: In Code (Not Recommended for Production)

```python
import os
os.environ["BIOPORTAL_API_KEY"] = "your-key"
```

### Step 3: Verify Configuration

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def test_api_keys():
    # Test with configuration
    config = LookupConfig()
    lookup = CentralKnowledgeLookup(config)
    
    # Check if sources are available
    print(f"BioPortal available: {await lookup.is_source_available('BioPortal')}")
    
    # Test search with BioPortal
    try:
        result = await lookup.search_concepts(
            "diabetes",
            sources=["BioPortal"]
        )
        print(f"Search successful: {len(result.concepts)} concepts")
    except Exception as e:
        print(f"Error: {e}")
    
    await lookup.close()

asyncio.run(test_api_keys())
```

## Best Practices

### 1. Don't Hardcode API Keys

```python
# ❌ BAD
API_KEY = "sk-1234567890abcdef"

# ✅ GOOD
import os
API_KEY = os.environ.get("BIOPORTAL_API_KEY")
if not API_KEY:
    raise ValueError("API key not set")
```

### 2. Use Environment Variable Managers

- **direnv**: Auto-load .env based on directory
- **python-dotenv**: Load .env files in Python
- **AWS Secrets Manager**: For cloud deployments
- **HashiCorp Vault**: For enterprise use

### 3. Rotate Keys Regularly

- Set reminders to rotate API keys
- Use different keys for development/staging/production
- Audit which services have access to each key

### 4. Handle Missing Keys Gracefully

```python
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource
from knowledge_lookup.exceptions import ConfigurationError

lookup = CentralKnowledgeLookup()

# Check availability before use
if not await lookup.is_source_available(KnowledgeSource.BIOPORTAL):
    print("BioPortal not available, skipping...")
    # Use alternative sources
```

## Rate Limits and API Keys

### Improved limits with API Keys

| Source | Without Key | With Key |
|--------|-------------|----------|
| BioPortal | 5 req/min | 100 req/min |
| UMLS | N/A | 1000 req/day |
| ChEMBL | 5 req/min | 100 req/min |

## Troubleshooting

### Error: "API key required"

```python
# Check if key is set
import os
print(os.environ.get("BIOPORTAL_API_KEY"))  # Should print your key or None
```

### Error: "Invalid API key"

1. Verify key format (no spaces, correct length)
2. Check key hasn't expired
3. Ensure correct environment variable name
4. Restart your application after setting variables

### Error: "Rate limit exceeded"

1. Implement exponential backoff
2. Reduce query frequency
3. Cache results
4. Consider upgrading to paid tier
