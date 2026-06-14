"""
Unit tests for DBpediaAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.dbpedia_adapter import DBpediaAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class TestDBpediaAdapter:
    """Tests for DBpediaAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create DBpediaAdapter instance."""
        return DBpediaAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test DBpediaAdapter initialization."""
        adapter = DBpediaAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.DBPEDIA
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.DBPEDIA

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert result is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self, adapter):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.DBPEDIA: 5.0})
        adapter = DBpediaAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # --- _make_request with headers (line 41) ---

    @pytest.mark.asyncio
    async def test_make_request_with_headers_logs(self, adapter):
        """Test _make_request logs headers when provided."""
        with patch.object(adapter, "_get_session", new_callable=AsyncMock) as mock_session:
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = AsyncMock(return_value={"results": {}})
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_response)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value.get.return_value = ctx
            result = await adapter._make_request(
                "https://dbpedia.org/sparql",
                params={"query": "test"},
                headers={"Custom-Header": "value"},
            )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_make_request_exception(self, adapter):
        """Test _make_request returns empty dict on exception."""
        with patch.object(adapter, "_get_session", new_callable=AsyncMock) as mock_session:
            mock_session.return_value.get.side_effect = Exception("Connection failed")
            result = await adapter._make_request("https://dbpedia.org/sparql")
        assert result == {}

    # --- search_concepts (lines 61-85) ---

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts returns converted concepts."""
        mock_data = {
            "results": {
                "bindings": [
                    {
                        "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
                        "label": {"value": "Aspirin"},
                        "abstract": {"value": "A drug used to reduce pain"},
                        "type": {"value": "http://www.w3.org/2002/07/owl#Class"},
                    }
                ]
            }
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=mock_data
        ):
            results = await adapter.search_concepts("Aspirin", limit=10)
        assert len(results) == 1
        assert results[0].primary_id == "Aspirin"

    @pytest.mark.asyncio
    async def test_search_concepts_no_results(self, adapter):
        """Test search_concepts returns empty with no results."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ):
            results = await adapter.search_concepts("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_no_bindings(self, adapter):
        """Test search_concepts returns empty with no bindings."""
        with patch.object(
            adapter,
            "run_sparql_query",
            new_callable=AsyncMock,
            return_value={"results": {}},
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_exception(self, adapter):
        """Test search_concepts returns empty on exception."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_filters_none_concepts(self, adapter):
        """Test search_concepts filters out None concepts."""
        mock_data = {
            "results": {
                "bindings": [
                    {"invalid": "data"},
                    {
                        "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
                        "label": {"value": "Aspirin"},
                    },
                ]
            }
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=mock_data
        ):
            results = await adapter.search_concepts("Aspirin")
        assert len(results) == 1

    # --- get_concept_details (lines 87-111) ---

    @pytest.mark.asyncio
    async def test_get_concept_details_with_full_uri(self, adapter):
        """Test get_concept_details with full DBpedia URI."""
        mock_data = {
            "results": {
                "bindings": [
                    {
                        "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                        "value": {"value": "Aspirin", "xml:lang": "en"},
                    }
                ]
            }
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await adapter.get_concept_details("http://dbpedia.org/resource/Aspirin")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_with_short_id(self, adapter):
        """Test get_concept_details prepends URI for short IDs."""
        mock_data = {
            "results": {
                "bindings": [
                    {
                        "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                        "value": {"value": "Aspirin", "xml:lang": "en"},
                    }
                ]
            }
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await adapter.get_concept_details("Aspirin")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_results(self, adapter):
        """Test get_concept_details returns None with no results."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ):
            result = await adapter.get_concept_details("Aspirin")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_exception(self, adapter):
        """Test get_concept_details returns None on exception."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=Exception("fail")
        ):
            result = await adapter.get_concept_details("Aspirin")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_no_bindings(self, adapter):
        """Test get_concept_details returns None with no bindings."""
        with patch.object(
            adapter,
            "run_sparql_query",
            new_callable=AsyncMock,
            return_value={"results": {}},
        ):
            result = await adapter.get_concept_details("Aspirin")
        assert result is None

    # --- _convert_dbpedia_result_to_concept (lines 113-137) ---

    def test_convert_result_basic(self, adapter):
        """Test _convert_dbpedia_result_to_concept with basic data."""
        result = {
            "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
            "label": {"value": "Aspirin"},
        }
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "Aspirin"
        assert concept.primary_label == "Aspirin"
        assert concept.concept_type == ConceptType.UNKNOWN
        assert concept.confidence_score == 0.6

    def test_convert_result_with_abstract(self, adapter):
        """Test _convert_dbpedia_result_to_concept includes abstract."""
        result = {
            "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
            "label": {"value": "Aspirin"},
            "abstract": {"value": "A common pain reliever"},
        }
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert "A common pain reliever" in concept.definitions

    def test_convert_result_long_abstract_truncated(self, adapter):
        """Test _convert_dbpedia_result_to_concept truncates long abstracts."""
        result = {
            "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
            "label": {"value": "Aspirin"},
            "abstract": {"value": "A" * 600},
        }
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert len(concept.definitions[0]) < 600
        assert concept.definitions[0].endswith("...")

    def test_convert_result_with_type(self, adapter):
        """Test _convert_dbpedia_result_to_concept adds type as category."""
        result = {
            "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
            "label": {"value": "Aspirin"},
            "type": {"value": "http://www.w3.org/2002/07/owl#Class"},
        }
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert "owl#Class" in concept.categories

    def test_convert_result_missing_resource(self, adapter):
        """Test _convert_dbpedia_result_to_concept returns None without resource."""
        result = {"label": {"value": "Test"}}
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept is None

    def test_convert_result_missing_label(self, adapter):
        """Test _convert_dbpedia_result_to_concept returns None without label."""
        result = {"resource": {"value": "http://dbpedia.org/resource/Aspirin"}}
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept is None

    def test_convert_result_short_abstract(self, adapter):
        """Test _convert_dbpedia_result_to_concept does not truncate short abstracts."""
        result = {
            "resource": {"value": "http://dbpedia.org/resource/Aspirin"},
            "label": {"value": "Aspirin"},
            "abstract": {"value": "Short abstract"},
        }
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept.definitions[0] == "Short abstract"

    def test_convert_result_exception(self, adapter):
        """Test _convert_dbpedia_result_to_concept returns None on exception."""
        concept = adapter._convert_dbpedia_result_to_concept(None)
        assert concept is None

    # --- _convert_dbpedia_entity_to_unified (lines 139-184) ---

    def test_convert_entity_with_label(self, adapter):
        """Test _convert_dbpedia_entity_to_unified finds English label."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            }
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert concept is not None
        assert concept.primary_label == "Aspirin"

    def test_convert_entity_no_label_uses_id(self, adapter):
        """Test _convert_dbpedia_entity_to_unified uses entity ID when no label."""
        properties = []
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Test_Entity", properties
        )
        assert concept is not None
        assert concept.primary_label == "Test Entity"

    def test_convert_entity_with_abstract(self, adapter):
        """Test _convert_dbpedia_entity_to_unified includes abstract when URI matches."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            },
            {
                "property": {"value": "dbo:abstract"},
                "value": {"value": "A common drug", "xml:lang": "en"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert "A common drug" in concept.definitions

    def test_convert_entity_long_abstract_truncated(self, adapter):
        """Test _convert_dbpedia_entity_to_unified truncates long abstracts."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            },
            {
                "property": {"value": "dbo:abstract"},
                "value": {"value": "A" * 1100, "xml:lang": "en"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert len(concept.definitions[0]) < 1100
        assert concept.definitions[0].endswith("...")

    def test_convert_entity_with_type(self, adapter):
        """Test _convert_dbpedia_entity_to_unified adds type as category."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            },
            {
                "property": {"value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                "value": {"value": "http://dbpedia.org/ontology/Drug"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert "Drug" in concept.categories

    def test_convert_entity_with_icd10(self, adapter):
        """Test _convert_dbpedia_entity_to_unified adds ICD-10 category."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            },
            {
                "property": {"value": "http://dbpedia.org/ontology/icd10"},
                "value": {"value": "A01"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert any("ICD-10" in c for c in concept.categories)

    def test_convert_entity_short_abstract(self, adapter):
        """Test _convert_dbpedia_entity_to_unified does not truncate short abstracts."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            },
            {
                "property": {"value": "dbo:abstract"},
                "value": {"value": "Short abstract", "xml:lang": "en"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert concept.definitions[0] == "Short abstract"

    def test_convert_entity_non_en_label_ignored(self, adapter):
        """Test _convert_dbpedia_entity_to_unified ignores non-English labels."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirina", "xml:lang": "es"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert concept.primary_label == "Aspirin"

    def test_convert_entity_non_en_abstract_ignored(self, adapter):
        """Test _convert_dbpedia_entity_to_unified ignores non-English abstract."""
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Aspirin", "xml:lang": "en"},
            },
            {
                "property": {"value": "dbo:abstract"},
                "value": {"value": "Un fármaco", "xml:lang": "es"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", properties
        )
        assert concept.definitions == []

    def test_convert_entity_exception(self, adapter):
        """Test _convert_dbpedia_entity_to_unified returns None on exception."""
        concept = adapter._convert_dbpedia_entity_to_unified(None, None)
        assert concept is None

    # --- run_sparql_query ---

    @pytest.mark.asyncio
    async def test_run_sparql_query_with_limit(self, adapter):
        """Test run_sparql_query appends LIMIT when not present."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.run_sparql_query("SELECT ?s WHERE { ?s ?p ?o }", limit=10)
            call_args = mock.call_args
            # _make_request(self, url, params, headers, json_data) -> call_args[1] has kwargs
            # but run_sparql_query passes params as keyword arg
            params = call_args.kwargs.get("params") or (call_args.args[1] if len(call_args.args) > 1 else None)
            assert params is not None
            assert "LIMIT 10" in params["query"]

    @pytest.mark.asyncio
    async def test_run_sparql_query_no_limit(self, adapter):
        """Test run_sparql_query does not add LIMIT when already present."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.run_sparql_query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 5")
            call_args = mock.call_args
            params = call_args.kwargs.get("params") or (call_args.args[1] if len(call_args.args) > 1 else None)
            assert params is not None
            assert params["query"].count("LIMIT") == 1

    @pytest.mark.asyncio
    async def test_run_sparql_query_no_limit_param(self, adapter):
        """Test run_sparql_query without limit parameter."""
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.run_sparql_query("SELECT ?s WHERE { ?s ?p ?o }")
            call_args = mock.call_args
            params = call_args.kwargs.get("params") or (call_args.args[1] if len(call_args.args) > 1 else None)
            assert params is not None
            assert "LIMIT" not in params["query"]
