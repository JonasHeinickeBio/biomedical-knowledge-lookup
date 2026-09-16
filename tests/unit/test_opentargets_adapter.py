"""
Unit tests for OpenTargetsAdapter.
"""

from unittest.mock import patch

import pytest

from knowledge_lookup.adapters.opentargets_adapter import OpenTargetsAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

MAKE_REQUEST = "knowledge_lookup.adapters.opentargets_adapter.OpenTargetsAdapter._make_request"


def _search_response(*hits):
    return {"data": {"search": {"hits": list(hits)}}}


ASTHMA_HIT = {
    "id": "MONDO_0004979",
    "name": "asthma",
    "entity": "disease",
    "description": "A bronchial disease that is characterized by chronic inflammation.",
    "category": ["respiratory or thoracic disease", "phenotype"],
}
TP53_HIT = {
    "id": "ENSG00000141510",
    "name": "TP53",
    "entity": "target",
    "description": "tumor protein p53",
    "category": ["protein_coding"],
}


class TestOpenTargetsAdapter:
    """Tests for OpenTargetsAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create OpenTargetsAdapter instance."""
        return OpenTargetsAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test OpenTargetsAdapter initialization."""
        adapter = OpenTargetsAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.OPENTARGETS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.OPENTARGETS

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
        config = LookupConfig(rate_limits={KnowledgeSource.OPENTARGETS: 5.0})
        adapter = OpenTargetsAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_success(self, mock_make_request, adapter):
        """Test successful search concepts."""
        mock_make_request.return_value = _search_response(ASTHMA_HIT)

        results = await adapter.search_concepts("asthma", limit=10)
        assert isinstance(results, list)
        assert len(results) == 1

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_empty_response(self, mock_make_request, adapter):
        """Test search concepts with empty response."""
        mock_make_request.return_value = _search_response()

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_sends_page_size(self, mock_make_request, adapter):
        """The GraphQL search asks for ``limit`` hits."""
        mock_make_request.return_value = _search_response()

        await adapter.search_concepts("asthma", limit=7)
        payload = mock_make_request.call_args.kwargs["json_data"]
        assert payload["variables"] == {"queryString": "asthma", "size": 7}
        assert "page: {index: 0, size: $size}" in payload["query"]

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_http_error(self, mock_make_request, adapter):
        """Test search concepts with HTTP error."""
        mock_make_request.side_effect = Exception("HTTP error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_network_error(self, mock_make_request, adapter):
        """Test search concepts with network error."""
        mock_make_request.side_effect = Exception("Network error")

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_graphql_errors(self, mock_make_request, adapter):
        """GraphQL errors (HTTP 200 without data) give [] and are logged."""
        mock_make_request.return_value = {"errors": [{"message": "Cannot query field 'x'"}]}

        with patch("knowledge_lookup.adapters.opentargets_adapter.logger") as mock_logger:
            results = await adapter.search_concepts("asthma")
        assert results == []
        assert "Cannot query field 'x'" in mock_logger.warning.call_args.args[0]

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
            pass  # Should not raise any exceptions

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_disease(self, mock_make_request, adapter):
        """Test get_concept_details for disease entity type (EFO_ prefix)."""
        mock_make_request.return_value = {
            "data": {
                "disease": {
                    "id": "EFO_0000616",
                    "name": "type 2 diabetes mellitus",
                    "description": "A chronic metabolic disease.",
                }
            }
        }
        result = await adapter.get_concept_details("EFO_0000616")
        assert result is not None
        assert result.primary_id == "EFO_0000616"
        assert result.primary_label == "type 2 diabetes mellitus"
        assert result.concept_type == ConceptType.DISEASE
        assert result.definitions == ["A chronic metabolic disease."]

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_disease_query_matches_schema(
        self, mock_make_request, adapter
    ):
        """Regression: disease details use ``disease(efoId:)`` and ``description``."""
        mock_make_request.return_value = {"data": {"disease": None}}

        await adapter.get_concept_details("MONDO_0004979")
        payload = mock_make_request.call_args.kwargs["json_data"]
        assert "disease(efoId: $efoId)" in payload["query"]
        assert "description" in payload["query"]
        assert "definition" not in payload["query"]
        assert "disease(id:" not in payload["query"]
        assert payload["variables"] == {"efoId": "MONDO_0004979"}

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_disease_full_record(self, mock_make_request, adapter):
        """Synonyms and therapeutic areas from the current Disease type are mapped."""
        mock_make_request.return_value = {
            "data": {
                "disease": {
                    "id": "MONDO_0004979",
                    "name": "asthma",
                    "description": "A bronchial disease.",
                    "synonyms": [
                        {"relation": "hasExactSynonym", "terms": ["bronchial hyperreactivity"]},
                        {"relation": "hasRelatedSynonym", "terms": []},
                    ],
                    "dbXRefs": ["DOID:2841", "UMLS:C0004096"],
                    "therapeuticAreas": [
                        {"id": "EFO_0000651", "name": "phenotype"},
                        {"id": "OTAR_0000010", "name": "respiratory or thoracic disease"},
                    ],
                }
            }
        }
        result = await adapter.get_concept_details("MONDO_0004979")
        assert result.synonyms == ["bronchial hyperreactivity"]
        assert result.categories == ["phenotype", "respiratory or thoracic disease"]
        assert (
            result.identifiers[0].url == "https://platform.opentargets.org/disease/MONDO_0004979"
        )

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_target(self, mock_make_request, adapter):
        """Test get_concept_details for target entity type (ENSG prefix)."""
        mock_make_request.return_value = {
            "data": {
                "target": {
                    "id": "ENSG00000141510",
                    "approvedSymbol": "TP53",
                    "approvedName": "tumor protein p53",
                    "biotype": "protein_coding",
                    "functionDescriptions": ["Multifunctional transcription factor."],
                    "synonyms": [{"label": "p53", "source": "uniprot"}],
                }
            }
        }
        result = await adapter.get_concept_details("ENSG00000141510")
        assert result is not None
        assert result.primary_id == "ENSG00000141510"
        assert result.primary_label == "TP53"
        assert result.concept_type == ConceptType.GENE
        assert result.definitions == [
            "Multifunctional transcription factor.",
            "Biotype: protein_coding",
        ]
        assert result.synonyms == ["TP53", "tumor protein p53", "p53"]
        payload = mock_make_request.call_args.kwargs["json_data"]
        assert "target(ensemblId: $ensemblId)" in payload["query"]

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_mondo_prefix(self, mock_make_request, adapter):
        """Test get_concept_details for MONDO_ prefix (disease)."""
        mock_make_request.return_value = {
            "data": {
                "disease": {
                    "id": "MONDO_0005180",
                    "name": "Alzheimer disease",
                    "description": "A neurodegenerative disease.",
                }
            }
        }
        result = await adapter.get_concept_details("MONDO_0005180")
        assert result is not None
        assert result.primary_label == "Alzheimer disease"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("concept_id", "expected"),
        [
            ("MONDO:0009061", "MONDO_0009061"),
            ("ORPHA:99835", "Orphanet_99835"),
            ("Orphanet_99835", "Orphanet_99835"),
            ("HP_0002099", "HP_0002099"),
        ],
    )
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_disease_id_forms(
        self, mock_make_request, adapter, concept_id, expected
    ):
        """Non-Ensembl IDs are diseases; CURIE-style IDs are normalized."""
        mock_make_request.return_value = {
            "data": {"disease": {"id": expected, "name": "Rare disease"}}
        }
        result = await adapter.get_concept_details(concept_id)
        assert result is not None
        assert result.concept_type == ConceptType.DISEASE
        assert mock_make_request.call_args.kwargs["json_data"]["variables"] == {"efoId": expected}

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_no_data(self, mock_make_request, adapter):
        """Test get_concept_details when data is empty."""
        mock_make_request.return_value = {"data": {}}
        result = await adapter.get_concept_details("EFO_9999999")
        assert result is None

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_unknown_disease(self, mock_make_request, adapter):
        """Unknown IDs come back as ``{"disease": null}``."""
        mock_make_request.return_value = {"data": {"disease": None}}
        result = await adapter.get_concept_details("EFO_9999999")
        assert result is None

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_get_concept_details_error(self, mock_make_request, adapter):
        """Test get_concept_details with error."""
        mock_make_request.side_effect = Exception("API error")
        result = await adapter.get_concept_details("EFO_0000616")
        assert result is None

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_with_hits(self, mock_make_request, adapter):
        """Test search with actual hits returned."""
        mock_make_request.return_value = _search_response(TP53_HIT, ASTHMA_HIT)
        results = await adapter.search_concepts("cancer", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_uses_hit_entity_type(self, mock_make_request, adapter):
        """Regression: hits keep their name as label and their entity as concept type."""
        mock_make_request.return_value = _search_response(ASTHMA_HIT, TP53_HIT)
        disease, target = await adapter.search_concepts("asthma", limit=10)

        assert disease.primary_id == "MONDO_0004979"
        assert disease.primary_label == "asthma"
        assert disease.concept_type == ConceptType.DISEASE
        assert disease.identifiers[0].url == (
            "https://platform.opentargets.org/disease/MONDO_0004979"
        )
        assert disease.definitions[0].startswith("A bronchial disease")
        assert "respiratory or thoracic disease" in disease.categories

        assert target.primary_id == "ENSG00000141510"
        assert target.primary_label == "TP53"
        assert target.concept_type == ConceptType.GENE
        assert target.identifiers[0].url == (
            "https://platform.opentargets.org/target/ENSG00000141510"
        )
        assert target.definitions == ["tumor protein p53"]

    @pytest.mark.asyncio
    @patch(MAKE_REQUEST)
    async def test_search_concepts_limit(self, mock_make_request, adapter):
        """Search never returns more than ``limit`` concepts."""
        mock_make_request.return_value = _search_response(ASTHMA_HIT, TP53_HIT)
        results = await adapter.search_concepts("asthma", limit=1)
        assert len(results) == 1

    def test_convert_result_disease_with_definition(self, adapter):
        """Legacy payloads with ``definition`` still fill definitions."""
        concept = adapter._convert_opentargets_result_to_concept(
            {
                "id": "EFO_0000616",
                "name": "diabetes",
                "definition": "A metabolic disease",
            },
            entity_type="disease",
        )
        assert concept is not None
        assert concept.primary_label == "diabetes"
        assert "A metabolic disease" in concept.definitions

    def test_convert_result_target_with_biotype(self, adapter):
        """Test _convert result for target with biotype."""
        concept = adapter._convert_opentargets_result_to_concept(
            {
                "id": "ENSG00000169318",
                "approvedSymbol": "TP53",
                "biotype": "protein_coding",
            },
            entity_type="target",
        )
        assert concept is not None
        assert concept.primary_label == "TP53"
        assert any("protein_coding" in d for d in concept.definitions)

    def test_convert_result_without_entity_type(self, adapter):
        """Test _convert result without entity_type (defaults to target)."""
        concept = adapter._convert_opentargets_result_to_concept(
            {"id": "ENSG00000169318", "approvedSymbol": "TP53"}
        )
        assert concept is not None
        assert concept.concept_type == "GENE"

    def test_convert_result_other_entity_type(self, adapter):
        """Entities other than target/disease (e.g. drug) are not labelled as genes."""
        concept = adapter._convert_opentargets_result_to_concept(
            {"id": "CHEMBL25", "name": "ASPIRIN", "entity": "drug"}, entity_type="drug"
        )
        assert concept.primary_label == "ASPIRIN"
        assert concept.concept_type == ConceptType.UNKNOWN
