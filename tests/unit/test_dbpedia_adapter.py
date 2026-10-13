"""
Unit tests for DBpediaAdapter.
"""

import re
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
        with patch.object(adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}):
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
        with patch.object(adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}):
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
                "property": {"value": "http://dbpedia.org/ontology/abstract"},
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
                "property": {"value": "http://dbpedia.org/ontology/abstract"},
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
                "property": {"value": "http://dbpedia.org/ontology/abstract"},
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
                "property": {"value": "http://dbpedia.org/ontology/abstract"},
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

    # --- regression tests: property IRIs, SPARQL injection, log level ---

    @staticmethod
    def _structure(sparql: str) -> str:
        """Query text with string literals and IRIs blanked, to compare query structure."""
        import re

        without_literals = re.sub(r'"(?:[^"\\\n\r]|\\.)*"', '""', sparql)
        return re.sub(r"<[^<>\s]*>", "<>", without_literals)

    def test_convert_entity_real_bindings_extract_label_and_abstract(self, adapter):
        """Regression: full property IRIs (as DBpedia returns them) match label and abstract."""
        # Shaped like the live SPARQL JSON bindings for a DBpedia resource
        properties = [
            {
                "property": {"type": "uri", "value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {
                    "type": "literal",
                    "xml:lang": "en",
                    "value": "Type 2 diabetes mellitus",
                },
            },
            {
                "property": {"type": "uri", "value": "http://dbpedia.org/ontology/abstract"},
                "value": {"type": "literal", "xml:lang": "en", "value": "A metabolic disorder."},
            },
            {
                "property": {
                    "type": "uri",
                    "value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                },
                "value": {"type": "uri", "value": "http://dbpedia.org/ontology/Disease"},
            },
            {
                "property": {"type": "uri", "value": "http://dbpedia.org/ontology/icd10"},
                "value": {"type": "literal", "value": "E11"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Type_2_diabetes", properties
        )
        assert concept.primary_label == "Type 2 diabetes mellitus"
        assert concept.definitions == ["A metabolic disorder."]
        assert "Disease" in concept.categories
        assert "ICD-10: E11" in concept.categories

    @pytest.mark.asyncio
    async def test_search_query_injection_is_escaped(self, adapter):
        """Regression: search text cannot change the structure of the SPARQL query."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.search_concepts("aspirin", limit=5)
            benign = mock.call_args.args[0]
            await adapter.search_concepts(
                "aspirin' . } } SELECT * WHERE { ?s ?p ?o } #\"\\", limit=5
            )
            injected = mock.call_args.args[0]
        assert self._structure(injected) == self._structure(benign)
        assert "bif:contains \"'aspirin SELECT WHERE s p o'\"" in injected

    @pytest.mark.asyncio
    async def test_search_without_words_makes_no_request(self, adapter):
        """A query with no word characters returns [] without querying DBpedia."""
        with patch.object(adapter, "run_sparql_query", new_callable=AsyncMock) as mock:
            assert await adapter.search_concepts("'\"{}") == []
        mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_concept_details_iri_injection_is_encoded(self, adapter):
        """Regression: characters that would close the <IRI> are percent-encoded."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.get_concept_details("Aspirin")
            benign = mock.call_args.args[0]
            await adapter.get_concept_details("Aspirin> ?p ?o } SELECT * WHERE { <x")
            injected = mock.call_args.args[0]
        assert self._structure(injected) == self._structure(benign)
        assert "<http://dbpedia.org/resource/Aspirin%3E_?p_?o_%7D_SELECT_*_WHERE_%7B_%3Cx>" in (
            injected
        )

    @pytest.mark.asyncio
    async def test_get_concept_details_unknown_resource_returns_none(self, adapter):
        """A resource without any bindings does not exist; no fallback concept is built."""
        with patch.object(
            adapter,
            "run_sparql_query",
            new_callable=AsyncMock,
            return_value={"head": {"vars": ["property", "value"]}, "results": {"bindings": []}},
        ):
            assert await adapter.get_concept_details("No_such_resource_xyz") is None

    def test_convert_entity_deduplicates_types(self, adapter):
        """DBpedia repeats rdf:type rows (one per graph); categories list each type once."""
        type_row = {
            "property": {"value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
            "value": {"type": "uri", "value": "http://dbpedia.org/ontology/Disease"},
        }
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Type_2_diabetes", [type_row, type_row, type_row]
        )
        assert concept.categories == ["Disease"]

    @pytest.mark.asyncio
    async def test_get_concept_details_filters_to_english(self, adapter):
        """Labels in other languages are filtered out so they do not fill the LIMIT."""
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.get_concept_details("Aspirin")
        assert 'langMatches(lang(?value), "en")' in mock.call_args.args[0]

    @pytest.mark.asyncio
    async def test_make_request_logs_params_only_at_debug(self, adapter, caplog):
        """Regression: request params and headers are not logged at INFO."""
        import logging

        from knowledge_lookup.base import KnowledgeSourceAdapter

        logger_name = "knowledge_lookup.adapters.dbpedia_adapter"
        with patch.object(
            KnowledgeSourceAdapter, "_make_request", new_callable=AsyncMock, return_value={}
        ):
            caplog.set_level(logging.INFO, logger=logger_name)
            await adapter._make_request(
                "https://dbpedia.org/sparql", params={"query": "q"}, headers={"X": "y"}
            )
            assert not [r for r in caplog.records if "Request" in r.getMessage()]

            caplog.set_level(logging.DEBUG, logger=logger_name)
            await adapter._make_request(
                "https://dbpedia.org/sparql", params={"query": "q"}, headers={"X": "y"}
            )
            debug_records = [r for r in caplog.records if "Request" in r.getMessage()]
        assert debug_records
        assert all(r.levelno == logging.DEBUG for r in debug_records)

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
            params = call_args.kwargs.get("params") or (
                call_args.args[1] if len(call_args.args) > 1 else None
            )
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
            params = call_args.kwargs.get("params") or (
                call_args.args[1] if len(call_args.args) > 1 else None
            )
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
            params = call_args.kwargs.get("params") or (
                call_args.args[1] if len(call_args.args) > 1 else None
            )
            assert params is not None
            assert "LIMIT" not in params["query"]

    @staticmethod
    def _search_row(name: str, type_iri: str, abstract: str | None = None) -> dict:
        row = {
            "resource": {"value": f"http://dbpedia.org/resource/{name}"},
            "label": {"value": name.replace("_", " ")},
            "type": {"value": type_iri},
        }
        if abstract is not None:
            row["abstract"] = {"value": abstract}
        return row

    @pytest.mark.asyncio
    async def test_search_returns_each_resource_once_with_merged_types(self, adapter):
        """Regression: one row per rdf:type repeated a resource and the repeats used up `limit`."""
        thing = "http://www.w3.org/2002/07/owl#Thing"
        drug = "http://dbpedia.org/ontology/Drug"
        rows = [
            self._search_row("Metformin", thing),
            self._search_row("Metformin", drug, "An antidiabetic drug."),
            self._search_row("Metformin", thing),
            self._search_row("Metformin_hydrochloride", drug),
            self._search_row("Buformin", drug),
        ]
        with patch.object(
            adapter,
            "run_sparql_query",
            new_callable=AsyncMock,
            return_value={"results": {"bindings": rows}},
        ):
            results = await adapter.search_concepts("metformin", limit=2)

        assert [c.primary_id for c in results] == ["Metformin", "Metformin_hydrochloride"]
        assert results[0].categories == ["owl#Thing", "Drug"]
        assert results[0].definitions == ["An antidiabetic drug."]
        assert results[1].categories == ["Drug"]

    @pytest.mark.asyncio
    async def test_search_limits_resources_in_a_subquery(self, adapter):
        import re

        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.search_concepts("metformin", limit=5)

        sparql = mock.call_args.args[0]
        # LIMIT closes the resource subquery, before the rdf:type join multiplies the rows
        assert re.search(
            r"SELECT DISTINCT \?resource \?label .*LIMIT 5\s*\}\s*OPTIONAL", sparql, re.S
        )
        assert "limit" not in mock.call_args.kwargs


def _prop(prop_iri, value, lang=None, kind="literal"):
    cell = {"type": kind, "value": value}
    if lang:
        cell["xml:lang"] = lang
    return {"property": {"type": "uri", "value": prop_iri}, "value": cell}


_DBO = "http://dbpedia.org/ontology/"
_SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"


class TestDBpediaExternalIdentifiers:
    """Identifiers surfaced by get_concept_details (values from live DBpedia)."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return DBpediaAdapter(lookup_config)

    def _crohn(self, adapter):
        rows = [
            _prop("http://www.w3.org/2000/01/rdf-schema#label", "Crohn's disease", "en"),
            _prop(f"{_DBO}meshId", "D003424"),
            _prop(f"{_DBO}omim", "266600"),
            _prop(f"{_DBO}medlinePlus", "000249"),
            _prop(f"{_DBO}icd10", "K50"),
            _prop(f"{_DBO}icd9", "555"),
            _prop(f"{_DBO}diseasesDB", "3178"),
            _prop(_SAME_AS, "http://www.wikidata.org/entity/Q1472", kind="uri"),
            _prop(_SAME_AS, "http://rdf.freebase.com/ns/m.0h1n9", kind="uri"),
            _prop(_SAME_AS, "http://wikidata.org/entity/Q1472", kind="uri"),
        ]
        return adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Crohn's_disease", rows
        )

    def test_disease_identifiers(self, adapter):
        concept = self._crohn(adapter)

        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ids >= {
            (KnowledgeSource.DBPEDIA, "Crohn's_disease"),
            (KnowledgeSource.WIKIDATA, "Q1472"),
            (KnowledgeSource.MESH, "D003424"),
            (KnowledgeSource.OMIM, "266600"),
            (KnowledgeSource.MEDLINEPLUS, "000249"),
        }
        for expected in ("ICD-10: K50", "ICD-9: 555", "DiseasesDB: 3178", "Freebase: /m/0h1n9"):
            assert expected in concept.categories

    def test_wikidata_sameas_link_is_resolvable(self, adapter):
        concept = self._crohn(adapter)
        wikidata = [i for i in concept.identifiers if i.source == KnowledgeSource.WIKIDATA]

        assert len(wikidata) == 1
        assert wikidata[0].url == "http://www.wikidata.org/entity/Q1472"

    def test_chemical_identifiers_and_prefixes(self, adapter):
        rows = [
            _prop(f"{_DBO}chEBI", "15365"),
            _prop(f"{_DBO}chEMBL", "25"),
            _prop(f"{_DBO}pubchem", "2244"),
            _prop(f"{_DBO}kegg", "D00109"),
            _prop(f"{_DBO}kegg", "C01405"),
            _prop(f"{_DBO}casNumber", "50-78-2"),
            _prop(f"{_DBO}atcCode", ","),  # junk value seen in live data
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/Aspirin", rows
        )

        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert ids >= {
            (KnowledgeSource.CHEBI, "CHEBI:15365"),
            (KnowledgeSource.CHEMBL, "CHEMBL25"),
            (KnowledgeSource.PUBCHEM, "2244"),
            (KnowledgeSource.KEGG, "D00109"),
            (KnowledgeSource.KEGG, "C01405"),
        }
        assert "CAS: 50-78-2" in concept.categories
        assert not any(c.startswith("ATC") for c in concept.categories)

    @pytest.mark.asyncio
    async def test_query_requests_identifier_properties_and_filters_sameas(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.get_concept_details("Crohn's_disease")

        sparql = mock.call_args.args[0]
        for prop in ("meshId", "omim", "medlinePlus", "icd10", "chEBI", "chEMBL", "pubchem"):
            assert f"<{_DBO}{prop}>" in sparql
        # owl:sameAs has ~70 interlanguage links; only Wikidata/Freebase are fetched
        assert "owl:sameAs" in sparql
        assert "http://www.wikidata.org/entity/" in sparql
        assert mock.call_args.kwargs["limit"] == 200


_RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
_REDIRECTS = f"{_DBO}wikiPageRedirects"


def _wikidata_links(n):
    return [
        _prop(_SAME_AS, f"http://www.wikidata.org/entity/Q{1000 + i}", kind="uri")
        for i in range(n)
    ]


class TestDBpediaLiveFindings:
    """Behaviour found by running the adapter live over ~14 resources."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return DBpediaAdapter(lookup_config)

    def _convert(self, adapter, rows, iri="http://dbpedia.org/resource/X"):
        return adapter._convert_dbpedia_entity_to_unified(iri, rows)

    def test_a_few_wikidata_links_are_kept(self, adapter):
        """Some resources merge two Wikipedia articles, e.g. Fatigue -> Q9690 and Q15729017."""
        concept = self._convert(adapter, _wikidata_links(2))
        wikidata = [i for i in concept.identifiers if i.source == KnowledgeSource.WIKIDATA]
        assert len(wikidata) == 2

    def test_an_ambiguous_wikidata_cluster_is_discarded(self, adapter):
        """P53 and Interleukin_6 each link to ~15,000 unrelated Wikidata items."""
        rows = [
            _prop(_RDFS_LABEL, "P53", "en"),
            *_wikidata_links(12),
            _prop(f"{_DBO}meshId", "D1"),
        ]
        concept = self._convert(adapter, rows)

        assert not any(i.source == KnowledgeSource.WIKIDATA for i in concept.identifiers)
        # the other identifiers on the resource are unaffected
        assert any(i.source == KnowledgeSource.MESH for i in concept.identifiers)

    @pytest.mark.parametrize(
        ("value", "kept"),
        [("N02BA01", True), ("Combinations:", False), (",", False), ("", False)],
    )
    def test_atc_values_must_look_like_atc_codes(self, adapter, value, kept):
        concept = self._convert(adapter, [_prop(f"{_DBO}atcCode", value)])
        assert any(c.startswith("ATC") for c in concept.categories) is kept

    def test_trailing_dot_is_stripped_from_icd_codes(self, adapter):
        """DBpedia stores ICD-10 for breast cancer as "C50." and for T2D as "E11."."""
        concept = self._convert(adapter, [_prop(f"{_DBO}icd10", "C50.")])
        assert "ICD-10: C50" in concept.categories

    @pytest.mark.asyncio
    async def test_redirect_pages_are_followed(self, adapter):
        """The SARS-CoV-2 resource is a redirect with no data of its own."""
        redirect = {
            "results": {
                "bindings": [
                    _prop(_REDIRECTS, "http://dbpedia.org/resource/SARS-CoV-2", kind="uri")
                ]
            }
        }
        target = {
            "results": {
                "bindings": [
                    _prop(_RDFS_LABEL, "SARS-CoV-2", "en"),
                    _prop(_SAME_AS, "http://www.wikidata.org/entity/Q82069695", kind="uri"),
                ]
            }
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=[redirect, target]
        ) as mock:
            concept = await adapter.get_concept_details(
                "Severe_acute_respiratory_syndrome_coronavirus_2"
            )

        assert mock.await_count == 2
        assert "<http://dbpedia.org/resource/SARS-CoV-2>" in mock.call_args_list[1].args[0]
        assert concept.primary_id == "SARS-CoV-2"
        assert (KnowledgeSource.WIKIDATA, "Q82069695") in {
            (i.source, i.identifier) for i in concept.identifiers
        }

    @pytest.mark.asyncio
    async def test_redirect_loops_are_bounded(self, adapter):
        loop = {
            "results": {
                "bindings": [_prop(_REDIRECTS, "http://dbpedia.org/resource/A", kind="uri")]
            }
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=loop
        ) as mock:
            await adapter.get_concept_details("A")

        assert mock.await_count == 3  # the resource plus at most two hops

    @pytest.mark.asyncio
    async def test_sameas_is_fetched_through_a_limited_subquery(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.get_concept_details("P53")

        sparql = mock.call_args.args[0]
        assert re.search(r"owl:sameAs \?value .*LIMIT 12", sparql, re.S)


def _result(*rows):
    return {"results": {"bindings": list(rows)}}


def _uri(value):
    return {"type": "uri", "value": value}


def _rel_row(prop, target, label=None):
    row = {"property": _uri(prop), "target": _uri(f"http://dbpedia.org/resource/{target}")}
    if label:
        row["label"] = {"type": "literal", "value": label, "xml:lang": "en"}
    return row


class TestDBpediaMappings:
    @pytest.fixture
    def adapter(self, lookup_config):
        return DBpediaAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_mappings_use_the_shared_shape(self, adapter):
        rows = [
            _prop(_DBO + "meshId", "D003424"),
            _prop(_DBO + "omim", "266600"),
            _prop(_DBO + "icd10", "K50."),
            _prop(_SAME_AS, "http://www.wikidata.org/entity/Q1472", kind="uri"),
        ]
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(*rows)
        ):
            mappings = await adapter.get_mappings("Crohn's_disease")

        assert {
            "fromId": "Crohn's_disease",
            "toId": "D003424",
            "fromSource": "DBpedia",
            "toSource": "MESH",
            "mappingType": "xref",
            "confidence": 0.9,
        } in mappings
        by_source = {(m["toSource"], m["toId"]): m for m in mappings}
        assert by_source[("WIKIDATA", "Q1472")]["mappingType"] == "sameAs"
        assert ("OMIM", "266600") in by_source
        assert ("ICD-10", "K50") in by_source  # label, and the trailing dot is gone

    @pytest.mark.asyncio
    async def test_mappings_apply_the_same_validation_as_details(self, adapter):
        rows = [
            _prop(_DBO + "atcCode", "Combinations:"),
            _prop(_DBO + "nciId", "-tumors/rare-soft-tissue-tumors/desmoid-tumor"),
            *_wikidata_links(9),
        ]
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(*rows)
        ):
            assert await adapter.get_mappings("P53") == []

    @pytest.mark.asyncio
    async def test_mappings_follow_redirects(self, adapter):
        redirect = _result(_prop(_REDIRECTS, "http://dbpedia.org/resource/SARS-CoV-2", kind="uri"))
        target = _result(_prop(_DBO + "meshId", "D000086402"))
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=[redirect, target]
        ):
            mappings = await adapter.get_mappings(
                "Severe_acute_respiratory_syndrome_coronavirus_2"
            )
        assert mappings[0]["fromId"] == "SARS-CoV-2"

    @pytest.mark.asyncio
    async def test_unknown_resource_and_errors_give_no_mappings(self, adapter):
        with patch.object(adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}):
            assert await adapter.get_mappings("Nope") == []
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=RuntimeError("x")
        ):
            assert await adapter.get_mappings("Nope") == []

    def test_orphacodes_are_prefixed(self, adapter):
        """Live values are bare numbers: XXYY_syndrome has dbo:orpha "10"."""
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/XXYY_syndrome",
            [_prop(_DBO + "orpha", "10"), _prop(_DBO + "orpha", "not-a-code")],
        )
        ids = [(i.source, i.identifier) for i in concept.identifiers]
        assert (KnowledgeSource.ORPHANET, "ORPHA:10") in ids
        assert len([i for i in ids if i[0] == KnowledgeSource.ORPHANET]) == 1

    def test_nci_thesaurus_ids_are_mapped_when_well_formed(self, adapter):
        concept = adapter._convert_dbpedia_entity_to_unified(
            "http://dbpedia.org/resource/X",
            [_prop(_DBO + "nciId", "C84957"), _prop(_DBO + "nciId", "junk/path")],
        )
        ids = {(i.source, i.identifier) for i in concept.identifiers}
        assert (KnowledgeSource.NCIEVS, "C84957") in ids
        assert not any(i.identifier == "junk/path" for i in concept.identifiers)


class TestDBpediaRelationships:
    @pytest.fixture
    def adapter(self, lookup_config):
        return DBpediaAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_edges_carry_the_shared_fields(self, adapter):
        rows = [
            _rel_row(_DBO + "class", "Nonsteroidal_anti-inflammatory_drug"),
            _rel_row("http://purl.org/dc/terms/subject", "Category:Aspirin", "Category:Aspirin"),
            _rel_row(
                _DBO + "routesOfAdministration", "Oral_administration", "Oral administration"
            ),
        ]
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(*rows)
        ):
            edges = await adapter.get_relationships("Aspirin")

        assert {
            "relation_label": "is_a",
            "related_id": "Nonsteroidal_anti-inflammatory_drug",
            # no English label: derived from the resource name
            "related_name": "Nonsteroidal anti-inflammatory drug",
            "source": "DBpedia",
            "property": _DBO + "class",
        } in edges
        by_label = {e["relation_label"]: e for e in edges}
        assert by_label["has_category"]["related_id"] == "Category:Aspirin"
        assert by_label["route_of_administration"]["related_name"] == "Oral administration"

    @pytest.mark.asyncio
    async def test_limit_applies_per_relation_label(self, adapter):
        rows = [_rel_row("http://purl.org/dc/terms/subject", f"Category:C{i}") for i in range(19)]
        rows.append(_rel_row(_DBO + "class", "NSAID"))
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(*rows)
        ):
            edges = await adapter.get_relationships("Aspirin", limit=3)

        labels = [e["relation_label"] for e in edges]
        assert labels.count("has_category") == 3
        assert labels.count("is_a") == 1

    @pytest.mark.asyncio
    async def test_unknown_properties_and_duplicates_are_dropped(self, adapter):
        rows = [
            _rel_row(_DBO + "somethingElse", "X"),
            _rel_row(_DBO + "symptom", "Fatigue"),
            _rel_row(_DBO + "symptom", "Fatigue"),
            _rel_row(_DBO + "treatment", "Corticosteroid"),
            _rel_row(_DBO + "medication", "Corticosteroid"),  # same label+target as treatment
        ]
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(*rows)
        ):
            edges = await adapter.get_relationships("Crohn's_disease")

        assert [(e["relation_label"], e["related_id"]) for e in edges] == [
            ("has_symptom", "Fatigue"),
            ("treated_by", "Corticosteroid"),
        ]

    @pytest.mark.asyncio
    async def test_query_selects_only_resource_targets(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.get_relationships("Crohn's disease")

        sparql = mock.call_args.args[0]
        assert "<http://dbpedia.org/resource/Crohn's_disease>" in sparql
        assert "isIRI(?target)" in sparql
        assert f"<{_DBO}symptom>" in sparql
        assert mock.call_args.kwargs["limit"] == 300

    def test_relation_labels_are_known_to_term_expansion(self):
        from knowledge_lookup.adapters.dbpedia_adapter import _RELATION_PROPERTIES
        from knowledge_lookup.core.term_expansion import is_taxonomic_relation

        assert {l for l in _RELATION_PROPERTIES.values() if is_taxonomic_relation(l)} == {"is_a"}

    @pytest.mark.asyncio
    async def test_degrades_on_error_or_bad_limit(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=RuntimeError("x")
        ):
            assert await adapter.get_relationships("Aspirin") == []
        with patch.object(adapter, "run_sparql_query", new_callable=AsyncMock) as mock:
            assert await adapter.get_relationships("Aspirin", limit=0) == []
        mock.assert_not_called()


class TestDBpediaSynonymsAndLookup:
    @pytest.fixture
    def adapter(self, lookup_config):
        return DBpediaAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_synonyms_are_redirect_titles(self, adapter):
        rows = [
            {"redirect": _uri("http://dbpedia.org/resource/Crohn%27s_disease")},  # itself
            {"redirect": _uri("http://dbpedia.org/resource/Crohn_disease")},
            {"redirect": _uri("http://dbpedia.org/resource/Morbus_Crohn")},
            {"redirect": _uri("http://dbpedia.org/resource/Crohn_disease")},
        ]
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(*rows)
        ) as mock:
            names = await adapter.get_synonyms("Crohn's_disease", limit=20)

        assert names == ["Crohn disease", "Morbus Crohn"]
        assert (
            "wikiPageRedirects <http://dbpedia.org/resource/Crohn's_disease>"
            in (mock.call_args.args[0])
        )
        assert mock.call_args.kwargs["limit"] == 20

    @pytest.mark.asyncio
    async def test_synonyms_degrade_on_error(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, side_effect=RuntimeError("x")
        ):
            assert await adapter.get_synonyms("Aspirin") == []

    @pytest.mark.asyncio
    async def test_find_by_mesh_id(self, adapter):
        row = {
            "resource": _uri("http://dbpedia.org/resource/Crohn's_disease"),
            "label": {"type": "literal", "value": "Crohn's disease", "xml:lang": "en"},
        }
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(row)
        ) as mock:
            found = await adapter.find_by_identifier(KnowledgeSource.MESH, "D003424")

        assert [c.primary_id for c in found] == ["Crohn's_disease"]
        assert found[0].primary_label == "Crohn's disease"
        assert found[0].confidence_score == 0.9
        sparql = mock.call_args.args[0]
        assert f'<{_DBO}meshId> ?id . FILTER (STR(?id) = "D003424")' in sparql

    @pytest.mark.asyncio
    async def test_find_by_wikidata_id_uses_sameas(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.find_by_identifier(KnowledgeSource.WIKIDATA, "Q1472")
        assert "owl:sameAs <http://www.wikidata.org/entity/Q1472>" in mock.call_args.args[0]

    @pytest.mark.asyncio
    async def test_find_strips_curie_prefix_for_bare_stored_ids(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.find_by_identifier("CHEBI", "CHEBI:15365")
        assert 'STR(?id) = "15365"' in mock.call_args.args[0]

    @pytest.mark.asyncio
    async def test_missing_label_falls_back_to_the_resource_name(self, adapter):
        row = {"resource": _uri("http://dbpedia.org/resource/Crohn%27s_disease")}
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value=_result(row)
        ):
            found = await adapter.find_by_identifier("OMIM", "266600")
        assert found[0].primary_label == "Crohn's disease"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("source", "identifier"),
        [
            (KnowledgeSource.BIOPORTAL, "x"),
            ("nonsense", "x"),
            (KnowledgeSource.MESH, " "),
            (KnowledgeSource.WIKIDATA, "not-a-qid"),
            (KnowledgeSource.WIKIDATA, "Q1> } #"),
        ],
    )
    async def test_unsupported_input_makes_no_request(self, adapter, source, identifier):
        with patch.object(adapter, "run_sparql_query", new_callable=AsyncMock) as mock:
            assert await adapter.find_by_identifier(source, identifier) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_identifier_is_an_escaped_literal(self, adapter):
        with patch.object(
            adapter, "run_sparql_query", new_callable=AsyncMock, return_value={}
        ) as mock:
            await adapter.find_by_identifier(KnowledgeSource.OMIM, '1") } UNION { ?s ?p ?o')
        assert 'STR(?id) = "1\\") } UNION { ?s ?p ?o")' in mock.call_args.args[0]
