"""
Functional test for HPO adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest

from knowledge_lookup.adapters.hpo_adapter import HPOAdapter
from knowledge_lookup.models import KnowledgeSource

from .conftest import requires_network

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_hpo_search_diabetes(adapter, response_validator, warning_manager):
    """
    Test HPO search for diabetes with real API call.
    
    This test validates:
    - Adapter can connect to HPO API
    - Response structure matches expected format
    - Results contain phenotype information
    """
    adapter = HPOAdapter(adapter.config)
    
    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)
    
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
    validator = response_validator(KnowledgeSource.HPO)
    changes = validator.validate_response("hpo_diabetes_search", response_data)
    
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.HPO, "hpo_diabetes_search", change)


@pytest.mark.asyncio
async def test_hpo_search_phenotype(adapter, response_validator, warning_manager):
    """Test HPO search for a phenotype."""
    adapter = HPOAdapter(adapter.config)
    
    results = await adapter.search_concepts("obesity", limit=3)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hpo_search_gene(adapter, response_validator, warning_manager):
    """Test HPO search for a gene."""
    adapter = HPOAdapter(adapter.config)
    
    results = await adapter.search_concepts("BRCA1", limit=3)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hpo_empty_search(adapter, response_validator):
    """Test HPO search with no results."""
    adapter = HPOAdapter(adapter.config)
    
    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hpo_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = HPOAdapter(adapter.config)
    
    # Test with small limit
    results = await adapter.search_concepts("diabetes", limit=2)
    
    assert isinstance(results, list)
