"""Unit tests for ClinicalTablesAdapter (NLM Clinical Table Search Service); no network.

The responses in ``tests/fixtures/clinicaltables_responses.py`` are real answers recorded
from the live service; payloads built by hand are used only for edge cases the live service
does not produce on demand (prefix neighbours, malformed bodies, hierarchies).
"""

import asyncio
import copy
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qsl, urlencode

import pytest

from knowledge_lookup.adapters import _vocab_common, clinicaltables_adapter
from knowledge_lookup.adapters.clinicaltables_adapter import (
    DEFAULT_TABLES,
    TABLES,
    ClinicalTablesAdapter,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.clinicaltables_responses import RECORDED, request_key

pytestmark = pytest.mark.unit

ALL_TABLES = ["icd10cm", "conditions", "loinc_items", "hpo", "icd11_codes", "disease_names"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(clinicaltables_adapter.TABLES_ENV, raising=False)
    monkeypatch.setattr(clinicaltables_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return ClinicalTablesAdapter(lookup_config)


def _without_max_list(key):
    """Request key minus ``maxList``: the recording used a small page, tests ask for more."""
    url, _, query = key.partition("?")
    kept = [(k, v) for k, v in parse_qsl(query) if k != "maxList"]
    return url + "?" + urlencode(sorted(kept))


RECORDED_ANY_PAGE = {_without_max_list(k): v for k, v in RECORDED.items()}


def replay():
    """Fake ``_make_request`` answering from the recorded live responses."""

    async def fake(url, params=None, headers=None, json_data=None):
        key = _without_max_list(request_key(url, params))
        if key not in RECORDED_ANY_PAGE:
            raise AssertionError(f"unrecorded request: {key}")
        return copy.deepcopy(RECORDED_ANY_PAGE[key])

    return fake


def table_of(url):
    return url.rsplit("/api/", 1)[1].split("/", 1)[0]


def payload(table_name, rows, extras=None):
    """Hand-built answer: rows = [(code, label), ...]."""
    return [
        len(rows),
        [r[0] for r in rows],
        extras,
        [[r[1]] for r in rows],
    ]


def router(by_table):
    """Fake ``_make_request`` answering by table name (value: payload or Exception)."""

    async def fake(url, params=None, headers=None, json_data=None):
        value = by_table[table_of(url)]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CLINICALTABLES
        assert adapter.is_available() is True

    def test_default_tables(self, adapter):
        assert adapter.tables == DEFAULT_TABLES == ("icd10cm", "conditions", "loinc_items", "hpo")

    def test_tables_from_environment(self, lookup_config, monkeypatch):
        monkeypatch.setenv(clinicaltables_adapter.TABLES_ENV, " HPO, icd11_codes ,hpo,nope,")
        assert ClinicalTablesAdapter(lookup_config).tables == ("hpo", "icd11_codes")

    def test_environment_with_only_unknown_tables_falls_back(self, lookup_config, monkeypatch):
        monkeypatch.setenv(clinicaltables_adapter.TABLES_ENV, "nope")
        assert ClinicalTablesAdapter(lookup_config).tables == DEFAULT_TABLES

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("G93.32", "G93.32"),
            ("g93.32", "G93.32"),
            ("G9332", "G93.32"),
            (" U09.9 ", "U09.9"),
            ("T67.6XXS", "T67.6XXS"),
            ("E11", "E11"),
            ("not a code", None),
            ("", None),
            ("12927", None),
        ],
    )
    def test_normalize_icd10cm(self, raw, expected):
        assert ClinicalTablesAdapter.normalize_icd10cm(raw) == expected

    @pytest.mark.parametrize(
        "raw,table,code",
        [
            ("ICD10CM:G93.32", "icd10cm", "G93.32"),
            ("icd10cm:g9332", "icd10cm", "G93.32"),
            ("G93.32", "icd10cm", "G93.32"),
            ("CONDITIONS:12927", "conditions", "12927"),
            ("LOINC:70735-6", "loinc_items", "70735-6"),
            ("70735-6", "loinc_items", "70735-6"),
            ("loinc_items:70735-6", "loinc_items", "70735-6"),
            ("HP:0012378", "hpo", "HP:0012378"),
            ("HPO:0012378", "hpo", "HP:0012378"),
            ("hp_0012378", "hpo", "HP:0012378"),
            ("ICD11:MG22", "icd11_codes", "MG22"),
            ("DISEASE_NAMES:C0015672", "disease_names", "C0015672"),
            ("c0015672", "disease_names", "C0015672"),
        ],
    )
    def test_resolve_id(self, adapter, raw, table, code):
        resolved = adapter._resolve_id(raw)
        assert resolved is not None
        assert (resolved[0].name, resolved[1]) == (table, code)

    @pytest.mark.parametrize(
        "raw", ["", "   ", None, "fatigue", "XYZ:123", "ICD10CM:", "ICD10CM:not-a-code"]
    )
    def test_resolve_id_rejects_garbage(self, adapter, raw):
        assert adapter._resolve_id(raw) is None

    def test_every_table_has_a_unique_prefix(self):
        assert len({t.prefix for t in TABLES.values()}) == len(TABLES)


class TestParsePayload:
    table = TABLES["icd10cm"]

    @pytest.mark.parametrize(
        "body",
        [None, {}, "text", [], [0], [0, [], None], [0, "x", None, []], {"error": "x"}],
    )
    def test_malformed_bodies_give_nothing(self, body):
        assert ClinicalTablesAdapter._parse_payload(self.table, body) == []

    def test_rows_with_missing_display_and_extras(self):
        body = [2, ["A", None, "", "B"], {"f": ["x"]}, [["Label A"]]]
        rows = ClinicalTablesAdapter._parse_payload(self.table, body)
        assert [r["code"] for r in rows] == ["A", "B"]
        assert rows[0]["label"] == "Label A" and rows[0]["extra"] == {"f": "x"}
        assert rows[1]["label"] == "" and rows[1]["extra"] == {"f": None}


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_all_tables_interleaves_and_types(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            results = await adapter.search_concepts("fatigue", limit=20, tables=ALL_TABLES)
        assert req.call_count == len(ALL_TABLES)
        ids = [c.primary_id for c in results]
        # first round: the top hit of every table, in the order the tables were asked for
        assert ids[:6] == [
            "ICD10CM:R53.83",
            "CONDITIONS:2329",
            "LOINC:64101-9",
            "HP:0012378",
            "ICD11:MG22",
            "DISEASE_NAMES:C0015672",
        ]
        assert len(ids) == len(set(ids)) == 17  # conditions has only two fatigue entries
        by_id = {c.primary_id: c for c in results}
        assert by_id["ICD10CM:G93.31"].primary_label == "Postviral fatigue syndrome"
        assert by_id["HP:0012378"].concept_type == ConceptType.PHENOTYPE
        assert by_id["LOINC:64101-9"].concept_type == ConceptType.OBSERVATION
        assert by_id["ICD10CM:R53.82"].concept_type == ConceptType.DISEASE
        assert all(c.sources == [KnowledgeSource.CLINICALTABLES] for c in results)

    @pytest.mark.asyncio
    async def test_search_request_parameters(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            await adapter.search_concepts("fatigue", limit=3, tables=["icd10cm", "hpo"])
        calls = {table_of(c.args[0]): c.args[1] for c in req.call_args_list}
        # ICD-10-CM searches the code only unless the name field is asked for
        assert calls["icd10cm"]["sf"] == "code,name"
        assert calls["icd10cm"]["terms"] == "fatigue" and calls["icd10cm"]["maxList"] == 3
        assert calls["icd10cm"]["cf"] == "code" and calls["icd10cm"]["df"] == "name"
        assert "ef" not in calls["icd10cm"]
        assert "sf" not in calls["hpo"]  # service default (id, name, synonym.term)
        assert "synonym" in calls["hpo"]["ef"].split(",")

    @pytest.mark.asyncio
    async def test_default_tables_are_searched(self, adapter):
        seen = []

        async def fake(url, params=None, headers=None, json_data=None):
            seen.append(table_of(url))
            return [0, [], None, []]

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.search_concepts("fatigue") == []
        assert sorted(seen) == sorted(DEFAULT_TABLES)

    @pytest.mark.asyncio
    async def test_limit_is_respected_and_capped(self, adapter):
        rows = [(f"A{i:02d}", f"Name {i}") for i in range(10)]
        big = payload("icd10cm", rows)
        with patch.object(adapter, "_make_request", AsyncMock(return_value=big)) as req:
            results = await adapter.search_concepts("x", limit=4, tables=["icd10cm"])
            await adapter.search_concepts("x", limit=9999, tables=["icd10cm"])
        assert [c.primary_id for c in results] == [f"ICD10CM:A0{i}" for i in range(4)]
        assert req.call_args_list[0].args[1]["maxList"] == 4
        assert req.call_args_list[1].args[1]["maxList"] == clinicaltables_adapter._MAX_LIST

    @pytest.mark.asyncio
    async def test_limit_trims_interleaved_results(self, adapter):
        fake = router(
            {
                "icd10cm": payload("icd10cm", [("A01", "One"), ("A02", "Two")]),
                "disease_names": payload("disease_names", [("C0000001", "Uno")]),
            }
        )
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            results = await adapter.search_concepts(
                "x", limit=2, tables=["icd10cm", "disease_names"]
            )
        assert [c.primary_id for c in results] == ["ICD10CM:A01", "DISEASE_NAMES:C0000001"]

    @pytest.mark.asyncio
    async def test_duplicates_are_removed(self, adapter):
        dup = payload("icd10cm", [("A01", "One"), ("A01", "One again")])
        with patch.object(adapter, "_make_request", AsyncMock(return_value=dup)):
            results = await adapter.search_concepts("x", tables=["icd10cm"])
        assert [c.primary_id for c in results] == ["ICD10CM:A01"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), (None, 5), ("x", 0), ("x", -1)])
    async def test_empty_query_or_limit_makes_no_request(self, adapter, query, limit):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts(query, limit=limit) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_hits(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            assert await adapter.search_concepts("zzzzqqqq", limit=3, tables=["icd10cm"]) == []

    @pytest.mark.asyncio
    async def test_one_failing_table_does_not_hide_the_others(self, adapter):
        fake = router(
            {
                "icd10cm": RuntimeError("boom"),
                "hpo": payload("hpo", [("HP:0000001", "All")], {"definition": ["d"]}),
            }
        )
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            results = await adapter.search_concepts("x", tables=["icd10cm", "hpo"])
        assert [c.primary_id for c in results] == ["HP:0000001"]

    @pytest.mark.asyncio
    async def test_unknown_tables_in_call_are_ignored(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts("x", tables=["nope"]) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_rows_without_a_label_are_skipped(self, adapter):
        body = payload("icd10cm", [("A01", ""), ("A02", "Two")])
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            results = await adapter.search_concepts("x", tables=["icd10cm"])
        assert [c.primary_id for c in results] == ["ICD10CM:A02"]


class TestDetails:
    @pytest.mark.asyncio
    async def test_icd10cm_by_curie_and_bare_code(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            curie = await adapter.get_concept_details("ICD10CM:G93.32")
            bare = await adapter.get_concept_details("g9332")
        assert curie.primary_id == bare.primary_id == "ICD10CM:G93.32"
        assert curie.primary_label == "Myalgic encephalomyelitis/chronic fatigue syndrome"
        assert curie.concept_type == ConceptType.DISEASE
        assert curie.categories == ["clinicaltables:icd10cm"]
        data = curie.source_data[KnowledgeSource.CLINICALTABLES]
        assert data["table"] == "icd10cm" and data["code"] == "G93.32"
        # exact-code lookup: code field only, wide page because search is prefix based
        params = req.call_args_list[0].args[1]
        assert params["sf"] == "code" and params["terms"] == "G93.32" and params["maxList"] == 100

    @pytest.mark.asyncio
    async def test_icd10cm_post_covid_code(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            concept = await adapter.get_concept_details("U09.9")
        assert concept.primary_label == "Post COVID-19 condition, unspecified"

    @pytest.mark.asyncio
    async def test_prefix_neighbours_are_filtered_out(self, adapter):
        body = payload("icd10cm", [("G93.31", "Postviral"), ("G93.32", "ME/CFS"), ("G93.39", "x")])
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            concept = await adapter.get_concept_details("ICD10CM:G93.32")
            missing = await adapter.get_concept_details("ICD10CM:G93.3")
        assert concept.primary_label == "ME/CFS"
        assert missing is None

    @pytest.mark.asyncio
    async def test_conditions_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            concept = await adapter.get_concept_details("CONDITIONS:12927")
            diabetes = await adapter.get_concept_details("CONDITIONS:2143")
        assert concept.primary_id == "CONDITIONS:12927"
        assert concept.primary_label == "Chronic fatigue syndrome"
        data = concept.source_data[KnowledgeSource.CLINICALTABLES]
        assert data["icd10cm"] == [{"code": "R53.82", "name": "Chronic fatigue, unspecified"}]
        assert data["icd9cm"] == {"code": "780.71", "name": "Chronic fatigue syndrome"}
        assert data["info_links"][0]["url"].endswith("chronicfatiguesyndrome.html")
        # consumer name differs from the primary name -> kept as a synonym; DM from the table
        assert diabetes.primary_label == "Diabetes mellitus"
        assert "Diabetes mellitus (DM)" in diabetes.synonyms and "DM" in diabetes.synonyms

    @pytest.mark.asyncio
    async def test_loinc_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            by_curie = await adapter.get_concept_details("LOINC:70735-6")
            by_bare = await adapter.get_concept_details("70735-6")
        assert by_curie.primary_id == by_bare.primary_id == "LOINC:70735-6"
        assert by_curie.primary_label.startswith("Functional Assessment of Chronic Illness")
        assert by_curie.concept_type == ConceptType.OBSERVATION
        data = by_curie.source_data[KnowledgeSource.CLINICALTABLES]
        assert data["isCopyrighted"] is True  # external copyright holder (FACIT)
        assert data["terms_of_use"] == "https://loinc.org/terms-of-use"

    @pytest.mark.asyncio
    async def test_hpo_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            concept = await adapter.get_concept_details("HP:0012432")
        assert concept.primary_id == "HP:0012432"
        assert concept.primary_label == "Chronic fatigue"
        assert concept.concept_type == ConceptType.PHENOTYPE
        assert concept.parents == ["HP:0012378"]
        assert "Chronic extreme exhaustion" in concept.synonyms
        assert concept.definitions[0].startswith("Subjective feeling of tiredness")

    @pytest.mark.asyncio
    async def test_icd11_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            concept = await adapter.get_concept_details("ICD11:MG22")
        assert concept.primary_label == "Fatigue"
        assert "exhaustion" in concept.synonyms and "Fatigue" not in concept.synonyms
        assert concept.definitions[0].startswith("A feeling of exhaustion")
        data = concept.source_data[KnowledgeSource.CLINICALTABLES]
        assert data["type"] == "stem" and data["source"].startswith("http://id.who.int/icd/")

    @pytest.mark.asyncio
    async def test_disease_names_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            concept = await adapter.get_concept_details("C0015672")
        assert concept.primary_id == "DISEASE_NAMES:C0015672"
        assert concept.source_data[KnowledgeSource.CLINICALTABLES]["cui"] == "C0015672"

    @pytest.mark.asyncio
    async def test_unknown_code_is_none(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[0, [], None, []])):
            assert await adapter.get_concept_details("ICD10CM:Z99.99") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw", ["", "fatigue", None, "XYZ:1"])
    async def test_unrecognised_ids_make_no_request(self, adapter, raw):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.get_concept_details(raw) is None
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_gives_none(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("503"))):
            assert await adapter.get_concept_details("ICD10CM:G93.32") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_conditions_mappings(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            maps = await adapter.get_mappings("CONDITIONS:12927")
        assert {(m["toSource"], m["toId"]) for m in maps} == {
            ("ICD10CM", "R53.82"),
            ("ICD9CM", "780.71"),
            ("MEDLINEPLUS", "http://www.nlm.nih.gov/medlineplus/chronicfatiguesyndrome.html"),
        }
        for m in maps:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "CONDITIONS:12927" and m["fromSource"] == "CLINICALTABLES"
        assert {m["mappingType"] for m in maps} == {"suggested_code", "info_link"}

    @pytest.mark.asyncio
    async def test_conditions_mappings_fall_back_to_code_list_and_dedupe(self, adapter):
        body = [
            1,
            ["1"],
            {
                "icd10cm_codes": ["S06.0X?,S06.0X?, T14.9"],
                "icd10cm": [None],
                "term_icd9_code": [None],
            },
            [["Injury"]],
        ]
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            maps = await adapter.get_mappings("CONDITIONS:1")
        assert [m["toId"] for m in maps] == ["S06.0X?", "T14.9"]

    @pytest.mark.asyncio
    async def test_disease_names_maps_to_umls(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            maps = await adapter.get_mappings("DISEASE_NAMES:C0015672")
        assert [(m["toSource"], m["toId"]) for m in maps] == [("UMLS", "C0015672")]

    @pytest.mark.asyncio
    async def test_hpo_xrefs(self, adapter):
        body = [
            1,
            ["HP:0001945"],
            {
                "xref": [[{"id": "UMLS:C0015967", "name": "Fever"}, "SNOMEDCT_US:386661006", "x"]],
                "is_a": [[]],
            },
            [["Fever"]],
        ]
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            maps = await adapter.get_mappings("HP:0001945")
        assert [(m["toSource"], m["toId"]) for m in maps] == [
            ("UMLS", "UMLS:C0015967"),
            ("SNOMEDCT_US", "SNOMEDCT_US:386661006"),
        ]

    @pytest.mark.asyncio
    async def test_tables_without_cross_references(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            assert await adapter.get_mappings("ICD10CM:G93.32") == []
            assert await adapter.get_mappings("LOINC:70735-6") == []
            assert await adapter.get_mappings("HP:0012432") == []  # xref is null

    @pytest.mark.asyncio
    async def test_unknown_id_and_errors(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[0, [], None, []])):
            assert await adapter.get_mappings("ICD10CM:Z99.99") == []
        assert await adapter.get_mappings("nonsense") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("CONDITIONS:12927") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_hpo_is_a(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            rels = await adapter.get_relationships("HP:0012432")
        assert rels == [
            {
                "relation_label": "is_a",
                "related_id": "HP:0012378",
                "related_name": "Fatigue",
                "source": "CLINICALTABLES",
            }
        ]

    @pytest.mark.asyncio
    async def test_other_tables_have_no_hierarchy(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            assert await adapter.get_relationships("ICD10CM:G93.32") == []

    @pytest.mark.asyncio
    async def test_unknown_id_and_errors(self, adapter):
        assert await adapter.get_relationships("nonsense") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("HP:0012432") == []


class TestThrottle:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        adapter._spacer.interval = 0.05
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(_vocab_common.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[0, [], None, []])):
            await adapter.search_concepts("x", tables=["icd10cm"])
            await adapter.search_concepts("x", tables=["icd10cm"])
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6

    @pytest.mark.asyncio
    async def test_parallel_table_requests_are_serialised_by_the_spacer(self, adapter):
        order = []

        async def fake(url, params=None, headers=None, json_data=None):
            order.append(table_of(url))
            await asyncio.sleep(0)
            return [0, [], None, []]

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            await adapter.search_concepts("x", tables=["hpo", "icd10cm"])
        assert order == ["hpo", "icd10cm"]
