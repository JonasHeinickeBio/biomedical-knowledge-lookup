"""
Unit tests for RxNormAdapter (HTTP mocked with trimmed real RxNav responses).
"""

from unittest.mock import AsyncMock

import pytest

from knowledge_lookup.adapters.rxnorm_adapter import RxNormAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import rxnorm_responses as fx

pytestmark = pytest.mark.unit

_PROPERTIES = {
    "1191": fx.PROPERTIES_ASPIRIN,
    "153010": fx.PROPERTIES_ADVIL,
    "243670": fx.PROPERTIES_ASPIRIN_81,
    "153008": fx.PROPERTIES_ADVIL_TABLET,
    "317541": fx.PROPERTIES_ORAL_TABLET,
    "314293": fx.PROPERTIES_PIN,
    "4493": fx.PROPERTIES_FLUOXETINE,
    "316074": fx.PROPERTIES_SCDC,
}
_RELATED = {
    "1191": fx.RELATED_ASPIRIN,
    "153010": fx.RELATED_ADVIL,
    "243670": fx.RELATED_ASPIRIN_81,
    "314293": fx.RELATED_ADVIL,  # PIN -> IN only: a group with an unmapped tty is ignored
}


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
        if path == "rxcui.json":
            return {"aspirin": fx.EXACT_ASPIRIN, "Advil": fx.EXACT_ADVIL}.get(
                params["name"], fx.EXACT_NONE
            )
        if path == "drugs.json":
            return fx.DRUGS_ASPIRIN if params["name"] == "aspirin 81" else fx.DRUGS_NONE
        if path == "approximateTerm.json":
            return {"fluoxetin": fx.APPROX_FLUOXETIN, "chronic fatigue": fx.APPROX_WEAK}.get(
                params["term"], fx.APPROX_EMPTY
            )
        parts = path.split("/")
        if parts[0] == "rxcui" and len(parts) == 3:
            rxcui, leaf = parts[1], parts[2]
            if leaf == "properties.json":
                return (
                    {"properties": _PROPERTIES[rxcui]["properties"]}
                    if rxcui in _PROPERTIES
                    else {}
                )
            if leaf == "related.json":
                return _RELATED.get(rxcui, fx.RELATED_EMPTY)
            if leaf == "allProperties.json":
                assert params == {"prop": "codes"}
                return fx.CODES_ASPIRIN if rxcui in ("1191", "243670") else fx.CODES_EMPTY
            if leaf == "ndcs.json":
                return fx.NDCS_ASPIRIN_81 if rxcui == "243670" else fx.NDCS_EMPTY
        return {}

    return AsyncMock(side_effect=fake)


@pytest.fixture
def adapter(lookup_config):
    a = RxNormAdapter(lookup_config)
    a._last_request = float("-inf")
    return a


def _patch(adapter, router):
    adapter._make_request = router
    return router


class TestBasics:
    def test_source_availability_timeout(self, adapter):
        assert adapter.get_source() == KnowledgeSource.RXNORM
        assert adapter.is_available() is True
        assert adapter.min_request_timeout >= 30.0

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1191", "1191"),
            (" 1191 ", "1191"),
            ("RXCUI:1191", "1191"),
            ("rxnorm : 1191", "1191"),
            ("aspirin", None),
            ("", None),
            ("1191x", None),
            (None, None),
            (1191, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert RxNormAdapter.normalize_id(raw) == expected


@pytest.mark.asyncio
class TestSearch:
    async def test_exact_name(self, adapter):
        router = _patch(adapter, _router())
        result = await adapter.search_concepts("aspirin")
        assert [c.primary_id for c in result] == ["1191"]
        c = result[0]
        assert c.primary_label == "aspirin"
        assert c.concept_type == ConceptType.DRUG
        assert "tty:IN" in c.categories
        assert "ingredient" in c.semantic_types
        assert c.confidence_score == 0.95
        assert c.source_data[KnowledgeSource.RXNORM]["tty"] == "IN"
        # exact hits must not trigger the broader searches
        urls = [call.args[0] for call in router.call_args_list]
        assert not any(u.endswith("drugs.json") for u in urls)
        first_params = router.call_args_list[0].args[1]
        assert first_params == {"name": "aspirin", "search": 2}

    async def test_brand_name(self, adapter):
        _patch(adapter, _router())
        result = await adapter.search_concepts("Advil")
        assert [(c.primary_id, c.categories) for c in result] == [("153010", ["tty:BN"])]

    async def test_rxcui_query_returns_details(self, adapter):
        _patch(adapter, _router())
        result = await adapter.search_concepts("RxNorm:243670")
        assert [c.primary_id for c in result] == ["243670"]
        assert result[0].synonyms == ["ASA 81 MG Oral Tablet"]

    async def test_unknown_rxcui_query(self, adapter):
        _patch(adapter, _router())
        assert await adapter.search_concepts("999999999") == []

    async def test_contains_search_sorted_by_term_type(self, adapter):
        _patch(adapter, _router())
        result = await adapter.search_concepts("aspirin 81")
        ttys = [c.source_data[KnowledgeSource.RXNORM]["tty"] for c in result]
        ranks = ["IN", "BN", "SCD", "SBD", "BPCK"]
        assert ttys == sorted(ttys, key=ranks.index)
        assert all(c.confidence_score == 0.7 for c in result)

    async def test_contains_search_respects_limit(self, adapter):
        _patch(adapter, _router())
        full = await adapter.search_concepts("aspirin 81", limit=50)
        assert len(full) > 2
        assert len(await adapter.search_concepts("aspirin 81", limit=2)) == 2

    async def test_approximate_fallback_keeps_score(self, adapter):
        _patch(adapter, _router())
        result = await adapter.search_concepts("fluoxetin")
        assert [c.primary_id for c in result] == ["4493"]  # duplicate candidates merged
        assert result[0].confidence_score == 0.6
        assert result[0].source_data[KnowledgeSource.RXNORM]["approximate_score"] > 12

    async def test_weak_approximate_matches_are_dropped(self, adapter):
        _patch(adapter, _router())
        assert await adapter.search_concepts("chronic fatigue") == []

    async def test_approximate_ignores_bad_scores(self, adapter):
        bad = {
            "approximateGroup": {"candidate": [{"rxcui": "4493", "score": "n/a"}, {"score": "20"}]}
        }
        _patch(adapter, _router({"approximateTerm.json": bad}))
        assert await adapter.search_concepts("fluoxetin") == []

    async def test_nothing_found(self, adapter):
        _patch(adapter, _router())
        assert await adapter.search_concepts("zzzzqq") == []

    async def test_blank_query_and_bad_limit(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.search_concepts("   ") == []
        assert await adapter.search_concepts("") == []
        assert await adapter.search_concepts("aspirin", limit=0) == []
        router.assert_not_called()

    async def test_error_returns_empty(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.search_concepts("aspirin") == []

    async def test_non_dict_response_returns_empty(self, adapter):
        _patch(adapter, AsyncMock(return_value=["unexpected"]))
        assert await adapter.search_concepts("aspirin") == []


@pytest.mark.asyncio
class TestDetails:
    async def test_details(self, adapter):
        _patch(adapter, _router())
        c = await adapter.get_concept_details("RXCUI:1191")
        assert c is not None
        assert c.primary_id == "1191"
        assert c.confidence_score == 1.0
        assert any("RxCUI 1191" in d for d in c.definitions)
        assert c.synonyms == []  # empty synonym is not recorded
        assert c.sources == [KnowledgeSource.RXNORM]

    async def test_umls_cui_becomes_identifier(self, adapter):
        _patch(adapter, _router())
        c = await adapter.get_concept_details("314293")
        assert any(
            i.source == KnowledgeSource.UMLS and i.identifier == "C0000001" for i in c.identifiers
        )

    async def test_unknown_tty_is_kept(self, adapter):
        props = {"properties": {"rxcui": "9", "name": "odd", "tty": "XYZ", "synonym": "odd"}}
        _patch(adapter, _router({"rxcui/9/properties.json": props}))
        c = await adapter.get_concept_details("9")
        assert c.categories == ["tty:XYZ"]
        assert c.semantic_types == ["XYZ"]
        assert c.synonyms == []  # synonym equal to the label is dropped

    async def test_missing_rxcui(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_concept_details("999999999") is None

    async def test_invalid_id_makes_no_request(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_concept_details("aspirin") is None
        router.assert_not_called()

    async def test_error(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_concept_details("1191") is None


@pytest.mark.asyncio
class TestRelationships:
    async def test_ingredient(self, adapter):
        router = _patch(adapter, _router())
        rels = await adapter.get_relationships("1191")
        labels = {r["relation_label"] for r in rels}
        assert labels == {"has_tradename", "has_form", "ingredient_of"}
        for r in rels:
            assert set(r) >= {"relation_label", "related_id", "related_name", "source", "tty"}
            assert r["source"] == "RxNorm"
        by_label = {r["relation_label"]: r["tty"] for r in rels}
        assert by_label["has_tradename"] == "BN"
        assert by_label["has_form"] == "PIN"
        related_call = [c for c in router.call_args_list if c.args[0].endswith("related.json")][0]
        assert related_call.args[1] == {"tty": "BN PIN SCD SBD"}

    async def test_ingredient_cap_is_per_label(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships("1191", limit=1)
        counts = {}
        for r in rels:
            counts[r["relation_label"]] = counts.get(r["relation_label"], 0) + 1
        # ingredient_of spans SCD and SBD: one each
        assert counts == {"has_tradename": 1, "has_form": 1, "ingredient_of": 2}

    async def test_brand(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships("153010")
        assert {(r["relation_label"], r["related_id"]) for r in rels} == {
            ("tradename_of", "5640"),
            ("has_branded_drug", "153008"),
        }

    async def test_clinical_drug(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships("243670")
        assert {(r["relation_label"], r["related_id"]) for r in rels} == {
            ("has_dose_form", "317541"),
            ("has_ingredient", "1191"),
            ("has_tradename", "724444"),
        }

    async def test_precise_ingredient_ignores_unmapped_groups(self, adapter):
        _patch(adapter, _router())
        rels = await adapter.get_relationships("314293")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [("form_of", "5640")]

    async def test_duplicates_removed(self, adapter):
        dup = {
            "relatedGroup": {
                "conceptGroup": [
                    {"tty": "IN", "conceptProperties": [{"rxcui": "5", "name": "x"}] * 2},
                    {
                        "tty": "IN",
                        "conceptProperties": [{"rxcui": "5", "name": "x"}, {"name": "no id"}],
                    },
                ]
            }
        }
        _patch(adapter, _router({"rxcui/243670/related.json": dup}))
        rels = await adapter.get_relationships("243670")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [("has_ingredient", "5")]

    async def test_term_types_without_relations(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_relationships("317541") == []  # dose form: thousands of drugs
        assert await adapter.get_relationships("316074") == []  # SCDC
        assert not any(c.args[0].endswith("related.json") for c in router.call_args_list)

    async def test_unknown_rxcui_and_invalid_input(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_relationships("999999999") == []
        assert await adapter.get_relationships("aspirin") == []
        assert await adapter.get_relationships("1191", limit=0) == []
        assert router.call_count == 1  # only the properties lookup of the unknown RxCUI

    async def test_empty_related_group(self, adapter):
        _patch(adapter, _router({"rxcui/1191/related.json": {}}))
        assert await adapter.get_relationships("1191") == []

    async def test_error(self, adapter):
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_relationships("1191") == []


@pytest.mark.asyncio
class TestMappings:
    async def test_ingredient_codes(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings("1191")
        got = {(m["toSource"], m["toId"]) for m in maps}
        assert {
            ("DrugBank", "DB00945"),
            ("UNII", "R16CO5Y76E"),
            ("SNOMEDCT", "387458008"),
            ("SNOMEDCT", "7947003"),
            ("ATC", "N02BA01"),
            ("ATC", "B01AC06"),
            ("VUID", "4017536"),
        } <= got
        for m in maps:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "1191" and m["fromSource"] == "RxNorm"
        # SPL set ids and Multum codes are deliberately not mapped
        assert not any(m["toSource"] in {"SPL_SET_ID", "MMSL_CODE"} for m in maps)
        assert next(m for m in maps if m["toSource"] == "ATC")["mappingType"] == "atc_code"
        assert len(got) == len(maps)  # de-duplicated

    async def test_umls_cui(self, adapter):
        _patch(adapter, _router())
        maps = await adapter.get_mappings("314293")
        assert [(m["toSource"], m["toId"], m["confidence"]) for m in maps] == [
            ("UMLS", "C0000001", 0.9)
        ]

    async def test_duplicate_codes_collapsed(self, adapter):
        codes = {
            "propConceptGroup": {
                "propConcept": [
                    {"propName": "ATC", "propValue": "N02BA01"},
                    {"propName": "ATC", "propValue": "N02BA01"},
                    {"propName": "DRUGBANK", "propValue": ""},
                ]
            }
        }
        _patch(adapter, _router({"rxcui/1191/allProperties.json": codes}))
        maps = await adapter.get_mappings("1191")
        assert [(m["toSource"], m["toId"]) for m in maps] == [("ATC", "N02BA01")]

    async def test_codes_are_cached(self, adapter):
        router = _patch(adapter, _router())
        await adapter.get_mappings("1191")
        await adapter.get_mappings("1191")
        calls = [c for c in router.call_args_list if c.args[0].endswith("allProperties.json")]
        assert len(calls) == 1

    async def test_cache_is_bounded(self, adapter, monkeypatch):
        monkeypatch.setattr("knowledge_lookup.adapters.rxnorm_adapter._CODES_CACHE_SIZE", 2)
        _patch(adapter, _router())
        for rxcui in ("1191", "243670", "1191", "243670"):
            await adapter._code_properties(rxcui)
        assert len(adapter._codes) <= 2
        await adapter._code_properties("5640")
        assert len(adapter._codes) == 2

    async def test_unknown_invalid_and_error(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_mappings("999999999") == []
        assert await adapter.get_mappings("not-an-id") == []
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_mappings("1191") == []


@pytest.mark.asyncio
class TestNdc:
    async def test_product_ndcs(self, adapter):
        _patch(adapter, _router())
        ndcs = await adapter.get_ndc("RXCUI:243670")
        assert len(ndcs) == 6
        assert ndcs[0] == "21130048112"

    async def test_ingredient_has_no_ndcs(self, adapter):
        _patch(adapter, _router())
        assert await adapter.get_ndc("1191") == []

    async def test_invalid_and_error(self, adapter):
        router = _patch(adapter, _router())
        assert await adapter.get_ndc("aspirin") == []
        router.assert_not_called()
        _patch(adapter, AsyncMock(side_effect=RuntimeError("boom")))
        assert await adapter.get_ndc("243670") == []


@pytest.mark.asyncio
class TestThrottle:
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        monkeypatch.setattr("knowledge_lookup.adapters.rxnorm_adapter.asyncio.sleep", fake_sleep)
        _patch(adapter, _router())
        adapter._last_request = 0.0  # as if a request just happened (monotonic clock >> 0)
        import time

        adapter._last_request = time.monotonic()
        await adapter._get("https://rxnav.nlm.nih.gov/REST/rxcui.json", {"name": "aspirin"})
        assert sleeps and 0 < sleeps[0] <= 0.06 + 1e-6  # float noise when the clock is coarse
