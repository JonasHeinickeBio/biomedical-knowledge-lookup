"""Unit tests for DiseaseOntologyAdapter (Disease Ontology via OLS4); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.doid_adapter import DiseaseOntologyAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.doid_responses import (
    CHILDREN_DM,
    GRAPH_ASTHMA,
    PARENTS_CFS,
    PARENTS_DM,
    SEARCH_CFS,
    TERM_CFS,
    TERM_DM,
)

pytestmark = pytest.mark.unit

CFS_IRI = "http://purl.obolibrary.org/obo/DOID_8544"


@pytest.fixture
def adapter(lookup_config):
    return DiseaseOntologyAdapter(lookup_config)


def _router(**by_suffix):
    """Fake ``_make_request`` answering by URL suffix (longest match first)."""

    async def fake(url, params=None, headers=None, json_data=None):
        for suffix in sorted(by_suffix, key=len, reverse=True):
            if url.endswith(suffix):
                value = by_suffix[suffix]
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
        raise AssertionError(f"unexpected URL {url}")

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.DOID
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw",
        ["DOID:8544", "doid:8544", "DOID_8544", "8544", CFS_IRI, f"  {CFS_IRI} "],
    )
    def test_id_normalisation(self, raw):
        assert DiseaseOntologyAdapter._to_iri(raw) == CFS_IRI

    def test_id_normalisation_keeps_leading_zeros(self):
        assert DiseaseOntologyAdapter._to_iri("DOID:0080848").endswith("DOID_0080848")

    @pytest.mark.parametrize("raw", ["", "  ", "HP:0000001", "chronic fatigue", "DOID:", None])
    def test_invalid_ids(self, raw):
        assert DiseaseOntologyAdapter._to_iri(raw) is None

    def test_curie_conversion(self):
        assert DiseaseOntologyAdapter._to_curie(CFS_IRI) == "DOID:8544"
        assert DiseaseOntologyAdapter._to_curie("MIM_145600") == "MIM:145600"
        assert DiseaseOntologyAdapter._to_curie("plain") == "plain"

    def test_term_url_is_double_encoded(self, adapter):
        url = adapter._term_url(CFS_IRI, "/graph")
        assert url.endswith(
            "/ontologies/doid/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FDOID_8544/graph"
        )

    @pytest.mark.parametrize(
        "database,expected",
        [
            ("SNOMEDCT_US_2025_09_01", "SNOMEDCT_US"),
            ("SNOMEDCT_US", "SNOMEDCT_US"),
            ("MIM", "OMIM"),
            ("ORDO", "Orphanet"),
            ("NCI", "NCIT"),
            ("UMLS_CUI", "UMLS"),
            ("MESH", "MESH"),
            ("ICD10CM", "ICD10CM"),
        ],
    )
    def test_database_normalisation(self, database, expected):
        assert DiseaseOntologyAdapter._normalise_database(database) == expected


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_filters_and_sets_fields(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(SEARCH_CFS))
        ) as req:
            results = await adapter.search_concepts("chronic fatigue syndrome", limit=10)
        params = req.call_args.args[1]
        assert params["ontology"] == "doid"
        assert params["obsoletes"] == "false"
        assert [c.primary_id for c in results] == ["DOID:8544", "DOID:631", "DOID:0080848"]
        cfs = results[0]
        assert cfs.primary_label == "chronic fatigue syndrome"
        assert cfs.concept_type == ConceptType.DISEASE
        assert "Myalgic encephalomyelitis" in cfs.synonyms
        # the curator note is dropped, the real definition kept
        assert len(cfs.definitions) == 1 and cfs.definitions[0].startswith("A syndrome that")
        assert cfs.confidence_score > results[1].confidence_score
        assert cfs.source_data[KnowledgeSource.DOID]["obo_id"] == "DOID:8544"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(SEARCH_CFS))
        ) as req:
            results = await adapter.search_concepts("fatigue", limit=2)
        assert len(results) == 2
        assert req.call_args.args[1]["rows"] == 2

    @pytest.mark.asyncio
    async def test_search_by_doid_uses_details(self, adapter):
        router = _router(DOID_8544=TERM_CFS, **{"/parents": PARENTS_CFS})
        with patch.object(adapter, "_make_request", router):
            results = await adapter.search_concepts("DOID:8544")
        assert [c.primary_id for c in results] == ["DOID:8544"]

    @pytest.mark.asyncio
    async def test_search_numeric_text_is_a_text_query(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value={"response": {"docs": []}})
        ) as req:
            assert await adapter.search_concepts("1234") == []
        assert req.call_args.args[1]["q"] == "1234"

    @pytest.mark.asyncio
    async def test_search_by_unknown_doid(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.search_concepts("DOID:9999999") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("diabetes", 0)])
    async def test_search_empty_inputs(self, adapter, query, limit):
        assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_search_empty_and_malformed_responses(self, adapter):
        for payload in ({}, {"response": {}}, {"response": {"docs": []}}, None):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("diabetes") == []

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("diabetes") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_for_ids_in_every_form(self, adapter):
        router = _router(DOID_8544=TERM_CFS, **{"/parents": PARENTS_CFS})
        with patch.object(adapter, "_make_request", router):
            for raw in ("DOID:8544", "DOID_8544", "8544", CFS_IRI):
                concept = await adapter.get_concept_details(raw)
                assert concept is not None and concept.primary_id == "DOID:8544"

    @pytest.mark.asyncio
    async def test_details_content_leaf_term(self, adapter):
        router = _router(DOID_8544=TERM_CFS, **{"/parents": PARENTS_CFS})
        with patch.object(adapter, "_make_request", router):
            concept = await adapter.get_concept_details("DOID:8544")
        assert concept.primary_label == "chronic fatigue syndrome"
        assert concept.concept_type == ConceptType.DISEASE
        assert "CFS" in concept.synonyms
        assert concept.parents == ["syndrome"]
        assert concept.children == []  # has_children is false: no children request made
        assert "Xref: UMLS:C0015674" in concept.categories
        assert "Xref: SNOMEDCT_US:193054000" in concept.categories
        assert any(i.identifier == CFS_IRI for i in concept.identifiers)
        data = concept.source_data[KnowledgeSource.DOID]
        assert data["obo_id"] == "DOID:8544" and "DO_rare_slim" in data["in_subset"]

    @pytest.mark.asyncio
    async def test_details_with_children(self, adapter):
        router = _router(DOID_9351=TERM_DM, **{"/parents": PARENTS_DM, "/children": CHILDREN_DM})
        with patch.object(adapter, "_make_request", router):
            concept = await adapter.get_concept_details("DOID:9351")
        assert concept.parents == ["glucose metabolism disease"]
        assert concept.children == ["type 1 diabetes mellitus", "type 2 diabetes mellitus"]

    @pytest.mark.asyncio
    async def test_details_survives_failing_hierarchy(self, adapter):
        async def fake(url, params=None, headers=None, json_data=None):
            if url.endswith(("/parents", "/children")):
                raise RuntimeError("down")
            return copy.deepcopy(TERM_DM)

        with patch.object(adapter, "_make_request", fake):
            concept = await adapter.get_concept_details("DOID:9351")
        assert concept is not None and concept.parents == [] and concept.children == []

    @pytest.mark.asyncio
    async def test_details_obsolete_marker(self, adapter):
        term = copy.deepcopy(TERM_CFS)
        term["is_obsolete"] = True
        term["_links"] = {}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=term)):
            concept = await adapter.get_concept_details("DOID:8544")
        assert "obsolete" in concept.categories

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [{}, [], None, {"iri": "x"}])
    async def test_details_missing_or_unusable(self, adapter, payload):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            assert await adapter.get_concept_details("DOID:8544") is None

    @pytest.mark.asyncio
    async def test_details_invalid_id_and_error(self, adapter):
        assert await adapter.get_concept_details("") is None
        assert await adapter.get_concept_details("HP:0000001") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.get_concept_details("DOID:8544") is None

    def test_term_without_obo_id_falls_back_to_short_form(self, adapter):
        term = {"iri": CFS_IRI, "label": "chronic fatigue syndrome", "short_form": "DOID_8544"}
        assert adapter._term_to_concept(term).primary_id == "DOID:8544"
        assert adapter._term_to_concept({"iri": CFS_IRI}) is None

    def test_definitions_filter_notes_and_dedup(self, adapter):
        target: list[str] = []
        adapter._add_definitions(
            target,
            ["Xref MGI. OMIM mapping confirmed by DO. [SN].", "Real.", "Real.", "  ", 5],
        )
        assert target == ["Real."]
        adapter._add_definitions(target, None)
        adapter._add_definitions(target, "No OMIM mapping, confirmed by DO. [LS].")
        assert target == ["Real."]
        adapter._add_definitions(None, "x")  # must not raise


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships_from_graph(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(GRAPH_ASTHMA))
        ) as req:
            rels = await adapter.get_relationships("DOID:2841", limit=100)
        assert req.call_args.args[0].endswith("DOID_2841/graph")
        by_label: dict[str, list[dict]] = {}
        for rel in rels:
            by_label.setdefault(rel["relation_label"], []).append(rel)
        assert by_label["is_a"][0]["related_id"] == "DOID:1176"
        assert by_label["is_a"][0]["related_name"] == "bronchial disease"
        assert by_label["has_phenotype"][0]["related_id"] == "HP:0002099"
        assert {r["related_id"] for r in by_label["has_symptom"]} == {
            "SYMP:0000614",
            "SYMP:0000615",
        }  # the duplicate edge is collapsed
        assert by_label["has_subclass"][0]["related_name"] == "chronic asthma"
        assert by_label["inverse_disease_has_feature"][0]["related_id"] == "DOID:1827"
        assert by_label["inverse_contributes_to_condition"][0]["related_id"] == "MIM:600807"
        assert all(r["source"] == "DOID" for r in rels)
        assert by_label["is_a"][0]["direction"] == "outgoing"
        assert by_label["has_subclass"][0]["direction"] == "incoming"
        assert by_label["has_symptom"][0]["relation_iri"].endswith("RO_0002452")
        # ordering: parents, own relations, children, inverse relations
        labels = [r["relation_label"] for r in rels]
        assert labels.index("is_a") < labels.index("has_phenotype") < labels.index("has_subclass")
        assert labels.index("has_subclass") < labels.index("inverse_disease_has_feature")
        # unrelated / self / unlabeled edges are not reported
        assert len(rels) == 7

    @pytest.mark.asyncio
    async def test_relationships_limit(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(GRAPH_ASTHMA))
        ):
            capped = await adapter.get_relationships("DOID:2841", limit=3)
        assert [r["relation_label"] for r in capped] == ["is_a", "has_phenotype", "has_symptom"]

    @pytest.mark.asyncio
    async def test_relationships_edge_cases(self, adapter):
        assert await adapter.get_relationships("not an id") == []
        assert await adapter.get_relationships("DOID:2841", limit=0) == []
        for payload in ([], {}, {"nodes": None, "edges": None}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.get_relationships("DOID:2841") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("DOID:2841") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_from_obo_xref(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(TERM_CFS))
        ):
            mappings = await adapter.get_mappings("DOID:8544")
        targets = {m["toId"]: m for m in mappings}
        assert set(targets) == {
            "GARD:7121",
            "ICD10CM:G93.32",
            "ICD9CM:780.71",
            "MESH:D015673",
            "NCIT:C3037",
            "SNOMEDCT_US:193054000",
            "UMLS:C0015674",
        }
        assert targets["UMLS:C0015674"] == {
            "fromId": "DOID:8544",
            "toId": "UMLS:C0015674",
            "fromSource": "DOID",
            "toSource": "UMLS",
            "mappingType": "xref",
            "confidence": 0.9,
        }

    @pytest.mark.asyncio
    async def test_mappings_fall_back_to_annotation_and_dedup(self, adapter):
        term = {
            "iri": CFS_IRI,
            "obo_id": "DOID:8544",
            "label": "chronic fatigue syndrome",
            "annotation": {
                "database_cross_reference": ["MESH:D015673", "MESH:D015673", "bad", "MIM:1"]
            },
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=term)):
            assert [m["toId"] for m in await adapter.get_mappings("DOID:8544")] == [
                "MESH:D015673",
                "OMIM:1",
            ]
        term["annotation"] = {"database_cross_reference": "ORDO:423"}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=term)):
            assert [m["toId"] for m in await adapter.get_mappings("DOID:8544")] == ["Orphanet:423"]

    @pytest.mark.asyncio
    async def test_mappings_failures(self, adapter):
        assert await adapter.get_mappings("") == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            assert await adapter.get_mappings("DOID:8544") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("DOID:8544") == []
