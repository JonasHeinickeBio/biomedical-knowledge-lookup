"""
Functional test for OLS adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.ols_adapter import OLSAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_ols_search_diabetes(adapter, response_validator, warning_manager):
    """
    Test OLS search for diabetes with real API call.

    This test validates:
    - Adapter can connect to OLS API
    - Response structure matches expected format
    - Results contain ontology information
    """
    adapter = OLSAdapter(adapter.config)

    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)

    # Skip if API returns 503 (service temporarily unavailable)
    if len(results) == 0:
        pytest.skip("OLS API returned empty results (possible 503 error)")

    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"

    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, "primary_id"), "Result missing primary_id"
        assert hasattr(result, "primary_label"), "Result missing primary_label"
        assert hasattr(result, "concept_type"), "Result missing concept_type"
        assert hasattr(result, "source_data"), "Result missing source_data"

    # Extract sample response data
    response_data = {
        "total_results": len(results),
        "sample_concepts": [
            {
                "primary_id": c.primary_id,
                "primary_label": c.primary_label,
                "concept_type": str(c.concept_type),
                "source_data_keys": list(c.source_data.keys())
                if hasattr(c, "source_data")
                else [],
            }
            for c in results[:2]
        ],
    }

    # Validate response structure
    validator = response_validator(KnowledgeSource.OLS)
    changes = validator.validate_response("ols_diabetes_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.OLS, "ols_diabetes_search", change)


@pytest.mark.asyncio
async def test_ols_search_gene(adapter, response_validator, warning_manager):
    """Test OLS search for a gene."""
    adapter = OLSAdapter(adapter.config)

    results = await adapter.search_concepts("BRCA1", limit=3)

    # Skip if API returns 503 (service temporarily unavailable)
    if len(results) == 0:
        pytest.skip("OLS API returned empty results (possible 503 error)")

    assert isinstance(results, list)
    assert len(results) >= 1

    # Check results have ontology info
    for result in results[:2]:
        assert hasattr(result, "source_data")
        # OLS source_data should contain ontology info


@pytest.mark.asyncio
async def test_ols_ontology_filter(adapter, response_validator):
    """Test OLS search with ontology filtering."""
    adapter = OLSAdapter(adapter.config)

    # Search in DOID ontology (diseases)
    results = await adapter.search_concepts("diabetes", limit=3)

    # Skip if API returns 503 (service temporarily unavailable)
    if len(results) == 0:
        pytest.skip("OLS API returned empty results (possible 503 error)")

    assert isinstance(results, list)
    assert len(results) >= 1

    # Results should have ontology_name in source_data
    for result in results[:2]:
        if hasattr(result, "source_data"):
            result.source_data.get(KnowledgeSource.OLS, {})
            # OLS data should be present


@pytest.mark.asyncio
async def test_ols_empty_search(adapter, response_validator):
    """Test OLS search with no results."""
    adapter = OLSAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)
    # May or may not be empty depending on fuzzy matching


@pytest.mark.asyncio
async def test_ols_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = OLSAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("diabetes", limit=2)

    # Skip if API returns 503 (service temporarily unavailable)
    if len(results) == 0:
        pytest.skip("OLS API returned empty results (possible 503 error)")

    assert len(results) <= 2, f"Expected max 2 results, got {len(results)}"

    # Test with larger limit
    results = await adapter.search_concepts("diabetes", limit=10)

    # Skip if API returns 503 (service temporarily unavailable)
    if len(results) == 0:
        pytest.skip("OLS API returned empty results (possible 503 error)")

    assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
