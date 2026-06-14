"""
Unit tests for BioLinkerAdapter.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.biolinker_adapter import BioLinkerAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class TestBioLinkerAdapter:
    """Tests for BioLinkerAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create BioLinkerAdapter instance."""
        return BioLinkerAdapter(lookup_config)

    def _make_mock_session(self, response_json, status=200):
        """Helper to create a mock aiohttp session with closed=False."""
        mock_response = AsyncMock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=response_json)
        if status != 200:
            mock_response.text = AsyncMock(return_value="Error")
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=mock_cm)
        return mock_session

    def test_adapter_initialization(self, lookup_config):
        """Test BioLinkerAdapter initialization."""
        adapter = BioLinkerAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.BIOLINKER
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.BIOLINKER

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
        config = LookupConfig(rate_limits={KnowledgeSource.BIOLINKER: 5.0})
        adapter = BioLinkerAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_timeout_error(self, adapter):
        """Test search when TimeoutError occurs - retries then returns []."""
        mock_session = self._make_mock_session({})
        mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())
        adapter.session = mock_session
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await adapter.search_concepts("test query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_general_exception(self, adapter):
        """Test search when general exception occurs."""
        mock_session = self._make_mock_session({})
        mock_session.post = MagicMock(side_effect=Exception("Connection error"))
        adapter.session = mock_session
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await adapter.search_concepts("test query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_non_200_status(self, adapter):
        """Test search when API returns non-200 status."""
        mock_session = self._make_mock_session({}, status=500)
        adapter.session = mock_session
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await adapter.search_concepts("test query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_long_query(self, adapter):
        """Test search with long query (> 10 words)."""
        mock_session = self._make_mock_session({"results": []})
        adapter.session = mock_session
        results = await adapter.search_concepts("word " * 15)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_short_query(self, adapter):
        """Test search with short query (< 3 words)."""
        mock_session = self._make_mock_session({"results": []})
        adapter.session = mock_session
        results = await adapter.search_concepts("BRCA2")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_medium_query(self, adapter):
        """Test search with medium query (3-10 words)."""
        mock_session = self._make_mock_session({"results": []})
        adapter.session = mock_session
        results = await adapter.search_concepts("the quick brown fox jumps")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search with actual results."""
        biolinker_response = {
            "results": [
                {"best_candidate": {"id": "C0001", "label": "Diabetes", "type": ["disease"]}, "surface_form": "diabetes", "start": 0, "end": 8, "category": "entities"}
            ]
        }
        mock_session = self._make_mock_session(biolinker_response)
        adapter.session = mock_session
        results = await adapter.search_concepts("diabetes")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_annotate_sentence_success(self, adapter):
        """Test annotate_sentence with successful response."""
        biolinker_response = {
            "results": [
                {"best_candidate": {"id": "C0001", "label": "Diabetes", "description": "A metabolic disease", "type": ["disease"]}, "surface_form": "diabetes", "start": 0, "end": 8, "category": "entities"},
                {"best_candidate": {"id": "C0002", "label": "causes", "description": "", "type": ["predicate"]}, "surface_form": "causes", "start": 9, "end": 15, "category": "predicates"},
                {"best_candidate": {"id": "C0003", "label": "Obesity", "description": "Being overweight", "type": ["disease"]}, "surface_form": "obesity", "start": 16, "end": 23, "category": "entities"},
            ]
        }
        mock_session = self._make_mock_session(biolinker_response)
        adapter.session = mock_session
        annotation = await adapter.annotate_sentence("diabetes causes obesity")
        assert "entities" in annotation
        assert "predicates" in annotation
        assert "relations" in annotation
        assert annotation["total_concepts"] == 3

    @pytest.mark.asyncio
    async def test_annotate_sentence_error(self, adapter):
        """Test annotate_sentence when search returns empty due to error."""
        mock_session = self._make_mock_session({})
        mock_session.post = MagicMock(side_effect=Exception("Connection error"))
        adapter.session = mock_session
        with patch("asyncio.sleep", new_callable=AsyncMock):
            annotation = await adapter.annotate_sentence("test")
            assert annotation["entities"] == []
            assert annotation["total_concepts"] == 0

    @pytest.mark.asyncio
    async def test_annotate_multiple_sentences(self, adapter):
        """Test annotate_multiple_sentences."""
        biolinker_response = {"results": []}
        mock_session = self._make_mock_session(biolinker_response)
        adapter.session = mock_session
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await adapter.annotate_multiple_sentences(["sentence 1", "sentence 2"])
            assert len(results) == 2

    def test_identify_sentence_relations(self, adapter):
        """Test _identify_sentence_relations."""
        entities = [
            {"surface_form": "diabetes", "label": "Diabetes", "id": "C0001", "type": "disease", "position": {"start": 0, "end": 8}, "confidence": 0.9},
            {"surface_form": "obesity", "label": "Obesity", "id": "C0003", "type": "disease", "position": {"start": 16, "end": 23}, "confidence": 0.85},
        ]
        predicates = [
            {"surface_form": "causes", "label": "causes", "id": "C0002", "type": "predicate", "position": {"start": 9, "end": 15}, "confidence": 0.95}
        ]
        relations = adapter._identify_sentence_relations(entities, predicates)
        assert len(relations) == 1
        assert relations[0]["subject"]["label"] == "Diabetes"
        assert relations[0]["predicate"]["label"] == "causes"
        assert relations[0]["object"]["label"] == "Obesity"

    def test_identify_sentence_relations_no_nearby_entities(self, adapter):
        """Test with no nearby entities."""
        entities = [{"surface_form": "diabetes", "label": "Diabetes", "id": "C0001", "type": "disease", "position": {"start": 0, "end": 8}, "confidence": 0.9}]
        predicates = [{"surface_form": "far", "label": "related", "id": "C0002", "type": "predicate", "position": {"start": 200, "end": 210}, "confidence": 0.95}]
        relations = adapter._identify_sentence_relations(entities, predicates)
        assert len(relations) == 0

    def test_identify_sentence_relations_one_nearby_entity(self, adapter):
        """Test with only 1 nearby entity."""
        entities = [{"surface_form": "diabetes", "label": "Diabetes", "id": "C0001", "type": "disease", "position": {"start": 0, "end": 8}, "confidence": 0.9}]
        predicates = [{"surface_form": "causes", "label": "causes", "id": "C0002", "type": "predicate", "position": {"start": 9, "end": 15}, "confidence": 0.95}]
        relations = adapter._identify_sentence_relations(entities, predicates)
        assert len(relations) == 0

    def test_identify_sentence_relations_empty(self, adapter):
        """Test with empty entities and predicates."""
        relations = adapter._identify_sentence_relations([], [])
        assert relations == []

    @pytest.mark.asyncio
    async def test_get_concept_details_returns_none(self, adapter):
        """Test get_concept_details returns None."""
        result = await adapter.get_concept_details("C0001")
        assert result is None

    def test_process_biolinker_response_no_results_key(self, adapter):
        """Test _process_biolinker_response with no results key."""
        result = adapter._process_biolinker_response({}, 10)
        assert result == []

    def test_process_biolinker_response_with_results(self, adapter):
        """Test _process_biolinker_response with results."""
        response_data = {
            "results": [
                {"best_candidate": {"id": "C0001", "label": "Diabetes", "description": "A metabolic disease", "type": ["disease"]}, "surface_form": "diabetes", "start": 0, "end": 8, "category": "entities"}
            ]
        }
        concepts = adapter._process_biolinker_response(response_data, 10)
        assert len(concepts) == 1

    def test_process_biolinker_response_limit(self, adapter):
        """Test _process_biolinker_response respects limit."""
        response_data = {
            "results": [
                {"best_candidate": {"id": f"C{i:04d}", "label": f"Concept {i}", "type": ["disease"]}, "surface_form": f"concept{i}", "category": "entities"}
                for i in range(5)
            ]
        }
        concepts = adapter._process_biolinker_response(response_data, 2)
        assert len(concepts) == 2

    def test_process_biolinker_response_error_in_result(self, adapter):
        """Test with error in one result."""
        response_data = {
            "results": [
                {"bad": "data"},
                {"best_candidate": {"id": "C0001", "label": "Diabetes", "type": ["disease"]}, "surface_form": "diabetes", "category": "entities"},
            ]
        }
        concepts = adapter._process_biolinker_response(response_data, 10)
        assert len(concepts) == 1

    def test_convert_biolinker_result_full(self, adapter):
        """Test _convert_biolinker_result_to_concept with all fields."""
        result = {
            "best_candidate": {"id": "C0001", "label": "Diabetes", "description": "A metabolic disease", "type": ["disease"]},
            "surface_form": "diabetes", "start": 0, "end": 8, "category": "entities",
        }
        concept = adapter._convert_biolinker_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "C0001"
        assert concept.primary_label == "Diabetes"
        assert "A metabolic disease" in concept.definitions
        assert "diabetes" in concept.synonyms

    def test_convert_biolinker_result_no_best_candidate(self, adapter):
        """Test with no best_candidate."""
        concept = adapter._convert_biolinker_result_to_concept({"surface_form": "test"})
        assert concept is None

    def test_convert_biolinker_result_no_id(self, adapter):
        """Test with no id."""
        concept = adapter._convert_biolinker_result_to_concept({"best_candidate": {"label": "Test", "type": ["disease"]}, "surface_form": "test"})
        assert concept is None

    def test_convert_biolinker_result_no_label(self, adapter):
        """Test with no label."""
        concept = adapter._convert_biolinker_result_to_concept({"best_candidate": {"id": "C0001", "type": ["disease"]}, "surface_form": "test"})
        assert concept is None

    def test_convert_biolinker_result_semantic_types_as_string(self, adapter):
        """Test conversion when semantic_types is a string."""
        result = {"best_candidate": {"id": "C0001", "label": "Diabetes", "type": "disease"}, "surface_form": "diabetes", "category": "entities"}
        concept = adapter._convert_biolinker_result_to_concept(result)
        assert concept is not None
        assert concept.semantic_types == ["disease"]

    def test_convert_biolinker_result_semantic_types_none(self, adapter):
        """Test when semantic_types is None."""
        result = {"best_candidate": {"id": "C0001", "label": "Diabetes", "type": None}, "surface_form": "diabetes", "category": "entities"}
        concept = adapter._convert_biolinker_result_to_concept(result)
        assert concept is not None

    def test_convert_biolinker_result_surface_form_same_as_label(self, adapter):
        """Test when surface_form equals label."""
        result = {"best_candidate": {"id": "C0001", "label": "Diabetes", "type": ["disease"]}, "surface_form": "Diabetes", "category": "entities"}
        concept = adapter._convert_biolinker_result_to_concept(result)
        assert concept is not None
        assert "Diabetes" not in concept.synonyms

    def test_convert_biolinker_result_error(self, adapter):
        """Test error handling."""
        concept = adapter._convert_biolinker_result_to_concept(None)
        assert concept is None

    def test_map_semantic_type_disease(self, adapter):
        """Test _map_semantic_type_to_concept_type for disease types."""
        assert adapter._map_semantic_type_to_concept_type(["disease"]) == ConceptType.DISEASE
        assert adapter._map_semantic_type_to_concept_type(["disorder"]) == ConceptType.DISEASE

    def test_map_semantic_type_symptom(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["symptom"]) == ConceptType.SYMPTOM

    def test_map_semantic_type_drug(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["drug"]) == ConceptType.DRUG

    def test_map_semantic_type_gene(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["gene"]) == ConceptType.GENE

    def test_map_semantic_type_protein(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["protein"]) == ConceptType.PROTEIN

    def test_map_semantic_type_pathway(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["pathway"]) == ConceptType.PATHWAY

    def test_map_semantic_type_anatomy(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["anatomy"]) == ConceptType.ANATOMY

    def test_map_semantic_type_phenotype(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["phenotype"]) == ConceptType.PHENOTYPE

    def test_map_semantic_type_chemical(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["chemical"]) == ConceptType.CHEMICAL

    def test_map_semantic_type_organism(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["organism"]) == ConceptType.ANATOMY
        assert adapter._map_semantic_type_to_concept_type(["species"]) == ConceptType.ORGANISM

    def test_map_semantic_type_procedure(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["procedure"]) == ConceptType.PROCEDURE

    def test_map_semantic_type_unknown(self, adapter):
        assert adapter._map_semantic_type_to_concept_type(["unknown_type"]) == ConceptType.UNKNOWN

    def test_map_semantic_type_empty(self, adapter):
        """Test with empty list."""
        assert adapter._map_semantic_type_to_concept_type([]) == ConceptType.UNKNOWN

    def test_calculate_confidence_score_full(self, adapter):
        """Test _calculate_confidence_score with all boosts."""
        result = {"category": "entities", "surface_form": "Diabetes"}
        best_candidate = {"description": "A disease", "type": ["disease"], "label": "Diabetes"}
        score = adapter._calculate_confidence_score(result, best_candidate)
        assert score == 1.0

    def test_calculate_confidence_score_minimal(self, adapter):
        """Test _calculate_confidence_score with minimal data."""
        result = {"category": "predicates", "surface_form": "causes"}
        best_candidate = {"label": "related", "type": []}
        score = adapter._calculate_confidence_score(result, best_candidate)
        assert score == 0.7

    def test_generate_concept_url_umls(self, adapter):
        """Test _generate_concept_url for UMLS C-code."""
        url = adapter._generate_concept_url("C0001")
        assert url == "https://uts.nlm.nih.gov/uts/umls/concept/C0001"

    def test_generate_concept_url_non_umls(self, adapter):
        """Test _generate_concept_url for non-UMLS ID."""
        assert adapter._generate_concept_url("DOID:162") is None

    def test_generate_concept_url_empty(self, adapter):
        """Test _generate_concept_url with empty ID."""
        assert adapter._generate_concept_url("") is None

    @pytest.mark.asyncio
    async def test_close(self, adapter):
        """Test close method."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        adapter.session = mock_session
        await adapter.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_session(self, adapter):
        """Test close when session is None."""
        adapter.session = None
        await adapter.close()

    @pytest.mark.asyncio
    async def test_close_session_already_closed(self, adapter):
        """Test close when session is already closed."""
        mock_session = MagicMock()
        mock_session.closed = True
        adapter.session = mock_session
        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass
