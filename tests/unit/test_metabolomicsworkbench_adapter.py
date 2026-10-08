"""Unit tests for MetabolomicsWorkbenchAdapter (REST API); no network."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import metabolomicsworkbench_adapter as mw
from knowledge_lookup.adapters.metabolomicsworkbench_adapter import MetabolomicsWorkbenchAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.metabolomicsworkbench_responses import (
    COMPOUND_LACTIC_ACID,
    DISEASE_LONG_COVID,
    DISEASE_NONE,
    REFMET_LACTIC_ACID,
    REFMET_MATCH_LACTATE,
    REFMET_MATCH_NONE,
    REFMET_MG,
    STUDIES_FOR_LACTIC_ACID,
    STUDY_LONG_COVID,
    STUDY_METABOLITES,
    STUDY_PREFIX_MATCH,
    STUDY_SEARCH_MECFS,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_throttle_delay(monkeypatch):
    monkeypatch.setattr(mw, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return MetabolomicsWorkbenchAdapter(lookup_config)


def router(routes, calls=None):
    """Fake ``_make_request``: ``routes`` maps a path (after ``/rest/``) to a payload/exception."""

    async def fake(url, params=None, headers=None, json_data=None):
        path = url.split("/rest/", 1)[1]
        if calls is not None:
            calls.append(path)
        if path not in routes:
            raise AssertionError(f"unexpected path {path}")
        value = routes[path]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    return fake


LACTIC = {
    "refmet/refmet_id/RM0135904/all": REFMET_LACTIC_ACID,
    "compound/regno/37125/all": COMPOUND_LACTIC_ACID,
}


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.METABOLOMICSWORKBENCH
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ST002003", ("study", "ST002003")),
            ("st002003", ("study", "ST002003")),
            ("MW:ST002003", ("study", "ST002003")),
            ("RM0135904", ("refmet", "RM0135904")),
            ("RefMet:RM0135904", ("refmet", "RM0135904")),
            ("regno:37125", ("regno", "37125")),
            ("MWRN:0037125", ("regno", "37125")),
            ("Lactic acid", ("name", "Lactic acid")),
            ("MG 18:0/0:0/0:0", ("name", "MG 18:0/0:0/0:0")),
            ("ST00200", ("name", "ST00200")),  # too short for a study id: treated as a name
            ("", None),
            ("   ", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert MetabolomicsWorkbenchAdapter._parse_id(raw) == expected

    def test_records_shapes(self):
        records = MetabolomicsWorkbenchAdapter._records
        assert records([]) == []
        assert records({}) == []
        assert records(None) == []
        assert records("<html>") == []
        assert records({"a": 1, "b": 2}) == [{"a": 1, "b": 2}]  # flat record
        assert records({"1": {"x": 1}, "2": {"x": 2}}) == [{"x": 1}, {"x": 2}]

    def test_segment_escaping_keeps_slash_and_colon(self):
        seg = MetabolomicsWorkbenchAdapter._seg
        assert seg("MG 18:0/0:0/0:0") == "MG%2018:0/0:0/0:0"
        assert seg("1,2,4-Trihydroxybenzene") == "1,2,4-Trihydroxybenzene"
        assert seg("a?b#c") == "a%3Fb%23c"


class TestSearch:
    @pytest.mark.asyncio
    async def test_studies_for_a_disease_term(self, adapter):
        calls = []
        routes = {
            "refmet/match/chronic%20fatigue": REFMET_MATCH_NONE,
            "study/study_title/chronic%20fatigue/summary": STUDY_SEARCH_MECFS,
        }
        with patch.object(adapter, "_make_request", router(routes, calls)):
            concepts = await adapter.search_concepts("chronic fatigue", limit=10)
        assert [c.primary_id for c in concepts] == ["ST004941", "ST002003"]
        first = concepts[0]
        assert first.concept_type == ConceptType.STUDY
        assert first.sources == [KnowledgeSource.METABOLOMICSWORKBENCH]
        assert first.identifiers[0].url.endswith("StudyID=ST004941")
        assert "StudyID=CHRONIC" not in first.identifiers[0].url  # upstream URL is malformed
        assert "30 samples" in first.definitions[0]
        assert first.categories == ["Homo sapiens"]
        assert first.semantic_types == ["LC-MS"]
        assert first.source_data[KnowledgeSource.METABOLOMICSWORKBENCH]["license"] == "CC BY 4.0"
        assert concepts[0].confidence_score > concepts[1].confidence_score
        assert calls == [
            "refmet/match/chronic%20fatigue",
            "study/study_title/chronic%20fatigue/summary",
        ]

    @pytest.mark.asyncio
    async def test_metabolite_comes_first_then_studies(self, adapter):
        routes = {
            "refmet/match/lactate": REFMET_MATCH_LACTATE,
            "study/study_title/lactate/summary": STUDY_LONG_COVID,  # single flat hit
        }
        with patch.object(adapter, "_make_request", router(routes)):
            concepts = await adapter.search_concepts("lactate", limit=5)
        assert [c.primary_id for c in concepts] == ["RM0135904", "ST003103"]
        metabolite = concepts[0]
        assert metabolite.concept_type == ConceptType.METABOLITE
        assert metabolite.primary_label == "Lactic acid"
        assert metabolite.categories == ["Organic acids", "Short-chain acids"]
        assert metabolite.identifiers[0].url.endswith("REFMET_ID=RM0135904")

    @pytest.mark.asyncio
    async def test_limit_counts_the_metabolite(self, adapter):
        routes = {
            "refmet/match/lactate": REFMET_MATCH_LACTATE,
            "study/study_title/lactate/summary": STUDY_SEARCH_MECFS,
        }
        with patch.object(adapter, "_make_request", router(routes)):
            assert len(await adapter.search_concepts("lactate", limit=2)) == 2
            assert len(await adapter.search_concepts("lactate", limit=1)) == 1
            assert await adapter.search_concepts("lactate", limit=0) == []

    @pytest.mark.asyncio
    async def test_refmet_failure_still_returns_studies(self, adapter):
        routes = {
            "refmet/match/lactate": RuntimeError("down"),
            "study/study_title/lactate/summary": STUDY_LONG_COVID,
        }
        with patch.object(adapter, "_make_request", router(routes)):
            concepts = await adapter.search_concepts("lactate")
        assert [c.primary_id for c in concepts] == ["ST003103"]

    @pytest.mark.asyncio
    async def test_slash_in_query_stays_raw(self, adapter):
        calls = []
        routes = {
            "refmet/match/ME/CFS": REFMET_MATCH_NONE,
            "study/study_title/ME/CFS/summary": [],
        }
        with patch.object(adapter, "_make_request", router(routes, calls)):
            assert await adapter.search_concepts("ME/CFS") == []
        assert calls[0] == "refmet/match/ME/CFS"

    @pytest.mark.asyncio
    async def test_search_by_id_goes_to_details(self, adapter):
        routes = {
            "study/study_id/ST003103/summary": STUDY_LONG_COVID,
            "study/study_id/ST003103/disease": DISEASE_LONG_COVID,
        }
        with patch.object(adapter, "_make_request", router(routes)):
            concepts = await adapter.search_concepts("ST003103")
        assert [c.primary_id for c in concepts] == ["ST003103"]
        with patch.object(
            adapter, "_make_request", router({"study/study_id/ST999999/summary": []})
        ):
            assert await adapter.search_concepts("ST999999") == []

    @pytest.mark.asyncio
    async def test_empty_and_error(self, adapter):
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts(None) == []
        routes = {"refmet/match/x": REFMET_MATCH_NONE, "study/study_title/x/summary": []}
        with patch.object(adapter, "_make_request", router(routes)):
            assert await adapter.search_concepts("x") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_study(self, adapter):
        routes = {
            "study/study_id/ST003103/summary": STUDY_LONG_COVID,
            "study/study_id/ST003103/disease": DISEASE_LONG_COVID,
        }
        with patch.object(adapter, "_make_request", router(routes)):
            concept = await adapter.get_concept_details("MW:ST003103")
        assert concept.primary_id == "ST003103"
        assert concept.categories == ["Homo sapiens", "COVID-19"]
        assert concept.semantic_types == ["GC-MS/LC-MS"]
        assert "condition: COVID-19" in concept.definitions[0]
        assert "; condition" in concept.definitions[0] and " ;" not in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.METABOLOMICSWORKBENCH]
        assert data["disease"] == "COVID-19" and data["institute"] == "Universidad CEU San Pablo"
        assert concept.confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_study_prefix_match_is_filtered_to_exact_id(self, adapter):
        routes = {
            "study/study_id/ST002003/summary": STUDY_PREFIX_MATCH,
            "study/study_id/ST002003/disease": DISEASE_NONE,
        }
        with patch.object(adapter, "_make_request", router(routes)):
            concept = await adapter.get_concept_details("ST002003")
        assert concept.primary_id == "ST002003"
        assert concept.categories == ["Homo sapiens"]
        # "ST0020" is not a full id, so it is looked up as a RefMet name and finds nothing
        with patch.object(adapter, "_make_request", router({"refmet/name/ST0020/all": []})):
            assert await adapter.get_concept_details("ST0020") is None

    @pytest.mark.asyncio
    async def test_study_without_title_or_disease_failure(self, adapter):
        routes = {
            "study/study_id/ST000009/summary": {"study_id": "ST000009", "study_title": ""},
        }
        with patch.object(adapter, "_make_request", router(routes)):
            assert await adapter.get_concept_details("ST000009") is None
        routes = {
            "study/study_id/ST003103/summary": STUDY_LONG_COVID,
            "study/study_id/ST003103/disease": RuntimeError("down"),
        }
        with patch.object(adapter, "_make_request", router(routes)):
            concept = await adapter.get_concept_details("ST003103")
        assert concept is not None and concept.categories == ["Homo sapiens"]

    @pytest.mark.asyncio
    async def test_metabolite_by_refmet_id(self, adapter):
        with patch.object(adapter, "_make_request", router(LACTIC)):
            concept = await adapter.get_concept_details("RM0135904")
        assert concept.primary_id == "RM0135904"
        assert concept.primary_label == "Lactic acid"
        assert concept.concept_type == ConceptType.METABOLITE
        assert concept.synonyms == ["L-Lactic acid", "(2S)-2-hydroxypropanoic acid"]
        assert concept.categories == ["Organic acids", "Short-chain acids"]
        assert "C3H6O3" in concept.definitions[0]
        ids = {i.source: i.identifier for i in concept.identifiers}
        assert ids == {
            KnowledgeSource.METABOLOMICSWORKBENCH: "RM0135904",
            KnowledgeSource.PUBCHEM: "107689",
            KnowledgeSource.KEGG: "C00186",
            KnowledgeSource.CHEBI: "422",
        }
        data = concept.source_data[KnowledgeSource.METABOLOMICSWORKBENCH]
        assert data["hmdb_id"] == "HMDB0000190"
        assert data["inchi_key"] == "JVTAAEKCZFNVCJ-REOHCLBHSA-N"
        assert data["regno"] == "37125"

    @pytest.mark.asyncio
    async def test_metabolite_by_name_and_slash_name(self, adapter):
        routes = {"refmet/name/MG%2018:0/0:0/0:0/all": REFMET_MG}
        calls = []
        with patch.object(adapter, "_make_request", router(routes, calls)):
            concept = await adapter.get_concept_details("MG 18:0/0:0/0:0")
        assert concept.primary_id == "RM0134397"
        assert concept.categories == ["Glycerolipids", "Monoradylglycerols", "MAG"]
        # a negative registry number marks a class without compound record: no second call
        assert calls == ["refmet/name/MG%2018:0/0:0/0:0/all"]

    @pytest.mark.asyncio
    async def test_metabolite_by_regno(self, adapter):
        with patch.object(adapter, "_make_request", router(LACTIC)):
            concept = await adapter.get_concept_details("regno:37125")
        assert concept.primary_id == "regno:37125"
        assert concept.primary_label == "L-Lactic acid"
        assert concept.synonyms == ["(2S)-2-hydroxypropanoic acid"]
        assert {i.source for i in concept.identifiers} >= {KnowledgeSource.CHEBI}

    @pytest.mark.asyncio
    async def test_unknown_and_error(self, adapter):
        with patch.object(adapter, "_make_request", router({"compound/regno/5/all": []})):
            assert await adapter.get_concept_details("regno:5") is None
        with patch.object(
            adapter, "_make_request", router({"refmet/refmet_id/RM1234567/all": []})
        ):
            assert await adapter.get_concept_details("RM1234567") is None
        with patch.object(
            adapter, "_make_request", router({"study/study_id/ST999999/summary": []})
        ):
            assert await adapter.get_concept_details("ST999999") is None
        # regno 0 is not a valid compound registry number: no request is made at all
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=AssertionError)):
            assert await adapter.get_concept_details("regno:0") is None
        assert await adapter.get_concept_details("") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_concept_details("RM0135904") is None

    @pytest.mark.asyncio
    async def test_compound_lookup_failure_is_an_error_not_partial_data(self, adapter):
        routes = {
            "refmet/refmet_id/RM0135904/all": REFMET_LACTIC_ACID,
            "compound/regno/37125/all": RuntimeError("down"),
        }
        with patch.object(adapter, "_make_request", router(routes)):
            assert await adapter.get_concept_details("RM0135904") is None

    def test_metabolite_without_identifiers_is_none(self, adapter):
        assert adapter._metabolite_to_concept({}, {}) is None
        assert adapter._match_to_concept({"refmet_id": "RM1", "refmet_name": "-"}) is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        with patch.object(adapter, "_make_request", router(LACTIC)):
            mappings = await adapter.get_mappings("RM0135904")
        assert {m["toId"] for m in mappings} == {
            "PUBCHEM:107689",
            "KEGG:C00186",
            "CHEBI:422",
            "HMDB:HMDB0000190",
            "METACYC:L-LACTATE",
            "INCHIKEY:JVTAAEKCZFNVCJ-REOHCLBHSA-N",
        }
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "RM0135904"
            assert m["fromSource"] == "METABOLOMICSWORKBENCH"

    @pytest.mark.asyncio
    async def test_chebi_prefix_is_not_doubled_and_regno_source(self, adapter):
        compound = dict(COMPOUND_LACTIC_ACID, chebi_id="CHEBI:422", lm_id="LMFA00000001")
        with patch.object(
            adapter, "_make_request", router({"compound/regno/37125/all": compound})
        ):
            mappings = await adapter.get_mappings("regno:37125")
        ids = {m["toId"] for m in mappings}
        assert "CHEBI:422" in ids and "LIPIDMAPS:LMFA00000001" in ids
        assert {m["fromId"] for m in mappings} == {"regno:37125"}

    @pytest.mark.asyncio
    async def test_no_mappings_for_studies_unknown_or_errors(self, adapter):
        assert await adapter.get_mappings("ST003103") == []
        assert await adapter.get_mappings("") == []
        with patch.object(
            adapter, "_make_request", router({"refmet/refmet_id/RM1234567/all": []})
        ):
            assert await adapter.get_mappings("RM1234567") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_mappings("RM0135904") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_study_to_metabolites(self, adapter):
        routes = {"study/study_id/ST004941/metabolites": STUDY_METABOLITES}
        with patch.object(adapter, "_make_request", router(routes)):
            rels = await adapter.get_relationships("ST004941")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [
            ("measures_metabolite", "3-Hydroxyanthranilic acid"),
            ("measures_metabolite", "5-Hydroxyindoleacetic acid"),
            ("measures_metabolite", "Tryptophan"),
        ]
        assert rels[0]["analysis_ids"] == ["AN008374", "AN008375"]
        assert rels[0]["analyses"] == 2
        assert rels[1]["analyses"] == 1
        assert all(r["source"] == "METABOLOMICSWORKBENCH" for r in rels)

    @pytest.mark.asyncio
    async def test_study_metabolites_are_capped(self, adapter):
        routes = {"study/study_id/ST004941/metabolites": STUDY_METABOLITES}
        with patch.object(adapter, "_make_request", router(routes)):
            assert len(await adapter.get_relationships("ST004941", limit=2)) == 2
            assert await adapter.get_relationships("ST004941", limit=0) == []

    @pytest.mark.asyncio
    async def test_metabolite_to_studies_newest_first(self, adapter):
        routes = dict(LACTIC)
        routes["study/refmet_name/Lactic%20acid/summary"] = STUDIES_FOR_LACTIC_ACID
        with patch.object(adapter, "_make_request", router(routes)):
            rels = await adapter.get_relationships("RM0135904", limit=3)
        assert [r["related_id"] for r in rels] == ["ST003103", "ST002003", "ST000002"]
        assert {r["relation_label"] for r in rels} == {"measured_in_study"}
        assert rels[0]["total_studies"] == 4  # duplicates are counted once

    @pytest.mark.asyncio
    async def test_unknown_metabolite_and_errors(self, adapter):
        with patch.object(
            adapter, "_make_request", router({"refmet/refmet_id/RM1234567/all": []})
        ):
            assert await adapter.get_relationships("RM1234567") == []
        # a regno-only compound has no RefMet name to look studies up by
        with patch.object(adapter, "_make_request", router({"compound/regno/37125/all": {}})):
            assert await adapter.get_relationships("regno:37125") == []
        assert await adapter.get_relationships("") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_relationships("ST004941") == []


class TestThrottling:
    @pytest.mark.asyncio
    async def test_calls_are_spaced(self, adapter, monkeypatch):
        monkeypatch.setattr(mw, "_MIN_INTERVAL", 0.5)
        now = [50.0]
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)
            now[0] += delay

        monkeypatch.setattr(mw.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(mw, "time", SimpleNamespace(monotonic=lambda: now[0]))
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[])):
            for _ in range(3):
                await adapter._get("refmet/match/x")
        assert len(sleeps) == 2
        assert all(abs(d - 0.5) < 1e-6 for d in sleeps)
