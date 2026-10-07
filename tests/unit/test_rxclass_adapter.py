"""
Unit tests for RxClassAdapter (HTTP mocked with trimmed real responses).
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.rxclass_adapter import RxClassAdapter, _parent_code, atc_level
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import rxclass_responses as fx

pytestmark = pytest.mark.unit


def _router(overrides=None):
    """``_make_request`` replacement routing by URL path (real fixtures by default)."""
    overrides = overrides or {}

    async def fake(url, params=None, headers=None, json_data=None):
        path = url.split("/REST/", 1)[1]
        params = params or {}
        assert path.endswith(".json"), "RxNav answers XML unless the path ends in .json"
        if path in overrides:
            value = overrides[path]
            if isinstance(value, Exception):
                raise value
            return value
        if path == "rxclass/allClasses.json":
            return fx.ALL_CLASSES
        if path == "rxclass/class/byDrugName.json":
            return fx.BY_DRUGNAME_ADVIL if params["drugName"].lower() == "advil" else fx.EMPTY
        if path == "rxclass/class/byRxcui.json":
            return fx.BY_RXCUI_ASPIRIN if params["rxcui"] == "1191" else fx.EMPTY
        if path == "rxclass/classMembers.json":
            return fx.CLASS_MEMBERS_N02BA if params["classId"] == "N02BA" else fx.EMPTY
        if path == "rxcui/1191/properties.json":
            return fx.PROPERTIES_ASPIRIN
        if path == "rxcui.json":
            return fx.RXCUI_IBUPROFEN if params["name"] == "ibuprofen" else fx.EMPTY
        if path == "approximateTerm.json":
            return {
                "fluoxetin": fx.APPROXIMATE_FLUOXETIN,
                "asprin": fx.APPROXIMATE_ASPRIN_WEAK,
            }.get(params["term"], fx.EMPTY)
        return fx.EMPTY

    return AsyncMock(side_effect=fake)


@pytest.fixture
def adapter(lookup_config):
    a = RxClassAdapter(lookup_config)
    a._last_request = float("-inf")
    return a


class TestHelpers:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.RXCLASS
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1191", ("rxcui", "1191")),
            ("RXCUI:1191", ("rxcui", "1191")),
            ("RxNorm: 1191", ("rxcui", "1191")),
            ("N02BA", ("atc", "N02BA")),
            ("atc:n02ba01", ("atc", "N02BA01")),
            ("N", ("atc", "N")),
            ("aspirin", None),
            ("N02BA0", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert RxClassAdapter.parse_id(raw) == expected

    def test_levels_and_parents(self):
        assert [atc_level(c) for c in ("N", "N02", "N02B", "N02BA", "N02BA01", "x1")] == [
            1,
            2,
            3,
            4,
            5,
            None,
        ]
        assert _parent_code("N02BA01") == "N02BA"
        assert _parent_code("N02BA") == "N02B"
        assert _parent_code("N02B") == "N02"
        assert _parent_code("N02") == "N"
        assert _parent_code("N") is None
        assert _parent_code("bad") is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_drug_name_search_returns_drug_with_atc(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            res = await adapter.search_concepts("Advil", limit=5)
        drug = res[0]
        assert drug.primary_id == "5640"
        assert drug.primary_label == "ibuprofen"
        assert drug.concept_type == ConceptType.DRUG
        assert "ATC M01AE" in drug.categories
        data = drug.source_data[KnowledgeSource.RXCLASS]
        assert data["kind"] == "drug" and data["tty"] == "IN"
        assert {c["id"] for c in data["atc_classes"]} >= {"M01AE", "C01EB"}

    @pytest.mark.asyncio
    async def test_class_name_search_exact_first(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            res = await adapter.search_concepts("analgesics", limit=10)
        assert res[0].primary_id == "N02"
        assert res[0].source_data[KnowledgeSource.RXCLASS]["atc_level"] == 2
        assert all(c.concept_type == ConceptType.DRUG for c in res)
        assert {"S02DA", "A03D"} <= {c.primary_id for c in res}  # substring matches

    @pytest.mark.asyncio
    async def test_search_limit(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            assert len(await adapter.search_concepts("analgesics", limit=2)) == 2
            assert await adapter.search_concepts("analgesics", limit=0) == []

    @pytest.mark.asyncio
    async def test_search_by_atc_code(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()) as mock:
            res = await adapter.search_concepts("N02BA")
        assert [c.primary_id for c in res] == ["N02BA"]
        assert res[0].parents == ["OTHER ANALGESICS AND ANTIPYRETICS"]
        assert mock.await_count == 1  # only allClasses; no drug lookup for a code

    @pytest.mark.asyncio
    async def test_search_by_level5_code_returns_drug(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            res = await adapter.search_concepts("n02ba01")
        assert [(c.primary_id, c.primary_label) for c in res] == [("1191", "aspirin")]
        assert res[0].source_data[KnowledgeSource.RXCLASS]["atc_code"] == "N02BA01"

    @pytest.mark.asyncio
    async def test_search_by_rxcui(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            res = await adapter.search_concepts("1191")
        assert res[0].primary_label == "aspirin"

    @pytest.mark.asyncio
    async def test_approximate_fallback_accepts_confident_match(self, adapter):
        overrides = {
            "rxcui/4493/properties.json": {
                "properties": {"rxcui": "4493", "name": "fluoxetine", "tty": "IN", "synonym": ""}
            }
        }
        with patch.object(adapter, "_make_request", new=_router(overrides)):
            res = await adapter.search_concepts("fluoxetin")
        assert [(c.primary_id, c.primary_label) for c in res] == [("4493", "fluoxetine")]
        assert res[0].categories == []  # no ATC rows in this mocked answer

    @pytest.mark.asyncio
    async def test_approximate_fallback_rejects_weak_match(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            assert await adapter.search_concepts("asprin") == []

    @pytest.mark.asyncio
    async def test_approximate_fallback_skips_garbage_scores(self, adapter):
        bad = {"approximateGroup": {"candidate": [{"rxcui": "1", "score": "n/a"}]}}
        with patch.object(adapter, "_make_request", new=_router({"approximateTerm.json": bad})):
            assert await adapter.search_concepts("qwerty") == []

    @pytest.mark.asyncio
    async def test_search_empty_and_errors(self, adapter):
        assert await adapter.search_concepts("  ") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("aspirin") == []

    @pytest.mark.asyncio
    async def test_search_survives_one_failed_branch(self, adapter):
        overrides = {"rxclass/class/byDrugName.json": RuntimeError("boom")}
        with patch.object(adapter, "_make_request", new=_router(overrides)):
            res = await adapter.search_concepts("analgesics")
        assert res and res[0].primary_id == "N02"


class TestDetails:
    @pytest.mark.asyncio
    async def test_drug_details(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            c = await adapter.get_concept_details("RXCUI:1191")
        assert c.primary_id == "1191" and c.primary_label == "aspirin"
        classes = c.source_data[KnowledgeSource.RXCLASS]["atc_classes"]
        # The aspirin / codeine combination row (N02AJ) belongs to another RxCUI.
        assert [x["id"] for x in classes] == ["A01AD", "B01AC", "N02BA"]

    @pytest.mark.asyncio
    async def test_class_details_hierarchy_from_class_list(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            c = await adapter.get_concept_details("ATC:N02B")
        assert c.primary_label == "OTHER ANALGESICS AND ANTIPYRETICS"
        assert c.parents == ["ANALGESICS"]
        assert "Salicylic acid and derivatives" in c.children
        assert c.categories == ["ATC level 3"]
        assert c.source_data[KnowledgeSource.RXCLASS]["parent_id"] == "N02"

    @pytest.mark.asyncio
    async def test_class_details_top_level_has_no_parent(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            c = await adapter.get_concept_details("N")
        assert c.parents == []
        assert "parent_id" not in c.source_data[KnowledgeSource.RXCLASS]
        assert "ANALGESICS" in c.children

    @pytest.mark.asyncio
    async def test_details_missing_invalid_and_error(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            assert await adapter.get_concept_details("99999999") is None  # unknown RxCUI
            assert await adapter.get_concept_details("Z99ZZ") is None  # unknown class
            assert await adapter.get_concept_details("N02BA99") is None  # unknown level 5
        assert await adapter.get_concept_details("not an id!") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("1191") is None

    @pytest.mark.asyncio
    async def test_all_classes_cached_and_empty_not_cached(self, adapter):
        mock = _router()
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.get_concept_details("N02")
            await adapter.get_concept_details("N02B")
        assert mock.await_count == 1
        fresh = RxClassAdapter(adapter.config)
        failing = _router({"rxclass/allClasses.json": {}})
        with patch.object(fresh, "_make_request", new=failing):
            assert await fresh.get_concept_details("N02") is None
            await fresh.get_concept_details("N02")
        assert failing.await_count == 2


class TestRelationships:
    @pytest.mark.asyncio
    async def test_drug_has_atc_class(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            rels = await adapter.get_relationships("1191")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [
            ("has_atc_class", "A01AD"),
            ("has_atc_class", "B01AC"),
            ("has_atc_class", "N02BA"),
        ]
        assert set(rels[0]) >= {"relation_label", "related_id", "related_name", "source"}
        assert rels[0]["atc_level"] == 4

    @pytest.mark.asyncio
    async def test_class_parent_children_members(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            rels = await adapter.get_relationships("N02B")
            assert {r["relation_label"] for r in rels} == {"has_parent", "has_child"}
            rels = await adapter.get_relationships("N02BA", limit=3)
        labels = [r["relation_label"] for r in rels]
        assert labels[0] == "has_parent" and labels.count("has_member") == 3
        member = next(r for r in rels if r["relation_label"] == "has_member")
        assert (member["related_id"], member["related_name"], member["atc_code"]) == (
            "1191",
            "aspirin",
            "N02BA01",
        )

    @pytest.mark.asyncio
    async def test_higher_level_members_use_ingredient_filter(self, adapter):
        mock = _router()
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.get_relationships("N02")
        params = [c.args[1] for c in mock.call_args_list if "classMembers" in c.args[0]][0]
        assert params["ttys"] == "IN"

    @pytest.mark.asyncio
    async def test_relationships_edge_cases(self, adapter):
        assert await adapter.get_relationships("garbage!") == []
        assert await adapter.get_relationships("1191", limit=0) == []
        with patch.object(adapter, "_make_request", new=_router()):
            assert await adapter.get_relationships("N02BA01") == []  # level 5: not a class
            assert await adapter.get_relationships("Z99ZZ") == []
            assert await adapter.get_relationships("99999999") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("N02BA") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_rxcui_to_atc(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            maps = await adapter.get_mappings("1191")
        by_type: dict[str, list[str]] = {}
        for m in maps:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            by_type.setdefault(m["mappingType"], []).append(m["toId"])
        assert by_type["atc_class"] == ["A01AD", "B01AC", "N02BA"]
        # Only N02BA is in the mocked classMembers, so just one level 5 code is found.
        assert by_type["atc5"] == ["N02BA01"]

    @pytest.mark.asyncio
    async def test_umls_cui_included_when_present(self, adapter):
        props = {
            "properties": {"rxcui": "1191", "name": "aspirin", "tty": "IN", "umlscui": "C0004057"}
        }
        with patch.object(
            adapter, "_make_request", new=_router({"rxcui/1191/properties.json": props})
        ):
            maps = await adapter.get_mappings("1191")
        assert (maps[-1]["toId"], maps[-1]["toSource"]) == ("C0004057", "UMLS")

    @pytest.mark.asyncio
    async def test_level5_code_to_rxcui(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            maps = await adapter.get_mappings("ATC:N02BA01")
            assert maps == [
                {
                    "fromId": "N02BA01",
                    "toId": "1191",
                    "fromSource": "ATC",
                    "toSource": "RxNorm",
                    "mappingType": "atc5_to_rxcui",
                    "confidence": 1.0,
                }
            ]
            assert await adapter.get_mappings("N02BA99") == []
            assert await adapter.get_mappings("N02BA") == []
            assert await adapter.get_mappings("99999999") == []
        assert await adapter.get_mappings("nope!") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("1191") == []


class TestHelpersApi:
    @pytest.mark.asyncio
    async def test_lookup_rxcui(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            assert await adapter.lookup_rxcui("ibuprofen") == "5640"
            assert await adapter.lookup_rxcui("") is None
            assert await adapter.lookup_rxcui("zzzqqq") is None
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.lookup_rxcui("ibuprofen") is None

    @pytest.mark.asyncio
    async def test_lookup_rxcui_falls_back_to_approximate(self, adapter):
        overrides = {
            "rxcui/4493/properties.json": {
                "properties": {"rxcui": "4493", "name": "fluoxetine", "tty": "IN"}
            }
        }
        with patch.object(adapter, "_make_request", new=_router(overrides)):
            assert await adapter.lookup_rxcui("fluoxetin") == "4493"

    @pytest.mark.asyncio
    async def test_get_atc_for_drug(self, adapter):
        with patch.object(adapter, "_make_request", new=_router()):
            out = await adapter.get_atc_for_drug("Advil")
            assert out[0]["rxcui"] == "5640"
            assert "M01AE" in {c["id"] for c in out[0]["atc_classes"]}
            assert await adapter.get_atc_for_drug("") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_atc_for_drug("Advil") == []

    @pytest.mark.asyncio
    async def test_non_dict_response_is_treated_as_empty(self, adapter):
        with patch.object(adapter, "_make_request", new=AsyncMock(return_value=["x"])):
            assert await adapter.get_atc_for_drug("aspirin") == []
