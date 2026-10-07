"""Unit tests for CellOntologyAdapter (Cell Ontology via OLS4); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.cellontology_adapter import CellOntologyAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.cellontology_responses import (
    CHILDREN_T_CELL,
    GRAPH_T_CELL,
    PARENTS_T_CELL,
    SEARCH_T_CELL,
    TERM_T_CELL,
)

pytestmark = pytest.mark.unit

T_CELL_IRI = "http://purl.obolibrary.org/obo/CL_0000084"


@pytest.fixture
def adapter(lookup_config):
    return CellOntologyAdapter(lookup_config)


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


def details_router():
    return _router(
        CL_0000084=TERM_T_CELL,
        **{"/parents": PARENTS_T_CELL, "/children": CHILDREN_T_CELL},
    )


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CELLONTOLOGY
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw",
        ["CL:0000084", "cl:0000084", "CL_0000084", "0000084", T_CELL_IRI, f"  {T_CELL_IRI} "],
    )
    def test_id_normalisation(self, raw):
        assert CellOntologyAdapter._to_iri(raw) == T_CELL_IRI

    @pytest.mark.parametrize("raw", ["", "  ", "HP:0000001", "T cell", "CL:12", None])
    def test_invalid_ids(self, raw):
        assert CellOntologyAdapter._to_iri(raw) is None

    def test_curie_conversion(self):
        assert CellOntologyAdapter._to_curie(T_CELL_IRI) == "CL:0000084"
        assert CellOntologyAdapter._to_curie("GO_0002456") == "GO:0002456"
        assert CellOntologyAdapter._to_curie("plain") == "plain"

    def test_term_url_is_double_encoded(self, adapter):
        url = adapter._term_url(T_CELL_IRI, "/graph")
        assert url.endswith(
            "/ontologies/cl/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FCL_0000084/graph"
        )


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_filters_non_cl_and_sets_fields(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(SEARCH_T_CELL))
        ) as req:
            results = await adapter.search_concepts("T cell", limit=10)
        params = req.call_args.args[1]
        assert params["ontology"] == "cl"
        assert params["obsoletes"] == "false"
        assert [c.primary_id for c in results] == ["CL:0000084", "CL:0000827"]  # UBERON dropped
        t_cell = results[0]
        assert t_cell.primary_label == "T cell"
        assert t_cell.concept_type == ConceptType.CELL_TYPE
        assert "T lymphocyte" in t_cell.synonyms
        assert t_cell.definitions[0].startswith("A type of lymphocyte")
        assert t_cell.confidence_score > results[1].confidence_score

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(SEARCH_T_CELL))
        ) as req:
            results = await adapter.search_concepts("T cell", limit=1)
        assert len(results) == 1
        assert req.call_args.args[1]["rows"] == 1

    @pytest.mark.asyncio
    async def test_search_by_cl_id_uses_details(self, adapter):
        with patch.object(adapter, "_make_request", details_router()):
            results = await adapter.search_concepts("CL:0000084")
        assert [c.primary_id for c in results] == ["CL:0000084"]

    @pytest.mark.asyncio
    async def test_search_by_unknown_cl_id(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.search_concepts("CL:9999999") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("T cell", 0)])
    async def test_search_empty_inputs(self, adapter, query, limit):
        assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_search_empty_and_malformed_responses(self, adapter):
        for payload in ({}, {"response": {}}, {"response": {"docs": []}}, None):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("T cell") == []
        docs = {
            "response": {
                "docs": [
                    {"obo_id": "CL:1"},  # no label
                    {"label": "x"},  # no id
                    {"obo_id": "CL:0000084", "label": "T cell"},
                    {"obo_id": "CL:0000084", "label": "T cell"},  # duplicate
                ]
            }
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=docs)):
            results = await adapter.search_concepts("T cell")
        assert [c.primary_id for c in results] == ["CL:0000084"]

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("T cell") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_for_ids_in_every_form(self, adapter):
        with patch.object(adapter, "_make_request", details_router()):
            for raw in ("CL:0000084", "CL_0000084", T_CELL_IRI):
                concept = await adapter.get_concept_details(raw)
                assert concept is not None and concept.primary_id == "CL:0000084"

    @pytest.mark.asyncio
    async def test_details_content(self, adapter):
        with patch.object(adapter, "_make_request", details_router()):
            concept = await adapter.get_concept_details("CL:0000084")
        assert concept.primary_label == "T cell"
        assert concept.concept_type == ConceptType.CELL_TYPE
        assert {"T lymphocyte", "T-cell"} <= set(concept.synonyms)
        assert concept.parents == ["lymphocyte"]
        assert "alpha-beta T cell" in concept.children
        assert "Xref: MESH:D013601" in concept.categories
        assert any(i.identifier == T_CELL_IRI for i in concept.identifiers)
        assert concept.source_data[KnowledgeSource.CELLONTOLOGY]["obo_id"] == "CL:0000084"

    @pytest.mark.asyncio
    async def test_details_survives_failing_hierarchy(self, adapter):
        router = _router(CL_0000084=TERM_T_CELL, **{"/parents": RuntimeError("x")})

        async def fake(url, params=None, headers=None, json_data=None):
            if url.endswith("/children"):
                raise RuntimeError("down")
            return await router(url, params)

        with patch.object(adapter, "_make_request", fake):
            concept = await adapter.get_concept_details("CL:0000084")
        assert concept is not None and concept.parents == [] and concept.children == []

    @pytest.mark.asyncio
    async def test_details_obsolete_marker(self, adapter):
        term = copy.deepcopy(TERM_T_CELL)
        term["is_obsolete"] = True
        term["_links"] = {}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=term)):
            concept = await adapter.get_concept_details("CL:0000084")
        assert "obsolete" in concept.categories

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [{}, [], None, {"iri": "x"}])
    async def test_details_missing_or_unusable(self, adapter, payload):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            assert await adapter.get_concept_details("CL:0000084") is None

    @pytest.mark.asyncio
    async def test_details_invalid_id_and_error(self, adapter):
        assert await adapter.get_concept_details("") is None
        assert await adapter.get_concept_details("HP:0000001") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.get_concept_details("CL:0000084") is None

    def test_term_without_obo_id_falls_back_to_short_form(self, adapter):
        term = {"iri": T_CELL_IRI, "label": "T cell", "short_form": "CL_0000084"}
        assert adapter._term_to_concept(term).primary_id == "CL:0000084"
        assert adapter._term_to_concept({"iri": T_CELL_IRI}) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships_from_graph(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(GRAPH_T_CELL))
        ):
            rels = await adapter.get_relationships("CL:0000084", limit=100)
        by_label = {}
        for rel in rels:
            by_label.setdefault(rel["relation_label"], []).append(rel)
        assert by_label["is_a"][0]["related_id"] == "CL:0000542"
        assert by_label["is_a"][0]["related_name"] == "lymphocyte"
        assert by_label["develops_from"][0]["related_id"] == "CL:0000827"
        assert by_label["capable_of"][0]["related_id"] == "GO:0002456"
        assert {r["related_name"] for r in by_label["has_subclass"]} >= {"alpha-beta T cell"}
        assert "inverse_occurs_in" in by_label
        assert all(r["source"] == "CL" for r in rels)
        assert {r["direction"] for r in by_label["is_a"]} == {"outgoing"}
        assert {r["direction"] for r in by_label["has_subclass"]} == {"incoming"}
        # ordering: parents, own relations, children, inverse relations
        labels = [r["relation_label"] for r in rels]
        assert labels.index("is_a") < labels.index("develops_from") < labels.index("has_subclass")
        assert labels.index("has_subclass") < labels.index("inverse_occurs_in")

    @pytest.mark.asyncio
    async def test_relationships_limit_and_dedup(self, adapter):
        graph = copy.deepcopy(GRAPH_T_CELL)
        graph["edges"].append(copy.deepcopy(graph["edges"][0]))  # duplicate edge
        graph["edges"].append(
            {"source": T_CELL_IRI, "target": T_CELL_IRI, "label": "x", "uri": ""}
        )
        graph["edges"].append({"source": "a", "target": "b", "label": "unrelated", "uri": ""})
        with patch.object(adapter, "_make_request", AsyncMock(return_value=graph)):
            everything = await adapter.get_relationships("CL:0000084", limit=100)
            capped = await adapter.get_relationships("CL:0000084", limit=3)
        assert sum(r["relation_label"] == "is_a" for r in everything) == 1
        assert all(r["related_id"] != "CL:0000084" for r in everything)
        assert len(capped) == 3

    @pytest.mark.asyncio
    async def test_relationships_edge_cases(self, adapter):
        assert await adapter.get_relationships("not an id") == []
        assert await adapter.get_relationships("CL:0000084", limit=0) == []
        for payload in ([], {}, {"nodes": None, "edges": None}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.get_relationships("CL:0000084") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("CL:0000084") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_from_obo_xref(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(TERM_T_CELL))
        ):
            mappings = await adapter.get_mappings("CL:0000084")
        targets = {m["toId"]: m for m in mappings}
        assert "MESH:D013601" in targets and "FMA:62870" in targets
        mesh = targets["MESH:D013601"]
        assert mesh == {
            "fromId": "CL:0000084",
            "toId": "MESH:D013601",
            "fromSource": "CL",
            "toSource": "MESH",
            "mappingType": "xref",
            "confidence": 0.9,
        }

    @pytest.mark.asyncio
    async def test_mappings_fall_back_to_annotation_and_dedup(self, adapter):
        term = {
            "iri": T_CELL_IRI,
            "obo_id": "CL:0000084",
            "label": "T cell",
            "annotation": {"database_cross_reference": ["MESH:D013601", "MESH:D013601", "bad"]},
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=term)):
            assert [m["toId"] for m in await adapter.get_mappings("CL:0000084")] == [
                "MESH:D013601"
            ]
        term["annotation"] = {"database_cross_reference": "FMA:1"}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=term)):
            assert [m["toId"] for m in await adapter.get_mappings("CL:0000084")] == ["FMA:1"]

    @pytest.mark.asyncio
    async def test_mappings_failures(self, adapter):
        assert await adapter.get_mappings("") == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            assert await adapter.get_mappings("CL:0000084") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("CL:0000084") == []
