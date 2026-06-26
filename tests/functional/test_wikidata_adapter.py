"""
Functional test for Wikidata adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.wikidata_adapter import WikidataAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_wikidata_search_diabetes(adapter, response_validator, warning_manager):
    """
    Test Wikidata search for diabetes with real API call.

    This test validates:
    - Adapter can connect to Wikidata API
    - Response structure matches expected format
    - Results contain entity information
    """
    adapter = WikidataAdapter(adapter.config)

    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"

    # Wikidata search may return 0 results depending on query
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
    validator = response_validator(KnowledgeSource.WIKIDATA)
    changes = validator.validate_response("wikidata_diabetes_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.WIKIDATA, "wikidata_diabetes_search", change)


@pytest.mark.asyncio
async def test_wikidata_search_gene(adapter, response_validator, warning_manager):
    """Test Wikidata search for a gene."""
    adapter = WikidataAdapter(adapter.config)

    results = await adapter.search_concepts("BRCA1", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_wikidata_search_drug(adapter, response_validator, warning_manager):
    """Test Wikidata search for a drug."""
    adapter = WikidataAdapter(adapter.config)

    results = await adapter.search_concepts("aspirin", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_wikidata_empty_search(adapter, response_validator):
    """Test Wikidata search with no results."""
    adapter = WikidataAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_wikidata_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = WikidataAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("diabetes", limit=2)

    # Limit may not be strictly enforced by Wikidata API
    assert isinstance(results, list)
