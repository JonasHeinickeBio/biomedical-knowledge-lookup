"""
Unit tests for EnsemblAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.ensembl_adapter import EnsemblAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


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
                {
                    "homologies": [
                        {"target": {"id": f"ENSG{i}", "species": "x"}} for i in range(5)
                    ]
                }
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
    async def test_cafes_sends_all_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_cafes(
                "homo_sapiens",
                limit=10,
                offset=5,
                cafe_type="expansion",
                tax_id=9606,
                min_count=1,
                max_count=9,
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/cafe/genetree/homo_sapiens")
        assert params["limit"] == 10
        assert params["offset"] == 5
        assert params["type"] == "expansion"
        assert params["tax_id"] == 9606
        assert params["min"] == 1
        assert params["max"] == 9

    @pytest.mark.asyncio
    async def test_cafes_drops_none_optionals(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_cafes("homo_sapiens")
        _, params, _ = self._last_call(mock_req)
        for key in ("type", "tax_id", "min", "max"):
            assert key not in params
        assert params["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_genetree(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_genetree(9606)
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/genetree/9606")
        assert params == {"content-type": "application/json"}

    @pytest.mark.asyncio
    async def test_alignment_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_alignment(
                "homo_sapiens", "11", 100, 200, 10, 20,
                alignment="clustal", method="net", data="conservation", type_="dna",
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/alignment/region/homo_sapiens/11/100/200/10/20")
        assert params["alignment"] == "clustal"
        assert params["method"] == "net"
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
        url, _, _ = self._last_call(mock_req)
        assert url.endswith("/xrefs/name/homo_sapiens/BRCA1/HGNC")

    # -- Information ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_info_endpoint_urls(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_info_rest()
            await adapter.get_info_ping()
            await adapter.get_info_software()
            await adapter.get_info_data()
            await adapter.get_info_divisions()
            await adapter.get_info_variation()
            await adapter.get_info_compara()
            urls = [c.args[0] for c in mock_req.call_args_list]
        for url, path in zip(
            urls,
            [
                "/info/rest",
                "/info/ping",
                "/info/software",
                "/info/data",
                "/info/divisions",
                "/info/variation",
                "/info/compara",
            ],
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
            await adapter.get_info_assembly("homo_sapiens")
            await adapter.get_info_biotypes(type_="gene")
            await adapter.get_info_genomes(9606)
            await adapter.get_info_populations()
            await adapter.get_info_analysis("homo_sapiens")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/info/assembly")
        assert calls[1].args[0].endswith("/info/biotypes")
        assert calls[2].args[0].endswith("/info/genomes")
        assert calls[3].args[0].endswith("/info/populations")
        assert calls[4].args[0].endswith("/info/analysis")
        assert calls[0].kwargs["params"]["species"] == "homo_sapiens"
        assert calls[1].kwargs["params"]["type"] == "gene"
        assert calls[2].kwargs["params"]["tax_id"] == 9606
        assert "tax_id" not in calls[3].kwargs["params"]
        assert calls[4].kwargs["params"]["species"] == "homo_sapiens"

    # -- Linkage disequilibrium --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ld_requires_region_or_seq_id(self, adapter):
        with pytest.raises(ValueError, match="seq_region or seq_id"):
            await adapter.get_ld("homo_sapiens")

    @pytest.mark.asyncio
    async def test_ld_seq_id_fallback_and_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ld("homo_sapiens", seq_id="11")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/ld/homo_sapiens/11")
        assert params["window"] == 2000
        assert params["ld"] == "r"
        assert params["limit"] == 2000
        assert params["offset"] == 1

    # -- Lookup (batch) --------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_lookup_ids_posts_array(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.lookup_ids(["ENSG00000000001", "ENSG00000000002"], expand=1, all_=1)
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/lookup/id")
        assert params["expand"] == 1
        assert params["all"] == 1
        assert json_data == ["ENSG00000000001", "ENSG00000000002"]

    @pytest.mark.asyncio
    async def test_lookup_symbols_posts_array(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.lookup_symbols("homo_sapiens", ["BRCA1", "BRCA2"])
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/lookup/symbol")
        assert params["species"] == "homo_sapiens"
        assert json_data == ["BRCA1", "BRCA2"]

    # -- Mapping ------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_map_cdna_get_with_single_type(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.map_cdna("X_99999", type_="exon,transcript")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/map/cdna/X_99999")
        assert params["type"] == "exon,transcript"
        assert json_data is None

    @pytest.mark.asyncio
    async def test_map_cdna_posts_types_array(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.map_cdna("X_99999", types=["exon", "transcript"])
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/map/cdna/X_99999")
        assert json_data == ["exon", "transcript"]
        assert "type" not in params

    @pytest.mark.asyncio
    async def test_map_cds_and_translation(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.map_cds("NC_000011.10")
            await adapter.map_translation("ENSP00000000001", types=["exon"])
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/map/cds/NC_000011.10")
        assert calls[0].kwargs.get("json_data") is None
        assert calls[1].args[0].endswith("/map/translation/ENSP00000000001")
        assert calls[1].kwargs["json_data"] == ["exon"]

    @pytest.mark.asyncio
    async def test_map_ids_posts_dict(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.map_ids("homo_sapiens", ["ENSG00000000001"], "protein")
        url, _, json_data = self._last_call(mock_req)
        assert url.endswith("/map/homo_sapiens")
        assert json_data == {"id": ["ENSG00000000001"], "target": "protein"}

    # -- Ontologies ---------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ontology_search_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ontology(
                "go", term="kinase", type_="molecular_function", id_="GO:0000001"
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/ontology/go")
        assert params["term"] == "kinase"
        assert params["type"] == "molecular_function"
        assert params["id"] == "GO:0000001"

    @pytest.mark.asyncio
    async def test_ontology_parents_and_id(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_ontology_parents("GO:0000001")
            await adapter.get_ontology_id("GO:0000001")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/ontology/parents/GO:0000001")
        assert calls[1].args[0].endswith("/ontology/id/GO:0000001")

    # -- Taxonomy -------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_taxonomy_endpoints(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_taxonomy_id(9606)
            await adapter.get_taxonomy_name("homo sapiens")
            await adapter.get_taxonomy_common("human")
            await adapter.get_taxonomy_root()
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/taxonomy/id/9606")
        assert calls[1].args[0].endswith("/taxonomy/name/homo sapiens")
        assert calls[2].args[0].endswith("/taxonomy/common/human")
        assert calls[3].args[0].endswith("/taxonomy/root")

    # -- Overlap -----------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_overlap_ids_posts_array(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.overlap_ids(["ENSG00000000001"], feature="gene", all_=1)
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/overlap/id")
        assert params["feature"] == "gene"
        assert params["all"] == 1
        assert json_data == ["ENSG00000000001"]

    @pytest.mark.asyncio
    async def test_overlap_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_overlap_region(
                "homo_sapiens", "11", 100, 200, feature="gene"
            )
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/overlap/region/homo_sapiens/11/100/200")
        assert params["up"] == 0
        assert params["down"] == 0
        assert params["feature"] == "gene"
        assert "all" not in params
        assert "limit" not in params
        assert json_data is None

    @pytest.mark.asyncio
    async def test_overlap_translations_posts_array(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.overlap_translations(["ENSP00000000001"], feature="gene")
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/overlap/translation")
        assert params["feature"] == "gene"
        assert json_data == ["ENSP00000000001"]

    # -- Phenotype ------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_phenotype_search_params(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_phenotypes(
                species="homo_sapiens",
                gene="BRCA1",
                region="homo_sapiens:11:100-200",
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/phenotype")
        assert params["species"] == "homo_sapiens"
        assert params["gene"] == "BRCA1"
        assert params["region"] == "homo_sapiens:11:100-200"
        assert params["limit"] == 100
        assert params["offset"] == 1
        assert "term" not in params
        assert "accession" not in params

    @pytest.mark.asyncio
    async def test_phenotype_lookup_endpoints(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_phenotype("RGD:1234")
            await adapter.get_phenotype_by_accession("RGD:1234")
            await adapter.get_phenotypes_by_gene("BRCA1", species="homo_sapiens")
            await adapter.get_phenotypes_by_region("homo_sapiens", "11", 100, 200)
            await adapter.get_phenotypes_by_term("cancer")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/phenotype/RGD:1234")
        assert calls[1].args[0].endswith("/phenotype/accession/RGD:1234")
        assert calls[2].args[0].endswith("/phenotype/gene/BRCA1")
        assert calls[2].kwargs["params"]["species"] == "homo_sapiens"
        assert calls[3].args[0].endswith("/phenotype/region/homo_sapiens/11/100/200")
        assert calls[4].args[0].endswith("/phenotype/term/cancer")

    # -- Regulation ---------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_binding_matrix(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_binding_matrix("homo_sapiens")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/species/homo_sapiens/binding_matrix")
        assert params["feature"] == "protein_coding"
        assert params["type"] == "all"
        assert params["limit"] == 100
        assert params["offset"] == 1
        assert "min" not in params
        assert "max" not in params

    # -- Sequence --------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sequences_posts_array(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_sequences(
                ["ENSG00000000001", "ENSG00000000002"], type_="cdna", class_="canonical"
            )
        url, params, json_data = self._last_call(mock_req)
        assert url.endswith("/sequence/id")
        assert params["type"] == "cdna"
        assert params["class"] == "canonical"
        assert json_data == ["ENSG00000000001", "ENSG00000000002"]

    @pytest.mark.asyncio
    async def test_sequence_region(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_sequence("homo_sapiens", "11", 100, 200)
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/sequence/region/homo_sapiens/11/100/200")
        assert params["type"] == "dna"
        assert "class" not in params

    # -- Transcript haplotypes --------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_transcript_haplotypes(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_transcript_haplotypes(
                "ENST00000000001",
                assembly="GRCh38",
                population="1000genomes",
                type_="ref",
                min_=0.1,
                max_=0.9,
            )
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/transcript/ENST00000000001/haplotypes")
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
        assert json_data == ["NG_012345.1:g.1>A"]

    @pytest.mark.asyncio
    async def test_vep_ids_and_regions(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.vep_ids("homo_sapiens", ["1234"])
            await adapter.vep_regions("homo_sapiens", ["11:100-200"])
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/vep/homo_sapiens/id")
        assert calls[0].kwargs["json_data"] == ["1234"]
        assert calls[1].args[0].endswith("/vep/homo_sapiens/region")
        assert calls[1].kwargs["json_data"] == ["11:100-200"]

    # -- Variation ----------------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_variations(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_variations("homo_sapiens", type_="snp", feature_type="gene")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/variation")
        assert params["spid"] == "homo_sapiens"
        assert params["type"] == "snp"
        assert params["feature_type"] == "gene"
        assert params["limit"] == 50
        assert params["offset"] == 0

    @pytest.mark.asyncio
    async def test_variations_by_article(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.get_variations_by_pmcid("PMC12345")
            await adapter.get_variations_by_pmid("12345678")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/variation/pmcid/PMC12345")
        assert calls[1].args[0].endswith("/variation/pmid/12345678")

    @pytest.mark.asyncio
    async def test_variant_recoder(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.variant_recoder("homo_sapiens", type_="snp")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/variant_recoder")
        assert params["spid"] == "homo_sapiens"
        assert params["type"] == "snp"

    # -- GA4GH ------------------------------------------------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ga4gh_list_and_single_forms(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.ga4gh_callsets()
            await adapter.ga4gh_callsets("CS1")
            await adapter.ga4gh_beacon(study="ST1", dataset="DS1", variant="V1")
            calls = mock_req.call_args_list
        assert calls[0].args[0].endswith("/ga4gh/callsets")
        assert calls[1].args[0].endswith("/ga4gh/callsets/CS1")
        assert calls[2].args[0].endswith("/ga4gh/beacon")
        assert calls[2].kwargs["params"]["study"] == "ST1"
        assert calls[2].kwargs["params"]["dataset"] == "DS1"
        assert calls[2].kwargs["params"]["variant"] == "V1"

    @pytest.mark.asyncio
    async def test_ga4gh_features_uses_query_param(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            await adapter.ga4gh_features(featureset="FS1")
        url, params, _ = self._last_call(mock_req)
        assert url.endswith("/ga4gh/features")
        assert params["featureset"] == "FS1"

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
