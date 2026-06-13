"""
Unit tests for UMLSAdapter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.adapters.umls_adapter import UMLSAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept

# ── Helper factories ────────────────────────────────────────────────────


def make_search_result(
    cui: str = "C001",
    name: str = "Diabetes",
    root_source: str = "SNOMEDCT",
    uri: str | None = None,
):
    """Build a mock ``SearchResult``-like object with the same shape."""
    result = MagicMock()
    result.ui = cui
    result.name = name
    result.root_source = root_source
    result.uri = uri or f"https://uts.nlm.nih.gov/uts/rest/content/current/source/{root_source}/{cui}"
    result.raw = {}
    return result


def make_concept(ui: str = "C001", name: str = "Diabetes", semantic_types: list[dict] | None = None):
    concept = MagicMock()
    concept.ui = ui
    concept.name = name
    concept.semantic_types = semantic_types or []
    concept.atom_count = 0
    concept.raw = {}
    return concept


def make_profile(
    concept=None,
    definitions: list[str] | None = None,
    relations: list | None = None,
    atoms: list | None = None,
    preferred_atom=None,
):
    profile = MagicMock()
    profile.concept = concept
    profile.definitions = definitions or []
    profile.relations = relations or []
    profile.atoms = atoms or []
    profile.preferred_atom = preferred_atom
    profile.raw = {}
    return profile


def make_definition(value: str, root_source: str = "SNOMEDCT"):
    d = MagicMock()
    d.value = value
    d.root_source = root_source
    return d


def make_relation(related_id: str, relation_label: str, **kw):
    r = MagicMock()
    r.related_id = related_id
    r.relation_label = relation_label
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def make_atom(name: str, root_source: str = "SNOMEDCT", ui: str = "A001"):
    a = MagicMock()
    a.name = name
    a.root_source = root_source
    a.ui = ui
    return a


# ── Tests ───────────────────────────────────────────────────────────────


class TestUMLSAdapter:
    """Tests for UMLSAdapter backed by umls-python-client."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create UMLSAdapter instance."""
        return UMLSAdapter(lookup_config)

    @pytest.fixture
    def mock_client(self):
        """Create a mock AsyncUMLSClient with async search_api / cui_api."""
        client = MagicMock()
        client.search_api = MagicMock()
        client.cui_api = MagicMock()
        return client

    # ── Basics ──────────────────────────────────────────────────────

    def test_adapter_initialization(self, lookup_config):
        """Test UMLSAdapter initialization."""
        adapter = UMLSAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.UMLS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        assert adapter.get_source() == KnowledgeSource.UMLS

    def test_is_available(self, adapter):
        assert isinstance(adapter.is_available(), bool)

    def test_get_rate_limit_default(self, adapter):
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        config = LookupConfig(rate_limits={KnowledgeSource.UMLS: 5.0})
        adapter = UMLSAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    # ── search_concepts ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, adapter, mock_client):
        """Search returns two results with proper conversion."""
        mock_response = MagicMock()
        mock_response.result = [
            make_search_result("C001", "Diabetes", "SNOMEDCT"),
            make_search_result("C002", "Diabetes Mellitus", "ICD10CM"),
        ]
        mock_client.search_api.search = AsyncMock(return_value=mock_response)
        adapter.client = mock_client

        results = await adapter.search_concepts("diabetes", limit=10)
        assert len(results) == 2
        assert all(isinstance(r, UnifiedConcept) for r in results)

        # Exact match (case-insensitive)
        assert results[0].primary_label == "Diabetes"
        assert results[0].primary_id == "C001"
        assert results[0].concept_type == ConceptType.DISEASE
        assert results[0].confidence_score == 0.95

        # Partial match
        assert results[1].primary_label == "Diabetes Mellitus"
        assert results[1].concept_type == ConceptType.DISEASE
        assert results[1].confidence_score == 0.85

        mock_client.search_api.search.assert_awaited_once_with(
            search_string="diabetes", page_size=10, return_id_type="concept"
        )

    @pytest.mark.asyncio
    async def test_search_concepts_empty(self, adapter, mock_client):
        mock_response = MagicMock()
        mock_response.result = []
        mock_client.search_api.search = AsyncMock(return_value=mock_response)
        adapter.client = mock_client

        results = await adapter.search_concepts("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_error(self, adapter, mock_client):
        mock_client.search_api.search = AsyncMock(side_effect=Exception("API error"))
        adapter.client = mock_client

        results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_no_client(self, adapter):
        adapter.client = None
        results = await adapter.search_concepts("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_respects_limit(self, adapter, mock_client):
        mock_response = MagicMock()
        mock_response.result = [
            make_search_result(f"C{i:03d}", f"Concept {i}")
            for i in range(10)
        ]
        mock_client.search_api.search = AsyncMock(return_value=mock_response)
        adapter.client = mock_client

        results = await adapter.search_concepts("test", limit=3)
        assert len(results) == 3
        assert [r.primary_id for r in results] == ["C000", "C001", "C002"]

    # ── get_concept_details ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter, mock_client):
        """Full profile with definitions, relations, atoms."""
        cui = "C001"
        concept_info = make_concept(
            ui=cui,
            name="Diabetes",
            semantic_types=[{"uri": "https://uts.nlm.nih.gov/uts/rest/semantic-network/semantic-type/T047", "name": "Disease or Syndrome"}],
        )
        profile = make_profile(
            concept=concept_info,
            definitions=[make_definition("A metabolic disorder", "SNOMEDCT")],
            relations=[
                make_relation("C002", "PAR"),
                make_relation("C003", "CHD"),
                make_relation("C004", "RB"),
            ],
            atoms=[
                make_atom("Diabetes mellitus", "SNOMEDCT", "A001"),
                make_atom("Diabetes", "ICD10CM", "A002"),
            ],
            preferred_atom=make_atom("Diabetes mellitus", "SNOMEDCT", "A001"),
        )

        mock_client.cui_api.get_cui_info = AsyncMock(
            return_value=MagicMock(result=concept_info)
        )
        mock_client.cui_api.get_concept_profile = AsyncMock(
            return_value=MagicMock(result=profile)
        )
        adapter.client = mock_client

        concept = await adapter.get_concept_details(cui)
        assert concept is not None
        assert concept.primary_id == cui
        assert concept.primary_label == "Diabetes"
        assert concept.concept_type == ConceptType.DISEASE  # from root_source SNOMEDCT
        assert concept.confidence_score == 0.95
        assert concept.definitions == ["A metabolic disorder"]
        assert "Diabetes mellitus" in concept.synonyms
        assert "SNOMEDCT" in concept.categories
        assert "ICD10CM" in concept.categories
        assert "C002" in concept.parents
        assert "C003" in concept.children
        assert "C004" in concept.related

    @pytest.mark.asyncio
    async def test_get_concept_details_no_client(self, adapter):
        adapter.client = None
        result = await adapter.get_concept_details("C001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_error(self, adapter, mock_client):
        mock_client.cui_api.get_cui_info = AsyncMock(
            side_effect=Exception("API error")
        )
        adapter.client = mock_client
        result = await adapter.get_concept_details("C001")
        assert result is None

    # ── Default methods ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        assert await adapter.get_mappings("C001") == []

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        assert await adapter.get_relationships("C001") == []

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        async with adapter:
            pass

    # ── Type mapping ────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "source, expected",
        [
            ("SNOMEDCT", ConceptType.DISEASE),
            ("ICD10CM", ConceptType.DISEASE),
            ("ICD10", ConceptType.DISEASE),
            ("ICD9CM", ConceptType.DISEASE),
            ("ICD10PCS", ConceptType.PROCEDURE),
            ("OMIM", ConceptType.DISEASE),
            ("ORDO", ConceptType.DISEASE),
            ("NCI", ConceptType.DISEASE),
            ("MEDDRA", ConceptType.DISEASE),
            ("RXNORM", ConceptType.DRUG),
            ("NDDF", ConceptType.DRUG),
            ("DRUGBANK", ConceptType.DRUG),
            ("CHEMBL", ConceptType.CHEMICAL),
            ("PUBCHEM", ConceptType.CHEMICAL),
            ("MSH", ConceptType.CHEMICAL),
            ("HGNC", ConceptType.GENE),
            ("UNIPROT", ConceptType.GENE),
            ("ENSEMBL", ConceptType.GENE),
            ("REFSEQ", ConceptType.GENE),
            ("GENBANK", ConceptType.GENE),
            ("HPO", ConceptType.PHENOTYPE),
            ("FMA", ConceptType.ANATOMICAL_ENTITY),
            ("UBERON", ConceptType.ANATOMICAL_ENTITY),
            ("GO", ConceptType.BIOLOGICAL_PROCESS),
            ("KEGG", ConceptType.PATHWAY),
            ("REACTOME", ConceptType.PATHWAY),
            ("CPT", ConceptType.PROCEDURE),
            ("LOINC", ConceptType.PROCEDURE),
            ("UNKNOWN_SRC", ConceptType.UNKNOWN),
        ],
    )
    def test_determine_concept_type_from_source(self, source, expected):
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)
        assert adapter._determine_concept_type_from_source(source) == expected

    @pytest.mark.parametrize(
        "name, query, expected",
        [
            ("Diabetes", "diabetes", 0.95),
            ("Diabetes mellitus", "diabetes mellitus", 0.95),
            ("DIABETES", "diabetes", 0.95),
            ("Diabetes mellitus", "diabetes", 0.85),
            ("Hypertension", "diabetes", 0.75),
        ],
    )
    def test_confidence_scoring(self, name, query, expected):
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)

        result = make_search_result(cui="C001", name=name, root_source="SNOMEDCT")
        concept = adapter._convert_search_result(result, query)
        assert concept.confidence_score == expected, (
            f"name={name!r} query={query!r}: expected {expected}, got {concept.confidence_score}"
        )

    def test_semantic_type_mapping(self):
        """Semantic types with TUIs map to correct concept types."""
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)

        result = adapter._determine_concept_type_from_semantic_types(
            [{"uri": "https://uts.nlm.nih.gov/uts/rest/semantic-network/semantic-type/T047", "name": "Disease or Syndrome"}]
        )
        assert result == ConceptType.DISEASE

        result = adapter._determine_concept_type_from_semantic_types(
            [{"uri": "https://uts.nlm.nih.gov/uts/rest/semantic-network/semantic-type/T121", "name": "Pharmacologic Substance"}]
        )
        assert result == ConceptType.DRUG

        result = adapter._determine_concept_type_from_semantic_types(
            [{"uri": "https://uts.nlm.nih.gov/uts/rest/semantic-network/semantic-type/T028", "name": "Gene or Genome"}]
        )
        assert result == ConceptType.GENE

        # Unknown TUI
        result = adapter._determine_concept_type_from_semantic_types(
            [{"uri": "https://uts.nlm.nih.gov/uts/rest/semantic-network/semantic-type/T999", "name": "Unknown"}]
        )
        assert result == ConceptType.UNKNOWN
