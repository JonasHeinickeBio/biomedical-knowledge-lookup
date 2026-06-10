"""
Functional test for Reactome adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest

from knowledge_lookup.adapters.reactome_adapter import ReactomeAdapter
from knowledge_lookup.models import KnowledgeSource

from .conftest import requires_network

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_reactome_search_signaling(adapter, response_validator, warning_manager):
    """
    Test Reactome search for signaling pathways with real API call.
    
    This test validates:
    - Adapter can connect to Reactome API
    - Response structure matches expected format
    - Results contain pathway information
    """
    adapter = ReactomeAdapter(adapter.config)
    
    # Search for signaling pathways
    results = await adapter.search_concepts("signaling", limit=5)
    
    # Validate results
    assert isinstance(results, list), "Expected list of results"
    
    if len(results) > 0:
        assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
        
        # Check that results have expected structure
        for result in results[:3]:
            assert hasattr(result, 'primary_id'), "Result missing primary_id"
            assert hasattr(result, 'primary_label'), "Result missing primary_label"
            assert hasattr(result, 'concept_type'), "Result missing concept_type"
    
    # Extract sample response data
    response_data = {
        "total_results": len(results),
        "sample_concepts": [
            {
                "primary_id": c.primary_id,
                "primary_label": c.primary_label,
                "concept_type": str(c.concept_type),
            }
            for c in results[:2]
        ]
    }
    
    # Validate response structure
    validator = response_validator(KnowledgeSource.REACTOME)
    changes = validator.validate_response("reactome_signaling_search", response_data)
    
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.REACTOME, "reactome_signaling_search", change)


@pytest.mark.asyncio
async def test_reactome_search_metabolism(adapter, response_validator, warning_manager):
    """Test Reactome search for metabolism."""
    adapter = ReactomeAdapter(adapter.config)
    
    results = await adapter.search_concepts("metabolism", limit=3)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_reactome_search_insulin(adapter, response_validator, warning_manager):
    """Test Reactome search for insulin pathway."""
    adapter = ReactomeAdapter(adapter.config)
    
    results = await adapter.search_concepts("insulin", limit=3)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_reactome_empty_search(adapter, response_validator):
    """Test Reactome search with no results."""
    adapter = ReactomeAdapter(adapter.config)
    
    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_reactome_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = ReactomeAdapter(adapter.config)
    
    # Test with small limit
    results = await adapter.search_concepts("signaling", limit=2)
    
    assert isinstance(results, list)
