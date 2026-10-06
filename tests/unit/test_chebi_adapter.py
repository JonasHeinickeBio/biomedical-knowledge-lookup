"""Unit tests for ChEBIAdapter (EBI ChEBI public REST API); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.chebi_adapter import ChEBIAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.chebi_responses import (
    CHILDREN_ASPIRIN,
    COMPOUND_ASPIRIN,
    PARENTS_ASPIRIN,
    SEARCH_ASPIRIN,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter(lookup_config):
    return ChEBIAdapter(lookup_config)


def _router(parents=PARENTS_ASPIRIN, children=CHILDREN_ASPIRIN, compound=COMPOUND_ASPIRIN):
    async def fake(url, params=None, headers=None, json_data=None):
        for marker, value in (
            ("/ontology/parents/", parents),
            ("/ontology/children/", children),
            ("/compound/", compound),
        ):
            if marker in url:
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
        raise AssertionError(f"unexpected URL {url}")

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CHEBI
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("CHEBI:15365", "15365"),
            ("chebi:15365", "15365"),
            ("CHEBI_15365", "15365"),
            ("15365", "15365"),
            ("  15365 ", "15365"),
            ("CHEBI:0015365", "15365"),
            ("http://purl.obolibrary.org/obo/CHEBI_15365", "15365"),
            ("HP:0000001", None),
            ("aspirin", None),
            ("", None),
            (None, None),
        ],
    )
    def test_id_normalisation(self, raw, expected):
        assert ChEBIAdapter._numeric_id(raw) == expected


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_hoists_exact_name_and_cleans_html(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(SEARCH_ASPIRIN))
        ) as req:
            results = await adapter.search_concepts("acetylsalicylic acid", limit=10)
        assert req.call_args.args[0].endswith("/es_search/")
        assert req.call_args.args[1]["term"] == "acetylsalicylic acid"
        assert results[0].primary_id == "CHEBI:15365"  # exact name first, despite ES order
        labels = {c.primary_label for c in results}
        assert "coenzyme Q10" in labels  # <small><sub> markup stripped
        top = results[0]
        assert top.concept_type == ConceptType.CHEMICAL
        assert top.confidence_score == 0.9
        assert top.source_data[KnowledgeSource.CHEBI]["formula"] == "C9H8O4"

    @pytest.mark.asyncio
    async def test_search_keeps_es_order_without_exact_hit_and_limits(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(SEARCH_ASPIRIN))
        ) as req:
            results = await adapter.search_concepts("aspirin", limit=2)
        assert [c.primary_id for c in results] == ["CHEBI:759292", "CHEBI:749969"]
        assert results[0].confidence_score == 0.75  # 2-star entry
        assert req.call_args.args[1]["size"] >= 15

    @pytest.mark.asyncio
    async def test_search_dedups_and_skips_bad_hits(self, adapter):
        payload = {
            "results": [
                {"_source": {"chebi_accession": "CHEBI:1", "name": "a", "stars": 3}},
                {"_source": {"chebi_accession": "CHEBI:1", "name": "a", "stars": 3}},
                {"_source": {"chebi_accession": "CHEBI:2"}},
                {"_source": {"name": "no id"}},
                {},
            ]
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            assert [c.primary_id for c in await adapter.search_concepts("a")] == ["CHEBI:1"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("  ", 5), ("aspirin", 0), (None, 5)])
    async def test_search_empty_inputs(self, adapter, query, limit):
        assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_search_empty_and_error(self, adapter):
        for payload in ({}, {"results": []}, None):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("aspirin") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("aspirin") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_content(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(COMPOUND_ASPIRIN))
        ) as req:
            concept = await adapter.get_concept_details("15365")
        assert req.call_args.args[0].endswith("/compound/15365/")
        assert concept.primary_id == "CHEBI:15365"
        assert concept.primary_label == "acetylsalicylic acid"
        assert concept.concept_type == ConceptType.CHEMICAL
        assert concept.definitions[0].startswith("A member of the class of benzoic acids")
        assert "2-acetoxybenzoic acid" in concept.synonyms
        assert "acetylsalicylic acid" not in concept.synonyms
        assert len(concept.synonyms) == len(set(concept.synonyms))
        assert "benzoic acids" in concept.parents
        assert "Yosprala" not in concept.children  # 'has part' is not a subclass edge
        assert "role: non-steroidal anti-inflammatory drug" in concept.categories
        data = concept.source_data[KnowledgeSource.CHEBI]
        assert data["formula"] == "C9H8O4"
        assert data["mass"] == "180.159"
        assert data["inchikey"] == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
        assert data["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
        assert "non-steroidal anti-inflammatory drug" in data["roles"]
        assert "CHEBI:2890" in data["secondary_ids"]
        assert concept.confidence_score == 0.9
        assert any(i.identifier == "CHEBI:15365" for i in concept.identifiers)

    @pytest.mark.asyncio
    async def test_details_children_via_is_a(self, adapter):
        compound = copy.deepcopy(COMPOUND_ASPIRIN)
        compound["ontology_relations"]["incoming_relations"].append(
            {
                "init_id": 1,
                "init_name": "child <i>x</i>",
                "relation_type": "is a",
                "final_id": 15365,
            }
        )
        with patch.object(adapter, "_make_request", AsyncMock(return_value=compound)):
            concept = await adapter.get_concept_details("CHEBI:15365")
        assert concept.children == ["child x"]

    @pytest.mark.asyncio
    async def test_details_invalid_missing_error(self, adapter):
        assert await adapter.get_concept_details("not an id") is None
        for payload in ({}, [], None, {"chebi_accession": "CHEBI:1"}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.get_concept_details("CHEBI:1") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("404"))):
            assert await adapter.get_concept_details("CHEBI:1") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships_shape_and_order(self, adapter):
        with patch.object(adapter, "_make_request", _router()):
            rels = await adapter.get_relationships("CHEBI:15365", limit=100)
        labels = [r["relation_label"] for r in rels]
        assert (
            labels.index("is_a") < labels.index("has_role") < labels.index("has_functional_parent")
        )
        for rel in rels:
            assert set(rel) >= {"relation_label", "related_id", "related_name", "source"}
            assert rel["related_id"].startswith("CHEBI:") and rel["source"] == "ChEBI"
        role = next(r for r in rels if r["relation_label"] == "has_role")
        assert role["direction"] == "outgoing"
        assert role["related_name"]
        assert "is_conjugate_acid_of" in labels
        incoming = [r for r in rels if r["direction"] == "incoming"]
        assert incoming and all(r["relation_label"].startswith("inverse_") for r in incoming)
        assert labels.index(incoming[0]["relation_label"]) > labels.index("is_a")

    @pytest.mark.asyncio
    async def test_relationships_children_is_a_become_has_subclass(self, adapter):
        children = {
            "ontology_relations": {
                "incoming_relations": [
                    {"init_id": 5, "init_name": "kid", "relation_type": "is a", "final_id": 1},
                    {"init_id": 5, "init_name": "kid", "relation_type": "is a", "final_id": 1},
                ]
            }
        }
        with patch.object(adapter, "_make_request", _router(parents={}, children=children)):
            rels = await adapter.get_relationships("1")
        assert rels == [
            {
                "relation_label": "has_subclass",
                "related_id": "CHEBI:5",
                "related_name": "kid",
                "source": "ChEBI",
                "direction": "incoming",
            }
        ]

    @pytest.mark.asyncio
    async def test_relationships_limit(self, adapter):
        with patch.object(adapter, "_make_request", _router()):
            assert len(await adapter.get_relationships("15365", limit=2)) == 2
            # the cap also applies while reading the children endpoint
            outgoing = len(PARENTS_ASPIRIN["ontology_relations"]["outgoing_relations"])
            assert (
                len(await adapter.get_relationships("15365", limit=outgoing + 1)) == outgoing + 1
            )
            assert await adapter.get_relationships("15365", limit=0) == []

    @pytest.mark.asyncio
    async def test_relationships_partial_failure_and_bad_input(self, adapter):
        assert await adapter.get_relationships("bogus") == []
        with patch.object(adapter, "_make_request", _router(children=RuntimeError("x"))):
            rels = await adapter.get_relationships("15365", limit=100)
        assert rels and all(r["direction"] == "outgoing" for r in rels)
        with patch.object(
            adapter,
            "_make_request",
            _router(parents=RuntimeError("x"), children=RuntimeError("y")),
        ):
            assert await adapter.get_relationships("15365") == []
        broken = {
            "ontology_relations": {"outgoing_relations": [{"relation_type": ""}, {"final_id": 3}]}
        }
        with patch.object(adapter, "_make_request", _router(parents=broken, children={})):
            assert await adapter.get_relationships("15365") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=copy.deepcopy(COMPOUND_ASPIRIN))
        ):
            mappings = await adapter.get_mappings("CHEBI:15365")
        pairs = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("DrugBank", "DB00945") in pairs
        assert ("KEGG DRUG", "D00109") in pairs
        assert ("KEGG COMPOUND", "C01405") in pairs
        assert ("HMDB", "HMDB0001879") in pairs
        assert ("CAS", "50-78-2") in pairs
        assert not any(source == "PubMed" for source, _ in pairs)  # citations are not mappings
        assert sum(1 for s, i in pairs if s == "CAS") == 1  # CAS deduplicated across databases
        first = mappings[0]
        assert first["fromId"] == "CHEBI:15365" and first["fromSource"] == "ChEBI"
        assert set(first) == {
            "fromId",
            "toId",
            "fromSource",
            "toSource",
            "mappingType",
            "confidence",
        }

    @pytest.mark.asyncio
    async def test_mappings_edge_cases(self, adapter):
        assert await adapter.get_mappings("bogus") == []
        payload = {
            "database_accessions": {
                "MANUAL_X_REF": [
                    {"source_name": "X", "accession_number": ""},
                    {"source_name": "", "accession_number": "1"},
                    {"source_name": "Y", "accession_number": "2"},
                    {"source_name": "Y", "accession_number": "2"},
                ]
            }
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            result = await adapter.get_mappings("7")
        assert [(m["fromId"], m["toSource"], m["toId"]) for m in result] == [("CHEBI:7", "Y", "2")]
        for bad in ([], None, {}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=bad)):
                assert await adapter.get_mappings("7") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("7") == []
