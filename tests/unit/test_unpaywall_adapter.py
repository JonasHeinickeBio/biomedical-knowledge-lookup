"""Unit tests for UnpaywallAdapter (synthetic fixtures from the documented schema, no network).

The tests use the invented address ``reader@lab.test``; no real address is ever needed.
"""

import copy
import datetime
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import _vocab_common
from knowledge_lookup.adapters import unpaywall_adapter as up
from knowledge_lookup.adapters.unpaywall_adapter import UnpaywallAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import unpaywall_responses as fx

pytestmark = pytest.mark.unit

EMAIL = "reader@lab.test"
GREEN = fx.GREEN_WORK["doi"]
GOLD = fx.GOLD_WORK["doi"]
CLOSED = fx.CLOSED_WORK["doi"]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for name in ("UNPAYWALL_EMAIL", "UNPAYWALL_API_KEY", "unpaywall_api_key"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv("UNPAYWALL_EMAIL", EMAIL)
    a = UnpaywallAdapter(LookupConfig())
    a._spacer.interval = 0
    return a


def router(routes):
    """Fake ``_make_request``: ``routes`` maps the path after ``/v2/`` to a response/exception."""

    async def fake(url, params=None, **kwargs):
        path = url.split("/v2/")[1]
        value = routes[path]
        if callable(value):
            value = value(params or {})
        if isinstance(value, Exception):
            raise value
        return value

    return AsyncMock(side_effect=fake)


class FakeClientError(Exception):
    """Mimics ``aiohttp.ClientResponseError``: its text quotes the full request URL."""

    def __init__(self, status, url):
        super().__init__(f"{status}, message='Unprocessable', url='{url}'")
        self.status = status


class TestEmail:
    def test_unavailable_without_email(self):
        adapter = UnpaywallAdapter(LookupConfig())
        assert adapter.get_source() == KnowledgeSource.UNPAYWALL
        assert adapter.is_available() is False

    def test_available_with_env_email(self, adapter, monkeypatch):
        assert adapter.is_available() is True
        monkeypatch.delenv("UNPAYWALL_EMAIL")
        assert adapter.is_available() is False  # read at call time, not frozen at init

    def test_config_fallback(self):
        adapter = UnpaywallAdapter(LookupConfig(api_keys={"unpaywall": EMAIL}))
        assert adapter.is_available() is True

    def test_env_wins_over_config(self, monkeypatch):
        monkeypatch.setenv("UNPAYWALL_EMAIL", "env@lab.test")
        adapter = UnpaywallAdapter(LookupConfig(api_keys={"unpaywall": EMAIL}))
        assert adapter._email() == "env@lab.test"

    @pytest.mark.parametrize("value", ["", "   ", "not-an-email", "a b@c.de", "a@b", "@x.org"])
    def test_invalid_addresses_are_rejected(self, monkeypatch, value):
        monkeypatch.setenv("UNPAYWALL_EMAIL", value)
        assert UnpaywallAdapter(LookupConfig()).is_available() is False

    @pytest.mark.asyncio
    async def test_no_request_is_made_without_email(self):
        adapter = UnpaywallAdapter(LookupConfig())
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts("fatigue") == []
            assert await adapter.get_concept_details(GREEN) is None
            assert await adapter.get_relationships(GREEN) == []
            assert await adapter.get_mappings(GREEN) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_is_sent_only_as_query_parameter(self, adapter):
        mock = router({GREEN: fx.GREEN_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.get_concept_details(GREEN)
        assert mock.call_args.kwargs["params"] == {"email": EMAIL}
        assert EMAIL not in mock.call_args.args[0]
        assert mock.call_args.kwargs.get("headers") is None

    @pytest.mark.asyncio
    async def test_email_never_reaches_the_logs(self, adapter, caplog):
        url = f"https://api.unpaywall.org/v2/{GREEN}?email={EMAIL}"
        mock = router({GREEN: FakeClientError(422, url), "search": FakeClientError(500, url)})
        with caplog.at_level(logging.DEBUG), patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details(GREEN) is None
            assert await adapter.search_concepts("fatigue") == []
            assert await adapter.get_relationships(GREEN) == []
            assert await adapter.get_mappings(GREEN) == []
        assert caplog.records
        assert EMAIL not in caplog.text
        assert "lab.test" not in caplog.text
        assert "HTTP 422" in caplog.text

    @pytest.mark.asyncio
    async def test_missing_email_message_does_not_name_an_address(self, caplog):
        adapter = UnpaywallAdapter(LookupConfig())
        with caplog.at_level(logging.WARNING):
            await adapter.get_concept_details(GREEN)
        assert "UNPAYWALL_EMAIL" in caplog.text


class TestParseId:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("10.1038/NATURE12373", "10.1038/nature12373"),
            ("doi:10.1038/nature12373", "10.1038/nature12373"),
            ("DOI: 10.1038/nature12373", "10.1038/nature12373"),
            ("https://doi.org/10.1038/nature12373", "10.1038/nature12373"),
            ("http://dx.doi.org/10.1038/nature12373", "10.1038/nature12373"),
            (
                "10.1002/(SICI)1097-0258(19980815)17:15<1661::AID-SIM968>3.0.CO;2-2",
                "10.1002/(sici)1097-0258(19980815)17:15<1661::aid-sim968>3.0.co;2-2",
            ),
            ("PMID:123", None),
            ("long covid", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert UnpaywallAdapter.parse_id(raw) == expected


class TestDetails:
    @pytest.mark.asyncio
    async def test_green_work(self, adapter):
        mock = router({GREEN: fx.GREEN_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(f"https://doi.org/{GREEN.upper()}")
        assert concept.primary_id == GREEN
        assert concept.primary_label == "A synthetic study of fatigue after infection"
        assert concept.concept_type == ConceptType.CITATION
        assert concept.sources == [KnowledgeSource.UNPAYWALL]
        assert "oa_status:green" in concept.categories
        assert "journal:Journal of Synthetic Examples" in concept.categories
        data = concept.source_data[KnowledgeSource.UNPAYWALL]
        assert data["is_oa"] is True
        assert data["oa_status"] == "green"
        assert data["has_repository_copy"] is True
        assert data["journal_issns"] == ["1234-5678", "8765-4321"]
        best = data["best_oa_location"]
        assert best["version"] == "acceptedVersion"
        assert best["host_type"] == "repository"
        assert best["license"] is None  # an absent licence stays absent
        assert best["repository_institution"] == "pubmedcentral.nih.gov"
        assert best["url_for_pdf"].endswith("/pdf")
        assert data["n_oa_locations"] == 2  # the duplicate copy is merged
        assert data["n_embargoed_locations"] == 1
        assert data["authors"][0] == {
            "name": "Jane Doe",
            "orcid": "http://orcid.org/0000-0000-0000-0001",
        }
        assert data["authors"][2]["name"] == "Consortium for Examples"
        assert data["url"] == f"https://doi.org/{GREEN}"

    @pytest.mark.asyncio
    async def test_gold_and_closed_works(self, adapter):
        mock = router({GOLD: fx.GOLD_WORK, CLOSED: fx.CLOSED_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            gold = await adapter.get_concept_details(GOLD)
            closed = await adapter.get_concept_details(CLOSED)
        gdata = gold.source_data[KnowledgeSource.UNPAYWALL]
        assert gdata["oa_status"] == "gold"
        assert gdata["best_oa_location"]["license"] == "cc-by"
        assert gdata["journal_is_in_doaj"] is True
        assert gdata["authors"] == []
        cdata = closed.source_data[KnowledgeSource.UNPAYWALL]
        assert cdata["is_oa"] is False
        assert cdata["oa_status"] == "closed"
        assert cdata["best_oa_location"] is None
        assert cdata["oa_locations"] == []
        assert cdata["journal_issns"] == []

    @pytest.mark.asyncio
    async def test_location_list_is_capped(self, adapter):
        work = copy.deepcopy(fx.GREEN_WORK)
        work["oa_locations"] = [
            {**fx.PREPRINT_LOCATION, "url": f"http://arxiv.org/pdf/2301.{i:05d}"}
            for i in range(30)
        ]
        concept = adapter._work_to_concept(work)
        data = concept.source_data[KnowledgeSource.UNPAYWALL]
        assert len(data["oa_locations"]) == up.MAX_LOCATIONS
        assert data["n_oa_locations"] == 31  # best location + 30

    @pytest.mark.asyncio
    async def test_record_is_cached_per_instance(self, adapter):
        mock = router({GREEN: fx.GREEN_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.get_concept_details(GREEN)
            await adapter.get_relationships(GREEN)
            await adapter.get_mappings(GREEN)
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_is_bounded_and_misses_are_not_cached(self, adapter, monkeypatch):
        monkeypatch.setattr(up, "CACHE_SIZE", 2)
        records = {f"10.1234/n{i}": {**fx.GOLD_WORK, "doi": f"10.1234/n{i}"} for i in range(3)}
        mock = router({**records, "10.1234/miss": fx.ERROR_404})
        with patch.object(adapter, "_make_request", new=mock):
            for doi in records:
                assert await adapter.get_concept_details(doi)
            assert list(adapter._records) == ["10.1234/n1", "10.1234/n2"]
            assert await adapter.get_concept_details("10.1234/miss") is None
            assert await adapter.get_concept_details("10.1234/miss") is None
        assert mock.call_count == 5

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response",
        [
            fx.ERROR_404,
            fx.ERROR_422,
            {},
            {"doi": ""},
            [1],
            None,
            "text",
            FakeClientError(404, "u"),
        ],
    )
    async def test_error_and_odd_responses(self, adapter, response):
        mock = router({GREEN: response})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details(GREEN) is None
            assert await adapter.get_relationships(GREEN) == []
            assert await adapter.get_mappings(GREEN) == []

    @pytest.mark.asyncio
    async def test_invalid_ids(self, adapter):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details("long covid") is None
            assert await adapter.get_relationships("PMID:1") == []
            assert await adapter.get_mappings("") == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_doi_path_is_quoted(self, adapter):
        doi = "10.1002/a b#c"
        mock = router({"10.1002/a%20b%23c": {**fx.GOLD_WORK, "doi": doi}})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter._record(doi) is not None

    def test_untitled_work_uses_its_doi(self, adapter):
        concept = adapter._work_to_concept({"doi": "10.1234/x"})
        assert concept.primary_label == "10.1234/x"

    def test_conversion_errors_are_swallowed(self, adapter):
        assert (
            adapter._work_to_concept({"doi": "10.1234/x", "z_authors": [1], "oa_locations": 5})
            is None
        )
        assert adapter._work_to_concept({"title": "no doi"}) is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_search(self, adapter):
        mock = router({"search": fx.SEARCH_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("fatigue", limit=5)
        assert [c.primary_id for c in concepts] == [GREEN, GOLD]  # duplicate dropped
        assert mock.call_args.kwargs["params"] == {"query": "fatigue", "email": EMAIL}

    @pytest.mark.asyncio
    async def test_open_access_filter_and_limit(self, adapter):
        mock = router({"search": fx.SEARCH_RESPONSE})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("fatigue", 1, open_access_only=False)
        assert len(concepts) == 1
        assert mock.call_args.kwargs["params"]["is_oa"] == "false"

    @pytest.mark.asyncio
    async def test_entries_may_be_bare_doi_objects(self, adapter):
        mock = router({"search": {"results": [fx.GOLD_WORK, {"junk": 1}, "x", {"response": 5}]}})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("open")
        assert [c.primary_id for c in concepts] == [GOLD]

    @pytest.mark.asyncio
    async def test_doi_query_resolves_directly(self, adapter):
        mock = router({GOLD: fx.GOLD_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts(f"doi:{GOLD}")
        assert [c.primary_id for c in concepts] == [GOLD]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query, limit", [("", 5), ("   ", 5), (None, 5), ("fatigue", 0)])
    async def test_empty_query_or_zero_limit(self, adapter, query, limit):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts(query, limit) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response", [{"results": []}, {"results": None}, {"results": "x"}, [1], None, fx.ERROR_422]
    )
    async def test_empty_and_error_responses(self, adapter, response):
        mock = router({"search": response})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts("fatigue") == []

    @pytest.mark.asyncio
    async def test_outer_guard(self, adapter):
        with patch.object(adapter, "_get", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("fatigue") == []
            assert await adapter.get_concept_details(GREEN) is None
            assert await adapter.get_relationships(GREEN) == []
            assert await adapter.get_mappings(GREEN) == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_green_work_edges(self, adapter):
        mock = router({GREEN: fx.GREEN_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(GREEN)
        assert [e["relation_label"] for e in edges] == [
            "available_at",
            "available_at",
            "published_in",
            "published_by",
        ]
        best, preprint, journal, publisher = edges
        assert best["related_id"] == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9999999"
        assert best["related_name"] == "pubmedcentral.nih.gov"
        assert best["version"] == "acceptedVersion" and best["is_best"] is True
        assert best["license"] is None
        assert preprint["version"] == "submittedVersion"
        assert preprint["license"] == "cc-by-nc"
        assert journal["related_id"] == "ISSN:1234-5678"
        assert journal["issns"] == ["1234-5678", "8765-4321"]
        assert journal["journal_is_in_doaj"] is False
        assert publisher["related_id"] == "Example Publisher Ltd"
        assert all(e["source"] == "UNPAYWALL" for e in edges)

    @pytest.mark.asyncio
    async def test_limit_caps_locations(self, adapter):
        mock = router({GREEN: fx.GREEN_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(GREEN, limit=1)
            none = await adapter.get_relationships(GREEN, limit=0)
        assert [e["relation_label"] for e in edges] == [
            "available_at",
            "published_in",
            "published_by",
        ]
        assert none == []

    @pytest.mark.asyncio
    async def test_closed_work_has_no_locations(self, adapter):
        mock = router({CLOSED: fx.CLOSED_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(CLOSED)
        assert [e["relation_label"] for e in edges] == ["published_in"]
        assert edges[0]["related_id"] == "Closed Examples"

    @pytest.mark.asyncio
    async def test_location_name_falls_back_to_host_type(self, adapter):
        work = copy.deepcopy(fx.GOLD_WORK)
        work["publisher"] = None
        work["journal_name"] = None
        work["journal_issns"] = ""
        work["journal_issn_l"] = None
        mock = router({GOLD: work})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(GOLD)
        assert [e["relation_label"] for e in edges] == ["available_at"]
        assert edges[0]["related_name"] == "publisher copy"
        assert edges[0]["related_id"] == "https://doi.org/10.1234/gold.2024.002"

    @pytest.mark.asyncio
    async def test_locations_without_urls_are_skipped(self, adapter):
        work = copy.deepcopy(fx.GOLD_WORK)
        work["best_oa_location"] = {"host_type": "publisher"}
        work["oa_locations"] = [{"host_type": "repository"}, "junk"]
        mock = router({GOLD: work})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(GOLD)
        assert [e["relation_label"] for e in edges] == ["published_in", "published_by"]


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        mock = router({GREEN: fx.GREEN_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings(f"doi:{GREEN}")
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("DOI", GREEN),
            ("ISSN-L", "1234-5678"),
            ("ISSN", "1234-5678"),
            ("ISSN", "8765-4321"),
        }
        assert all(m["fromId"] == GREEN and m["fromSource"] == "UNPAYWALL" for m in mappings)
        assert all(m["mappingType"] == "exact" and m["confidence"] == 1.0 for m in mappings)

    @pytest.mark.asyncio
    async def test_closed_work_only_maps_the_doi(self, adapter):
        mock = router({CLOSED: fx.CLOSED_WORK})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings(CLOSED)
        assert [(m["toSource"], m["toId"]) for m in mappings] == [("DOI", CLOSED)]

    @pytest.mark.asyncio
    async def test_issns_may_be_a_list(self, adapter):
        work = {**fx.GOLD_WORK, "journal_issns": ["2345-6789", " ", "3456-7890"]}
        mock = router({GOLD: work})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings(GOLD)
        assert [m["toId"] for m in mappings if m["toSource"] == "ISSN"] == [
            "2345-6789",
            "3456-7890",
        ]


class TestLimitsAndThrottling:
    @pytest.mark.asyncio
    async def test_daily_budget_is_enforced_and_resets(self, adapter, monkeypatch, caplog):
        day = {"d": datetime.date(2026, 10, 9)}
        monkeypatch.setattr(up, "_utc_today", lambda: day["d"])
        monkeypatch.setattr(up, "DAILY_LIMIT", 2)
        adapter._day = day["d"]
        mock = router(
            {f"10.1234/n{i}": {**fx.GOLD_WORK, "doi": f"10.1234/n{i}"} for i in range(4)}
        )
        with caplog.at_level(logging.WARNING), patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details("10.1234/n0")
            assert await adapter.get_concept_details("10.1234/n1")
            assert await adapter.get_concept_details("10.1234/n2") is None  # over budget
            assert mock.call_count == 2
            assert "100,000 calls/day" in caplog.text
            assert await adapter.get_concept_details("10.1234/n0")  # cached: free
            day["d"] += datetime.timedelta(days=1)
            assert await adapter.get_concept_details("10.1234/n3")  # new UTC day
        assert adapter._calls_today == 1

    def test_documented_daily_limit(self):
        assert up.DAILY_LIMIT == 100_000

    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        sleeps: list[float] = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        clock = {"now": 10.0}
        # replace the names inside the helper module only: patching asyncio.sleep or
        # time.monotonic themselves would also change the event loop's clock
        monkeypatch.setattr(_vocab_common, "asyncio", SimpleNamespace(sleep=fake_sleep))
        monkeypatch.setattr(_vocab_common, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
        adapter._spacer.interval = up.MIN_INTERVAL
        mock = router(
            {"10.1234/a": fx.GOLD_WORK, "10.1234/b": fx.GREEN_WORK, "10.1234/c": fx.GOLD_WORK}
        )
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.get_concept_details("10.1234/a")
            await adapter.get_concept_details("10.1234/b")
            clock["now"] += 5.0
            await adapter.get_concept_details("10.1234/c")
        assert sleeps == [pytest.approx(up.MIN_INTERVAL)]


class TestRegistry:
    def test_registered(self):
        from knowledge_lookup.adapters import ADAPTER_CLASSES

        assert ADAPTER_CLASSES[KnowledgeSource.UNPAYWALL] is UnpaywallAdapter
