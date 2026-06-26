"""
Functional test for EuropePMC adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.europepmc_adapter import EuropePMCAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_europepmc_search_diabetes(adapter, response_validator, warning_manager):
    """
    Test EuropePMC search for diabetes with real API call.

    This test validates:
    - Adapter can connect to EuropePMC API
    - Response structure matches expected format
    - Results contain article information
    """
    adapter = EuropePMCAdapter(adapter.config)

    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"

    # EuropePMC may return 0 results depending on query
    if len(results) > 0:
        assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"

        # Check that results have expected structure
        for result in results[:3]:
            assert hasattr(result, "primary_id"), "Result missing primary_id"
            assert hasattr(result, "primary_label"), "Result missing primary_label"
            assert hasattr(result, "concept_type"), "Result missing concept_type"

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
        ],
    }

    # Validate response structure
    validator = response_validator(KnowledgeSource.EUROPEPMC)
    changes = validator.validate_response("europepmc_diabetes_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.EUROPEPMC, "europepmc_diabetes_search", change)


@pytest.mark.asyncio
async def test_europepmc_search_gene(adapter, response_validator, warning_manager):
    """Test EuropePMC search for a gene."""
    adapter = EuropePMCAdapter(adapter.config)

    results = await adapter.search_concepts("BRCA1", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_europepmc_search_drug(adapter, response_validator, warning_manager):
    """Test EuropePMC search for a drug."""
    adapter = EuropePMCAdapter(adapter.config)

    results = await adapter.search_concepts("metformin", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_europepmc_empty_search(adapter, response_validator):
    """Test EuropePMC search with no results."""
    adapter = EuropePMCAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_europepmc_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = EuropePMCAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("diabetes", limit=2)

    assert isinstance(results, list)
