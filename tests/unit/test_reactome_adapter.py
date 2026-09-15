"""
Unit tests for ReactomeAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

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
