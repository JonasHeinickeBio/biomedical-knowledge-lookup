"""
Unit tests for OpenTargetsAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.opentargets_adapter import OpenTargetsAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestOpenTargetsAdapter:
    """Tests for OpenTargetsAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OpenTargetsAdapter instance."""
        return OpenTargetsAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OpenTargetsAdapter initialization."""
        adapter = OpenTargetsAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OPENTARGETS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OPENTARGETS

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
        config = LookupConfig(rate_limits={KnowledgeSource.OPENTARGETS: 5.0})
        adapter = OpenTargetsAdapter(config)
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
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_search_concepts_http_error(self, mock_make_request, adapter):
        """Test search concepts with HTTP error."""
        mock_make_request.side_effect = Exception("HTTP error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_search_concepts_network_error(self, mock_make_request, adapter):
        """Test search concepts with network error."""
        mock_make_request.side_effect = Exception("Network error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

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

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_get_concept_details_disease(self, mock_make_request, adapter):
        """Test get_concept_details for disease entity type (EFO_ prefix)."""
        mock_make_request.return_value = {
            "data": {
                "disease": {
                    "id": "EFO_0000616",
                    "name": "type 2 diabetes mellitus",
                    "definition": "A chronic metabolic disease.",
                }
            }
        }
        result = await adapter.get_concept_details("EFO_0000616")
        assert result is not None
        assert result.primary_id == "EFO_0000616"
        assert result.primary_label == "type 2 diabetes mellitus"

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_get_concept_details_target(self, mock_make_request, adapter):
        """Test get_concept_details for target entity type (ENSG prefix)."""
        mock_make_request.return_value = {
            "data": {
                "target": {
                    "id": "ENSG00000169318",
                    "approvedSymbol": "TP53",
                    "biotype": "protein_coding",
                }
            }
        }
        result = await adapter.get_concept_details("ENSG00000169318")
        assert result is not None
        assert result.primary_id == "ENSG00000169318"
        assert result.primary_label == "TP53"

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_get_concept_details_mondo_prefix(self, mock_make_request, adapter):
        """Test get_concept_details for MONDO_ prefix (disease)."""
        mock_make_request.return_value = {
            "data": {
                "disease": {
                    "id": "MONDO_0005180",
                    "name": "Alzheimer disease",
                    "definition": "A neurodegenerative disease.",
                }
            }
        }
        result = await adapter.get_concept_details("MONDO_0005180")
        assert result is not None
        assert result.primary_label == "Alzheimer disease"

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_get_concept_details_orpha_prefix(self, mock_make_request, adapter):
        """Test get_concept_details for ORPHA prefix (disease)."""
        mock_make_request.return_value = {
            "data": {
                "disease": {
                    "id": "ORPHA:99835",
                    "name": "Rare disease",
                }
            }
        }
        result = await adapter.get_concept_details("ORPHA:99835")
        assert result is not None

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_get_concept_details_no_data(self, mock_make_request, adapter):
        """Test get_concept_details when data is empty."""
        mock_make_request.return_value = {"data": {}}
        result = await adapter.get_concept_details("EFO_9999999")
        assert result is None

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_get_concept_details_error(self, mock_make_request, adapter):
        """Test get_concept_details with error."""
        mock_make_request.side_effect = Exception("API error")
        result = await adapter.get_concept_details("EFO_0000616")
        assert result is None

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_search_concepts_with_hits(self, mock_make_request, adapter):
        """Test search with actual hits returned."""
        mock_make_request.return_value = {
            "data": {
                "search": {
                    "hits": [
                        {
                            "id": "ENSG00000169318",
                            "name": "TP53",
                            "entity": "target",
                            "description": "Tumor protein p53",
                        },
                        {
                            "id": "EFO_0000616",
                            "name": "type 2 diabetes",
                            "entity": "disease",
                            "description": "A metabolic disease",
                        },
                    ]
                }
            }
        }
        results = await adapter.search_concepts("cancer", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_convert_result_disease_with_definition(self, mock_make_request, adapter):
        """Test _convert result for disease with definition."""
        concept = adapter._convert_opentargets_result_to_concept(
            {
                "id": "EFO_0000616",
                "name": "diabetes",
                "definition": "A metabolic disease",
            },
            entity_type="disease",
        )
        assert concept is not None
        assert concept.primary_label == "diabetes"
        assert "A metabolic disease" in concept.definitions

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_convert_result_target_with_biotype(self, mock_make_request, adapter):
        """Test _convert result for target with biotype."""
        concept = adapter._convert_opentargets_result_to_concept(
            {
                "id": "ENSG00000169318",
                "approvedSymbol": "TP53",
                "biotype": "protein_coding",
            },
            entity_type="target",
        )
        assert concept is not None
        assert concept.primary_label == "TP53"
        assert any("protein_coding" in d for d in concept.definitions)

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request")
    async def test_convert_result_without_entity_type(self, mock_make_request, adapter):
        """Test _convert result without entity_type (defaults to target)."""
        concept = adapter._convert_opentargets_result_to_concept(
            {"id": "ENSG00000169318", "approvedSymbol": "TP53"}
        )
        assert concept is not None
        assert concept.concept_type.value == "gene"
