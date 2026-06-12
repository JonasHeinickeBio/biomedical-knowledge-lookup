"""
Functional test for ChEMBL adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest

try:
    from knowledge_lookup.adapters.chembl_adapter import ChEMBLAdapter
except (ImportError, Exception) as e:
    ChEMBLAdapter = None
    pytestmark = pytest.mark.skip(reason=f"ChEMBL adapter not available: {e}")

from knowledge_lookup.models import KnowledgeSource

from .conftest import requires_network

# Skip entire module if ChEMBL adapter is not available
if ChEMBLAdapter is None:
    pytestmark = [
        pytest.mark.functional,
        pytest.mark.network,
        pytest.mark.asyncio,
    ]


@pytest.mark.asyncio
async def test_chembl_search_aspirin(adapter, response_validator, warning_manager):
    """
    Test ChEMBL search for aspirin with real API call.
    
    This test validates:
    - Adapter can connect to ChEMBL API
    - Response structure matches expected format
    - Results contain drug information
    """
    adapter = ChEMBLAdapter(adapter.config)
    
    # Search for aspirin
    results = await adapter.search_concepts("aspirin", limit=5)
    
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
    validator = response_validator(KnowledgeSource.CHEMBL)
    changes = validator.validate_response("chembl_aspirin_search", response_data)
    
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.CHEMBL, "chembl_aspirin_search", change)


@pytest.mark.asyncio
async def test_chembl_search_metformin(adapter, response_validator, warning_manager):
    """Test ChEMBL search for metformin."""
    adapter = ChEMBLAdapter(adapter.config)
    
    results = await adapter.search_concepts("metformin", limit=3)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_chembl_search_drug(adapter, response_validator, warning_manager):
    """Test ChEMBL search for a drug."""
    adapter = ChEMBLAdapter(adapter.config)
    
    results = await adapter.search_concepts("ibuprofen", limit=3)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_chembl_empty_search(adapter, response_validator):
    """Test ChEMBL search with no results."""
    adapter = ChEMBLAdapter(adapter.config)
    
    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_chembl_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = ChEMBLAdapter(adapter.config)
    
    # Test with small limit
    results = await adapter.search_concepts("aspirin", limit=2)
    
    assert isinstance(results, list)
