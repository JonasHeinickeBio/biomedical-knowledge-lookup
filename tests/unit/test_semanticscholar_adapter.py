"""Unit tests for SemanticScholarAdapter (trimmed real responses, no network)."""

import asyncio
import copy
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.adapters import semanticscholar_adapter as ss
from knowledge_lookup.adapters.semanticscholar_adapter import (
    SemanticScholarAdapter,
    _RateLimited,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import semanticscholar_responses as fx

pytestmark = pytest.mark.unit

PAPER_ID = "e7b00aef2c3fa2da51aa4647e1e9e38566bf1be6"
DOI = "10.1038/s41579-022-00846-2"


@pytest.fixture(autouse=True)
def _no_key_no_waits(monkeypatch):
    monkeypatch.delenv(ss.API_KEY_ENV, raising=False)
    # config keys only (no SEMANTICSCHOLAR_API_KEY / .env lookup: keep the tests hermetic)
    monkeypatch.setattr(
        LookupConfig, "get_api_key", lambda self, service: self._api_keys_dict.get(service)
    )
    monkeypatch.setattr(ss, "MIN_REQUEST_INTERVAL", 0.0)


@pytest.fixture
def sleeps(monkeypatch):
    """Record the sleeps of the module without actually waiting (the event loop keeps the
    real ``asyncio.sleep``: only the module's own reference is replaced)."""
    recorded: list[float] = []

    async def fake_sleep(seconds):
        recorded.append(seconds)

    monkeypatch.setattr(ss, "asyncio", SimpleNamespace(Lock=asyncio.Lock, sleep=fake_sleep))
    return recorded


@pytest.fixture
def adapter():
    return SemanticScholarAdapter(LookupConfig())


def patched(adapter, *results):
    """Patch ``_send`` with a sequence of results (``_RateLimited``, dict, None or Exception)."""
    mock = AsyncMock(side_effect=list(results))
    return patch.object(adapter, "_send", new=mock), mock


def sent_url(mock, index=-1):
    return mock.call_args_list[index].args[0]


def sent_params(mock, index=-1):
    return mock.call_args_list[index].args[1]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.SEMANTICSCHOLAR
        assert adapter.is_available() is True  # keyless works (rate limited)
        assert adapter.api_key is None and adapter._headers() == {}

    def test_key_from_environment_and_config(self, monkeypatch):
        monkeypatch.setenv(ss.API_KEY_ENV, "env-test-key")
        assert SemanticScholarAdapter(LookupConfig()).api_key == "env-test-key"
        monkeypatch.delenv(ss.API_KEY_ENV)
        config = LookupConfig(api_keys={"semanticscholar": "cfg-test-key"})
        keyed = SemanticScholarAdapter(config)
        assert keyed.api_key == "cfg-test-key"
        assert keyed._headers() == {"x-api-key": "cfg-test-key"}

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (PAPER_ID, PAPER_ID),
            (PAPER_ID.upper(), PAPER_ID),
            (f"DOI:{DOI}", f"DOI:{DOI}"),
            (f"doi:{DOI}", f"DOI:{DOI}"),
            (DOI, f"DOI:{DOI}"),
            (f"https://doi.org/{DOI}", f"DOI:{DOI}"),
            (f"http://dx.doi.org/{DOI}", f"DOI:{DOI}"),
            ("DOI:not-a-doi", None),
            ("PMID:36639608", "PMID:36639608"),
            ("pmid 36639608", "PMID:36639608"),
            ("36639608", "PMID:36639608"),
            ("PMCID:PMC9839201", "PMCID:9839201"),
            ("PMC9839201", "PMCID:9839201"),
            ("pmc9839201", "PMCID:9839201"),
            ("PMCID:9839201", "PMCID:9839201"),
            ("PMCabc", None),
            ("ARXIV:2006.10256", "ARXIV:2006.10256"),
            ("arXiv:2006.10256", "ARXIV:2006.10256"),
            ("CorpusId:255800506", "CorpusId:255800506"),
            ("corpus:255800506", "CorpusId:255800506"),
            ("MAG:3035965352", "MAG:3035965352"),
            ("acl:W12-3456", "ACL:W12-3456"),
            ("URL:https://arxiv.org/abs/2006.10256", "URL:https://arxiv.org/abs/2006.10256"),
            ("not an id", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_paper_id(self, raw, expected):
        assert SemanticScholarAdapter.normalize_paper_id(raw) == expected

    @pytest.mark.parametrize(
        "query, expected",
        [
            (f"DOI:{DOI}", True),
            (DOI, True),
            (PAPER_ID, True),
            ("PMID:1234", True),
            ("PMC9839201", True),
            ("arxiv:2006.10256", True),
            ("long covid", False),
            ("12345", False),  # a bare number is searched as text
        ],
    )
    def test_looks_like_id(self, query, expected):
        assert SemanticScholarAdapter._looks_like_id(query) is expected

    def test_path_encoding(self):
        assert SemanticScholarAdapter._path(f"DOI:{DOI}") == f"DOI:{DOI}"
        assert SemanticScholarAdapter._path("DOI:10.1002/(SICI)1097 x#y") == (
            "DOI:10.1002/(SICI)1097%20x%23y"
        )


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_concepts(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            results = await adapter.search_concepts("long covid", limit=3)
        assert sent_url(mock) == f"{ss.BASE_URL}/paper/search"
        params = sent_params(mock)
        assert params["query"] == "long covid" and params["limit"] == 3
        assert "tldr" in params["fields"] and "authors.name" in params["fields"]
        assert results and all(c.concept_type == ConceptType.CITATION for c in results)
        first = results[0]
        assert first.primary_id == fx.SEARCH_LONG_COVID["data"][0]["paperId"]
        assert first.sources == [KnowledgeSource.SEMANTICSCHOLAR]

    @pytest.mark.asyncio
    async def test_limit_handling(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            results = await adapter.search_concepts("long covid", limit=1)
        assert len(results) == 1
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            await adapter.search_concepts("long covid", limit=5000)
        assert sent_params(mock)["limit"] == ss.MAX_SEARCH_LIMIT
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            assert await adapter.search_concepts("long covid", limit=0) == []
            assert await adapter.search_concepts("", limit=5) == []
            assert await adapter.search_concepts("   ", limit=5) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicates_and_unusable_rows_are_dropped(self, adapter):
        record = fx.PAPER_DAVIS
        data = {
            "total": 4,
            "data": [record, copy.deepcopy(record), {"paperId": "x" * 40}, "junk", {"title": "t"}],
        }
        ctx, _ = patched(adapter, data)
        with ctx:
            results = await adapter.search_concepts("long covid", limit=10)
        assert [c.primary_id for c in results] == [PAPER_ID]

    @pytest.mark.asyncio
    async def test_empty_and_malformed_responses(self, adapter):
        for response in ({"total": 0, "offset": 0, "data": []}, {"data": None}, None, {}):
            ctx, _ = patched(adapter, response)
            with ctx:
                assert await adapter.search_concepts("zzzz", 5) == []

    @pytest.mark.asyncio
    async def test_identifier_query_resolves_to_that_paper(self, adapter):
        ctx, mock = patched(adapter, fx.PAPER_DAVIS)
        with ctx:
            results = await adapter.search_concepts(f"DOI:{DOI}", limit=5)
        assert [c.primary_id for c in results] == [PAPER_ID]
        assert sent_url(mock).endswith(f"/paper/DOI:{DOI}")

    @pytest.mark.asyncio
    async def test_unknown_identifier_falls_back_to_text_search(self, adapter):
        ctx, mock = patched(adapter, None, fx.SEARCH_LONG_COVID)
        with ctx:
            results = await adapter.search_concepts("PMID:99999999", limit=2)
        assert len(results) == 2
        assert sent_url(mock, 0).endswith("/paper/PMID:99999999")
        assert sent_url(mock, 1).endswith("/paper/search")

    @pytest.mark.asyncio
    async def test_unexpected_error_is_swallowed(self, adapter):
        with patch.object(adapter, "_get", new=AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.search_concepts("long covid", 5) == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_by_doi(self, adapter):
        ctx, mock = patched(adapter, fx.PAPER_DAVIS)
        with ctx:
            concept = await adapter.get_concept_details(DOI)
        assert sent_url(mock) == f"{ss.BASE_URL}/paper/DOI:{DOI}"
        assert sent_params(mock) == {"fields": ss.PAPER_FIELDS}
        assert concept.primary_id == PAPER_ID
        assert (
            concept.primary_label == "Long COVID: major findings, mechanisms and recommendations"
        )
        assert concept.concept_type == ConceptType.CITATION
        assert concept.definitions and concept.definitions[0].startswith("Long COVID is")
        assert set(concept.semantic_types) == {"Review", "JournalArticle"}
        for category in (
            "year:2023",
            "venue:Nature Reviews Microbiology",
            "open_access",
            "field:Medicine",
        ):
            assert category in concept.categories
        identifiers = {i.identifier for i in concept.identifiers}
        assert {f"DOI:{DOI}", "PMID:36639608", "PMC9839201"} <= identifiers
        data = concept.source_data[KnowledgeSource.SEMANTICSCHOLAR]
        assert data["tldr"].startswith("To strengthen long COVID research")
        assert data["citation_count"] == 3472 and data["influential_citation_count"] == 166
        assert data["reference_count"] == 223
        assert data["open_access_pdf"].endswith(".pdf")
        assert data["corpusId"] == 255800506
        assert data["authors"][0] == "Hannah E. Davis"
        assert data["external_ids"]["PubMed"] == "36639608"
        assert "authorId" not in str(data)  # names only, no author profile ids

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "raw, path",
        [
            (PAPER_ID, f"paper/{PAPER_ID}"),
            ("PMID:36639608", "paper/PMID:36639608"),
            ("36639608", "paper/PMID:36639608"),
            ("PMC9839201", "paper/PMCID:9839201"),
            ("CorpusId:255800506", "paper/CorpusId:255800506"),
            ("arxiv:2006.10256", "paper/ARXIV:2006.10256"),
        ],
    )
    async def test_id_forms_reach_the_api_in_its_notation(self, adapter, raw, path):
        ctx, mock = patched(adapter, fx.PAPER_DAVIS)
        with ctx:
            assert await adapter.get_concept_details(raw) is not None
        assert sent_url(mock) == f"{ss.BASE_URL}/{path}"

    @pytest.mark.asyncio
    async def test_missing_abstract_tldr_and_pdf(self, adapter):
        record = copy.deepcopy(fx.PAPER_DAVIS)
        record.update(abstract=None, tldr=None, openAccessPdf=None, venue="", fieldsOfStudy=None)
        record["externalIds"] = {"DOI": DOI, "PubMedCentral": "PMC9839201"}
        ctx, _ = patched(adapter, record)
        with ctx:
            concept = await adapter.get_concept_details(DOI)
        assert concept.definitions == []
        data = concept.source_data[KnowledgeSource.SEMANTICSCHOLAR]
        assert data["tldr"] is None and data["open_access_pdf"] is None
        assert not any(c.startswith(("venue:", "field:")) for c in concept.categories)
        assert "PMC9839201" in {i.identifier for i in concept.identifiers}  # no double prefix

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_failed(self, adapter):
        ctx, _ = patched(adapter, None)
        with ctx:
            assert await adapter.get_concept_details("DOI:10.9999/doesnotexist") is None
        ctx, mock = patched(adapter, fx.PAPER_DAVIS)
        with ctx:
            assert await adapter.get_concept_details("not an id") is None
            assert await adapter.get_concept_details("") is None
        mock.assert_not_called()
        ctx, _ = patched(adapter, RuntimeError("HTTP 500"))
        with ctx:
            assert await adapter.get_concept_details(DOI) is None
        ctx, _ = patched(adapter, {"paperId": PAPER_ID, "title": "  "})
        with ctx:
            assert await adapter.get_concept_details(DOI) is None

    @pytest.mark.asyncio
    async def test_unexpected_error_is_swallowed(self, adapter):
        with patch.object(adapter, "_get", new=AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.get_concept_details(DOI) is None

    @pytest.mark.asyncio
    async def test_malformed_record_is_swallowed(self, adapter):
        ctx, _ = patched(adapter, {"paperId": PAPER_ID, "title": "T", "authors": 5})
        with ctx:
            assert await adapter.get_concept_details(DOI) is None
        assert (
            adapter._paper_to_concept({"paperId": PAPER_ID, "title": "T", "year": 1}) is not None
        )


class TestRelationships:
    @pytest.mark.asyncio
    async def test_references_and_citations(self, adapter):
        ctx, mock = patched(adapter, fx.REFERENCES_DAVIS, fx.CITATIONS_DAVIS)
        with ctx:
            rels = await adapter.get_relationships(DOI, limit=5)
        assert sent_url(mock, 0) == f"{ss.BASE_URL}/paper/DOI:{DOI}/references"
        assert sent_url(mock, 1) == f"{ss.BASE_URL}/paper/DOI:{DOI}/citations"
        assert sent_params(mock, 0) == {"fields": ss.EDGE_FIELDS, "limit": 5}
        cites = [r for r in rels if r["relation_label"] == "cites"]
        cited_by = [r for r in rels if r["relation_label"] == "cited_by"]
        assert cites and cited_by and len(rels) == len(cites) + len(cited_by)
        first = cites[0]
        assert first["related_id"] == fx.REFERENCES_DAVIS["data"][0]["citedPaper"]["paperId"]
        assert first["source"] == "SEMANTICSCHOLAR"
        assert first["is_influential"] is False and first["year"] == 2022
        assert first["related_name"].startswith("Nirmatrelvir")
        assert first["doi"] == "10.1101/2022.11.03.22281783"
        assert "pmid" not in first
        assert any(r.get("pmid") for r in cites + cited_by)
        assert cited_by[0]["related_id"] == fx.CITATIONS_DAVIS["data"][0]["citingPaper"]["paperId"]

    @pytest.mark.asyncio
    async def test_cap_dedup_and_unresolved_rows(self, adapter):
        refs = copy.deepcopy(fx.REFERENCES_DAVIS)
        refs["data"].append(copy.deepcopy(refs["data"][0]))  # duplicate
        refs["data"].append({"isInfluential": True, "citedPaper": {"paperId": None, "title": "?"}})
        refs["data"].append({"citedPaper": "junk"})
        refs["data"].append("junk")
        ctx, _ = patched(adapter, refs, {"data": []})
        with ctx:
            rels = await adapter.get_relationships(DOI, limit=100)
        ids = [r["related_id"] for r in rels]
        assert len(ids) == len(set(ids)) == len(fx.REFERENCES_DAVIS["data"])
        ctx, _ = patched(adapter, fx.REFERENCES_DAVIS, fx.CITATIONS_DAVIS)
        with ctx:
            rels = await adapter.get_relationships(DOI, limit=2)
        assert len([r for r in rels if r["relation_label"] == "cites"]) == 2
        assert len([r for r in rels if r["relation_label"] == "cited_by"]) == 2

    @pytest.mark.asyncio
    async def test_influence_flag_only_when_present(self, adapter):
        row = {"citedPaper": {"paperId": "a" * 40, "title": "No flag", "year": 2020}}
        influential = {"isInfluential": True, "citedPaper": {"paperId": "b" * 40, "title": "T"}}
        ctx, _ = patched(adapter, {"data": [row, influential]}, {"data": []})
        with ctx:
            rels = await adapter.get_relationships(DOI)
        assert "is_influential" not in rels[0]
        assert rels[1]["is_influential"] is True

    @pytest.mark.asyncio
    async def test_limit_bounds_and_invalid_ids(self, adapter):
        ctx, mock = patched(adapter, fx.REFERENCES_DAVIS, fx.CITATIONS_DAVIS)
        with ctx:
            await adapter.get_relationships(DOI, limit=10_000)
        assert sent_params(mock, 0)["limit"] == ss.MAX_EDGE_LIMIT
        ctx, mock = patched(adapter, fx.REFERENCES_DAVIS)
        with ctx:
            assert await adapter.get_relationships(DOI, limit=0) == []
            assert await adapter.get_relationships("not an id") == []
            assert await adapter.get_relationships("") == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_one_failing_direction_keeps_the_other(self, adapter):
        ctx, _ = patched(adapter, RuntimeError("HTTP 500"), fx.CITATIONS_DAVIS)
        with ctx:
            rels = await adapter.get_relationships(DOI, limit=5)
        assert rels and {r["relation_label"] for r in rels} == {"cited_by"}
        ctx, _ = patched(adapter, None, None)
        with ctx:
            assert await adapter.get_relationships(DOI) == []

    @pytest.mark.asyncio
    async def test_unexpected_error_is_swallowed(self, adapter):
        with patch.object(adapter, "_get", new=AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.get_relationships(DOI) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_external_ids(self, adapter):
        ctx, mock = patched(adapter, fx.PAPER_DAVIS)
        with ctx:
            mappings = await adapter.get_mappings("PMID:36639608")
        assert sent_params(mock) == {"fields": ss.MAPPING_FIELDS}
        assert all(
            m["fromId"] == PAPER_ID and m["fromSource"] == "SEMANTICSCHOLAR" for m in mappings
        )
        assert {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"} == set(
            mappings[0]
        )
        pairs = {(m["toSource"], m["toId"]) for m in mappings}
        assert pairs == {
            ("DOI", DOI),
            ("PMID", "36639608"),
            ("PMCID", "PMC9839201"),
            ("CorpusId", "255800506"),
        }
        assert all(m["mappingType"] == "exact" and m["confidence"] == 1.0 for m in mappings)

    @pytest.mark.asyncio
    async def test_all_known_id_types_and_corpus_fallback(self, adapter):
        record = {
            "paperId": PAPER_ID,
            "corpusId": 7,
            "externalIds": {
                "DOI": "10.1/x",
                "ArXiv": "2006.10256",
                "MAG": "3035965352",
                "ACL": "W12-1",
                "DBLP": "journals/x",
                "PubMed": "",
                "Unknown": "ignored",
            },
        }
        ctx, _ = patched(adapter, record)
        with ctx:
            mappings = await adapter.get_mappings(DOI)
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("DOI", "10.1/x"),
            ("ArXiv", "2006.10256"),
            ("MAG", "3035965352"),
            ("ACL", "W12-1"),
            ("DBLP", "journals/x"),
            ("CorpusId", "7"),
        }

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        for response in (None, {}, {"externalIds": {"DOI": DOI}}):
            ctx, _ = patched(adapter, response)
            with ctx:
                assert await adapter.get_mappings(DOI) == []
        ctx, mock = patched(adapter, fx.PAPER_DAVIS)
        with ctx:
            assert await adapter.get_mappings("garbage") == []
        mock.assert_not_called()
        with patch.object(adapter, "_get", new=AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.get_mappings(DOI) == []


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_429_is_retried_with_doubling_backoff_then_succeeds(self, adapter, sleeps):
        ctx, mock = patched(adapter, _RateLimited(None), _RateLimited(None), fx.PAPER_DAVIS)
        with ctx:
            concept = await adapter.get_concept_details(DOI)
        assert concept is not None
        assert mock.await_count == 3
        assert sleeps == [ss.RATE_LIMIT_BACKOFF, 2 * ss.RATE_LIMIT_BACKOFF]

    @pytest.mark.asyncio
    async def test_retry_after_is_honoured_and_capped(self, adapter, sleeps):
        ctx, _ = patched(adapter, _RateLimited(7.0), _RateLimited(900.0), fx.PAPER_DAVIS)
        with ctx:
            assert await adapter.get_concept_details(DOI) is not None
        assert sleeps == [7.0, ss.MAX_RATE_LIMIT_WAIT]

    @pytest.mark.asyncio
    async def test_persistent_429_degrades_without_hammering(self, adapter, sleeps, caplog):
        ctx, mock = patched(adapter, *[_RateLimited(None)] * 20)
        with ctx, caplog.at_level(logging.WARNING, logger=ss.logger.name):
            assert await adapter.get_concept_details(DOI) is None
            assert mock.await_count == ss.MAX_RATE_LIMIT_RETRIES + 1
            mock.reset_mock(side_effect=True)
            mock.side_effect = [_RateLimited(None)] * 20
            assert await adapter.search_concepts("long covid", 5) == []
            assert await adapter.get_relationships(DOI) == []
            assert await adapter.get_mappings(DOI) == []
        assert "429" in caplog.text and ss.API_KEY_ENV in caplog.text  # keyless hint
        # details, search and mappings: one request each; relationships: two
        assert len(sleeps) == 5 * ss.MAX_RATE_LIMIT_RETRIES

    @pytest.mark.asyncio
    async def test_no_keyless_hint_when_a_key_is_set(self, sleeps, caplog, monkeypatch):
        monkeypatch.setenv(ss.API_KEY_ENV, "env-test-key")
        keyed = SemanticScholarAdapter(LookupConfig())
        ctx, _ = patched(keyed, *[_RateLimited(None)] * 3)
        with ctx, caplog.at_level(logging.WARNING, logger=ss.logger.name):
            assert await keyed.get_concept_details(DOI) is None
        assert "429" in caplog.text and ss.API_KEY_ENV not in caplog.text
        assert "env-test-key" not in caplog.text  # the key is never logged

    @pytest.mark.asyncio
    async def test_non_429_errors_are_not_retried_by_the_loop(self, adapter, sleeps):
        ctx, mock = patched(adapter, RuntimeError("HTTP 500"))
        with ctx:
            assert await adapter.get_concept_details(DOI) is None
        assert mock.await_count == 1 and sleeps == []

    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        monkeypatch.setattr(ss, "MIN_REQUEST_INTERVAL", 1.0)
        slept: list[float] = []

        async def fake_sleep(seconds):
            slept.append(seconds)

        clock = iter([100.0, 100.0, 100.2, 100.2, 105.0, 105.0])
        monkeypatch.setattr(ss, "asyncio", SimpleNamespace(Lock=asyncio.Lock, sleep=fake_sleep))
        monkeypatch.setattr(ss, "time", SimpleNamespace(monotonic=lambda: next(clock)))
        ctx, mock = patched(adapter, None, None, None)
        with ctx:
            for _ in range(3):
                await adapter._get("paper/x")
        assert mock.await_count == 3
        assert len(slept) == 1
        assert 0.7 < slept[0] <= ss.MIN_REQUEST_INTERVAL + 1e-6


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, error=None):
        self.status = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self._error:
            raise self._error

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self.responses.pop(0)


class TestSend:
    """The real HTTP method against a fake aiohttp session."""

    async def run(self, adapter, *responses):
        session = FakeSession(*responses)
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            result = await adapter._send(f"{ss.BASE_URL}/paper/x", {"fields": "title"})
        return result, session

    @pytest.mark.asyncio
    async def test_success_without_key_sends_no_key_header(self, adapter):
        result, session = await self.run(adapter, FakeResponse(200, {"paperId": "p"}))
        assert result == {"paperId": "p"}
        headers = session.calls[0]["headers"]
        assert "x-api-key" not in headers and headers["User-Agent"].startswith("AID-PAIS")
        assert session.calls[0]["params"] == {"fields": "title"}

    @pytest.mark.asyncio
    async def test_key_is_sent_as_header_only(self, monkeypatch):
        monkeypatch.setenv(ss.API_KEY_ENV, "env-test-key")
        keyed = SemanticScholarAdapter(LookupConfig())
        _, session = await self.run(keyed, FakeResponse(200, {"paperId": "p"}))
        assert session.calls[0]["headers"]["x-api-key"] == "env-test-key"
        assert "env-test-key" not in str(session.calls[0]["params"])
        assert "env-test-key" not in session.calls[0]["url"]

    @pytest.mark.asyncio
    async def test_429_returns_marker_with_retry_after(self, adapter):
        result, _ = await self.run(adapter, FakeResponse(429, headers={"Retry-After": "12"}))
        assert isinstance(result, _RateLimited) and result.retry_after == 12.0
        result, _ = await self.run(adapter, FakeResponse(429))
        assert isinstance(result, _RateLimited) and result.retry_after is None
        result, _ = await self.run(adapter, FakeResponse(429, headers={"Retry-After": "soon"}))
        assert isinstance(result, _RateLimited) and result.retry_after is None

    @pytest.mark.asyncio
    async def test_429_does_not_trip_the_circuit_breaker(self, adapter):
        breaker = MagicMock()
        breaker.allow_request.return_value = True
        adapter.set_circuit_breaker(breaker)
        result, session = await self.run(adapter, FakeResponse(429))
        assert isinstance(result, _RateLimited)
        assert len(session.calls) == 1  # no immediate retry by the base class
        breaker.record_failure.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [400, 404])
    async def test_unknown_or_malformed_id_is_none_not_an_error(self, adapter, status):
        breaker = MagicMock()
        breaker.allow_request.return_value = True
        adapter.set_circuit_breaker(breaker)
        result, session = await self.run(adapter, FakeResponse(status, {"error": "not found"}))
        assert result is None and len(session.calls) == 1
        breaker.record_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_server_error_raises_after_base_retries(self, adapter):
        failing = [FakeResponse(500, error=RuntimeError("HTTP 500")) for _ in range(5)]
        session = FakeSession(*failing)
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            with pytest.raises(RuntimeError):
                await adapter._send(f"{ss.BASE_URL}/paper/x", None)
        assert 1 < len(session.calls) <= 4
