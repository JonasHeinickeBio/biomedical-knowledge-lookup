"""Unit tests for OmicsDIAdapter (trimmed real responses, no network)."""

import copy
import json
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import omicsdi_adapter as om
from knowledge_lookup.adapters._omics_common import RequestThrottle
from knowledge_lookup.adapters.omicsdi_adapter import OmicsDIAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import omicsdi_responses as fx

pytestmark = pytest.mark.unit


class HttpError(Exception):
    """Stands in for aiohttp.ClientResponseError (only ``status`` is inspected)."""

    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


@pytest.fixture
def adapter():
    instance = OmicsDIAdapter(LookupConfig())
    instance._throttle.interval = 0
    return instance


def serve(adapter, routes):
    """Patch ``_make_request``: ``routes`` maps a URL to a payload, an exception or a callable."""
    calls = []

    async def fake(url, params=None, headers=None, json_data=None):
        calls.append((url, params))
        route = routes.get(url)
        if callable(route):
            route = route(params)
        if isinstance(route, Exception):
            raise route
        if route is None:
            raise HttpError(404)
        return copy.deepcopy(route)

    mock = AsyncMock(side_effect=fake)
    return patch.object(adapter, "_make_request", new=mock), calls


def routes_for(detail=None, similar=None, search=None):
    return {
        om.GET_URL: detail,
        om.SIMILAR_URL: similar,
        om.SEARCH_URL: search,
    }


def dump(concept):
    return json.dumps(concept.model_dump(), default=str)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.OMICSDI
        assert adapter.is_available() is True
        assert adapter.min_request_timeout == 60.0

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("geo:GSE16059", ("geo", "GSE16059")),
            ("GEO:GSE16059", ("geo", "GSE16059")),
            ("OMICSDI:pride:PXD076216", ("pride", "PXD076216")),
            ("arrayexpress:E-GEOD-16059", ("biostudies-arrayexpress", "E-GEOD-16059")),
            ("metabolights:MTBLS161", ("metabolights_dataset", "MTBLS161")),
            ("GSE16059", ("geo", "GSE16059")),
            ("PXD076216", ("pride", "PXD076216")),
            ("pad000026", ("pride", "pad000026")),
            ("MSV000090685", ("massive", "MSV000090685")),
            ("MTBLS161", ("metabolights_dataset", "MTBLS161")),
            ("ST000450", ("metabolomics_workbench", "ST000450")),
            ("E-MTAB-14669", ("biostudies-arrayexpress", "E-MTAB-14669")),
            ("S-EPMC11603833", ("biostudies-literature", "S-EPMC11603833")),
            ("PRJNA1265093", ("project", "PRJNA1265093")),
            ("EGAS00001000001", ("ega", "EGAS00001000001")),
            ("phs001327", ("dbgap", "phs001327")),
            ("PMID:34316076", None),
            ("nope:123", None),
            ("geo:", None),
            ("", None),
            ("hello world", None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert OmicsDIAdapter.normalize_id(raw) == expected

    def test_names_helper_tolerates_odd_shapes(self):
        assert om._names(5) == []
        assert om._names(None) == []
        assert om._names("Homo sapiens") == ["Homo sapiens"]
        assert om._names([{"acc": "", "name": " a "}, "a", {"name": None}, 3, ""]) == ["a"]

    def test_resolve_database(self):
        assert OmicsDIAdapter.resolve_database("ENA") == "project"
        assert OmicsDIAdapter.resolve_database("iProX") == "iprox"
        assert OmicsDIAdapter.resolve_database("unknown") is None
        assert OmicsDIAdapter.resolve_database("") is None


class TestBuildQuery:
    def test_multiword_and_special_text_become_phrases(self):
        assert OmicsDIAdapter.build_query("long covid") == '"long covid"'
        assert OmicsDIAdapter.build_query("ME/CFS") == '"ME/CFS"'
        assert OmicsDIAdapter.build_query("fatigue") == "fatigue"

    def test_phrase_off_and_lucene_passthrough(self):
        assert OmicsDIAdapter.build_query("long covid", phrase=False) == "long covid"
        assert OmicsDIAdapter.build_query("long AND covid") == "long AND covid"
        assert OmicsDIAdapter.build_query('"ME/CFS" OR "long covid"') == '"ME/CFS" OR "long covid"'
        assert OmicsDIAdapter.build_query("disease:fatigue") == "disease:fatigue"

    def test_filters(self):
        query = OmicsDIAdapter.build_query(
            "long covid",
            {
                "omics_type": "proteomics",
                "organism": "human",
                "repository": "metabolights",
                "disease": "Chronic Fatigue Syndrome",
                "tissue": ["Blood", "Plasma"],
                "ignored": "x",
                "empty": "",
            },
        )
        assert query == (
            '"long covid" AND omics_type:"Proteomics" AND TAXONOMY:9606'
            ' AND repository:"MetaboLights" AND disease:"Chronic Fatigue Syndrome"'
            ' AND (tissue:"Blood" OR tissue:"Plasma")'
        )

    def test_filter_only_and_unusable_values(self):
        assert OmicsDIAdapter.build_query("", {"omics": "Metabolomics"}) == (
            'omics_type:"Metabolomics"'
        )
        # an organism name that cannot be mapped is dropped instead of producing a bad clause
        assert OmicsDIAdapter.build_query("x", {"organism": "dragon"}) == "x"
        assert OmicsDIAdapter.build_query("x", {"tissue": [" ", None]}) == "x"
        assert (
            OmicsDIAdapter.build_query("x", {"repository": "pride"}) == 'x AND repository:"pride"'
        )
        assert (
            OmicsDIAdapter.build_query("x", {"database": "weirdo"}) == 'x AND repository:"weirdo"'
        )
        assert OmicsDIAdapter.build_query("", None) == ""


class TestSearch:
    @pytest.mark.asyncio
    async def test_hits_become_study_concepts(self, adapter):
        patcher, calls = serve(adapter, routes_for(search=fx.SEARCH_RESPONSE))
        with patcher:
            concepts = await adapter.search_concepts("chronic fatigue", limit=10)
        assert [c.primary_id for c in concepts] == [
            "metabolights_dataset:MTBLS161",
            "massive:MSV000090685",
            "metabolomics_workbench:ST000450",
            "geo:GSE16059",
            "project:PRJNA1265093",
        ]
        first = concepts[0]
        assert first.concept_type == ConceptType.STUDY
        assert first.sources == [KnowledgeSource.OMICSDI]
        assert "Metabolic profiling" in first.primary_label
        assert first.semantic_types == ["Metabolomics"]
        assert "omics:Metabolomics" in first.categories
        assert "year:2015" in first.categories
        data = first.source_data[KnowledgeSource.OMICSDI]
        assert data["publication_date"] == "2015-06-08"
        assert data["url"].startswith("https://www.omicsdi.org/dataset/metabolights_dataset/")
        # free text with a space is sent as a phrase, from offset 0
        assert calls[0][1] == {"query": '"chronic fatigue"', "size": 10, "start": 0}
        # Date.toString() and "Homo Sapiens (ncbitaxon:9606)" forms are understood
        massive = concepts[1].source_data[KnowledgeSource.OMICSDI]
        assert massive["taxon_ids"] == ["9606"]

    @pytest.mark.asyncio
    async def test_filters_reach_the_query(self, adapter):
        patcher, calls = serve(adapter, routes_for(search=fx.SEARCH_RESPONSE))
        with patcher:
            await adapter.search_datasets(
                "long covid", 3, filters={"omics_type": "transcriptomics", "organism": "9606"}
            )
        assert calls[0][1]["query"] == (
            '"long covid" AND omics_type:"Transcriptomics" AND TAXONOMY:9606'
        )
        assert calls[0][1]["size"] == 3

    @pytest.mark.asyncio
    async def test_limit_is_capped_and_zero_means_empty(self, adapter):
        patcher, calls = serve(adapter, routes_for(search={"count": 0, "datasets": []}))
        with patcher:
            assert await adapter.search_datasets("x", 0) == []
            assert calls == []
            await adapter.search_datasets("x", 5000)
        assert calls[0][1]["size"] == om.PAGE_SIZE

    @pytest.mark.asyncio
    async def test_paging(self, adapter, monkeypatch):
        monkeypatch.setattr(om, "PAGE_SIZE", 2)
        hits = [dict(fx.SEARCH_RESPONSE["datasets"][0], id=f"MTBLS{i}") for i in range(1, 6)]

        def page(params):
            return {
                "count": 5,
                "datasets": hits[params["start"] : params["start"] + params["size"]],
            }

        patcher, calls = serve(adapter, routes_for(search=page))
        with patcher:
            concepts = await adapter.search_datasets("fatigue", 5)
        assert [c.source_data[KnowledgeSource.OMICSDI]["accession"] for c in concepts] == [
            f"MTBLS{i}" for i in range(1, 6)
        ]
        assert [c[1]["start"] for c in calls] == [0, 2, 4]
        assert [c[1]["size"] for c in calls] == [2, 2, 1]

    @pytest.mark.asyncio
    async def test_stops_on_a_page_without_new_datasets(self, adapter, monkeypatch):
        monkeypatch.setattr(om, "PAGE_SIZE", 2)
        same = {"count": 9, "datasets": fx.SEARCH_RESPONSE["datasets"][:2]}
        patcher, calls = serve(adapter, routes_for(search=same))
        with patcher:
            concepts = await adapter.search_datasets("fatigue", 6)
        assert len(concepts) == 2
        assert len(calls) == 2  # the repeated page added nothing, so the loop ended

    @pytest.mark.asyncio
    async def test_incomplete_hits(self, adapter):
        hits = [
            {"id": "GSE1", "source": "geo", "title": None, "description": None},
            {"id": None, "source": "geo", "title": "no id"},
            {"id": "GSE2", "source": None, "title": "no source"},
            "junk",
        ]
        patcher, _ = serve(adapter, routes_for(search={"count": 4, "datasets": hits}))
        with patcher:
            concepts = await adapter.search_datasets("x", 10)
        assert [(c.primary_id, c.primary_label) for c in concepts] == [("geo:GSE1", "GSE1")]
        assert concepts[0].definitions == []

    @pytest.mark.asyncio
    async def test_404_means_no_result_and_errors_return_empty(self, adapter):
        patcher, _ = serve(adapter, routes_for(search=None))  # None -> HTTP 404
        with patcher:
            assert await adapter.search_concepts("zzzqqq", 5) == []
        patcher, _ = serve(adapter, routes_for(search=HttpError(500)))
        with patcher:
            assert await adapter.search_concepts("fatigue", 5) == []
        patcher, _ = serve(adapter, routes_for(search={"count": 0, "datasets": []}))
        with patcher:
            assert await adapter.search_concepts("fatigue", 5) == []
        patcher, _ = serve(adapter, routes_for(search=["not", "a", "dict"]))
        with patcher:
            assert await adapter.search_concepts("fatigue", 5) == []

    @pytest.mark.asyncio
    async def test_empty_query_and_bad_limit(self, adapter):
        assert await adapter.search_concepts("   ", 5) == []
        assert await adapter.search_concepts("fatigue", 0) == []
        assert await adapter.search_datasets("", 5) == []

    @pytest.mark.asyncio
    async def test_accession_query_resolves_to_details(self, adapter):
        patcher, calls = serve(adapter, routes_for(detail=fx.DETAIL_GEO))
        with patcher:
            concepts = await adapter.search_concepts("geo:GSE16059")
        assert [c.primary_id for c in concepts] == ["geo:GSE16059"]
        assert calls[0][0] == om.GET_URL
        patcher, _ = serve(adapter, routes_for(detail=None, search=None))
        with patcher:
            assert await adapter.search_concepts("GSE404") == []

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_empty(self, adapter):
        with patch.object(adapter, "search_datasets", side_effect=RuntimeError("boom")):
            assert await adapter.search_concepts("fatigue") == []
        with patch.object(adapter, "build_query", side_effect=RuntimeError("boom")):
            assert await adapter.search_datasets("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_geo_dataset(self, adapter):
        patcher, calls = serve(adapter, routes_for(detail=fx.DETAIL_GEO))
        with patcher:
            concept = await adapter.get_concept_details("GSE16059")
        assert calls == [(om.GET_URL, {"accession": "GSE16059", "database": "geo"})]
        assert concept.primary_id == "geo:GSE16059"
        assert concept.concept_type == ConceptType.STUDY
        data = concept.source_data[KnowledgeSource.OMICSDI]
        assert data["publication_date"] == "2009-05-12"  # from "2009/05/12"
        assert data["organisms"] == ["Homo sapiens"]
        assert data["taxon_ids"] == ["9606"]
        assert data["secondary_accessions"] == ["PRJNA115475"]
        assert data["repository"] == "GEO"
        assert data["url"] == "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE16059"
        assert "chronic fatiguing illness" in concept.definitions[0].lower()

    @pytest.mark.asyncio
    async def test_pride_dataset_has_publications_tissue_disease_and_sibling_identifier(
        self, adapter
    ):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_PRIDE))
        with patcher:
            concept = await adapter.get_concept_details("pride:PXD076216")
        data = concept.source_data[KnowledgeSource.OMICSDI]
        assert data["pmids"] == ["41932997"]
        assert data["tissues"] == ["Cerebrospinal Fluid"]
        assert data["diseases"] == ["Chronic Fatigue Syndrome"]
        assert data["experiment_types"] == ["Data-dependent acquisition", "Mass Spectrometry"]
        assert data["publication_date"] == "2026-04-06"
        assert "tissue:Cerebrospinal Fluid" in concept.categories
        assert any(
            i.source == KnowledgeSource.PRIDE and i.identifier == "PXD076216"
            for i in concept.identifiers
        )

    @pytest.mark.asyncio
    async def test_arrayexpress_catch_all_omics_types_are_not_reported(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_ARRAYEXPRESS))
        with patcher:
            concept = await adapter.get_concept_details("E-MTAB-14669")
        data = concept.source_data[KnowledgeSource.OMICSDI]
        assert data["omics_types"] == []
        assert len(data["omics_types_raw"]) == 5
        assert data["publication_date"] == "2025-02-24"  # from dates.release
        assert any(i.source == KnowledgeSource.BIOSTUDIES for i in concept.identifiers)

    @pytest.mark.asyncio
    async def test_massive_date_and_secondary_accession(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_MASSIVE))
        with patcher:
            concept = await adapter.get_concept_details("massive:MSV000090685")
        data = concept.source_data[KnowledgeSource.OMICSDI]
        assert data["publication_date"] == "2022-11-09"  # "Wed Nov 09 17:18:00 GMT 2022"
        assert data["secondary_accessions"] == ["PXD038078"]

    @pytest.mark.asyncio
    async def test_personal_data_is_never_copied(self, adapter):
        for detail in (fx.DETAIL_PRIDE, fx.DETAIL_MASSIVE, fx.DETAIL_METABOLIGHTS):
            assert any(detail.get(k) for k in ("submitterMail", "labHeadMail"))
            patcher, _ = serve(adapter, routes_for(detail=detail))
            with patcher:
                concept = await adapter.get_concept_details(f"{detail['source']}:{detail['id']}")
            text = dump(concept)
            assert "@example.org" not in text
            assert "Test Submitter" not in text
            assert "Test Labhead" not in text

    @pytest.mark.asyncio
    async def test_ena_project_falls_back_to_the_search_hit(self, adapter):
        search = {"count": 1, "datasets": [fx.SEARCH_RESPONSE["datasets"][4]]}
        patcher, calls = serve(adapter, routes_for(detail=None, search=search))
        with patcher:
            concept = await adapter.get_concept_details("PRJNA1265093")
        assert concept.primary_id == "project:PRJNA1265093"
        assert [c[0] for c in calls] == [om.GET_URL, om.SEARCH_URL]
        assert calls[1][1]["query"] == '"PRJNA1265093"'

    @pytest.mark.asyncio
    async def test_fallback_ignores_other_accessions_and_databases(self, adapter):
        wrong = dict(fx.SEARCH_RESPONSE["datasets"][4], id="PRJNA999")
        other_db = dict(fx.SEARCH_RESPONSE["datasets"][4], source="geo")
        patcher, _ = serve(
            adapter, routes_for(detail=None, search={"datasets": [wrong, other_db, "junk"]})
        )
        with patcher:
            assert await adapter.get_concept_details("project:PRJNA1265093") is None

    @pytest.mark.asyncio
    async def test_not_found_invalid_and_errors(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=HttpError(404), search=None))
        with patcher:
            assert await adapter.get_concept_details("geo:GSE404") is None
        patcher, calls = serve(adapter, routes_for())
        with patcher:
            assert await adapter.get_concept_details("not an id") is None
        assert calls == []
        patcher, _ = serve(adapter, routes_for(detail=HttpError(500), search=HttpError(500)))
        with patcher:
            assert await adapter.get_concept_details("geo:GSE1") is None
        patcher, _ = serve(adapter, routes_for(detail={"message": "Not found"}, search=None))
        with patcher:
            assert await adapter.get_concept_details("geo:GSE1") is None

    @pytest.mark.asyncio
    async def test_conversion_error_returns_none(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_GEO))
        with patcher, patch.object(adapter, "_create_concept", side_effect=RuntimeError("x")):
            assert await adapter.get_concept_details("geo:GSE16059") is None

    @pytest.mark.asyncio
    async def test_outer_failure_returns_none(self, adapter):
        with patch.object(adapter, "_load_record", side_effect=RuntimeError("boom")):
            assert await adapter.get_concept_details("geo:GSE16059") is None
            assert await adapter.get_relationships("geo:GSE16059") == []
            assert await adapter.get_mappings("geo:GSE16059") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_dataset_edges_and_similar_datasets(self, adapter):
        patcher, calls = serve(
            adapter, routes_for(detail=fx.DETAIL_PRIDE, similar=fx.SIMILAR_RESPONSE)
        )
        with patcher:
            relations = await adapter.get_relationships("pride:PXD076216")
        by_label = {}
        for r in relations:
            assert {"relation_label", "related_id", "related_name", "source"} <= set(r)
            assert r["source"] == "OMICSDI"
            by_label.setdefault(r["relation_label"], []).append(r["related_id"])
        assert by_label["has_publication"] == ["PMID:41932997"]
        assert by_label["has_organism"] == ["NCBITaxon:9606"]
        assert by_label["has_disease"] == ["OMICSDI:DISEASE:Chronic Fatigue Syndrome"]
        assert by_label["has_tissue"] == ["OMICSDI:TISSUE:Cerebrospinal Fluid"]
        assert by_label["has_omics_type"] == ["OMICSDI:OMICS_TYPE:Proteomics"]
        assert by_label["similar_to"][0] == "biostudies-arrayexpress:E-GEOD-59489"
        assert len(by_label["similar_to"]) == 5
        scores = [r["score"] for r in relations if r["relation_label"] == "similar_to"]
        assert scores[0] == pytest.approx(10.4, abs=0.01)
        assert calls[1] == (om.SIMILAR_URL, {"accession": "PXD076216", "database": "pride"})

    @pytest.mark.asyncio
    async def test_similar_is_capped_deduplicated_and_excludes_the_dataset_itself(self, adapter):
        template = fx.SIMILAR_RESPONSE["datasets"][0]
        hits = [dict(template, id="PXD076216", source="pride")]  # itself
        hits += [dict(template, id=f"GSE{i}", source="geo") for i in range(1, 16)]
        hits += [dict(template, id="GSE1", source="geo", score="bad")]
        hits += [dict(template, id="GSE99", source="geo", score=None)]
        hits += ["junk", {"id": None}]
        patcher, _ = serve(
            adapter, routes_for(detail=fx.DETAIL_PRIDE, similar={"count": 20, "datasets": hits})
        )
        with patcher:
            relations = await adapter.get_relationships("PXD076216")
        similar = [r["related_id"] for r in relations if r["relation_label"] == "similar_to"]
        assert len(similar) == om.SIMILAR_CAP
        assert "pride:PXD076216" not in similar
        assert len(set(similar)) == len(similar)

    @pytest.mark.asyncio
    async def test_bad_scores_are_left_out(self, adapter):
        hits = [
            dict(fx.SIMILAR_RESPONSE["datasets"][0], id="GSE1", source="geo", score="bad"),
            dict(fx.SIMILAR_RESPONSE["datasets"][0], id="GSE2", source="geo", score=None),
        ]
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_PRIDE, similar={"datasets": hits}))
        with patcher:
            relations = await adapter.get_relationships("PXD076216")
        similar = [r for r in relations if r["relation_label"] == "similar_to"]
        assert len(similar) == 2 and all("score" not in r for r in similar)

    @pytest.mark.asyncio
    async def test_similar_failure_keeps_the_other_edges(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_PRIDE, similar=HttpError(500)))
        with patcher:
            relations = await adapter.get_relationships("PXD076216")
        assert {r["relation_label"] for r in relations} >= {"has_publication", "has_organism"}
        assert all(r["relation_label"] != "similar_to" for r in relations)

    @pytest.mark.asyncio
    async def test_unmapped_organism_and_instruments(self, adapter):
        detail = dict(
            fx.DETAIL_PRIDE,
            organisms=[{"acc": "", "name": "Dragon species"}],
            instruments=["Orbitrap"],
        )
        patcher, _ = serve(adapter, routes_for(detail=detail, similar=None))
        with patcher:
            relations = await adapter.get_relationships("PXD076216")
        ids = {r["relation_label"]: r["related_id"] for r in relations}
        assert ids["has_organism"] == "OMICSDI:ORGANISM:Dragon species"
        assert ids["uses_instrument"] == "OMICSDI:INSTRUMENT:Orbitrap"

    @pytest.mark.asyncio
    async def test_invalid_and_missing(self, adapter):
        assert await adapter.get_relationships("PMID:1") == []
        patcher, _ = serve(adapter, routes_for(detail=None, search=None))
        with patcher:
            assert await adapter.get_relationships("geo:GSE404") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_repository_secondary_accession_pmid_and_taxon(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_MASSIVE))
        with patcher:
            mappings = await adapter.get_mappings("MSV000090685")
        assert all(
            set(m) == {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"}
            for m in mappings
        )
        triples = {(m["toSource"], m["toId"]) for m in mappings}
        assert triples == {
            ("MassIVE", "MSV000090685"),
            ("PRIDE", "PXD038078"),
            ("PubMed", "37722890"),
            ("NCBITaxon", "9606"),
        }
        assert {m["fromId"] for m in mappings} == {"massive:MSV000090685"}
        assert mappings[0]["mappingType"] == "exact"

    @pytest.mark.asyncio
    async def test_geo_secondary_accession_is_a_bioproject(self, adapter):
        patcher, _ = serve(adapter, routes_for(detail=fx.DETAIL_GEO))
        with patcher:
            mappings = await adapter.get_mappings("geo:GSE16059")
        assert ("BioProject", "PRJNA115475") in {(m["toSource"], m["toId"]) for m in mappings}
        assert OmicsDIAdapter._accession_source("XYZ1") == "secondary_accession"
        assert OmicsDIAdapter._accession_source("PXD1234") == "PRIDE"
        assert OmicsDIAdapter._accession_source("GSE1") == "GEO"
        assert OmicsDIAdapter._accession_source("E-MTAB-1") == "ArrayExpress"

    @pytest.mark.asyncio
    async def test_invalid_and_missing(self, adapter):
        assert await adapter.get_mappings("nonsense") == []
        patcher, _ = serve(adapter, routes_for(detail=None, search=None))
        with patcher:
            assert await adapter.get_mappings("geo:GSE404") == []


class TestThrottle:
    @pytest.mark.asyncio
    async def test_every_request_waits_on_the_throttle(self, adapter):
        patcher, _ = serve(
            adapter, routes_for(detail=fx.DETAIL_PRIDE, similar=fx.SIMILAR_RESPONSE)
        )
        with patcher, patch.object(RequestThrottle, "wait", new=AsyncMock()) as wait:
            await adapter.get_relationships("pride:PXD076216")
        assert wait.await_count == 2  # dataset/get + getSimilar

    def test_default_interval_stays_below_two_requests_per_second(self):
        assert OmicsDIAdapter(LookupConfig())._throttle.interval >= 0.5
