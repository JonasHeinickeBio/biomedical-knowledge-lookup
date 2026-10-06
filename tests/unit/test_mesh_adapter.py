"""
Unit tests for MeSHAdapter (HTTP mocked with trimmed real responses).
"""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.mesh_adapter import MeSHAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import mesh_responses as fx

pytestmark = pytest.mark.unit


def _details_for(ident: str, via: str | None = None) -> dict:
    """SPARQL batch fixture restricted to one record (optionally tagged with a term ID)."""
    out = copy.deepcopy(fx.SPARQL_DETAILS)
    rows = [r for r in out["results"]["bindings"] if r["d"]["value"].endswith(ident)]
    if via:
        for r in rows:
            r["via"] = {"type": "literal", "value": via}
    out["results"]["bindings"] = rows
    return out


def _router(lookups=None, details=None, rels=None):
    """Build a ``_make_request`` replacement routing by URL / query text."""
    lookups = lookups or {}

    async def fake(url, params=None, headers=None, json_data=None):
        if "/lookup/" in url:
            kind = url.rsplit("/", 1)[-1]
            return lookups.get((kind, params["match"]), [])
        query = params["query"]
        if "broaderDescriptor" in query and "SELECT ?kind ?r ?l" in query:
            return rels if rels is not None else {"results": {"bindings": []}}
        return details if details is not None else {"results": {"bindings": []}}

    return fake


@pytest.fixture
def adapter(lookup_config):
    return MeSHAdapter(lookup_config)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.MESH
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("MESH:D003920", "D003920"),
            ("MeSH:D003920", "D003920"),
            ("mesh:d003920", "D003920"),
            ("D003920", "D003920"),
            ("  C000657245 ", "C000657245"),
            ("http://id.nlm.nih.gov/mesh/Q000175", "Q000175"),
            ("MESH:T046399", None),
            ("HP:0012378", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert MeSHAdapter.normalize_id(raw) == expected


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_exact_label(self, adapter):
        lookups = {
            ("descriptor", "exact"): fx.LOOKUP_DESCRIPTOR_EXACT,
            ("descriptor", "contains"): [],
            ("term", "contains"): [],
        }
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=_router(lookups, _details_for("D015673"))),
        ):
            res = await adapter.search_concepts("Fatigue Syndrome, Chronic", limit=5)
        assert [c.primary_id for c in res] == ["D015673"]
        c = res[0]
        assert c.primary_label == "Fatigue Syndrome, Chronic"
        assert c.concept_type == ConceptType.DISEASE
        assert "Myalgic Encephalomyelitis" in c.synonyms
        assert "Fatigue Syndrome, Chronic" not in c.synonyms
        assert c.definitions and c.definitions[0].startswith("A syndrome characterized")
        data = c.source_data[KnowledgeSource.MESH]
        assert "C10.668.364" in data["tree_numbers"]
        assert data["record_type"] == "TopicalDescriptor"
        assert c.identifiers[0].url.endswith("D015673")

    @pytest.mark.asyncio
    async def test_search_entry_term_resolves_to_descriptor(self, adapter):
        lookups = {
            ("descriptor", "exact"): [],
            ("descriptor", "contains"): [],
            ("term", "contains"): fx.LOOKUP_TERM_LONG_COVID,
        }
        details = _details_for("D000094024", via="T001119073")
        with patch.object(
            adapter, "_make_request", new=AsyncMock(side_effect=_router(lookups, details))
        ) as mock:
            res = await adapter.search_concepts("long covid", limit=5)
        assert [c.primary_id for c in res] == ["D000094024"]
        assert "Post-COVID Conditions" in res[0].synonyms
        # Term IDs are resolved server-side in the batched SPARQL query.
        sparql_query = mock.call_args_list[-1].kwargs["params"]["query"]
        assert "mesh:T001119073" in sparql_query

    @pytest.mark.asyncio
    async def test_search_ranks_exact_before_substring_and_respects_limit(self, adapter):
        lookups = {
            ("descriptor", "exact"): [],
            ("descriptor", "contains"): [
                {
                    "resource": "http://id.nlm.nih.gov/mesh/D015673",
                    "label": "Fatigue Syndrome, Chronic",
                },
                {"resource": "http://id.nlm.nih.gov/mesh/D001305", "label": "Auditory Fatigue"},
                {"resource": "http://id.nlm.nih.gov/mesh/D005221", "label": "Fatigue"},
            ],
            ("term", "contains"): [],
        }
        both = _details_for("D015673")
        both["results"]["bindings"] += _details_for("D005221")["results"]["bindings"]
        # Fixture has no D005221 rows; fabricate a minimal one so ranking is observable.
        both["results"]["bindings"] += [
            {
                "d": {"value": "http://id.nlm.nih.gov/mesh/D005221"},
                "kind": {"value": "label"},
                "v": {"value": "Fatigue"},
            },
            {
                "d": {"value": "http://id.nlm.nih.gov/mesh/D001305"},
                "kind": {"value": "label"},
                "v": {"value": "Auditory Fatigue"},
            },
        ]
        with patch.object(
            adapter, "_make_request", new=AsyncMock(side_effect=_router(lookups, both))
        ):
            res = await adapter.search_concepts("fatigue", limit=2)
        assert [c.primary_id for c in res] == ["D005221", "D015673"]  # exact, then prefix

    @pytest.mark.asyncio
    async def test_search_by_identifier_short_circuits(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=_router(details=_details_for("D015673"))),
        ) as mock:
            res = await adapter.search_concepts("MESH:D015673")
        assert [c.primary_id for c in res] == ["D015673"]
        assert mock.await_count == 1  # one SPARQL call, no REST look-ups

    @pytest.mark.asyncio
    async def test_search_empty_inputs_and_no_hits(self, adapter):
        assert await adapter.search_concepts("   ") == []
        assert await adapter.search_concepts("x", limit=0) == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=_router())):
            assert await adapter.search_concepts("zzzzqq") == []

    @pytest.mark.asyncio
    async def test_search_one_endpoint_failing_still_returns_others(self, adapter):
        calls = _router(
            {("descriptor", "exact"): fx.LOOKUP_DESCRIPTOR_EXACT}, _details_for("D015673")
        )

        async def flaky(url, params=None, headers=None, json_data=None):
            if url.endswith("/term"):
                raise RuntimeError("boom")
            return await calls(url, params, headers, json_data)

        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=flaky)):
            res = await adapter.search_concepts("Fatigue Syndrome, Chronic")
        assert [c.primary_id for c in res] == ["D015673"]

    @pytest.mark.asyncio
    async def test_search_all_failing_returns_empty(self, adapter):
        with patch.object(
            adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("down"))
        ):
            assert await adapter.search_concepts("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_descriptor(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=_router(details=_details_for("D015673"))),
        ):
            c = await adapter.get_concept_details("MeSH:D015673")
        assert c.primary_id == "D015673"
        assert c.categories == ["C"]
        assert c.source_data[KnowledgeSource.MESH]["active"] is True

    @pytest.mark.asyncio
    async def test_details_supplementary_concept_uses_note(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=_router(details=_details_for("C000657245"))),
        ):
            c = await adapter.get_concept_details("C000657245")
        assert c.concept_type == ConceptType.DISEASE  # SCR_Disease
        assert c.definitions[0].startswith("A viral disorder")
        assert c.source_data[KnowledgeSource.MESH]["active"] is False

    @pytest.mark.asyncio
    async def test_details_qualifier(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=_router(details=_details_for("Q000175"))),
        ):
            c = await adapter.get_concept_details("Q000175")
        assert c.primary_label == "diagnosis"
        assert c.concept_type == ConceptType.UNKNOWN

    @pytest.mark.asyncio
    async def test_details_invalid_missing_and_error(self, adapter):
        assert await adapter.get_concept_details("not-an-id") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=_router())):
            assert await adapter.get_concept_details("D999999999") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("D015673") is None

    def test_concept_type_rules(self):
        t = MeSHAdapter._concept_type
        base = {"types": ["TopicalDescriptor"], "trees": []}
        assert t("D1", {**base, "trees": ["C23.888.592.1"]}) == ConceptType.SYMPTOM
        assert t("D1", {**base, "trees": ["D12.776.1"]}) == ConceptType.PROTEIN
        assert t("D1", {**base, "trees": ["D02.1"]}) == ConceptType.CHEMICAL
        assert t("D1", {**base, "trees": ["A01.1"]}) == ConceptType.ANATOMICAL_ENTITY
        assert t("D1", {**base, "trees": ["B01.1"]}) == ConceptType.ORGANISM
        assert t("D1", {**base, "trees": ["E01.1"]}) == ConceptType.PROCEDURE
        assert t("D1", {**base, "trees": ["G01.1"]}) == ConceptType.BIOLOGICAL_PROCESS
        assert t("D1", {**base, "trees": ["Z01"]}) == ConceptType.UNKNOWN
        assert t("C1", {"types": ["SCR_Chemical"], "trees": []}) == ConceptType.CHEMICAL
        assert t("C1", {"types": ["SCR_Population"], "trees": []}) == ConceptType.UNKNOWN


class TestLookupDescriptor:
    @pytest.mark.asyncio
    async def test_exact_label_case_insensitive(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(return_value=fx.LOOKUP_DESCRIPTOR_EXACT),
        ) as mock:
            c = await adapter.lookup_descriptor("fatigue syndrome, chronic")
        assert c.primary_id == "D015673"
        assert c.primary_label == "Fatigue Syndrome, Chronic"
        assert mock.await_count == 1
        assert mock.call_args.kwargs["params"]["match"] == "exact"

    @pytest.mark.asyncio
    async def test_no_match_blank_and_error(self, adapter):
        assert await adapter.lookup_descriptor("") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=[])):
            assert await adapter.lookup_descriptor("nope") is None
        with patch.object(
            adapter, "_make_request", new=AsyncMock(return_value=fx.LOOKUP_DESCRIPTOR_EXACT)
        ):
            assert await adapter.lookup_descriptor("something else") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.lookup_descriptor("nope") is None


class TestRelationshipsAndMappings:
    @pytest.mark.asyncio
    async def test_relationships(self, adapter):
        with patch.object(
            adapter,
            "_make_request",
            new=AsyncMock(side_effect=_router(rels=fx.SPARQL_RELATIONSHIPS)),
        ):
            rels = await adapter.get_relationships("MESH:D005221")
        by_label: dict[str, list] = {}
        for r in rels:
            assert set(r) >= {"relation_label", "related_id", "related_name", "source"}
            by_label.setdefault(r["relation_label"], []).append(r)
        assert by_label["broader_than"][0]["related_id"] == "MESH:D012816"
        assert by_label["broader_than"][0]["related_name"] == "Signs and Symptoms"
        assert {r["related_name"] for r in by_label["narrower_than"]} >= {"Mental Fatigue"}
        assert by_label["allowed_qualifier"][0]["related_id"].startswith("MESH:Q")
        assert "see_also" in by_label

    @pytest.mark.asyncio
    async def test_relationships_limit_is_per_kind_and_dedups(self, adapter):
        doubled = copy.deepcopy(fx.SPARQL_RELATIONSHIPS)
        doubled["results"]["bindings"] += copy.deepcopy(doubled["results"]["bindings"])
        with patch.object(
            adapter, "_make_request", new=AsyncMock(side_effect=_router(rels=doubled))
        ):
            rels = await adapter.get_relationships("D005221", limit=1)
        labels = [r["relation_label"] for r in rels]
        assert len(labels) == len(set(labels))

    @pytest.mark.asyncio
    async def test_relationships_invalid_empty_and_error(self, adapter):
        assert await adapter.get_relationships("junk") == []
        assert await adapter.get_relationships("D005221", limit=0) == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("D005221") == []

    @pytest.mark.asyncio
    async def test_mappings_for_supplementary_concept(self, adapter):
        payload = {
            "results": {
                "bindings": [
                    {
                        "kind": {"value": "preferred_mapped_to"},
                        "r": {"value": "http://id.nlm.nih.gov/mesh/D018352"},
                    },
                    {
                        "kind": {"value": "preferred_mapped_to"},
                        "r": {"value": "http://id.nlm.nih.gov/mesh/D018352"},
                    },
                    {
                        "kind": {"value": "mapped_to"},
                        "r": {"value": "http://id.nlm.nih.gov/mesh/D011024"},
                    },
                ]
            }
        }
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=payload)):
            maps = await adapter.get_mappings("C000657245")
        assert [m["toId"] for m in maps] == ["MESH:D018352", "MESH:D011024"]
        assert maps[0]["fromId"] == "MESH:C000657245"
        assert maps[0]["confidence"] > maps[1]["confidence"]
        assert set(maps[0]) == {
            "fromId",
            "toId",
            "fromSource",
            "toSource",
            "mappingType",
            "confidence",
        }

    @pytest.mark.asyncio
    async def test_mappings_invalid_and_error(self, adapter):
        assert await adapter.get_mappings("zzz") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("D015673") == []
        with patch.object(
            adapter, "_make_request", new=AsyncMock(return_value=["not", "a", "dict"])
        ):
            assert await adapter.get_mappings("D015673") == []
