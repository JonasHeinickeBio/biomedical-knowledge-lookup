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
    async def test_search_concepts_exact_symbol_match(self, adapter):
        """An exact gene symbol resolves via lookup/symbol in one request,
        without falling back to xrefs/symbol."""
        data = {"id": "ENSG00000012048", "display_name": "BRCA1"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            results = await adapter.search_concepts("BRCA1", limit=10)

        assert len(results) == 1
        assert results[0].primary_id == "ENSG00000012048"
        mock_req.assert_awaited_once()
        url = mock_req.call_args.args[0]
        assert url.endswith("/lookup/symbol/homo_sapiens/BRCA1")

    @pytest.mark.asyncio
    async def test_lookup_by_symbol_returns_concept(self, adapter):
        data = {"id": "ENSG00000012048", "display_name": "BRCA1"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            concept = await adapter._lookup_by_symbol("BRCA1")
        assert concept is not None
        assert concept.primary_id == "ENSG00000012048"

    @pytest.mark.asyncio
    async def test_lookup_by_symbol_no_id_returns_none(self, adapter):
        """A non-dict (e.g. the xrefs list shape) or missing-id response means
        no exact match — the caller should fall back to xrefs/symbol."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [{"id": "ENSG00000012048"}]
            assert await adapter._lookup_by_symbol("BRCA1") is None

    @pytest.mark.asyncio
    async def test_lookup_by_symbol_error_returns_none(self, adapter):
        """A 400 (no match) or any other failure degrades to None, not an exception."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("400 no valid lookup found")
            assert await adapter._lookup_by_symbol("p53") is None

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts falls back to xrefs/symbol when lookup/symbol
        finds no exact match, expanding each xref via get_concept_details."""
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
        adapter._convert_ensembl_result_to_concept(result)

    @pytest.mark.asyncio
    async def test_get_relationships_returns_ortholog_edges(self, adapter):
        """get_relationships exposes homology/id orthologs as edge dicts (same
        shape as KEGG/STRING/WikiPathways)."""
        homology_data = {
            "data": [
                {
                    "id": "ENSG00000012048",
                    "homologies": [
                        {
                            "type": "ortholog_one2one",
                            "target": {"id": "ENSMUSG00000017146", "species": "mus_musculus"},
                        },
                        {
                            "type": "ortholog_one2many",
                            "target": {"id": "ENSPTRG00000009123", "species": "pan_troglodytes"},
                        },
                    ],
                }
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = homology_data
            rels = await adapter.get_relationships("ENSG00000012048", limit=5)

        url, params = mock_req.call_args.args
        assert url.endswith("/homology/id/homo_sapiens/ENSG00000012048")
        assert params["type"] == "orthologues"
        assert [r["related_id"] for r in rels] == ["ENSMUSG00000017146", "ENSPTRG00000009123"]
        assert all(r["relation_label"] == "ortholog" for r in rels)
        assert all(r["source"] == "Ensembl" for r in rels)
        assert rels[0]["species"] == "mus_musculus"
        assert rels[0]["homology_type"] == "ortholog_one2one"

    @pytest.mark.asyncio
    async def test_get_relationships_respects_limit(self, adapter):
        homology_data = {
            "data": [
                {
                    "homologies": [
                        {"target": {"id": f"ENSG{i}", "species": "x"}} for i in range(5)
                    ]
                }
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = homology_data
            rels = await adapter.get_relationships("ENSG00000012048", limit=2)
        assert len(rels) == 2

    @pytest.mark.asyncio
    async def test_get_relationships_empty_on_no_data(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"data": []}
            assert await adapter.get_relationships("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_relationships_degrades_on_error(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("network down")
            assert await adapter.get_relationships("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_relationships_blank_id_returns_empty(self, adapter):
        assert await adapter.get_relationships("   ") == []

    @pytest.mark.asyncio
    async def test_get_mappings_returns_xref_mappings(self, adapter):
        """get_mappings exposes xrefs/id cross-references as mapping dicts
        (same shape as KEGGAdapter.get_mappings)."""
        xrefs_data = [
            {"dbname": "HGNC", "primary_id": "HGNC:1100", "display_id": "BRCA1"},
            {"dbname": "ArrayExpress", "primary_id": "ENSG00000012048", "display_id": "BRCA1"},
            {"dbname": "", "primary_id": "should-be-skipped"},
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = xrefs_data
            mappings = await adapter.get_mappings("ENSG00000012048")

        url = mock_req.call_args.args[0]
        assert url.endswith("/xrefs/id/ENSG00000012048")
        assert len(mappings) == 2
        assert mappings[0] == {
            "fromId": "ENSG00000012048",
            "toId": "HGNC:1100",
            "fromSource": "Ensembl",
            "toSource": "HGNC",
            "mappingType": "xref",
            "confidence": 0.9,
        }

    @pytest.mark.asyncio
    async def test_get_mappings_empty_on_non_list(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"error": "boom"}
            assert await adapter.get_mappings("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_mappings_degrades_on_error(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("network down")
            assert await adapter.get_mappings("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_mappings_blank_id_returns_empty(self, adapter):
        assert await adapter.get_mappings("   ") == []

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass
