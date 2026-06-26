"""
Unit tests for WikidataAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.wikidata_adapter import WikidataAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig


class TestWikidataAdapter:
    """Tests for WikidataAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create WikidataAdapter instance."""
        return WikidataAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test WikidataAdapter initialization."""
        adapter = WikidataAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.WIKIDATA
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.WIKIDATA

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
        config = LookupConfig(rate_limits={KnowledgeSource.WIKIDATA: 5.0})
        adapter = WikidataAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_with_results(self, adapter):
        """Test search_concepts with actual results (lines 59-62)."""
        sparql_data = {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q12136"},
                        "itemLabel": {"value": "Diabetes mellitus"},
                        "itemDescription": {"value": "metabolic disease"},
                        "instanceOfLabel": {"value": "disease"},
                    }
                ]
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            results = await adapter.search_concepts("diabetes", limit=10)
            assert len(results) == 1
            assert results[0].primary_id == "Q12136"

    @pytest.mark.asyncio
    async def test_search_concepts_empty_bindings(self, adapter):
        """Test search when bindings is empty."""
        sparql_data = {"results": {"bindings": []}}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            results = await adapter.search_concepts("nonexistent")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_conversion_returns_none(self, adapter):
        """Test search when conversion returns None."""
        sparql_data = {"results": {"bindings": [{}]}}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            with patch.object(adapter, "_convert_wikidata_result_to_concept", return_value=None):
                results = await adapter.search_concepts("test")
                assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("SPARQL error")
            results = await adapter.search_concepts("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter):
        """Test successful get_concept_details (lines 79-110)."""
        sparql_data = {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q12136"},
                        "itemLabel": {"value": "Diabetes mellitus"},
                        "itemDescription": {"value": "metabolic disease"},
                        "instanceOfLabel": {"value": "disease"},
                        "umlsCui": {"value": "C0011849"},
                        "meshId": {"value": "D003924"},
                        "icd10": {"value": "E10"},
                        "ncbiTaxonId": {"value": "9606"},
                    }
                ]
            }
        }
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            result = await adapter.get_concept_details("Q12136")
            assert result is not None
            assert result.primary_id == "Q12136"

    @pytest.mark.asyncio
    async def test_get_concept_details_non_q_id(self, adapter):
        """Test get_concept_details with non-Q ID (returns None, lines 75-77)."""
        result = await adapter.get_concept_details("P12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_bindings(self, adapter):
        """Test get_concept_details with empty bindings."""
        sparql_data = {"results": {"bindings": []}}
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = sparql_data
            result = await adapter.get_concept_details("Q12136")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter):
        """Test get_concept_details error handling."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("SPARQL error")
            result = await adapter.get_concept_details("Q12136")
            assert result is None

    def test_convert_wikidata_result_full(self, adapter):
        """Test _convert_wikidata_result_to_concept with all fields (lines 114-141)."""
        result = {
            "item": {"value": "http://www.wikidata.org/entity/Q12136"},
            "itemLabel": {"value": "Diabetes mellitus"},
            "itemDescription": {"value": "metabolic disease"},
            "instanceOfLabel": {"value": "disease"},
        }
        concept = adapter._convert_wikidata_result_to_concept(result)
        assert concept is not None
        assert concept.primary_id == "Q12136"
        assert concept.primary_label == "Diabetes mellitus"
        assert "metabolic disease" in concept.definitions
        assert "disease" in concept.categories

    def test_convert_wikidata_result_no_description(self, adapter):
        """Test _convert_wikidata_result_to_concept without description."""
        result = {
            "item": {"value": "http://www.wikidata.org/entity/Q12136"},
            "itemLabel": {"value": "Diabetes mellitus"},
        }
        concept = adapter._convert_wikidata_result_to_concept(result)
        assert concept is not None
        assert len(concept.definitions) == 0

    def test_convert_wikidata_result_no_instance_of(self, adapter):
        """Test _convert_wikidata_result_to_concept without instanceOf."""
        result = {
            "item": {"value": "http://www.wikidata.org/entity/Q12136"},
            "itemLabel": {"value": "Diabetes mellitus"},
            "instanceOfLabel": {"value": ""},
        }
        concept = adapter._convert_wikidata_result_to_concept(result)
        assert concept is not None
        assert len(concept.categories) == 0

    def test_convert_wikidata_result_error(self, adapter):
        """Test _convert_wikidata_result error handling."""
        concept = adapter._convert_wikidata_result_to_concept(None)
        assert concept is None

    def test_convert_wikidata_details_full(self, adapter):
        """Test _convert_wikidata_details_to_concept with all fields (lines 147-195)."""
        bindings = [
            {
                "itemLabel": {"value": "Diabetes mellitus"},
                "itemDescription": {"value": "metabolic disease"},
                "instanceOfLabel": {"value": "disease"},
                "umlsCui": {"value": "C0011849"},
                "meshId": {"value": "D003924"},
                "icd10": {"value": "E10"},
                "ncbiTaxonId": {"value": "9606"},
            }
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q12136", bindings)
        assert concept is not None
        assert concept.primary_id == "Q12136"
        assert concept.primary_label == "Diabetes mellitus"
        assert "metabolic disease" in concept.definitions
        assert "ICD-10: E10" in concept.categories
        assert "NCBI Taxon: 9606" in concept.categories

    def test_convert_wikidata_details_empty_bindings(self, adapter):
        """Test _convert_wikidata_details_to_concept with empty bindings."""
        concept = adapter._convert_wikidata_details_to_concept("Q12136", [])
        assert concept is None

    def test_convert_wikidata_details_no_optional_fields(self, adapter):
        """Test _convert_wikidata_details without optional fields."""
        bindings = [{"itemLabel": {"value": "Diabetes mellitus"}}]
        concept = adapter._convert_wikidata_details_to_concept("Q12136", bindings)
        assert concept is not None
        assert len(concept.definitions) == 0
        assert len(concept.categories) == 0

    def test_convert_wikidata_details_duplicate_instance_of(self, adapter):
        """Test _convert_wikidata_details when instanceOf already in categories."""
        bindings = [
            {"itemLabel": {"value": "Test"}, "instanceOfLabel": {"value": "disease"}},
            {"itemLabel": {"value": "Test"}, "instanceOfLabel": {"value": "disease"}},
        ]
        concept = adapter._convert_wikidata_details_to_concept("Q12136", bindings)
        assert concept is not None
        assert concept.categories.count("disease") == 1

    def test_convert_wikidata_details_error(self, adapter):
        """Test _convert_wikidata_details error handling."""
        concept = adapter._convert_wikidata_details_to_concept("Q12136", None)
        assert concept is None

    def test_determine_concept_type_disease(self, adapter):
        """Test _determine_concept_type_from_instance_of for disease (lines 199-214)."""
        assert adapter._determine_concept_type_from_instance_of("disease") == ConceptType.DISEASE
        assert adapter._determine_concept_type_from_instance_of("disorder") == ConceptType.DISEASE
        assert adapter._determine_concept_type_from_instance_of("syndrome") == ConceptType.DISEASE

    def test_determine_concept_type_drug(self, adapter):
        """Test _determine_concept_type_from_instance_of for drug."""
        assert adapter._determine_concept_type_from_instance_of("drug") == ConceptType.DRUG
        assert (
            adapter._determine_concept_type_from_instance_of("pharmaceutical") == ConceptType.DRUG
        )
        assert adapter._determine_concept_type_from_instance_of("medication") == ConceptType.DRUG

    def test_determine_concept_type_gene(self, adapter):
        """Test _determine_concept_type_from_instance_of for gene."""
        assert adapter._determine_concept_type_from_instance_of("gene") == ConceptType.GENE
        assert (
            adapter._determine_concept_type_from_instance_of("genetic element") == ConceptType.GENE
        )

    def test_determine_concept_type_protein(self, adapter):
        """Test _determine_concept_type_from_instance_of for protein."""
        assert adapter._determine_concept_type_from_instance_of("protein") == ConceptType.PROTEIN

    def test_determine_concept_type_chemical(self, adapter):
        """Test _determine_concept_type_from_instance_of for chemical."""
        assert (
            adapter._determine_concept_type_from_instance_of("chemical compound")
            == ConceptType.CHEMICAL
        )

    def test_determine_concept_type_organism(self, adapter):
        """Test _determine_concept_type_from_instance_of for organism."""
        assert adapter._determine_concept_type_from_instance_of("taxon") == ConceptType.ORGANISM
        assert adapter._determine_concept_type_from_instance_of("species") == ConceptType.ORGANISM
        assert adapter._determine_concept_type_from_instance_of("organism") == ConceptType.ORGANISM

    def test_determine_concept_type_unknown(self, adapter):
        """Test _determine_concept_type_from_instance_of for unknown type."""
        assert (
            adapter._determine_concept_type_from_instance_of("something else")
            == ConceptType.UNKNOWN
        )

    def test_determine_concept_type_empty_string(self, adapter):
        """Test _determine_concept_type_from_instance_of with empty string."""
        assert adapter._determine_concept_type_from_instance_of("") == ConceptType.UNKNOWN

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
