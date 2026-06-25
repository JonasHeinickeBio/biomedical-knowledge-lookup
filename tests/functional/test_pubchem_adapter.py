"""
Functional test for PubChem adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.pubchem_adapter import PubChemAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_pubchem_search_aspirin(adapter, response_validator, warning_manager):
    """
    Test PubChem search for aspirin with real API call.

    This test validates:
    - Adapter can connect to PubChem API
    - Response structure matches expected format
    - Results contain compound information
    """
    adapter = PubChemAdapter(adapter.config)

    # Search for aspirin
    results = await adapter.search_concepts("aspirin", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"

    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, "primary_id"), "Result missing primary_id"
        assert hasattr(result, "primary_label"), "Result missing primary_label"
        assert hasattr(result, "concept_type"), "Result missing concept_type"
        assert hasattr(result, "definitions"), "Result missing definitions"

    # Extract sample response data
    response_data = {
        "total_results": len(results),
        "sample_concepts": [
            {
                "primary_id": c.primary_id,
                "primary_label": c.primary_label,
                "concept_type": str(c.concept_type),
                "definitions": c.definitions if hasattr(c, "definitions") else [],
            }
            for c in results[:2]
        ],
    }

    # Validate response structure
    validator = response_validator(KnowledgeSource.PUBCHEM)
    changes = validator.validate_response("pubchem_aspirin_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.PUBCHEM, "pubchem_aspirin_search", change)


@pytest.mark.asyncio
async def test_pubchem_search_metformin(adapter, response_validator, warning_manager):
    """Test PubChem search for metformin."""
    adapter = PubChemAdapter(adapter.config)

    results = await adapter.search_concepts("metformin", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_pubchem_search_ibuprofen(adapter, response_validator, warning_manager):
    """Test PubChem search for ibuprofen."""
    adapter = PubChemAdapter(adapter.config)

    results = await adapter.search_concepts("ibuprofen", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_pubchem_empty_search(adapter, response_validator):
    """Test PubChem search with no results."""
    adapter = PubChemAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_pubchem_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = PubChemAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("aspirin", limit=2)

    assert len(results) <= 2, f"Expected max 2 results, got {len(results)}"

    # Test with larger limit
    results = await adapter.search_concepts("aspirin", limit=10)

    assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
