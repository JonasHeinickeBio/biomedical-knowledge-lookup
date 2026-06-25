"""
Functional test for OpenTargets adapter.

Tests real API calls to validate response structures and detect changes.
OpenTargets API is now free to use without authentication.
"""

import pytest
from knowledge_lookup.adapters.opentargets_adapter import OpenTargetsAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.api]


@pytest.mark.asyncio
async def test_opentargets_search_diabetes(adapter, response_validator, warning_manager):
    """
    Test OpenTargets search for diabetes with real API call.

    This test validates:
    - Adapter can connect to OpenTargets API
    - Response structure matches expected format
    - Results contain target-disease associations
    """
    # OpenTargets API is now free - no API key required
    adapter = OpenTargetsAdapter(adapter.config)

    # Search for diabetes
    results = await adapter.search_concepts("diabetes", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
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
                "primary_id": r.primary_id,
                "primary_label": r.primary_label,
                "concept_type": r.concept_type,
            }
            for r in results[:3]
        ],
    }

    # Validate against fixture
    validator = response_validator(KnowledgeSource.OPENTARGETS)
    changes = validator.validate_response("search_diabetes", response_data)

    # Report any changes as warnings (don't fail)
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.OPENTARGETS, "search_diabetes", change)

    warning_manager.print_warnings()


@pytest.mark.asyncio
async def test_opentargets_search_gene(adapter, response_validator, warning_manager):
    """
    Test OpenTargets search for a gene with real API call.

    This test validates:
    - Adapter can search for gene concepts
    - Response structure is consistent
    """
    adapter = OpenTargetsAdapter(adapter.config)

    # Search for a gene
    results = await adapter.search_concepts("BRCA1", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"

    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, "primary_id"), "Result missing primary_id"
        assert hasattr(result, "primary_label"), "Result missing primary_label"

    # Extract sample response data
    response_data = {
        "total_results": len(results),
        "sample_concepts": [
            {
                "primary_id": r.primary_id,
                "primary_label": r.primary_label,
            }
            for r in results[:3]
        ],
    }

    # Validate against fixture
    validator = response_validator(KnowledgeSource.OPENTARGETS)
    changes = validator.validate_response("search_gene", response_data)

    # Report any changes as warnings
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.OPENTARGETS, "search_gene", change)

    warning_manager.print_warnings()


@pytest.mark.asyncio
async def test_opentargets_search_cancer(adapter, response_validator, warning_manager):
    """
    Test OpenTargets search for cancer with real API call.

    This test validates:
    - Adapter can search for disease concepts
    - Response structure is consistent
    """
    adapter = OpenTargetsAdapter(adapter.config)

    # Search for cancer
    results = await adapter.search_concepts("cancer", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
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
                "primary_id": r.primary_id,
                "primary_label": r.primary_label,
                "concept_type": r.concept_type,
            }
            for r in results[:3]
        ],
    }

    # Validate against fixture
    validator = response_validator(KnowledgeSource.OPENTARGETS)
    changes = validator.validate_response("search_cancer", response_data)

    # Report any changes as warnings
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.OPENTARGETS, "search_cancer", change)

    warning_manager.print_warnings()


@pytest.mark.asyncio
async def test_opentargets_get_concept_details(adapter, response_validator, warning_manager):
    """
    Test OpenTargets get concept details with real API call.

    This test validates:
    - Adapter can retrieve detailed concept information
    - Response structure is consistent
    """
    adapter = OpenTargetsAdapter(adapter.config)

    # Get details for a known target
    results = await adapter.search_concepts("ENSG00000139618", limit=1)

    # Skip if no results returned
    if len(results) == 0:
        pytest.skip("No search results to get details for")

    target_id = results[0].primary_id

    # Get details for this target
    details = await adapter.get_concept_details(target_id)

    # Skip if details not available (API may have issues)
    if details is None:
        pytest.skip("get_concept_details returned None")

    # Validate details
    assert hasattr(details, "primary_id"), "Details missing primary_id"

    # Extract sample response data
    response_data = {
        "primary_id": details.primary_id,
        "primary_label": details.primary_label,
        "concept_type": details.concept_type,
    }

    # Validate against fixture
    validator = response_validator(KnowledgeSource.OPENTARGETS)
    changes = validator.validate_response("get_details", response_data)

    # Report any changes as warnings
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.OPENTARGETS, "get_details", change)

    warning_manager.print_warnings()


@pytest.mark.asyncio
async def test_opentargets_with_limit(adapter, response_validator, warning_manager):
    """
    Test OpenTargets search with limit parameter.

    This test validates:
    - Limit parameter works correctly
    - Response structure is consistent with limited results
    """
    adapter = OpenTargetsAdapter(adapter.config)

    # Search with limit
    results = await adapter.search_concepts("diabetes", limit=3)

    # Validate limit
    assert len(results) <= 3, f"Expected at most 3 results, got {len(results)}"

    # Extract sample response data
    response_data = {
        "total_results": len(results),
        "sample_concepts": [
            {
                "primary_id": r.primary_id,
                "primary_label": r.primary_label,
            }
            for r in results
        ],
    }

    # Validate against fixture
    validator = response_validator(KnowledgeSource.OPENTARGETS)
    changes = validator.validate_response("search_with_limit", response_data)

    # Report any changes as warnings
    for change in changes:
        warning_manager.add_warning(KnowledgeSource.OPENTARGETS, "search_with_limit", change)

    warning_manager.print_warnings()
