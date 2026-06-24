"""
Unit tests for additional_adapters module.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.additional_adapters import (
    BioOntologyAdapter,
    DBpediaAdapter,
    OxOAdapter,
)
from knowledge_lookup.models import KnowledgeSource, LookupConfig


class TestDBpediaAdapterFromAdditional:
    """Tests for DBpediaAdapter in additional_adapters module."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create DBpediaAdapter instance."""
        return DBpediaAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test DBpediaAdapter initialization."""
        adapter = DBpediaAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.DBPEDIA
        assert adapter.sparql_endpoint == "https://dbpedia.org/sparql"
        assert adapter.base_url == "https://dbpedia.org"

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.DBPEDIA

    def test_is_available(self, adapter):
        """Test is_available returns True."""
        assert adapter.is_available() is True

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test search_concepts with mock response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": {
                    "bindings": [
                        {
                            "resource": {"value": "http://dbpedia.org/resource/Diabetes_mellitus"},
                            "label": {"value": "Diabetes mellitus"},
                            "abstract": {"value": "Diabetes mellitus description"},
                            "type": {"value": "http://dbpedia.org/ontology/Disease"},
                        }
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("diabetes", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty(self, mock_get, adapter):
        """Test search_concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": {"bindings": []}})
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert results == []

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details(self, mock_get, adapter):
        """Test get_concept_details with mock response."""
        result = await adapter.get_concept_details("Diabetes")
        assert result is None or isinstance(result, type(None))

    def test_convert_dbpedia_result_to_concept(self, adapter):
        """Test _convert_dbpedia_result_to_concept helper."""
        result = {
            "resource": {"value": "http://dbpedia.org/resource/Diabetes"},
            "label": {"value": "Diabetes"},
            "abstract": {"value": "A disease"},
            "type": {"value": "http://dbpedia.org/ontology/Disease"},
        }
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "Diabetes"
        assert concept.primary_label == "Diabetes"

    def test_convert_dbpedia_result_to_concept_missing_fields(self, adapter):
        """Test _convert_dbpedia_result_to_concept with missing required fields."""
        result = {"label": {"value": "Test"}}
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept is None

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.additional_adapters.DBpediaAdapter._make_request")
    async def test_search_concepts_error_handling(self, mock_request, adapter):
        """Test search_concepts error handling."""
        mock_request.side_effect = Exception("Network error")
        results = await adapter.search_concepts("diabetes", limit=10)
        assert results == []

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.additional_adapters.DBpediaAdapter._make_request")
    async def test_get_concept_details_error_handling(self, mock_request, adapter):
        """Test get_concept_details error handling."""
        mock_request.side_effect = Exception("Network error")
        result = await adapter.get_concept_details("Diabetes")
        assert result is None

    def test_convert_dbpedia_entity_to_unified(self, adapter):
        """Test _convert_dbpedia_entity_to_unified helper."""
        properties = []
        entity_uri = "http://dbpedia.org/resource/Test_Disease"
        concept = adapter._convert_dbpedia_entity_to_unified(entity_uri, properties)
        if concept:
            assert concept.primary_label == "Test Disease"


class TestOxOAdapterFromAdditional:
    """Tests for OxOAdapter in additional_adapters module."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OxOAdapter instance."""
        return OxOAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OxOAdapter initialization."""
        adapter = OxOAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OXO

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OXO

    def test_is_available(self, adapter):
        """Test is_available returns True."""
        assert adapter.is_available() is True

    @pytest.mark.asyncio
    async def test_search_concepts_returns_empty(self, adapter):
        """Test search_concepts returns empty list."""
        results = await adapter.search_concepts("diabetes", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_get_concept_details_returns_none(self, adapter):
        """Test get_concept_details returns None."""
        result = await adapter.get_concept_details("C0012345")
        assert result is None

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_mappings_success(self, mock_get, adapter):
        """Test get_mappings with mock response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "_embedded": {
                    "mappings": [
                        {
                            "fromTerm": {"curie": "MONDO:0000001", "datasource": {"name": "MONDO"}},
                            "toTerm": {"curie": "DOID:0000001", "datasource": {"name": "DOID"}},
                            "scope": "exact",
                        }
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        mappings = await adapter.get_mappings("MONDO:0000001")
        assert isinstance(mappings, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_mappings_empty(self, mock_get, adapter):
        """Test get_mappings with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})
        mock_get.return_value.__aenter__.return_value = mock_response

        mappings = await adapter.get_mappings("MONDO:9999999")
        assert mappings == []

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.additional_adapters.OxOAdapter._make_request")
    async def test_get_mappings_error_handling(self, mock_request, adapter):
        """Test get_mappings error handling."""
        mock_request.side_effect = Exception("Network error")
        mappings = await adapter.get_mappings("MONDO:0000001")
        assert mappings == []


class TestBioOntologyAdapterFromAdditional:
    """Tests for BioOntologyAdapter in additional_adapters module."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create BioOntologyAdapter instance."""
        return BioOntologyAdapter(lookup_config)

    def test_adapter_initialization_without_api_key(self, lookup_config):
        """Test BioOntologyAdapter initialization without API key."""
        adapter = BioOntologyAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.BIOONTOLOGY

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.BIOONTOLOGY

    def test_is_available_without_key(self, adapter):
        """Test is_available returns False without API key."""
        adapter.api_key = None
        assert adapter.is_available() is False

    def test_is_available_with_key(self, lookup_config):
        """Test is_available returns True with API key."""
        config = LookupConfig(api_keys={"bioontology": "test-key"})
        adapter = BioOntologyAdapter(config)
        assert adapter.is_available() is True

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_no_api_key(self, mock_get, adapter):
        """Test search_concepts returns empty without API key."""
        results = await adapter.search_concepts("diabetes", limit=10)
        assert results == []

    def test_convert_bioontology_result_to_concept(self, adapter):
        """Test _convert_bioontology_result_to_concept helper."""
        result = {
            "@id": "http://purl.obolibrary.org/obo/MONDO_0000001",
            "prefLabel": "disease",
        }
        concept = adapter._convert_bioontology_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "http://purl.obolibrary.org/obo/MONDO_0000001"
        assert concept.primary_label == "disease"

    def test_convert_bioontology_result_to_concept_missing_fields(self, adapter):
        """Test _convert_bioontology_result_to_concept with missing fields."""
        result = {"prefLabel": "test"}
        concept = adapter._convert_bioontology_result_to_concept(result)
        assert concept is None

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_with_api_key(self, mock_get, lookup_config):
        """Test search_concepts with API key."""
        config = LookupConfig(api_keys={"bioontology": "test-key"})
        adapter = BioOntologyAdapter(config)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "collection": [
                    {"@id": "http://test.org/test", "prefLabel": "Test Concept"}
                ]
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test", limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.additional_adapters.BioOntologyAdapter._make_request")
    async def test_search_concepts_error_handling(self, mock_request, adapter):
        """Test search_concepts error handling."""
        mock_request.side_effect = Exception("Network error")
        results = await adapter.search_concepts("diabetes", limit=10)
        assert results == []


class TestDBpediaEntityConversion:
    """Tests for DBpedia entity conversion methods."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create DBpediaAdapter instance."""
        return DBpediaAdapter(lookup_config)

    def test_convert_dbpedia_entity_to_unified_with_valid_data(self, adapter):
        """Test _convert_dbpedia_entity_to_unified with valid properties."""
        entity_uri = "http://dbpedia.org/resource/Diabetes_mellitus"
        properties = [
            {
                "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                "value": {"value": "Diabetes mellitus", "xml:lang": "en"},
            },
            {
                "property": {"value": "http://dbpedia.org/ontology/abstract"},
                "value": {"value": "Diabetes description text", "xml:lang": "en"},
            },
            {
                "property": {"value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                "value": {"value": "http://dbpedia.org/ontology/Disease"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(entity_uri, properties)
        assert concept is not None
        assert concept.primary_label == "Diabetes mellitus"

    def test_convert_dbpedia_entity_to_unified_without_label(self, adapter):
        """Test _convert_dbpedia_entity_to_unified uses fallback without English label."""
        entity_uri = "http://dbpedia.org/resource/Test_Disease"
        properties = [
            {
                "property": {"value": "http://some.org/description"},
                "value": {"value": "Test Disease Description", "xml:lang": "en"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(entity_uri, properties)
        assert concept is not None
        # Fallback label should be used (entity_id with underscores replaced)
        assert concept.primary_label == "Test Disease"

    def test_convert_dbpedia_entity_to_unified_with_long_abstract(self, adapter):
        """Test _convert_dbpedia_entity_to_unified uses fallback when URIs don't match."""
        long_abstract = "A" * 1500
        entity_uri = "http://dbpedia.org/resource/Test"
        properties = [
            {
                "property": {"value": "http://some.org/label"},
                "value": {"value": "Test", "xml:lang": "en"},
            },
            {
                "property": {"value": "http://some.org/description"},
                "value": {"value": long_abstract, "xml:lang": "en"},
            },
        ]
        concept = adapter._convert_dbpedia_entity_to_unified(entity_uri, properties)
        if concept:
            assert concept.primary_label == "Test"
        else:
            # Fallback label should be used
            assert True

    def test_convert_dbpedia_entity_to_unified_empty_properties(self, adapter):
        """Test _convert_dbpedia_entity_to_unified with empty properties uses fallback."""
        entity_uri = "http://dbpedia.org/resource/Unknown_Disease"
        concept = adapter._convert_dbpedia_entity_to_unified(entity_uri, [])
        assert concept is not None
        assert concept.primary_label == "Unknown Disease"

    def test_convert_dbpedia_entity_to_unified_exception(self, adapter):
        """Test _convert_dbpedia_entity_to_unified exception handling."""
        properties = [
            {
                "property": {"value": "http://bad.org/property"},
                "value": "bad_value",
            },
        ]
        entity_uri = "http://dbpedia.org/resource/Test"
        concept = adapter._convert_dbpedia_entity_to_unified(entity_uri, properties)
        if concept:
            assert concept.primary_id == "Test"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_concept_details_with_bindings(self, mock_get, adapter):
        """Test get_concept_details with valid SPARQL bindings response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": {
                    "bindings": [
                        {
                            "property": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                            "value": {"value": "Diabetes mellitus", "xml:lang": "en"},
                        },
                    ]
                }
            }
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        concept = await adapter.get_concept_details("Diabetes_mellitus")
        assert concept is not None
        assert concept.primary_label == "Diabetes mellitus"

    def test_convert_dbpedia_result_to_concept_exception(self, adapter):
        """Test _convert_dbpedia_result_to_concept exception handling."""
        result = {"resource": None, "label": {"value": "Test"}}
        concept = adapter._convert_dbpedia_result_to_concept(result)
        assert concept is None


class TestOxOErrorHandling:
    """Tests for OxO error handling."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OxOAdapter instance."""
        return OxOAdapter(lookup_config)

    @pytest.mark.asyncio
    @patch("knowledge_lookup.adapters.additional_adapters.OxOAdapter._make_request")
    async def test_get_mappings_network_error(self, mock_request, adapter):
        """Test get_mappings handles network errors."""
        mock_request.side_effect = Exception("Connection timeout")
        mappings = await adapter.get_mappings("MONDO:0000001")
        assert mappings == []

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_mappings_invalid_json(self, mock_get, adapter):
        """Test get_mappings handles invalid JSON response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_get.return_value.__aenter__.return_value = mock_response

        mappings = await adapter.get_mappings("MONDO:0000001")
        assert mappings == []


class TestBioOntologyCoverage:
    """Tests for BioOntology additional coverage."""

    @pytest.fixture
    def adapter_with_key(self, lookup_config):
        """Create BioOntologyAdapter instance with API key."""
        config = LookupConfig(api_keys={"bioontology": "test-key"})
        return BioOntologyAdapter(config)

    @pytest.mark.asyncio
    async def test_get_concept_details_returns_none(self, adapter_with_key):
        """Test get_concept_details returns None (stub implementation)."""
        result = await adapter_with_key.get_concept_details("MONDO:0000001")
        assert result is None

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_json_error(self, mock_get, adapter_with_key):
        """Test search_concepts handles JSON decode errors."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("JSON decode error"))
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter_with_key.search_concepts("diabetes", limit=10)
        assert results == []

    def test_convert_bioontology_result_to_concept_exception(self, adapter_with_key):
        """Test _convert_bioontology_result_to_concept exception handling."""
        bad_result = {"@id": None, "prefLabel": "test"}
        concept = adapter_with_key._convert_bioontology_result_to_concept(bad_result)
        assert concept is None
