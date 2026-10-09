"""Unit tests for BioStudiesAdapter (trimmed real responses, no network)."""

import copy
import json
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import biostudies_adapter as bs
from knowledge_lookup.adapters._omics_common import RequestThrottle
from knowledge_lookup.adapters.biostudies_adapter import BioStudiesAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import biostudies_responses as fx

pytestmark = pytest.mark.unit

AE_SEARCH = f"{bs.BASE_URL}/arrayexpress/search"
ALL_SEARCH = f"{bs.BASE_URL}/search"


def study_url(accession):
    return f"{bs.BASE_URL}/studies/{accession}"


def info_url(accession):
    return f"{bs.BASE_URL}/studies/{accession}/info"


class HttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


@pytest.fixture
def adapter():
    instance = BioStudiesAdapter(LookupConfig())
    instance._throttle.interval = 0
    return instance


def serve(adapter, routes):
    """Patch ``_make_request``; unknown URLs answer 404, exceptions are raised."""
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

    return patch.object(adapter, "_make_request", new=AsyncMock(side_effect=fake)), calls


def geod_routes():
    return {
        study_url("E-GEOD-16059"): fx.STUDY_GEOD_16059,
        info_url("E-GEOD-16059"): fx.INFO_GEOD_16059,
    }


def mtab_routes():
    return {
        study_url("E-MTAB-14669"): fx.STUDY_MTAB_14669,
        info_url("E-MTAB-14669"): fx.INFO_MTAB_14669,
    }


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.BIOSTUDIES
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("E-GEOD-16059", "E-GEOD-16059"),
            (" E-MTAB-14669 ", "E-MTAB-14669"),
            ("BIOSTUDIES:E-MTAB-14669", "E-MTAB-14669"),
            ("arrayexpress:E-MEXP-31", "E-MEXP-31"),
            ("S-EPMC7260435", "S-EPMC7260435"),
            ("S-BSST123", "S-BSST123"),
            ("PMID:123", None),
            ("GSE16059", None),
            ("two words", None),
            ("", None),
        ],
    )
    def test_normalize_accession(self, raw, expected):
        assert BioStudiesAdapter.normalize_accession(raw) == expected

    def test_flatten_handles_dicts_lists_and_junk(self):
        nested = [{"a": 1}, [{"b": 2}, [{"c": 3}]], "x", None]
        assert list(bs._flatten(nested)) == [{"a": 1}, {"b": 2}, {"c": 3}]
        assert list(bs._flatten({"d": 4})) == [{"d": 4}]
        assert list(bs._flatten(None)) == []

    def test_attr_list_skips_incomplete_attributes_and_reads_term_ids(self):
        attrs = [
            {
                "name": "Study type",
                "value": "x",
                "valqual": [{"name": "TermId", "value": "EFO_1"}],
            },
            {"name": "Empty", "value": ""},
            {"value": "no name"},
            "junk",
        ]
        assert bs._attr_list(attrs) == [("Study type", "x", "EFO_1")]
        assert bs._attr_list(None) == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_defaults_to_the_arrayexpress_collection(self, adapter):
        patcher, calls = serve(adapter, {AE_SEARCH: fx.SEARCH_RESPONSE})
        with patcher:
            concepts = await adapter.search_concepts("chronic fatigue", limit=10)
        assert [c.primary_id for c in concepts] == ["E-GEOD-59489", "E-GEOD-14577", "E-GEOD-31187"]
        first = concepts[0]
        assert first.concept_type == ConceptType.STUDY
        assert first.sources == [KnowledgeSource.BIOSTUDIES]
        assert "Chronic Fatigue" in first.primary_label
        assert "collection:ArrayExpress" in first.categories
        assert "year:2014" in first.categories
        data = first.source_data[KnowledgeSource.BIOSTUDIES]
        assert data["release_date"] == "2014-08-12"
        assert data["files_count"] == 26
        assert data["links_count"] == 2
        assert data["url"] == "https://www.ebi.ac.uk/biostudies/studies/E-GEOD-59489"
        # hits carry author names only as one string: they are not copied
        assert "Test Author" not in json.dumps(first.model_dump(), default=str)
        assert calls[0][0] == AE_SEARCH
        assert calls[0][1] == {
            "query": "chronic fatigue",
            "pageSize": 10,
            "page": 1,
            "type": "study",
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

    @pytest.mark.asyncio
    async def test_all_collections_other_collection_sort_and_phrase(self, adapter):
        patcher, calls = serve(
            adapter,
            {ALL_SEARCH: fx.SEARCH_EMPTY, f"{bs.BASE_URL}/bioimages/search": fx.SEARCH_EMPTY},
        )
        with patcher:
            await adapter.search_studies("long covid", 5, collection="all")
            await adapter.search_studies(
                "long covid",
                5,
                collection="BioImages",
                sort="release_date",
                descending=False,
                phrase=True,
            )
            await adapter.search_studies("long covid", 5, collection=None, sort="bogus")
        assert calls[0][0] == ALL_SEARCH
        assert calls[1][0] == f"{bs.BASE_URL}/bioimages/search"
        assert calls[1][1]["query"] == '"long covid"'
        assert calls[1][1]["sortBy"] == "release_date"
        assert calls[1][1]["sortOrder"] == "ascending"
        assert calls[2][0] == ALL_SEARCH and calls[2][1]["sortBy"] == "relevance"

    @pytest.mark.asyncio
    async def test_phrase_leaves_lucene_syntax_alone(self, adapter):
        patcher, calls = serve(adapter, {AE_SEARCH: fx.SEARCH_EMPTY})
        with patcher:
            await adapter.search_studies("fatigue AND covid", 5, phrase=True)
        assert calls[0][1]["query"] == "fatigue AND covid"

    @pytest.mark.asyncio
    async def test_invalid_collection_is_rejected_without_a_request(self, adapter):
        patcher, calls = serve(adapter, {})
        with patcher:
            assert await adapter.search_studies("x", 5, collection="a/../b") == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_paging_is_one_based_and_stops_on_short_page(self, adapter, monkeypatch):
        monkeypatch.setattr(bs, "PAGE_SIZE", 2)
        hits = [dict(fx.SEARCH_RESPONSE["hits"][0], accession=f"E-MTAB-{i}") for i in range(1, 6)]

        def page(params):
            lo = (params["page"] - 1) * params["pageSize"]
            return {"hits": hits[lo : lo + params["pageSize"]], "totalHits": 5}

        patcher, calls = serve(adapter, {AE_SEARCH: page})
        with patcher:
            concepts = await adapter.search_studies("x", 5)
        assert [c.primary_id for c in concepts] == [f"E-MTAB-{i}" for i in range(1, 6)]
        assert [c[1]["page"] for c in calls] == [1, 2, 3]
        assert [c[1]["pageSize"] for c in calls] == [2, 2, 2]  # page numbers need a fixed size

    @pytest.mark.asyncio
    async def test_limit_capped_zero_and_duplicates(self, adapter):
        dup = {"hits": fx.SEARCH_RESPONSE["hits"][:1] * 3, "totalHits": 3}
        patcher, calls = serve(adapter, {AE_SEARCH: dup})
        with patcher:
            assert await adapter.search_studies("x", 0) == []
            assert calls == []
            concepts = await adapter.search_studies("x", 5000)
        assert len(concepts) == 1
        assert calls[0][1]["pageSize"] == bs.PAGE_SIZE

    @pytest.mark.asyncio
    async def test_empty_unknown_and_failing_searches(self, adapter):
        for response in (fx.SEARCH_EMPTY, None, HttpError(500), ["x"], {"hits": "bad"}):
            patcher, _ = serve(adapter, {AE_SEARCH: response})
            with patcher:
                assert await adapter.search_concepts("zzzqqq", 5) == []
        assert await adapter.search_concepts("  ", 5) == []
        assert await adapter.search_concepts("fatigue", 0) == []

    @pytest.mark.asyncio
    async def test_hits_without_accession_are_skipped(self, adapter):
        hits = {"hits": [{"title": "no accession"}, "junk", {"accession": "E-MTAB-1"}]}
        patcher, _ = serve(adapter, {AE_SEARCH: hits})
        with patcher:
            concepts = await adapter.search_studies("x", 5)
        assert [(c.primary_id, c.primary_label) for c in concepts] == [("E-MTAB-1", "E-MTAB-1")]

    @pytest.mark.asyncio
    async def test_accession_query_resolves_to_details(self, adapter):
        patcher, calls = serve(adapter, geod_routes())
        with patcher:
            concepts = await adapter.search_concepts("E-GEOD-16059")
        assert [c.primary_id for c in concepts] == ["E-GEOD-16059"]
        assert calls[0][0] == study_url("E-GEOD-16059")
        patcher, _ = serve(adapter, {})
        with patcher:
            assert await adapter.search_concepts("E-GEOD-404") == []

    @pytest.mark.asyncio
    async def test_unexpected_exceptions_return_empty(self, adapter):
        with patch.object(adapter, "search_studies", side_effect=RuntimeError("boom")):
            assert await adapter.search_concepts("fatigue") == []
        with patch.object(adapter, "_request", side_effect=RuntimeError("boom")):
            assert await adapter.search_studies("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_arrayexpress_study(self, adapter):
        patcher, calls = serve(adapter, geod_routes())
        with patcher:
            concept = await adapter.get_concept_details("E-GEOD-16059")
        assert [c[0] for c in calls] == [study_url("E-GEOD-16059"), info_url("E-GEOD-16059")]
        assert concept.primary_id == "E-GEOD-16059"
        assert concept.concept_type == ConceptType.STUDY
        assert concept.primary_label.startswith("Gene Expression in Peripheral Blood")
        assert "peripheral blood leukocytes" in concept.definitions[0].lower()
        assert concept.semantic_types == ["transcription profiling by array"]
        data = concept.source_data[KnowledgeSource.BIOSTUDIES]
        assert data["collection"] == "ArrayExpress"
        assert data["release_date"] == "2009-05-12"
        assert data["organisms"] == ["Homo sapiens"]
        assert data["taxon_ids"] == ["9606"]
        assert data["technologies"] == ["Array assay"]
        assert data["assay_molecules"] == ["RNA assay"]
        assert data["sample_count"] == 88
        assert data["authors_count"] == 3
        assert data["files_count"] == 178
        assert data["files_url"].startswith("https://ftp.ebi.ac.uk/biostudies/")
        assert data["publications"][0]["pmid"] == "19503787"
        assert data["publications"][0]["doi"] == "10.1371/journal.pone.0005805"
        assert data["links"] == [{"url": "GSE16059", "type": "GEO"}]
        assert any(
            i.source == KnowledgeSource.OMICSDI
            and i.identifier == "biostudies-arrayexpress:E-GEOD-16059"
            for i in concept.identifiers
        )

    @pytest.mark.asyncio
    async def test_author_names_and_emails_are_never_copied(self, adapter):
        patcher, _ = serve(adapter, geod_routes())
        with patcher:
            concept = await adapter.get_concept_details("E-GEOD-16059")
        text = json.dumps(concept.model_dump(), default=str)
        assert "@example.org" not in text
        assert "Test Author" not in text
        assert "Author A" not in text  # publication author list

    @pytest.mark.asyncio
    async def test_study_without_publication_doi_or_pmid(self, adapter):
        patcher, _ = serve(adapter, mtab_routes())
        with patcher:
            concept = await adapter.get_concept_details("BIOSTUDIES:E-MTAB-14669")
        data = concept.source_data[KnowledgeSource.BIOSTUDIES]
        assert "publications" not in data  # empty values are omitted
        assert data["links"] == [{"url": "ERP166883", "type": "ENA"}]
        assert data["authors_count"] == 3
        assert data["files_count"] == 10
        assert data["release_date"] == "2025-02-24"

    @pytest.mark.asyncio
    async def test_info_failure_still_returns_the_study(self, adapter):
        routes = {study_url("E-GEOD-16059"): fx.STUDY_GEOD_16059}  # info answers 404
        patcher, _ = serve(adapter, routes)
        with patcher:
            concept = await adapter.get_concept_details("E-GEOD-16059")
        data = concept.source_data[KnowledgeSource.BIOSTUDIES]
        assert "files_count" not in data and data["release_date"] == "2009-05-12"

    @pytest.mark.asyncio
    async def test_release_date_falls_back_to_info(self, adapter):
        study = copy.deepcopy(fx.STUDY_GEOD_16059)
        study["attributes"] = [a for a in study["attributes"] if a["name"] != "ReleaseDate"]
        routes = {
            study_url("E-GEOD-16059"): study,
            info_url("E-GEOD-16059"): fx.INFO_GEOD_16059,
        }
        patcher, _ = serve(adapter, routes)
        with patcher:
            concept = await adapter.get_concept_details("E-GEOD-16059")
        assert concept.source_data[KnowledgeSource.BIOSTUDIES]["release_date"] == "2009-05-12"

    @pytest.mark.asyncio
    async def test_not_found_invalid_and_errors(self, adapter):
        patcher, _ = serve(adapter, {})
        with patcher:
            assert await adapter.get_concept_details("E-XXXX-0000000") is None
        patcher, calls = serve(adapter, {})
        with patcher:
            assert await adapter.get_concept_details("not an id") is None
        assert calls == []
        patcher, _ = serve(adapter, {study_url("E-GEOD-1"): HttpError(500)})
        with patcher:
            assert await adapter.get_concept_details("E-GEOD-1") is None
        patcher, _ = serve(adapter, {study_url("E-GEOD-1"): {"errorMessage": "Study not found"}})
        with patcher:
            assert await adapter.get_concept_details("E-GEOD-1") is None

    @pytest.mark.asyncio
    async def test_odd_study_shapes_do_not_raise(self, adapter):
        weird = {
            "accno": "S-BSST1",
            "attributes": [{"name": "Title", "value": "A study"}],
            "section": {
                "attributes": [
                    {"name": "Disease", "value": "ME/CFS"},
                    {"name": "Organism", "value": "Mus musculus"},
                ],
                "subsections": [
                    [
                        {
                            "type": "Publication",
                            "accno": "PMC1",
                            "attributes": [{"name": "DOI", "value": "bad"}],
                        }
                    ],
                    {
                        "type": "Publication",
                        "accno": "123",
                        "attributes": [],
                        "links": [
                            {
                                "url": "10.1000/xyz",
                                "attributes": [{"name": "Type", "value": "DOI"}],
                            }
                        ],
                    },
                    {"type": "Samples", "attributes": [{"name": "Sample count", "value": "many"}]},
                    "junk",
                ],
                "links": [
                    {"url": ""},
                    {"url": "E-MTAB-1"},
                    {"url": "SAMEA1", "attributes": [{"name": "Type", "value": "BioSamples"}]},
                ],
            },
        }
        patcher, _ = serve(adapter, {study_url("S-BSST1"): weird})
        with patcher:
            concept = await adapter.get_concept_details("S-BSST1")
            relations = await adapter.get_relationships("S-BSST1")
        data = concept.source_data[KnowledgeSource.BIOSTUDIES]
        assert data["diseases"] == ["ME/CFS"]
        assert data["publications"] == [{"pmid": "123", "doi": "10.1000/xyz", "title": None}]
        assert "sample_count" not in data
        labels = {(r["relation_label"], r["related_id"]) for r in relations}
        assert ("linked_study", "E-MTAB-1") in labels
        assert ("has_biosample", "BioSamples:SAMEA1") in labels
        assert ("has_organism", "NCBITaxon:10090") in labels

    @pytest.mark.asyncio
    async def test_conversion_and_outer_errors(self, adapter):
        patcher, _ = serve(adapter, geod_routes())
        with patcher, patch.object(adapter, "_create_concept", side_effect=RuntimeError("x")):
            assert await adapter.get_concept_details("E-GEOD-16059") is None
        with patch.object(adapter, "_load_record", side_effect=RuntimeError("boom")):
            assert await adapter.get_concept_details("E-GEOD-16059") is None
            assert await adapter.get_relationships("E-GEOD-16059") == []
            assert await adapter.get_mappings("E-GEOD-16059") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_edges_of_an_arrayexpress_study(self, adapter):
        patcher, _ = serve(adapter, geod_routes())
        with patcher:
            relations = await adapter.get_relationships("E-GEOD-16059")
        for r in relations:
            assert {"relation_label", "related_id", "related_name", "source"} <= set(r)
            assert r["source"] == "BIOSTUDIES"
        edges = {(r["relation_label"], r["related_id"]) for r in relations}
        assert edges == {
            ("has_publication", "PMID:19503787"),
            ("has_organism", "NCBITaxon:9606"),
            ("has_experiment_type", "EFO:0002768"),
            ("uses_technology", "BIOSTUDIES:TECHNOLOGY:Array assay"),
            ("has_assay_molecule", "BIOSTUDIES:ASSAY_MOLECULE:RNA assay"),
            ("has_geo_series", "GEO:GSE16059"),
        }
        pub = next(r for r in relations if r["relation_label"] == "has_publication")
        assert pub["doi"] == "10.1371/journal.pone.0005805"

    @pytest.mark.asyncio
    async def test_ena_link_and_missing(self, adapter):
        patcher, _ = serve(adapter, mtab_routes())
        with patcher:
            relations = await adapter.get_relationships("E-MTAB-14669")
        assert ("has_ena_project", "ENA:ERP166883") in {
            (r["relation_label"], r["related_id"]) for r in relations
        }
        patcher, _ = serve(adapter, {})
        with patcher:
            assert await adapter.get_relationships("E-MTAB-0") == []
        assert await adapter.get_relationships("nonsense") == []

    def test_doi_only_publication_and_unknown_link_types(self):
        record = {
            "publications": [
                {"pmid": None, "doi": "10.1/x", "title": None},
                {"pmid": None, "doi": None},
            ],
            "organisms": ["Unknown organism"],
            "study_types": [{"name": "RNA-seq", "term_id": None}],
            "technologies": [],
            "assay_molecules": [],
            "links": [{"url": "XYZ1", "type": "Custom"}, {"url": "PRJNA1", "type": ""}],
        }
        edges = {
            (r["relation_label"], r["related_id"])
            for r in BioStudiesAdapter._record_relationships(record)
        }
        assert ("has_publication", "DOI:10.1/x") in edges
        assert ("has_organism", "BIOSTUDIES:ORGANISM:Unknown organism") in edges
        assert ("has_experiment_type", "BIOSTUDIES:EXPERIMENT_TYPE:RNA-seq") in edges
        assert ("has_external_record", "Custom:XYZ1") in edges
        assert ("has_external_record", "link:PRJNA1") in edges


class TestMappings:
    @pytest.mark.asyncio
    async def test_accession_pmid_doi_and_geo(self, adapter):
        patcher, _ = serve(adapter, geod_routes())
        with patcher:
            mappings = await adapter.get_mappings("E-GEOD-16059")
        assert all(
            set(m) == {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"}
            for m in mappings
        )
        triples = {(m["toSource"], m["toId"], m["mappingType"]) for m in mappings}
        assert triples == {
            ("ArrayExpress", "E-GEOD-16059", "exact"),
            ("PubMed", "19503787", "related"),
            ("DOI", "10.1371/journal.pone.0005805", "related"),
            ("GEO", "GSE16059", "exact"),
        }
        assert {m["fromId"] for m in mappings} == {"E-GEOD-16059"}

    @pytest.mark.asyncio
    async def test_other_collection_and_unknown_links(self, adapter):
        study = copy.deepcopy(fx.STUDY_MTAB_14669)
        study["attributes"] = [a for a in study["attributes"] if a["name"] != "AttachTo"]
        study["section"]["links"] = [
            [
                {"url": "ERP1", "attributes": [{"name": "Type", "value": "ENA"}]},
                {"url": "weird", "attributes": [{"name": "Type", "value": "Other"}]},
            ]
        ]
        patcher, _ = serve(adapter, {study_url("E-MTAB-14669"): study})
        with patcher:
            mappings = await adapter.get_mappings("E-MTAB-14669")
        triples = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("BioStudies", "E-MTAB-14669") in triples
        assert ("ENA", "ERP1") in triples
        assert not any(t[1] == "weird" for t in triples)

    @pytest.mark.asyncio
    async def test_invalid_and_missing(self, adapter):
        assert await adapter.get_mappings("nonsense") == []
        patcher, _ = serve(adapter, {})
        with patcher:
            assert await adapter.get_mappings("E-MTAB-0") == []


class TestThrottle:
    @pytest.mark.asyncio
    async def test_every_request_waits_on_the_throttle(self, adapter):
        patcher, _ = serve(adapter, geod_routes())
        with patcher, patch.object(RequestThrottle, "wait", new=AsyncMock()) as wait:
            await adapter.get_concept_details("E-GEOD-16059")
        assert wait.await_count == 2  # studies/<acc> + studies/<acc>/info

    def test_default_interval_stays_below_two_requests_per_second(self):
        assert BioStudiesAdapter(LookupConfig())._throttle.interval >= 0.5
