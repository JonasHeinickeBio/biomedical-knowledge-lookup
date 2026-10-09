"""Unit tests for OpenAIREAdapter (trimmed real v3 responses, no network)."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import _vocab_common
from knowledge_lookup.adapters import openaire_adapter as oa
from knowledge_lookup.adapters.openaire_adapter import OpenAIREAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import openaire_responses as fx

pytestmark = pytest.mark.unit

DAVIS = fx.DAVIS_ID
FUNDED = fx.PRODUCT_FUNDED["id"]
PROJECT = fx.PROJECT_SFI["id"]
DOI = "10.1038/s41579-022-00846-2"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OPENAIRE_ACCESS_TOKEN", raising=False)


@pytest.fixture
def adapter():
    a = OpenAIREAdapter(LookupConfig())
    a._spacer.interval = 0  # no spacing in tests (throttling has its own test)
    return a


def router(routes):
    """Fake ``_make_request``: ``routes`` maps a URL path (after /graph/v3/) to a response,
    an exception, or a callable ``(params) -> response``."""

    async def fake(url, params=None, headers=None, **kwargs):
        path = url.split("/graph/v3/")[1]
        value = routes[path]
        if callable(value):
            value = value(params or {})
        if isinstance(value, Exception):
            raise value
        return value

    return AsyncMock(side_effect=fake)


class NotFound(Exception):
    status = 404


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.OPENAIRE
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (DAVIS, ("oaid", DAVIS)),
            (f"50|{DAVIS}", ("oaid", DAVIS)),
            (f"openaire:{DAVIS}", ("oaid", DAVIS)),
            (
                f"https://explore.openaire.eu/search/publication?articleId={DAVIS}",
                ("oaid", DAVIS),
            ),
            (f"project:{PROJECT}", ("project", PROJECT)),
            (f"PROJECT:40|{PROJECT}", ("project", PROJECT)),
            (DOI, ("pid", DOI)),
            (f"doi:{DOI}", ("pid", DOI)),
            (f"DOI: {DOI}", ("pid", DOI)),
            (f"https://doi.org/{DOI}", ("pid", DOI)),
            ("PMID:36639608", ("pid", "36639608")),
            ("https://pubmed.ncbi.nlm.nih.gov/36639608/", ("pid", "36639608")),
            ("pmc9839201", ("pid", "PMC9839201")),
            ("arXiv:2003.06265v2", ("pid", "2003.06265")),
            ("https://arxiv.org/abs/2003.06265", ("pid", "2003.06265")),
            ("36639608", None),  # bare digits are search text, not an id
            ("long covid", None),
            ("project:nonsense", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert OpenAIREAdapter.parse_id(raw) == expected

    def test_token_header_only_when_set(self, adapter, monkeypatch):
        assert adapter._headers() == {}
        monkeypatch.setenv("OPENAIRE_ACCESS_TOKEN", "tok123")
        assert adapter._headers() == {"Authorization": "Bearer tok123"}

    @pytest.mark.asyncio
    async def test_token_is_sent_with_requests(self, adapter, monkeypatch):
        monkeypatch.setenv("OPENAIRE_ACCESS_TOKEN", "tok123")
        mock = AsyncMock(return_value=fx.EMPTY_RESPONSE)
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_products("long covid")
        assert mock.call_args.kwargs["headers"] == {"Authorization": "Bearer tok123"}

    @pytest.mark.asyncio
    async def test_no_identity_or_token_by_default(self, adapter):
        mock = AsyncMock(return_value=fx.EMPTY_RESPONSE)
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_products("long covid")
        assert mock.call_args.kwargs["headers"] == {}
        assert set(mock.call_args.kwargs["params"]) == {"search", "pageSize"}


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_products(self, adapter):
        mock = router({"research-products": fx.SEARCH_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_products("long covid", limit=5)
        assert [c.primary_id for c in concepts] == [DAVIS, fx.PRODUCT_DATASET["id"]]
        assert (
            concepts[0].primary_label
            == "Long COVID: major findings, mechanisms and recommendations"
        )
        assert concepts[0].concept_type == ConceptType.CITATION
        assert concepts[1].concept_type == ConceptType.REFERENCE
        params = mock.call_args.kwargs["params"]
        assert params == {"search": "long covid", "pageSize": 5}

    @pytest.mark.asyncio
    async def test_filters_are_passed(self, adapter):
        mock = router({"research-products": fx.EMPTY_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_products(
                "long covid", 500, product_type="Dataset", open_access_only=True, from_year=2022
            )
        params = mock.call_args.kwargs["params"]
        assert params["pageSize"] == 100  # API limit
        assert params["type"] == "dataset"
        assert params["accessRightLabel"] == '"Open Access"'
        assert params["fromPublicationYear"] == 2022

    @pytest.mark.asyncio
    async def test_unknown_type_returns_empty_without_request(self, adapter):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_products("x", product_type="film") == []
            assert await adapter.search_concepts("x", product_type="film") == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query, limit", [("", 5), ("   ", 5), (None, 5), ("long covid", 0)])
    async def test_empty_query_or_zero_limit(self, adapter, query, limit):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts(query, limit) == []
            assert await adapter.search_products(query or "", limit) == []
            assert await adapter.search_projects(query or "", limit) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_concepts_appends_projects(self, adapter):
        mock = router({"research-products": fx.SEARCH_RESPONSE, "projects": fx.PROJECT_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("long covid", limit=8)
        ids = [c.primary_id for c in concepts]
        assert ids == [DAVIS, fx.PRODUCT_DATASET["id"], f"project:{PROJECT}"]
        project_call = [c for c in mock.call_args_list if c.args[0].endswith("/projects")][0]
        assert project_call.kwargs["params"]["pageSize"] == 2  # limit // 4
        product_call = [c for c in mock.call_args_list if c.args[0].endswith("research-products")][
            0
        ]
        assert product_call.kwargs["params"]["pageSize"] == 6

    @pytest.mark.asyncio
    async def test_search_concepts_type_filter_skips_projects(self, adapter):
        mock = router({"research-products": fx.SEARCH_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("long covid", 20, product_type="dataset")
        assert len(concepts) == 2
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_search_concepts_small_limit_skips_projects(self, adapter):
        mock = router({"research-products": fx.SEARCH_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("long covid", limit=1)
        assert len(concepts) == 1
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_search_concepts_resolves_identifiers(self, adapter):
        mock = router({"research-products": fx.PID_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts(f"doi:{DOI}")
        assert [c.primary_id for c in concepts] == [DAVIS]
        assert mock.call_args.kwargs["params"]["pid"] == f'"{DOI}"'

    @pytest.mark.asyncio
    async def test_search_projects(self, adapter):
        mock = router({"projects": fx.PROJECT_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_projects("long covid", limit=3)
        assert [c.primary_id for c in concepts] == [f"project:{PROJECT}"]

    @pytest.mark.asyncio
    async def test_limit_truncates_and_dedupes(self, adapter):
        doubled = copy.deepcopy(fx.SEARCH_RESPONSE)
        doubled["results"] = doubled["results"] + [fx.PRODUCT_DAVIS, {"id": "x"}, "junk"]
        mock = router({"research-products": doubled})
        with patch.object(adapter, "_make_request", new=mock):
            assert len(await adapter.search_products("covid", 1)) == 1
            assert len(await adapter.search_products("covid", 10)) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response",
        [
            fx.EMPTY_RESPONSE,
            {"results": None},
            {"results": "oops"},
            ["not", "a", "dict"],
            None,
            RuntimeError("down"),
        ],
    )
    async def test_empty_and_error_responses(self, adapter, response):
        mock = router({"research-products": response, "projects": response})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_products("covid") == []
            assert await adapter.search_concepts("covid", 10) == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_product_by_doi(self, adapter):
        mock = router({"research-products": fx.PID_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(f"https://doi.org/{DOI}")
        assert concept.primary_id == DAVIS
        assert concept.sources == [KnowledgeSource.OPENAIRE]
        assert mock.call_args.kwargs["params"] == {"pid": f'"{DOI}"', "pageSize": 1}
        assert "Long COVID is an often debilitating" in concept.definitions[0]
        assert "year:2023" in concept.categories
        assert "journal:Nature Reviews Microbiology" in concept.categories
        assert "access:OPEN" in concept.categories
        assert "Post-Acute COVID-19 Syndrome" in concept.synonyms
        ids = {i.identifier for i in concept.identifiers}
        assert {f"DOI:{DOI}", "PMID:36639608", "PMC9839201"} <= ids

    @pytest.mark.asyncio
    async def test_product_source_data_states_open_access_faithfully(self, adapter):
        mock = router({f"research-products/{FUNDED}": fx.PRODUCT_FUNDED})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(FUNDED)
        data = concept.source_data[KnowledgeSource.OPENAIRE]
        assert data["doi"] == "10.1038/s41593-024-01576-9"
        access = data["open_access"]
        assert access["best_access_right"] == "OPEN"
        assert access["color"] == "hybrid"
        assert access["is_green"] is True
        assert access["publicly_funded"] is True
        assert access["licenses"] == ["CC BY"]
        assert data["instances"][0]["license"] == "CC BY"
        assert data["instances"][0]["open_access_route"] == "hybrid"
        assert data["instances"][1]["license"] is None  # absent stays absent
        assert data["projects"][0]["funder"] == "Science Foundation Ireland"
        assert data["url"].endswith(f"id={FUNDED}")

    @pytest.mark.asyncio
    async def test_closed_product_keeps_missing_fields_missing(self, adapter):
        mock = router({"research-products": fx.PID_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(DOI)
        data = concept.source_data[KnowledgeSource.OPENAIRE]
        assert data["open_access"]["color"] is None
        assert data["open_access"]["licenses"] == ["Springer Nature TDM"]
        assert data["pmid"] == "36639608"
        assert data["pmcid"] == "PMC9839201"
        assert data["authors"][0]["orcid"] == "0000-0002-1245-2034"

    @pytest.mark.asyncio
    async def test_project_details(self, adapter):
        mock = router({f"projects/{PROJECT}": fx.PROJECT_SFI})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(f"project:{PROJECT}")
        assert concept.primary_id == f"project:{PROJECT}"
        data = concept.source_data[KnowledgeSource.OPENAIRE]
        assert data["code"] == "20/COV/0312"
        assert data["funder"] == "Science Foundation Ireland"
        assert data["funding_stream"] == ("COVID-19 Rapid Response Funding Programme / Phase 1")
        assert data["funded_amount"] == 65144.6
        assert data["currency"] == "EUR"
        assert "funder:Science Foundation Ireland" in concept.categories

    @pytest.mark.asyncio
    async def test_bare_openaire_id_falls_back_to_project(self, adapter):
        mock = router(
            {
                f"research-products/{PROJECT}": NotFound("nope"),
                f"projects/{PROJECT}": fx.PROJECT_SFI,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(PROJECT)
        assert concept.primary_id == f"project:{PROJECT}"

    @pytest.mark.asyncio
    async def test_unknown_inputs_return_none(self, adapter):
        mock = router(
            {
                f"research-products/{DAVIS}": NotFound("nope"),
                f"projects/{DAVIS}": NotFound("nope"),
                "research-products": fx.EMPTY_RESPONSE,
                f"projects/{PROJECT}": {"error": "x"},
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details(DAVIS) is None
            assert await adapter.get_concept_details("10.9999/none") is None
            assert await adapter.get_concept_details("not an id") is None
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details(f"project:{PROJECT}") is None

    @pytest.mark.asyncio
    async def test_record_without_title_is_skipped(self, adapter):
        bad = {"id": DAVIS, "mainTitle": None}
        mock = router({f"research-products/{DAVIS}": bad})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details(DAVIS) is None

    def test_html_in_titles_is_stripped(self, adapter):
        item = copy.deepcopy(fx.PRODUCT_DAVIS)
        item["mainTitle"] = "A <i>CLDN25</i>   mutation"
        assert adapter._product_to_concept(item).primary_label == "A CLDN25 mutation"

    def test_conversion_errors_are_swallowed(self, adapter):
        assert adapter._product_to_concept({"id": DAVIS, "mainTitle": "T", "instances": 5}) is None
        assert adapter._project_to_concept({"id": PROJECT, "title": "T", "granted": 5}) is None
        assert adapter._project_to_concept({"id": PROJECT}) is None

    def test_long_abstract_is_capped(self, adapter):
        item = copy.deepcopy(fx.PRODUCT_DAVIS)
        item["descriptions"] = ["x" * 10000]
        concept = adapter._product_to_concept(item)
        assert len(concept.definitions[0]) == oa.MAX_ABSTRACT_CHARS


class TestRelationships:
    @pytest.mark.asyncio
    async def test_product_edges(self, adapter):
        mock = router(
            {
                "research-products": fx.PID_RESPONSE,
                "research-products/links": fx.SCHOLIX_LINKS,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(DOI, limit=10)
        by_label: dict[str, list] = {}
        for edge in edges:
            by_label.setdefault(edge["relation_label"], []).append(edge)
            assert edge["source"] == "OPENAIRE"
        funded = by_label["funded_by"][0]
        assert funded["related_id"].startswith("project:nih_")
        assert funded["funder"] == "National Institutes of Health"
        assert funded["grant_code"] == "5UL1TR002550-02"
        assert funded["funding_stream"]
        orgs = by_label["affiliated_with"]
        assert orgs[0]["ror"].startswith("https://ror.org/")
        hosts = {e["related_name"]: e for e in by_label["hosted_by"]}
        assert hosts["Nature Reviews Microbiology"]["access_right"] == "CLOSED"
        assert hosts["Nature Reviews Microbiology"]["license"] == "Springer Nature TDM"
        assert hosts["PubMed Central"]["access_right"] == "OPEN"
        assert {e["related_name"] for e in by_label["collected_from"]} >= {"Crossref"}
        cites = by_label["cites"]
        assert cites[0]["doi"] and cites[0]["total_links"] == 186
        links_call = [c for c in mock.call_args_list if c.args[0].endswith("/links")][0]
        assert links_call.kwargs["params"] == {"sourcePid": DOI, "pageSize": 10}

    @pytest.mark.asyncio
    async def test_limit_caps_every_group(self, adapter):
        mock = router(
            {
                f"research-products/{FUNDED}": fx.PRODUCT_FUNDED,
                "research-products/links": fx.EMPTY_RESPONSE,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(FUNDED, limit=1)
        labels = [e["relation_label"] for e in edges]
        assert labels.count("funded_by") == 1
        assert labels.count("affiliated_with") == 1
        assert labels.count("hosted_by") == 1
        assert labels.count("collected_from") == 1

    @pytest.mark.asyncio
    async def test_product_without_doi_has_no_scholix_call(self, adapter):
        item = copy.deepcopy(fx.PRODUCT_FUNDED)
        item["pids"] = [{"scheme": "handle", "value": "10197/30524"}]
        for inst in item["instances"]:
            inst.pop("pids", None)
            inst.pop("alternateIdentifiers", None)
        mock = router({f"research-products/{FUNDED}": item})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(FUNDED)
        assert edges
        assert all(not c.args[0].endswith("/links") for c in mock.call_args_list)

    @pytest.mark.asyncio
    async def test_scholix_dedupes_and_labels(self, adapter):
        links = copy.deepcopy(fx.SCHOLIX_LINKS)
        first = links["results"][0]
        first["relType"] = {"name": "isSupplementedBy"}
        links["results"] = [first, copy.deepcopy(first), {"target": {"identifiers": []}}]
        mock = router({"research-products": fx.PID_RESPONSE, "research-products/links": links})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(DOI)
        supplements = [e for e in edges if e["relation_label"] == "is_supplemented_by"]
        assert len(supplements) == 1

    @pytest.mark.asyncio
    async def test_unidentified_project_gets_readable_name(self, adapter):
        item = copy.deepcopy(fx.PRODUCT_FUNDED)
        item["projects"] = [
            {
                "id": "501100002081::1e5e62235d094afd01cd56e65112fc63",
                "code": "unidentified",
                "title": "unidentified",
                "funder": "Irish Research Council",
            }
        ]
        mock = router(
            {f"research-products/{FUNDED}": item, "research-products/links": fx.EMPTY_RESPONSE}
        )
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(FUNDED)
        funded = [e for e in edges if e["relation_label"] == "funded_by"][0]
        assert funded["related_name"] == "Irish Research Council (unidentified project)"

    @pytest.mark.asyncio
    async def test_project_edges(self, adapter):
        mock = router(
            {
                f"projects/{PROJECT}": fx.PROJECT_SFI,
                "research-products": fx.PROJECT_OUTPUTS,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(f"project:{PROJECT}", limit=5)
        labels = [e["relation_label"] for e in edges]
        assert labels == ["funded_by", "has_participant", "has_output", "has_output"]
        assert edges[0]["related_name"] == "Science Foundation Ireland"
        assert edges[0]["jurisdiction"] == "IE"
        assert edges[1]["ror"] == "https://ror.org/02tyrky19"
        assert edges[2]["total_outputs"] == 4
        outputs_call = [c for c in mock.call_args_list if c.args[0].endswith("research-products")][
            0
        ]
        assert outputs_call.kwargs["params"] == {"relProjectId": PROJECT, "pageSize": 5}

    @pytest.mark.asyncio
    async def test_invalid_zero_and_failing(self, adapter):
        mock = router(
            {
                "research-products": RuntimeError("down"),
                f"research-products/{DAVIS}": NotFound("x"),
                f"projects/{DAVIS}": NotFound("x"),
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_relationships("garbage") == []
            assert await adapter.get_relationships(DOI, limit=0) == []
            assert await adapter.get_relationships(DOI) == []
            assert await adapter.get_relationships(DAVIS) == []
            assert await adapter.get_relationships(f"project:{DAVIS}") == []

    @pytest.mark.asyncio
    async def test_get_project_outputs(self, adapter):
        outputs = copy.deepcopy(fx.PROJECT_OUTPUTS)
        outputs["results"] = [fx.PRODUCT_DAVIS]
        mock = router({"research-products": outputs})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.get_project_outputs(f"project:{PROJECT}", 3)
            assert [c.primary_id for c in concepts] == [DAVIS]
            assert await adapter.get_project_outputs(DOI) == []
            assert await adapter.get_project_outputs("junk") == []
            assert await adapter.get_project_outputs(PROJECT, 0) == []
        assert mock.call_args.kwargs["params"] == {"relProjectId": PROJECT, "pageSize": 3}


class TestMappings:
    @pytest.mark.asyncio
    async def test_product_mappings(self, adapter):
        mock = router({"research-products": fx.PID_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings("PMID:36639608")
        got = {(m["toSource"], m["toId"]) for m in mappings}
        assert got == {("DOI", DOI), ("PMID", "36639608"), ("PMCID", "PMC9839201")}
        for m in mappings:
            assert m["fromId"] == DAVIS
            assert m["fromSource"] == "OPENAIRE"
            assert m["mappingType"] == "exact"
            assert m["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_arxiv_and_handle_labels(self, adapter):
        item = copy.deepcopy(fx.PRODUCT_DAVIS)
        item["pids"] = [
            {"scheme": "arXiv", "value": "2003.06265"},
            {"scheme": "handle", "value": "10197/30524"},
            {"scheme": "doi", "value": "https://doi.org/10.1/ABC"},
            {"scheme": "mag_id", "value": "123"},
        ]
        item["instances"] = []
        mock = router({f"research-products/{DAVIS}": item})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings(DAVIS)
        got = {(m["toSource"], m["toId"]) for m in mappings}
        assert got == {
            ("ARXIV", "2003.06265"),
            ("HANDLE", "10197/30524"),
            ("DOI", "10.1/abc"),
            ("MAG_ID", "123"),
        }

    @pytest.mark.asyncio
    async def test_project_and_failures_have_no_mappings(self, adapter):
        mock = router({"research-products": fx.EMPTY_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_mappings(f"project:{PROJECT}") == []
            assert await adapter.get_mappings("garbage") == []
            assert await adapter.get_mappings("10.9999/none") == []
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=ValueError)):
            assert await adapter.get_mappings(DOI) == []


class TestThrottling:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        sleeps: list[float] = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        clock = {"now": 100.0}
        # replace the names inside the helper module only: patching asyncio.sleep or
        # time.monotonic themselves would also change the event loop's clock
        monkeypatch.setattr(_vocab_common, "asyncio", SimpleNamespace(sleep=fake_sleep))
        monkeypatch.setattr(_vocab_common, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
        adapter._spacer.interval = oa.MIN_INTERVAL
        mock = AsyncMock(return_value=fx.EMPTY_RESPONSE)
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_products("a")  # first request never waits
            await adapter.search_products("b")  # clock did not advance: must wait
            clock["now"] += 5.0
            await adapter.search_products("c")  # enough time has passed
        assert sleeps == [pytest.approx(oa.MIN_INTERVAL)]
        assert mock.call_count == 3

    def test_interval_stays_below_the_hourly_limit(self):
        assert 3600 / oa.MIN_INTERVAL <= 7200


class TestRegistry:
    def test_registered_and_lazy(self, lookup_config):
        from knowledge_lookup.adapters import ADAPTER_CLASSES

        assert ADAPTER_CLASSES[KnowledgeSource.OPENAIRE] is OpenAIREAdapter


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_entries_without_ids_are_skipped(self, adapter):
        item = copy.deepcopy(fx.PRODUCT_FUNDED)
        item["projects"] = [{"id": None, "title": "no id"}]
        item["organizations"] = [{"id": None, "legalName": "no id"}]
        item["instances"] = [{"hostedBy": {}}, {"hostedBy": {"key": None}}]
        item["collectedFrom"] = [{"value": "no key"}, "junk"]
        mock = router(
            {f"research-products/{FUNDED}": item, "research-products/links": fx.EMPTY_RESPONSE}
        )
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_relationships(FUNDED) == []

    @pytest.mark.asyncio
    async def test_project_participants_and_outputs_without_ids_are_skipped(self, adapter):
        project = copy.deepcopy(fx.PROJECT_SFI)
        project["funding"] = {}
        project["links"] = [
            {"header": {"relationClass": "hasParticipant", "relatedIdentifier": None}},
            {"header": {"relationClass": "isParticipant", "relatedIdentifier": "x"}},
        ]
        outputs = {
            "header": {"numFound": 1},
            "results": [{"id": None}, {"id": "a", "mainTitle": ""}],
        }
        mock = router({f"projects/{PROJECT}": project, "research-products": outputs})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_relationships(f"project:{PROJECT}") == []

    def test_project_summary_acronym_and_keywords(self, adapter):
        project = copy.deepcopy(fx.PROJECT_SFI)
        project.update(
            {"summary": "Long  COVID <b>study</b>", "acronym": "LC", "keywords": "a, b,,"}
        )
        concept = adapter._project_to_concept(project)
        assert concept.definitions == ["Long COVID study"]
        assert concept.synonyms == ["LC", "a", "b"]

    @pytest.mark.asyncio
    async def test_unexpected_exceptions_never_escape(self, adapter):
        boom = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(adapter, "_get", new=boom):
            assert await adapter.search_products("x") == []
            assert await adapter.search_projects("x") == []
            assert await adapter.search_concepts("x") == []
            assert await adapter.get_concept_details(DOI) is None
            assert await adapter.get_relationships(DOI) == []
            assert await adapter.get_mappings(DOI) == []
            assert await adapter.get_project_outputs(PROJECT) == []
