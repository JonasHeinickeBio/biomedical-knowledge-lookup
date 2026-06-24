"""
Unit tests for EUtilsAdapter.
"""

import sys
from unittest.mock import MagicMock, patch

mock_bioservices = MagicMock()
sys.modules["bioservices"] = mock_bioservices

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.eutils_adapter import (
    EUtilsAdapter,
    _extract_gene_field,
    _extract_protein_field,
    _extract_pubmed_field,
    _extract_taxonomy_field,
)
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestEUtilsAdapter:
    """Tests for EUtilsAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EUtilsAdapter instance."""
        return EUtilsAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test EUtilsAdapter initialization."""
        adapter = EUtilsAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.EUTILS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.EUTILS

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.EUTILS: 5.0})
        adapter = EUtilsAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_bioservices_import_error(self, adapter):
        """Test search when bioservices import fails (lines 37-39)."""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            results = await adapter.search_concepts("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_pubmed_results(self, adapter):
        """Test search with PubMed results (lines 50-74)."""
        mock_eu = MagicMock()
        mock_eu.ESearch.side_effect = [
            {"IdList": ["12345", "67890"]},  # pubmed
            {"IdList": []},  # gene
            {"IdList": []},  # protein
            {"IdList": []},  # taxonomy
        ]
        mock_eu.ESummary.return_value = {
            "DocSum": {
                "Item": [
                    {"Name": "Title", "ItemContent": "Test Article"},
                    {"Name": "AuthorList", "ItemContent": "Author1"},
                ]
            }
        }

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            results = await adapter.search_concepts("test", limit=4)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_gene_results(self, adapter):
        """Test search with Gene database results (lines 79-103)."""
        mock_eu = MagicMock()
        mock_eu.ESearch.side_effect = [
            {"IdList": []},  # pubmed
            {"IdList": ["1234"]},  # gene
            {"IdList": []},  # protein
            {"IdList": []},  # taxonomy
        ]
        mock_eu.ESummary.return_value = {
            "DocSum": {
                "Item": [
                    {"Name": "Name", "ItemContent": "BRCA2"},
                    {"Name": "Description", "ItemContent": "BRCA2 DNA repair associated"},
                ]
            }
        }

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            results = await adapter.search_concepts("BRCA2", limit=4)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_protein_results(self, adapter):
        """Test search with Protein database results (lines 112-136)."""
        mock_eu = MagicMock()
        mock_eu.ESearch.side_effect = [
            {"IdList": []},  # pubmed
            {"IdList": []},  # gene
            {"IdList": ["P04637"]},  # protein
            {"IdList": []},  # taxonomy
        ]
        mock_eu.ESummary.return_value = {
            "DocSum": {
                "Item": [
                    {"Name": "Title", "ItemContent": "Tumor protein p53"},
                    {"Name": "AccessionVersion", "ItemContent": "NP_000537"},
                ]
            }
        }

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            results = await adapter.search_concepts("TP53", limit=4)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_taxonomy_results(self, adapter):
        """Test search with Taxonomy database results (lines 145-174)."""
        mock_eu = MagicMock()
        mock_eu.ESearch.side_effect = [
            {"IdList": []},  # pubmed
            {"IdList": []},  # gene
            {"IdList": []},  # protein
            {"IdList": ["9606"]},  # taxonomy
        ]
        mock_eu.ESummary.return_value = {
            "DocSum": {
                "Item": [
                    {"Name": "ScientificName", "ItemContent": "Homo sapiens"},
                    {"Name": "CommonName", "ItemContent": "human"},
                ]
            }
        }

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            results = await adapter.search_concepts("human", limit=4)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search exception handling (lines 173-174)."""
        mock_eu = MagicMock()
        mock_eu.ESearch.side_effect = Exception("Search error")

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            results = await adapter.search_concepts("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_get_concept_details_import_error(self, adapter):
        """Test get_concept_details when bioservices import fails (lines 186-188)."""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            result = await adapter.get_concept_details("PMID:12345")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_pubmed(self, adapter):
        """Test get_concept_details for PMID (lines 196-200)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = "Full article text here"

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("PMID:12345")
            assert result is not None
            assert result.primary_id == "PMID:12345"

    @pytest.mark.asyncio
    async def test_get_concept_details_geneid(self, adapter):
        """Test get_concept_details for GeneID (lines 198-200)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = "Gene record"

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("GeneID:1234")
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_taxid(self, adapter):
        """Test get_concept_details for TaxID (lines 202-203)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = "Taxonomy record"

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("TaxID:9606")
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_protein_accession(self, adapter):
        """Test get_concept_details for protein accession (lines 207-208)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = "Protein record"

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("NP_000537")
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_nuccore_accession(self, adapter):
        """Test get_concept_details for nucleotide accession (line 210)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = "Nucleotide record"

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("NM_000537")
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_unknown_format(self, adapter):
        """Test get_concept_details with unknown format (defaults to pubmed, lines 223-234)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = "Some record"

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("12345")
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details exception handling (lines 250-253)."""
        mock_eu = MagicMock()
        mock_eu.EFetch.side_effect = Exception("Fetch error")

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("PMID:12345")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_record(self, adapter):
        """Test get_concept_details when EFetch returns None."""
        mock_eu = MagicMock()
        mock_eu.EFetch.return_value = None

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            result = await adapter.get_concept_details("PMID:12345")
            assert result is None

    def test_extract_pubmed_field_success(self):
        """Test _extract_pubmed_field (lines 257-264)."""
        docsum = {"Item": [{"Name": "Title", "ItemContent": "Test Article"}]}
        result = _extract_pubmed_field(docsum, "Title")
        assert result == "Test Article"

    def test_extract_pubmed_field_not_found(self):
        """Test _extract_pubmed_field with missing field."""
        docsum = {"Item": [{"Name": "Title", "ItemContent": "Test Article"}]}
        result = _extract_pubmed_field(docsum, "Author")
        assert result == ""

    def test_extract_pubmed_field_empty_docsum(self):
        """Test _extract_pubmed_field with empty docsum."""
        result = _extract_pubmed_field({}, "Title")
        assert result == ""

    def test_extract_pubmed_field_exception(self):
        """Test _extract_pubmed_field exception handling."""
        result = _extract_pubmed_field(None, "Title")
        assert result == ""

    def test_extract_gene_field_success(self):
        """Test _extract_gene_field (lines 268-275)."""
        docsum = {"Item": [{"Name": "Name", "ItemContent": "BRCA2"}]}
        result = _extract_gene_field(docsum, "Name")
        assert result == "BRCA2"

    def test_extract_gene_field_not_found(self):
        """Test _extract_gene_field with missing field."""
        docsum = {"Item": [{"Name": "Name", "ItemContent": "BRCA2"}]}
        result = _extract_gene_field(docsum, "Description")
        assert result == ""

    def test_extract_gene_field_exception(self):
        """Test _extract_gene_field exception handling."""
        result = _extract_gene_field(None, "Name")
        assert result == ""

    def test_extract_protein_field_success(self):
        """Test _extract_protein_field (lines 279-286)."""
        docsum = {"Item": [{"Name": "Title", "ItemContent": "Tumor protein p53"}]}
        result = _extract_protein_field(docsum, "Title")
        assert result == "Tumor protein p53"

    def test_extract_protein_field_not_found(self):
        """Test _extract_protein_field with missing field."""
        docsum = {"Item": [{"Name": "Title", "ItemContent": "Tumor protein p53"}]}
        result = _extract_protein_field(docsum, "AccessionVersion")
        assert result == ""

    def test_extract_protein_field_exception(self):
        """Test _extract_protein_field exception handling."""
        result = _extract_protein_field(None, "Title")
        assert result == ""

    def test_extract_taxonomy_field_success(self):
        """Test _extract_taxonomy_field (lines 290-297)."""
        docsum = {"Item": [{"Name": "ScientificName", "ItemContent": "Homo sapiens"}]}
        result = _extract_taxonomy_field(docsum, "ScientificName")
        assert result == "Homo sapiens"

    def test_extract_taxonomy_field_not_found(self):
        """Test _extract_taxonomy_field with missing field."""
        docsum = {"Item": [{"Name": "ScientificName", "ItemContent": "Homo sapiens"}]}
        result = _extract_taxonomy_field(docsum, "CommonName")
        assert result == ""

    def test_extract_taxonomy_field_exception(self):
        """Test _extract_taxonomy_field exception handling."""
        result = _extract_taxonomy_field(None, "ScientificName")
        assert result == ""

    @pytest.mark.asyncio
    async def test_search_pubmed_no_id_list(self, adapter):
        """Test search when pubmed returns no IdList."""
        mock_eu = MagicMock()
        mock_eu.ESearch.side_effect = [
            {"IdList": []},  # pubmed
            {"IdList": []},  # gene
            {"IdList": []},  # protein
            {"IdList": []},  # taxonomy
        ]

        with patch.dict("sys.modules", {"bioservices": MagicMock(EUtils=MagicMock(return_value=mock_eu))}):
            import importlib

            import knowledge_lookup.adapters.eutils_adapter as mod
            importlib.reload(mod)
            adapter.__class__ = mod.EUtilsAdapter
            results = await adapter.search_concepts("nonexistent", limit=20)
            assert results == []

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
