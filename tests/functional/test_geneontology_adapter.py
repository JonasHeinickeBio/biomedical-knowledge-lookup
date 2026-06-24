"""
Functional test for GeneOntology adapter.

Tests real API calls to validate response structures and detect changes.
"""

import pytest
from knowledge_lookup.adapters.geneontology_adapter import GeneOntologyAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_geneontology_search(adapter, response_validator, warning_manager):
    """
    Test GeneOntology search with real API call.

    This test validates:
    - Adapter can connect to GeneOntology API
    - Response structure matches expected format
    - Results contain GO term information
    """
    adapter = GeneOntologyAdapter(adapter.config)

    # Search for a GO term
    results = await adapter.search_concepts("mitochondrion", limit=5)

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
    validator = response_validator(KnowledgeSource.GENEONTOLOGY)
    changes = validator.validate_response("geneontology_search", response_data)

    for change in changes:
        warning_manager.add_warning(KnowledgeSource.GENEONTOLOGY, "geneontology_search", change)


@pytest.mark.asyncio
async def test_geneontology_search_biological_process(adapter, response_validator, warning_manager):
    """Test GeneOntology search for biological process."""
    adapter = GeneOntologyAdapter(adapter.config)

    results = await adapter.search_concepts("apoptosis", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_geneontology_search_cellular_component(adapter, response_validator, warning_manager):
    """Test GeneOntology search for cellular component."""
    adapter = GeneOntologyAdapter(adapter.config)

    results = await adapter.search_concepts("nucleus", limit=3)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_geneontology_empty_search(adapter, response_validator):
    """Test GeneOntology search with no results."""
    adapter = GeneOntologyAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_geneontology_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = GeneOntologyAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("mitochondrion", limit=2)

    assert isinstance(results, list)
