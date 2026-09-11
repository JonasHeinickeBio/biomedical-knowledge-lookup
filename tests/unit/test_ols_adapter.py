"""
Unit tests for OLSAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.ols_adapter import OLSAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class TestOLSAdapter:
    """Tests for OLSAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OLSAdapter instance."""
        adapter = OLSAdapter(lookup_config)
        yield adapter
        # Cleanup: close the aiohttp session to prevent "Unclosed client session" warnings
        if adapter.session and not adapter.session.closed:
            import asyncio

            asyncio.run(adapter.close())

    def test_adapter_initialization(self, lookup_config):
        """Test OLSAdapter initialization."""
        adapter = OLSAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OLS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OLS

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
        config = LookupConfig(rate_limits={KnowledgeSource.OLS: 5.0})
        adapter = OLSAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_success(self, mock_get, adapter):
        """Test successful search concepts."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test query", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_empty_response(self, mock_get, adapter):
        """Test search concepts with empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_http_error(self, mock_get, adapter):
        """Test search concepts with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500, message="Internal Server Error"
            )
        )
        mock_get.return_value.__aenter__.return_value = mock_response

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_search_concepts_network_error(self, mock_get, adapter):
        """Test search concepts with network error."""
        mock_get.side_effect = Exception("Network error")

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
            pass


class TestOLSSearchConcepts:
    """Tests for search_concepts with OLS response structure."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OLSAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_search_with_docs(self, adapter):
        """Test search_concepts with docs in response."""
        docs = [
            {
                "iri": "http://purl.obolibrary.org/obo/DOID_9351",
                "label": "diabetes mellitus",
                "description": ["A metabolic disease"],
                "synonym": ["diabetes", "DM"],
                "ontology_name": "doid",
                "short_form": "DOID_9351",
            }
        ]
        adapter._make_request = AsyncMock(return_value={"response": {"docs": docs}})

        result = await adapter.search_concepts("diabetes", limit=10)
        assert len(result) == 1
        assert result[0].primary_label == "diabetes mellitus"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, adapter):
        """Test search respects limit parameter."""
        docs = [
            {"iri": f"http://example.com/{i}", "label": f"Term{i}", "ontology_name": "test"}
            for i in range(5)
        ]
        adapter._make_request = AsyncMock(return_value={"response": {"docs": docs}})

        result = await adapter.search_concepts("test", limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_no_response_key(self, adapter):
        """Test search with no response key."""
        adapter._make_request = AsyncMock(return_value={})
        result = await adapter.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_no_docs_key(self, adapter):
        """Test search with no docs key."""
        adapter._make_request = AsyncMock(return_value={"response": {}})
        result = await adapter.search_concepts("test")
        assert result == []


class TestOLSGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OLSAdapter(lookup_config)

    @pytest.mark.asyncio
    async def test_get_details_with_iri(self, adapter):
        """Test get_concept_details with IRI."""
        adapter._make_request = AsyncMock(
            return_value={
                "_embedded": {
                    "terms": [
                        {
                            "iri": "http://purl.obolibrary.org/obo/DOID_9351",
                            "label": "diabetes mellitus",
                            "description": ["A disease"],
                            "synonyms": ["DM"],
                            "annotation": {"database_cross_reference": ["UMLS:C0011849"]},
                        }
                    ]
                }
            }
        )

        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/DOID_9351")
        assert result is not None
        assert result.primary_label == "diabetes mellitus"

    @pytest.mark.asyncio
    async def test_get_details_no_iri(self, adapter):
        """Test get_concept_details with non-IRI returns None."""
        result = await adapter.get_concept_details("DOID:9351")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_no_terms(self, adapter):
        """Test get_concept_details when no terms returned."""
        adapter._make_request = AsyncMock(return_value={"_embedded": {"terms": []}})

        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/DOID_9351")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_exception(self, adapter):
        """Test get_concept_details handles exceptions."""
        adapter._make_request = AsyncMock(side_effect=Exception("Error"))

        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/DOID_9351")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_no_embedded(self, adapter):
        """Test get_concept_details with no _embedded key."""
        adapter._make_request = AsyncMock(return_value={})
        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/DOID_9351")
        assert result is None


class TestOLSConvertResult:
    """Tests for _convert_ols_result_to_concept method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OLSAdapter(lookup_config)

    def test_convert_result_valid(self, adapter):
        """Test conversion with valid result."""
        result = {
            "iri": "http://purl.obolibrary.org/obo/DOID_9351",
            "label": "diabetes mellitus",
            "description": ["A metabolic disease"],
            "synonym": ["diabetes", "DM"],
            "ontology_name": "doid",
            "short_form": "DOID_9351",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "diabetes mellitus"
        assert "diabetes" in concept.synonyms

    def test_convert_result_no_iri(self, adapter):
        """Test returns None when no iri."""
        result = {"label": "Test"}
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_label(self, adapter):
        """Test returns None when no label."""
        result = {"iri": "http://example.com/1"}
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept is None

    def test_convert_result_synonym_as_string(self, adapter):
        """Test handles synonym as string."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "synonym": "single_syn",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert "single_syn" in concept.synonyms

    def test_convert_result_description_as_string(self, adapter):
        """Test handles description as string."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "description": "single description",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert "single description" in concept.definitions

    def test_convert_result_no_short_form(self, adapter):
        """Test conversion without short_form."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "ontology_name": "test",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept is not None

    def test_convert_result_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.ols_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_ols_result_to_concept({"iri": "test", "label": "test"})
            assert result is None

    def test_convert_result_disease_ontology(self, adapter):
        """Test detects disease ontology."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "ontology_name": "doid",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept.concept_type == ConceptType.DISEASE

    def test_convert_result_drug_ontology(self, adapter):
        """Test detects drug ontology."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "ontology_name": "drugbank",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept.concept_type == ConceptType.DRUG

    def test_convert_result_gene_ontology(self, adapter):
        """Test detects gene ontology."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "ontology_name": "go",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept.concept_type == ConceptType.GENE

    def test_convert_result_anatomy_ontology(self, adapter):
        """Test detects anatomy ontology."""
        result = {
            "iri": "http://example.com/1",
            "label": "Test",
            "ontology_name": "uberon",
        }
        concept = adapter._convert_ols_result_to_concept(result)
        assert concept.concept_type == ConceptType.ANATOMICAL_ENTITY


class TestOLSConvertConcept:
    """Tests for _convert_ols_concept_to_unified method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OLSAdapter(lookup_config)

    def test_convert_concept_valid(self, adapter):
        """Test detailed concept conversion."""
        data = {
            "iri": "http://purl.obolibrary.org/obo/DOID_9351",
            "label": "diabetes mellitus",
            "synonyms": ["DM"],
            "description": ["A disease"],
            "annotation": {"database_cross_reference": ["UMLS:C0011849"]},
            "obo_xref": [{"database": "UMLS", "id": "C0011849"}],
        }
        concept = adapter._convert_ols_concept_to_unified(data)
        assert concept is not None
        assert concept.primary_label == "diabetes mellitus"
        assert "DM" in concept.synonyms
        assert any("Xref:" in c for c in concept.categories)

    def test_convert_concept_no_iri(self, adapter):
        """Test returns None when no iri."""
        data = {"label": "Test"}
        concept = adapter._convert_ols_concept_to_unified(data)
        assert concept is None

    def test_convert_concept_no_label(self, adapter):
        """Test returns None when no label."""
        data = {"iri": "http://example.com/1"}
        concept = adapter._convert_ols_concept_to_unified(data)
        assert concept is None

    def test_convert_concept_xrefs_as_string(self, adapter):
        """Test handles database_cross_reference as string."""
        data = {
            "iri": "http://example.com/1",
            "label": "Test",
            "annotation": {"database_cross_reference": "UMLS:C0001"},
        }
        concept = adapter._convert_ols_concept_to_unified(data)
        assert any("Xref: UMLS:C0001" in c for c in concept.categories)

    def test_convert_concept_no_xrefs(self, adapter):
        """Test handles no xrefs."""
        data = {
            "iri": "http://example.com/1",
            "label": "Test",
        }
        concept = adapter._convert_ols_concept_to_unified(data)
        assert concept is not None

    def test_convert_concept_obo_xref_empty_db(self, adapter):
        """Test handles obo_xref with empty db/id."""
        data = {
            "iri": "http://example.com/1",
            "label": "Test",
            "obo_xref": [{"database": "", "id": ""}],
        }
        concept = adapter._convert_ols_concept_to_unified(data)
        assert concept is not None

    def test_convert_concept_description_as_string(self, adapter):
        """Test handles description as string."""
        data = {
            "iri": "http://example.com/1",
            "label": "Test",
            "description": "single description",
        }
        concept = adapter._convert_ols_concept_to_unified(data)
        assert "single description" in concept.definitions

    def test_convert_concept_with_links(self, adapter):
        """Test handles _links with parents/children."""
        data = {
            "iri": "http://example.com/1",
            "label": "Test",
            "_links": {
                "parents": {"href": "http://example.com/parents"},
                "children": {"href": "http://example.com/children"},
            },
        }
        concept = adapter._convert_ols_concept_to_unified(data)
        assert concept is not None

    def test_convert_concept_exception(self, adapter):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.ols_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter._convert_ols_concept_to_unified({"iri": "test", "label": "test"})
            assert result is None


class TestOLSDetermineConceptType:
    """Tests for _determine_concept_type_from_ontology method."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return OLSAdapter(lookup_config)

    def test_disease_doid(self, adapter):
        assert adapter._determine_concept_type_from_ontology("doid") == ConceptType.DISEASE

    def test_disease_mondo(self, adapter):
        assert adapter._determine_concept_type_from_ontology("mondo") == ConceptType.DISEASE

    def test_disease_ordo(self, adapter):
        assert adapter._determine_concept_type_from_ontology("ordo") == ConceptType.DISEASE

    def test_phenotype_hp(self, adapter):
        # "hp" (Human Phenotype Ontology) is a phenotype ontology, not a
        # disease one — it used to be listed in both branches, with the
        # disease branch shadowing the phenotype one since it came first.
        assert adapter._determine_concept_type_from_ontology("hp") == ConceptType.PHENOTYPE

    def test_chemical_chebi(self, adapter):
        # ChEBI ("Chemical Entities of Biological Interest") is the chemical
        # ontology; it used to be shadowed by an earlier "chebi" -> DRUG
        # branch and never actually reachable.
        assert adapter._determine_concept_type_from_ontology("chebi") == ConceptType.CHEMICAL

    def test_drug_drugbank(self, adapter):
        assert adapter._determine_concept_type_from_ontology("drugbank") == ConceptType.DRUG

    def test_gene_go(self, adapter):
        assert adapter._determine_concept_type_from_ontology("go") == ConceptType.GENE

    def test_gene_so(self, adapter):
        assert adapter._determine_concept_type_from_ontology("so") == ConceptType.GENE

    def test_gene_pr(self, adapter):
        assert adapter._determine_concept_type_from_ontology("pr") == ConceptType.GENE

    def test_anatomy_uberon(self, adapter):
        assert (
            adapter._determine_concept_type_from_ontology("uberon")
            == ConceptType.ANATOMICAL_ENTITY
        )

    def test_anatomy_fma(self, adapter):
        assert (
            adapter._determine_concept_type_from_ontology("fma") == ConceptType.ANATOMICAL_ENTITY
        )

    def test_anatomy_ma(self, adapter):
        assert adapter._determine_concept_type_from_ontology("ma") == ConceptType.ANATOMICAL_ENTITY

    def test_phenotype_mp(self, adapter):
        assert adapter._determine_concept_type_from_ontology("mp") == ConceptType.PHENOTYPE

    def test_phenotype_zp(self, adapter):
        assert adapter._determine_concept_type_from_ontology("zp") == ConceptType.PHENOTYPE

    def test_organism_ncbitaxon(self, adapter):
        assert adapter._determine_concept_type_from_ontology("ncbitaxon") == ConceptType.ORGANISM

    def test_unknown(self, adapter):
        assert adapter._determine_concept_type_from_ontology("unknown") == ConceptType.UNKNOWN
