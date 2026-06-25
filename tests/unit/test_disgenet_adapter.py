"""
Unit tests for DisGeNETAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.disgenet_adapter import DisGeNETAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestDisGeNETAdapter:
    """Tests for DisGeNETAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create DisGeNETAdapter instance."""
        return DisGeNETAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create DisGeNETAdapter with API key."""
        config = LookupConfig(api_keys={"disgenet": "test_api_key"})
        return DisGeNETAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test DisGeNETAdapter initialization."""
        adapter = DisGeNETAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.DISGENET
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.DISGENET

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
        config = LookupConfig(rate_limits={KnowledgeSource.DISGENET: 5.0})
        adapter = DisGeNETAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, adapter_with_api_key):
        """Test successful search concepts."""
        data = {
            "payload": [
                {"diseaseid": "DOID:162", "diseasename": "Diabetes", "score": 0.5},
            ]
        }
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            results = await adapter_with_api_key.search_concepts("7157", limit=10)
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_concepts_empty_response(self, adapter_with_api_key):
        """Test search concepts with empty response."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = None
            results = await adapter_with_api_key.search_concepts("nonexistent", limit=10)
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error returns empty list."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            results = await adapter.search_concepts("test")
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_http_error(self, adapter):
        """Test search concepts with HTTP error returns empty list."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("HTTP 500")
            results = await adapter.search_concepts("test")
            assert isinstance(results, list)
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
            pass  # Should not raise any exceptions

    # --- Additional tests to cover missing lines (22, 43-51, 68-73, 75-76, 127-162, 199-244, 257-270) ---

    def test_is_available_with_api_key(self, adapter_with_api_key):
        """Test is_available when API key is present."""
        assert adapter_with_api_key.is_available() is True

    def test_is_available_without_api_key(self):
        """Test is_available when API key is definitely missing."""
        config = LookupConfig(api_keys={})
        with patch("os.getenv", return_value=None):
            adapter_no_key = DisGeNETAdapter(config)
            assert adapter_no_key.is_available() is False

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter_with_api_key):
        """Test get_concept_details with successful response (lines 43-51)."""
        disease_data = {
            "diseaseid": "DOID:162",
            "diseasename": "Diabetes mellitus",
        }
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = disease_data
            result = await adapter_with_api_key.get_concept_details("DOID:162")
            assert result is not None
            assert result.primary_id == "DOID:162"
            assert result.primary_label == "Diabetes mellitus"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_data(self, adapter_with_api_key):
        """Test get_concept_details when no data returned."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = None
            result = await adapter_with_api_key.get_concept_details("DOID:162")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_diseaseid(self, adapter_with_api_key):
        """Test get_concept_details when diseaseid not in response."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"diseasename": "Test"}
            result = await adapter_with_api_key.get_concept_details("DOID:162")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_diseaseid(self, adapter_with_api_key):
        """Test get_concept_details when diseaseid not in response."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"diseasename": "Test"}
            result = await adapter_with_api_key.get_concept_details("DOID:162")
            assert result is None

    @pytest.mark.asyncio
    async def test_make_request_rate_limit_retry(self, adapter_with_api_key):
        """Test _make_request rate limit retry (lines 68-73)."""
        import aiohttp

        def raise_for_status():
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=429, message="rate limited"
            )

        response_429 = AsyncMock()
        response_429.status = 429
        response_429.raise_for_status = raise_for_status

        response_200 = AsyncMock()
        response_200.status = 200
        response_200.json = AsyncMock(return_value={"result": "success"})

        ctx_429 = AsyncMock()
        ctx_429.__aenter__ = AsyncMock(return_value=response_429)
        ctx_429.__aexit__ = AsyncMock(return_value=False)

        ctx_200 = AsyncMock()
        ctx_200.__aenter__ = AsyncMock(return_value=response_200)
        ctx_200.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=[ctx_429, ctx_200])

        with patch.object(
            adapter_with_api_key, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_get_session.return_value = mock_session
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await adapter_with_api_key._make_request("http://test.com/api")
                assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_make_request_http_error(self, adapter_with_api_key):
        """Test _make_request with HTTP error raises after retries."""
        import aiohttp

        def raise_for_status():
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=500, message="server error"
            )

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = raise_for_status

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_response)
        ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=ctx)

        with patch.object(
            adapter_with_api_key, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_get_session.return_value = mock_session
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(aiohttp.ClientResponseError):
                    await adapter_with_api_key._make_request("http://test.com/api")

    @pytest.mark.asyncio
    async def test_make_request_exception(self, adapter_with_api_key):
        """Test _make_request exception propagation after retries exhausted."""
        with patch.object(
            adapter_with_api_key, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_get_session.side_effect = Exception("Network error")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="Network error"):
                    await adapter_with_api_key._make_request("http://test.com/api")

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_success(self, adapter_with_api_key):
        """Test get_gene_disease_associations with parsed results (lines 127-162)."""
        data = {
            "payload": [
                {
                    "assocID": "123",
                    "symbolOfGene": "TP53",
                    "geneNcbiID": "7157",
                    "geneEnsemblIDs": ["ENSG00000141510"],
                    "geneNcbiType": "protein-coding",
                    "diseaseName": "Cancer",
                    "diseaseUMLSCUI": "C0006847",
                    "score": 0.5,
                    "yearInitial": 2000,
                    "yearFinal": 2020,
                    "numPMIDs": 100,
                    "numCTsupportingAssociation": 5,
                    "geneDSI": 0.5,
                    "geneDPI": 0.6,
                    "genepLI": 0.7,
                    "geneProteinStrIDs": [],
                    "geneProteinClassNames": [],
                    "diseaseClasses_MSH": [],
                    "diseaseClasses_UMLS_ST": [],
                    "diseaseClasses_DO": [],
                    "diseaseClasses_HPO": [],
                    "disease_prevalence_class": "requent",
                    "disease_prevalence_geo_area": "global",
                    "disease_prevalence_type": "point",
                    "disease_inheritance": "autosomal dominant",
                    "ei": 0.8,
                    "el": 0.9,
                }
            ]
        }
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            result = await adapter_with_api_key.get_gene_disease_associations(
                {"gene_ncbi_id": "7157"}
            )
            assert len(result) == 1
            assert result[0]["gene_symbol"] == "TP53"

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_raw(self, adapter_with_api_key):
        """Test get_gene_disease_associations with raw=True."""
        data = {"payload": [{"assocID": "123"}]}
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            result = await adapter_with_api_key.get_gene_disease_associations(
                {"gene_ncbi_id": "7157"}, raw=True
            )
            assert result == data

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_no_data(self, adapter_with_api_key):
        """Test get_gene_disease_associations when no data returned."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = None
            result = await adapter_with_api_key.get_gene_disease_associations(
                {"gene_ncbi_id": "7157"}
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_no_payload(self, adapter_with_api_key):
        """Test get_gene_disease_associations when no payload in response."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = {"error": "bad request"}
            result = await adapter_with_api_key.get_gene_disease_associations(
                {"gene_ncbi_id": "7157"}
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_evidence_success(self, adapter_with_api_key):
        """Test get_gene_disease_associations_evidence with parsed results (lines 199-244)."""
        data = {
            "payload": [
                {
                    "assocID": "123",
                    "symbolOfGene": "TP53",
                    "geneNcbiID": "7157",
                    "geneEnsemblIDs": ["ENSG00000141510"],
                    "geneNcbiType": "protein-coding",
                    "diseaseName": "Cancer",
                    "diseaseUMLSCUI": "C0006847",
                    "score": 0.5,
                    "yearInitial": 2000,
                    "yearFinal": 2020,
                    "numPMIDs": 100,
                    "numCTsupportingAssociation": 5,
                    "geneDSI": 0.5,
                    "geneDPI": 0.6,
                    "genepLI": 0.7,
                    "geneProteinStrIDs": [],
                    "geneProteinClassNames": [],
                    "diseaseClasses_MSH": [],
                    "diseaseClasses_UMLS_ST": [],
                    "diseaseClasses_DO": [],
                    "diseaseClasses_HPO": [],
                    "disease_prevalence_class": "requent",
                    "disease_prevalence_geo_area": "global",
                    "disease_prevalence_type": "point",
                    "disease_inheritance": "autosomal dominant",
                    "ei": 0.8,
                    "el": 0.9,
                }
            ]
        }
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            result = await adapter_with_api_key.get_gene_disease_associations_evidence(
                {"gene_ncbi_id": "7157"}
            )
            assert len(result) == 1
            assert result[0]["gene_symbol"] == "TP53"

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_evidence_raw(self, adapter_with_api_key):
        """Test get_gene_disease_associations_evidence with raw=True."""
        data = {"payload": [{"assocID": "123"}]}
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            result = await adapter_with_api_key.get_gene_disease_associations_evidence(
                {"gene_ncbi_id": "7157"}, raw=True
            )
            assert result == data

    @pytest.mark.asyncio
    async def test_get_gene_disease_associations_evidence_no_data(self, adapter_with_api_key):
        """Test get_gene_disease_associations_evidence when no data."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = None
            result = await adapter_with_api_key.get_gene_disease_associations_evidence(
                {"gene_ncbi_id": "7157"}
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter_with_api_key):
        """Test search_concepts with actual results (lines 257-270)."""
        data = {
            "payload": [
                {
                    "diseaseid": "DOID:162",
                    "diseasename": "Diabetes mellitus",
                    "score": 0.5,
                },
                {
                    "diseaseid": "DOID:9351",
                    "diseasename": "Type 2 diabetes",
                    "score": 0.7,
                },
            ]
        }
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            concepts = await adapter_with_api_key.search_concepts("7157", limit=2)
            assert len(concepts) == 2
            assert concepts[0].primary_id == "DOID:162"

    @pytest.mark.asyncio
    async def test_search_concepts_limit(self, adapter_with_api_key):
        """Test search respects limit."""
        data = {
            "payload": [
                {"diseaseid": f"DOID:{i}", "diseasename": f"Disease {i}", "score": 0.5}
                for i in range(5)
            ]
        }
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = data
            concepts = await adapter_with_api_key.search_concepts("7157", limit=2)
            assert len(concepts) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_no_data(self, adapter_with_api_key):
        """Test search when no data returned."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = None
            concepts = await adapter_with_api_key.search_concepts("7157")
            assert concepts == []
