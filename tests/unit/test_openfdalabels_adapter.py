"""
Unit tests for OpenFDALabelsAdapter (HTTP mocked with trimmed real openFDA responses).
"""

import time
from unittest.mock import AsyncMock

import pytest

from knowledge_lookup.adapters.openfdalabels_adapter import (
    OPENFDA_LABEL_URL,
    OpenFDALabelsAdapter,
    _quote,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import openfdalabels_responses as fx

pytestmark = pytest.mark.unit

BUP = fx.BUPROPION_LABEL["set_id"]
ASP = fx.ASPIRIN_LABEL["set_id"]
COMBO = fx.COMBO_LABEL["set_id"]
BARE = fx.NO_OPENFDA_LABEL["set_id"]
_BY_SET_ID = {
    BUP: fx.BUPROPION_LABEL,
    ASP: fx.ASPIRIN_LABEL,
    COMBO: fx.COMBO_LABEL,
    BARE: fx.NO_OPENFDA_LABEL,
}


BUP_NAMES = (
    'openfda.generic_name:"bupropion" OR openfda.brand_name:"bupropion"'
    ' OR openfda.substance_name:"bupropion"'
)


class NotFound(Exception):
    """Stands in for aiohttp.ClientResponseError (the base class reads ``.status``)."""

    status = 404


def _router(overrides=None):
    """``_make_request`` replacement routing by the ``search`` expression."""
    overrides = overrides or {}

    async def fake(url, params=None, headers=None, json_data=None):
        assert url == OPENFDA_LABEL_URL
        search = params["search"]
        if search in overrides:
            value = overrides[search]
            if isinstance(value, Exception):
                raise value
            return value
        if search.startswith("set_id:"):
            set_id = search.split('"')[1]
            if set_id in _BY_SET_ID:
                return {"meta": {}, "results": [_BY_SET_ID[set_id]]}
            raise NotFound(set_id)
        if search.startswith("openfda.generic_name:"):
            term = search.split('"')[1]
            hits = {
                "bupropion": fx.SEARCH_BUPROPION,
                "aspirin": fx.SEARCH_ASPIRIN,
                "Advil Dual Action": fx.SEARCH_COMBO,
            }
            if term in hits:
                return hits[term]
            raise NotFound(term)
        if search == 'indications_and_usage:"fatigue"':
            return fx.SEARCH_FATIGUE
        raise NotFound(search)

    return AsyncMock(side_effect=fake)


@pytest.fixture
def adapter(lookup_config, monkeypatch):
    monkeypatch.delenv("OPENFDA_API_KEY", raising=False)
    a = OpenFDALabelsAdapter(lookup_config)
    a._last_request = float("-inf")
    return a


def _patch(adapter, router):
    adapter._make_request = router
    return router


def _searches(router):
    return [c.args[1]["search"] for c in router.call_args_list]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.OPENFDALABELS
        assert adapter.is_available() is True
        assert adapter.api_key is None

    def test_api_key_from_env(self, lookup_config, monkeypatch):
        monkeypatch.setenv("OPENFDA_API_KEY", "test-key")
        assert OpenFDALabelsAdapter(lookup_config).api_key == "test-key"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (ASP, ASP),
            (ASP.upper(), ASP),
            (f" DailyMed:{ASP} ", ASP),
            (f"setid : {ASP}", ASP),
            ("aspirin", None),
            ("0058175f", None),
            (f'{ASP}" OR x', None),
            ("", None),
            (None, None),
            (5, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert OpenFDALabelsAdapter.normalize_id(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("boxed_warning", "boxed_warning"),
            ("Boxed Warning", "boxed_warning"),
            ("boxed", "boxed_warning"),
            ("black-box", "boxed_warning"),
            ("unknown section", "unknown_section"),  # unknown names are passed through
            ("indications", "indications_and_usage"),
            ("dosage", "dosage_and_administration"),
            ("interactions", "drug_interactions"),
            ("side effects", "adverse_reactions"),
            ("set_id", None),
            ("openfda", None),
            ("x; DROP", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_section(self, raw, expected):
        assert OpenFDALabelsAdapter.normalize_section(raw) == expected

    def test_quote_strips_query_syntax_breakers(self):
        assert _quote('asp"irin\\') == "asp irin"


@pytest.mark.asyncio
class TestSearch:
    async def test_name_search(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("aspirin", limit=5)
        assert [c.primary_id for c in result] == [ASP]
        c = result[0]
        assert c.primary_label == "Low Dose Aspirin"
        assert c.concept_type == ConceptType.DRUG
        assert "ASPIRIN" in c.synonyms
        assert "HUMAN OTC DRUG" in c.categories and "route:ORAL" in c.categories
        assert "drug label" in c.semantic_types
        assert c.sources == [KnowledgeSource.OPENFDALABELS]
        search = router.call_args_list[0].args[1]["search"]
        assert search == (
            'openfda.generic_name:"aspirin" OR openfda.brand_name:"aspirin"'
            ' OR openfda.substance_name:"aspirin"'
        )
        assert router.call_args_list[0].args[1]["limit"] == 5
        assert "api_key" not in router.call_args_list[0].args[1]

    async def test_api_key_is_sent_when_configured(self, adapter):
        adapter.api_key = "test-key"
        router = _patch(adapter, _router())
        await adapter.search_concepts("aspirin")
        assert router.call_args_list[0].args[1]["api_key"] == "test-key"

    async def test_indication_text_fallback(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("fatigue")
        assert [c.primary_id for c in result] == [BARE, ASP]
        assert len(_searches(router)) == 2
        assert _searches(router)[1] == 'indications_and_usage:"fatigue"'

    async def test_label_without_openfda_names_uses_product_text(self, adapter):
        _patch(adapter, _router())
        c = (await adapter.search_concepts("fatigue"))[0]
        assert c.primary_label.startswith("Citalopram Hydrobromide")
        assert len(c.primary_label) <= 60
        assert c.synonyms == [] and c.categories == ["boxed warning"]

    async def test_short_product_text_is_kept_whole(self, adapter):
        label = {"set_id": BUP, "spl_product_data_elements": ["Tiny Drug"]}
        _patch(adapter, _router({f'set_id:"{BUP}"': {"results": [label]}}))
        assert (await adapter.get_concept_details(BUP)).primary_label == "Tiny Drug"

    async def test_label_without_any_name_falls_back_to_set_id(self, adapter):
        _patch(adapter, _router({f'set_id:"{BUP}"': {"results": [{"id": "x", "set_id": BUP}]}}))
        c = await adapter.get_concept_details(BUP)
        assert c.primary_label == BUP and c.definitions == []

    async def test_set_id_query_returns_the_label(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts(f"DAILYMED:{BUP}")
        assert [c.primary_id for c in result] == [BUP]
        assert _searches(router) == [f'set_id:"{BUP}"']

    async def test_unknown_set_id_query(self, adapter):
        _patch(adapter, _router())
        assert await adapter.search_concepts("11111111-2222-3333-4444-555555555555") == []

    async def test_no_match_returns_empty(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.search_concepts("zzzzqq") == []
        assert len(_searches(router)) == 2

    async def test_query_cannot_inject_search_syntax(self, adapter):
        router = _patch(adapter, _router())
        await adapter.search_concepts('aspirin" OR set_id:"x')
        assert '"aspirin  OR set_id: x"' in _searches(router)[0]

    async def test_limit_and_hit_cap(self, adapter):
        both = {"results": fx.SEARCH_BUPROPION["results"] * 3}
        router = _patch(adapter, _router({BUP_NAMES: both}))
        assert len(await adapter.search_concepts("bupropion", limit=5)) == 1  # duplicates merged
        assert router.call_args_list[0].args[1]["limit"] == 5
        await adapter.search_concepts("bupropion", limit=5000)
        assert router.call_args_list[1].args[1]["limit"] == 100  # one call never pulls 5000 labels
        assert await adapter.search_concepts("bupropion", limit=0) == []

    async def test_limit_truncates_results(self, adapter):
        second = dict(fx.BUPROPION_LABEL, set_id="aaaaaaaa-0000-0000-0000-000000000000")
        both = {"results": [fx.BUPROPION_LABEL, second]}
        _patch(adapter, _router({BUP_NAMES: both}))
        assert len(await adapter.search_concepts("bupropion", limit=10)) == 2
        assert len(await adapter.search_concepts("bupropion", limit=1)) == 1

    async def test_blank_query(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts("") == []
        router.assert_not_called()

    async def test_error_returns_empty(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.search_concepts("aspirin") == []

    async def test_unexpected_shapes(self, adapter):
        _patch(adapter, AsyncMock(return_value=["unexpected"]))
        assert await adapter.search_concepts("aspirin") == []
        _patch(adapter, AsyncMock(return_value={"results": "oops"}))
        assert await adapter.search_concepts("aspirin") == []
        _patch(adapter, AsyncMock(return_value=fx.SEARCH_NOT_FOUND_BODY))
        assert await adapter.search_concepts("aspirin") == []
        _patch(adapter, AsyncMock(return_value={"results": ["x", {"set_id": BUP}]}))
        assert [c.primary_id for c in await adapter.search_concepts("aspirin")] == [BUP]


@pytest.mark.asyncio
class TestDetails:
    async def test_prescription_label(self, adapter):
        router = _patch(adapter, _router())
        c = await adapter.get_concept_details(BUP)
        assert c.primary_id == BUP
        assert c.primary_label == "buPropion Hydrochloride XL"
        assert "HUMAN PRESCRIPTION DRUG" in c.categories and "boxed warning" in c.categories
        assert "BUPROPION HYDROCHLORIDE" in c.synonyms
        assert c.definitions and len(c.definitions[0]) <= 500
        assert c.identifiers[0].url.endswith(f"setid={BUP}")
        assert _searches(router) == [f'set_id:"{BUP}"']
        data = c.source_data[KnowledgeSource.OPENFDALABELS]
        assert data["set_id"] == BUP and data["version"] and data["effective_time"]
        assert data["openfda"]["unii"] == ["ZG7E5POY8O"]
        assert "boxed_warning" in data["sections"] and "adverse_reactions" in data["sections"]
        # sections are trimmed in the concept, flagged, and still discoverable
        assert all(len(t) <= 1500 for t in data["sections"].values())
        assert "adverse_reactions" in data["sections_truncated"]
        assert "boxed_warning" not in data["sections_truncated"]
        assert "adverse_reactions" in data["section_names"]
        assert "set_id" not in data["section_names"]
        assert "spl_product_data_elements" not in data["section_names"]

    async def test_missing_label(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_concept_details("11111111-2222-3333-4444-555555555555") is None

    async def test_invalid_id_makes_no_request(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_concept_details("aspirin") is None
        router.assert_not_called()

    async def test_error(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_concept_details(BUP) is None


@pytest.mark.asyncio
class TestRelationships:
    async def test_single_ingredient_label(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships(BUP)
        ing = [r for r in rels if r["relation_label"] == "has_ingredient"]
        assert [(r["related_id"], r["unii"], r["label_uniis"]) for r in ing] == [
            ("BUPROPION HYDROCHLORIDE", "ZG7E5POY8O", ["ZG7E5POY8O"])
        ]
        assert {r["related_id"] for r in rels if r["relation_label"] == "has_rxnorm_product"} == {
            "993541",
            "993557",
        }
        for r in rels:
            assert set(r) >= {"relation_label", "related_id", "related_name", "source"}
            assert r["source"] == "openFDA"

    async def test_unii_is_not_paired_for_combination_products(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships(COMBO)
        ing = [r for r in rels if r["relation_label"] == "has_ingredient"]
        assert {r["related_id"] for r in ing} == {"IBUPROFEN", "ACETAMINOPHEN"}
        assert all(r["unii"] is None for r in ing)  # lists are not index-aligned
        assert all(sorted(r["label_uniis"]) == ["362O9ITL9D", "WK2XYI10QM"] for r in ing)

    async def test_pharm_classes(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships(ASP)
        classes = {r["related_id"]: r for r in rels if r["relation_label"] == "has_pharm_class"}
        moa = classes["Cyclooxygenase Inhibitors [MoA]"]
        assert moa["class_type"] == "MoA" and moa["related_name"] == "Cyclooxygenase Inhibitors"
        assert classes["Nonsteroidal Anti-inflammatory Drug [EPC]"]["class_type"] == "EPC"
        assert {c["class_type"] for c in classes.values()} == {"EPC", "MoA", "PE", "CS"}

    async def test_limit_caps_each_label(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships(ASP, limit=1)
        counts: dict[str, int] = {}
        for r in rels:
            counts[r["relation_label"]] = counts.get(r["relation_label"], 0) + 1
        assert counts == {"has_ingredient": 1, "has_pharm_class": 1, "has_rxnorm_product": 1}

    async def test_label_without_openfda_has_no_relationships(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_relationships(BARE) == []

    async def test_unknown_invalid_and_error(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_relationships("11111111-2222-3333-4444-555555555555") == []
        assert await adapter.get_relationships("aspirin") == []
        assert await adapter.get_relationships(ASP, limit=0) == []
        assert router.call_count == 1
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_relationships(ASP) == []


@pytest.mark.asyncio
class TestMappings:
    async def test_mappings(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings(BUP)
        got = {(m["toSource"], m["toId"]) for m in maps}
        assert ("RxNorm", "993541") in got and ("RxNorm", "993557") in got
        assert ("UNII", "ZG7E5POY8O") in got
        assert ("FDA_APPLICATION", "ANDA211200") in got
        assert ("DailyMed", f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={BUP}") in got
        assert any(s == "NDC" for s, _ in got)
        for m in maps:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == BUP and m["fromSource"] == "SPL"
        assert len(got) == len(maps)
        types = {m["mappingType"] for m in maps if m["toSource"] == "NDC"}
        assert types <= {"product_ndc", "package_ndc"}

    async def test_package_ndcs_are_capped(self, adapter):
        label = dict(fx.ASPIRIN_LABEL)
        label["openfda"] = dict(label["openfda"], package_ndc=[f"1-1-{i}" for i in range(100)])
        _patch(adapter, _router({f'set_id:"{ASP}"': {"results": [label]}}))
        maps = await adapter.get_mappings(ASP)
        assert len([m for m in maps if m["mappingType"] == "package_ndc"]) == 25

    async def test_label_without_openfda_still_maps_to_dailymed(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings(BARE)
        assert [(m["toSource"], m["mappingType"]) for m in maps] == [("DailyMed", "url")]

    async def test_unknown_invalid_and_error(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_mappings("11111111-2222-3333-4444-555555555555") == []
        assert await adapter.get_mappings("aspirin") == []
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_mappings(ASP) == []


@pytest.mark.asyncio
class TestLabelSection:
    async def test_full_text_is_not_trimmed(self, adapter):
        _patch(adapter, _router())
        text = await adapter.get_label_section(BUP, "adverse_reactions")
        assert text == "\n\n".join(fx.BUPROPION_LABEL["adverse_reactions"])
        assert len(text) > 1500  # the concept holds only the first 1500 characters

    async def test_aliases_and_case(self, adapter):
        _patch(adapter, _router())
        boxed = await adapter.get_label_section(f"DAILYMED:{BUP.upper()}", "Boxed Warning")
        assert boxed.startswith("WARNING: SUICIDAL THOUGHTS")
        assert await adapter.get_label_section(BUP, "boxed") == boxed
        assert "INDICATIONS" in await adapter.get_label_section(BUP, "indications")

    async def test_string_valued_section(self, adapter):
        label = dict(fx.BUPROPION_LABEL, boxed_warning="plain text")
        _patch(adapter, _router({f'set_id:"{BUP}"': {"results": [label]}}))
        assert await adapter.get_label_section(BUP, "boxed_warning") == "plain text"

    async def test_missing_section_label_or_bad_input(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_label_section(ASP, "boxed_warning") is None  # OTC: no boxed
        assert (
            await adapter.get_label_section("11111111-2222-3333-4444-555555555555", "warnings")
            is None
        )
        calls = router.call_count
        assert await adapter.get_label_section("aspirin", "warnings") is None
        assert await adapter.get_label_section(BUP, "set_id") is None
        assert await adapter.get_label_section(BUP, "bad name!") is None
        assert router.call_count == calls

    async def test_error(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_label_section(BUP, "warnings") is None


@pytest.mark.asyncio
class TestThrottle:
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        monkeypatch.setattr(
            "knowledge_lookup.adapters.openfdalabels_adapter.asyncio.sleep", fake_sleep
        )
        _patch(adapter, _router())
        adapter._last_request = time.monotonic()
        await adapter._search(f'set_id:"{ASP}"', 1)
        assert sleeps and 0 < sleeps[0] <= 0.3

    async def test_not_found_is_empty_other_errors_propagate(self, adapter):
        _patch(adapter, AsyncMock(side_effect=NotFound("x")))
        assert await adapter._search("x", 1) == []
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        with pytest.raises(RuntimeError):
            await adapter._search("x", 1)
