"""
Unit tests for UMLSAdapter.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
    semantic_type_names: list[str] | None = None,
):
    result = MagicMock()
    result.ui = cui
    result.name = name
    result.root_source = root_source
    result.uri = uri or f"https://uts.nlm.nih.gov/uts/rest/content/current/source/{root_source}/{cui}"
    result.raw = {"semanticTypes": semantic_type_names or []}
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
    definitions: list | None = None,
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
    r.additional_relation_label = None
    r.related_id_name = f"Name of {related_id}"
    r.root_source = "SNOMEDCT"
    r.ui = f"R{related_id}"
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def make_atom(name: str, root_source: str = "SNOMEDCT", ui: str = "A001", code: str | None = None):
    a = MagicMock()
    a.name = name
    a.root_source = root_source
    a.ui = ui
    a.code = code or ui
    a.uri = f"https://uts.nlm.nih.gov/uts/rest/content/current/source/{root_source}/{code or ui}"
    return a


# Async iterator helper for mocking ``iter_*`` methods
class AsyncIter:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for item in self.items:
            yield item


def make_mock_response(result):
    """Shortcut for a MagicMock that looks like ``UMLSResponse`` with ``.result``."""
    r = MagicMock()
    r.result = result
    return r


# ── Tests ───────────────────────────────────────────────────────────────


class TestUMLSAdapter:
    """Tests for UMLSAdapter backed by umls-python-client."""

    @pytest.fixture
    def adapter(self, lookup_config):
        return UMLSAdapter(lookup_config)

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.search_api = MagicMock()
        client.cui_api = MagicMock()
        client.crosswalk_api = MagicMock()
        client.release_api = MagicMock()
        return client

    # ── Basics ──────────────────────────────────────────────────────

    def test_adapter_initialization(self, lookup_config):
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

    # ── 1. search_concepts ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, adapter, mock_client):
        mock_client.search_api.search = AsyncMock(
            return_value=make_mock_response([
                make_search_result("C001", "Diabetes", "SNOMEDCT"),
                make_search_result("C002", "Diabetes Mellitus", "ICD10CM"),
            ])
        )
        adapter.client = mock_client

        results = await adapter.search_concepts("diabetes", limit=10)
        assert len(results) == 2
        assert all(isinstance(r, UnifiedConcept) for r in results)

        assert results[0].primary_label == "Diabetes"
        assert results[0].primary_id == "C001"
        assert results[0].concept_type == ConceptType.DISEASE
        assert results[0].confidence_score == 0.95

        assert results[1].primary_label == "Diabetes Mellitus"
        assert results[1].concept_type == ConceptType.DISEASE
        assert results[1].confidence_score == 0.85

        mock_client.search_api.search.assert_awaited_once_with(
            search_string="diabetes", page_size=10, return_id_type="concept",
            sabs=None, semantic_groups=None, semantic_types=None,
            search_type="words", partial_search=False,
        )

    @pytest.mark.asyncio
    async def test_search_concepts_with_filters(self, adapter, mock_client):
        mock_client.search_api.search = AsyncMock(
            return_value=make_mock_response([
                make_search_result("C001", "Diabetes", "SNOMEDCT"),
            ])
        )
        adapter.client = mock_client

        results = await adapter.search_concepts(
            "diabetes", limit=5,
            sabs="SNOMEDCT", semantic_groups="DISO",
            search_type="exact", partial_search=True,
        )
        assert len(results) == 1

        mock_client.search_api.search.assert_awaited_once_with(
            search_string="diabetes", page_size=5, return_id_type="concept",
            sabs="SNOMEDCT", semantic_groups="DISO", semantic_types=None,
            search_type="exact", partial_search=True,
        )

    @pytest.mark.asyncio
    async def test_search_concepts_empty(self, adapter, mock_client):
        mock_client.search_api.search = AsyncMock(
            return_value=make_mock_response([])
        )
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
        mock_client.search_api.search = AsyncMock(
            return_value=make_mock_response([
                make_search_result(f"C{i:03d}", f"Concept {i}")
                for i in range(10)
            ])
        )
        adapter.client = mock_client
        results = await adapter.search_concepts("test", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_concepts_with_mth_fallback(self, adapter, mock_client):
        mock_client.search_api.search = AsyncMock(
            return_value=make_mock_response([
                make_search_result("C001", "Amoxicillin", "MTH",
                                   semantic_type_names=["Pharmacologic Substance"]),
            ])
        )
        adapter.client = mock_client
        results = await adapter.search_concepts("amoxicillin", limit=5)
        assert len(results) == 1
        assert results[0].concept_type == ConceptType.DRUG

    @pytest.mark.asyncio
    async def test_search_concepts_with_mth_and_no_semantic_types(self, adapter, mock_client):
        mock_client.search_api.search = AsyncMock(
            return_value=make_mock_response([
                make_search_result("C001", "Unknown Concept", "MTH"),
            ])
        )
        adapter.client = mock_client
        results = await adapter.search_concepts("unknown", limit=5)
        assert len(results) == 1
        assert results[0].concept_type == ConceptType.UNKNOWN

    # ── 2. bulk_search ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_bulk_search_success(self, adapter, mock_client):
        mock_client.search_api.bulk_search = AsyncMock(
            return_value={
                "diabetes": make_mock_response([
                    make_search_result("C001", "Diabetes", "SNOMEDCT"),
                ]),
                "asthma": make_mock_response([
                    make_search_result("C002", "Asthma", "ICD10CM"),
                ]),
            }
        )
        adapter.client = mock_client

        results = await adapter.bulk_search(["diabetes", "asthma"], limit=5)
        assert set(results.keys()) == {"diabetes", "asthma"}
        assert len(results["diabetes"]) == 1
        assert results["diabetes"][0].primary_label == "Diabetes"
        assert len(results["asthma"]) == 1
        assert results["asthma"][0].primary_label == "Asthma"

        mock_client.search_api.bulk_search.assert_awaited_once_with(
            ["diabetes", "asthma"],
            page_size=5, return_id_type="concept",
            sabs=None, semantic_groups=None,
        )

    @pytest.mark.asyncio
    async def test_bulk_search_with_filters(self, adapter, mock_client):
        mock_client.search_api.bulk_search = AsyncMock(return_value={})
        adapter.client = mock_client

        await adapter.bulk_search(
            ["diabetes"], limit=3,
            sabs="SNOMEDCT", semantic_groups="DISO",
        )
        mock_client.search_api.bulk_search.assert_awaited_once_with(
            ["diabetes"],
            page_size=3, return_id_type="concept",
            sabs="SNOMEDCT", semantic_groups="DISO",
        )

    @pytest.mark.asyncio
    async def test_bulk_search_error(self, adapter, mock_client):
        mock_client.search_api.bulk_search = AsyncMock(side_effect=Exception("error"))
        adapter.client = mock_client
        results = await adapter.bulk_search(["test"])
        assert results == {}

    @pytest.mark.asyncio
    async def test_bulk_search_no_client(self, adapter):
        adapter.client = None
        results = await adapter.bulk_search(["test"])
        assert results == {}

    # ── 3. get_concept_details ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter, mock_client):
        cui = "C001"
        concept_info = make_concept(
            ui=cui, name="Diabetes",
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

        mock_client.cui_api.get_cui_info = AsyncMock(return_value=make_mock_response(concept_info))
        mock_client.cui_api.get_concept_profile = AsyncMock(return_value=make_mock_response(profile))
        adapter.client = mock_client

        concept = await adapter.get_concept_details(cui)
        assert concept is not None
        assert concept.primary_id == cui
        assert concept.primary_label == "Diabetes"
        assert concept.concept_type == ConceptType.DISEASE
        assert concept.confidence_score == 0.95
        assert concept.definitions == ["A metabolic disorder"]
        assert "Diabetes mellitus" in concept.synonyms
        assert "SNOMEDCT" in concept.categories
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
        mock_client.cui_api.get_cui_info = AsyncMock(side_effect=Exception("API error"))
        adapter.client = mock_client
        result = await adapter.get_concept_details("C001")
        assert result is None

    # ── 4. get_mappings (via get_atoms) ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_mappings_success(self, adapter, mock_client):
        mock_client.cui_api.get_atoms = AsyncMock(
            return_value=make_mock_response([
                make_atom("Diabetes", "SNOMEDCT", "A001", code="73211009"),
                make_atom("Diabetes mellitus", "ICD10CM", "A002", code="E11"),
                make_atom("DM", "MSH", "A003", code="D003920"),
            ])
        )
        adapter.client = mock_client

        mappings = await adapter.get_mappings("C001", limit=10)
        assert len(mappings) == 3
        assert mappings[0]["source"] == "SNOMEDCT"
        assert mappings[0]["source_id"] == "73211009"
        assert mappings[1]["source"] == "ICD10CM"
        assert mappings[1]["source_id"] == "E11"
        assert mappings[2]["source"] == "MSH"
        assert mappings[2]["source_id"] == "D003920"

        mock_client.cui_api.get_atoms.assert_awaited_once_with(
            "C001", sabs=None, page_size=10,
        )

    @pytest.mark.asyncio
    async def test_get_mappings_with_target(self, adapter, mock_client):
        mock_client.cui_api.get_atoms = AsyncMock(
            return_value=make_mock_response([
                make_atom("Diabetes", "SNOMEDCT", "A001", code="73211009"),
            ])
        )
        adapter.client = mock_client

        mappings = await adapter.get_mappings("C001", target_source="SNOMEDCT", limit=10)
        assert len(mappings) == 1
        assert mappings[0]["source"] == "SNOMEDCT"

        mock_client.cui_api.get_atoms.assert_awaited_once_with(
            "C001", sabs="SNOMEDCT", page_size=10,
        )

    @pytest.mark.asyncio
    async def test_get_mappings_deduplicates(self, adapter, mock_client):
        """Same (source, id) pair should only appear once."""
        mock_client.cui_api.get_atoms = AsyncMock(
            return_value=make_mock_response([
                make_atom("Diabetes", "SNOMEDCT", "A001", code="73211009"),
                make_atom("Diabetes", "SNOMEDCT", "A001", code="73211009"),  # duplicate
                make_atom("DM", "MSH", "A002", code="D003920"),
            ])
        )
        adapter.client = mock_client
        mappings = await adapter.get_mappings("C001", limit=10)
        assert len(mappings) == 2

    @pytest.mark.asyncio
    async def test_get_mappings_error(self, adapter, mock_client):
        mock_client.cui_api.get_atoms = AsyncMock(side_effect=Exception("error"))
        adapter.client = mock_client
        mappings = await adapter.get_mappings("C001")
        assert mappings == []

    @pytest.mark.asyncio
    async def test_get_mappings_no_client(self, adapter):
        adapter.client = None
        mappings = await adapter.get_mappings("C001")
        assert mappings == []

    # ── 5. get_relationships ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_relationships_success(self, adapter, mock_client):
        mock_client.cui_api.get_relations = AsyncMock(
            return_value=make_mock_response([
                make_relation("C002", "PAR"),
                make_relation("C003", "CHD"),
                make_relation("C004", "RB"),
            ])
        )
        adapter.client = mock_client

        rels = await adapter.get_relationships("C001", limit=10)
        assert len(rels) == 3
        assert rels[0]["relation_label"] == "PAR"
        assert rels[0]["related_id"] == "C002"
        assert rels[1]["relation_label"] == "CHD"
        assert rels[1]["related_id"] == "C003"
        assert rels[2]["relation_label"] == "RB"

        mock_client.cui_api.get_relations.assert_awaited_once_with(
            "C001", include_relation_labels=None, page_size=10,
        )

    @pytest.mark.asyncio
    async def test_get_relationships_filtered(self, adapter, mock_client):
        mock_client.cui_api.get_relations = AsyncMock(
            return_value=make_mock_response([
                make_relation("C002", "PAR"),
            ])
        )
        adapter.client = mock_client

        rels = await adapter.get_relationships("C001", relation_labels="PAR", limit=10)
        assert len(rels) == 1
        assert rels[0]["relation_label"] == "PAR"

        mock_client.cui_api.get_relations.assert_awaited_once_with(
            "C001", include_relation_labels="PAR", page_size=10,
        )

    @pytest.mark.asyncio
    async def test_get_relationships_error(self, adapter, mock_client):
        mock_client.cui_api.get_relations = AsyncMock(side_effect=Exception("error"))
        adapter.client = mock_client
        rels = await adapter.get_relationships("C001")
        assert rels == []

    @pytest.mark.asyncio
    async def test_get_relationships_no_client(self, adapter):
        adapter.client = None
        rels = await adapter.get_relationships("C001")
        assert rels == []

    # ── 6. Streaming iterators ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_iter_definitions(self, adapter, mock_client):
        """Stream definitions with pagination."""
        mock_client.cui_api.iter_definitions.return_value = AsyncIter([
            make_definition("Def one", "SNOMEDCT"),
            make_definition("Def two", "MSH"),
        ])
        adapter.client = mock_client

        collected = []
        async for d in adapter.iter_definitions("C001", page_size=10):
            collected.append(d)

        assert len(collected) == 2
        assert collected[0]["value"] == "Def one"
        assert collected[1]["root_source"] == "MSH"

        mock_client.cui_api.iter_definitions.assert_called_once_with(
            "C001", page_size=10,
        )

    @pytest.mark.asyncio
    async def test_iter_definitions_empty(self, adapter, mock_client):
        mock_client.cui_api.iter_definitions.return_value = AsyncIter([])
        adapter.client = mock_client

        collected = [d async for d in adapter.iter_definitions("C001")]
        assert collected == []

    @pytest.mark.asyncio
    async def test_iter_definitions_no_client(self, adapter):
        adapter.client = None
        collected = [d async for d in adapter.iter_definitions("C001")]
        assert collected == []

    @pytest.mark.asyncio
    async def test_iter_relations(self, adapter, mock_client):
        """Stream relations with pagination."""
        mock_client.cui_api.iter_relations.return_value = AsyncIter([
            make_relation("C002", "PAR"),
            make_relation("C003", "CHD"),
        ])
        adapter.client = mock_client

        collected = []
        async for r in adapter.iter_relations("C001", page_size=50, relation_labels="PAR,CHD"):
            collected.append(r)

        assert len(collected) == 2
        assert collected[0]["relation_label"] == "PAR"
        assert collected[1]["related_id"] == "C003"

        mock_client.cui_api.iter_relations.assert_called_once_with(
            "C001", page_size=50, include_relation_labels="PAR,CHD",
        )

    @pytest.mark.asyncio
    async def test_iter_relations_no_client(self, adapter):
        adapter.client = None
        collected = [r async for r in adapter.iter_relations("C001")]
        assert collected == []

    # ── Default methods ─────────────────────────────────────────────

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
        assert concept.confidence_score == expected

    def test_semantic_type_mapping(self):
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

        result = adapter._determine_concept_type_from_semantic_types(
            [{"uri": "https://uts.nlm.nih.gov/uts/rest/semantic-network/semantic-type/T999", "name": "Unknown"}]
        )
        assert result == ConceptType.UNKNOWN

    @pytest.mark.parametrize(
        "type_names, expected",
        [
            (["Disease or Syndrome"], ConceptType.DISEASE),
            (["Pharmacologic Substance"], ConceptType.DRUG),
            (["Gene or Genome"], ConceptType.GENE),
            (["Sign or Symptom"], ConceptType.SYMPTOM),
            (["Organic Chemical"], ConceptType.CHEMICAL),
            (["Body Part, Organ, or Organ Component"], ConceptType.ANATOMICAL_ENTITY),
            (["Unknown Type"], ConceptType.UNKNOWN),
            ([], ConceptType.UNKNOWN),
        ],
    )
    def test_semantic_type_name_mapping(self, type_names, expected):
        config = LookupConfig(api_keys={"umls": "test_key"})
        adapter = UMLSAdapter(config)
        assert adapter._determine_concept_type_from_semantic_type_names(type_names) == expected

    # ── 7. CROSSWALK CODES ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_crosswalk_codes_success(self, adapter, mock_client):
        mock_atom = MagicMock()
        mock_atom.cui = "C001"
        mock_atom.name = "Diabetes mellitus"
        mock_atom.root_source = "SNOMEDCT"
        mock_atom.code = "73211009"
        mock_atom.ui = "A001"
        mock_atom.term_type = "PT"
        mock_atom.language = "ENG"

        mock_client.crosswalk_api.get_crosswalk = AsyncMock(
            return_value=make_mock_response([mock_atom])
        )
        adapter.client = mock_client

        results = await adapter.crosswalk_codes("ICD10CM", "E11.9", target_source="SNOMEDCT_US")
        assert len(results) >= 1
        assert results[0]["cui"] == "C001"
        assert results[0]["source"] == "SNOMEDCT"
        assert results[0]["source_id"] == "73211009"

        mock_client.crosswalk_api.get_crosswalk.assert_awaited_once_with(
            source="ICD10CM", id="E11.9", target_source="SNOMEDCT_US",
            include_obsolete=False, page_size=25,
        )

    @pytest.mark.asyncio
    async def test_crosswalk_codes_no_client(self, adapter):
        adapter.client = None
        results = await adapter.crosswalk_codes("ICD10CM", "E11")
        assert results == []

    @pytest.mark.asyncio
    async def test_crosswalk_codes_error(self, adapter, mock_client):
        mock_client.crosswalk_api.get_crosswalk = AsyncMock(
            side_effect=Exception("Crosswalk error")
        )
        adapter.client = mock_client
        results = await adapter.crosswalk_codes("ICD10CM", "E11")
        assert results == []

    @pytest.mark.asyncio
    async def test_crosswalk_codes_deduplicates(self, adapter, mock_client):
        """Same CUI should only appear once."""
        mock_atom = MagicMock()
        mock_atom.cui = "C001"
        mock_atom.name = "Diabetes"
        mock_atom.root_source = "SNOMEDCT"
        mock_atom.code = "73211009"
        mock_atom.ui = "A001"
        mock_atom.term_type = "PT"
        mock_atom.language = "ENG"

        mock_client.crosswalk_api.get_crosswalk = AsyncMock(
            return_value=make_mock_response([mock_atom, mock_atom])
        )
        adapter.client = mock_client

        results = await adapter.crosswalk_codes("ICD10CM", "E11")
        assert len(results) == 1

    # ── 8. DOWNLOAD TERMINOLOGY ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_download_terminology_no_client(self, adapter):
        adapter.client = None
        with pytest.raises(RuntimeError, match="client not available"):
            await adapter.download_terminology("2025AA")

    @pytest.mark.asyncio
    async def test_download_terminology_no_release_name(self, adapter, mock_client):
        """When release_name is None, should list current releases first."""
        mock_release = MagicMock()
        mock_release.name = "2025AA"

        mock_client.release_api.list_releases = AsyncMock(
            return_value=make_mock_response([mock_release])
        )
        mock_client.release_api.download_file = AsyncMock(return_value=Path("/tmp/test.zip"))
        adapter.client = mock_client

        result = await adapter.download_terminology(
            release_name=None,
            output_dir="/tmp",
            overwrite=True,
        )
        assert result is not None
        mock_client.release_api.list_releases.assert_awaited_once_with(current=True)

    @pytest.mark.asyncio
    async def test_download_terminology_with_name(self, adapter, mock_client):
        """When release_name is specified, should download directly."""
        mock_client.release_api.download_file = AsyncMock(return_value=Path("/tmp/test.zip"))
        adapter.client = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await adapter.download_terminology(
                release_name="2025AA",
                output_dir=tmpdir,
                overwrite=False,
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_download_terminology_error(self, adapter, mock_client):
        mock_client.release_api.download_file = AsyncMock(
            side_effect=Exception("Download failed")
        )
        adapter.client = mock_client

        with pytest.raises(Exception, match="Download failed"):
            await adapter.download_terminology("2025AA", output_dir="/tmp")

    # ── 9. CACHE INTEGRATION ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_concepts_with_cache(self, adapter, mock_client):
        """When cache is configured, search should cache results."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from knowledge_lookup.umls.cache import UMLSCache

            cache = UMLSCache(db_path=f"{tmpdir}/test.db", auto_fts=True)
            adapter_with_cache = UMLSAdapter(adapter.config, cache=cache)
            adapter_with_cache.client = mock_client

            mock_client.search_api.search = AsyncMock(
                return_value=make_mock_response([
                    make_search_result("C001", "Diabetes", "SNOMEDCT"),
                ])
            )

            results = await adapter_with_cache.search_concepts("diabetes", limit=10)
            assert len(results) == 1
            assert results[0].primary_label == "Diabetes"

            # Concept should be cached
            cached = cache.get_concept("C001")
            assert cached is not None
            assert cached["name"] == "Diabetes"

    @pytest.mark.asyncio
    async def test_search_concepts_cache_hit(self, adapter, mock_client):
        """When cache has the data, should return from cache without API call."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from knowledge_lookup.umls.cache import UMLSCache

            cache = UMLSCache(db_path=f"{tmpdir}/test.db", auto_fts=True)
            adapter_with_cache = UMLSAdapter(adapter.config, cache=cache)
            adapter_with_cache.client = mock_client

            # Pre-populate cache
            cache.cache_search_result("C001", "Diabetes", "SNOMEDCT")

            # API should NOT be called
            mock_client.search_api.search = AsyncMock(
                side_effect=Exception("Should not be called")
            )

            results = await adapter_with_cache.search_concepts("diabetes", limit=10)
            assert len(results) >= 1
            assert results[0].primary_id == "C001"

    @pytest.mark.asyncio
    async def test_search_concepts_cache_fallback_on_error(self, adapter, mock_client):
        """When API fails, cache should act as fallback."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from knowledge_lookup.umls.cache import UMLSCache

            cache = UMLSCache(db_path=f"{tmpdir}/test.db", auto_fts=True)
            adapter_with_cache = UMLSAdapter(adapter.config, cache=cache)
            adapter_with_cache.client = mock_client

            # Pre-populate cache
            cache.cache_search_result("C001", "Diabetes", "SNOMEDCT")

            # API fails
            mock_client.search_api.search = AsyncMock(
                side_effect=Exception("API unavailable")
            )

            results = await adapter_with_cache.search_concepts("diabetes", limit=10, use_cache=True)
            assert len(results) >= 1
            assert results[0].primary_id == "C001"

    def test_adapter_cache_disabled_by_default(self, adapter):
        """By default, cache should be None."""
        assert adapter._cache is None

    def test_adapter_cache_enabled(self):
        """Cache can be passed during construction."""
        import tempfile

        from knowledge_lookup.umls.cache import UMLSCache
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = UMLSCache(db_path=f"{tmpdir}/test.db")
            adapter_with_cache = UMLSAdapter(LookupConfig(), cache=cache)
            assert adapter_with_cache._cache is cache
