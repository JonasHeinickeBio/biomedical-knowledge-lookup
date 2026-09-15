"""
Unit tests for ClinVarAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from knowledge_lookup.adapters.clinvar_adapter import ClinVarAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestClinVarAdapter:
    """Tests for ClinVarAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create ClinVarAdapter instance."""
        return ClinVarAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test ClinVarAdapter initialization."""
        adapter = ClinVarAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.CLINVAR
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.CLINVAR

    def test_is_available(self, adapter):
        """Test is_available returns True (public API)."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.CLINVAR: 3.0})
        adapter = ClinVarAdapter(config)
        assert adapter.get_rate_limit() == 3.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        # First call: esearch
        esearch_response = AsyncMock()
        esearch_response.status = 200
        esearch_response.raise_for_status = MagicMock()
        esearch_response.json = AsyncMock(return_value={"esearchresult": {"idlist": ["12345"]}})

        # Second call: esummary
        esummary_response = AsyncMock()
        esummary_response.status = 200
        esummary_response.raise_for_status = MagicMock()
        esummary_response.json = AsyncMock(
            return_value={
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "uid": "12345",
                        "title": "NM_000492.4(CFTR):c.1521_1523delCTT (p.Phe508del)",
                        "clinical_significance": {"description": "Pathogenic"},
                        "obj_type": "single nucleotide variant",
                    },
                }
            }
        )

        mock_get.return_value.__aenter__.side_effect = [esearch_response, esummary_response]

        results = await adapter.search_concepts("CFTR", limit=5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert "ClinVar:12345" == results[0].primary_id

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty ID list."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"esearchresult": {"idlist": []}})
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_http_error(self, mock_get, adapter):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500, message="Internal Server Error"
            )
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_network_error(self, mock_get, adapter):
        """Test search concepts with network error."""
        mock_get.side_effect = Exception("Network error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_success(self, mock_get, adapter):
        """Test get_concept_details with valid ID."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "uid": "12345",
                        "title": "CFTR variant",
                        "clinical_significance": {"description": "Pathogenic"},
                    },
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("ClinVar:12345")
        assert result is not None
        assert result.primary_id == "ClinVar:12345"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_not_found(self, mock_get, adapter):
        """Test get_concept_details when result is not found."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"result": {"uids": []}})
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await adapter.get_concept_details("ClinVar:99999")
        assert result is None

    @staticmethod
    def _esummary_item():
        """Trimmed esummary record for ClinVar variation 17661 (current format)."""
        return {
            "uid": "17661",
            "obj_type": "single nucleotide variant",
            "accession": "VCV000017661",
            "accession_version": "VCV000017661.162",
            "title": "NM_007294.4(BRCA1):c.181T>G (p.Cys61Gly)",
            "germline_classification": {
                "description": "Pathogenic",
                "last_evaluated": "2015/08/10 00:00",
                "review_status": "reviewed by expert panel",
                "fda_recognized_database": "",
                "trait_set": [
                    {
                        "trait_xrefs": [{"db_source": "MONDO", "db_id": "MONDO:0011450"}],
                        "trait_name": "Breast-ovarian cancer, familial, susceptibility to, 1",
                    }
                ],
            },
            "clinical_impact_classification": {
                "description": "",
                "last_evaluated": "1/01/01 00:00",
                "review_status": "",
                "fda_recognized_database": "",
                "trait_set": [],
            },
            "oncogenicity_classification": {
                "description": "",
                "last_evaluated": "1/01/01 00:00",
                "review_status": "",
                "fda_recognized_database": "",
                "trait_set": [],
            },
            "record_status": "",
            "gene_sort": "BRCA1",
            "genes": [{"symbol": "BRCA1", "geneid": "672", "strand": "-", "source": "submitted"}],
            "molecular_consequence_list": ["missense variant", "non-coding transcript variant"],
            "protein_change": "C61G, C14G",
        }

    def test_convert_reads_germline_classification(self, adapter):
        """Regression: current records carry significance under germline_classification."""
        concept = adapter._convert_result_to_concept(self._esummary_item())
        assert concept is not None
        assert concept.primary_id == "ClinVar:17661"
        assert "clinical_significance:Pathogenic" in concept.categories
        assert "review_status:reviewed by expert panel" in concept.categories
        assert (
            "condition:Breast-ovarian cancer, familial, susceptibility to, 1" in concept.categories
        )
        assert "gene:BRCA1" in concept.categories
        assert concept.semantic_types[0] == "single nucleotide variant"
        assert "missense variant" in concept.semantic_types
        # Empty somatic classifications add nothing
        assert not any(
            c.startswith(("clinical_impact:", "oncogenicity:")) for c in concept.categories
        )

    def test_convert_reads_somatic_classifications(self, adapter):
        """Oncogenicity / clinical impact classifications are reported when present."""
        item = self._esummary_item()
        item["germline_classification"]["description"] = ""
        item["germline_classification"]["trait_set"] = []
        item["oncogenicity_classification"] = {
            "description": "Oncogenic",
            "review_status": "criteria provided, single submitter",
            "trait_set": [{"trait_name": "Breast neoplasm"}],
        }
        concept = adapter._convert_result_to_concept(item)
        assert "oncogenicity:Oncogenic" in concept.categories
        assert "condition:Breast neoplasm" in concept.categories
        assert not any(c.startswith("clinical_significance:") for c in concept.categories)

    def test_convert_reads_legacy_clinical_significance(self, adapter):
        """Older payloads with clinical_significance / top-level trait_set still work."""
        concept = adapter._convert_result_to_concept(
            {
                "uid": "12345",
                "title": "CFTR variant",
                "clinical_significance": {"description": "Pathogenic"},
                "trait_set": [{"trait_name": "Cystic fibrosis"}],
            }
        )
        assert "clinical_significance:Pathogenic" in concept.categories
        assert "condition:Cystic fibrosis" in concept.categories

    def test_convert_esummary_error_item_returns_none(self, adapter):
        """esummary reports unknown IDs as {"uid": ..., "error": ...}."""
        item = {"uid": "999999999", "error": "cannot get document summary"}
        assert adapter._convert_result_to_concept(item) is None

    @pytest.mark.asyncio
    async def test_get_concept_details_germline_classification(self, adapter):
        """get_concept_details returns significance and conditions for current records."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {
                "header": {"type": "esummary", "version": "0.3"},
                "result": {"uids": ["17661"], "17661": self._esummary_item()},
            }
            result = await adapter.get_concept_details("VCV000017661")
        assert mock_req.call_args.args[1]["id"] == "000017661"
        assert "clinical_significance:Pathogenic" in result.categories

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("ClinVar:12345")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions
