"""
Unit tests for UniProtAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.uniprot_adapter import UniProtAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestUniProtAdapter:
    """Tests for UniProtAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create UniProtAdapter instance."""
        return UniProtAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test UniProtAdapter initialization."""
        adapter = UniProtAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.UNIPROT
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.UNIPROT

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
        config = LookupConfig(rate_limits={KnowledgeSource.UNIPROT: 5.0})
        adapter = UniProtAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts with actual results (lines 40-42)."""
        uniprot_data = {
            "results": [
                {
                    "primaryAccession": "P04637",
                    "genes": [{"geneName": {"value": "TP53"}}],
                    "proteinDescription": {
                        "recommendedName": {"fullName": {"value": "Tumor protein p53"}}
                    },
                    "organism": {"scientificName": "Homo sapiens"},
                    "comments": [
                        {
                            "commentType": "FUNCTION",
                            "texts": [{"value": "Acts as a tumor suppressor"}],
                        }
                    ],
                }
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = uniprot_data
            results = await adapter.search_concepts("TP53", limit=10)
            assert len(results) == 1
            assert results[0].primary_id == "P04637"

    @pytest.mark.asyncio
    async def test_search_concepts_result_conversion_returns_none(self, adapter):
        """Test search when _convert_uniprot_result_to_concept returns None."""
        uniprot_data = {"results": [{"invalid": "data"}]}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = uniprot_data
            with patch.object(adapter, "_convert_uniprot_result_to_concept", return_value=None):
                results = await adapter.search_concepts("test")
                assert len(results) == 0

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
        """Test successful get_concept_details (lines 58-59)."""
        data = {
            "primaryAccession": "P04637",
            "genes": [{"geneName": {"value": "TP53"}}],
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Tumor protein p53"}}
            },
            "organism": {"scientificName": "Homo sapiens"},
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("P04637")
            assert result is not None
            assert result.primary_id == "P04637"

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling (lines 63-65)."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("P04637")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_data(self, adapter):
        """Test get_concept_details with empty data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            result = await adapter.get_concept_details("P04637")
            assert result is None

    def test_convert_uniprot_result_full(self, adapter):
        """Test _convert_uniprot_result_to_concept with all fields (lines 69-129)."""
        result = {
            "primaryAccession": "P04637",
            "genes": [
                {"geneName": {"value": "TP53"}},
                {"geneName": {"value": "p53"}},
            ],
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Tumor protein p53"}}
            },
            "organism": {"scientificName": "Homo sapiens"},
            "comments": [
                {"commentType": "FUNCTION", "texts": [{"value": "Acts as a tumor suppressor"}]},
                {"commentType": "OTHER", "texts": [{"value": "Some other comment"}]},
            ],
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "P04637"
        assert concept.primary_label == "TP53"
        assert "Tumor protein p53" in concept.synonyms
        assert "p53" in concept.synonyms
        assert "Acts as a tumor suppressor" in concept.definitions
        assert "Organism: Homo sapiens" in concept.categories
        assert concept.confidence_score == 0.95

    def test_convert_uniprot_no_accession(self, adapter):
        """Test _convert_uniprot_result_to_concept with no accession (returns None)."""
        result = {"genes": []}
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is None

    def test_convert_uniprot_no_genes(self, adapter):
        """Test conversion when no genes are present - uses recommended name as label."""
        result = {
            "primaryAccession": "P04637",
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Tumor protein p53"}}
            },
            "organism": {"scientificName": "Homo sapiens"},
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "Tumor protein p53"

    def test_convert_uniprot_no_recommended_name(self, adapter):
        """Test conversion when no recommended name - uses accession as label."""
        result = {"primaryAccession": "P04637"}
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "P04637"

    def test_convert_uniprot_gene_name_same_as_label(self, adapter):
        """Test that gene names identical to label are not added as synonyms."""
        result = {
            "primaryAccession": "P04637",
            "genes": [{"geneName": {"value": "TP53"}}],
            "proteinDescription": {"recommendedName": {"fullName": {"value": "TP53"}}},
            "organism": {"scientificName": "Homo sapiens"},
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert concept.synonyms.count("TP53") == 0

    def test_convert_uniprot_empty_genes_list(self, adapter):
        """Test conversion with empty genes list."""
        result = {
            "primaryAccession": "P04637",
            "genes": [],
            "proteinDescription": {},
            "organism": {"scientificName": "Homo sapiens"},
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "P04637"

    def test_convert_uniprot_gene_name_empty(self, adapter):
        """Test conversion with gene name that has empty value."""
        result = {
            "primaryAccession": "P04637",
            "genes": [{"geneName": {"value": ""}}],
            "proteinDescription": {"recommendedName": {"fullName": {"value": "Protein X"}}},
            "organism": {"scientificName": "Homo sapiens"},
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "Protein X"

    def test_convert_uniprot_no_organism(self, adapter):
        """Test conversion without organism data."""
        result = {
            "primaryAccession": "P04637",
            "genes": [{"geneName": {"value": "TP53"}}],
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Tumor protein p53"}}
            },
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert len(concept.categories) == 0

    def test_convert_uniprot_no_function_comments(self, adapter):
        """Test conversion with no FUNCTION comments."""
        result = {
            "primaryAccession": "P04637",
            "genes": [{"geneName": {"value": "TP53"}}],
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Tumor protein p53"}}
            },
            "organism": {"scientificName": "Homo sapiens"},
            "comments": [{"commentType": "SUBCELLULAR LOCATION", "texts": [{"value": "Nucleus"}]}],
        }
        concept = adapter._convert_uniprot_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0

    def test_convert_uniprot_error(self, adapter):
        """Test _convert_uniprot_result_to_concept with error-causing data."""
        concept = adapter._convert_uniprot_result_to_concept(None)
        assert concept is None

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
