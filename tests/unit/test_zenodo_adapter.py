"""Unit tests for ZenodoAdapter (Zenodo REST API); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import zenodo_adapter
from knowledge_lookup.adapters.zenodo_adapter import ZenodoAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.zenodo_responses import (
    REC_COMMUNITY_FIGURE,
    REC_DRYAD_DATASET,
    REC_EMBARGOED,
    REC_LONG_COVID_VACCINE,
    REC_SOFTWARE,
    REC_SUPPLEMENT_PMID,
    SEARCH_EMPTY,
    SEARCH_ME_CFS_DATASETS,
)

pytestmark = pytest.mark.unit

RECORDS = {
    str(r["id"]): r
    for r in (
        REC_DRYAD_DATASET,
        REC_LONG_COVID_VACCINE,
        REC_SUPPLEMENT_PMID,
        REC_COMMUNITY_FIGURE,
        REC_SOFTWARE,
        REC_EMBARGOED,
    )
}


class NotFound(Exception):
    """Stand-in for the HTTP 404 error raised by the request layer."""


def router(records=None, search=None):
    """Fake ``_make_request`` answering ``/records`` and ``/records/<id>``."""
    records = RECORDS if records is None else records

    async def fake(url, params=None, headers=None, json_data=None):
        path = url.removeprefix(zenodo_adapter.ZENODO_API_URL + "/")
        if path == "records":
            if isinstance(search, Exception):
                raise search
            return copy.deepcopy(search if search is not None else SEARCH_ME_CFS_DATASETS)
        record_id = path.removeprefix("records/")
        if record_id not in records:
            raise NotFound("404 NOT FOUND")  # what raise_for_status() surfaces
        return copy.deepcopy(records[record_id])

    return fake


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ZENODO_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ZENODO_API_KEY", raising=False)
    monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_SEARCH", 0.0)
    monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_SEARCH_TOKEN", 0.0)
    monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_RECORD", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return ZenodoAdapter(lookup_config)


def search_page(ids):
    """A search response with minimal hits for ``ids``."""
    return {
        "hits": {
            "total": 999,
            "hits": [
                {
                    "id": i,
                    "metadata": {"title": f"Record {i}", "resource_type": {"type": "dataset"}},
                }
                for i in ids
            ],
        }
    }


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ZENODO
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("10576421", "10576421"),
            ("zenodo.10576421", "10576421"),
            ("Zenodo.10576421", "10576421"),
            ("zenodo:10576421", "10576421"),
            ("10.5281/zenodo.10576421", "10576421"),
            ("doi:10.5281/zenodo.10576421", "10576421"),
            ("https://doi.org/10.5281/zenodo.10576421", "10576421"),
            ("https://zenodo.org/records/10576421", "10576421"),
            ("https://zenodo.org/record/10576421", "10576421"),
            ("https://zenodo.org/doi/10.5281/zenodo.10576421", "10576421"),
            ("  10.5281/ZENODO.10576421  ", "10576421"),
            ("0010576421", "10576421"),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert ZenodoAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "  ",
            None,
            "abc",
            "zenodo.",
            "10.5061/dryad.f1vhhmgsb",
            "0",
            "1234567890123",
            "12 34",
        ],
    )
    def test_invalid_ids(self, raw):
        assert ZenodoAdapter._parse_id(raw) is None

    @pytest.mark.parametrize(
        "relation,expected",
        [
            ("isSupplementTo", "is_supplement_to"),
            ("cites", "cites"),
            ("hasVersion", "has_version"),
            ("isVersionOf", "is_version_of"),
        ],
    )
    def test_snake_case(self, relation, expected):
        assert ZenodoAdapter._snake(relation) == expected

    @pytest.mark.parametrize(
        "scheme,identifier,expected",
        [
            ("doi", "10.1/x", "DOI:10.1/x"),
            ("doi", "https://doi.org/10.1/x", "DOI:10.1/x"),
            ("pmid", "123", "PMID:123"),
            ("pmid", "PMID:123", "PMID:123"),
            ("arxiv", "arXiv:1904.04095", "arXiv:1904.04095"),
            ("arxiv", "1904.04095", "arXiv:1904.04095"),
            ("url", "https://example.org/a", "https://example.org/a"),
            ("", "https://example.org/a", "https://example.org/a"),
            ("handle", "20.500/1", "handle:20.500/1"),
        ],
    )
    def test_curie(self, scheme, identifier, expected):
        assert ZenodoAdapter._curie(scheme, identifier) == expected


class TestRequests:
    @pytest.mark.asyncio
    async def test_anonymous_request_has_no_credentials(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._zenodo("records", {"q": "x"})
        url, params, headers = req.call_args.args
        assert url == "https://zenodo.org/api/records" and params == {"q": "x"}
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_token_from_environment_is_sent_as_header_only(self, adapter, monkeypatch):
        monkeypatch.setenv("ZENODO_ACCESS_TOKEN", "tok-123")
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._zenodo("records", {"q": "x"})
        url, params, headers = req.call_args.args
        assert headers["Authorization"] == "Bearer tok-123"
        assert "tok-123" not in url and "tok-123" not in str(params)

    def test_token_from_config(self):
        configured = ZenodoAdapter(LookupConfig(api_keys={"zenodo": "cfg-token"}))
        assert configured._token() == "cfg-token"

    @pytest.mark.asyncio
    async def test_search_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_SEARCH", 2.1)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(zenodo_adapter.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(zenodo_adapter.time, "monotonic", lambda: 100.0)  # frozen clock
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._zenodo("records", {})
            await adapter._zenodo("records", {})
        assert sleeps == [pytest.approx(2.1)]

    @pytest.mark.asyncio
    async def test_buckets_are_throttled_independently(self, adapter, monkeypatch):
        monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_SEARCH", 2.1)
        monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_RECORD", 0.5)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(zenodo_adapter.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(zenodo_adapter.time, "monotonic", lambda: 100.0)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._zenodo("records", {})  # first search: no wait
            await adapter._zenodo("records/1")  # first record read: no wait either
            await adapter._zenodo("records/2")  # second record read waits the short interval
        assert sleeps == [pytest.approx(0.5)]

    @pytest.mark.asyncio
    async def test_token_shortens_search_interval(self, adapter, monkeypatch):
        monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_SEARCH", 2.1)
        monkeypatch.setattr(zenodo_adapter, "_MIN_INTERVAL_SEARCH_TOKEN", 1.0)
        monkeypatch.setenv("ZENODO_ACCESS_TOKEN", "t")
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(zenodo_adapter.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(zenodo_adapter.time, "monotonic", lambda: 100.0)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._zenodo("records", {})
            await adapter._zenodo("records", {})
        assert sleeps == [pytest.approx(1.0)]


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_dataset_hits_become_concepts(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            results = await adapter.search_concepts(
                "myalgic encephalomyelitis", limit=3, resource_type="Dataset"
            )
        params = req.call_args.args[1]
        assert params == {
            "q": "myalgic encephalomyelitis",
            "size": 3,
            "page": 1,
            "sort": "bestmatch",
            "type": "dataset",
        }
        assert [c.primary_id for c in results] == ["4960364", "12791948", "19078496"]
        first = results[0]
        assert first.concept_type == ConceptType.STUDY
        assert first.confidence_score == pytest.approx(0.9)
        assert results[1].confidence_score < first.confidence_score
        assert first.semantic_types == ["Dataset"]
        assert first.identifiers[0].url == "https://zenodo.org/records/4960364"

    @pytest.mark.asyncio
    async def test_search_without_type_sends_no_type(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            await adapter.search_concepts("long covid", limit=2, sort="mostrecent")
        params = req.call_args.args[1]
        assert "type" not in params and params["sort"] == "mostrecent"

    @pytest.mark.asyncio
    async def test_search_pages_with_constant_page_size(self, adapter):
        pages = [search_page(range(1, 26)), search_page(range(26, 31))]
        mock = AsyncMock(side_effect=pages)
        with patch.object(adapter, "_make_request", mock):
            results = await adapter.search_concepts("covid", limit=30)
        assert len(results) == 30 and len({c.primary_id for c in results}) == 30
        sent = [call.args[1] for call in mock.call_args_list]
        assert [(p["page"], p["size"]) for p in sent] == [(1, 25), (2, 25)]

    @pytest.mark.asyncio
    async def test_search_stops_when_results_run_out(self, adapter):
        mock = AsyncMock(side_effect=[search_page(range(1, 11))])
        with patch.object(adapter, "_make_request", mock):
            results = await adapter.search_concepts("rare", limit=40)
        assert len(results) == 10 and mock.call_count == 1

    @pytest.mark.asyncio
    async def test_search_limit_is_capped_at_two_pages(self, adapter):
        mock = AsyncMock(side_effect=[search_page(range(1, 26)), search_page(range(26, 51))])
        with patch.object(adapter, "_make_request", mock):
            results = await adapter.search_concepts("covid", limit=500)
        assert len(results) == 50 and mock.call_count == 2

    @pytest.mark.asyncio
    async def test_search_deduplicates_and_skips_unusable_hits(self, adapter):
        page = search_page([5, 5, 6])
        page["hits"]["hits"] += [{"id": "abc", "metadata": {"title": "x"}}, {"id": 9}, "junk"]
        with patch.object(adapter, "_make_request", AsyncMock(return_value=page)):
            results = await adapter.search_concepts("x", limit=10)
        assert [c.primary_id for c in results] == ["5", "6"]

    @pytest.mark.asyncio
    async def test_search_by_record_id_uses_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            results = await adapter.search_concepts("10.5281/zenodo.10576421")
        assert [c.primary_id for c in results] == ["10576421"]
        assert req.call_args.args[0].endswith("/records/10576421")

    @pytest.mark.asyncio
    async def test_short_bare_number_is_a_search_term(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            await adapter.search_concepts("2021", limit=2)
        assert req.call_args.args[0].endswith("/records")

    @pytest.mark.asyncio
    async def test_search_unknown_record_id(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.search_concepts("zenodo.99999999") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), (None, 5), ("x", 0), ("x", -3)])
    async def test_search_empty_inputs(self, adapter, query, limit):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts(query, limit=limit) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"resource_type": "spreadsheet"},
            {"sort": "oldest"},
            {"sort": None, "resource_type": "x"},
        ],
    )
    async def test_search_invalid_options_return_empty_without_request(self, adapter, kwargs):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts("x", **kwargs) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_empty_and_malformed_responses(self, adapter):
        for payload in (SEARCH_EMPTY, {}, {"hits": None}, {"hits": {"hits": None}}, None, []):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("zzzz") == []

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        fake = router(search=RuntimeError("boom"))
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_dataset_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            concept = await adapter.get_concept_details("zenodo.10576421")
        assert concept is not None
        assert concept.primary_id == "10576421"
        assert concept.concept_type == ConceptType.STUDY
        assert concept.confidence_score == pytest.approx(0.95)
        assert concept.primary_label == "Characterising long COVID-like COVID-19 vaccine reactions"
        assert [i.identifier for i in concept.identifiers] == [
            "10576421",
            "DOI:10.5281/zenodo.10576421",
        ]
        assert concept.identifiers[1].url == "https://doi.org/10.5281/zenodo.10576421"
        assert "<p>" not in concept.definitions[0] and "&nbsp;" not in concept.definitions[0]
        assert concept.categories[0] == "Long COVID"
        data = concept.source_data[KnowledgeSource.ZENODO]
        assert data["doi"] == "10.5281/zenodo.10576421"
        assert data["concept_doi"] == "10.5281/zenodo.10576420"
        assert data["license"] == "cc-by-4.0" and data["access_right"] == "open"
        assert data["file_count"] == 1 and data["total_size_bytes"] == 7876615
        assert data["url"] == "https://zenodo.org/records/10576421"
        assert data["creators"] == ["Carroll, Harriet"]
        assert data["attribution"].startswith("Carroll, Harriet (2024). Characterising")
        assert "cc-by-4.0" in data["license_note"]
        # nothing that points at file content leaks into the concept
        assert "/files/" not in str(data) and "checksum" not in str(data)

    @pytest.mark.asyncio
    async def test_details_accept_every_id_form(self, adapter):
        forms = [
            "10576421",
            "zenodo.10576421",
            "10.5281/zenodo.10576421",
            "https://zenodo.org/records/10576421",
        ]
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            ids = [(await adapter.get_concept_details(f)).primary_id for f in forms]
        assert ids == ["10576421"] * 4

    @pytest.mark.asyncio
    async def test_foreign_doi_record_and_communities(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            concept = await adapter.get_concept_details("4960364")
        data = concept.source_data[KnowledgeSource.ZENODO]
        assert data["doi"] == "10.5061/dryad.f1vhhmgsb"
        assert data["concept_doi"] is None
        assert data["communities"] == ["dryad"] and data["license"] == "cc-zero"
        assert data["creator_count"] == 6

    @pytest.mark.asyncio
    async def test_software_publication_and_embargoed_records(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            software = await adapter.get_concept_details("20414304")
            figure = await adapter.get_concept_details("12762596")
            embargoed = await adapter.get_concept_details("21302835")
        assert software.concept_type == ConceptType.UNKNOWN
        assert software.source_data[KnowledgeSource.ZENODO]["license"] == "mit-license"
        assert figure.source_data[KnowledgeSource.ZENODO]["resource_subtype"] == "figure"
        data = embargoed.source_data[KnowledgeSource.ZENODO]
        assert data["access_right"] == "embargoed" and data["embargo_date"] == "2026-12-30"
        assert data["file_count"] == 0 and data["total_size_bytes"] == 0
        assert "embargoed" in data["license_note"]

    @pytest.mark.asyncio
    async def test_publication_type_and_sparse_record(self, adapter):
        record = {
            "id": 77,
            "metadata": {
                "resource_type": {"type": "publication"},
                "creators": [{"name": "A"}, {"name": "B"}],
            },
            "files": [{"key": "a", "size": 10}, {"key": "b", "size": 5.5}, {"key": "c"}, "junk"],
        }
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router({"77": record}))):
            concept = await adapter.get_concept_details("77")
        assert concept.concept_type == ConceptType.REFERENCE
        assert concept.primary_label == "zenodo.77"
        data = concept.source_data[KnowledgeSource.ZENODO]
        assert data["file_count"] == 3 and data["total_size_bytes"] == 15.5
        assert data["attribution"].startswith("A et al. ()")
        assert data["doi"] is None and data["url"] == "https://zenodo.org/records/77"
        assert len(concept.identifiers) == 1

    @pytest.mark.asyncio
    async def test_details_invalid_missing_and_error(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.get_concept_details("nonsense") is None
            assert await adapter.get_concept_details("zenodo.99999999") is None
        for payload in ({}, {"id": 1}, {"id": 1, "metadata": {}}, [], None):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.get_concept_details("12345") is None
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value={"id": "x", "metadata": {"a": 1}})
        ):
            assert await adapter.get_concept_details("12345") is None

    @pytest.mark.asyncio
    async def test_plain_text_conversion(self):
        text = ZenodoAdapter._plain_text(
            "<p>Background</p>\n\n<p>5 &lt; 6 &amp; more<br/>done</p>"
        )
        assert text == "Background 5 < 6 & more done"
        assert ZenodoAdapter._plain_text(None) == ""

    @pytest.mark.asyncio
    async def test_long_description_is_capped(self, adapter):
        record = copy.deepcopy(REC_LONG_COVID_VACCINE)
        record["metadata"]["description"] = "<p>" + "x" * 20000 + "</p>"
        with patch.object(adapter, "_make_request", AsyncMock(return_value=record)):
            concept = await adapter.get_concept_details("10576421")
        assert len(concept.definitions[0]) == zenodo_adapter._MAX_DESCRIPTION_LENGTH


class TestRelationships:
    @pytest.mark.asyncio
    async def test_supplement_record(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            rels = await adapter.get_relationships("3708367")
        labels = [(r["relation_label"], r["related_id"]) for r in rels]
        assert labels == [
            ("has_license", "cc-by-4.0"),
            ("in_community", "zenodo-community:humanitasirccs"),
            ("is_version_of", "DOI:10.5281/zenodo.3708366"),
            ("is_supplement_to", "PMID:30777853"),
            ("is_supplement_to", "DOI:10.1158/0008-5472.CAN-18-1544"),
        ]
        assert rels[1]["url"] == "https://zenodo.org/communities/humanitasirccs"
        assert rels[3]["datacite_relation"] == "isSupplementTo" and rels[3]["scheme"] == "pmid"
        assert all(r["source"] == "ZENODO" for r in rels)

    @pytest.mark.asyncio
    async def test_resource_type_and_url_targets(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            rels = await adapter.get_relationships("12762596")
        part_of = [r for r in rels if r["relation_label"] == "is_part_of"]
        assert [r["related_id"] for r in part_of] == [
            "DOI:10.13133/2284-4880/1398",
            "lsid:urn:lsid:plazi.org:pub:FFAB31351A73FFE06C32FFDBDD462A50",
            "https://zenodo.org/record/12762584",
        ]
        assert part_of[0]["resource_type"] == "publication-article"

    @pytest.mark.asyncio
    async def test_limit_dedup_and_malformed_related_identifiers(self, adapter):
        record = copy.deepcopy(REC_SUPPLEMENT_PMID)
        record["metadata"]["related_identifiers"] = [
            {"identifier": "1", "relation": "cites", "scheme": "pmid"},
            {"identifier": "1", "relation": "cites", "scheme": "pmid"},
            {"identifier": "", "relation": "cites", "scheme": "pmid"},
            {"identifier": "2", "scheme": "pmid"},
            "junk",
        ]
        with patch.object(adapter, "_make_request", AsyncMock(return_value=record)):
            rels = await adapter.get_relationships("3708367", limit=50)
            capped = await adapter.get_relationships("3708367", limit=2)
        assert [r["related_id"] for r in rels if r["relation_label"] == "cites"] == ["PMID:1"]
        assert len(capped) == 2

    @pytest.mark.asyncio
    async def test_first_version_has_no_self_version_link(self, adapter):
        record = copy.deepcopy(REC_LONG_COVID_VACCINE)
        record["conceptrecid"] = str(record["id"])
        with patch.object(adapter, "_make_request", AsyncMock(return_value=record)):
            rels = await adapter.get_relationships("10576421")
        assert [r["relation_label"] for r in rels] == ["has_license"]

    @pytest.mark.asyncio
    async def test_relationships_failures(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.get_relationships("nonsense") == []
            assert await adapter.get_relationships("10576421", limit=0) == []
            assert await adapter.get_relationships("zenodo.99999999") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("12345") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_with_pmid_and_doi(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            mappings = await adapter.get_mappings("zenodo.3708367")
        summary = [(m["toId"], m["toSource"], m["mappingType"]) for m in mappings]
        assert summary == [
            ("DOI:10.5281/zenodo.3708367", "DOI", "same_as"),
            ("DOI:10.5281/zenodo.3708366", "DOI", "version_group"),
            ("PMID:30777853", "PUBMED", "is_supplement_to"),
            ("DOI:10.1158/0008-5472.CAN-18-1544", "DOI", "is_supplement_to"),
        ]
        for m in mappings:
            assert set(m) >= {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "3708367" and m["fromSource"] == "ZENODO"

    @pytest.mark.asyncio
    async def test_arxiv_mapping_and_ignored_schemes(self, adapter):
        record = copy.deepcopy(REC_LONG_COVID_VACCINE)
        record["metadata"]["related_identifiers"] = [
            {"identifier": "arXiv:1904.04095", "relation": "references", "scheme": "arxiv"},
            {"identifier": "https://example.org/x", "relation": "cites", "scheme": "url"},
            {"identifier": "urn:lsid:x", "relation": "cites", "scheme": "lsid"},
            {"identifier": "arXiv:1904.04095", "relation": "references", "scheme": "arxiv"},
            "junk",
        ]
        with patch.object(adapter, "_make_request", AsyncMock(return_value=record)):
            mappings = await adapter.get_mappings("10576421")
        arxiv = [m for m in mappings if m["toSource"] == "ARXIV"]
        assert len(arxiv) == 1 and arxiv[0]["toId"] == "arXiv:1904.04095"
        assert not any("example.org" in m["toId"] for m in mappings)

    @pytest.mark.asyncio
    async def test_record_without_doi_has_no_mappings(self, adapter):
        record = {"id": 5, "metadata": {"title": "x"}}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=record)):
            assert await adapter.get_mappings("5") == []

    @pytest.mark.asyncio
    async def test_mappings_failures(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.get_mappings("nonsense") == []
            assert await adapter.get_mappings("zenodo.99999999") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("12345") == []
