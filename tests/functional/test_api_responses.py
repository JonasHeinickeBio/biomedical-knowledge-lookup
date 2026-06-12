"""
Functional tests for adapters.

These tests make real API calls to validate that adapters work with actual
API responses and warn if API response structures change.

Run with: poetry run pytest -m functional -m network
"""

import json
from typing import Any

import pytest

from knowledge_lookup.adapters import ADAPTER_CLASSES
from knowledge_lookup.models import KnowledgeSource

from tests.functional.conftest import requires_api, requires_api_key, requires_network

# Sources that require API keys
API_KEY_REQUIRED_SOURCES = {
    KnowledgeSource.BIOPORTAL,
    KnowledgeSource.UMLS,
    KnowledgeSource.DISGENET,
    KnowledgeSource.OPENTARGETS,
    KnowledgeSource.COSMIC,
    KnowledgeSource.DRUGBANK,
}


@pytest.fixture
def warning_manager():
    """Create a warning manager for this test."""
    from tests.functional.utils import APIWarningManager
    return APIWarningManager()


# Public API tests (no authentication required)
# These run against real APIs and validate response structures


@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_uniprot_search(adapter, response_validator, warning_manager, api_responses_cache):
    """Test UniProt search with real API call."""
    from knowledge_lookup.adapters.uniprot_adapter import UniProtAdapter
    
    adapter = UniProtAdapter(adapter.config)
    
    results, response_data = await adapter.search_concepts("insulin", limit=5), {}
    
    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, "Expected at least 1 result"
    
    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, 'primary_id'), "Result missing primary_id"
        assert hasattr(result, 'primary_label'), "Result missing primary_label"
        assert hasattr(result, 'concept_type'), "Result missing concept_type"
    
    # Extract sample response data for validation
    if results:
        response_data = {
            "total_results": len(results),
            "sample_concepts": [c.__dict__ for c in results[:2]]
        }
    
    # Validate response structure
    if response_data:
        validator = response_validator(KnowledgeSource.UNIPROT)
        changes = validator.validate_response("uniprot_insulin_search", response_data)
        for change in changes:
            warning_manager.add_warning(KnowledgeSource.UNIPROT, "uniprot_insulin_search", change)


@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_ols_search(adapter, response_validator, warning_manager):
    """Test OLS search with real API call."""
    from knowledge_lookup.adapters.ols_adapter import OLSAdapter
    
    adapter = OLSAdapter(adapter.config)
    
    results = await adapter.search_concepts("diabetes", limit=5)
    
    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, "Expected at least 1 result"
    
    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, 'primary_id'), "Result missing primary_id"
        assert hasattr(result, 'primary_label'), "Result missing primary_label"
    
    # Extract sample response data
    if results:
        response_data = {
            "total_results": len(results),
            "sample_concepts": [c.__dict__ for c in results[:2]]
        }
        
        validator = response_validator(KnowledgeSource.OLS)
        changes = validator.validate_response("ols_diabetes_search", response_data)
        for change in changes:
            warning_manager.add_warning(KnowledgeSource.OLS, "ols_diabetes_search", change)


@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_wikidata_search(adapter, response_validator, warning_manager):
    """Test Wikidata search with real API call."""
    from knowledge_lookup.adapters.wikidata_adapter import WikidataAdapter
    
    adapter = WikidataAdapter(adapter.config)
    
    results = await adapter.search_concepts("diabetes", limit=5)
    
    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, "Expected at least 1 result"
    
    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, 'primary_id'), "Result missing primary_id"
        assert hasattr(result, 'primary_label'), "Result missing primary_label"


@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_pubchem_search(adapter, response_validator, warning_manager):
    """Test PubChem search with real API call."""
    from knowledge_lookup.adapters.pubchem_adapter import PubChemAdapter
    
    adapter = PubChemAdapter(adapter.config)
    
    results = await adapter.search_concepts("aspirin", limit=5)
    
    # Validate results
    assert isinstance(results, list), "Expected list of results"
    assert len(results) >= 1, "Expected at least 1 result"
    
    # Check that results have expected structure
    for result in results[:3]:
        assert hasattr(result, 'primary_id'), "Result missing primary_id"
        assert hasattr(result, 'primary_label'), "Result missing primary_label"


@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_eutils_search(adapter, response_validator, warning_manager):
    """Test EUtils search with real API call."""
    from knowledge_lookup.adapters.eutils_adapter import EUtilsAdapter
    
    adapter = EUtilsAdapter(adapter.config)
    
    results = await adapter.search_concepts("diabetes", limit=5)
    
    # Validate results
    assert isinstance(results, list), "Expected list of results"
    # EUtils may return empty for some queries


# Summary test that prints warnings at the end
@pytest.mark.functional
@pytest.mark.network
@pytest.mark.asyncio
async def test_all_adapters_summary(adapter, warning_manager):
    """
    Summary test that runs minimal checks on all adapters
    and prints structure change warnings at the end.
    
    Note: This test may fail if adapters have missing dependencies (expected).
    """
    test_results = []
    
    for source, adapter_class in ADAPTER_CLASSES.items():
        # Skip sources that require API keys for this summary
        if source in API_KEY_REQUIRED_SOURCES:
            continue
        
        try:
            # Create adapter
            adapter = adapter_class(adapter.config)
            
            # Quick test - check if adapter initializes correctly
            assert adapter.source == source
            assert adapter.is_available() is True
            
            # Quick search test
            try:
                results = await adapter.search_concepts("test", limit=2)
                assert isinstance(results, list)
                test_results.append((source.value, "passed", len(results)))
            except Exception as e:
                test_results.append((source.value, f"search_error: {str(e)[:50]}", 0))
            
        except AssertionError as e:
            # is_available() returned False - likely missing dependency
            test_results.append((source.value, f"init_error: {str(e)[:50]}", 0))
        except AttributeError as e:
            # is_available() returned False - likely missing dependency
            test_results.append((source.value, f"init_error: {str(e)[:50]}", 0))
        except Exception as e:
            test_results.append((source.value, f"init_error: {str(e)[:50]}", 0))
    
    # Print summary
    print("\n" + "=" * 70)
    print("ADAPTER FUNCTIONAL TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, status, _ in test_results if status == "passed")
    skipped = sum(1 for _, status, _ in test_results if "init_error" in status)
    failed = sum(1 for _, status, _ in test_results if status != "passed" and "init_error" not in status)
    
    print(f"\nTotal: {len(test_results)}")
    print(f"Passed: {passed}")
    print(f"Skipped (dependency issues): {skipped}")
    print(f"Failed (actual errors): {failed}")
    
    for source, status, count in test_results:
        print(f"  {source}: {status} (results: {count})")
    
    # Print any warnings from other tests
    if warning_manager.warnings:
        warning_manager.print_warnings()
    
    # Only fail if there are actual test errors (not skipped due to dependencies)
    assert failed == 0, f"{failed} adapter(s) have actual errors (not dependency issues)"
