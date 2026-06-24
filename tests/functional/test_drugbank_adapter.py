"""
Functional test for DrugBank adapter.

Tests real API calls to validate response structures and detect changes.
Requires DRUGBANK_API_KEY environment variable.
"""

import os

import pytest
from knowledge_lookup.adapters.drugbank_adapter import DrugBankAdapter
from knowledge_lookup.models import KnowledgeSource

from .conftest import requires_api_key

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.api]


@pytest.fixture
def drugbank_available():
    """Check if DrugBank API key is available."""
    api_key = os.environ.get("DRUGBANK_API_KEY")
    return api_key is not None and len(api_key) > 10


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.DRUGBANK)
async def test_drugbank_search_aspirin(
    adapter, response_validator, warning_manager, drugbank_available
):
    """
    Test DrugBank search for aspirin with real API call.

    This test validates:
    - Adapter can connect to DrugBank API
    - Response structure matches expected format
    - Results contain drug information
    """
    if not drugbank_available:
        pytest.skip("DRUGBANK_API_KEY not set")

    adapter = DrugBankAdapter(adapter.config)

    # Search for aspirin
    results = await adapter.search_concepts("aspirin", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
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
    validator = response_validator(KnowledgeSource.DRUGBANK)
    changes = validator.validate_response("drugbank_aspirin_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.DRUGBANK, "drugbank_aspirin_search", change)

    # Print changes if any
    if changes:
        print("\nDrugBank response structure changes detected:")
        for change in changes:
            print(f"  - {change}")


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.DRUGBANK)
async def test_drugbank_search_metformin(
    adapter, response_validator, warning_manager, drugbank_available
):
    """Test DrugBank search for metformin."""
    if not drugbank_available:
        pytest.skip("DRUGBANK_API_KEY not set")

    adapter = DrugBankAdapter(adapter.config)

    results = await adapter.search_concepts("metformin", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.DRUGBANK)
async def test_drugbank_search_insulin(
    adapter, response_validator, warning_manager, drugbank_available
):
    """Test DrugBank search for insulin."""
    if not drugbank_available:
        pytest.skip("DRUGBANK_API_KEY not set")

    adapter = DrugBankAdapter(adapter.config)

    results = await adapter.search_concepts("insulin", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.DRUGBANK)
async def test_drugbank_empty_search(
    adapter, response_validator, drugbank_available
):
    """Test DrugBank search with no results."""
    if not drugbank_available:
        pytest.skip("DRUGBANK_API_KEY not set")

    adapter = DrugBankAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.DRUGBANK)
async def test_drugbank_limit_parameter(
    adapter, response_validator, drugbank_available
):
    """Test that limit parameter works correctly."""
    if not drugbank_available:
        pytest.skip("DRUGBANK_API_KEY not set")

    adapter = DrugBankAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("aspirin", limit=2)

    assert len(results) <= 2, f"Expected max 2 results, got {len(results)}"

    # Test with larger limit
    results = await adapter.search_concepts("aspirin", limit=10)

    assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
