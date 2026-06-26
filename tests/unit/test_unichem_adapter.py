"""
Unit tests for UniChemAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.unichem_adapter import UniChemAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestUniChemAdapter:
    """Tests for UniChemAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create UniChemAdapter instance."""
        return UniChemAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test UniChemAdapter initialization."""
        adapter = UniChemAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.UNICHEM
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.UNICHEM

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
        config = LookupConfig(rate_limits={KnowledgeSource.UNICHEM: 5.0})
        adapter = UniChemAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- search_concepts (lines 41-67) ---

    @pytest.mark.asyncio
    async def test_search_concepts_not_available(self, lookup_config):
        """Test search_concepts returns empty when not available."""
        adapter = UniChemAdapter(lookup_config)
        adapter.unichem = None
        results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search_concepts returns empty on exception."""
        with patch.object(adapter, "_determine_search_strategy", side_effect=Exception("fail")):
            results = await adapter.search_concepts("test")
        assert results == []

    # --- _determine_search_strategy (lines 69-91) ---

    def test_determine_search_strategy_inchikey(self, adapter):
        """Test _determine_search_strategy identifies InChIKey."""
        with patch.object(adapter, "_search_by_inchikey", return_value=["concept"]) as mock:
            adapter._determine_search_strategy("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", 10)
            mock.assert_called_once()

    def test_determine_search_strategy_inchi(self, adapter):
        """Test _determine_search_strategy identifies InChI."""
        with patch.object(adapter, "_search_by_inchi", return_value=["concept"]) as mock:
            adapter._determine_search_strategy(
                "InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)/t/h11H",
                10,
            )
            mock.assert_called_once()

    def test_determine_search_strategy_source_id(self, adapter):
        """Test _determine_search_strategy falls back to source ID search."""
        with patch.object(adapter, "_search_by_uci", return_value=[]):
            with patch.object(adapter, "_search_by_inchikey", return_value=[]):
                with patch.object(adapter, "_search_by_inchi", return_value=[]):
                    with patch.object(
                        adapter, "_search_by_source_id", return_value=["concept"]
                    ) as mock:
                        adapter._determine_search_strategy("CHEMBL25", 10)
                        mock.assert_called_once()

    def test_determine_search_strategy_uci(self, adapter):
        """Test _determine_search_strategy tries UCI first."""
        with patch.object(adapter, "_search_by_uci", return_value=["concept"]) as mock:
            adapter._determine_search_strategy("12345", 10)
            mock.assert_called_once()

    def test_determine_search_strategy_strategy_exception(self, adapter):
        """Test _determine_search_strategy continues after strategy exception."""
        with patch.object(adapter, "_search_by_uci", side_effect=Exception("fail")):
            with patch.object(adapter, "_search_by_inchikey", return_value=["concept"]) as mock:
                adapter._determine_search_strategy("test", 10)
                mock.assert_called_once()

    # --- _search_by_uci (lines 93-100) ---

    def test_search_by_uci_not_digit(self, adapter):
        """Test _search_by_uci returns empty for non-digit query."""
        results = adapter._search_by_uci("abc", 10)
        assert results == []

    def test_search_by_uci_no_unichem(self, adapter):
        """Test _search_by_uci returns empty when unichem is None."""
        adapter.unichem = None
        results = adapter._search_by_uci("12345", 10)
        assert results == []

    def test_search_by_uci_success(self, adapter):
        """Test _search_by_uci calls get_compounds with uci."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.return_value = None
        with patch.object(adapter, "_extract_concepts_from_compound_data", return_value=["c1"]):
            adapter._search_by_uci("12345", 10)
            adapter.unichem.get_compounds.assert_called_once_with("12345", "uci")

    # --- _search_by_inchikey (lines 102-108) ---

    def test_search_by_inchikey_invalid_format(self, adapter):
        """Test _search_by_inchikey returns empty for invalid InChIKey."""
        results = adapter._search_by_inchikey("invalid", 10)
        assert results == []

    def test_search_by_inchikey_no_unichem(self, adapter):
        """Test _search_by_inchikey returns empty when unichem is None."""
        adapter.unichem = None
        results = adapter._search_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", 10)
        assert results == []

    def test_search_by_inchikey_success(self, adapter):
        """Test _search_by_inchikey calls get_compounds with inchikey."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.return_value = None
        with patch.object(adapter, "_extract_concepts_from_compound_data", return_value=[]):
            adapter._search_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", 10)
            adapter.unichem.get_compounds.assert_called_once_with(
                "BSYNRYMUTXBXSQ-UHFFFAOYSA-N", "inchikey"
            )

    # --- _search_by_inchi (lines 110-116) ---

    def test_search_by_inchi_invalid(self, adapter):
        """Test _search_by_inchi returns empty for non-InChI query."""
        results = adapter._search_by_inchi("not_inchi", 10)
        assert results == []

    def test_search_by_inchi_no_unichem(self, adapter):
        """Test _search_by_inchi returns empty when unichem is None."""
        adapter.unichem = None
        results = adapter._search_by_inchi("InChI=1S/test", 10)
        assert results == []

    def test_search_by_inchi_success(self, adapter):
        """Test _search_by_inchi calls get_compounds."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.return_value = None
        with patch.object(adapter, "_extract_concepts_from_compound_data", return_value=[]):
            adapter._search_by_inchi("InChI=1S/test", 10)
            adapter.unichem.get_compounds.assert_called_once_with("InChI=1S/test", "inchi")

    # --- _search_by_source_id (lines 118-137) ---

    def test_search_by_source_id_no_unichem(self, adapter):
        """Test _search_by_source_id returns empty when unichem is None."""
        adapter.unichem = None
        results = adapter._search_by_source_id("CHEMBL25", 10)
        assert results == []

    def test_search_by_source_id_success(self, adapter):
        """Test _search_by_source_id iterates common sources."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.return_value = None
        with patch.object(adapter, "_extract_concepts_from_compound_data", return_value=["c1"]):
            adapter._search_by_source_id("CHEMBL25", 10)
            assert adapter.unichem.get_compounds.call_count == 4

    def test_search_by_source_id_exception_per_source(self, adapter):
        """Test _search_by_source_id continues after per-source exception."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.side_effect = [Exception("fail"), None, None, None]
        with patch.object(adapter, "_extract_concepts_from_compound_data", return_value=[]):
            adapter._search_by_source_id("CHEMBL25", 10)

    # --- _extract_concepts_from_compound_data (lines 139-153) ---

    def test_extract_concepts_none_data(self, adapter):
        """Test _extract_concepts_from_compound_data returns empty for None."""
        results = adapter._extract_concepts_from_compound_data(None, 10)
        assert results == []

    def test_extract_concepts_no_compounds_key(self, adapter):
        """Test _extract_concepts_from_compound_data returns empty without compounds key."""
        results = adapter._extract_concepts_from_compound_data({}, 10)
        assert results == []

    def test_extract_concepts_empty_compounds(self, adapter):
        """Test _extract_concepts_from_compound_data returns empty for empty compounds."""
        results = adapter._extract_concepts_from_compound_data({"compounds": []}, 10)
        assert results == []

    def test_extract_concepts_with_compounds(self, adapter):
        """Test _extract_concepts_from_compound_data extracts concepts."""
        data = {"compounds": [{"uci": "12345", "sources": []}]}
        with patch.object(adapter, "_convert_compound_to_concept", return_value="concept"):
            results = adapter._extract_concepts_from_compound_data(data, 10)
            assert results == ["concept"]

    def test_extract_concepts_respects_limit(self, adapter):
        """Test _extract_concepts_from_compound_data respects limit."""
        data = {"compounds": [{"uci": str(i)} for i in range(20)]}
        with patch.object(adapter, "_convert_compound_to_concept", return_value="concept"):
            results = adapter._extract_concepts_from_compound_data(data, 5)
            assert len(results) == 5

    def test_extract_concepts_none_concept_filtered(self, adapter):
        """Test _extract_concepts_from_compound_data filters None concepts."""
        data = {"compounds": [{"uci": "1"}, {"uci": "2"}]}
        with patch.object(adapter, "_convert_compound_to_concept", side_effect=["concept", None]):
            results = adapter._extract_concepts_from_compound_data(data, 10)
            assert len(results) == 1

    # --- get_concept_details (lines 155-182) ---

    @pytest.mark.asyncio
    async def test_get_concept_details_not_available(self, lookup_config):
        """Test get_concept_details returns None when not available."""
        adapter = UniChemAdapter(lookup_config)
        adapter.unichem = None
        result = await adapter.get_concept_details("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_unichem(self, adapter):
        """Test get_concept_details returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_concept_details("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_valid_data(self, adapter):
        """Test get_concept_details returns concept when valid."""
        adapter.unichem = MagicMock()
        data = {"compounds": [{"uci": "12345", "sources": []}]}
        adapter.unichem.get_compounds.return_value = data
        with patch.object(adapter, "_is_valid_compound_data", return_value=True):
            with patch.object(adapter, "_convert_compound_to_concept", return_value="concept"):
                result = await adapter.get_concept_details("12345")
        assert result == "concept"

    @pytest.mark.asyncio
    async def test_get_concept_details_invalid_data(self, adapter):
        """Test get_concept_details returns None when data invalid."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.return_value = None
        with patch.object(adapter, "_is_valid_compound_data", return_value=False):
            result = await adapter.get_concept_details("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter):
        """Test get_concept_details returns None on exception."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.side_effect = Exception("fail")
        result = await adapter.get_concept_details("12345")
        assert result is None

    # --- get_cross_references (lines 184-207) ---

    @pytest.mark.asyncio
    async def test_get_cross_references_not_available(self, lookup_config):
        """Test get_cross_references returns empty when not available."""
        adapter = UniChemAdapter(lookup_config)
        adapter.unichem = None
        result = await adapter.get_cross_references("12345")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_cross_references_no_compound_data(self, adapter):
        """Test get_cross_references returns empty when no compound data."""
        with patch.object(adapter, "_find_compound_data", return_value=None):
            result = await adapter.get_cross_references("12345")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_cross_references_exception(self, adapter):
        """Test get_cross_references returns empty on exception."""
        with patch.object(adapter, "_find_compound_data", side_effect=Exception("fail")):
            result = await adapter.get_cross_references("12345")
        assert result == {}

    # --- _find_compound_data (lines 209-229) ---

    def test_find_compound_data_no_unichem(self, adapter):
        """Test _find_compound_data returns None when unichem is None."""
        adapter.unichem = None
        result = adapter._find_compound_data("12345")
        assert result is None

    def test_find_compound_data_uci_valid(self, adapter):
        """Test _find_compound_data returns when UCI is valid."""
        adapter.unichem = MagicMock()
        data = {"compounds": [{"uci": "12345"}]}
        adapter.unichem.get_compounds.return_value = data
        with patch.object(adapter, "_is_valid_compound_data", return_value=True):
            result = adapter._find_compound_data("12345")
        assert result == data

    def test_find_compound_data_fallback_to_sources(self, adapter):
        """Test _find_compound_data falls back to common sources."""
        adapter.unichem = MagicMock()
        empty_data = {"compounds": []}
        valid_data = {"compounds": [{"uci": "12345"}]}
        adapter.unichem.get_compounds.side_effect = [empty_data, valid_data]
        with patch.object(adapter, "_is_valid_compound_data", side_effect=[False, True]):
            result = adapter._find_compound_data("12345")
        assert result == valid_data

    def test_find_compound_data_source_exception(self, adapter):
        """Test _find_compound_data continues after source exception."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_compounds.side_effect = [
            None,  # UCI returns None -> not valid
            Exception("fail"),  # ChEMBL
            {"compounds": []},  # ChEBI - valid structure but empty
        ]
        with patch.object(adapter, "_is_valid_compound_data", side_effect=[False, False]):
            result = adapter._find_compound_data("12345")
        assert result is None

    # --- _is_valid_compound_data (lines 231-237) ---

    def test_is_valid_compound_data_none(self, adapter):
        """Test _is_valid_compound_data returns False for None."""
        assert adapter._is_valid_compound_data(None) is False

    def test_is_valid_compound_data_no_compounds(self, adapter):
        """Test _is_valid_compound_data returns False without compounds key."""
        assert adapter._is_valid_compound_data({}) is False

    def test_is_valid_compound_data_empty(self, adapter):
        """Test _is_valid_compound_data returns False for empty compounds."""
        assert not adapter._is_valid_compound_data({"compounds": []})

    def test_is_valid_compound_data_valid(self, adapter):
        """Test _is_valid_compound_data returns True for valid data."""
        assert adapter._is_valid_compound_data({"compounds": [{"uci": "1"}]})

    # --- _extract_cross_references_with_urls (lines 239-259) ---

    @pytest.mark.asyncio
    async def test_extract_cross_references_with_urls(self, adapter):
        """Test _extract_cross_references_with_urls extracts xrefs."""
        data = {
            "compounds": [
                {
                    "sources": [
                        {
                            "shortName": "ChEMBL",
                            "compoundId": "CHEMBL25",
                            "url": "https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25/",
                        }
                    ]
                }
            ]
        }
        result = await adapter._extract_cross_references_with_urls(data)
        assert "ChEMBL" in result
        assert result["ChEMBL"][0]["id"] == "CHEMBL25"

    @pytest.mark.asyncio
    async def test_extract_cross_references_no_url(self, adapter):
        """Test _extract_cross_references_with_urls skips sources without URL."""
        data = {"compounds": [{"sources": [{"shortName": "ChEMBL", "compoundId": "CHEMBL25"}]}]}
        result = await adapter._extract_cross_references_with_urls(data)
        assert "ChEMBL" not in result

    @pytest.mark.asyncio
    async def test_extract_cross_references_no_compound_id(self, adapter):
        """Test _extract_cross_references_with_urls skips sources without compoundId."""
        data = {
            "compounds": [{"sources": [{"shortName": "ChEMBL", "url": "https://example.com"}]}]
        }
        result = await adapter._extract_cross_references_with_urls(data)
        assert "ChEMBL" not in result

    # --- _build_compound_url (lines 261-323) ---

    @pytest.mark.asyncio
    async def test_build_compound_url_chembl(self, adapter):
        """Test _build_compound_url for ChEMBL source."""
        url = await adapter._build_compound_url(1, "CHEMBL25")
        assert "chembl" in url.lower()

    @pytest.mark.asyncio
    async def test_build_compound_url_chebi(self, adapter):
        """Test _build_compound_url for ChEBI source."""
        url = await adapter._build_compound_url(2, "CHEBI:12345")
        assert "chebi" in url.lower()

    @pytest.mark.asyncio
    async def test_build_compound_url_drugbank(self, adapter):
        """Test _build_compound_url for DrugBank source."""
        url = await adapter._build_compound_url(3, "DB00001")
        assert "drugbank" in url.lower()

    @pytest.mark.asyncio
    async def test_build_compound_url_pubchem(self, adapter):
        """Test _build_compound_url for PubChem source."""
        url = await adapter._build_compound_url(4, "2244")
        assert "pubchem" in url.lower()

    @pytest.mark.asyncio
    async def test_build_compound_url_unknown_source(self, adapter):
        """Test _build_compound_url falls back to get_source_info_by_id."""
        with patch.object(
            adapter, "get_source_info_by_id", new_callable=AsyncMock, return_value=None
        ):
            url = await adapter._build_compound_url(999, "TEST123")
        assert "unichem" in url.lower()

    @pytest.mark.asyncio
    async def test_build_compound_url_unknown_source_with_info(self, adapter):
        """Test _build_compound_url uses source info for unknown source."""
        with patch.object(
            adapter,
            "get_source_info_by_id",
            new_callable=AsyncMock,
            return_value={"srcUrl": "https://example.com/"},
        ):
            url = await adapter._build_compound_url(999, "TEST123")
        assert url == "https://example.com/TEST123"

    @pytest.mark.asyncio
    async def test_build_compound_url_chembl_in_url(self, adapter):
        """Test _build_compound_url constructs ChEMBL-like URL."""
        with patch.object(
            adapter,
            "get_source_info_by_id",
            new_callable=AsyncMock,
            return_value={"srcUrl": "https://www.ebi.ac.uk/chembl"},
        ):
            url = await adapter._build_compound_url(999, "CHEMBL25")
        assert "compound_report_card" in url

    @pytest.mark.asyncio
    async def test_build_compound_url_drugbank_in_url(self, adapter):
        """Test _build_compound_url constructs DrugBank-like URL."""
        with patch.object(
            adapter,
            "get_source_info_by_id",
            new_callable=AsyncMock,
            return_value={"srcUrl": "https://www.drugbank.ca"},
        ):
            url = await adapter._build_compound_url(999, "DB00001")
        assert "drugs" in url

    @pytest.mark.asyncio
    async def test_build_compound_url_pubchem_in_url(self, adapter):
        """Test _build_compound_url constructs PubChem-like URL."""
        with patch.object(
            adapter,
            "get_source_info_by_id",
            new_callable=AsyncMock,
            return_value={"srcUrl": "https://pubchem.ncbi.nlm.nih.gov"},
        ):
            url = await adapter._build_compound_url(999, "2244")
        assert "compound" in url

    @pytest.mark.asyncio
    async def test_build_compound_url_chebi_in_url(self, adapter):
        """Test _build_compound_url constructs ChEBI-like URL."""
        with patch.object(
            adapter,
            "get_source_info_by_id",
            new_callable=AsyncMock,
            return_value={"srcUrl": "https://www.ebi.ac.uk/chebi"},
        ):
            url = await adapter._build_compound_url(999, "CHEBI:12345")
        assert "searchId" in url

    # --- _get_source_name (lines 325-327) ---

    def test_get_source_name_short_name(self, adapter):
        """Test _get_source_name prefers shortName."""
        result = adapter._get_source_name({"shortName": "ChEMBL"})
        assert result == "ChEMBL"

    def test_get_source_name_long_name(self, adapter):
        """Test _get_source_name falls back to nameLong."""
        result = adapter._get_source_name({"nameLong": "ChEMBL Database"})
        assert result == "ChEMBL Database"

    def test_get_source_name_default(self, adapter):
        """Test _get_source_name returns default format."""
        result = adapter._get_source_name({"sourceID": "1"})
        assert result == "source_1"

    # --- get_all_src_ids (lines 331-361) ---

    @pytest.mark.asyncio
    async def test_get_all_src_ids_no_unichem(self, adapter):
        """Test get_all_src_ids returns empty when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_all_src_ids()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_src_ids_cached(self, adapter):
        """Test get_all_src_ids returns cached value."""
        adapter.unichem = MagicMock()
        with patch.object(adapter._cache, "get", return_value=[1, 2, 3]):
            result = await adapter.get_all_src_ids()
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_all_src_ids_success(self, adapter):
        """Test get_all_src_ids fetches and caches."""
        adapter.unichem = MagicMock()
        adapter.unichem.get_all_src_ids.return_value = [1, 2, 3]
        with patch.object(adapter._cache, "get", return_value=None):
            with patch.object(adapter._cache, "set"):
                with patch("asyncio.to_thread", return_value=[1, 2, 3]):
                    result = await adapter.get_all_src_ids()
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_all_src_ids_exception(self, adapter):
        """Test get_all_src_ids returns empty on exception."""
        adapter.unichem = MagicMock()
        with patch.object(adapter._cache, "get", return_value=None):
            with patch("asyncio.to_thread", side_effect=Exception("fail")):
                result = await adapter.get_all_src_ids()
        assert result == []

    # --- get_compounds (lines 363-397) ---

    @pytest.mark.asyncio
    async def test_get_compounds_no_unichem(self, adapter):
        """Test get_compounds returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_compounds("CHEMBL25", "chembl")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_compounds_cached(self, adapter):
        """Test get_compounds returns cached value."""
        adapter.unichem = MagicMock()
        cached = {"compounds": [{"uci": "12345"}]}
        with patch.object(adapter._cache, "get", return_value=cached):
            result = await adapter.get_compounds("CHEMBL25", "chembl")
        assert result == cached

    @pytest.mark.asyncio
    async def test_get_compounds_success(self, adapter):
        """Test get_compounds fetches and caches."""
        adapter.unichem = MagicMock()
        data = {"compounds": [{"uci": "12345"}]}
        with patch.object(adapter._cache, "get", return_value=None):
            with patch.object(adapter._cache, "set"):
                with patch("asyncio.to_thread", return_value=data):
                    result = await adapter.get_compounds("CHEMBL25", "chembl")
        assert result == data

    @pytest.mark.asyncio
    async def test_get_compounds_exception(self, adapter):
        """Test get_compounds returns None on exception."""
        adapter.unichem = MagicMock()
        with patch.object(adapter._cache, "get", return_value=None):
            with patch("asyncio.to_thread", side_effect=Exception("fail")):
                result = await adapter.get_compounds("CHEMBL25", "chembl")
        assert result is None

    # --- get_connectivity (lines 399-418) ---

    @pytest.mark.asyncio
    async def test_get_connectivity_no_unichem(self, adapter):
        """Test get_connectivity returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_connectivity("CHEMBL25", "chembl")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_connectivity_success(self, adapter):
        """Test get_connectivity returns data."""
        adapter.unichem = MagicMock()
        data = {"connectivity": "test"}
        with patch("asyncio.to_thread", return_value=data):
            result = await adapter.get_connectivity("CHEMBL25", "chembl")
        assert result == data

    @pytest.mark.asyncio
    async def test_get_connectivity_exception(self, adapter):
        """Test get_connectivity returns None on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_connectivity("CHEMBL25", "chembl")
        assert result is None

    # --- get_id_from_name (lines 420-438) ---

    @pytest.mark.asyncio
    async def test_get_id_from_name_no_unichem(self, adapter):
        """Test get_id_from_name returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_id_from_name("chembl")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_id_from_name_success(self, adapter):
        """Test get_id_from_name returns ID."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", return_value=1):
            result = await adapter.get_id_from_name("chembl")
        assert result == 1

    @pytest.mark.asyncio
    async def test_get_id_from_name_exception(self, adapter):
        """Test get_id_from_name returns None on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_id_from_name("chembl")
        assert result is None

    # --- get_images (lines 440-459) ---

    @pytest.mark.asyncio
    async def test_get_images_no_unichem(self, adapter):
        """Test get_images returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_images("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_images_success(self, adapter):
        """Test get_images returns SVG data."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", return_value="<svg>test</svg>"):
            result = await adapter.get_images("12345", "test.svg")
        assert result == "<svg>test</svg>"

    @pytest.mark.asyncio
    async def test_get_images_exception(self, adapter):
        """Test get_images returns None on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_images("12345")
        assert result is None

    # --- get_inchi_from_inchikey (lines 461-479) ---

    @pytest.mark.asyncio
    async def test_get_inchi_from_inchikey_no_unichem(self, adapter):
        """Test get_inchi_from_inchikey returns empty when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_inchi_from_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_inchi_from_inchikey_success(self, adapter):
        """Test get_inchi_from_inchikey returns InChI data."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", return_value=["InChI=1S/test"]):
            result = await adapter.get_inchi_from_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == ["InChI=1S/test"]

    @pytest.mark.asyncio
    async def test_get_inchi_from_inchikey_exception(self, adapter):
        """Test get_inchi_from_inchikey returns empty on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_inchi_from_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == []

    # --- get_source_info_by_id (lines 481-514) ---

    @pytest.mark.asyncio
    async def test_get_source_info_by_id_no_unichem(self, adapter):
        """Test get_source_info_by_id returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_source_info_by_id(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_source_info_by_id_cached(self, adapter):
        """Test get_source_info_by_id returns cached value."""
        adapter.unichem = MagicMock()
        cached = {"srcUrl": "https://example.com"}
        with patch.object(adapter._cache, "get", return_value=cached):
            result = await adapter.get_source_info_by_id(1)
        assert result == cached

    @pytest.mark.asyncio
    async def test_get_source_info_by_id_success(self, adapter):
        """Test get_source_info_by_id fetches and caches."""
        adapter.unichem = MagicMock()
        info = {"srcUrl": "https://example.com"}
        with patch.object(adapter._cache, "get", return_value=None):
            with patch.object(adapter._cache, "set"):
                with patch("asyncio.to_thread", return_value=info):
                    result = await adapter.get_source_info_by_id(1)
        assert result == info

    @pytest.mark.asyncio
    async def test_get_source_info_by_id_exception(self, adapter):
        """Test get_source_info_by_id returns None on exception."""
        adapter.unichem = MagicMock()
        with patch.object(adapter._cache, "get", return_value=None):
            with patch("asyncio.to_thread", side_effect=Exception("fail")):
                result = await adapter.get_source_info_by_id(1)
        assert result is None

    # --- get_source_info_by_name (lines 516-551) ---

    @pytest.mark.asyncio
    async def test_get_source_info_by_name_no_unichem(self, adapter):
        """Test get_source_info_by_name returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_source_info_by_name("chembl")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_source_info_by_name_cached(self, adapter):
        """Test get_source_info_by_name returns cached value."""
        adapter.unichem = MagicMock()
        cached = {"srcUrl": "https://example.com"}
        with patch.object(adapter._cache, "get", return_value=cached):
            result = await adapter.get_source_info_by_name("chembl")
        assert result == cached

    @pytest.mark.asyncio
    async def test_get_source_info_by_name_success(self, adapter):
        """Test get_source_info_by_name fetches and caches."""
        adapter.unichem = MagicMock()
        info = {"srcUrl": "https://example.com"}
        with patch.object(adapter._cache, "get", return_value=None):
            with patch.object(adapter._cache, "set"):
                with patch("asyncio.to_thread", return_value=info):
                    result = await adapter.get_source_info_by_name("chembl")
        assert result == info

    @pytest.mark.asyncio
    async def test_get_source_info_by_name_exception(self, adapter):
        """Test get_source_info_by_name returns None on exception."""
        adapter.unichem = MagicMock()
        with patch.object(adapter._cache, "get", return_value=None):
            with patch("asyncio.to_thread", side_effect=Exception("fail")):
                result = await adapter.get_source_info_by_name("chembl")
        assert result is None

    # --- get_sources (lines 553-583) ---

    @pytest.mark.asyncio
    async def test_get_sources_no_unichem(self, adapter):
        """Test get_sources returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_sources()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sources_cached(self, adapter):
        """Test get_sources returns cached value."""
        adapter.unichem = MagicMock()
        cached = {"sources": "test"}
        with patch.object(adapter._cache, "get", return_value=cached):
            result = await adapter.get_sources()
        assert result == cached

    @pytest.mark.asyncio
    async def test_get_sources_success(self, adapter):
        """Test get_sources fetches and caches."""
        adapter.unichem = MagicMock()
        data = {"sources": "test"}
        with patch.object(adapter._cache, "get", return_value=None):
            with patch.object(adapter._cache, "set"):
                with patch("asyncio.to_thread", return_value=data):
                    result = await adapter.get_sources()
        assert result == data

    @pytest.mark.asyncio
    async def test_get_sources_exception(self, adapter):
        """Test get_sources returns None on exception."""
        adapter.unichem = MagicMock()
        with patch.object(adapter._cache, "get", return_value=None):
            with patch("asyncio.to_thread", side_effect=Exception("fail")):
                result = await adapter.get_sources()
        assert result is None

    # --- get_sources_by_inchikey (lines 585-603) ---

    @pytest.mark.asyncio
    async def test_get_sources_by_inchikey_no_unichem(self, adapter):
        """Test get_sources_by_inchikey returns empty when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_sources_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_sources_by_inchikey_success(self, adapter):
        """Test get_sources_by_inchikey returns data."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", return_value=[1, 2]):
            result = await adapter.get_sources_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_get_sources_by_inchikey_exception(self, adapter):
        """Test get_sources_by_inchikey returns empty on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_sources_by_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == []

    # --- get_sources_by_inchikey_verbose (lines 605-623) ---

    @pytest.mark.asyncio
    async def test_get_sources_by_inchikey_verbose_no_unichem(self, adapter):
        """Test get_sources_by_inchikey_verbose returns empty when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_sources_by_inchikey_verbose("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_sources_by_inchikey_verbose_success(self, adapter):
        """Test get_sources_by_inchikey_verbose returns data."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", return_value=[{"source": 1}]):
            result = await adapter.get_sources_by_inchikey_verbose("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == [{"source": 1}]

    @pytest.mark.asyncio
    async def test_get_sources_by_inchikey_verbose_exception(self, adapter):
        """Test get_sources_by_inchikey_verbose returns empty on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_sources_by_inchikey_verbose("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        assert result == []

    # --- get_structure (lines 625-646) ---

    @pytest.mark.asyncio
    async def test_get_structure_no_unichem(self, adapter):
        """Test get_structure returns None when unichem is None."""
        adapter.unichem = None
        result = await adapter.get_structure("CHEMBL25", "chembl")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_structure_success(self, adapter):
        """Test get_structure returns data."""
        adapter.unichem = MagicMock()
        data = {"standardinchi": "InChI=...", "standardinchikey": "ABC-DEF-GHI"}
        with patch("asyncio.to_thread", return_value=data):
            result = await adapter.get_structure("CHEMBL25", "chembl")
        assert result == data

    @pytest.mark.asyncio
    async def test_get_structure_exception(self, adapter):
        """Test get_structure returns None on exception."""
        adapter.unichem = MagicMock()
        with patch("asyncio.to_thread", side_effect=Exception("fail")):
            result = await adapter.get_structure("CHEMBL25", "chembl")
        assert result is None

    # --- _convert_compound_to_concept (lines 648-673) ---

    def test_convert_compound_to_concept_no_uci(self, adapter):
        """Test _convert_compound_to_concept returns None without UCI."""
        result = adapter._convert_compound_to_concept({})
        assert result is None

    def test_convert_compound_to_concept_success(self, adapter):
        """Test _convert_compound_to_concept creates concept."""
        compound = {
            "uci": "12345",
            "sources": [
                {
                    "shortName": "ChEMBL",
                    "compoundId": "CHEMBL25",
                    "url": "https://example.com",
                }
            ],
        }
        result = adapter._convert_compound_to_concept(compound)
        assert result is not None
        assert result.primary_id == "12345"

    def test_convert_compound_to_concept_exception(self, adapter):
        """Test _convert_compound_to_concept returns None on exception."""
        result = adapter._convert_compound_to_concept(None)
        assert result is None

    # --- get_cache_stats (lines 675-682) ---

    def test_get_cache_stats(self, adapter):
        """Test get_cache_stats returns stats."""
        stats = adapter.get_cache_stats()
        assert isinstance(stats, dict)

    # --- clear_cache (lines 684-692) ---

    def test_clear_cache(self, adapter):
        """Test clear_cache clears cache."""
        with patch.object(adapter._cache, "clear") as mock_clear:
            adapter.clear_cache()
            mock_clear.assert_called_once_with("unichem")

    def test_clear_cache_custom_namespace(self, adapter):
        """Test clear_cache with custom namespace."""
        with patch.object(adapter._cache, "clear") as mock_clear:
            adapter.clear_cache(namespace="custom")
            mock_clear.assert_called_once_with("custom")

    # --- _create_base_concept (lines 694-698) ---

    def test_create_base_concept(self, adapter):
        """Test _create_base_concept creates concept."""
        from knowledge_lookup.models import ConceptType

        result = adapter._create_base_concept("12345")
        assert result.primary_id == "12345"
        assert result.primary_label == "UCI_12345"
        assert result.concept_type == ConceptType.CHEMICAL

    # --- _add_unichem_identifier (lines 700-707) ---

    def test_add_unichem_identifier(self, adapter):
        """Test _add_unichem_identifier adds identifier."""
        concept = adapter._create_base_concept("12345")
        adapter._add_unichem_identifier(concept, "12345")
        assert len(concept.identifiers) == 1
        assert concept.identifiers[0].identifier == "12345"

    # --- _add_source_identifiers (lines 709-724) ---

    def test_add_source_identifiers(self, adapter):
        """Test _add_source_identifiers adds source identifiers."""
        concept = adapter._create_base_concept("12345")
        compound = {
            "sources": [
                {"shortName": "ChEMBL", "compoundId": "CHEMBL25", "url": "https://example.com"}
            ]
        }
        adapter._add_source_identifiers(concept, compound)
        assert len(concept.identifiers) > 0

    def test_add_source_identifiers_no_compound_id(self, adapter):
        """Test _add_source_identifiers skips sources without compoundId."""
        concept = adapter._create_base_concept("12345")
        compound = {"sources": [{"shortName": "ChEMBL"}]}
        adapter._add_source_identifiers(concept, compound)
        assert len(concept.identifiers) == 0

    # --- _add_source_categories (lines 726-730) ---

    def test_add_source_categories(self, adapter):
        """Test _add_source_categories adds category names."""
        concept = adapter._create_base_concept("12345")
        compound = {"sources": [{"shortName": "ChEMBL"}, {"shortName": "DrugBank"}]}
        adapter._add_source_categories(concept, compound)
        assert "ChEMBL" in concept.categories
        assert "DrugBank" in concept.categories

    def test_add_source_categories_no_short_name(self, adapter):
        """Test _add_source_categories skips sources without shortName."""
        concept = adapter._create_base_concept("12345")
        compound = {"sources": [{"nameLong": "Test"}]}
        adapter._add_source_categories(concept, compound)
        assert concept.categories == []

    # --- _set_concept_metadata (lines 732-735) ---

    def test_set_concept_metadata(self, adapter):
        """Test _set_concept_metadata sets confidence and source data."""
        from knowledge_lookup.models import KnowledgeSource

        concept = adapter._create_base_concept("12345")
        compound = {"test": "data"}
        adapter._set_concept_metadata(concept, compound)
        assert concept.confidence_score == 0.9
        assert KnowledgeSource.UNICHEM in concept.source_data
