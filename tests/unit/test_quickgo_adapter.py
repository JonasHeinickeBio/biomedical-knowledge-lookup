"""
Unit tests for QuickGOAdapter.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

mock_bioservices = MagicMock()
sys.modules["bioservices"] = mock_bioservices

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.quickgo_adapter import QuickGOAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept


class TestQuickGOAdapter:
    """Tests for QuickGOAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create QuickGOAdapter instance."""
        return QuickGOAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test QuickGOAdapter initialization."""
        adapter = QuickGOAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.QUICKGO

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.QUICKGO

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.QUICKGO: 5.0})
        adapter = QuickGOAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass


class TestQuickGOSearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return QuickGOAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_import_error(self, adapter):
        """Test search returns empty when bioservices not available."""
        with patch.dict("sys.modules", {"bioservices": None}):
            result = await adapter.search_concepts("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_search_with_go_terms(self, adapter):
        """Test search with GO term results."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [
            {"id": "GO:0008150", "name": "biological_process", "aspect": "biological_process", "definition": "A process", "isObsolete": False}
        ]
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("biological process", limit=10)
            assert len(result) == 1
            assert result[0].primary_id == "GO:0008150"

    @pytest.mark.asyncio
    async def test_search_molecular_function(self, adapter):
        """Test search with molecular function term."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"id": "GO:0003674", "name": "molecular_function", "aspect": "molecular_function"}]
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("molecular function", limit=10)
            assert result[0].concept_type == ConceptType.MOLECULAR_FUNCTION

    @pytest.mark.asyncio
    async def test_search_cellular_component(self, adapter):
        """Test search with cellular component term."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"id": "GO:0005575", "name": "cellular_component", "aspect": "cellular_component"}]
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("cellular component", limit=10)
            assert result[0].concept_type == ConceptType.CELLULAR_COMPONENT

    @pytest.mark.asyncio
    async def test_search_unknown_aspect(self, adapter):
        """Test search with unknown aspect defaults to biological_process."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"id": "GO:9999999", "name": "unknown", "aspect": "unknown"}]
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("unknown", limit=10)
            assert result[0].concept_type == ConceptType.BIOLOGICAL_PROCESS

    @pytest.mark.asyncio
    async def test_search_with_annotations(self, adapter):
        """Test search with annotation results."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = []
        mock_qgo.Annotation.return_value = [{"geneProductId": "P12345", "goId": "GO:0008150", "qualifier": "enables", "evidenceCode": "IEA", "aspect": "biological_process"}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("P12345", limit=10)
            assert result[0].concept_type == ConceptType.GENE_DISEASE_ASSOCIATION

    @pytest.mark.asyncio
    async def test_search_exception(self, adapter):
        """Test search handles exceptions."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.side_effect = Exception("API Error")
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("test", limit=10)
            assert result == []

    @pytest.mark.asyncio
    async def test_search_term_not_dict(self, adapter):
        """Test search skips non-dict terms."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = ["not_a_dict", 123]
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("test", limit=10)
            assert result == []

    @pytest.mark.asyncio
    async def test_search_term_no_id_or_name(self, adapter):
        """Test search skips terms without id or name."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"id": "", "name": ""}]
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.search_concepts("test", limit=10)
            assert result == []


class TestQuickGOGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return QuickGOAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_get_details_import_error(self, adapter):
        """Test get_details returns None when bioservices not available."""
        with patch.dict("sys.modules", {"bioservices": None}):
            result = await adapter.get_concept_details("GO:0008150")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_details_go_term(self, adapter):
        """Test get_details for GO term."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"name": "biological_process", "aspect": "biological_process", "definition": "A process", "synonyms": ["BP"], "isObsolete": False, "comment": "test", "usage": "test"}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:0008150")
            assert result is not None
            assert result.primary_id == "GO:0008150"

    @pytest.mark.asyncio
    async def test_get_details_go_term_molecular_function(self, adapter):
        """Test get_details for molecular function."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"name": "molecular_function", "aspect": "molecular_function"}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:0003674")
            assert result.concept_type == ConceptType.MOLECULAR_FUNCTION

    @pytest.mark.asyncio
    async def test_get_details_go_term_cellular_component(self, adapter):
        """Test get_details for cellular component."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"name": "cellular_component", "aspect": "cellular_component"}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:0005575")
            assert result.concept_type == ConceptType.CELLULAR_COMPONENT

    @pytest.mark.asyncio
    async def test_get_details_go_term_unknown_aspect(self, adapter):
        """Test get_details for unknown aspect."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"name": "unknown", "aspect": "unknown"}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:9999999")
            assert result.concept_type == ConceptType.BIOLOGICAL_PROCESS

    @pytest.mark.asyncio
    async def test_get_details_go_term_empty_name(self, adapter):
        """Test get_details skips term with empty name."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = [{"name": "", "aspect": "biological_process"}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:0008150")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_details_go_term_no_results(self, adapter):
        """Test get_details returns None when no results."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:0008150")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_details_annotation(self, adapter):
        """Test get_details for non-GO annotation concept."""
        mock_qgo = MagicMock()
        mock_qgo.Annotation.return_value = [{"geneProductId": "P12345", "goId": "GO:0008150", "qualifier": "enables", "evidenceCode": "IEA", "aspect": "biological_process", "reference": "REF:001", "withFrom": ["gene"], "taxonId": "9606", "date": "2024-01-01", "assignedBy": "UniProt", "extensions": []}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("P12345")
            assert result.concept_type == ConceptType.GENE_DISEASE_ASSOCIATION

    @pytest.mark.asyncio
    async def test_get_details_annotation_no_results(self, adapter):
        """Test get_details returns None for annotation with no results."""
        mock_qgo = MagicMock()
        mock_qgo.Annotation.return_value = []
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("P12345")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_details_annotation_empty_gene_or_go(self, adapter):
        """Test get_details skips annotation with empty gene or go id."""
        mock_qgo = MagicMock()
        mock_qgo.Annotation.return_value = [{"geneProductId": "", "goId": ""}]
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("P12345")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_details_exception(self, adapter):
        """Test get_details handles exceptions."""
        mock_qgo = MagicMock()
        mock_qgo.get_go_terms.side_effect = Exception("API Error")
        with patch.dict("sys.modules", {"bioservices": MagicMock(QuickGO=MagicMock(return_value=mock_qgo))}):
            result = await adapter.get_concept_details("GO:0008150")
            assert result is None
