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
        kegg_text = (
            "ENTRY       H00001\nNAME        Diabetes mellitus\nDESCRIPTION A metabolic disease"
        )
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

    # ------------------------------------------------------------------
    # Extended multi-database search
    # ------------------------------------------------------------------

    def test_supported_databases(self, adapter):
        """Supported databases include the classic and expanded KEGG sets."""
        dbs = adapter.supported_databases()
        for expected in ("disease", "drug", "pathway", "gene", "compound", "enzyme"):
            assert expected in dbs

    @pytest.mark.asyncio
    async def test_search_concepts_pathway(self, adapter):
        """Searching the pathway database returns PATHWAY concepts."""
        text = "map04930\tType II diabetes mellitus\nmap04940\tType I diabetes mellitus"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            results = await adapter.search_concepts("diabetes", databases=["pathway"])
            assert len(results) == 2
            assert results[0].primary_id == "map04930"
            assert results[0].concept_type == "PATHWAY"

    @pytest.mark.asyncio
    async def test_search_concepts_gene_uses_organism(self, adapter):
        """Gene search is scoped to the organism in the request URL."""
        text = "hsa:1953\tMEGF6, EGFL3; some protein"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            results = await adapter.search_concepts("INS", databases=["gene"], organism="hsa")
            called_url = mock_req.call_args.args[0]
            assert "/find/hsa/INS" in called_url
            assert results[0].primary_id == "hsa:1953"
            assert results[0].concept_type == "GENE"

    @pytest.mark.asyncio
    async def test_search_concepts_compound_and_enzyme(self, adapter):
        """Compound and enzyme searches map to the right concept types."""
        compound_text = "C01405\tAspirin; Acetylsalicylic acid"
        enzyme_text = "2.7.1.1\thexokinase; glucokinase"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [compound_text, enzyme_text]
            results = await adapter.search_concepts(
                "x", databases=["compound", "enzyme"], limit=10
            )
            assert len(results) == 2
            assert results[0].concept_type == "CHEMICAL"
            assert results[1].primary_id == "2.7.1.1"
            assert results[1].concept_type == "MOLECULAR_FUNCTION"

    @pytest.mark.asyncio
    async def test_search_concepts_respects_limit_across_dbs(self, adapter):
        """Limit is enforced across multiple databases."""
        text = "map00001\tA\nmap00002\tB\nmap00003\tC"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            results = await adapter.search_concepts("x", databases=["pathway", "pathway"], limit=2)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_unknown_database_skipped(self, adapter):
        """Unknown databases are skipped without a request."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = "dr:D00001\tAspirin"
            results = await adapter.search_concepts("aspirin", databases=["bogus", "drug"])
            assert mock_req.call_count == 1
            assert len(results) == 1

    # ------------------------------------------------------------------
    # Entry resolution / details
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "concept_id,expected",
        [
            ("H00001", "ds:H00001"),
            ("D00001", "dr:D00001"),
            ("C01405", "C01405"),
            ("K00844", "K00844"),
            ("hsa:1953", "hsa:1953"),
            ("hsa00010", "hsa00010"),
            ("path:hsa00010", "hsa00010"),
            ("2.7.1.1", "2.7.1.1"),
            ("TEST:001", None),
        ],
    )
    def test_build_get_entry(self, adapter, concept_id, expected):
        """Various id forms resolve to the correct get entry."""
        assert adapter._build_get_entry(concept_id) == expected

    @pytest.mark.asyncio
    async def test_get_concept_details_gene(self, adapter):
        """Gene details parse NAME, ORGANISM and infer GENE type."""
        text = (
            "ENTRY       1953              CDS\n"
            "SYMBOL      MEGF6, EGFL3\n"
            "NAME        (RefSeq) some protein precursor\n"
            "ORGANISM    hsa  Homo sapiens (human)"
        )
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            result = await adapter.get_concept_details("hsa:1953")
            assert result is not None
            assert result.concept_type == "GENE"
            assert result.primary_label == "(RefSeq) some protein precursor"

    @pytest.mark.asyncio
    async def test_get_concept_details_pathway(self, adapter):
        """Pathway details infer PATHWAY type and capture CLASS."""
        text = (
            "ENTRY       hsa00010                    Pathway\n"
            "NAME        Glycolysis / Gluconeogenesis - Homo sapiens (human)\n"
            "CLASS       Metabolism; Carbohydrate metabolism"
        )
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            result = await adapter.get_concept_details("hsa00010")
            assert result is not None
            assert result.concept_type == "PATHWAY"
            assert result.source_data["KEGG"]["class"].startswith("Metabolism")

    @pytest.mark.asyncio
    async def test_get_concept_details_unresolvable(self, adapter):
        """Unresolvable ids return None without a request."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            result = await adapter.get_concept_details("BOGUS")
            assert result is None
            mock_req.assert_not_called()

    # ------------------------------------------------------------------
    # Mappings (DBLINKS)
    # ------------------------------------------------------------------

    def test_parse_dblinks(self, adapter):
        """DBLINKS block parses into database -> id lists."""
        text = (
            "DBLINKS     GO: 0005515 0006096\n"
            "            PubChem: 1003\n"
            "            KEGG DISEASE: H00001\n"
            "COMMENT     something"
        )
        parsed = dict(adapter._parse_dblinks(text))
        assert parsed["GO"] == ["0005515", "0006096"]
        assert parsed["KEGG DISEASE"] == ["H00001"]

    @pytest.mark.asyncio
    async def test_get_mappings_from_dblinks(self, adapter):
        """get_mappings returns dicts derived from DBLINKS."""
        text = "ENTRY       C01405                    Compound\nDBLINKS     PubChem: 2244\n"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            mappings = await adapter.get_mappings("C01405")
            assert len(mappings) == 1
            assert mappings[0]["toSource"] == "PubChem"
            assert mappings[0]["toId"] == "2244"

    @pytest.mark.asyncio
    async def test_get_mappings_unresolvable_returns_empty(self, adapter):
        """Unresolvable ids short-circuit to [] without a request."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_mappings("TEST:001") == []
            mock_req.assert_not_called()

    # ------------------------------------------------------------------
    # Relationships (link)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_relationships_gene(self, adapter):
        """Gene relationships use link/pathway and return pathway links."""
        text = "hsa:10327\tpath:hsa00010\nhsa:10327\tpath:hsa04930"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            rels = await adapter.get_relationships("hsa:10327")
            assert mock_req.call_args.args[0].endswith("/link/pathway/hsa:10327")
            assert len(rels) == 2
            assert rels[0]["related_id"] == "path:hsa00010"
            assert rels[0]["relation_label"] == "in_pathway"

    @pytest.mark.asyncio
    async def test_get_relationships_pathway(self, adapter):
        """Pathway relationships link back to organism genes."""
        text = "path:hsa00010\thsa:124\npath:hsa00010\thsa:125"
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = text
            rels = await adapter.get_relationships("hsa00010")
            assert "/link/hsa/hsa00010" in mock_req.call_args.args[0]
            assert rels[0]["relation_label"] == "has_gene"

    @pytest.mark.asyncio
    async def test_get_relationships_unsupported_type(self, adapter):
        """Drug entries produce no relationships and no request."""
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as mock_req:
            assert await adapter.get_relationships("D00001") == []
            mock_req.assert_not_called()
