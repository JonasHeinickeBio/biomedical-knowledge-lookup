"""Unit tests for MetaboLightsAdapter (EBI Search + MetaboLights web service); no network."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.adapters import metabolights_adapter as ml
from knowledge_lookup.adapters.metabolights_adapter import MetaboLightsAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.metabolights_responses import (
    COMPOUND_MINIMAL,
    COMPOUND_MTBLC16651,
    ENTRY_COMPOUND_NAMES,
    ENTRY_MTBLS161,
    ENTRY_MTBLS3707,
    NO_HITS,
    SEARCH_COMPOUNDS_LACTATE,
    SEARCH_STUDIES_FOR_CHEBI_422,
    SEARCH_STUDIES_LONG_COVID,
    SEARCH_STUDIES_MECFS,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_throttle_delay(monkeypatch):
    monkeypatch.setattr(ml, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return MetaboLightsAdapter(lookup_config)


def router(search=None, entries=None, compounds=None, calls=None):
    """Fake ``_request``.

    ``search`` maps a query string to a payload, ``entries`` an id list (comma joined) to a
    payload, ``compounds`` an accession to a payload (``None`` is a "does not exist" answer).
    """
    search, entries, compounds = search or {}, entries or {}, compounds or {}

    async def fake(url, params=None):
        if calls is not None:
            calls.append((url, params))
        if "/entry/" in url:
            key = url.split("/entry/", 1)[1]
            value = entries[key]
        elif "/ws/compounds/" in url:
            value = compounds[url.rsplit("/", 1)[1]]
        elif url == ml.EBI_SEARCH_URL:
            value = search[params["query"]]
        else:
            raise AssertionError(f"unexpected URL {url}")
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.METABOLIGHTS
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("MTBLS161", ("study", "MTBLS161")),
            ("mtbls161", ("study", "MTBLS161")),
            ("MetaboLights:MTBLS161", ("study", "MTBLS161")),
            ("MTBLC16651", ("compound", "MTBLC16651")),
            ("MTBLC0016651", ("compound", "MTBLC16651")),
            ("CHEBI:16651", ("compound", "MTBLC16651")),
            ("chebi_422", ("compound", "MTBLC422")),
            ("lactate", None),
            ("161", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert MetaboLightsAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ME/CFS", "ME CFS"),
            ("chronic fatigue", "chronic fatigue"),
            ('"quoted" (term) a:b', "quoted term a b"),
            ("SARS-CoV-2", "SARS-CoV-2"),
            ("-lead - dash", "lead dash"),
            ("***", ""),
        ],
    )
    def test_clean_query(self, raw, expected):
        assert MetaboLightsAdapter._clean_query(raw) == expected

    def test_helpers(self):
        assert ml._iso("20150123") == "2015-01-23"
        assert ml._iso("2015") == "2015"
        assert ml._first({"fields": {}}, "name") == ""
        assert ml._unique(["A", "a", "b"]) == ["A", "b"]


class TestRequest:
    @staticmethod
    def session_returning(status, payload=None, raises=None):
        response = MagicMock()
        response.status = status
        response.raise_for_status = MagicMock(side_effect=raises)
        response.json = AsyncMock(return_value=payload)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get = MagicMock(return_value=context)
        return session

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [400, 403, 404])
    async def test_not_found_statuses_are_none_and_not_failures(self, adapter, status):
        breaker = MagicMock()
        breaker.allow_request.return_value = True
        adapter.set_circuit_breaker(breaker)
        session = self.session_returning(status)
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            assert await adapter._request("https://example.org/x") is None
        breaker.record_failure.assert_not_called()
        breaker.record_success.assert_called()
        session.get.assert_called_once()  # not retried

    @pytest.mark.asyncio
    async def test_success_returns_json(self, adapter):
        session = self.session_returning(200, {"content": 1})
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            assert await adapter._request("https://example.org/x", {"a": 1}) == {"content": 1}
        _, kwargs = session.get.call_args
        assert kwargs["params"] == {"a": 1}
        assert kwargs["headers"]["Accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_server_error_raises(self, adapter):
        session = self.session_returning(200, None, raises=RuntimeError("500"))
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            with pytest.raises(RuntimeError):
                await adapter._request("https://example.org/x")


class TestSearch:
    @pytest.mark.asyncio
    async def test_studies_only(self, adapter):
        calls = []
        search = {
            "(chronic fatigue) AND id:MTBLC*": NO_HITS,
            "(chronic fatigue) AND id:MTBLS*": SEARCH_STUDIES_MECFS,
        }
        with patch.object(adapter, "_request", router(search, calls=calls)):
            concepts = await adapter.search_concepts("chronic fatigue", limit=10)
        assert [c.primary_id for c in concepts] == ["MTBLS161"]
        study = concepts[0]
        assert study.concept_type == ConceptType.STUDY
        assert study.sources == [KnowledgeSource.METABOLIGHTS]
        assert study.identifiers[0].url == "https://www.ebi.ac.uk/metabolights/MTBLS161"
        assert study.categories == ["Homo sapiens", "Chronic Fatigue Syndrome"]
        assert study.semantic_types == ["NMR spectroscopy"]
        assert "ME/CFS" in study.definitions[0]
        assert study.source_data[KnowledgeSource.METABOLIGHTS]["release_date"] == "2015-06-08"
        assert calls[0][1]["size"] == 10 and calls[0][1]["format"] == "json"

    @pytest.mark.asyncio
    async def test_long_covid_studies_in_order(self, adapter):
        search = {
            "(long covid) AND id:MTBLC*": NO_HITS,
            "(long covid) AND id:MTBLS*": SEARCH_STUDIES_LONG_COVID,
        }
        with patch.object(adapter, "_request", router(search)):
            concepts = await adapter.search_concepts("long covid", limit=2)
        assert [c.primary_id for c in concepts] == ["MTBLS14790", "MTBLS11718"]
        assert concepts[0].confidence_score > concepts[1].confidence_score

    @pytest.mark.asyncio
    async def test_metabolites_and_studies_are_mixed(self, adapter):
        search = {
            "(lactate) AND id:MTBLC*": SEARCH_COMPOUNDS_LACTATE,
            "(lactate) AND id:MTBLS*": SEARCH_STUDIES_LONG_COVID,
        }
        with patch.object(adapter, "_request", router(search)):
            mixed = await adapter.search_concepts("lactate", limit=4)
            assert [c.primary_id for c in mixed] == [
                "MTBLC16004",
                "MTBLC16651",
                "MTBLS14790",
                "MTBLS11718",
            ]
            # with room to spare, studies do not crowd out the metabolites and vice versa
            many = await adapter.search_concepts("lactate", limit=10)
            assert len(many) == 6
            only_one = await adapter.search_concepts("lactate", limit=1)
            assert [c.primary_id for c in only_one] == ["MTBLC16004"]
        metabolite = mixed[1]
        assert metabolite.concept_type == ConceptType.METABOLITE
        assert metabolite.definitions == [
            "An optically active form of lactate having (S)-configuration."
        ]

    @pytest.mark.asyncio
    async def test_unnamed_metabolite_hits_are_skipped(self, adapter):
        unnamed = {"hitCount": 1, "entries": [{"id": "MTBLC5", "fields": {"name": []}}]}
        search = {"(x) AND id:MTBLC*": unnamed, "(x) AND id:MTBLS*": NO_HITS}
        with patch.object(adapter, "_request", router(search)):
            assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_shortfall_of_studies_is_filled_with_metabolites(self, adapter):
        search = {
            "(lactate) AND id:MTBLC*": SEARCH_COMPOUNDS_LACTATE,
            "(lactate) AND id:MTBLS*": NO_HITS,
        }
        with patch.object(adapter, "_request", router(search)):
            concepts = await adapter.search_concepts("lactate", limit=3)
        assert len(concepts) == 3 and all(c.primary_id.startswith("MTBLC") for c in concepts)

    @pytest.mark.asyncio
    async def test_operators_in_the_query_are_neutralised(self, adapter):
        calls = []
        search = {"(ME CFS) AND id:MTBLC*": NO_HITS, "(ME CFS) AND id:MTBLS*": NO_HITS}
        with patch.object(adapter, "_request", router(search, calls=calls)):
            assert await adapter.search_concepts("ME/CFS") == []
        assert [c[1]["query"] for c in calls] == [
            "(ME CFS) AND id:MTBLC*",
            "(ME CFS) AND id:MTBLS*",
        ]

    @pytest.mark.asyncio
    async def test_search_by_id_goes_to_details(self, adapter):
        with patch.object(adapter, "_request", router(entries={"MTBLS161": ENTRY_MTBLS161})):
            concepts = await adapter.search_concepts("MTBLS161")
        assert [c.primary_id for c in concepts] == ["MTBLS161"]
        with patch.object(adapter, "_request", router(entries={"MTBLS9": {"entries": []}})):
            assert await adapter.search_concepts("MTBLS9") == []

    @pytest.mark.asyncio
    async def test_empty_none_and_errors(self, adapter):
        assert await adapter.search_concepts("   ") == []
        assert await adapter.search_concepts(None) == []
        assert await adapter.search_concepts("***") == []
        assert await adapter.search_concepts("lactate", limit=0) == []
        with patch.object(adapter, "_request", AsyncMock(return_value=None)):
            assert await adapter.search_concepts("lactate") == []
        with patch.object(adapter, "_request", AsyncMock(return_value=["junk"])):
            assert await adapter.search_concepts("lactate") == []
        with patch.object(adapter, "_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("lactate") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_study(self, adapter):
        calls = []
        with patch.object(
            adapter, "_request", router(entries={"MTBLS161": ENTRY_MTBLS161}, calls=calls)
        ):
            concept = await adapter.get_concept_details("MetaboLights:MTBLS161")
        assert concept.primary_id == "MTBLS161"
        assert concept.categories == ["Homo sapiens", "Chronic Fatigue Syndrome"]
        data = concept.source_data[KnowledgeSource.METABOLIGHTS]
        assert data["dois"] == ["10.1007/s11306-015-0816-5"]
        assert data["pubmed_ids"] == []
        assert data["compound_count"] == 3  # duplicates collapsed
        assert data["instruments"] == ["Bruker"]
        assert data["submission_date"] == "2015-01-23"
        assert data["status"] == "Public"
        assert concept.confidence_score == 0.95
        assert "METABOLIGHTS" in calls[0][1]["fields"]

    @pytest.mark.asyncio
    async def test_compound(self, adapter):
        with patch.object(
            adapter, "_request", router(compounds={"MTBLC16651": COMPOUND_MTBLC16651})
        ):
            concept = await adapter.get_concept_details("CHEBI:16651")
        assert concept.primary_id == "MTBLC16651"
        assert concept.primary_label == "(S)-lactate"
        assert concept.concept_type == ConceptType.METABOLITE
        assert concept.synonyms == ["(2S)-2-hydroxypropanoate"]
        assert concept.categories == [
            "Homo sapiens",
            "Escherichia coli",
            "Salmonella typhimurium",
            "Arabidopsis thaliana",
        ]
        ids = {i.source: i.identifier for i in concept.identifiers}
        assert ids[KnowledgeSource.CHEBI] == "CHEBI:16651"
        data = concept.source_data[KnowledgeSource.METABOLIGHTS]
        assert data["inchikey"] == "JVTAAEKCZFNVCJ-REOHCLBHSA-M"
        assert data["formula"] == "C3H5O3"
        assert data["study_accessions"] == ["MTBLS8"]
        assert data["has_pathways"] is True and data["has_nmr"] is False

    @pytest.mark.asyncio
    async def test_minimal_compound_and_invalid_records(self, adapter):
        with patch.object(adapter, "_request", router(compounds={"MTBLC1": COMPOUND_MINIMAL})):
            concept = await adapter.get_concept_details("MTBLC1")
        assert concept.primary_label == "tiny"
        assert concept.synonyms == [] and concept.definitions == []
        assert [i.source for i in concept.identifiers] == [KnowledgeSource.METABOLIGHTS]
        nameless = {"content": {"accession": "MTBLC2", "name": ""}}
        with patch.object(adapter, "_request", router(compounds={"MTBLC2": nameless})):
            assert await adapter.get_concept_details("MTBLC2") is None
        no_accession = {"content": {"name": "x"}}
        with patch.object(adapter, "_request", router(compounds={"MTBLC3": no_accession})):
            assert await adapter.get_concept_details("MTBLC3") is None

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        with patch.object(adapter, "_request", router(compounds={"MTBLC99999999": None})):
            assert await adapter.get_concept_details("MTBLC99999999") is None
        with patch.object(adapter, "_request", router(entries={"MTBLS99999999": {"entries": []}})):
            assert await adapter.get_concept_details("MTBLS99999999") is None
        assert await adapter.get_concept_details("lactate") is None
        assert await adapter.get_concept_details("") is None
        with patch.object(adapter, "_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_concept_details("MTBLS161") is None
        # an entry without a title cannot become a concept
        untitled = {"entries": [{"id": "MTBLS5", "fields": {"name": []}}]}
        with patch.object(adapter, "_request", router(entries={"MTBLS5": untitled})):
            assert await adapter.get_concept_details("MTBLS5") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_compound_mappings(self, adapter):
        with patch.object(
            adapter, "_request", router(compounds={"MTBLC16651": COMPOUND_MTBLC16651})
        ):
            mappings = await adapter.get_mappings("MTBLC16651")
        assert [(m["toId"], m["toSource"], m["mappingType"]) for m in mappings] == [
            ("CHEBI:16651", "CHEBI", "exactMatch"),
            ("INCHIKEY:JVTAAEKCZFNVCJ-REOHCLBHSA-M", "INCHIKEY", "xref"),
        ]
        assert set(mappings[0]) == {
            "fromId",
            "toId",
            "fromSource",
            "toSource",
            "mappingType",
            "confidence",
        }
        assert mappings[0]["fromId"] == "MTBLC16651"
        assert mappings[0]["fromSource"] == "METABOLIGHTS"

    @pytest.mark.asyncio
    async def test_compound_without_chebi_or_inchikey_falls_back_to_accession(self, adapter):
        with patch.object(adapter, "_request", router(compounds={"MTBLC1": COMPOUND_MINIMAL})):
            mappings = await adapter.get_mappings("MTBLC1")
        assert [m["toId"] for m in mappings] == ["CHEBI:1"]

    @pytest.mark.asyncio
    async def test_study_mappings(self, adapter):
        with patch.object(adapter, "_request", router(entries={"MTBLS3707": ENTRY_MTBLS3707})):
            mappings = await adapter.get_mappings("MTBLS3707")
        assert [(m["toId"], m["toSource"]) for m in mappings] == [
            ("PMID:35021089", "PUBMED"),
            ("doi:10.1016/j.celrep.2021.110233", "DOI"),
            ("NCBITaxon:9606", "NCBITAXON"),
            ("NCBITaxon:10090", "NCBITAXON"),
        ]

    @pytest.mark.asyncio
    async def test_study_with_doi_only(self, adapter):
        with patch.object(adapter, "_request", router(entries={"MTBLS161": ENTRY_MTBLS161})):
            mappings = await adapter.get_mappings("MTBLS161")
        assert [m["toId"] for m in mappings] == ["doi:10.1007/s11306-015-0816-5"]

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        with patch.object(adapter, "_request", router(compounds={"MTBLC9": None})):
            assert await adapter.get_mappings("MTBLC9") == []
        with patch.object(adapter, "_request", router(entries={"MTBLS9": {"entries": []}})):
            assert await adapter.get_mappings("MTBLS9") == []
        assert await adapter.get_mappings("nope") == []
        with patch.object(adapter, "_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_mappings("MTBLS161") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_study_relationships(self, adapter):
        calls = []
        entries = {
            "MTBLS161": ENTRY_MTBLS161,
            "MTBLC16797,MTBLC15366,MTBLC422": ENTRY_COMPOUND_NAMES,
        }
        with patch.object(adapter, "_request", router(entries=entries, calls=calls)):
            rels = await adapter.get_relationships("MTBLS161")
        compounds = [r for r in rels if r["relation_label"] == "measures_compound"]
        assert [(r["related_id"], r["related_name"]) for r in compounds] == [
            ("MTBLC16797", "1-methylnicotinamide"),
            ("MTBLC15366", "MTBLC15366"),  # name unavailable: falls back to the id
            ("MTBLC422", "(S)-lactic acid"),
        ]
        assert compounds[0]["total_compounds"] == 3
        organisms = [r for r in rels if r["relation_label"] == "studies_organism"]
        assert [r["related_id"] for r in organisms] == ["Homo sapiens"]
        publications = [r for r in rels if r["relation_label"] == "has_publication"]
        assert [r["related_id"] for r in publications] == ["doi:10.1007/s11306-015-0816-5"]
        assert publications[0]["related_name"].startswith("Metabolic profiling reveals")
        assert all(r["source"] == "METABOLIGHTS" for r in rels)

    @pytest.mark.asyncio
    async def test_study_relationships_with_taxonomy_and_pmid(self, adapter):
        entries = {"MTBLS3707": ENTRY_MTBLS3707, "MTBLC16651": ENTRY_COMPOUND_NAMES}
        with patch.object(adapter, "_request", router(entries=entries)):
            rels = await adapter.get_relationships("MTBLS3707", limit=5)
        organisms = [r["related_id"] for r in rels if r["relation_label"] == "studies_organism"]
        assert organisms == ["NCBITaxon:9606", "NCBITaxon:10090"]
        publications = [r for r in rels if r["relation_label"] == "has_publication"]
        # the PubMed id wins over the DOI when both exist
        assert [r["related_id"] for r in publications] == ["PMID:35021089"]
        assert publications[0]["related_name"].startswith("SCP4-STK35")

    @pytest.mark.asyncio
    async def test_study_compounds_are_capped(self, adapter):
        entries = {"MTBLS161": ENTRY_MTBLS161, "MTBLC16797": ENTRY_COMPOUND_NAMES}
        with patch.object(adapter, "_request", router(entries=entries)):
            rels = await adapter.get_relationships("MTBLS161", limit=1)
        assert [r["related_id"] for r in rels if r["relation_label"] == "measures_compound"] == [
            "MTBLC16797"
        ]
        assert await adapter.get_relationships("MTBLS161", limit=0) == []

    @pytest.mark.asyncio
    async def test_study_without_compounds_makes_no_name_request(self, adapter):
        entry = copy.deepcopy(ENTRY_MTBLS161)
        entry["entries"][0]["fields"]["METABOLIGHTS"] = []
        calls = []
        with patch.object(adapter, "_request", router(entries={"MTBLS161": entry}, calls=calls)):
            rels = await adapter.get_relationships("MTBLS161")
        assert {r["relation_label"] for r in rels} == {"studies_organism", "has_publication"}
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_compound_relationships(self, adapter):
        calls = []
        search = {'"CHEBI:16651" AND id:MTBLS*': SEARCH_STUDIES_FOR_CHEBI_422}
        compounds = {"MTBLC16651": COMPOUND_MTBLC16651}
        with patch.object(adapter, "_request", router(search, compounds=compounds, calls=calls)):
            rels = await adapter.get_relationships("CHEBI:16651", limit=5)
        studies = [r for r in rels if r["relation_label"] == "measured_in_study"]
        assert [r["related_id"] for r in studies] == ["MTBLS15528", "MTBLS14089"]
        assert studies[0]["total_studies"] == 143
        assert studies[0]["related_name"].startswith("Integrated Multi-omics")
        organisms = [
            (r["related_id"], r["related_name"])
            for r in rels
            if r["relation_label"] == "found_in_organism"
        ]
        assert organisms == [
            ("Homo sapiens", "Homo sapiens"),
            ("NCBITaxon:562", "Escherichia coli"),
            ("NCBITaxon:90371", "Salmonella typhimurium"),
            ("Arabidopsis thaliana", "Arabidopsis thaliana"),
        ]
        assert calls[0][1]["size"] == 5

    @pytest.mark.asyncio
    async def test_compound_organisms_are_capped(self, adapter):
        search = {'"CHEBI:16651" AND id:MTBLS*': NO_HITS}
        compounds = {"MTBLC16651": COMPOUND_MTBLC16651}
        with patch.object(adapter, "_request", router(search, compounds=compounds)):
            rels = await adapter.get_relationships("MTBLC16651", limit=2)
        assert [r["related_name"] for r in rels] == ["Homo sapiens", "Escherichia coli"]

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        with patch.object(adapter, "_request", router(entries={"MTBLS9": {"entries": []}})):
            assert await adapter.get_relationships("MTBLS9") == []
        search = {'"CHEBI:9" AND id:MTBLS*': NO_HITS}
        with patch.object(adapter, "_request", router(search, compounds={"MTBLC9": None})):
            assert await adapter.get_relationships("MTBLC9") == []
        assert await adapter.get_relationships("nope") == []
        with patch.object(adapter, "_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_relationships("MTBLS161") == []


class TestThrottling:
    @pytest.mark.asyncio
    async def test_calls_are_spaced(self, adapter, monkeypatch):
        monkeypatch.setattr(ml, "_MIN_INTERVAL", 0.2)
        now = [10.0]
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)
            now[0] += delay

        monkeypatch.setattr(ml.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(ml, "time", SimpleNamespace(monotonic=lambda: now[0]))
        session = TestRequest.session_returning(200, {})
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            for _ in range(3):
                await adapter._request("https://example.org/x")
        assert len(sleeps) == 2
        assert all(abs(d - 0.2) < 1e-6 for d in sleeps)
