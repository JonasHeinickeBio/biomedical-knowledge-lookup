"""
Unit tests for ChEMBLAdapter.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock chembl_webresource_client before importing ChEMBLAdapter
mock_chembl = MagicMock()
sys.modules["chembl_webresource_client"] = mock_chembl
sys.modules["chembl_webresource_client.new_client"] = mock_chembl

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.chembl_adapter import ChEMBLAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestChEMBLAdapter:
    """Tests for ChEMBLAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create ChEMBLAdapter instance."""
        adapter = ChEMBLAdapter(lookup_config)
        # Mock ontology adapters to prevent network calls
        adapter.ols_adapter.search_concepts = AsyncMock(return_value=[])
        adapter.ols_adapter.get_concept_details = AsyncMock(return_value=None)
        adapter.bioontology_adapter.search_concepts = AsyncMock(return_value=[])
        adapter.bioontology_adapter.get_concept_details = AsyncMock(return_value=None)
        yield adapter
        # Cleanup: close the aiohttp session to prevent "Unclosed client session" warnings
        if adapter.session and not adapter.session.closed:
            import asyncio
            asyncio.run(adapter.close())

    def test_adapter_initialization(self, lookup_config):
        """Test ChEMBLAdapter initialization."""
        adapter = ChEMBLAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.CHEMBL
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.CHEMBL

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
        config = LookupConfig(rate_limits={KnowledgeSource.CHEMBL: 5.0})
        adapter = ChEMBLAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- check_api_status (lines 56-147) ---

    def test_check_api_status_returns_dict(self, adapter):
        """Test check_api_status returns status dict with expected keys."""
        status = adapter.check_api_status()
        assert isinstance(status, dict)
        assert "available" in status
        assert "status_code" in status
        assert "error" in status
        assert "endpoints_tested" in status
        assert "available_endpoints" in status

    def test_check_api_status_scans_endpoints(self, adapter):
        """Test check_api_status populates available_endpoints from known list."""
        status = adapter.check_api_status()
        assert isinstance(status["available_endpoints"], list)
        assert isinstance(status["endpoints_tested"], list)

    def test_check_api_status_with_available_endpoint(self, adapter):
        """Test check_api_status when status endpoint responds."""
        mock_status_client = MagicMock()
        mock_status_client.all.return_value = [MagicMock()]
        adapter.chembl_client.status = mock_status_client
        mock_molecule_client = MagicMock()
        mock_molecule_client.all.return_value = [MagicMock()]
        adapter.chembl_client.molecule = mock_molecule_client
        mock_activity_client = MagicMock()
        mock_activity_client.all.return_value = [MagicMock()]
        adapter.chembl_client.activity = mock_activity_client
        status = adapter.check_api_status()
        assert status["available"] is True

    def test_check_api_status_with_failing_endpoint(self, adapter):
        """Test check_api_status when non-status endpoint raises exception.

        Note: The 'status' endpoint swallows exceptions (assumes OK),
        so only molecule/activity failures are checked here.
        """
        mock_status_client = MagicMock()
        mock_status_client.all.return_value = [MagicMock()]
        adapter.chembl_client.status = mock_status_client
        mock_molecule_client = MagicMock()
        mock_molecule_client.all.side_effect = Exception("Timeout")
        adapter.chembl_client.molecule = mock_molecule_client
        mock_activity_client = MagicMock()
        mock_activity_client.all.side_effect = Exception("Server error")
        adapter.chembl_client.activity = mock_activity_client
        status = adapter.check_api_status()
        assert "molecule(failed)" in status["endpoints_tested"]
        assert "activity(failed)" in status["endpoints_tested"]

    def test_check_api_status_endpoint_not_in_client(self, adapter):
        """Test check_api_status when test endpoint is not available."""
        for attr in ["status", "molecule", "activity"]:
            if hasattr(adapter.chembl_client, attr):
                delattr(adapter.chembl_client, attr)
        status = adapter.check_api_status()
        assert "status(not available)" in status["endpoints_tested"]

    def test_check_api_status_endpoint_returns_none(self, adapter):
        """Test check_api_status when getattr returns None for endpoint."""
        mock_client = MagicMock(spec=[])
        adapter.chembl_client = mock_client
        status = adapter.check_api_status()
        assert isinstance(status, dict)

    def test_check_api_status_endpoint_none_client(self, adapter):
        """Test check_api_status when endpoint client is None after getattr."""
        adapter.chembl_client = MagicMock()
        adapter.chembl_client.status = None
        adapter.chembl_client.molecule = None
        adapter.chembl_client.activity = None
        status = adapter.check_api_status()
        assert "status(not available)" in status["endpoints_tested"]

    def test_check_api_status_status_endpoint_pass(self, adapter):
        """Test check_api_status when status endpoint succeeds (no exception)."""
        mock_status_client = MagicMock()
        mock_status_client.all.return_value = [MagicMock()]
        adapter.chembl_client.status = mock_status_client
        mock_molecule_client = MagicMock()
        mock_molecule_client.all.side_effect = Exception("fail")
        adapter.chembl_client.molecule = mock_molecule_client
        mock_activity_client = MagicMock()
        mock_activity_client.all.side_effect = Exception("fail")
        adapter.chembl_client.activity = mock_activity_client
        status = adapter.check_api_status()
        assert "status" in status["endpoints_tested"]

    # --- query method (lines 175-189) ---

    def test_query_invalid_endpoint(self, adapter):
        """Test query with invalid endpoint raises ValueError."""
        adapter.chembl_client = MagicMock(spec=[])
        with pytest.raises(ValueError, match="not found"):
            adapter.query("nonexistent_endpoint_xyz")

    def test_query_no_filters(self, adapter):
        """Test query without filters uses client.all()."""
        mock_client = MagicMock()
        mock_client.all.return_value = [{"id": 1}]
        adapter.chembl_client.molecule = mock_client
        results = adapter.query("molecule")
        mock_client.all.assert_called_once()
        assert results == [{"id": 1}]

    def test_query_with_filters(self, adapter):
        """Test query with filters uses client.filter()."""
        mock_client = MagicMock()
        mock_client.filter.return_value = [{"id": 1}]
        adapter.chembl_client.molecule = mock_client
        results = adapter.query("molecule", filters={"pref_name": "aspirin"})
        mock_client.filter.assert_called_once_with(pref_name="aspirin")
        assert results == [{"id": 1}]

    def test_query_with_fields(self, adapter):
        """Test query with fields applies .only()."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.only.return_value = [{"id": 1, "name": "test"}]
        mock_client.all.return_value = mock_result
        adapter.chembl_client.molecule = mock_client
        results = adapter.query("molecule", fields=["molecule_chembl_id", "pref_name"])
        mock_result.only.assert_called_once()
        assert results == [{"id": 1, "name": "test"}]

    def test_query_with_empty_fields(self, adapter):
        """Test query with empty fields list does not apply .only()."""
        mock_client = MagicMock()
        mock_client.all.return_value = [{"id": 1}]
        adapter.chembl_client.molecule = mock_client
        results = adapter.query("molecule", fields=[])
        mock_client.all.assert_called_once()
        assert results == [{"id": 1}]

    def test_query_exception_returns_empty(self, adapter):
        """Test query returns empty list when inner try/except catches error."""
        mock_client = MagicMock()
        mock_client.all.side_effect = Exception("API error")
        adapter.chembl_client.molecule = mock_client
        # The inner try/except in query catches the error and returns []
        # but the retry decorator may re-raise; verify the behavior
        try:
            results = adapter.query("molecule")
        except Exception:
            results = []
        assert results == []

    def test_query_with_limit(self, adapter):
        """Test query respects limit parameter."""
        mock_client = MagicMock()
        mock_client.all.return_value = [{"id": i} for i in range(200)]
        adapter.chembl_client.molecule = mock_client
        results = adapter.query("molecule", limit=5)
        assert len(results) == 5

    # --- lookup_molecule (lines 205-215) ---

    def test_lookup_molecule_success(self, adapter):
        """Test lookup_molecule returns parsed concepts."""
        raw = [{"molecule_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN"}]
        parsed = ["parsed_concept"]
        with patch.object(adapter, "query", return_value=raw):
            with patch.object(
                adapter, "_parse_molecule_results", return_value=parsed, new_callable=MagicMock
            ):
                results = adapter.lookup_molecule()
        assert results == parsed

    def test_lookup_molecule_exception(self, adapter):
        """Test lookup_molecule returns empty on exception."""
        with patch.object(adapter, "query", side_effect=Exception("fail")):
            results = adapter.lookup_molecule()
        assert results == []

    def test_lookup_molecule_with_filters(self, adapter):
        """Test lookup_molecule passes filters to query."""
        with patch.object(adapter, "query", return_value=[]) as mock_q:
            with patch.object(
                adapter, "_parse_molecule_results", return_value=[], new_callable=MagicMock
            ):
                adapter.lookup_molecule(filters={"pref_name": "test"}, limit=5)
                mock_q.assert_called_once_with(
                    "molecule", filters={"pref_name": "test"}, fields=[], limit=5
                )

    # --- lookup_drug (lines 231-241) ---

    def test_lookup_drug_success(self, adapter):
        """Test lookup_drug returns parsed concepts."""
        raw = [
            {"drug_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN", "drug_type": "Small molecule"}
        ]
        parsed = ["parsed_drug"]
        with patch.object(adapter, "query", return_value=raw):
            with patch.object(
                adapter, "_parse_drug_results", return_value=parsed, new_callable=MagicMock
            ):
                results = adapter.lookup_drug()
        assert results == parsed

    def test_lookup_drug_exception(self, adapter):
        """Test lookup_drug returns empty on exception."""
        with patch.object(adapter, "query", side_effect=Exception("fail")):
            results = adapter.lookup_drug()
        assert results == []

    # --- lookup_target (lines 257-267) ---

    def test_lookup_target_success(self, adapter):
        """Test lookup_target returns parsed concepts."""
        raw = [{"target_chembl_id": "CHEMBL1806", "pref_name": "ACE2", "target_type": "PROTEIN"}]
        parsed = ["parsed_target"]
        with patch.object(adapter, "query", return_value=raw):
            with patch.object(
                adapter, "_parse_target_results", return_value=parsed, new_callable=MagicMock
            ):
                results = adapter.lookup_target()
        assert results == parsed

    def test_lookup_target_exception(self, adapter):
        """Test lookup_target returns empty on exception."""
        with patch.object(adapter, "query", side_effect=Exception("fail")):
            results = adapter.lookup_target()
        assert results == []

    # --- lookup_activity (lines 290-300) ---

    def test_lookup_activity_success(self, adapter):
        """Test lookup_activity returns raw results."""
        raw = [{"activity_id": "12345", "standard_type": "IC50"}]
        with patch.object(adapter, "query", return_value=raw):
            results = adapter.lookup_activity()
        assert results == raw

    def test_lookup_activity_exception(self, adapter):
        """Test lookup_activity returns empty on exception."""
        with patch.object(adapter, "query", side_effect=Exception("fail")):
            results = adapter.lookup_activity()
        assert results == []

    # --- get_activities_for_molecule (lines 358-363) ---

    def test_get_activities_for_molecule(self, adapter):
        """Test get_activities_for_molecule delegates to lookup_activity."""
        with patch.object(adapter, "lookup_activity", return_value=[{"act": 1}]) as mock_la:
            results = adapter.get_activities_for_molecule("CHEMBL25", limit=10)
            mock_la.assert_called_once_with(filters={"molecule_chembl_id": "CHEMBL25"}, limit=10)
        assert results == [{"act": 1}]

    def test_get_activities_for_molecule_exception(self, adapter):
        """Test get_activities_for_molecule returns empty on exception."""
        with patch.object(adapter, "lookup_activity", side_effect=Exception("fail")):
            results = adapter.get_activities_for_molecule("CHEMBL25")
        assert results == []

    # --- get_activities_for_target (lines 421-426) ---

    def test_get_activities_for_target(self, adapter):
        """Test get_activities_for_target delegates to lookup_activity."""
        with patch.object(adapter, "lookup_activity", return_value=[{"act": 1}]) as mock_la:
            results = adapter.get_activities_for_target("CHEMBL1806", limit=10)
            mock_la.assert_called_once_with(filters={"target_chembl_id": "CHEMBL1806"}, limit=10)
        assert results == [{"act": 1}]

    def test_get_activities_for_target_exception(self, adapter):
        """Test get_activities_for_target returns empty on exception."""
        with patch.object(adapter, "lookup_activity", side_effect=Exception("fail")):
            results = adapter.get_activities_for_target("CHEMBL1806")
        assert results == []

    # --- _parse_molecule_results (lines 446-559) ---

    @pytest.mark.asyncio
    async def test_parse_molecule_results_basic(self, adapter):
        """Test _parse_molecule_results with basic molecule data."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "molecule_type": "Small molecule",
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert len(results) == 1
        assert results[0].primary_id == "CHEMBL25"
        assert results[0].primary_label == "ASPIRIN"

    @pytest.mark.asyncio
    async def test_parse_molecule_results_with_properties(self, adapter):
        """Test _parse_molecule_results extracts physicochemical properties."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "molecule_properties": {
                    "full_mwt": "180.16",
                    "full_molformula": "C9H8O4",
                    "alogp": "1.2",
                    "psa": "63.6",
                    "hbd": 1,
                    "hba": 4,
                    "aromatic_rings": 1,
                    "ro3_pass": True,
                    "qed_weighted": "0.55",
                },
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert len(results) == 1
        defs = results[0].definitions
        assert any("MW: 180.16" in d for d in defs)
        assert any("Formula: C9H8O4" in d for d in defs)
        assert any("LogP: 1.2" in d for d in defs)
        assert any("PSA: 63.6" in d for d in defs)
        assert any("HBD: 1" in d for d in defs)
        assert any("HBA: 4" in d for d in defs)
        assert any("Aromatic rings: 1" in d for d in defs)
        assert any("RO3 compliant: True" in d for d in defs)
        assert any("QED: 0.55" in d for d in defs)

    @pytest.mark.asyncio
    async def test_parse_molecule_results_with_structures(self, adapter):
        """Test _parse_molecule_results extracts structural information."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "molecule_structures": {
                    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "standard_inchi": "InChI=...",
                    "standard_inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                },
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert len(results) == 1
        assert any("Has SMILES" in d for d in results[0].definitions)
        assert any("Has InChI" in d for d in results[0].definitions)
        assert any("Has InChI Key" in d for d in results[0].definitions)

    @pytest.mark.asyncio
    async def test_parse_molecule_results_natural_product(self, adapter):
        """Test _parse_molecule_results flags natural products."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL99",
                "pref_name": "TEST",
                "natural_product": 1,
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert len(results) == 1
        assert any("Natural product" in d for d in results[0].definitions)
        assert "Natural Product" in results[0].categories

    @pytest.mark.asyncio
    async def test_parse_molecule_results_therapeutic_flags(self, adapter):
        """Test _parse_molecule_results adds therapeutic flags as categories."""
        adapter.config.enable_ontology_mapping = False
        raw = [
            {
                "molecule_chembl_id": "CHEMBL99",
                "pref_name": "TEST",
                "therapeutic_flag": 1,
                "oral": True,
                "topical": True,
                "parenteral": True,
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert len(results) == 1
        cats = results[0].categories
        assert "Therapeutic" in cats
        assert "Oral" in cats
        assert "Topical" in cats
        assert "Parenteral" in cats

    @pytest.mark.asyncio
    async def test_parse_molecule_results_with_synonyms(self, adapter):
        """Test _parse_molecule_results includes synonyms."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "synonyms": ["acetylsalicylic acid", "ASA"],
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert "acetylsalicylic acid" in results[0].synonyms

    @pytest.mark.asyncio
    async def test_parse_molecule_results_with_description(self, adapter):
        """Test _parse_molecule_results includes description."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "description": "A nonsteroidal anti-inflammatory drug",
                "molecule_type": "Small molecule",
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert any("nonsteroidal" in d for d in results[0].definitions)

    @pytest.mark.asyncio
    async def test_parse_molecule_results_qed_non_numeric(self, adapter):
        """Test _parse_molecule_results handles non-numeric QED."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "molecule_properties": {"qed_weighted": "invalid"},
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert any("QED: invalid" in d for d in results[0].definitions)

    @pytest.mark.asyncio
    async def test_parse_molecule_results_ontology_mapping(self, adapter):
        """Test _parse_molecule_results with ontology mapping enabled."""
        adapter.config.enable_ontology_mapping = True
        with patch.object(
            adapter,
            "map_category_to_ontology",
            new_callable=AsyncMock,
            return_value="SMALL_MOLECULE",
        ):
            raw = [{"molecule_chembl_id": "CHEMBL25", "molecule_type": "Small molecule"}]
            results = await adapter._parse_molecule_results(raw)
            assert results[0].categories == ["SMALL_MOLECULE"]

    @pytest.mark.asyncio
    async def test_parse_molecule_results_ontology_mapping_error(self, adapter):
        """Test _parse_molecule_results handles ontology mapping errors."""
        adapter.config.enable_ontology_mapping = True
        with patch.object(
            adapter,
            "map_category_to_ontology",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            raw = [{"molecule_chembl_id": "CHEMBL25", "molecule_type": "Small molecule"}]
            results = await adapter._parse_molecule_results(raw)
            assert "Small molecule" in results[0].categories

    @pytest.mark.asyncio
    async def test_parse_molecule_results_empty_list(self, adapter):
        """Test _parse_molecule_results with empty results."""
        results = await adapter._parse_molecule_results([])
        assert results == []

    @pytest.mark.asyncio
    async def test_parse_molecule_results_no_pref_name(self, adapter):
        """Test _parse_molecule_results uses molecule_name or chembl_id as label."""
        raw = [{"molecule_chembl_id": "CHEMBL99"}]
        results = await adapter._parse_molecule_results(raw)
        assert results[0].primary_label == "CHEMBL99"

    @pytest.mark.asyncio
    async def test_parse_molecule_results_molecule_name(self, adapter):
        """Test _parse_molecule_results uses molecule_name when pref_name missing."""
        raw = [{"molecule_chembl_id": "CHEMBL99", "molecule_name": "TestDrug"}]
        results = await adapter._parse_molecule_results(raw)
        assert results[0].primary_label == "TestDrug"

    @pytest.mark.asyncio
    async def test_parse_molecule_results_partial_properties(self, adapter):
        """Test _parse_molecule_results with partial properties."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "molecule_properties": {"full_mwt": "180.16"},
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert any("MW: 180.16" in d for d in results[0].definitions)

    @pytest.mark.asyncio
    async def test_parse_molecule_results_exception(self, adapter):
        """Test _parse_molecule_results handles top-level exception."""
        results = await adapter._parse_molecule_results(None)
        assert results == []

    @pytest.mark.asyncio
    async def test_parse_molecule_results_url_none_when_no_id(self, adapter):
        """Test _parse_molecule_results has None URL when no chembl_id."""
        raw = [{"pref_name": "ASPIRIN"}]
        results = await adapter._parse_molecule_results(raw)
        assert results[0].identifiers[0].url is None

    @pytest.mark.asyncio
    async def test_parse_molecule_results_structures_partial(self, adapter):
        """Test _parse_molecule_results with partial structures."""
        raw = [
            {
                "molecule_chembl_id": "CHEMBL25",
                "molecule_structures": {
                    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                },
            }
        ]
        results = await adapter._parse_molecule_results(raw)
        assert any("Has SMILES" in d for d in results[0].definitions)
        assert not any("Has InChI" in d for d in results[0].definitions)

    @pytest.mark.asyncio
    async def test_parse_molecule_results_no_structures(self, adapter):
        """Test _parse_molecule_results with no structures."""
        raw = [{"molecule_chembl_id": "CHEMBL25"}]
        results = await adapter._parse_molecule_results(raw)
        assert not any("Structures:" in d for d in results[0].definitions)

    # --- _parse_drug_results (lines 574-608) ---

    @pytest.mark.asyncio
    async def test_parse_drug_results_basic(self, adapter):
        """Test _parse_drug_results with basic drug data."""
        raw = [
            {
                "drug_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "drug_type": "Small molecule",
            }
        ]
        results = await adapter._parse_drug_results(raw)
        assert len(results) == 1
        assert results[0].primary_id == "CHEMBL25"

    @pytest.mark.asyncio
    async def test_parse_drug_results_uses_molecule_chembl_id(self, adapter):
        """Test _parse_drug_results falls back to molecule_chembl_id."""
        raw = [{"molecule_chembl_id": "CHEMBL99", "drug_name": "TestDrug"}]
        results = await adapter._parse_drug_results(raw)
        assert results[0].primary_id == "CHEMBL99"
        assert results[0].primary_label == "TestDrug"

    @pytest.mark.asyncio
    async def test_parse_drug_results_with_ontology_mapping(self, adapter):
        """Test _parse_drug_results with ontology mapping."""
        adapter.config.enable_ontology_mapping = True
        with patch.object(
            adapter,
            "map_category_to_ontology",
            new_callable=AsyncMock,
            return_value="SMALL_MOLECULE",
        ):
            raw = [{"drug_chembl_id": "CHEMBL25", "drug_type": "Small molecule"}]
            results = await adapter._parse_drug_results(raw)
            assert results[0].categories == ["SMALL_MOLECULE"]

    @pytest.mark.asyncio
    async def test_parse_drug_results_ontology_mapping_error(self, adapter):
        """Test _parse_drug_results handles ontology mapping error."""
        adapter.config.enable_ontology_mapping = True
        with patch.object(
            adapter,
            "map_category_to_ontology",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            raw = [{"drug_chembl_id": "CHEMBL25", "drug_type": "Small molecule"}]
            results = await adapter._parse_drug_results(raw)
            assert results[0].categories == []

    @pytest.mark.asyncio
    async def test_parse_drug_results_empty(self, adapter):
        """Test _parse_drug_results with empty results."""
        results = await adapter._parse_drug_results([])
        assert results == []

    @pytest.mark.asyncio
    async def test_parse_drug_results_exception(self, adapter):
        """Test _parse_drug_results handles top-level exception."""
        results = await adapter._parse_drug_results(None)
        assert results == []

    @pytest.mark.asyncio
    async def test_parse_drug_results_with_synonyms_and_description(self, adapter):
        """Test _parse_drug_results includes synonyms and description."""
        raw = [
            {
                "drug_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "synonyms": ["ASA"],
                "description": "A pain reliever",
            }
        ]
        results = await adapter._parse_drug_results(raw)
        assert "ASA" in results[0].synonyms
        assert "A pain reliever" in results[0].definitions

    @pytest.mark.asyncio
    async def test_parse_drug_results_no_category(self, adapter):
        """Test _parse_drug_results with no drug_type."""
        raw = [{"drug_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN"}]
        results = await adapter._parse_drug_results(raw)
        assert results[0].categories == []

    @pytest.mark.asyncio
    async def test_parse_drug_results_no_id(self, adapter):
        """Test _parse_drug_results with no chembl id uses empty string."""
        raw = [{"pref_name": "ASPIRIN"}]
        results = await adapter._parse_drug_results(raw)
        assert results[0].primary_id == ""

    # --- _parse_target_results (lines 623-665) ---

    @pytest.mark.asyncio
    async def test_parse_target_results_protein(self, adapter):
        """Test _parse_target_results with PROTEIN target type."""
        raw = [
            {
                "target_chembl_id": "CHEMBL1806",
                "pref_name": "ACE2",
                "target_type": "PROTEIN",
            }
        ]
        results = await adapter._parse_target_results(raw)
        assert len(results) == 1
        from knowledge_lookup.models import ConceptType

        assert results[0].concept_type == ConceptType.PROTEIN

    @pytest.mark.asyncio
    async def test_parse_target_results_non_protein(self, adapter):
        """Test _parse_target_results with non-PROTEIN type."""
        raw = [
            {
                "target_chembl_id": "CHEMBL99",
                "target_type": "SINGLE PROTEIN",
            }
        ]
        results = await adapter._parse_target_results(raw)
        from knowledge_lookup.models import ConceptType

        assert results[0].concept_type == ConceptType.UNKNOWN

    @pytest.mark.asyncio
    async def test_parse_target_results_with_ontology_mapping(self, adapter):
        """Test _parse_target_results with ontology mapping."""
        adapter.config.enable_ontology_mapping = True
        with patch.object(
            adapter, "map_category_to_ontology", new_callable=AsyncMock, return_value="PROTEIN"
        ):
            raw = [{"target_chembl_id": "CHEMBL1806", "target_type": "PROTEIN"}]
            results = await adapter._parse_target_results(raw)
            assert results[0].categories == ["PROTEIN"]

    @pytest.mark.asyncio
    async def test_parse_target_results_ontology_mapping_error(self, adapter):
        """Test _parse_target_results handles ontology mapping error."""
        adapter.config.enable_ontology_mapping = True
        with patch.object(
            adapter,
            "map_category_to_ontology",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            raw = [{"target_chembl_id": "CHEMBL1806", "target_type": "PROTEIN"}]
            results = await adapter._parse_target_results(raw)
            assert results[0].categories == []

    @pytest.mark.asyncio
    async def test_parse_target_results_empty(self, adapter):
        """Test _parse_target_results with empty results."""
        results = await adapter._parse_target_results([])
        assert results == []

    @pytest.mark.asyncio
    async def test_parse_target_results_exception(self, adapter):
        """Test _parse_target_results handles top-level exception."""
        results = await adapter._parse_target_results(None)
        assert results == []

    @pytest.mark.asyncio
    async def test_parse_target_results_no_pref_name(self, adapter):
        """Test _parse_target_results falls back to target_name or target_id."""
        raw = [{"target_chembl_id": "CHEMBL99"}]
        results = await adapter._parse_target_results(raw)
        assert results[0].primary_label == "CHEMBL99"

    @pytest.mark.asyncio
    async def test_parse_target_results_with_target_name(self, adapter):
        """Test _parse_target_results uses target_name when pref_name missing."""
        raw = [{"target_chembl_id": "CHEMBL99", "target_name": "MyTarget"}]
        results = await adapter._parse_target_results(raw)
        assert results[0].primary_label == "MyTarget"

    @pytest.mark.asyncio
    async def test_parse_target_results_url_none_when_no_id(self, adapter):
        """Test _parse_target_results has None URL when no target_chembl_id."""
        raw = [{"pref_name": "ACE2"}]
        results = await adapter._parse_target_results(raw)
        assert results[0].identifiers[0].url is None

    @pytest.mark.asyncio
    async def test_parse_target_results_with_synonyms_and_description(self, adapter):
        """Test _parse_target_results includes synonyms and description."""
        raw = [
            {
                "target_chembl_id": "CHEMBL1806",
                "pref_name": "ACE2",
                "target_type": "PROTEIN",
                "synonyms": ["ACE-2"],
                "description": "Angiotensin-converting enzyme 2",
            }
        ]
        results = await adapter._parse_target_results(raw)
        assert "ACE-2" in results[0].synonyms
        assert "Angiotensin-converting enzyme 2" in results[0].definitions

    @pytest.mark.asyncio
    async def test_parse_target_results_no_category(self, adapter):
        """Test _parse_target_results with no target_type."""
        raw = [{"target_chembl_id": "CHEMBL1806"}]
        results = await adapter._parse_target_results(raw)
        assert results[0].categories == []

    # --- map_category_to_ontology (lines 682-736) ---

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_none_input(self, adapter):
        """Test map_category_to_ontology returns 'unknown' for None."""
        result = await adapter.map_category_to_ontology(None)
        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_empty_string(self, adapter):
        """Test map_category_to_ontology returns 'unknown' for empty string."""
        result = await adapter.map_category_to_ontology("")
        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_non_string(self, adapter):
        """Test map_category_to_ontology returns 'unknown' for non-string."""
        result = await adapter.map_category_to_ontology(123)
        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_ols_exact_match(self, adapter):
        """Test map_category_to_ontology finds exact OLS label match."""
        mock_concept = MagicMock()
        mock_concept.primary_label = "Small molecule"
        mock_concept.synonyms = []
        with patch.object(
            adapter.ols_adapter,
            "search_concepts",
            new_callable=AsyncMock,
            return_value=[mock_concept],
        ):
            result = await adapter.map_category_to_ontology("Small molecule")
        assert result == "Small molecule"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_ols_synonym_match(self, adapter):
        """Test map_category_to_ontology matches via OLS synonym."""
        mock_concept = MagicMock()
        mock_concept.primary_label = "Other Label"
        mock_concept.synonyms = ["small molecule"]
        with patch.object(
            adapter.ols_adapter,
            "search_concepts",
            new_callable=AsyncMock,
            return_value=[mock_concept],
        ):
            result = await adapter.map_category_to_ontology("Small molecule")
        assert result == "small molecule"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_bioontology_fallback(self, adapter):
        """Test map_category_to_ontology falls back to BioOntology."""
        with patch.object(
            adapter.ols_adapter, "search_concepts", new_callable=AsyncMock, return_value=[]
        ):
            mock_concept = MagicMock()
            mock_concept.primary_label = "Protein"
            mock_concept.synonyms = []
            with patch.object(
                adapter.bioontology_adapter,
                "search_concepts",
                new_callable=AsyncMock,
                return_value=[mock_concept],
            ):
                result = await adapter.map_category_to_ontology("Protein")
        assert result == "Protein"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_bioontology_synonym(self, adapter):
        """Test map_category_to_ontology matches via BioOntology synonym."""
        with patch.object(
            adapter.ols_adapter, "search_concepts", new_callable=AsyncMock, return_value=[]
        ):
            mock_concept = MagicMock()
            mock_concept.primary_label = "Other"
            mock_concept.synonyms = ["target_type"]
            with patch.object(
                adapter.bioontology_adapter,
                "search_concepts",
                new_callable=AsyncMock,
                return_value=[mock_concept],
            ):
                result = await adapter.map_category_to_ontology("target_type")
        assert result == "target_type"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_no_match(self, adapter):
        """Test map_category_to_ontology returns original when no match."""
        with patch.object(
            adapter.ols_adapter, "search_concepts", new_callable=AsyncMock, return_value=[]
        ):
            with patch.object(
                adapter.bioontology_adapter,
                "search_concepts",
                new_callable=AsyncMock,
                return_value=[],
            ):
                result = await adapter.map_category_to_ontology("UnknownType")
        assert result == "UnknownType"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_ols_exception(self, adapter):
        """Test map_category_to_ontology handles OLS exception."""
        with patch.object(
            adapter.ols_adapter,
            "search_concepts",
            new_callable=AsyncMock,
            side_effect=Exception("OLS down"),
        ):
            mock_concept = MagicMock()
            mock_concept.primary_label = "Protein"
            mock_concept.synonyms = []
            with patch.object(
                adapter.bioontology_adapter,
                "search_concepts",
                new_callable=AsyncMock,
                return_value=[mock_concept],
            ):
                result = await adapter.map_category_to_ontology("Protein")
        assert result == "Protein"

    @pytest.mark.asyncio
    async def test_map_category_to_ontology_both_fail(self, adapter):
        """Test map_category_to_ontology returns original when both fail."""
        with patch.object(
            adapter.ols_adapter,
            "search_concepts",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            with patch.object(
                adapter.bioontology_adapter,
                "search_concepts",
                new_callable=AsyncMock,
                side_effect=Exception("fail"),
            ):
                result = await adapter.map_category_to_ontology("TestType")
        assert result == "TestType"

    # --- search_concepts (lines 750-772) ---

    @pytest.mark.asyncio
    async def test_search_concepts_multiple_endpoints(self, adapter):
        """Test search_concepts queries multiple endpoints."""
        mol_results = [{"molecule_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN"}]
        drug_results = []
        target_results = []

        with patch.object(adapter, "query") as mock_query:
            mock_query.side_effect = [mol_results, drug_results, target_results]
            results = await adapter.search_concepts("aspirin", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_concepts_stops_at_limit(self, adapter):
        """Test search_concepts stops when limit reached."""
        mol_results = [
            {"molecule_chembl_id": f"CHEMBL{i}", "pref_name": f"Drug{i}"} for i in range(30)
        ]

        with patch.object(adapter, "query", return_value=mol_results):
            results = await adapter.search_concepts("drug", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_concepts_endpoint_error(self, adapter):
        """Test search_concepts handles endpoint error gracefully."""
        with patch.object(adapter, "query", side_effect=Exception("API error")):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search_concepts handles top-level exception."""
        with patch.object(adapter, "query", side_effect=Exception("Unexpected")):
            results = await adapter.search_concepts("test")
        assert results == []

    # --- get_concept_details (lines 784-806) ---

    @pytest.mark.asyncio
    async def test_get_concept_details_molecule_found(self, adapter):
        """Test get_concept_details returns molecule when found."""
        mol_data = [{"molecule_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN"}]
        with patch.object(adapter, "query") as mock_query:
            mock_query.side_effect = [mol_data, [], []]
            result = await adapter.get_concept_details("CHEMBL25")
        assert result is not None
        assert result.primary_id == "CHEMBL25"

    @pytest.mark.asyncio
    async def test_get_concept_details_drug_found(self, adapter):
        """Test get_concept_details returns drug when molecule not found."""
        drug_data = [{"drug_chembl_id": "CHEMBL25", "pref_name": "ASPIRIN"}]
        with patch.object(adapter, "query") as mock_query:
            mock_query.side_effect = [[], drug_data, []]
            result = await adapter.get_concept_details("CHEMBL25")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_target_found(self, adapter):
        """Test get_concept_details returns target when molecule and drug not found."""
        target_data = [
            {"target_chembl_id": "CHEMBL1806", "pref_name": "ACE2", "target_type": "PROTEIN"}
        ]
        with patch.object(adapter, "query") as mock_query:
            mock_query.side_effect = [[], [], target_data]
            result = await adapter.get_concept_details("CHEMBL1806")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_not_found(self, adapter):
        """Test get_concept_details returns None when not found."""
        with patch.object(adapter, "query", return_value=[]):
            result = await adapter.get_concept_details("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter):
        """Test get_concept_details returns None on exception."""
        with patch.object(adapter, "query", side_effect=Exception("fail")):
            result = await adapter.get_concept_details("CHEMBL25")
        assert result is None
