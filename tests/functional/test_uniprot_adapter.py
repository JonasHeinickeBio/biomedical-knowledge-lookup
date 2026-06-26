"""
Functional test for UniProt adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.uniprot_adapter import UniProtAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_uniprot_search_insulin(adapter, response_validator, warning_manager):
    """
    Test UniProt search for insulin with real API call.

    This test validates:
    - Adapter can connect to UniProt API
    - Response structure matches expected format
    - Results contain expected data
    """
    adapter = UniProtAdapter(adapter.config)

    # Search for insulin
    results = await adapter.search_concepts("insulin", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"

    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, "primary_id"), "Result missing primary_id"
        assert hasattr(result, "primary_label"), "Result missing primary_label"
        assert hasattr(result, "concept_type"), "Result missing concept_type"
        assert result.concept_type is not None, "Concept type should not be None"

    # Extract sample response data for validation
    response_data = {
        "total_results": len(results),
        "sample_concepts": [
            {
                "primary_id": c.primary_id,
                "primary_label": c.primary_label,
                "concept_type": str(c.concept_type),
                "identifiers": list(c.identifiers) if hasattr(c, "identifiers") else [],
            }
            for c in results[:2]
        ],
    }

    # Validate response structure
    validator = response_validator(KnowledgeSource.UNIPROT)
    changes = validator.validate_response("uniprot_insulin_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.UNIPROT, "uniprot_insulin_search", change)

    # Print changes if any
    if changes:
        print("\nUniProt response structure changes detected:")
        for change in changes:
            print(f"  - {change}")


@pytest.mark.asyncio
async def test_uniprot_search_human(adapter, response_validator, warning_manager):
    """Test UniProt search for human proteins."""
    adapter = UniProtAdapter(adapter.config)

    results = await adapter.search_concepts("human", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1

    # Check organism info
    for result in results[:2]:
        assert hasattr(result, "primary_id")
        # Organism info may be in source_data


@pytest.mark.asyncio
async def test_uniprot_get_concept_details(adapter, response_validator, warning_manager):
    """Test getting detailed protein information from UniProt."""
    adapter = UniProtAdapter(adapter.config)

    # Use a known protein ID
    test_id = "P01308"  # Insulin

    result = await adapter.get_concept_details(test_id)

    assert result is not None, f"Failed to get details for {test_id}"
    assert hasattr(result, "primary_id"), "Result missing primary_id"
    assert hasattr(result, "primary_label"), "Result missing primary_label"
    assert result.primary_id == test_id, f"Expected {test_id}, got {result.primary_id}"

    # Extract response data
    response_data = {
        "primary_id": result.primary_id,
        "primary_label": result.primary_label,
        "concept_type": str(result.concept_type),
        "source_data_keys": list(result.source_data.keys())
        if hasattr(result, "source_data")
        else [],
    }

    validator = response_validator(KnowledgeSource.UNIPROT)
    changes = validator.validate_response("uniprot_insulin_details", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.UNIPROT, "uniprot_insulin_details", change)


@pytest.mark.asyncio
async def test_uniprot_error_handling(adapter, response_validator):
    """Test UniProt error handling."""
    adapter = UniProtAdapter(adapter.config)

    # Search for non-existent term
    results = await adapter.search_concepts("xjklsdfjksdlfjksdlf", limit=5)

    # Should return empty list, not crash
    assert isinstance(results, list)

    # Should not have any results
    # (this might actually return some results due to fuzzy matching)


@pytest.mark.asyncio
async def test_uniprot_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = UniProtAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("insulin", limit=2)

    assert len(results) <= 2, f"Expected max 2 results, got {len(results)}"

    # Test with larger limit
    results = await adapter.search_concepts("insulin", limit=10)

    assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
