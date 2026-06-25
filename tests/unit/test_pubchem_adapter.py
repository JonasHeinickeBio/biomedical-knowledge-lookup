"""
Unit tests for PubChemAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.pubchem_adapter import PubChemAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestPubChemAdapter:
    """Tests for PubChemAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create PubChemAdapter instance."""
        return PubChemAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test PubChemAdapter initialization."""
        adapter = PubChemAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.PUBCHEM
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.PUBCHEM

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert result is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.PUBCHEM: 5.0})
        adapter = PubChemAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- search_concepts (lines 28-51) ---

    @pytest.mark.asyncio
    async def test_search_concepts_with_cids(self, adapter):
        """Test search_concepts fetches details for each CID."""
        mock_cids = {"IdentifierList": {"CID": [2244, 2245]}}
        mock_desc = {
            "InformationList": {"Information": [{"Title": "Aspirin", "Description": "A drug"}]}
        }
        mock_props = {
            "PropertyTable": {
                "Properties": [{"IUPACName": "acetylsalicylic acid", "MolecularFormula": "C9H8O4"}]
            }
        }

        async def mock_make_request(url, *args, **kwargs):
            if "cids" in url:
                return mock_cids
            elif "description" in url:
                return mock_desc
            elif "property" in url:
                return mock_props
            return {}

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            results = await adapter.search_concepts("aspirin", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_no_cids(self, adapter):
        """Test search_concepts returns empty with no CIDs."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value={}):
            results = await adapter.search_concepts("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_no_identifier_list(self, adapter):
        """Test search_concepts returns empty with no IdentifierList."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={"IdentifierList": {}}
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search_concepts returns empty on exception."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_none_concept_filtered(self, adapter):
        """Test search_concepts filters None concepts."""
        mock_cids = {"IdentifierList": {"CID": [2244, 2245]}}
        mock_desc_empty = {"InformationList": {"Information": []}}
        call_count = 0

        async def mock_make_request(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "cids" in url:
                return mock_cids
            return mock_desc_empty

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            results = await adapter.search_concepts("test", limit=10)
        assert results == []

    # --- get_concept_details (lines 53-103) ---

    @pytest.mark.asyncio
    async def test_get_concept_details_full(self, adapter):
        """Test get_concept_details with full data."""
        mock_desc = {
            "InformationList": {
                "Information": [
                    {
                        "Title": "Aspirin",
                        "Description": "A nonsteroidal anti-inflammatory drug",
                    }
                ]
            }
        }
        mock_props = {
            "PropertyTable": {
                "Properties": [
                    {
                        "IUPACName": "acetylsalicylic acid",
                        "MolecularFormula": "C9H8O4",
                        "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                    }
                ]
            }
        }

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            elif "property" in url:
                return mock_props
            return {}

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None
        assert result.primary_id == "2244"
        assert result.primary_label == "Aspirin"
        assert "A nonsteroidal anti-inflammatory drug" in result.definitions
        assert "acetylsalicylic acid" in result.synonyms
        assert "Formula: C9H8O4" in result.categories

    @pytest.mark.asyncio
    async def test_get_concept_details_no_info(self, adapter):
        """Test get_concept_details returns None with no info."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, return_value={}):
            result = await adapter.get_concept_details("2244")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_information_list(self, adapter):
        """Test get_concept_details returns None without InformationList."""
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value={"InformationList": {}},
        ):
            result = await adapter.get_concept_details("2244")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_information(self, adapter):
        """Test get_concept_details returns None with empty Information."""
        with patch.object(
            adapter,
            "_make_request",
            new_callable=AsyncMock,
            return_value={"InformationList": {"Information": []}},
        ):
            result = await adapter.get_concept_details("2244")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_description(self, adapter):
        """Test get_concept_details handles missing Description field."""
        mock_desc = {"InformationList": {"Information": [{"Title": "Test"}]}}
        mock_props = {"PropertyTable": {"Properties": [{}]}}

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            return mock_props

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None
        assert result.definitions == []

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter):
        """Test get_concept_details returns None on exception."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            result = await adapter.get_concept_details("2244")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_fallback_title(self, adapter):
        """Test get_concept_details uses fallback title when Title missing."""
        mock_desc = {"InformationList": {"Information": [{}]}}
        mock_props = {"PropertyTable": {"Properties": [{}]}}

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            return mock_props

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None
        assert result.primary_label == "PubChem CID 2244"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_iupac(self, adapter):
        """Test get_concept_details handles missing IUPACName."""
        mock_desc = {"InformationList": {"Information": [{"Title": "Test"}]}}
        mock_props = {"PropertyTable": {"Properties": [{"MolecularFormula": "C9H8O4"}]}}

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            return mock_props

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None
        assert "Formula: C9H8O4" in result.categories

    @pytest.mark.asyncio
    async def test_get_concept_details_no_formula(self, adapter):
        """Test get_concept_details handles missing MolecularFormula."""
        mock_desc = {"InformationList": {"Information": [{"Title": "Test"}]}}
        mock_props = {"PropertyTable": {"Properties": [{"IUPACName": "test"}]}}

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            return mock_props

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None
        assert "test" in result.synonyms

    @pytest.mark.asyncio
    async def test_get_concept_details_no_inchikey(self, adapter):
        """Test get_concept_details handles missing InChIKey."""
        mock_desc = {"InformationList": {"Information": [{"Title": "Test"}]}}
        mock_props = {
            "PropertyTable": {"Properties": [{"IUPACName": "test", "MolecularFormula": "C9H8O4"}]}
        }

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            return mock_props

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None
        assert len(result.identifiers) == 1

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_props(self, adapter):
        """Test get_concept_details handles empty PropertyTable."""
        mock_desc = {"InformationList": {"Information": [{"Title": "Test"}]}}
        mock_props = {"PropertyTable": {"Properties": [{}]}}

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            return mock_props

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_props_exception(self, adapter):
        """Test get_concept_details handles props request exception."""
        mock_desc = {"InformationList": {"Information": [{"Title": "Test"}]}}

        async def mock_make_request(url, *args, **kwargs):
            if "description" in url:
                return mock_desc
            if "property" in url:
                raise Exception("Props request failed")
            return {}

        with patch.object(adapter, "_make_request", side_effect=mock_make_request):
            result = await adapter.get_concept_details("2244")
        assert result is None
