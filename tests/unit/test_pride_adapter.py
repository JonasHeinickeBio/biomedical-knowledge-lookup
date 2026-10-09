"""Unit tests for PRIDEAdapter (trimmed real responses, no network)."""

import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.adapters import pride_adapter as pr
from knowledge_lookup.adapters._omics_common import RequestThrottle
from knowledge_lookup.adapters.pride_adapter import PRIDEAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import pride_responses as fx

pytestmark = pytest.mark.unit


def project_url(accession):
    return pr.PROJECT_URL.format(accession=accession)


class HttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


@pytest.fixture
def adapter():
    instance = PRIDEAdapter(LookupConfig())
    instance._throttle.interval = 0
    return instance


def serve(adapter, routes):
    """Patch ``_make_request_text`` (PRIDE answers text/plain for project records).

    A route is a payload (serialised to JSON text, like the real service), a callable on the
    request params, a raw ``str`` (sent as is) or an exception; unknown URLs answer 404.
    """
    calls = []

    async def fake(url, params=None, headers=None):
        calls.append((url, params))
        route = routes.get(url)
        if callable(route):
            route = route(params)
        if isinstance(route, Exception):
            raise route
        if route is None:
            raise HttpError(404)
        return route if isinstance(route, str) else json.dumps(copy.deepcopy(route))

    return patch.object(adapter, "_make_request_text", new=AsyncMock(side_effect=fake)), calls


def with_files(adapter, count=36):
    return patch.object(adapter, "_file_count", new=AsyncMock(return_value=count))


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.PRIDE
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("PXD076216", "PXD076216"),
            ("pxd076216", "PXD076216"),
            ("PRIDE:PXD076216", "PXD076216"),
            (" PAD000026 ", "PAD000026"),
            ("RPXD012345", "RPXD012345"),
            ("PXD1", None),
            ("MSV000090685", None),
            ("fatigue", None),
            ("", None),
        ],
    )
    def test_normalize_accession(self, raw, expected):
        assert PRIDEAdapter.normalize_accession(raw) == expected

    def test_build_filter(self):
        assert PRIDEAdapter.build_filter({"disease": "Chronic fatigue syndrome"}) == (
            "diseases==Chronic fatigue syndrome"
        )
        assert (
            PRIDEAdapter.build_filter(
                {"species": ["Homo sapiens (human)", "x"], "tissue": "Blood plasma", "bogus": "y"}
            )
            == "organisms==Homo sapiens (human),organismsPart==Blood plasma"
        )
        assert PRIDEAdapter.build_filter({"disease": "", "tissue": [], "species": None}) is None
        assert PRIDEAdapter.build_filter(None) is None

    def test_term_helpers(self):
        assert pr._terms("bad") == []
        terms = pr._terms(["Blood plasma", "blood plasma", {"name": "X", "accession": "BTO:1"}, 5])
        assert terms == [{"name": "Blood plasma", "id": None}, {"name": "X", "id": "BTO:1"}]
        assert pr._strings(["a", "a", 3, " b "]) == ["a", "b"]
        assert pr._strings("a") == []
        assert pr._cv_id({"name": "h", "id": "NEWT:9606"}) == "NCBITaxon:9606"
        assert pr._cv_id({"name": "h", "id": "DOID:8544"}) == "DOID:8544"
        assert pr._cv_id({"name": "h", "id": None}) is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_hits_become_study_concepts(self, adapter):
        patcher, calls = serve(adapter, {pr.SEARCH_URL: fx.SEARCH_RESPONSE})
        with patcher:
            concepts = await adapter.search_concepts("fatigue", limit=10)
        assert [c.primary_id for c in concepts] == ["PXD076216", "PXD073644", "PAD000026"]
        first = concepts[0]
        assert first.concept_type == ConceptType.STUDY
        assert first.sources == [KnowledgeSource.PRIDE]
        assert "ME/CFS" in first.primary_label
        assert "disease:Chronic fatigue syndrome" in first.categories
        assert "tissue:Cerebrospinal fluid" in first.categories
        assert "species:Homo sapiens (human)" in first.categories
        assert "year:2026" in first.categories
        assert "Data-dependent acquisition" in first.semantic_types
        data = first.source_data[KnowledgeSource.PRIDE]
        assert data["pmids"] == ["41932997"]
        assert data["dois"] == ["10.1038/s41598-026-46965-1"]
        assert data["publication_date"] == "2026-04-05"
        assert data["files_count"] == 3
        assert data["url"] == "https://www.ebi.ac.uk/pride/archive/projects/PXD076216"
        assert data["affiliations"]
        # first page, 0-based; keyword goes to search/projects (projects?keyword= is ignored)
        assert calls[0] == (
            pr.SEARCH_URL,
            {"keyword": "fatigue", "pageSize": 10, "page": 0},
        )

    @pytest.mark.asyncio
    async def test_pubmed_zero_means_no_pmid(self, adapter):
        patcher, _ = serve(adapter, {pr.SEARCH_URL: fx.SEARCH_RESPONSE})
        with patcher:
            concepts = await adapter.search_projects("fatigue", 5)
        affinity = concepts[2].source_data[KnowledgeSource.PRIDE]  # PAD000026 has pubMed:0 too
        assert affinity["pmids"] == ["41785863"]
        assert affinity["dois"] == ["10.1016/j.xcrm.2026.102647", "10.2139/SSRN.5284518"]
        assert affinity["dataset_doi"] == "10.6019/PAD000026"

    @pytest.mark.asyncio
    async def test_filters_and_sort_reach_the_request(self, adapter):
        patcher, calls = serve(adapter, {pr.SEARCH_URL: fx.SEARCH_EMPTY})
        with patcher:
            await adapter.search_projects(
                "fatigue",
                5,
                filters={"disease": "Chronic fatigue syndrome"},
                sort="submission_date",
                descending=False,
            )
            await adapter.search_projects("fatigue", 5, sort="publication_date")
            await adapter.search_projects("fatigue", 5, sort="bogus")
        assert calls[0][1]["filter"] == "diseases==Chronic fatigue syndrome"
        assert calls[0][1]["sortConditions"] == "submissionDate"
        assert calls[0][1]["sortDirection"] == "ASC"
        assert calls[1][1]["sortConditions"] == "publicationDate"
        assert calls[1][1]["sortDirection"] == "DESC"
        assert "sortConditions" not in calls[2][1] and "filter" not in calls[2][1]

    @pytest.mark.asyncio
    async def test_paging_is_zero_based_with_constant_page_size(self, adapter, monkeypatch):
        monkeypatch.setattr(pr, "PAGE_SIZE", 2)
        projects = [dict(fx.SEARCH_RESPONSE[0], accession=f"PXD00000{i}") for i in range(1, 6)]

        def page(params):
            lo = params["page"] * params["pageSize"]
            return projects[lo : lo + params["pageSize"]]

        patcher, calls = serve(adapter, {pr.SEARCH_URL: page})
        with patcher:
            concepts = await adapter.search_projects("fatigue", 5)
        assert [c.primary_id for c in concepts] == [f"PXD00000{i}" for i in range(1, 6)]
        assert [c[1]["page"] for c in calls] == [0, 1, 2]
        assert {c[1]["pageSize"] for c in calls} == {2}

    @pytest.mark.asyncio
    async def test_limit_zero_cap_duplicates_and_empty_inputs(self, adapter):
        dup = fx.SEARCH_RESPONSE[:1] * 3
        patcher, calls = serve(adapter, {pr.SEARCH_URL: dup})
        with patcher:
            assert await adapter.search_projects("x", 0) == []
            assert await adapter.search_projects("   ", 5) == []
            assert calls == []
            concepts = await adapter.search_projects("x", 5000)
        assert len(concepts) == 1
        assert calls[0][1]["pageSize"] == pr.PAGE_SIZE
        assert await adapter.search_concepts("", 5) == []
        assert await adapter.search_concepts("fatigue", 0) == []

    @pytest.mark.asyncio
    async def test_empty_failing_and_odd_responses(self, adapter):
        for response in (fx.SEARCH_EMPTY, None, HttpError(500), {"not": "a list"}, "not json{"):
            patcher, _ = serve(adapter, {pr.SEARCH_URL: response})
            with patcher:
                assert await adapter.search_concepts("zzzqqq", 5) == []

    @pytest.mark.asyncio
    async def test_hits_without_accession_are_skipped(self, adapter):
        payload = [{"title": "no accession"}, "junk", {"accession": "pxd000001"}]
        patcher, _ = serve(adapter, {pr.SEARCH_URL: payload})
        with patcher:
            concepts = await adapter.search_projects("x", 5)
        assert [(c.primary_id, c.primary_label) for c in concepts] == [("PXD000001", "PXD000001")]

    @pytest.mark.asyncio
    async def test_accession_query_resolves_to_details(self, adapter):
        patcher, calls = serve(adapter, {project_url("PXD076216"): fx.DETAIL_PXD076216})
        with patcher, with_files(adapter):
            concepts = await adapter.search_concepts("PXD076216")
        assert [c.primary_id for c in concepts] == ["PXD076216"]
        assert calls[0][0] == project_url("PXD076216")
        patcher, _ = serve(adapter, {})
        with patcher, with_files(adapter):
            assert await adapter.search_concepts("PXD999999") == []

    @pytest.mark.asyncio
    async def test_unexpected_exceptions_return_empty(self, adapter):
        with patch.object(adapter, "search_projects", side_effect=RuntimeError("boom")):
            assert await adapter.search_concepts("fatigue") == []
        with patch.object(adapter, "_request", side_effect=RuntimeError("boom")):
            assert await adapter.search_projects("fatigue") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_project_with_cv_terms_and_file_count(self, adapter):
        patcher, calls = serve(adapter, {project_url("PXD076216"): fx.DETAIL_PXD076216})
        with patcher, with_files(adapter, 36) as files:
            concept = await adapter.get_concept_details("PRIDE:pxd076216")
        files.assert_awaited_once_with("PXD076216")
        assert calls == [(project_url("PXD076216"), None)]
        assert concept.primary_id == "PXD076216"
        assert concept.concept_type == ConceptType.STUDY
        assert "ME/CFS" in concept.primary_label
        assert "cerebrospinal fluid" in concept.definitions[0].lower()
        assert "Me/cfs" in concept.synonyms  # project keywords
        data = concept.source_data[KnowledgeSource.PRIDE]
        assert data["species"] == [{"name": "Homo sapiens (human)", "id": "NEWT:9606"}]
        assert data["taxon_ids"] == ["9606"]
        assert data["tissues"][0]["id"] == "BTO:0000237"
        assert data["diseases"][0]["id"] == "DOID:8544"
        assert data["instruments"][0] == {"name": "Q Exactive", "id": "MS:1001911"}
        assert [m["id"] for m in data["modifications"]][0] == "MOD:00425"
        assert data["license"] == "Creative Commons Public Domain (CC0)"
        assert data["files_count"] == 36
        assert data["submission_date"] == "2026-03-27"
        assert data["software"] == ["MaxQuant"]
        assert any(
            i.source == KnowledgeSource.OMICSDI and i.identifier == "pride:PXD076216"
            for i in concept.identifiers
        )

    @pytest.mark.asyncio
    async def test_dataset_doi_and_tissue_without_disease(self, adapter):
        patcher, _ = serve(adapter, {project_url("PXD001357"): fx.DETAIL_PXD001357})
        with patcher, with_files(adapter, None):
            concept = await adapter.get_concept_details("PXD001357")
        data = concept.source_data[KnowledgeSource.PRIDE]
        assert data["dataset_doi"] == "10.6019/PXD001357"
        assert "files_count" not in data and "diseases" not in data
        assert data["license"] == "EBI terms of use"

    @pytest.mark.asyncio
    async def test_submitter_and_lab_head_details_are_never_copied(self, adapter):
        for fixture in (fx.DETAIL_PXD076216, fx.DETAIL_PXD001357):
            assert fixture["submitters"][0]["email"] and fixture["labPIs"][0]["email"]
            patcher, _ = serve(adapter, {project_url(fixture["accession"]): fixture})
            with patcher, with_files(adapter):
                concept = await adapter.get_concept_details(fixture["accession"])
            text = json.dumps(concept.model_dump(), default=str)
            for forbidden in ("@example.org", "Test Submitter", "Test Labhead", "0000-0000"):
                assert forbidden not in text
        patcher, _ = serve(adapter, {pr.SEARCH_URL: fx.SEARCH_RESPONSE})
        with patcher:
            concepts = await adapter.search_projects("fatigue", 3)
        assert all(
            "Test Submitter" not in json.dumps(c.model_dump(), default=str) for c in concepts
        )

    @pytest.mark.asyncio
    async def test_not_found_invalid_and_errors(self, adapter):
        patcher, _ = serve(adapter, {})
        with patcher, with_files(adapter):
            assert await adapter.get_concept_details("PXD000000") is None
        patcher, calls = serve(adapter, {})
        with patcher:
            assert await adapter.get_concept_details("fatigue") is None
        assert calls == []
        patcher, _ = serve(adapter, {project_url("PXD000001"): HttpError(500)})
        with patcher:
            assert await adapter.get_concept_details("PXD000001") is None
        patcher, _ = serve(adapter, {project_url("PXD000001"): ["not", "a", "dict"]})
        with patcher:
            assert await adapter.get_concept_details("PXD000001") is None

    @pytest.mark.asyncio
    async def test_conversion_and_outer_errors(self, adapter):
        patcher, _ = serve(adapter, {project_url("PXD076216"): fx.DETAIL_PXD076216})
        with (
            patcher,
            with_files(adapter),
            patch.object(adapter, "_create_concept", side_effect=RuntimeError("x")),
        ):
            assert await adapter.get_concept_details("PXD076216") is None
        with patch.object(adapter, "_load_record", side_effect=RuntimeError("boom")):
            assert await adapter.get_concept_details("PXD076216") is None
            assert await adapter.get_relationships("PXD076216") == []
            assert await adapter.get_mappings("PXD076216") == []


class TestFileCount:
    @staticmethod
    def fake_session(headers, status_error=None):
        response = MagicMock()
        response.headers = headers
        response.raise_for_status = MagicMock(side_effect=status_error)
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=response)
        manager.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get = MagicMock(return_value=manager)
        return session

    @pytest.mark.asyncio
    async def test_reads_total_records_header_of_a_one_row_listing(self, adapter):
        session = self.fake_session({"total_records": "36"})
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            assert await adapter._file_count("PXD076216") == 36
        url = session.get.call_args.args[0]
        assert url.endswith("/projects/PXD076216/files")
        assert session.get.call_args.kwargs["params"] == {"pageSize": 1, "page": 0}

    @pytest.mark.asyncio
    async def test_missing_header_and_errors_give_none(self, adapter):
        session = self.fake_session({})
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            assert await adapter._file_count("PXD076216") is None
        session = self.fake_session({"total_records": "x"}, status_error=HttpError(404))
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            assert await adapter._file_count("PXD076216") is None

    @pytest.mark.asyncio
    async def test_non_integer_result_is_ignored(self, adapter):
        with patch.object(adapter, "_call_with_retry", new=AsyncMock(return_value="36")):
            assert await adapter._file_count("PXD076216") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_cv_annotated_edges(self, adapter):
        patcher, calls = serve(adapter, {project_url("PXD076216"): fx.DETAIL_PXD076216})
        with patcher:
            relations = await adapter.get_relationships("PXD076216")
        assert len(calls) == 1  # no file-count request for relationships
        for r in relations:
            assert {"relation_label", "related_id", "related_name", "source"} <= set(r)
            assert r["source"] == "PRIDE"
        edges = {(r["relation_label"], r["related_id"]) for r in relations}
        assert {
            ("has_species", "NCBITaxon:9606"),
            ("has_tissue", "BTO:0000237"),
            ("has_disease", "DOID:8544"),
            ("uses_instrument", "MS:1001911"),
            ("has_modification", "MOD:00394"),
            ("has_experiment_type", "PRIDE:0000627"),
            ("has_publication", "PMID:41932997"),
        } <= edges
        pub = next(r for r in relations if r["relation_label"] == "has_publication")
        assert pub["doi"] == "10.1038/s41598-026-46965-1"

    @pytest.mark.asyncio
    async def test_terms_without_accessions_and_doi_only_publication(self, adapter):
        detail = {
            "accession": "PXD000001",
            "title": "t",
            "organisms": [{"name": "Homo sapiens (human)"}, {"name": "Dragon"}],
            "diseases": [{"name": "Some disease"}],
            "references": [{"pubmedID": 0, "doi": "10.1/x"}, {"pubmedID": 5, "doi": ""}],
        }
        patcher, _ = serve(adapter, {project_url("PXD000001"): detail})
        with patcher:
            relations = await adapter.get_relationships("PXD000001")
        edges = {(r["relation_label"], r["related_id"]) for r in relations}
        assert ("has_species", "NCBITaxon:9606") in edges  # from the name table
        assert ("has_species", "PRIDE:SPECIES:Dragon") in edges
        assert ("has_disease", "PRIDE:DISEASE:Some disease") in edges
        assert ("has_publication", "DOI:10.1/x") in edges
        assert ("has_publication", "PMID:5") in edges

    @pytest.mark.asyncio
    async def test_invalid_and_missing(self, adapter):
        assert await adapter.get_relationships("nonsense") == []
        patcher, _ = serve(adapter, {})
        with patcher:
            assert await adapter.get_relationships("PXD000000") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_pxd_doi_pmid_and_taxonomy(self, adapter):
        patcher, _ = serve(adapter, {project_url("PXD001357"): fx.DETAIL_PXD001357})
        with patcher:
            mappings = await adapter.get_mappings("PXD001357")
        assert all(
            set(m) == {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"}
            for m in mappings
        )
        triples = {(m["toSource"], m["toId"], m["mappingType"]) for m in mappings}
        assert triples == {
            ("PRIDE", "PXD001357", "exact"),
            ("DOI", "10.6019/PXD001357", "exact"),
            ("PubMed", "25429530", "related"),
            ("DOI", "10.1038/srep07104", "related"),
            ("NCBITaxon", "9606", "related"),
        }
        assert {m["fromId"] for m in mappings} == {"PXD001357"}

    @pytest.mark.asyncio
    async def test_invalid_and_missing(self, adapter):
        assert await adapter.get_mappings("nonsense") == []
        patcher, _ = serve(adapter, {})
        with patcher:
            assert await adapter.get_mappings("PXD000000") == []


class TestThrottle:
    @pytest.mark.asyncio
    async def test_every_request_waits_on_the_throttle(self, adapter):
        patcher, _ = serve(adapter, {project_url("PXD076216"): fx.DETAIL_PXD076216})
        session = TestFileCount.fake_session({"total_records": "3"})
        with (
            patcher,
            patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)),
            patch.object(RequestThrottle, "wait", new=AsyncMock()) as wait,
        ):
            await adapter.get_concept_details("PXD076216")
        assert wait.await_count == 2  # projects/<acc> + the one-row files listing

    def test_default_interval_stays_below_two_requests_per_second(self):
        assert PRIDEAdapter(LookupConfig())._throttle.interval >= 0.5
