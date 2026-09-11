"""
Unit tests for BioPortalAdapter.
"""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class TestBioPortalAdapter:
    """Tests for BioPortalAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create BioPortalAdapter instance."""
        return BioPortalAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create BioPortalAdapter with API key."""
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test BioPortalAdapter initialization."""
        adapter = BioPortalAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.BIOPORTAL

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.BIOPORTAL

    def test_is_available(self, adapter):
        """Test is_available method."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.BIOPORTAL: 5.0})
        adapter = BioPortalAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass


class TestBioPortalSearchConcepts:
    """Tests for search_concepts method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    @pytest.mark.asyncio
    async def test_search_no_api_key(self, adapter_with_api_key):
        """Test search_concepts returns empty when no API key."""
        adapter_with_api_key.api_key = None
        result = await adapter_with_api_key.search_concepts("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_with_collection_items(self, adapter_with_api_key):
        """Test search_concepts with collection items."""
        collection = [
            {
                "@id": "http://purl.bioontology.org/ontology/SNOMEDCT/123",
                "prefLabel": "Diabetes",
                "synonym": ["DM"],
                "definition": ["A disease"],
                "links": {"ontology": "http://data.bioontology.org/ontologies/SNOMEDCT"},
            }
        ]
        adapter_with_api_key._make_request = AsyncMock(return_value={"collection": collection})
        result = await adapter_with_api_key.search_concepts("diabetes", limit=10)
        assert len(result) == 1
        assert result[0].primary_label == "Diabetes"

    @pytest.mark.asyncio
    async def test_search_filters_by_limit(self, adapter_with_api_key):
        """Test search_concepts respects limit."""
        collection = [
            {"@id": f"http://example.com/{i}", "prefLabel": f"Term{i}"} for i in range(5)
        ]
        adapter_with_api_key._make_request = AsyncMock(return_value={"collection": collection})
        result = await adapter_with_api_key.search_concepts("test", limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_http_error(self, adapter_with_api_key):
        """Test search handles HTTP errors."""
        adapter_with_api_key._make_request = AsyncMock(side_effect=aiohttp.ClientError("Error"))
        result = await adapter_with_api_key.search_concepts("test")
        assert result == []


class TestBioPortalGetConceptDetails:
    """Tests for get_concept_details method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    @pytest.mark.asyncio
    async def test_get_details_no_api_key(self, adapter_with_api_key):
        """Test get_concept_details returns None without API key."""
        adapter_with_api_key.api_key = None
        result = await adapter_with_api_key.get_concept_details("http://example.com/ontology/123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_no_slash(self, adapter_with_api_key):
        """Test get_concept_details returns None for concept without slash."""
        result = await adapter_with_api_key.get_concept_details("NOSLASH")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_short_parts(self, adapter_with_api_key):
        """Test get_concept_details returns None for short parts."""
        result = await adapter_with_api_key.get_concept_details("only-one-part")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_details_with_slash(self, adapter_with_api_key):
        """Test get_concept_details extracts ontology from URL."""
        adapter_with_api_key._make_request = AsyncMock(
            return_value={"@id": "http://example.com/ontology/123", "prefLabel": "Test"}
        )
        result = await adapter_with_api_key.get_concept_details("http://example.com/ontology/123")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_details_exception(self, adapter_with_api_key):
        """Test get_concept_details handles exceptions."""
        adapter_with_api_key._make_request = AsyncMock(side_effect=Exception("Error"))
        result = await adapter_with_api_key.get_concept_details("http://example.com/ontology/123")
        assert result is None


class TestBioPortalConvertResult:
    """Tests for _convert_bioportal_result_to_concept method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    def test_convert_result_valid(self, adapter_with_api_key):
        """Test conversion with valid result."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Diabetes",
            "synonym": ["DM", "Diabetes Mellitus"],
            "definition": ["A metabolic disease"],
            "links": {"ontology": "http://data.bioontology.org/ontologies/DOID"},
        }
        concept = adapter_with_api_key._convert_bioportal_result_to_concept(result)
        assert concept is not None
        assert concept.primary_label == "Diabetes"
        assert "DM" in concept.synonyms
        assert "A metabolic disease" in concept.definitions

    def test_convert_result_no_id(self, adapter_with_api_key):
        """Test conversion returns None when no @id."""
        result = {"prefLabel": "Test"}
        concept = adapter_with_api_key._convert_bioportal_result_to_concept(result)
        assert concept is None

    def test_convert_result_no_label(self, adapter_with_api_key):
        """Test conversion returns None when no prefLabel."""
        result = {"@id": "http://example.com/1"}
        concept = adapter_with_api_key._convert_bioportal_result_to_concept(result)
        assert concept is None

    def test_convert_result_synonyms_as_string(self, adapter_with_api_key):
        """Test conversion handles synonym as string."""
        result = {"@id": "http://example.com/1", "prefLabel": "Test", "synonym": "single_synonym"}
        concept = adapter_with_api_key._convert_bioportal_result_to_concept(result)
        assert "single_synonym" in concept.synonyms

    def test_convert_result_definitions_as_string(self, adapter_with_api_key):
        """Test conversion handles definition as string."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "definition": "single definition",
        }
        concept = adapter_with_api_key._convert_bioportal_result_to_concept(result)
        assert "single definition" in concept.definitions

    def test_convert_result_disease_type(self, adapter_with_api_key):
        """Test detects disease type."""
        result = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "links": {"ontology": "http://data.bioontology.org/ontologies/DOID"},
        }
        concept = adapter_with_api_key._convert_bioportal_result_to_concept(result)
        assert concept.concept_type == ConceptType.DISEASE

    def test_convert_result_exception(self, adapter_with_api_key):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.bioportal_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter_with_api_key._convert_bioportal_result_to_concept(
                {"@id": "test", "prefLabel": "test"}
            )
            assert result is None


class TestBioPortalConvertConcept:
    """Tests for _convert_bioportal_concept_to_unified method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    def test_convert_concept_valid(self, adapter_with_api_key):
        """Test detailed concept conversion."""
        data = {
            "@id": "http://example.com/1",
            "prefLabel": "Diabetes",
            "synonym": ["DM"],
            "definition": ["A disease"],
            "parents": [{"@id": "http://example.com/parent"}],
            "children": [{"@id": "http://example.com/child"}],
        }
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert concept is not None
        assert concept.primary_label == "Diabetes"
        assert "http://example.com/parent" in concept.parents
        assert "http://example.com/child" in concept.children

    def test_convert_concept_no_id(self, adapter_with_api_key):
        """Test returns None when no @id."""
        data = {"prefLabel": "Test"}
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert concept is None

    def test_convert_concept_no_label(self, adapter_with_api_key):
        """Test returns None when no prefLabel."""
        data = {"@id": "http://example.com/1"}
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert concept is None

    def test_convert_concept_synonyms_as_string(self, adapter_with_api_key):
        """Test handles synonym as string."""
        data = {"@id": "http://example.com/1", "prefLabel": "Test", "synonym": "single_syn"}
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert "single_syn" in concept.synonyms

    def test_convert_concept_definitions_as_string(self, adapter_with_api_key):
        """Test handles definition as string."""
        data = {"@id": "http://example.com/1", "prefLabel": "Test", "definition": "single def"}
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert "single def" in concept.definitions

    def test_convert_concept_parents_no_atid(self, adapter_with_api_key):
        """Test parents without @id are filtered out."""
        data = {"@id": "http://example.com/1", "prefLabel": "Test", "parents": [{"name": "no_id"}]}
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert concept.parents == []

    def test_convert_concept_children_no_atid(self, adapter_with_api_key):
        """Test children without @id are filtered out."""
        data = {
            "@id": "http://example.com/1",
            "prefLabel": "Test",
            "children": [{"name": "no_id"}],
        }
        concept = adapter_with_api_key._convert_bioportal_concept_to_unified(data)
        assert concept.children == []

    def test_convert_concept_exception(self, adapter_with_api_key):
        """Test handles exceptions."""
        with patch(
            "knowledge_lookup.adapters.bioportal_adapter.UnifiedConcept",
            side_effect=Exception("Error"),
        ):
            result = adapter_with_api_key._convert_bioportal_concept_to_unified(
                {"@id": "test", "prefLabel": "test"}
            )
            assert result is None


class TestBioPortalDetermineConceptType:
    """Tests for _determine_concept_type_from_ontology method."""

    @pytest.fixture
    def adapter_with_api_key(self):
        config = LookupConfig(api_keys={"bioportal": "test_api_key"})
        return BioPortalAdapter(config)

    def test_disease_type_doid(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("DOID")
            == ConceptType.DISEASE
        )

    def test_disease_type_mondo(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("MONDO")
            == ConceptType.DISEASE
        )

    def test_disease_type_ordo(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("ORDO")
            == ConceptType.DISEASE
        )

    def test_chemical_type_chebi(self, adapter_with_api_key):
        # ChEBI ("Chemical Entities of Biological Interest") is the chemical
        # ontology, not the drug-specific one (DrugBank) — it used to be
        # listed alongside drugbank in the drug branch, which shadowed the
        # separate chebi -> CHEMICAL branch and made it unreachable.
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("CHEBI")
            == ConceptType.CHEMICAL
        )

    def test_drug_type_drugbank(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("DrugBank")
            == ConceptType.DRUG
        )

    def test_gene_type_go(self, adapter_with_api_key):
        assert adapter_with_api_key._determine_concept_type_from_ontology("GO") == ConceptType.GENE

    def test_gene_type_so(self, adapter_with_api_key):
        assert adapter_with_api_key._determine_concept_type_from_ontology("SO") == ConceptType.GENE

    def test_anatomy_type_uberon(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("UBERON")
            == ConceptType.ANATOMICAL_ENTITY
        )

    def test_anatomy_type_fma(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("FMA")
            == ConceptType.ANATOMICAL_ENTITY
        )

    def test_phenotype_type_hp(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("HP")
            == ConceptType.PHENOTYPE
        )

    def test_phenotype_type_mp(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("MP")
            == ConceptType.PHENOTYPE
        )

    def test_unknown_type(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("UNKNOWN")
            == ConceptType.UNKNOWN
        )

    def test_case_insensitive(self, adapter_with_api_key):
        assert (
            adapter_with_api_key._determine_concept_type_from_ontology("doid")
            == ConceptType.DISEASE
        )
