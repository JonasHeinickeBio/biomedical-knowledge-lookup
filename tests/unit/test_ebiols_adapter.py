"""
Unit tests for EBIOLSAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.ebiols_adapter import EBIOLSAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestEBIOLSAdapter:
    """Tests for EBIOLSAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EBIOLSAdapter instance."""
        return EBIOLSAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test EBIOLSAdapter initialization."""
        adapter = EBIOLSAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.EBIOLS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.EBIOLS

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.EBIOLS: 5.0})
        adapter = EBIOLSAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})  # Mock response structure
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test query", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_http_error(self, mock_get, adapter):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_network_error(self, mock_get, adapter):
        """Test search concepts with network error."""
        mock_get.side_effect = Exception("Network error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_records_identifiers_under_ebiols(self, adapter):
        """Regression: identifiers and source_data are recorded under EBIOLS, not OLS."""
        # Shaped like a real OLS4 /api/search response
        ols4_search = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "iri": "http://purl.obolibrary.org/obo/MONDO_0004992",
                        "label": "cancer",
                        "ontology_name": "mondo",
                        "ontology_prefix": "MONDO",
                        "short_form": "MONDO_0004992",
                        "obo_id": "MONDO:0004992",
                        "description": ["A tumor composed of atypical neoplastic cells."],
                        "type": "class",
                    }
                ],
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ols4_search
            results = await adapter.search_concepts("cancer", limit=1)

        assert len(results) == 1
        concept = results[0]
        assert [i.source for i in concept.identifiers] == [
            KnowledgeSource.EBIOLS,
            KnowledgeSource.EBIOLS,
        ]
        assert KnowledgeSource.EBIOLS in concept.source_data
        assert KnowledgeSource.OLS not in concept.source_data

    @pytest.mark.asyncio
    async def test_details_records_identifiers_under_ebiols(self, adapter):
        """Regression: concept details are recorded under EBIOLS, not OLS."""
        ols4_terms = {
            "_embedded": {
                "terms": [
                    {
                        "iri": "http://purl.obolibrary.org/obo/HP_0001250",
                        "label": "Seizure",
                        "synonyms": ["Epileptic seizure"],
                        "description": ["A seizure is an intermittent abnormality."],
                        "obo_xref": [{"database": "UMLS", "id": "C0036572"}],
                    }
                ]
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ols4_terms
            concept = await adapter.get_concept_details(
                "http://purl.obolibrary.org/obo/HP_0001250"
            )

        assert concept is not None
        assert {i.source for i in concept.identifiers} == {KnowledgeSource.EBIOLS}
        assert KnowledgeSource.EBIOLS in concept.source_data
        assert KnowledgeSource.OLS not in concept.source_data

    def test_plain_ols_adapter_still_uses_ols(self, lookup_config):
        """The re-tagging must not leak into the parent OLS adapter."""
        from knowledge_lookup.adapters.ols_adapter import OLSAdapter

        concept = OLSAdapter(lookup_config)._convert_ols_result_to_concept(
            {"iri": "http://purl.obolibrary.org/obo/DOID_162", "label": "cancer"}
        )
        assert concept is not None
        assert concept.identifiers[0].source == KnowledgeSource.OLS

    def test_tagging_is_inherited_not_overridden(self):
        """Regression: the OLS converters tag with get_source(), so EBIOLS needs no override."""
        from knowledge_lookup.adapters.ols_adapter import OLSAdapter

        assert (
            EBIOLSAdapter._convert_ols_result_to_concept
            is OLSAdapter._convert_ols_result_to_concept
        )
        assert (
            EBIOLSAdapter._convert_ols_concept_to_unified
            is OLSAdapter._convert_ols_concept_to_unified
        )
        assert not hasattr(EBIOLSAdapter, "_retag_as_ebiols")

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
