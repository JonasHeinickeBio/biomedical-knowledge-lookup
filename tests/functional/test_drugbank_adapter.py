"""
Functional test for DrugBank adapter.

Tests real API calls to validate response structures and detect changes.
DrugBank records are served keyless by MyChem.info, so no API key is needed.
"""

import pytest

from knowledge_lookup.adapters.drugbank_adapter import DrugBankAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource

pytestmark = [pytest.mark.functional, pytest.mark.network, pytest.mark.api]


@pytest.mark.asyncio
async def test_drugbank_search_aspirin(adapter, response_validator, warning_manager):
    """
    Test DrugBank search for aspirin with real API call.

    This test validates:
    - Adapter can connect to MyChem.info
    - Response structure matches expected format
    - Results contain drug information
    """
    adapter = DrugBankAdapter(adapter.config)

    # Search for aspirin
    results = await adapter.search_concepts("aspirin", limit=5)

    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    assert "DB00945" in [r.primary_id for r in results]

    # Check that results have expected structure
    for result in results[:3]:
        assert result.primary_id.startswith("DB"), "Expected a DrugBank ID"
        assert result.primary_label, "Result missing primary_label"
        assert result.concept_type == ConceptType.DRUG

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
async def test_drugbank_search_metformin(adapter, response_validator, warning_manager):
    """Test DrugBank search for metformin."""
    adapter = DrugBankAdapter(adapter.config)

    results = await adapter.search_concepts("metformin", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_drugbank_search_insulin(adapter, response_validator, warning_manager):
    """Test DrugBank search for insulin."""
    adapter = DrugBankAdapter(adapter.config)

    results = await adapter.search_concepts("insulin", limit=3)

    assert isinstance(results, list)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_drugbank_get_concept_details(adapter):
    """Test DrugBank details for a known DrugBank ID."""
    adapter = DrugBankAdapter(adapter.config)

    details = await adapter.get_concept_details("DB00945")

    assert details is not None
    assert details.primary_id == "DB00945"
    assert details.primary_label == "Acetylsalicylic acid"
    assert details.identifiers[0].url == "https://go.drugbank.com/drugs/DB00945"


@pytest.mark.asyncio
async def test_drugbank_empty_search(adapter, response_validator):
    """Test DrugBank search with no results."""
    adapter = DrugBankAdapter(adapter.config)

    # Search for something very unlikely to exist
    results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj", limit=5)

    assert results == []


@pytest.mark.asyncio
async def test_drugbank_limit_parameter(adapter, response_validator):
    """Test that limit parameter works correctly."""
    adapter = DrugBankAdapter(adapter.config)

    # Test with small limit
    results = await adapter.search_concepts("aspirin", limit=2)

    assert len(results) <= 2, f"Expected max 2 results, got {len(results)}"

    # Test with larger limit
    results = await adapter.search_concepts("aspirin", limit=10)

    assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
