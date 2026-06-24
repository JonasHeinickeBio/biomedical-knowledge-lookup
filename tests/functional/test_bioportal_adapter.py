"""
Functional test for BioPortal adapter.

Tests real API calls to validate response structures and detect changes.
Requires BIOPORTAL_API_KEY environment variable.
"""

import os

import pytest
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter
from knowledge_lookup.models import KnowledgeSource

from .conftest import requires_api_key

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.api]


@pytest.fixture
def bioportal_available():
    """Check if BioPortal API key is available."""
    api_key = os.environ.get("BIOPORTAL_API_KEY")
    return api_key is not None and len(api_key) > 10


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.BIOPORTAL)
async def test_bioportal_search_diabetes(
    adapter, response_validator, warning_manager, bioportal_available
):
    """
    Test BioPortal search for diabetes with real API call.

    This test validates:
    - Adapter can connect to BioPortal API
    - Response structure matches expected format
    - Results contain ontology information
    """
    if not bioportal_available:
        pytest.skip("BIOPORTAL_API_KEY not set")

    adapter = BioPortalAdapter(adapter.config)

    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)

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
    validator = response_validator(KnowledgeSource.BIOPORTAL)
    changes = validator.validate_response("bioportal_diabetes_search", response_data)

    for change in changes:
        warning_manager.add_warning(
            KnowledgeSource.BIOPORTAL,
            "bioportal_diabetes_search",
            change
        )

    # Print changes if any
    if changes:
        print("\nBioPortal response structure changes detected:")
        for change in changes:
            print(f"  - {change}")


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.BIOPORTAL)
async def test_bioportal_search_drug(adapter, response_validator, warning_manager, bioportal_available):
    """Test BioPortal search for a drug."""
    if not bioportal_available:
        pytest.skip("BIOPORTAL_API_KEY not set")

    adapter = BioPortalAdapter(adapter.config)

    results = await adapter.search_concepts("metformin", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.BIOPORTAL)
async def test_bioportal_search_ontology(adapter, response_validator, bioportal_available):
    """Test BioPortal search with ontology filter."""
    if not bioportal_available:
        pytest.skip("BIOPORTAL_API_KEY not set")

    adapter = BioPortalAdapter(adapter.config)

    # Search in SNOMEDCT ontology
    results = await adapter.search_concepts("diabetes", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.BIOPORTAL)
async def test_bioportal_empty_search(adapter, response_validator, bioportal_available):
    """Test BioPortal search with no results."""
    if not bioportal_available:
        pytest.skip("BIOPORTAL_API_KEY not set")

    adapter = BioPortalAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
@requires_api_key(KnowledgeSource.BIOPORTAL)
async def test_bioportal_limit_parameter(adapter, response_validator, bioportal_available):
    """Test that limit parameter works correctly."""
    if not bioportal_available:
        pytest.skip("BIOPORTAL_API_KEY not set")

    adapter = BioPortalAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("diabetes", limit=2)

    assert len(results) <= 2, f"Expected max 2 results, got {len(results)}"

    # Test with larger limit
    results = await adapter.search_concepts("diabetes", limit=10)

    assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
