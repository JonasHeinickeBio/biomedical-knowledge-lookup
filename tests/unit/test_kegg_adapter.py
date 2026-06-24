"""
Unit tests for KEGGAdapter.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

mock_bioservices = MagicMock()
sys.modules["bioservices"] = mock_bioservices

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.kegg_adapter import KEGGAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestKEGGAdapter:
    """Tests for KEGGAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create KEGGAdapter instance."""
        return KEGGAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test KEGGAdapter initialization."""
        adapter = KEGGAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.KEGG
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.KEGG

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
        config = LookupConfig(rate_limits={KnowledgeSource.KEGG: 5.0})
        adapter = KEGGAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_disease_results(self, adapter):
        """Test search_concepts with disease results."""
        ds_text = "ds:H00001\tDiabetes mellitus; a metabolic disease\nds:H00002\tType 2 diabetes; a chronic disease"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [ds_text, ""]
            results = await adapter.search_concepts("diabetes", limit=10)
            assert len(results) == 2
            assert results[0].primary_id == "H00001"
            assert results[0].primary_label == "Diabetes mellitus"

    @pytest.mark.asyncio
    async def test_search_concepts_drug_results(self, adapter):
        """Test search_concepts with drug results."""
        dr_text = "dr:D00001\tAspirin; a pain reliever"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = ["", dr_text]
            results = await adapter.search_concepts("aspirin", limit=10)
            assert len(results) == 1
            assert results[0].primary_id == "D00001"

    @pytest.mark.asyncio
    async def test_search_concepts_both_disease_and_drug(self, adapter):
        """Test search with both disease and drug results."""
        ds_text = "ds:H00001\tDiabetes mellitus; a metabolic disease"
        dr_text = "dr:D00001\tMetformin; a diabetes drug"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [ds_text, dr_text]
            results = await adapter.search_concepts("diabetes", limit=10)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_empty_response(self, adapter):
        """Test search with empty response."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = ["", ""]
            results = await adapter.search_concepts("nonexistent", limit=10)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_disease_malformed_lines(self, adapter):
        """Test search with malformed lines (no tab separator)."""
        ds_text = "bad_line_no_tab\nanother_bad_line"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [ds_text, ""]
            results = await adapter.search_concepts("test", limit=10)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_error(self, adapter):
        """Test search error handling."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            results = await adapter.search_concepts("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_get_concept_details_disease(self, adapter):
        """Test get_concept_details for disease."""
        kegg_text = "ENTRY       H00001\nNAME        Diabetes mellitus\nDESCRIPTION A metabolic disease"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = kegg_text
            result = await adapter.get_concept_details("H00001")
            assert result is not None
            assert result.primary_id == "H00001"
            assert result.primary_label == "Diabetes mellitus"

    @pytest.mark.asyncio
    async def test_get_concept_details_drug(self, adapter):
        """Test get_concept_details for drug."""
        kegg_text = "ENTRY       D00001\nNAME        Aspirin\nDESCRIPTION Pain reliever"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = kegg_text
            result = await adapter.get_concept_details("D00001")
            assert result is not None
            assert result.primary_id == "D00001"

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("H00001")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_response(self, adapter):
        """Test get_concept_details with empty response."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ""
            result = await adapter.get_concept_details("H00001")
            assert result is None

    def test_parse_kegg_text_disease(self, adapter):
        """Test _parse_kegg_text for disease."""
        text = "ENTRY       H00001\nNAME        Diabetes mellitus\nDESCRIPTION A metabolic disease"
        concept = adapter._parse_kegg_text("H00001", text)
        assert concept is not None
        assert concept.primary_id == "H00001"
        assert concept.primary_label == "Diabetes mellitus"
        assert "A metabolic disease" in concept.definitions
        assert concept.confidence_score == 1.0

    def test_parse_kegg_text_drug(self, adapter):
        """Test _parse_kegg_text for drug."""
        text = "ENTRY       D00001\nNAME        Aspirin\nDESCRIPTION Pain reliever"
        concept = adapter._parse_kegg_text("D00001", text)
        assert concept is not None
        assert concept.primary_id == "D00001"
        assert concept.primary_label == "Aspirin"
        assert "Pain reliever" in concept.definitions

    def test_parse_kegg_text_no_name(self, adapter):
        """Test _parse_kegg_text when no NAME line."""
        text = "ENTRY       H00001\nDESCRIPTION A metabolic disease"
        concept = adapter._parse_kegg_text("H00001", text)
        assert concept is not None
        assert concept.primary_label == "H00001"

    def test_parse_kegg_text_no_description(self, adapter):
        """Test _parse_kegg_text with no description."""
        text = "ENTRY       H00001\nNAME        Diabetes mellitus"
        concept = adapter._parse_kegg_text("H00001", text)
        assert concept is not None
        assert len(concept.definitions) == 0

    def test_parse_kegg_text_unknown_type(self, adapter):
        """Test _parse_kegg_text with unknown prefix."""
        text = "ENTRY       X00001\nNAME        Unknown"
        concept = adapter._parse_kegg_text("X00001", text)
        assert concept is not None
        assert concept.concept_type == "UNKNOWN"

    def test_parse_kegg_text_error(self, adapter):
        """Test _parse_kegg_text error handling."""
        concept = adapter._parse_kegg_text("H00001", None)
        assert concept is None

    def test_parse_kegg_text_multiline_name(self, adapter):
        """Test _parse_kegg_text with NAME line containing semicolons."""
        text = "ENTRY       H00001\nNAME        Diabetes mellitus; Type 2; Chronic"
        concept = adapter._parse_kegg_text("H00001", text)
        assert concept is not None
        assert concept.primary_label == "Diabetes mellitus"

    @pytest.mark.asyncio
    async def test_search_concepts_line_with_single_part(self, adapter):
        """Test search when a line splits into only 1 part (no tab)."""
        ds_text = "ds:H00001"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [ds_text, ""]
            results = await adapter.search_concepts("test", limit=10)
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
            pass
