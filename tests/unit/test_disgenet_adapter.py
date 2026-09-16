"""
Unit tests for DisGeNETAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.adapters.disgenet_adapter import DisGeNETAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


def _response(*rows):
    """Shape of a DisGeNET v1 response (academic profile)."""
    return {
        "status": "OK",
        "paging": {
            "pageSize": 100,
            "totalElements": len(rows),
            "totalElementsInPage": len(rows),
            "currentPageNumber": 0,
        },
        "warnings": ["Academic roles can only access to CURATED sources: (CLINVAR, ...)"],
        "userinfo": {"profile": "ACADEMIC"},
        "payload": list(rows),
    }


def _disease_entity(cui="C0004096", name="Asthma", **extra):
    """Row of /entity/disease."""
    return {
        "diseaseClasses_MSH": ["Respiratory Tract Diseases (C08)", "Immune System Diseases (C20)"],
        "diseaseClasses_UMLS_ST": ["Disease or Syndrome (T047)"],
        "diseaseClasses_DO": ["disease of anatomical entity (7)"],
        "diseaseClasses_HPO": [],
        "name": name,
        "diseaseUMLSCUI": cui,
        "type": "disease",
        "diseaseCodes": [
            {"vocabulary": "MONDO", "code": "0004979"},
            {"vocabulary": "UMLS", "code": cui},
        ],
        "synonyms": [
            {"name": name, "isPTI": False},
            {"name": "Bronchial asthma, NOS", "isPTI": False},
            {"name": "BRONCHIAL ASTHMA", "isPTI": True},
        ],
        **extra,
    }


def _gda_row(cui="C0677776", disease="Hereditary Breast and Ovarian Cancer Syndrome", score=0.9):
    """Row of /gda/summary (no ``diseaseid`` / ``diseasename`` fields)."""
    return {
        "assocID": "x5SCdp4Bu8jCkiVmyEkl",
        "symbolOfGene": "BRCA1",
        "geneNcbiID": 672,
        "geneEnsemblIDs": ["ENSG00000012048"],
        "geneNcbiType": "protein-coding",
        "diseaseVocabularies": [f"UMLS_{cui}"],
        "diseaseName": disease,
        "diseaseType": "[disease]",
        "diseaseUMLSCUI": cui,
        "diseaseClasses_MSH": ["Neoplasms (C04)"],
        "diseaseClasses_UMLS_ST": ["Neoplastic Process (T191)"],
        "score": score,
        "numPMIDs": 15,
    }


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

    # --- search_concepts ---

    @pytest.mark.asyncio
    async def test_search_concepts_disease_name(self, adapter_with_api_key):
        """Free-text queries use /entity/disease and return DISEASE concepts."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response(
                _disease_entity(), _disease_entity("C0155877", "Allergic asthma")
            )
            results = await adapter_with_api_key.search_concepts("asthma", limit=10)

        assert [c.primary_id for c in results] == ["UMLS_C0004096", "UMLS_C0155877"]
        asthma = results[0]
        assert asthma.primary_label == "Asthma"
        assert asthma.concept_type == ConceptType.DISEASE
        assert asthma.synonyms == ["Bronchial asthma, NOS", "BRONCHIAL ASTHMA"]
        assert asthma.semantic_types == ["Disease or Syndrome (T047)"]
        assert "Respiratory Tract Diseases (C08)" in asthma.categories
        assert asthma.identifiers[0].identifier == "UMLS_C0004096"
        assert asthma.sources == [KnowledgeSource.DISGENET]

        mock_req.assert_awaited_once()
        assert mock_req.call_args.args[0].endswith("/entity/disease")
        assert mock_req.call_args.kwargs["params"] == {
            "disease_free_text_search_string": "asthma",
            "page_number": 0,
        }
        assert mock_req.call_args.kwargs["headers"]["Authorization"] == "test_api_key"

    @pytest.mark.asyncio
    async def test_search_concepts_reads_current_gda_fields(self, adapter_with_api_key):
        """Regression: v1 GDA rows carry diseaseUMLSCUI/diseaseName, not diseaseid."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response(
                _gda_row(score=0.9), _gda_row("C0376358", "Malignant neoplasm of prostate", 1.35)
            )
            results = await adapter_with_api_key.search_concepts("BRCA1", limit=10)

        assert [c.primary_id for c in results] == ["UMLS_C0677776", "UMLS_C0376358"]
        assert results[0].primary_label == "Hereditary Breast and Ovarian Cancer Syndrome"
        assert results[0].concept_type == ConceptType.DISEASE
        assert results[0].confidence_score == 0.9
        assert results[1].confidence_score == 1.0  # scores above 1 are clamped
        assert results[0].related == ["BRCA1"]
        assert mock_req.call_args.args[0].endswith("/gda/summary")
        assert mock_req.call_args.kwargs["params"] == {"gene_symbol": "BRCA1", "page_number": 0}

    @pytest.mark.asyncio
    async def test_search_concepts_ncbi_gene_id(self, adapter_with_api_key):
        """All-digit queries are NCBI gene IDs; no disease-name fallback."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response()
            results = await adapter_with_api_key.search_concepts("1017", limit=10)
        assert results == []
        mock_req.assert_awaited_once()
        assert mock_req.call_args.kwargs["params"] == {"gene_ncbi_id": "1017", "page_number": 0}

    @pytest.mark.asyncio
    async def test_search_concepts_symbol_falls_back_to_disease_name(self, adapter_with_api_key):
        """Symbol-like disease names (COPD) fall back to the disease name search."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = [
                _response(),
                _response(_disease_entity("C0024117", "Chronic Obstructive Airway Disease")),
            ]
            results = await adapter_with_api_key.search_concepts("COPD", limit=10)
        assert [c.primary_id for c in results] == ["UMLS_C0024117"]
        first, second = mock_req.call_args_list
        assert first.kwargs["params"] == {"gene_symbol": "COPD", "page_number": 0}
        assert second.kwargs["params"]["disease_free_text_search_string"] == "COPD"

    @pytest.mark.asyncio
    async def test_search_concepts_limit(self, adapter_with_api_key):
        """Test search respects limit."""
        rows = [_disease_entity(f"C000000{i}", f"Disease {i}") for i in range(5)]
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response(*rows)
            concepts = await adapter_with_api_key.search_concepts("disease", limit=2)
            assert len(concepts) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_skips_incomplete_rows(self, adapter_with_api_key):
        """Rows without a CUI or name are skipped instead of producing empty IDs."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response(
                {"diseaseid": "DOID:162", "diseasename": "Diabetes", "score": 0.5},
                _disease_entity(),
            )
            concepts = await adapter_with_api_key.search_concepts("asthma", limit=10)
        assert [c.primary_id for c in concepts] == ["UMLS_C0004096"]

    @pytest.mark.asyncio
    async def test_search_concepts_empty_query(self, adapter_with_api_key):
        """A blank query returns [] without a request."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            assert await adapter_with_api_key.search_concepts("  ") == []
        mock_req.assert_not_awaited()

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

    def test_is_available_with_api_key(self, adapter_with_api_key):
        """Test is_available when API key is present."""
        assert adapter_with_api_key.is_available() is True

    def test_is_available_without_api_key(self):
        """Test is_available when API key is definitely missing."""
        config = LookupConfig(api_keys={})
        with patch("os.getenv", return_value=None):
            adapter_no_key = DisGeNETAdapter(config)
            assert adapter_no_key.is_available() is False

    # --- get_concept_details ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("concept_id", "expected_param"),
        [
            ("UMLS_C0004096", "UMLS_C0004096"),
            ("C0004096", "UMLS_C0004096"),
            ("UMLS:C0004096", "UMLS_C0004096"),
            ("mondo:0004979", "MONDO_0004979"),
            ("MONDO_0004979", "MONDO_0004979"),
        ],
    )
    async def test_get_concept_details_success(
        self, adapter_with_api_key, concept_id, expected_param
    ):
        """Details use /entity/disease?disease=<VOCAB>_<code> (not /disease/{id})."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response(_disease_entity())
            result = await adapter_with_api_key.get_concept_details(concept_id)

        assert result is not None
        assert result.primary_id == "UMLS_C0004096"
        assert result.primary_label == "Asthma"
        assert result.concept_type == ConceptType.DISEASE
        url = mock_req.call_args.args[0]
        assert url.endswith("/entity/disease")
        assert "/disease/" not in url
        assert mock_req.call_args.kwargs["params"] == {"disease": expected_param}

    @pytest.mark.asyncio
    async def test_get_concept_details_picks_matching_cui(self, adapter_with_api_key):
        """When several rows come back, the one with the requested CUI wins."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response(
                _disease_entity("C0155877", "Allergic asthma"), _disease_entity()
            )
            result = await adapter_with_api_key.get_concept_details("UMLS_C0004096")
        assert result.primary_label == "Asthma"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_data(self, adapter_with_api_key):
        """Test get_concept_details when no data returned."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = None
            result = await adapter_with_api_key.get_concept_details("UMLS_C0004096")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_unknown_disease(self, adapter_with_api_key):
        """Unknown IDs come back as an empty payload."""
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = _response()
            result = await adapter_with_api_key.get_concept_details("UMLS_C9999999")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error_returns_none(self, adapter_with_api_key):
        """Regression: HTTP errors are logged and give None instead of raising."""
        import aiohttp

        error = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=404, message="Resource not found"
        )
        with patch.object(
            adapter_with_api_key, "_make_request", new_callable=AsyncMock, side_effect=error
        ):
            result = await adapter_with_api_key.get_concept_details("C0011849")
        assert result is None

    # --- _make_request ---

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

    # --- gene-disease associations ---

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
