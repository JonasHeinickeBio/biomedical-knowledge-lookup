"""Unit tests for BioRxivAdapter (trimmed real responses, no network)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import biorxiv_adapter as bx
from knowledge_lookup.adapters.biorxiv_adapter import BioRxivAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import biorxiv_responses as fx

pytestmark = pytest.mark.unit

ZHOU = "10.1101/2020.01.22.914952"
NEW_MEDRXIV = "10.64898/2026.09.22.26363331"
OLD_MEDRXIV = "10.1101/2021.01.27.21250617"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(bx.asyncio, "sleep", AsyncMock())


@pytest.fixture
def adapter():
    return BioRxivAdapter(LookupConfig())


class HttpError(Exception):
    """Stand-in for ``aiohttp.ClientResponseError`` (which needs a real request object)."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


def server_error():
    return HttpError(500)


def routed(adapter, routes):
    """Patch ``_make_request``: first route whose key is a substring of the URL answers.

    A route value that is an exception instance is raised; a list is consumed one element
    per call (the last element repeats).
    """
    calls: list[tuple[str, dict | None]] = []
    state: dict[str, int] = {}

    async def fake(url, params=None, headers=None, json_data=None):
        calls.append((url, params))
        for key, value in routes:
            if key in url:
                if isinstance(value, list):
                    index = state.get(key, 0)
                    state[key] = index + 1
                    value = value[min(index, len(value) - 1)]
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
        raise AssertionError(f"unexpected request {url}")

    return patch.object(adapter, "_make_request", new=fake), calls


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.BIORXIV
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (ZHOU, (ZHOU, None)),
            (ZHOU + "v2", (ZHOU, 2)),
            ("doi:" + ZHOU, (ZHOU, None)),
            ("https://doi.org/" + ZHOU, (ZHOU, None)),
            (f"https://www.biorxiv.org/content/{ZHOU}v1.full", (ZHOU, 1)),
            (
                f"https://www.medrxiv.org/content/{OLD_MEDRXIV}v3.full.pdf?download=1",
                (OLD_MEDRXIV, 3),
            ),
            (
                f"https://www.medrxiv.org/content/early/2021/01/29/{OLD_MEDRXIV}",
                (OLD_MEDRXIV, None),
            ),
            (NEW_MEDRXIV, (NEW_MEDRXIV, None)),
            ("doi:" + NEW_MEDRXIV + "v1", (NEW_MEDRXIV, 1)),
            ("long covid", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert BioRxivAdapter.parse_id(raw) == expected

    def test_server_order(self):
        assert BioRxivAdapter._server_order(OLD_MEDRXIV) == ("medrxiv", "biorxiv")
        assert BioRxivAdapter._server_order(NEW_MEDRXIV) == ("medrxiv", "biorxiv")
        assert BioRxivAdapter._server_order(ZHOU) == ("biorxiv", "medrxiv")


class TestDetails:
    @pytest.mark.asyncio
    async def test_latest_version_and_preprint_notice(self, adapter):
        ctx, calls = routed(adapter, [("/details/biorxiv/", fx.DETAILS_ZHOU)])
        with ctx:
            concept = await adapter.get_concept_details(ZHOU)
        assert calls[0][0] == f"https://api.biorxiv.org/details/biorxiv/{ZHOU}"
        assert concept.primary_id == ZHOU
        assert concept.concept_type == ConceptType.CITATION
        assert concept.primary_label.startswith("Discovery of a novel coronavirus")
        assert "not_peer_reviewed" in concept.categories
        assert "server:bioRxiv" in concept.categories
        assert "category:microbiology" in concept.categories
        assert "published_in_journal" in concept.categories
        data = concept.source_data[KnowledgeSource.BIORXIV]
        assert data["peer_reviewed"] is False
        assert "not peer reviewed" in data["notice"]
        assert data["version"] == 2
        assert [v["version"] for v in data["versions"]] == ["1", "2"]
        assert data["published_doi"] == "10.1038/s41586-020-2012-7"
        assert data["license_text"].startswith("No Creative Commons")
        assert data["authors"][0] == "Zhou, P."
        assert data["url"] == f"https://www.biorxiv.org/content/{ZHOU}v2"
        assert concept.definitions and concept.definitions[0].startswith("Since the SARS")

    @pytest.mark.asyncio
    async def test_specific_version_and_missing_version(self, adapter):
        ctx, _ = routed(adapter, [("/details/biorxiv/", fx.DETAILS_ZHOU)])
        with ctx:
            first = await adapter.get_concept_details(ZHOU + "v1")
            missing = await adapter.get_concept_details(ZHOU + "v9")
        assert first.source_data[KnowledgeSource.BIORXIV]["version"] == 1
        assert missing is None

    @pytest.mark.asyncio
    async def test_new_prefix_medrxiv_is_tried_first_and_unpublished(self, adapter):
        ctx, calls = routed(adapter, [("/details/medrxiv/", fx.DETAILS_MEDRXIV_NEW_PREFIX)])
        with ctx:
            concept = await adapter.get_concept_details("https://doi.org/" + NEW_MEDRXIV)
        assert [c[0].split("/")[4] for c in calls] == ["medrxiv"]
        data = concept.source_data[KnowledgeSource.BIORXIV]
        assert concept.primary_id == NEW_MEDRXIV
        assert data["published_doi"] == ""
        assert data["server"] == "medRxiv"
        assert data["url"].startswith("https://www.medrxiv.org/content/10.64898/")
        assert "published_in_journal" not in concept.categories

    @pytest.mark.asyncio
    async def test_wrong_server_falls_through_to_other(self, adapter):
        ctx, calls = routed(
            adapter,
            [
                ("/details/biorxiv/", fx.NO_POSTS),
                ("/details/medrxiv/", fx.DETAILS_MEDRXIV_NEW_PREFIX),
            ],
        )
        with ctx:
            concept = await adapter.get_concept_details("10.1101/2020.05.05.123456")
        assert concept is not None
        assert [c[0].split("/")[4] for c in calls] == ["biorxiv", "medrxiv"]

    @pytest.mark.asyncio
    async def test_unknown_doi(self, adapter):
        ctx, _ = routed(adapter, [("/details/", fx.NO_POSTS)])
        with ctx:
            assert await adapter.get_concept_details("10.1101/9999.99.99.999999") is None

    @pytest.mark.asyncio
    async def test_details_500_falls_back_to_pubs(self, adapter):
        ctx, calls = routed(
            adapter,
            [("/details/", server_error()), ("/pubs/medrxiv/", fx.PUBS_ZHOU_AS_MEDRXIV)],
        )
        with ctx:
            concept = await adapter.get_concept_details(OLD_MEDRXIV)
        assert concept is not None
        assert concept.primary_id == OLD_MEDRXIV
        data = concept.source_data[KnowledgeSource.BIORXIV]
        assert data["partial"] is True
        assert data["published_doi"] == "10.1038/s41598-021-95565-8"
        assert any("/pubs/" in c[0] for c in calls)

    @pytest.mark.asyncio
    async def test_details_500_and_pubs_empty_returns_none(self, adapter):
        ctx, _ = routed(adapter, [("/details/", server_error()), ("/pubs/", fx.NO_POSTS)])
        with ctx:
            assert await adapter.get_concept_details(ZHOU) is None

    @pytest.mark.asyncio
    async def test_invalid_id_makes_no_request(self, adapter):
        ctx, calls = routed(adapter, [("/", fx.NO_POSTS)])
        with ctx:
            assert await adapter.get_concept_details("nonsense") is None
            assert await adapter.get_relationships("nonsense") == []
            assert await adapter.get_mappings("nonsense") == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_non_dict_payload_counts_as_failure(self, adapter):
        ctx, _ = routed(adapter, [("/", ["not", "a", "dict"])])
        with ctx:
            assert await adapter.get_concept_details(ZHOU) is None

    @pytest.mark.asyncio
    async def test_unexpected_error_is_swallowed(self, adapter):
        with patch.object(adapter, "_fetch_versions", side_effect=RuntimeError("x")):
            assert await adapter.get_concept_details(ZHOU) is None
            assert await adapter.get_relationships(ZHOU) == []
            assert await adapter.get_mappings(ZHOU) == []

    def test_row_without_doi_is_skipped(self, adapter):
        assert adapter._row_to_concept({"title": "x"}, []) is None
        assert (
            adapter._row_to_concept({"doi": "10.1101/a", "authors": 5, "title": None}, [])
            is not None
        )

    def test_row_conversion_error_is_swallowed(self, adapter):
        assert adapter._row_to_concept({"doi": "10.1101/a"}, [5]) is None  # type: ignore[list-item]


class TestRelationships:
    @pytest.mark.asyncio
    async def test_published_article_and_earlier_version(self, adapter):
        ctx, _ = routed(
            adapter,
            [
                ("/details/", fx.DETAILS_ZHOU),
                ("/pubs/biorxiv/", fx.PUBS_ZHOU),
                ("europepmc", fx.EPMC_ZHOU),
            ],
        )
        with ctx:
            edges = await adapter.get_relationships(ZHOU)
        assert [e["relation_label"] for e in edges] == ["is_preprint_of", "has_earlier_version"]
        published, earlier = edges
        assert published["related_id"] == "10.1038/s41586-020-2012-7"
        assert published["related_name"] == "Nature"
        assert published["published_date"] == "2020-02-03"
        assert published["related_pmid"] == "32015507"
        assert published["source"] == "BIORXIV"
        assert earlier["related_id"] == f"{ZHOU}v1"
        assert earlier["version"] == 1 and earlier["version_date"] == "2020-01-23"

    @pytest.mark.asyncio
    async def test_unpublished_preprint_has_no_published_edge_and_no_extra_requests(self, adapter):
        details = copy.deepcopy(fx.DETAILS_MEDRXIV_NEW_PREFIX)
        ctx, calls = routed(adapter, [("/details/", details)])
        with ctx:
            edges = await adapter.get_relationships(NEW_MEDRXIV)
        assert all(e["relation_label"] == "has_earlier_version" for e in edges)
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_published_without_pubs_or_epmc_data(self, adapter):
        ctx, _ = routed(
            adapter,
            [
                ("/details/", fx.DETAILS_ZHOU),
                ("/pubs/", server_error()),
                ("europepmc", server_error()),
            ],
        )
        with ctx:
            edges = await adapter.get_relationships(ZHOU)
        published = edges[0]
        assert published["related_name"] == "10.1038/s41586-020-2012-7"
        assert published["published_date"] is None
        assert "related_pmid" not in published

    @pytest.mark.asyncio
    async def test_partial_row_without_version_has_no_version_edges(self, adapter):
        ctx, _ = routed(
            adapter,
            [
                ("/details/", server_error()),
                ("/pubs/", fx.PUBS_ZHOU_AS_MEDRXIV),
                ("europepmc", {}),
            ],
        )
        with ctx:
            edges = await adapter.get_relationships(OLD_MEDRXIV)
        assert [e["relation_label"] for e in edges] == ["is_preprint_of"]

    @pytest.mark.asyncio
    async def test_unknown_preprint(self, adapter):
        ctx, _ = routed(adapter, [("/details/", fx.NO_POSTS)])
        with ctx:
            assert await adapter.get_relationships(ZHOU) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_doi_published_doi_and_pmid(self, adapter):
        ctx, _ = routed(adapter, [("/details/", fx.DETAILS_ZHOU), ("europepmc", fx.EPMC_ZHOU)])
        with ctx:
            mappings = await adapter.get_mappings(ZHOU)
        assert [(m["toSource"], m["toId"], m["mappingType"]) for m in mappings] == [
            ("DOI", ZHOU, "exact"),
            ("DOI", "10.1038/s41586-020-2012-7", "published_version"),
            ("PubMed", "32015507", "published_version"),
        ]
        assert all(m["fromId"] == ZHOU and m["fromSource"] == "BIORXIV" for m in mappings)
        assert set(mappings[0]) == {
            "fromId",
            "toId",
            "fromSource",
            "toSource",
            "mappingType",
            "confidence",
        }

    @pytest.mark.asyncio
    async def test_unpublished_only_self_mapping(self, adapter):
        ctx, calls = routed(adapter, [("/details/", fx.DETAILS_MEDRXIV_NEW_PREFIX)])
        with ctx:
            mappings = await adapter.get_mappings(NEW_MEDRXIV)
        assert len(mappings) == 1 and len(calls) == 1

    @pytest.mark.asyncio
    async def test_published_without_pmid(self, adapter):
        ctx, _ = routed(
            adapter, [("/details/", fx.DETAILS_ZHOU), ("europepmc", {"resultList": {}})]
        )
        with ctx:
            mappings = await adapter.get_mappings(ZHOU)
        assert [m["toSource"] for m in mappings] == ["DOI", "DOI"]

    @pytest.mark.asyncio
    async def test_unknown_preprint(self, adapter):
        ctx, _ = routed(adapter, [("/details/", fx.NO_POSTS)])
        with ctx:
            assert await adapter.get_mappings(ZHOU) == []


class TestEuropePmcSearch:
    @pytest.mark.asyncio
    async def test_search_concepts(self, adapter):
        ctx, calls = routed(adapter, [("europepmc", fx.EPMC_SEARCH)])
        with ctx:
            results = await adapter.search_concepts("long covid", limit=3)
        url, params = calls[0]
        assert url == bx.EPMC_URL
        assert params["query"] == (
            '(long covid) AND SRC:PPR AND (PUBLISHER:"bioRxiv" OR PUBLISHER:"medRxiv")'
        )
        assert params["pageSize"] == 3 and params["resultType"] == "core"
        assert "sort" not in params
        assert [c.primary_id for c in results] == [
            r["doi"] for r in fx.EPMC_SEARCH["resultList"]["result"]
        ]
        first = results[0]
        assert first.concept_type == ConceptType.CITATION
        assert "not_peer_reviewed" in first.categories
        assert "server:medRxiv" in first.categories
        assert "<i>" not in first.primary_label
        assert first.definitions
        data = first.source_data[KnowledgeSource.BIORXIV]
        assert data["peer_reviewed"] is False
        assert data["from_search_index"] is True
        assert data["url"].startswith("https://www.medrxiv.org/content/10.64898/")

    @pytest.mark.asyncio
    async def test_server_filter_and_sort(self, adapter):
        ctx, calls = routed(adapter, [("europepmc", fx.EPMC_SEARCH)])
        with ctx:
            await adapter.search_preprints("fatigue", 5, server="MedRxiv", sort="date")
        params = calls[0][1]
        assert params["query"].endswith('AND (PUBLISHER:"medRxiv")')
        assert params["sort"] == "P_PDATE_D desc"

    @pytest.mark.asyncio
    async def test_unknown_server_and_empty_queries(self, adapter):
        ctx, calls = routed(adapter, [("/", fx.EPMC_SEARCH)])
        with ctx:
            assert await adapter.search_preprints("x", 5, server="arxiv") == []
            assert await adapter.search_preprints("", 5) == []
            assert await adapter.search_preprints("x", 0) == []
            assert await adapter.search_concepts("x", 0) == []
            assert await adapter.search_concepts("  ", 5) == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_limit_is_capped(self, adapter):
        ctx, calls = routed(adapter, [("europepmc", fx.EPMC_SEARCH)])
        with ctx:
            results = await adapter.search_preprints("x", 5000)
        assert calls[0][1]["pageSize"] == bx.MAX_RESULTS
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_limit_truncates_and_deduplicates(self, adapter):
        data = copy.deepcopy(fx.EPMC_SEARCH)
        rows = data["resultList"]["result"]
        data["resultList"]["result"] = [rows[0], rows[0], {"title": "no doi"}, rows[1], rows[2]]
        ctx, _ = routed(adapter, [("europepmc", data)])
        with ctx:
            assert len(await adapter.search_preprints("x", 10)) == 3
            assert len(await adapter.search_preprints("x", 1)) == 1

    @pytest.mark.asyncio
    async def test_no_hits_does_not_trigger_fallback(self, adapter):
        empty = {"hitCount": 0, "resultList": {"result": []}}
        ctx, calls = routed(adapter, [("europepmc", empty)])
        with ctx:
            assert await adapter.search_concepts("zzzzzz") == []
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_doi_query_resolves_to_details(self, adapter):
        ctx, calls = routed(adapter, [("/details/biorxiv/", fx.DETAILS_ZHOU)])
        with ctx:
            results = await adapter.search_concepts(f"https://www.biorxiv.org/content/{ZHOU}v1")
        assert [c.primary_id for c in results] == [ZHOU]
        assert not any("europepmc" in c[0] for c in calls)

    @pytest.mark.asyncio
    async def test_doi_query_not_found(self, adapter):
        ctx, _ = routed(adapter, [("/details/", fx.NO_POSTS)])
        with ctx:
            assert await adapter.search_concepts("10.1101/9999.99.99.999999") == []

    @pytest.mark.asyncio
    async def test_unexpected_errors(self, adapter):
        with patch.object(adapter, "search_preprints", side_effect=RuntimeError("x")):
            assert await adapter.search_concepts("x") == []
        with patch.object(adapter, "_search_europepmc", side_effect=RuntimeError("x")):
            assert await adapter.search_preprints("x") == []

    def test_epmc_record_conversion_error_and_missing_fields(self, adapter):
        assert adapter._epmc_to_concept({"title": "x"}) is None
        assert adapter._epmc_to_concept({"doi": "10.1101/a", "authorString": 5}) is not None
        assert adapter._epmc_to_concept({"doi": "10.1101/a", "bookOrReportDetails": 3}) is not None
        assert (
            adapter._epmc_to_concept({"doi": "10.1101/a", "title": 3, "id": object()}) is not None
        )

    def test_published_pmid_edge_cases(self):
        assert BioRxivAdapter._published_pmid(None) is None
        assert BioRxivAdapter._published_pmid({"commentCorrectionList": {}}) is None
        record = {
            "commentCorrectionList": {
                "commentCorrection": [
                    "junk",
                    {"source": "MED", "id": "1", "type": "Erratum in"},
                    {"source": "PMC", "id": "2", "type": "Preprint of"},
                    {"source": "MED", "id": "3", "type": "Preprint of"},
                ]
            }
        }
        assert BioRxivAdapter._published_pmid(record) == "3"


def interval_page(rows, total, count=None):
    return {
        "messages": [
            {"status": "ok", "cursor": 0, "count": count or len(rows), "total": str(total)}
        ],
        "collection": rows,
    }


class TestWindowScan:
    @pytest.mark.asyncio
    async def test_epmc_failure_falls_back_to_recent_window(self, adapter, monkeypatch):
        class FixedDateTime(bx.datetime):
            @classmethod
            def now(cls, tz=None):
                return bx.datetime(2025, 9, 3, 12, tzinfo=tz)

        monkeypatch.setattr(bx, "datetime", FixedDateTime)
        ctx, calls = routed(
            adapter,
            [
                ("europepmc", server_error()),
                ("/details/biorxiv/", interval_page([], 0)),
                ("/details/medrxiv/", fx.INTERVAL_PAGE),
            ],
        )
        with ctx:
            results = await adapter.search_concepts("syndrome", limit=5)
        urls = [c[0] for c in calls if "europepmc" not in c[0]]
        assert urls[0] == "https://api.biorxiv.org/details/biorxiv/2025-08-27/2025-09-03/0"
        assert any("/details/medrxiv/2025-08-27/2025-09-03/0" in u for u in urls)
        assert results and all(
            "syndrome"
            in " ".join([c.primary_label] + (c.definitions or []) + c.categories).lower()
            for c in results
        )

    @pytest.mark.asyncio
    async def test_explicit_window_pages_until_total_and_keeps_latest_version(self, adapter):
        rows = fx.INTERVAL_PAGE["collection"]
        older = dict(rows[0], version="1", title="old title covid")
        newer = dict(rows[0], version="2", title="new title covid")
        page1 = interval_page([older, rows[1]], 3)
        page2 = interval_page([newer], 3)
        ctx, calls = routed(
            adapter,
            [
                ("/details/medrxiv/2025-09-01/2025-09-03/0", page1),
                ("/details/medrxiv/2025-09-01/2025-09-03/2", page2),
            ],
        )
        with ctx:
            results = await adapter.search_preprints(
                "covid", 10, server="medrxiv", start="2025-09-01", end="2025-09-03"
            )
        assert [c[0].rsplit("/", 1)[1] for c in calls] == ["0", "2"]
        assert [r.primary_label for r in results] == ["new title covid"]

    @pytest.mark.asyncio
    async def test_category_filter_is_sent_and_limit_stops_scan(self, adapter):
        rows = [
            dict(fx.INTERVAL_PAGE["collection"][0], doi=f"10.1101/x{i}", title="covid")
            for i in range(3)
        ]
        ctx, calls = routed(adapter, [("/details/", interval_page(rows, 500))])
        with ctx:
            results = await adapter.search_preprints(
                "covid",
                2,
                server="medrxiv",
                start="2025-09-01",
                end="2025-09-03",
                category="infectious_diseases",
            )
        assert len(results) == 2
        assert len(calls) == 1  # limit reached after the first page
        assert calls[0][1] == {"category": "infectious_diseases"}

    @pytest.mark.asyncio
    async def test_scan_stops_after_max_pages_and_on_failure(self, adapter, monkeypatch):
        monkeypatch.setattr(bx, "SCAN_MAX_PAGES", 2)
        rows = [
            dict(
                fx.INTERVAL_PAGE["collection"][0],
                doi="10.1101/nomatch",
                title="zzz",
                abstract="",
                category="",
            )
        ]
        ctx, calls = routed(adapter, [("/details/", interval_page(rows, 500))])
        with ctx:
            assert (
                await adapter.search_preprints(
                    "covid", 5, server="medrxiv", start="2025-09-01", end="2025-09-02"
                )
                == []
            )
        assert len(calls) == 2
        ctx, calls = routed(adapter, [("/details/", server_error())])
        with ctx:
            assert (
                await adapter.search_preprints(
                    "covid", 5, server="medrxiv", start="2025-09-01", end="2025-09-02"
                )
                == []
            )
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_invalid_dates(self, adapter):
        ctx, calls = routed(adapter, [("/", fx.INTERVAL_PAGE)])
        with ctx:
            assert await adapter.search_preprints("covid", 5, start="yesterday") == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_only_start_date_scans_up_to_today(self, adapter):
        ctx, calls = routed(adapter, [("/details/", interval_page([], 0))])
        with ctx:
            await adapter.search_preprints("covid", 5, server="biorxiv", start="2025-01-01")
        assert "/2025-01-01/" in calls[0][0]


class TestThrottle:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        clock = [10.0]
        monkeypatch.setattr(bx.time, "monotonic", lambda: clock[0])
        slept: list[float] = []

        async def fake_sleep(delay):
            slept.append(delay)
            clock[0] += delay

        monkeypatch.setattr(bx.asyncio, "sleep", fake_sleep)
        ctx, _ = routed(adapter, [("/details/", fx.DETAILS_ZHOU)])
        with ctx:
            await adapter.get_concept_details(ZHOU)
            await adapter.get_concept_details(ZHOU)
        assert len(slept) == 1
        assert slept[0] == pytest.approx(bx.REQUEST_INTERVAL, abs=1e-6)


def test_clean_and_split_helpers():
    assert bx._clean("<i>a</i>  b &amp; c") == "a b & c"
    assert bx._clean(None) == ""
    assert bx._split_authors("A, B.; C, D.;; ") == ["A, B.", "C, D."]
    assert bx._split_authors(None) == []
    assert bx._version_key({"version": "3"}) == 3
    assert bx._version_key({"version": "x"}) == 0
    assert bx._version_key({}) == 0
