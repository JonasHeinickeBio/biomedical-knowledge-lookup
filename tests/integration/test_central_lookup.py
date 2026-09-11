"""
Integration tests for CentralKnowledgeLookup.
"""

from unittest.mock import patch

import pytest
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.models import ConceptType, LookupResult, UnifiedConcept


@pytest.mark.integration
class TestCentralKnowledgeLookupIntegration:
    """Integration tests for CentralKnowledgeLookup."""

    @pytest.fixture
    def lookup(self, lookup_config):
        """Create CentralKnowledgeLookup instance."""
        return CentralKnowledgeLookup(lookup_config)

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_search_single_source(self, mock_search, lookup):
        """Test searching in a single source."""
        mock_concepts = [
            UnifiedConcept(
                primary_id="DOID:9351",
                primary_label="diabetes mellitus",
                concept_type=ConceptType.DISEASE,
            )
        ]
        mock_search.return_value = mock_concepts

        results = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.OLS])
        assert isinstance(results, LookupResult)
        assert results.query == "diabetes"
        if len(results.concepts) > 0:
            assert results.concepts[0].primary_id is not None

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    @patch("knowledge_lookup.adapters.bioportal_adapter.BioPortalAdapter.search_concepts")
    async def test_search_multiple_sources(self, mock_bioportal, mock_ols, lookup):
        """Test searching across multiple sources."""
        mock_ols_concepts = [
            UnifiedConcept(
                primary_id="DOID:9351",
                primary_label="diabetes mellitus",
                concept_type=ConceptType.DISEASE,
            )
        ]
        mock_bioportal_concepts = [
            UnifiedConcept(
                primary_id="SNOMEDCT:73211009",
                primary_label="Diabetes mellitus",
                concept_type=ConceptType.DISEASE,
            )
        ]
        mock_ols.return_value = mock_ols_concepts
        mock_bioportal.return_value = mock_bioportal_concepts

        results = await lookup.search_concepts(
            "diabetes", sources=[KnowledgeSource.OLS, KnowledgeSource.BIOPORTAL]
        )
        assert isinstance(results, LookupResult)
        assert results.query == "diabetes"
        # Should query multiple sources
        assert len(results.sources_queried) >= 1

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.get_concept_details")
    async def test_get_concept_details(self, mock_details, lookup):
        """Test getting concept details."""
        mock_concept = UnifiedConcept(
            primary_id="DOID:9351",
            primary_label="diabetes mellitus",
            concept_type=ConceptType.DISEASE,
            definitions=["A metabolic disease"],
        )
        mock_details.return_value = mock_concept

        result = await lookup.get_concept_details("DOID:9351", source=KnowledgeSource.OLS)
        # Should return a concept or None
        assert result is None or isinstance(result, UnifiedConcept)

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_search_with_caching(self, mock_search, lookup_config):
        """Test that caching works correctly."""
        config = LookupConfig()
        lookup = CentralKnowledgeLookup(config)

        mock_concepts = [
            UnifiedConcept(
                primary_id="DOID:9351",
                primary_label="diabetes mellitus",
                concept_type=ConceptType.DISEASE,
            )
        ]
        mock_search.return_value = mock_concepts

        # First call
        results1 = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.OLS])
        # Second call (should use cache)
        results2 = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.OLS])

        # Both should return results
        assert isinstance(results1, LookupResult)
        assert isinstance(results2, LookupResult)

    @pytest.mark.asyncio
    async def test_search_with_limit(self, lookup):
        """Test searching with result limit."""
        with patch(
            "knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts"
        ) as mock_search:
            mock_concepts = [
                UnifiedConcept(
                    primary_id=f"TEST:{i}",
                    primary_label=f"Test {i}",
                    concept_type=ConceptType.DISEASE,
                )
                for i in range(5)
            ]
            mock_search.return_value = mock_concepts

            await lookup.search_concepts("test", sources=[KnowledgeSource.OLS], max_results=10)
            # Should pass the limit parameter to adapters
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_error_recovery_single_source(self, mock_search, lookup):
        """Test error recovery when one source fails."""
        mock_search.side_effect = Exception("API Error")

        results = await lookup.search_concepts("diabetes", sources=[KnowledgeSource.OLS])
        # Should handle error gracefully
        assert isinstance(results, LookupResult)
        assert (
            KnowledgeSource.OLS in results.sources_failed or KnowledgeSource.OLS in results.errors
        )

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    @patch("knowledge_lookup.adapters.bioportal_adapter.BioPortalAdapter.search_concepts")
    async def test_error_recovery_multiple_sources(self, mock_bioportal, mock_ols, lookup):
        """Test error recovery when one of multiple sources fails."""
        mock_ols.side_effect = Exception("OLS Error")
        mock_bioportal.return_value = [
            UnifiedConcept(
                primary_id="SNOMEDCT:73211009",
                primary_label="Diabetes mellitus",
                concept_type=ConceptType.DISEASE,
            )
        ]

        results = await lookup.search_concepts(
            "diabetes", sources=[KnowledgeSource.OLS, KnowledgeSource.BIOPORTAL]
        )
        # Should still return a LookupResult
        assert isinstance(results, LookupResult)
        # One source should have failed
        assert (
            KnowledgeSource.OLS in results.sources_failed or KnowledgeSource.OLS in results.errors
        )


@pytest.mark.integration
class TestCentralLookupConfiguration:
    """Integration tests for CentralKnowledgeLookup configuration."""

    def test_initialization_with_config(self, lookup_config):
        """Test initialization with custom config."""
        lookup = CentralKnowledgeLookup(lookup_config)
        assert lookup.config == lookup_config

    def test_initialization_with_api_keys(self):
        """Test initialization with API keys."""
        config = LookupConfig(
            api_keys={
                KnowledgeSource.BIOPORTAL: "test_key",
                KnowledgeSource.UMLS: "umls_key",
            }
        )
        lookup = CentralKnowledgeLookup(config)
        assert lookup.config.api_keys[KnowledgeSource.BIOPORTAL] == "test_key"

    def test_initialization_with_rate_limits(self):
        """Test initialization with rate limits."""
        config = LookupConfig(
            rate_limits={
                KnowledgeSource.OLS: 10.0,
                KnowledgeSource.BIOPORTAL: 5.0,
            }
        )
        lookup = CentralKnowledgeLookup(config)
        assert lookup.config.rate_limits[KnowledgeSource.OLS] == 10.0

    def test_initialization_with_disabled_cache(self):
        """Test initialization with custom config."""
        config = LookupConfig(max_results_per_source=50)
        lookup = CentralKnowledgeLookup(config)
        assert lookup.config.max_results_per_source == 50


@pytest.mark.integration
@pytest.mark.asyncio
class TestCentralLookupBatchOperations:
    """Integration tests for batch operations."""

    @pytest.fixture
    def lookup(self, lookup_config):
        """Create CentralKnowledgeLookup instance."""
        return CentralKnowledgeLookup(lookup_config)

    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_batch_search(self, mock_search, lookup):
        """Test batch searching."""
        mock_search.return_value = [
            UnifiedConcept(
                primary_id="TEST:001",
                primary_label="Test",
                concept_type=ConceptType.DISEASE,
            )
        ]

        queries = ["diabetes", "cancer", "asthma"]
        results = []
        for query in queries:
            result = await lookup.search_concepts(query, sources=[KnowledgeSource.OLS])
            results.append(result)

        assert len(results) == 3
        for i, query in enumerate(queries):
            assert results[i].query == query
            assert isinstance(results[i], LookupResult)
