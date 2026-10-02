"""
Unit tests for EnsemblAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.adapters.ensembl_adapter import EnsemblAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestEnsemblAdapter:
    """Tests for EnsemblAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EnsemblAdapter instance."""
        return EnsemblAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test EnsemblAdapter initialization."""
        adapter = EnsemblAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.ENSEMBL
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.ENSEMBL

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
        config = LookupConfig(rate_limits={KnowledgeSource.ENSEMBL: 5.0})
        adapter = EnsemblAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_exact_symbol_match(self, adapter):
        """An exact gene symbol resolves via lookup/symbol in one request,
        without falling back to xrefs/symbol."""
        data = {"id": "ENSG00000012048", "display_name": "BRCA1"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            results = await adapter.search_concepts("BRCA1", limit=10)

        assert len(results) == 1
        assert results[0].primary_id == "ENSG00000012048"
        mock_req.assert_awaited_once()
        url = mock_req.call_args.args[0]
        assert url.endswith("/lookup/symbol/homo_sapiens/BRCA1")

    @pytest.mark.asyncio
    async def test_lookup_by_symbol_returns_concept(self, adapter):
        data = {"id": "ENSG00000012048", "display_name": "BRCA1"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            concept = await adapter._lookup_by_symbol("BRCA1")
        assert concept is not None
        assert concept.primary_id == "ENSG00000012048"

    @pytest.mark.asyncio
    async def test_lookup_by_symbol_no_id_returns_none(self, adapter):
        """A non-dict (e.g. the xrefs list shape) or missing-id response means
        no exact match — the caller should fall back to xrefs/symbol."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [{"id": "ENSG00000012048"}]
            assert await adapter._lookup_by_symbol("BRCA1") is None

    @pytest.mark.asyncio
    async def test_lookup_by_symbol_error_returns_none(self, adapter):
        """A 400 (no match) or any other failure degrades to None, not an exception."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("400 no valid lookup found")
            assert await adapter._lookup_by_symbol("p53") is None

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts falls back to xrefs/symbol when lookup/symbol
        finds no exact match, expanding each xref via get_concept_details."""
        ensembl_data = [
            {
                "id": "ENSG00000139618",
                "display_name": "BRCA2",
                "description": "BRCA2 DNA repair associated",
                "biotype": "protein_coding",
                "species": "homo_sapiens",
            },
            {
                "id": "ENSG00000139617",
                "display_name": "BRCA1",
                "description": "BRCA1 DNA repair associated",
                "biotype": "protein_coding",
                "species": "homo_sapiens",
            },
        ]

        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ensembl_data
            with patch.object(
                adapter, "get_concept_details", new_callable=AsyncMock
            ) as mock_detail:
                mock_detail.return_value = MagicMock()
                results = await adapter.search_concepts("BRCA2", limit=2)
                assert len(results) == 2
                assert mock_detail.call_count == 2

    @pytest.mark.asyncio
    async def test_search_concepts_concept_details_returns_none(self, adapter):
        """Test search when get_concept_details returns None for some results."""
        ensembl_data = [
            {"id": "ENSG00000139618"},
            {"id": "INVALID"},
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ensembl_data
            with patch.object(
                adapter, "get_concept_details", new_callable=AsyncMock
            ) as mock_detail:
                mock_detail.side_effect = [MagicMock(), None]
                results = await adapter.search_concepts("test", limit=10)
                assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_concepts_non_list_data(self, adapter):
        """Test search when API returns non-list data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"error": "bad query"}
            results = await adapter.search_concepts("bad query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_empty_list(self, adapter):
        """Test search when API returns empty list."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            results = await adapter.search_concepts("nonexistent")
            assert results == []

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
        """Test successful get_concept_details (lines 63-64)."""
        data = {"id": "ENSG00000139618", "display_name": "BRCA2"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is not None
            assert result.primary_id == "ENSG00000139618"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_id_in_data(self, adapter):
        """Test get_concept_details when data has no 'id' key."""
        data = {"display_name": "BRCA2"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling (lines 68-70)."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_data(self, adapter):
        """Test get_concept_details with empty data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_data_falsy(self, adapter):
        """Test get_concept_details when _make_request returns falsy data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            result = await adapter.get_concept_details("ENSG00000139618")
            assert result is None

    def test_convert_ensembl_result_to_concept_full(self, adapter):
        """Test _convert_ensembl_result_to_concept with all fields (lines 74-105)."""
        result = {
            "id": "ENSG00000139618",
            "display_name": "BRCA2",
            "description": "BRCA2 DNA repair associated",
            "biotype": "protein_coding",
            "species": "homo_sapiens",
        }
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "ENSG00000139618"
        assert concept.primary_label == "BRCA2"
        assert "BRCA2 DNA repair associated" in concept.definitions
        assert "Biotype: protein_coding" in concept.categories
        assert "Species: homo_sapiens" in concept.categories
        assert concept.confidence_score == 1.0

    def test_convert_ensembl_result_minimal(self, adapter):
        """Test _convert_ensembl_result_to_concept with minimal data."""
        result = {"id": "ENSG00000000001"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "ENSG00000000001"
        assert concept.primary_label == "ENSG00000000001"
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_ensembl_result_no_description_no_biotype(self, adapter):
        """Test conversion without optional fields."""
        result = {"id": "ENSG00000000001", "display_name": "GENE1"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_ensembl_result_with_description_no_biotype(self, adapter):
        """Test conversion with description but no biotype."""
        result = {"id": "ENSG00000000001", "display_name": "GENE1", "description": "A gene"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert "A gene" in concept.definitions
        assert len(concept.categories) == 0

    def test_convert_ensembl_result_with_biotype_no_description(self, adapter):
        """Test conversion with biotype but no description."""
        result = {"id": "ENSG00000000001", "display_name": "GENE1", "biotype": "lncRNA"}
        concept = adapter._convert_ensembl_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert "Biotype: lncRNA" in concept.categories

    def test_convert_ensembl_result_error(self, adapter):
        """Test _convert_ensembl_result_to_concept with bad data causing error."""
        result = {"id": None}
        adapter._convert_ensembl_result_to_concept(result)

    @pytest.mark.asyncio
    async def test_get_relationships_returns_ortholog_edges(self, adapter):
        """get_relationships exposes homology/id orthologs as edge dicts (same
        shape as KEGG/STRING/WikiPathways)."""
        homology_data = {
            "data": [
                {
                    "id": "ENSG00000012048",
                    "homologies": [
                        {
                            "type": "ortholog_one2one",
                            "target": {"id": "ENSMUSG00000017146", "species": "mus_musculus"},
                        },
                        {
                            "type": "ortholog_one2many",
                            "target": {"id": "ENSPTRG00000009123", "species": "pan_troglodytes"},
                        },
                    ],
                }
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = homology_data
            rels = await adapter.get_relationships("ENSG00000012048", limit=5)

        url, params = mock_req.call_args.args
        assert url.endswith("/homology/id/homo_sapiens/ENSG00000012048")
        assert params["type"] == "orthologues"
        assert [r["related_id"] for r in rels] == ["ENSMUSG00000017146", "ENSPTRG00000009123"]
        assert all(r["relation_label"] == "ortholog" for r in rels)
        assert all(r["source"] == "Ensembl" for r in rels)
        assert rels[0]["species"] == "mus_musculus"
        assert rels[0]["homology_type"] == "ortholog_one2one"

    @pytest.mark.asyncio
    async def test_get_relationships_respects_limit(self, adapter):
        homology_data = {
            "data": [
                {"homologies": [{"target": {"id": f"ENSG{i}", "species": "x"}} for i in range(5)]}
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = homology_data
            rels = await adapter.get_relationships("ENSG00000012048", limit=2)
        assert len(rels) == 2

    @pytest.mark.asyncio
    async def test_get_relationships_empty_on_no_data(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"data": []}
            assert await adapter.get_relationships("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_relationships_degrades_on_error(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("network down")
            assert await adapter.get_relationships("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_relationships_blank_id_returns_empty(self, adapter):
        assert await adapter.get_relationships("   ") == []

    @pytest.mark.asyncio
    async def test_get_mappings_returns_xref_mappings(self, adapter):
        """get_mappings exposes xrefs/id cross-references as mapping dicts
        (same shape as KEGGAdapter.get_mappings)."""
        xrefs_data = [
            {"dbname": "HGNC", "primary_id": "HGNC:1100", "display_id": "BRCA1"},
            {"dbname": "ArrayExpress", "primary_id": "ENSG00000012048", "display_id": "BRCA1"},
            {"dbname": "", "primary_id": "should-be-skipped"},
        ]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = xrefs_data
            mappings = await adapter.get_mappings("ENSG00000012048")

        url = mock_req.call_args.args[0]
        assert url.endswith("/xrefs/id/ENSG00000012048")
        assert len(mappings) == 2
        assert mappings[0] == {
            "fromId": "ENSG00000012048",
            "toId": "HGNC:1100",
            "fromSource": "Ensembl",
            "toSource": "HGNC",
            "mappingType": "xref",
            "confidence": 0.9,
        }

    @pytest.mark.asyncio
    async def test_get_mappings_empty_on_non_list(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"error": "boom"}
            assert await adapter.get_mappings("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_mappings_degrades_on_error(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("network down")
            assert await adapter.get_mappings("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_get_mappings_blank_id_returns_empty(self, adapter):
        assert await adapter.get_mappings("   ") == []

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass


class TestEnsemblAdapterEndpoints:
    """Tests for the full Ensembl REST catalog wrappers.

    The wrappers are deliberately thin: each test asserts the request URL,
    the query params (``None`` optionals dropped, JSON ``content-type``
    always present) and the POST body where applicable, plus that raw JSON
    is returned unmodified and exceptions propagate (the shared retry /
    circuit-breaker layer handles them, unlike the interface methods).
    """

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create EnsemblAdapter instance."""
        return EnsemblAdapter(lookup_config)

    @staticmethod
    def _last_call(mock_req):
        """Return ``(url, params, json_data)`` of the last mocked call."""
        call = mock_req.call_args
        return call.args[0], call.kwargs.get("params"), call.kwargs.get("json_data")

    # -- Archive ---------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_archive_id(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"id": "ARCH123"}
            result = await adapter.get_archive("ARCH123")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/archive/id/ARCH123")
        assert params == {"content-type": "application/json"}
        assert json_data is None
        assert result == {"id": "ARCH123"}

    # -- Comparative genomics -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_cafe_genetree_by_id(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_cafe_genetree("ENSG00000000001")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/cafe/genetree/id/ENSG00000000001")
        assert params == {"content-type": "application/json"}
        assert json_data is None

    @pytest.mark.asyncio
    async def test_cafe_genetree_by_symbol(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_cafe_genetree_by_symbol("homo_sapiens", "BRCA1")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/cafe/genetree/member/symbol/homo_sapiens/BRCA1")
        assert params == {"content-type": "application/json"}

    @pytest.mark.asyncio
    async def test_genetree(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_genetree("ENSG00000000001")
            await adapter.get_genetree_by_symbol("homo_sapiens", "BRCA1")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/genetree/id/ENSG00000000001")
        assert calls[1].args[0].endswith("/genetree/member/symbol/homo_sapiens/BRCA1")

    @pytest.mark.asyncio
    async def test_alignment_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_alignment(
                "homo_sapiens",
                "11:2159779-2159779:1",
                method="LASTZ_NET",
                alignment="Homo_sapiens.GRCh38",
                data="conservation",
                type_="dna",
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/alignment/region/homo_sapiens/11:2159779-2159779:1")
        assert params["method"] == "LASTZ_NET"
        assert params["alignment"] == "Homo_sapiens.GRCh38"
        assert params["data"] == "conservation"
        assert params["type"] == "dna"

    @pytest.mark.asyncio
    async def test_homology_by_symbol(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_homology_by_symbol(
                "homo_sapiens", "BRCA1", "orthologues", "mus_musculus"
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/homology/symbol/homo_sapiens/BRCA1")
        assert params["type"] == "orthologues"
        assert params["target_species"] == "mus_musculus"

    # -- Cross references ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_xrefs_by_name(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_xrefs_by_name("homo_sapiens", "BRCA1", "HGNC")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/xrefs/name/homo_sapiens/BRCA1")
        assert params["dbname"] == "HGNC"

    # -- Information ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_info_endpoint_urls(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_info_rest()
            await adapter.get_info_ping()
            await adapter.get_info_software()
            await adapter.get_info_data()
            await adapter.get_info_divisions()
            await adapter.get_info_variation("homo_sapiens")
            await adapter.get_info_comparas()
            await adapter.get_info_consequence_types()
            await adapter.get_info_compara_methods()
            urls = [c.args[0] for c in mock_req.call_args_list]
        for url, path in zip(
            urls,
            [
                "/info/rest",
                "/info/ping",
                "/info/software",
                "/info/data",
                "/info/divisions",
                "/info/variation/homo_sapiens",
                "/info/comparas",
                "/info/variation/consequence_types",
                "/info/compara/methods",
            ],
            strict=True,
        ):
            assert url.endswith(path)

    @pytest.mark.asyncio
    async def test_info_data_with_database(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_info_data("genomes")
        url, _, _ = self._last_call(mock_req)
        assert url.endswith("/info/data/genomes")

    @pytest.mark.asyncio
    async def test_info_species_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_info_species("homo_sapiens", format_="hash")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/info/species")
        assert params["species"] == "homo_sapiens"
        assert params["format"] == "hash"
        assert "tax_id" not in params

    @pytest.mark.asyncio
    async def test_info_assembly_biotypes_genomes_populations_analysis(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_info_assembly("homo_sapiens", region_name="1")
            await adapter.get_info_biotypes("homo_sapiens", type_="gene")
            await adapter.get_info_biotypes_by_name("protein_coding", "gene")
            await adapter.get_info_genome("homo_sapiens.GRCh38")
            await adapter.get_info_genomes_by_taxonomy("homo sapiens")
            await adapter.get_info_populations("homo_sapiens")
            await adapter.get_info_analysis("homo_sapiens")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/info/assembly/homo_sapiens/1")
        assert calls[1].args[0].endswith("/info/biotypes/homo_sapiens")
        assert calls[1].kwargs["params"]["type"] == "gene"
        assert calls[2].args[0].endswith("/info/biotypes/name/protein_coding/gene")
        assert calls[3].args[0].endswith("/info/genomes/homo_sapiens.GRCh38")
        assert calls[4].args[0].endswith("/info/genomes/taxonomy/homo sapiens")
        assert calls[5].args[0].endswith("/info/variation/populations/homo_sapiens")
        assert calls[6].args[0].endswith("/info/analysis/homo_sapiens")

    # -- Linkage disequilibrium --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ld_by_id(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ld_by_id(
                "homo_sapiens",
                "rs12345",
                "1000GENOMES:phase_3:EUR",
                window_size=500,
                r2=0.8,
            )
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/ld/homo_sapiens/rs12345/1000GENOMES:phase_3:EUR")
        assert params["window_size"] == 500
        assert params["r2"] == 0.8
        assert json_data is None

    @pytest.mark.asyncio
    async def test_ld_pairwise_and_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ld_pairwise("homo_sapiens", "rs1", "rs2")
            await adapter.get_ld_region(
                "homo_sapiens", "11:100..200", "1000GENOMES:phase_3:EUR", d_prime=0.9
            )
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/ld/homo_sapiens/pairwise/rs1/rs2")
        assert (
            calls[1]
            .args[0]
            .endswith("/ld/homo_sapiens/region/11:100..200/1000GENOMES:phase_3:EUR")
        )
        assert calls[1].kwargs["params"]["d_prime"] == 0.9
        assert "population_name" not in calls[0].kwargs["params"]

    @pytest.mark.asyncio
    async def test_ld_pairwise_population_is_query_param(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ld_pairwise(
                "homo_sapiens", "rs1", "rs2", population_name="1000GENOMES:phase_3:CEU", r2=0.5
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/ld/homo_sapiens/pairwise/rs1/rs2")
        assert params["population_name"] == "1000GENOMES:phase_3:CEU"
        assert params["r2"] == 0.5

    # -- Lookup (batch) --------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_lookup_ids_posts_ids_dict(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.lookup_ids(["ENSG00000000001", "ENSG00000000002"], expand=1, all_=1)
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/lookup/id")
        assert params["expand"] == 1
        assert params["all"] == 1
        assert json_data == {"ids": ["ENSG00000000001", "ENSG00000000002"]}

    @pytest.mark.asyncio
    async def test_lookup_symbols_posts_dict(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.lookup_symbols("homo_sapiens", ["BRCA1", "BRCA2"], expand=1)
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/lookup/symbol/homo_sapiens")
        assert params["expand"] == 1
        assert params["all"] == 0
        assert json_data == {"symbols": ["BRCA1", "BRCA2"]}

    # -- Mapping ------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_map_cdna_cds_translation(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.map_cdna("ENST00000000001", "100..200")
            await adapter.map_cds("ENST00000000001", "1..300")
            await adapter.map_translation("ENSP00000000001", "10..20")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/map/cdna/ENST00000000001/100..200")
        assert calls[1].args[0].endswith("/map/cds/ENST00000000001/1..300")
        assert calls[2].args[0].endswith("/map/translation/ENSP00000000001/10..20")
        for call in calls:
            assert call.kwargs.get("json_data") is None

    # -- Ontologies ---------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ontology_endpoints(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ontology_by_name("go")
            await adapter.get_ontology_ancestors("GO:0000001")
            await adapter.get_ontology_ancestors_chart("GO:0000001")
            await adapter.get_ontology_descendants("GO:0000001")
            await adapter.get_ontology_id("GO:0000001")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/ontology/name/go")
        assert calls[1].args[0].endswith("/ontology/ancestors/GO:0000001")
        assert calls[2].args[0].endswith("/ontology/ancestors/chart/GO:0000001")
        assert calls[3].args[0].endswith("/ontology/descendants/GO:0000001")
        assert calls[4].args[0].endswith("/ontology/id/GO:0000001")

    # -- Taxonomy -------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_taxonomy_endpoints(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_taxonomy_id(9606)
            await adapter.get_taxonomy_name("homo sapiens")
            await adapter.get_taxonomy_classification("9606")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/taxonomy/id/9606")
        assert calls[1].args[0].endswith("/taxonomy/name/homo sapiens")
        assert calls[2].args[0].endswith("/taxonomy/classification/9606")

    # -- Overlap -----------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_overlap_id(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_overlap_id("ENSG00000000001", feature="gene", all_=1, limit=50)
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/overlap/id/ENSG00000000001")
        assert params["feature"] == "gene"
        assert params["all"] == 1
        assert params["limit"] == 50
        assert "offset" not in params
        assert json_data is None

    @pytest.mark.asyncio
    async def test_overlap_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_overlap_region("homo_sapiens", "11:100-200", feature="gene")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/overlap/region/homo_sapiens/11:100-200")
        assert params["feature"] == "gene"
        assert "all" not in params
        assert "limit" not in params
        assert json_data is None

    @pytest.mark.asyncio
    async def test_overlap_translation(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_overlap_translation("ENSP00000000001", feature="cds")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/overlap/translation/ENSP00000000001")
        assert params["feature"] == "cds"
        assert "all" not in params
        assert json_data is None

    # -- Phenotype ------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_phenotype_endpoints(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_phenotypes_by_gene("homo_sapiens", "BRCA1")
            await adapter.get_phenotype_by_accession("homo_sapiens", "RGD:1234")
            await adapter.get_phenotypes_by_region("homo_sapiens", "11:100-200")
            await adapter.get_phenotypes_by_term("homo_sapiens", "cancer", limit=5, offset=2)
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/phenotype/gene/homo_sapiens/BRCA1")
        assert calls[0].kwargs["params"]["limit"] == 100
        assert calls[0].kwargs["params"]["offset"] == 1
        assert calls[1].args[0].endswith("/phenotype/accession/homo_sapiens/RGD:1234")
        assert calls[2].args[0].endswith("/phenotype/region/homo_sapiens/11:100-200")
        assert calls[3].args[0].endswith("/phenotype/term/homo_sapiens/cancer")
        assert calls[3].kwargs["params"]["limit"] == 5
        assert calls[3].kwargs["params"]["offset"] == 2

    # -- Regulation ---------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_binding_matrix(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_binding_matrix("homo_sapiens", "ENSPFM0001", min_=10, max_=20)
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/species/homo_sapiens/binding_matrix/ENSPFM0001")
        assert params["feature"] == "protein_coding"
        assert params["type"] == "all"
        assert params["limit"] == 100
        assert params["offset"] == 1
        assert params["min"] == 10
        assert params["max"] == 20

    # -- Sequence --------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sequences_posts_ids_dict(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_sequences(
                ["ENSG00000000001", "ENSG00000000002"], type_="cdna", class_="canonical"
            )
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/sequence/id")
        assert params["type"] == "cdna"
        assert params["class"] == "canonical"
        assert json_data == {"ids": ["ENSG00000000001", "ENSG00000000002"]}

    @pytest.mark.asyncio
    async def test_sequence_by_id(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_sequence_by_id("ENSG00000000001", type_="cdna")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/sequence/id/ENSG00000000001")
        assert params["type"] == "cdna"
        assert "class" not in params

    @pytest.mark.asyncio
    async def test_sequence_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_sequence("homo_sapiens", "11:100-200", class_="protein")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/sequence/region/homo_sapiens/11:100-200")
        assert params["type"] == "dna"
        assert params["class"] == "protein"

    # -- Transcript haplotypes --------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_transcript_haplotypes(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_transcript_haplotypes(
                "homo_sapiens",
                "ENST00000000001",
                assembly="GRCh38",
                population="1000genomes",
                type_="ref",
                min_=0.1,
                max_=0.9,
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/transcript_haplotypes/homo_sapiens/ENST00000000001")
        assert params["assembly"] == "GRCh38"
        assert params["population"] == "1000genomes"
        assert params["type"] == "ref"
        assert params["min"] == 0.1
        assert params["max"] == 0.9

    # -- VEP ------------------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_vep_hgvs(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.vep_hgvs("homo_sapiens", ["NG_012345.1:g.1>A"], cache=0, dir="ensembl")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/vep/homo_sapiens/hgvs")
        assert params["cache"] == 0
        assert params["dir"] == "ensembl"
        assert json_data == {"hgvs_notations": ["NG_012345.1:g.1>A"]}

    @pytest.mark.asyncio
    async def test_vep_ids_and_regions(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.vep_ids("homo_sapiens", ["1234"])
            await adapter.vep_regions("homo_sapiens", ["11 100 100 A/G 1"])
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/vep/homo_sapiens/id")
        assert calls[0].kwargs["json_data"] == {"ids": ["1234"]}
        assert calls[1].args[0].endswith("/vep/homo_sapiens/region")
        assert calls[1].kwargs["json_data"] == {"variants": ["11 100 100 A/G 1"]}

    @pytest.mark.asyncio
    async def test_vep_single_endpoints(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_vep_id("homo_sapiens", "rs123", canonical=1)
            await adapter.get_vep_hgvs("homo_sapiens", "ENST00000000001:c.1A>T", hgvs=1)
            await adapter.get_vep_region("homo_sapiens", "11:100-200", "A", canonical=1)
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/vep/homo_sapiens/id/rs123")
        # _params always injects the JSON content-type param Ensembl expects
        assert calls[0].kwargs["params"] == {"content-type": "application/json", "canonical": 1}
        # HGVS strings are percent-encoded into the path segment
        assert calls[1].args[0].endswith("/vep/homo_sapiens/hgvs/ENST00000000001%3Ac.1A%3ET")
        assert calls[1].kwargs["params"] == {"content-type": "application/json", "hgvs": 1}
        assert calls[2].args[0].endswith("/vep/homo_sapiens/region/11:100-200/A")
        assert calls[2].kwargs["params"] == {"content-type": "application/json", "canonical": 1}

    # -- Variation ----------------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_variation_single_and_batch(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_variation("homo_sapiens", "rs123", pops=1)
            await adapter.get_variations_by_ids("homo_sapiens", ["rs123", "rs456"])
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/variation/homo_sapiens/rs123")
        assert calls[0].kwargs["params"] == {"content-type": "application/json", "pops": 1}
        assert calls[1].args[0].endswith("/variation/homo_sapiens")
        assert calls[1].kwargs["json_data"] == {"ids": ["rs123", "rs456"]}

    @pytest.mark.asyncio
    async def test_variations_by_article(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_variations_by_pmcid("homo_sapiens", "PMC12345")
            await adapter.get_variations_by_pmid("homo_sapiens", "12345678", limit=5, offset=2)
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/variation/homo_sapiens/pmcid/PMC12345")
        assert calls[0].kwargs["params"] == {
            "content-type": "application/json",
            "limit": 10,
            "offset": 1,
        }
        assert calls[1].args[0].endswith("/variation/homo_sapiens/pmid/12345678")
        assert calls[1].kwargs["params"] == {
            "content-type": "application/json",
            "limit": 5,
            "offset": 2,
        }

    @pytest.mark.asyncio
    async def test_variant_recoder(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_variant_recoder("homo_sapiens", "rs123")
            await adapter.variant_recoder("homo_sapiens", ["ENST00000000001.1:c.1A>T"])
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/variant_recoder/homo_sapiens/rs123")
        assert calls[1].args[0].endswith("/variant_recoder/homo_sapiens")
        assert calls[1].kwargs["json_data"] == {"ids": ["ENST00000000001.1:c.1A>T"]}

    # -- GA4GH ------------------------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ga4gh_single_and_search(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.ga4gh_callsets("CS1")
            await adapter.ga4gh_get_dataset("DS1")
            await adapter.ga4gh_search_datasets()
            await adapter.ga4gh_search_variants(variantSetId="VS1")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/ga4gh/callsets/CS1")
        assert calls[1].args[0].endswith("/ga4gh/datasets/DS1")
        # empty searches are normalised to a minimal paged request
        assert calls[2].args[0].endswith("/ga4gh/datasets/search")
        assert calls[2].kwargs["json_data"] == {"pageSize": 1}
        assert calls[3].args[0].endswith("/ga4gh/variants/search")
        assert calls[3].kwargs["json_data"] == {"variantSetId": "VS1"}

    @pytest.mark.asyncio
    async def test_ga4gh_beacon(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.ga4gh_beacon()
            await adapter.ga4gh_beacon_query("1", 1000, "G", "A")
            await adapter.ga4gh_beacon_query_post({"referenceName": "1", "start": 1000})
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/ga4gh/beacon")
        assert calls[1].args[0].endswith("/ga4gh/beacon/query")
        assert calls[1].kwargs["params"] == {
            "content-type": "application/json",
            "referenceName": "1",
            "start": 1000,
            "referenceBases": "G",
            "alternateBases": "A",
            "assemblyId": "GRCh38",
        }
        assert calls[2].args[0].endswith("/ga4gh/beacon/query")
        assert calls[2].kwargs["json_data"] == {"referenceName": "1", "start": 1000}

    # -- Error handling ------------------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_endpoints_propagate_errors(self, adapter):
        """Endpoint wrappers do not swallow errors — retry / breaker handle them."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("network down")
            with pytest.raises(Exception, match="network down"):
                await adapter.get_archive("ARCH123")
            with pytest.raises(Exception, match="network down"):
                await adapter.lookup_ids(["ENSG00000000001"])
