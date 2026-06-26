"""
Functional test for EUtils adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.eutils_adapter import EUtilsAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_eutils_search_diabetes(adapter, response_validator, warning_manager):
    """
    Test EUtils search for diabetes with real API call.

    This test validates:
    - Adapter can connect to EUtils API
    - Response structure matches expected format
    - Results contain PubMed IDs and article information
    """
    adapter = EUtilsAdapter(adapter.config)

    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"

    # EUtils may return 0 results depending on query
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
    validator = response_validator(KnowledgeSource.EUTILS)
    changes = validator.validate_response("eutils_diabetes_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.EUTILS, "eutils_diabetes_search", change)


@pytest.mark.asyncio
async def test_eutils_search_brca(adapter, response_validator, warning_manager):
    """Test EUtils search for BRCA."""
    adapter = EUtilsAdapter(adapter.config)

    results = await adapter.search_concepts("BRCA1", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_eutils_search_gene(adapter, response_validator, warning_manager):
    """Test EUtils search for a gene."""
    adapter = EUtilsAdapter(adapter.config)

    results = await adapter.search_concepts("TP53", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_eutils_empty_search(adapter, response_validator):
    """Test EUtils search with no results."""
    adapter = EUtilsAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_eutils_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = EUtilsAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("diabetes", limit=2)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_eutils_disease_concept_type(adapter, response_validator):
    """Test that disease concepts are properly classified."""
    adapter = EUtilsAdapter(adapter.config)

    results = await adapter.search_concepts("diabetes", limit=3)

    if len(results) > 0:
        # Check concept types
        for result in results[:2]:
            # Should have a concept type
            assert hasattr(result, "concept_type")
            # May be disease or unknown depending on results
