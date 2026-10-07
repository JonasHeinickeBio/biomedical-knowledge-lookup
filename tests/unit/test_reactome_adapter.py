"""
Unit tests for ReactomeAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fixtures.reactome_responses import (
    ANCESTORS_APOPTOSIS,
    ENTITY_PATHWAYS_COMPLEX,
    HAS_EVENT_APOPTOSIS,
    PARTICIPANTS_APOPTOSIS,
    PARTICIPANTS_GLYCOLYSIS_SAMPLE,
    PATHWAY_APOPTOSIS,
    PATHWAYS_FOR_BRCA1,
    REFERENCE_MAPPING_ENSG,
    UNIPROT_BRCA1,
)

from knowledge_lookup.adapters.reactome_adapter import ReactomeAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class TestReactomeAdapter:
    """Tests for ReactomeAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create ReactomeAdapter instance."""
        return ReactomeAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test ReactomeAdapter initialization."""
        adapter = ReactomeAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.REACTOME
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.REACTOME

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
        config = LookupConfig(rate_limits={KnowledgeSource.REACTOME: 5.0})
        adapter = ReactomeAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @staticmethod
    def _group(type_name, entries):
        """One group of a /search/query response (the type is on each entry)."""
        return {
            "typeName": type_name,
            "entriesCount": len(entries),
            "rowCount": len(entries),
            "entries": entries,
        }

    @staticmethod
    def _entry(st_id, name, entry_type, **extra):
        return {
            "dbId": st_id.rsplit("-", 1)[-1],
            "stId": st_id,
            "id": st_id,
            "name": name,
            "type": entry_type,
            "exactType": entry_type,
            "species": ["Homo sapiens"],
            **extra,
        }

    @pytest.mark.asyncio
    async def test_search_concepts_with_pathway_results(self, adapter):
        """Test search_concepts with pathway results in the grouped response."""
        reactome_data = {
            "results": [
                self._group(
                    "Pathway",
                    [
                        self._entry(
                            "R-HSA-1640170", "Cell Cycle", "Pathway", summation="The cell cycle."
                        ),
                        self._entry(
                            "R-HSA-109581",
                            "Apoptosis",
                            "Pathway",
                            summation="Programmed cell death.",
                        ),
                    ],
                )
            ],
            "rowCount": 2,
            "numberOfGroups": 1,
            "numberOfMatches": 2,
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            results = await adapter.search_concepts("cell cycle", limit=10)
            assert len(results) == 2
            assert results[0].primary_id == "R-HSA-1640170"
            assert results[0].definitions == ["The cell cycle."]

    @pytest.mark.asyncio
    async def test_search_concepts_filters_non_pathway(self, adapter):
        """Test search keeps only Pathway/Reaction entries across all groups."""
        reactome_data = {
            "results": [
                self._group("Pathway", [self._entry("R-HSA-1640170", "Cell Cycle", "Pathway")]),
                self._group("Reaction", [self._entry("R-HSA-109582", "Hemostasis", "Reaction")]),
                self._group("Interactor", [self._entry("O15392-1", "BIRC5", "Interactor")]),
                self._group("Protein", [self._entry("R-HSA-50851", "BIRC5", "Protein")]),
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            results = await adapter.search_concepts("test", limit=10)
            assert [r.primary_id for r in results] == ["R-HSA-1640170", "R-HSA-109582"]

    @pytest.mark.asyncio
    async def test_search_concepts_reads_type_from_entries_not_groups(self, adapter):
        """Regression: groups have no ``type`` key; search must not return [] for them."""
        reactome_data = {
            "results": [
                {
                    "typeName": "Pathway",
                    "entriesCount": 288,
                    "rowCount": 1,
                    "entries": [self._entry("R-HSA-109581", "Apoptosis", "Pathway")],
                }
            ]
        }
        assert "type" not in reactome_data["results"][0]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            results = await adapter.search_concepts("apoptosis", limit=5)
        assert len(results) == 1
        assert results[0].primary_id == "R-HSA-109581"

    @pytest.mark.asyncio
    async def test_search_concepts_strips_highlighting_markup(self, adapter):
        """Search hits wrap matches in <span class="highlighting"> and use <BR>."""
        entry = self._entry(
            "R-HSA-109581",
            '<span class="highlighting" >Apoptosis</span>',
            "Pathway",
            summation='<span class="highlighting" >Apoptosis</span> is cell death.<BR>More text',
        )
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": [self._group("Pathway", [entry])]}
            results = await adapter.search_concepts("apoptosis", limit=5)
        assert results[0].primary_label == "Apoptosis"
        assert results[0].identifiers[0].label == "Apoptosis"
        assert results[0].definitions[0].startswith("Apoptosis is cell death.")
        assert "<" not in results[0].definitions[0]

    @pytest.mark.asyncio
    async def test_search_concepts_respects_limit_across_groups(self, adapter):
        """``rows`` applies per group, so the adapter caps the total at ``limit``."""
        reactome_data = {
            "results": [
                self._group(
                    "Pathway",
                    [self._entry(f"R-HSA-10{i}", f"Pathway {i}", "Pathway") for i in range(3)],
                ),
                self._group(
                    "Reaction",
                    [self._entry(f"R-HSA-20{i}", f"Reaction {i}", "Reaction") for i in range(3)],
                ),
            ]
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            results = await adapter.search_concepts("test", limit=4)
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_search_concepts_404_no_matches(self, adapter):
        """Reactome answers 404 when nothing matches; search returns []."""
        error = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=404, message="Not Found"
        )
        with patch.object(adapter, "_make_request", new_callable=AsyncMock, side_effect=error):
            results = await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_result_conversion_returns_none(self, adapter):
        """Test search when _convert_reactome_result returns None."""
        reactome_data = {"results": [{"typeName": "Pathway", "entries": [{"type": "Pathway"}]}]}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = reactome_data
            with patch.object(adapter, "_convert_reactome_result_to_concept", return_value=None):
                results = await adapter.search_concepts("test")
                assert len(results) == 0

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
        """Test successful get_concept_details."""
        data = {
            "stId": "R-HSA-1640170",
            "displayName": "Cell Cycle",
            "dbId": 1640170,
            "summation": [{"text": "The cell cycle."}],
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is not None
            assert result.primary_id == "R-HSA-1640170"

    @pytest.mark.asyncio
    async def test_get_concept_details_no_dbid(self, adapter):
        """Test get_concept_details when no 'dbId' in response."""
        data = {"name": "something"}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = data
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_data(self, adapter):
        """Test get_concept_details with empty data."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {}
            result = await adapter.get_concept_details("R-HSA-1640170")
            assert result is None

    def test_convert_reactome_result_full(self, adapter):
        """Test _convert_reactome_result_to_concept with all fields."""
        result = {
            "stId": "R-HSA-1640170",
            "name": "Cell Cycle",
            "summation": "The cell cycle describes the series of events.",
            "species": ["Homo sapiens", "Mus musculus"],
        }
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "R-HSA-1640170"
        assert concept.primary_label == "Cell Cycle"
        assert "The cell cycle describes the series of events." in concept.definitions
        assert "Homo sapiens" in concept.categories
        assert concept.confidence_score == 0.9

    def test_convert_reactome_result_no_stid(self, adapter):
        """Test _convert_reactome_result_to_concept with missing stId."""
        result = {"name": "Cell Cycle"}
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is None

    def test_convert_reactome_result_no_name(self, adapter):
        """Test _convert_reactome_result_to_concept with missing name."""
        result = {"stId": "R-HSA-1640170"}
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is None

    def test_convert_reactome_result_no_summation_no_species(self, adapter):
        """Test _convert_reactome_result without optional fields."""
        result = {"stId": "R-HSA-1640170", "name": "Cell Cycle"}
        concept = adapter._convert_reactome_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_reactome_result_error(self, adapter):
        """Test _convert_reactome_result error handling."""
        concept = adapter._convert_reactome_result_to_concept(None)
        assert concept is None

    def test_convert_reactome_details_full(self, adapter):
        """Test _convert_reactome_details_to_concept with all fields."""
        data = {
            "stId": "R-HSA-1640170",
            "displayName": "Cell Cycle",
            "summation": [{"text": "The cell cycle describes the series of events."}],
        }
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is not None
        assert concept.primary_id == "R-HSA-1640170"
        assert concept.primary_label == "Cell Cycle"
        assert "The cell cycle describes the series of events." in concept.definitions
        assert concept.confidence_score == 1.0

    @pytest.mark.parametrize(
        ("schema_class", "expected"),
        [
            ("Pathway", ConceptType.PATHWAY),
            ("TopLevelPathway", ConceptType.PATHWAY),
            ("Reaction", ConceptType.BIOLOGICAL_PROCESS),
            ("BlackBoxEvent", ConceptType.BIOLOGICAL_PROCESS),
            ("Complex", ConceptType.UNKNOWN),
            (None, ConceptType.UNKNOWN),
        ],
    )
    def test_concept_type_from_schema_class(self, adapter, schema_class, expected):
        """Search entries carry the class in "type", details in "schemaClass"."""
        hit = adapter._convert_reactome_result_to_concept(
            {"stId": "R-HSA-1", "name": "Event", "type": schema_class}
        )
        details = adapter._convert_reactome_details_to_concept(
            {"stId": "R-HSA-1", "displayName": "Event", "schemaClass": schema_class}
        )
        assert hit.concept_type == expected
        assert details.concept_type == expected

    def test_convert_reactome_details_no_stid(self, adapter):
        """Test _convert_reactome_details_to_concept with missing stId."""
        data = {"displayName": "Cell Cycle"}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is None

    def test_convert_reactome_details_no_display_name(self, adapter):
        """Test _convert_reactome_details_to_concept with missing displayName."""
        data = {"stId": "R-HSA-1640170"}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is None

    def test_convert_reactome_details_no_summation(self, adapter):
        """Test _convert_reactome_details_to_concept without summation."""
        data = {"stId": "R-HSA-1640170", "displayName": "Cell Cycle"}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is not None
        assert len(concept.definitions) == 0

    def test_convert_reactome_details_empty_summation(self, adapter):
        """Test _convert_reactome_details_to_concept with empty summation list."""
        data = {"stId": "R-HSA-1640170", "displayName": "Cell Cycle", "summation": []}
        concept = adapter._convert_reactome_details_to_concept(data)
        assert concept is not None

    def test_convert_reactome_details_error(self, adapter):
        """Test _convert_reactome_details error handling."""
        concept = adapter._convert_reactome_details_to_concept(None)
        assert concept is None

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

    @pytest.mark.asyncio
    async def test_repeated_no_match_searches_keep_the_breaker_closed(self, adapter):
        """Regression: Reactome's 404 "no match" answers opened the circuit breaker."""
        from knowledge_lookup.utils.retry_utils import CircuitBreaker

        breaker = CircuitBreaker(threshold=2, cooldown=60)
        adapter.set_circuit_breaker(breaker)
        response = MagicMock()
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=404, message="Not Found"
        )
        session = MagicMock()
        session.get.return_value.__aenter__ = AsyncMock(return_value=response)
        session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            for _ in range(5):
                assert await adapter.search_concepts("xkjshdfkjsdhfkljhsdkfj") == []

        assert session.get.call_count == 5  # every search reached Reactome
        assert breaker.state.value == "closed"
        assert breaker.failure_count == 0


def _http_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=status, message="x"
    )


class TestReactomeRelationships:
    """get_relationships: gene -> pathways and pathway hierarchy/participants."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return ReactomeAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_uniprot_accession_to_pathways(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = PATHWAYS_FOR_BRCA1
            rels = await adapter.get_relationships("P38398")
        url, params = req.call_args.args
        assert url.endswith("/data/mapping/UniProt/P38398/pathways")
        assert params == {"species": "9606"}
        assert [r["related_id"] for r in rels] == [
            "R-HSA-1221632",
            "R-HSA-3108214",
            "R-HSA-5685938",
            "R-HSA-5685942",
        ]
        first = rels[0]
        assert first["relation_label"] == "participates_in"
        assert first["related_name"] == first["name"] == "Meiotic synapsis"
        assert first["stId"] == "R-HSA-1221632"
        assert first["species"] == "Homo sapiens"
        assert first["source"] == "Reactome"
        assert first["schema_class"] == "Pathway"
        assert first["is_in_disease"] is False and first["is_inferred"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("identifier", "resource", "value"),
        [
            ("UniProt:P38398", "UniProt", "P38398"),
            ("ENSG00000012048.19", "ENSEMBL", "ENSG00000012048"),
            ("HGNC:1100", "HGNC", "1100"),
            ("NCBIGene:672", "NCBI%20Gene", "672"),
            ("672", "NCBI%20Gene", "672"),
            ("BRCA1", "HGNC", "BRCA1"),
        ],
    )
    async def test_identifier_forms_pick_the_mapping_resource(
        self, adapter, identifier, resource, value
    ):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = PATHWAYS_FOR_BRCA1
            rels = await adapter.get_relationships(identifier)
        assert req.call_args.args[0].endswith(f"/data/mapping/{resource}/{value}/pathways")
        assert len(rels) == 4

    @pytest.mark.asyncio
    async def test_accession_shaped_symbol_falls_back_to_hgnc(self, adapter):
        """P2RY12 looks like a UniProt accession but is a gene symbol."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [_http_error(404), PATHWAYS_FOR_BRCA1]
            rels = await adapter.get_relationships("P2RY12")
        assert len(rels) == 4
        assert req.await_args_list[0].args[0].endswith("/UniProt/P2RY12/pathways")
        assert req.await_args_list[1].args[0].endswith("/HGNC/P2RY12/pathways")

    @pytest.mark.asyncio
    async def test_species_option(self, lookup_config):
        adapter = ReactomeAdapter(lookup_config, species=None)
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = PATHWAYS_FOR_BRCA1
            await adapter.get_relationships("P38398")
        assert req.call_args.args[1] == {}

    @pytest.mark.asyncio
    async def test_limit_dedupe_and_malformed_entries(self, adapter):
        pathways = [*PATHWAYS_FOR_BRCA1, PATHWAYS_FOR_BRCA1[0], "junk", {"displayName": "no id"}]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = pathways
            assert len(await adapter.get_relationships("P38398", limit=3)) == 3
            assert len(await adapter.get_relationships("P38398", limit=50)) == 4
            assert await adapter.get_relationships("P38398", limit=0) == []

    @pytest.mark.asyncio
    async def test_no_pathways_unknown_and_errors(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = _http_error(404)
            assert await adapter.get_relationships("ZZZZNOPE") == []
            assert await adapter.get_relationships("") == []
            assert await adapter.get_relationships("not an id!") == []
            req.side_effect = _http_error(500)
            assert await adapter.get_relationships("P38398") == []
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_relationships("P38398") == []
            req.side_effect = None
            req.return_value = {"unexpected": "dict"}
            assert await adapter.get_relationships("P38398") == []

    @pytest.mark.asyncio
    async def test_pathway_hierarchy_and_participants(self, adapter):
        with (
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as req,
        ):
            text.side_effect = ["Pathway\n", HAS_EVENT_APOPTOSIS]
            req.side_effect = [ANCESTORS_APOPTOSIS, PARTICIPANTS_APOPTOSIS]
            rels = await adapter.get_relationships("R-HSA-109581.6", limit=3)
        assert text.await_args_list[0].args[0].endswith("/data/query/R-HSA-109581/schemaClass")
        assert text.await_args_list[1].args[0].endswith("/data/query/R-HSA-109581/hasEvent")
        by_label: dict[str, list] = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)

        parent = by_label["part_of"][0]
        assert parent["related_id"] == "R-HSA-5357801"
        assert parent["related_name"] == "Programmed Cell Death"
        assert parent["depth"] == 1 and parent["schema_class"] == "TopLevelPathway"

        children = by_label["has_part"]
        assert [c["related_id"] for c in children] == [
            "R-HSA-5357769",
            "R-HSA-109606",
            "R-HSA-75153",
        ]  # capped at limit=3 of 4
        assert children[0]["schema_class"] == "Pathway"

        participants = by_label["has_participant"]
        assert [p["related_id"] for p in participants] == ["Q12933", "Q15628", "Q13546"]
        assert participants[0]["related_name"] == "TRAF2"
        assert participants[0]["related_id_source"] == "UniProt"

    @pytest.mark.asyncio
    async def test_multi_level_ancestors_and_missing_children(self, adapter):
        paths = [
            [{"stId": "R-HSA-1"}, {"stId": "R-HSA-2", "displayName": "P"}, {"stId": "R-HSA-3"}],
            [{"stId": "R-HSA-1"}, {"stId": "R-HSA-3", "displayName": "Top"}],
            ["junk"],
            [{"stId": "R-HSA-1"}, {"displayName": "no id"}],
        ]
        with (
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as req,
        ):
            text.side_effect = ["Reaction", _http_error(404)]
            req.side_effect = [paths, []]
            rels = await adapter.get_relationships("R-HSA-1")
        assert [(r["related_id"], r["depth"]) for r in rels] == [
            ("R-HSA-2", 1),
            ("R-HSA-3", 1),  # the shallowest depth over all paths wins
        ]

    @pytest.mark.asyncio
    async def test_participants_chebi_isoform_and_dedupe(self, adapter):
        participants = [*PARTICIPANTS_GLYCOLYSIS_SAMPLE, *PARTICIPANTS_GLYCOLYSIS_SAMPLE]
        participants.append({"displayName": "x", "refEntities": [{"stId": "other:abc"}, {}]})
        participants.append({"displayName": "no refs", "refEntities": None})
        with (
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as req,
        ):
            text.side_effect = ["Pathway", ""]
            req.side_effect = [None, participants]
            rels = await adapter.get_relationships("R-HSA-70171")
        assert [r["related_id"] for r in rels] == ["CHEBI:15377", "P14618", "abc"]
        water, pkm, other = rels
        assert water["related_name"] == "water" and water["related_id_source"] == "ChEBI"
        assert water["participant"] == "H2O [cytosol]"
        assert pkm["isoform"] == "P14618-1" and pkm["related_name"] == "PKM"
        assert other["related_id_source"] == "other" and other["related_name"] == "abc"

    @pytest.mark.asyncio
    async def test_physical_entity_to_pathways(self, adapter):
        with (
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as req,
        ):
            text.return_value = "Complex"
            req.return_value = ENTITY_PATHWAYS_COMPLEX
            rels = await adapter.get_relationships("R-HSA-140976")
        assert req.call_args.args[0].endswith("/data/pathways/low/entity/R-HSA-140976")
        assert [r["related_id"] for r in rels][:2] == ["R-HSA-69416", "R-HSA-5357786"]
        assert all(r["relation_label"] == "participates_in" for r in rels)

    @pytest.mark.asyncio
    async def test_unknown_stable_id_and_bad_entity_response(self, adapter):
        with (
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as req,
        ):
            text.side_effect = _http_error(404)
            assert await adapter.get_relationships("R-HSA-0000000") == []
            text.side_effect = None
            text.return_value = "Complex"
            req.return_value = None
            assert await adapter.get_relationships("R-HSA-140976") == []

    @pytest.mark.asyncio
    async def test_text_endpoint_server_error_degrades(self, adapter):
        with patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text:
            text.side_effect = _http_error(500)
            assert await adapter.get_relationships("R-HSA-109581") == []


class TestReactomeMappings:
    """get_mappings: cross-references of proteins, pathways and entities."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return ReactomeAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_uniprot_cross_references(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = UNIPROT_BRCA1
            mappings = await adapter.get_mappings("UniProt:P38398")
        assert req.call_args.args[0].endswith("/data/query/uniprot:P38398")
        by_target = {(m["toSource"], m["toId"]): m for m in mappings}
        assert by_target[("Ensembl", "ENSG00000012048")]["mappingType"] == "exact"
        assert ("Ensembl", "ENSP00000350283") in by_target
        assert not any(i.startswith("ENST") for _, i in by_target)  # transcripts dropped
        assert by_target[("PDB", "1JM7")]["mappingType"] == "related"
        assert ("GeneCards", "BRCA1") in by_target
        assert ("OpenTargets", "ENSG00000012048") in by_target
        assert ("Pharos", "P38398") in by_target
        assert ("UniProt", "Q3LRJ0") in by_target  # secondary accession
        assert ("UniProt", "BRCA1_HUMAN") not in by_target  # entry names are not accessions
        assert not any(s.startswith("ZINC") for s, _ in by_target)
        for source in ("RefSeq", "PDB", "Ensembl"):
            assert sum(1 for m in mappings if m["toSource"] == source) <= 10
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "P38398" and m["fromSource"] == "Reactome"

    @pytest.mark.asyncio
    async def test_ensembl_gene_is_resolved_through_uniprot(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [REFERENCE_MAPPING_ENSG, UNIPROT_BRCA1]
            mappings = await adapter.get_mappings("ENSG00000012048")
        assert req.await_args_list[0].args[0].endswith("/references/mapping/ENSG00000012048")
        assert req.await_args_list[1].args[0].endswith("/data/query/uniprot:P38398")
        assert mappings[0]["toSource"] == "UniProt" and mappings[0]["toId"] == "P38398"
        assert mappings[0]["mappingType"] == "exact"
        assert mappings[0]["fromId"] == "ENSG00000012048"

    @pytest.mark.asyncio
    async def test_gene_symbol_filters_unrelated_matches(self, adapter):
        unrelated = {"stId": "uniprot:P84095", "identifier": "P84095", "geneName": ["RHOG"]}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [[unrelated, *REFERENCE_MAPPING_ENSG], UNIPROT_BRCA1]
            mappings = await adapter.get_mappings("BRCA1")
        assert [m["toId"] for m in mappings if m["toSource"] == "UniProt"][0] == "P38398"
        assert "P84095" not in {m["toId"] for m in mappings}
        assert req.await_count == 2

    @pytest.mark.asyncio
    async def test_unresolvable_identifiers(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            for identifier in ("672", "HGNC:1100", "NCBIGene:672", "", "not an id!"):
                assert await adapter.get_mappings(identifier) == []
            assert req.await_count == 0
            req.return_value = None
            assert await adapter.get_mappings("ZZZZNOPE") == []
            req.return_value = [{"stId": "ensembl:ENSG1"}, {"stId": "uniprot:", "identifier": ""}]
            assert await adapter.get_mappings("ENSG00000012048") == []

    @pytest.mark.asyncio
    async def test_pathway_mappings(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = PATHWAY_APOPTOSIS
            mappings = await adapter.get_mappings("R-HSA-109581")
        assert req.call_args.args[0].endswith("/data/query/R-HSA-109581")
        assert mappings[0] == {
            "fromId": "R-HSA-109581",
            "toId": "GO:0006915",
            "fromSource": "Reactome",
            "toSource": "GO",
            "mappingType": "related",
            "confidence": 0.9,
        }
        orthologs = [m for m in mappings if m["mappingType"] == "ortholog"]
        assert [m["toId"] for m in orthologs] == [
            "R-RNO-109581",
            "R-CFA-109581",
            "R-BTA-109581",
            "R-SSC-109581",
        ]

    @pytest.mark.asyncio
    async def test_physical_entity_mappings(self, adapter):
        entity = {
            "referenceEntity": {"databaseName": "ChEBI", "identifier": "15377"},
            "goCellularComponent": {"accession": "0005829"},
            "orthologousEvent": ["junk"],
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = entity
            mappings = await adapter.get_mappings("R-ALL-113592")
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("GO", "GO:0005829"),
            ("ChEBI", "15377"),
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = {"referenceEntity": {"databaseName": "ENSEMBL", "identifier": "X"}}
            mappings = await adapter.get_mappings("R-HSA-5")
        assert mappings[0]["toSource"] == "Ensembl"

    @pytest.mark.asyncio
    async def test_empty_and_malformed_data(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = ["not", "a", "dict"]
            assert await adapter.get_mappings("R-HSA-109581") == []
            assert await adapter.get_mappings("P38398") == []
            req.return_value = {"crossReference": [{"databaseName": "", "identifier": "x"}]}
            assert await adapter.get_mappings("P38398") == []

    @pytest.mark.asyncio
    async def test_errors_degrade_to_empty(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = _http_error(404)
            assert await adapter.get_mappings("R-HSA-0000000") == []
            req.side_effect = RuntimeError("boom")
            assert await adapter.get_mappings("P38398") == []


class TestReactomeChildParsing:
    @pytest.mark.asyncio
    async def test_malformed_tsv_lines_are_skipped(self, lookup_config):
        adapter = ReactomeAdapter(lookup_config)
        with (
            patch.object(adapter, "_make_request_text", new_callable=AsyncMock) as text,
            patch.object(adapter, "_make_request", new_callable=AsyncMock) as req,
        ):
            text.side_effect = ["Pathway", "onlyone\n\t\nR-HSA-2\tName\n"]
            req.side_effect = [None, None]
            rels = await adapter.get_relationships("R-HSA-1")
        assert [(r["related_id"], r["schema_class"]) for r in rels] == [("R-HSA-2", None)]
