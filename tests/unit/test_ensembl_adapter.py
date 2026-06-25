"""
Unit tests for EnsemblAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.ensembl_adapter import EnsemblAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestEnsemblAdapter:
    """Tests for EnsemblAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EnsemblAdapter instance."""
        return EnsemblAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test EnsemblAdapter initialization."""
        adapter = EnsemblAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.ENSEMBL
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.ENSEMBL

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
        config = LookupConfig(rate_limits={KnowledgeSource.ENSEMBL: 5.0})
        adapter = EnsemblAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts when API returns a list with items (lines 41-44)."""
        ensembl_data = [
            {
                "id": "ENSG00000139618",
                "display_name": "BRCA2",
                "description": "BRCA2 DNA repair associated",
                "biotype": "protein_coding",
                "species": "homo_sapiens",
            },
            {
                "id": "ENSG00000139617",
                "display_name": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "biotype": "protein_coding",
                "species": "homo_sapiens",
            },
        ]
        detail_data = {"id": "ENSG00000139618", "display_name": "BRCA2"}

        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ensembl_data
            with patch.object(
                adapter, "get_concept_details", new_callable=AsyncMock
            ) as mock_detail:
                mock_detail.return_value = MagicMock()
                results = await adapter.search_concepts("BRCA2", limit=2)
                assert len(results) == 2
                assert mock_detail.call_count == 2

    @pytest.mark.asyncio
    async def test_search_concepts_concept_details_returns_none(self, adapter):
        """Test search when get_concept_details returns None for some results."""
        ensembl_data = [
            {"id": "ENSG00000139618"},
            {"id": "INVALID"},
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ensembl_data
            with patch.object(
                adapter, "get_concept_details", new_callable=AsyncMock
            ) as mock_detail:
                mock_detail.side_effect = [MagicMock(), None]
                results = await adapter.search_concepts("test", limit=10)
                assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_concepts_non_list_data(self, adapter):
        """Test search when API returns non-list data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"error": "bad query"}
            results = await adapter.search_concepts("bad query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_empty_list(self, adapter):
        """Test search when API returns empty list."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            results = await adapter.search_concepts("nonexistent")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            results = await adapter.search_concepts("test")
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter):
        """Test successful get_concept_details (lines 63-64)."""
        data = {"id": "ENSG00000139618", "display_name": "BRCA2"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is not None
            assert result.primary_id == "ENSG00000139618"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_id_in_data(self, adapter):
        """Test get_concept_details when data has no 'id' key."""
        data = {"display_name": "BRCA2"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling (lines 68-70)."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_data(self, adapter):
        """Test get_concept_details with empty data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_data_falsy(self, adapter):
        """Test get_concept_details when _make_request returns falsy data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    def test_convert_ensembl_result_to_concept_full(self, adapter):
        """Test _convert_ensembl_result_to_concept with all fields (lines 74-105)."""
        result = {
            "id": "ENSG00000139618",
            "display_name": "BRCA2",
            "description": "BRCA2 DNA repair associated",
            "biotype": "protein_coding",
            "species": "homo_sapiens",
        }
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "ENSG00000139618"
        assert concept.primary_label == "BRCA2"
        assert "BRCA2 DNA repair associated" in concept.definitions
        assert "Biotype: protein_coding" in concept.categories
        assert "Species: homo_sapiens" in concept.categories
        assert concept.confidence_score == 1.0

    def test_convert_ensembl_result_minimal(self, adapter):
        """Test _convert_ensembl_result_to_concept with minimal data."""
        result = {"id": "ENSG00000000001"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "ENSG00000000001"
        assert concept.primary_label == "ENSG00000000001"
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_ensembl_result_no_description_no_biotype(self, adapter):
        """Test conversion without optional fields."""
        result = {"id": "ENSG00000000001", "display_name": "GENE1"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_ensembl_result_with_description_no_biotype(self, adapter):
        """Test conversion with description but no biotype."""
        result = {"id": "ENSG00000000001", "display_name": "GENE1", "description": "A gene"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert "A gene" in concept.definitions
        assert len(concept.categories) == 0

    def test_convert_ensembl_result_with_biotype_no_description(self, adapter):
        """Test conversion with biotype but no description."""
        result = {"id": "ENSG00000000001", "display_name": "GENE1", "biotype": "lncRNA"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert "Biotype: lncRNA" in concept.categories

    def test_convert_ensembl_result_error(self, adapter):
        """Test _convert_ensembl_result_to_concept with bad data causing error."""
        result = {"id": None}
        concept = adapter._convert_ensembl_result_to_concept(result)

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
