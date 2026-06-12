"""
Unit tests for UMLSAdapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.adapters.umls_adapter import UMLSAdapter
from knowledge_lookup.models import (
    ConceptType,
    KnowledgeSource,
    LookupConfig,
    UnifiedConcept,
)
from knowledge_lookup.umls.models import UMLSSearchResult


class TestUMLSAdapter:
    """Tests for UMLSAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create UMLSAdapter instance."""
        return UMLSAdapter(lookup_config)

    @pytest.fixture
    def adapter_with_api_key(self):
        """Create UMLSAdapter with API key."""
        config = LookupConfig(api_keys={"umls": "test_api_key"})
        return UMLSAdapter(config)

    def test_adapter_initialization(self, lookup_config):
        """Test UMLSAdapter initialization."""
        adapter = UMLSAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.UMLS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.UMLS

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
        config = LookupConfig(rate_limits={KnowledgeSource.UMLS: 5.0})
        adapter = UMLSAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, adapter):
        """Test successful search concepts."""
        mock_client = MagicMock()
        mock_results = [
            UMLSSearchResult("C001", "Diabetes", "UI001", "SNOMEDCT", "D123", "SNOMEDCT"),
            UMLSSearchResult("C002", "Diabetes Mellitus", "UI002", "ICD10CM", "E11", "ICD10CM"),
        ]
        mock_client.search_concepts.return_value = mock_results
        adapter.client = mock_client

        results = await adapter.search_concepts("diabetes", limit=10)
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, UnifiedConcept) for r in results)

        # Check first result: exact match "Diabetes" vs query "diabetes" (case-insensitive)
        assert results[0].primary_label == "Diabetes"
        assert results[0].primary_id == "C001"
        assert results[0].concept_type == ConceptType.DISEASE
        assert results[0].confidence_score == 0.95  # exact match

        # Check second result: partial match
        assert results[1].primary_label == "Diabetes Mellitus"
        assert results[1].primary_id == "C002"
        assert results[1].concept_type == ConceptType.DISEASE
        assert results[1].confidence_score == 0.85  # partial match (query is substring)

    @pytest.mark.asyncio
    async def test_search_concepts_empty_response(self, adapter):
        """Test search concepts with empty response."""
        mock_client = MagicMock()
        mock_client.search_concepts.return_value = []
        adapter.client = mock_client

        results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_http_error(self, adapter):
        """Test search concepts with HTTP error."""
        mock_client = MagicMock()
        mock_client.search_concepts.side_effect = Exception("HTTP Error")
        adapter.client = mock_client

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        mock_client = MagicMock()
        mock_client.search_concepts.side_effect = Exception("Network error")
        adapter.client = mock_client

        results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_respects_limit(self, adapter):
        """Test search concepts respects the limit parameter."""
        mock_client = MagicMock()
        mock_results = [
            UMLSSearchResult(f"C{i:03d}", f"Concept {i}", f"UI{i}", "SNOMEDCT", f"ID{i}", "SNOMEDCT")
            for i in range(10)
        ]
        mock_client.search_concepts.return_value = mock_results
        adapter.client = mock_client

        results = await adapter.search_concepts("test", limit=3)
        assert len(results) == 3
        assert [r.primary_id for r in results] == ["C000", "C001", "C002"]

    @pytest.mark.asyncio
    async def test_search_concepts_no_client(self, adapter):
        """Test search concepts when client is not available."""
        adapter.client = None
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
            pass  # Should not raise any exceptions

    # --- Conversion and type mapping tests ---

    @pytest.mark.parametrize(
        "source, expected_type",
        [
            # Diseases
            ("SNOMEDCT", ConceptType.DISEASE),
            ("ICD10CM", ConceptType.DISEASE),
            ("ICD10", ConceptType.DISEASE),
            ("ICD9CM", ConceptType.DISEASE),
            ("OMIM", ConceptType.DISEASE),
            ("ORDO", ConceptType.DISEASE),
            ("NCI", ConceptType.DISEASE),
            ("MEDDRA", ConceptType.DISEASE),
            # Drugs & Chemicals
            ("RXNORM", ConceptType.DRUG),
            ("NDDF", ConceptType.DRUG),
            ("DRUGBANK", ConceptType.DRUG),
            ("CHEMBL", ConceptType.CHEMICAL),
            ("PUBCHEM", ConceptType.CHEMICAL),
            ("MSH", ConceptType.CHEMICAL),
            # Genes
            ("HGNC", ConceptType.GENE),
            ("UNIPROT", ConceptType.GENE),
            ("ENSEMBL", ConceptType.GENE),
            ("REFSEQ", ConceptType.GENE),
            ("GENBANK", ConceptType.GENE),
            # Phenotypes
            ("HPO", ConceptType.PHENOTYPE),
            # Anatomy
            ("FMA", ConceptType.ANATOMICAL_ENTITY),
            ("UBERON", ConceptType.ANATOMICAL_ENTITY),
            # Biological processes
            ("GO", ConceptType.BIOLOGICAL_PROCESS),
            ("KEGG", ConceptType.PATHWAY),
            ("REACTOME", ConceptType.PATHWAY),
            # Procedures
            ("CPT", ConceptType.PROCEDURE),
            ("ICD10PCS", ConceptType.PROCEDURE),
            ("LOINC", ConceptType.PROCEDURE),
            # Unknown
            ("UNKNOWN_SOURCE", ConceptType.UNKNOWN),
        ],
    )
    def test_determine_concept_type_from_source(self, source, expected_type):
        """Test source-to-concept-type mapping."""
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)
        result = adapter._determine_concept_type_from_source(source)
        assert result == expected_type, f"Expected {expected_type} for source '{source}', got {result}"

    @pytest.mark.parametrize(
        "result_name, query, expected_score",
        [
            # Exact match (case-insensitive)
            ("Diabetes", "diabetes", 0.95),
            ("Diabetes mellitus", "diabetes mellitus", 0.95),
            ("DIABETES", "diabetes", 0.95),
            # Partial match (query is substring of result name or vice versa)
            ("Diabetes mellitus", "diabetes", 0.85),
            ("diabetes", "Diabetes mellitus", 0.85),
            # No match
            ("Hypertension", "diabetes", 0.75),
            ("Cancer", "diabetes", 0.75),
        ],
    )
    def test_confidence_scoring(self, result_name, query, expected_score):
        """Test confidence score based on name vs query matching."""
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)

        result = UMLSSearchResult(
            cui="C001",
            name=result_name,
            ui="UI001",
            source="SNOMEDCT",
            source_concept_id="D123",
            root_source="SNOMEDCT",
        )

        concept = adapter._convert_search_result_to_concept(result, query)
        assert concept.confidence_score == expected_score, (
            f"Expected {expected_score} for name='{result_name}' query='{query}', "
            f"got {concept.confidence_score}"
        )

    def test_convert_search_result_with_mesh(self):
        """Test conversion of a MeSH result (mapped to CHEMICAL)."""
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)

        result = UMLSSearchResult(
            cui="C002",
            name="Aspirin",
            ui="D001241",
            source="MSH",
            source_concept_id="D001241",
            root_source="MSH",
        )

        concept = adapter._convert_search_result_to_concept(result, "aspirin")
        assert concept.concept_type == ConceptType.CHEMICAL
        assert concept.source_data[KnowledgeSource.UMLS]["ui"] == "D001241"
        assert concept.source_data[KnowledgeSource.UMLS]["source"] == "MSH"

    def test_convert_search_result_with_hgnc(self):
        """Test conversion of an HGNC result (mapped to GENE)."""
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)

        result = UMLSSearchResult(
            cui="C003",
            name="TP53",
            ui="HGNC:11998",
            source="HGNC",
            source_concept_id="11998",
            root_source="HGNC",
        )

        concept = adapter._convert_search_result_to_concept(result, "tp53")
        assert concept.concept_type == ConceptType.GENE
