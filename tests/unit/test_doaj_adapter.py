"""Unit tests for DOAJAdapter (trimmed real v4 responses, no network)."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import unquote

import pytest

from knowledge_lookup.adapters import _vocab_common
from knowledge_lookup.adapters import doaj_adapter as dj
from knowledge_lookup.adapters.doaj_adapter import DOAJAdapter, sanitize_query
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import doaj_responses as fx

pytestmark = pytest.mark.unit

PLOS = fx.JOURNAL_PLOS["id"]
KARDIO = fx.JOURNAL_KARDIO["id"]
ARTICLE = fx.ARTICLE_PLOS["id"]
DOI = "10.1371/journal.pone.0326790"


@pytest.fixture
def adapter():
    a = DOAJAdapter(LookupConfig())
    a._spacer.interval = 0
    return a


def router(routes):
    """Fake ``_make_request``: ``routes`` maps the decoded path after ``/api/v4/`` to a
    response, an exception or a callable ``(params) -> response``."""

    async def fake(url, params=None, **kwargs):
        path = unquote(url.split("/api/v4/")[1])
        value = routes[path]
        if callable(value):
            value = value(params or {})
        if isinstance(value, Exception):
            raise value
        return value

    return AsyncMock(side_effect=fake)


class NotFound(Exception):
    status = 404


class TestSanitize:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("long covid", "long covid"),
            ("  long   covid ", "long covid"),
            ("title:medicine", "title:medicine"),
            ('bibjson.title:"lancet"', 'bibjson.title:"lancet"'),
            ("issn:1897-4252", "issn:1897-4252"),
            ("doi:10.1371/journal.pone.0326790", "doi:10.1371/journal.pone.0326790"),
            ("covid AND (fatigue OR pain)", "covid AND (fatigue OR pain)"),
            ("covid AND NOT vaccine", "covid AND NOT vaccine"),
            ('"long covid"', '"long covid"'),
            ("NOT vaccine", "NOT vaccine"),
            ("COVID-19: long (review", "COVID 19 long review"),
            ("covid AND", "covid and"),
            ("AND covid", "and covid"),
            ("covid AND OR pain", "covid and or pain"),
            ('title:"lancet', "title lancet"),
            ("title:(a OR b", "title a OR b".replace("OR", "or")),
            ("(review", "review"),
            ("a)b(", "a b"),
            ("title:()", "title"),
            ("a && b || c", "a b c"),
            ("wild*card?", "wild card"),
            ("path\\x ^2 ~3", "path x 2 3"),
            ("AND", "and"),
            ("", ""),
            ("   ", ""),
            (None, ""),
            ("+-!()[]{}", ""),
        ],
    )
    def test_sanitize_query(self, raw, expected):
        assert sanitize_query(raw) == expected

    def test_non_ascii_structured_query_passes(self):
        assert sanitize_query("title:Ménière") == "title:Ménière"
        assert sanitize_query("Müdigkeit bei ME/CFS") == "Müdigkeit bei ME CFS"


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.DOAJ
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (PLOS, ("any", PLOS)),
            (PLOS.upper(), ("any", PLOS)),
            (f"journal:{PLOS}", ("journal", PLOS)),
            (f"article:{ARTICLE}", ("article", ARTICLE)),
            (f"doaj:{PLOS}", ("any", PLOS)),
            (f"https://doaj.org/toc/{PLOS}", ("journal", PLOS)),
            (f"https://doaj.org/article/{ARTICLE}", ("article", ARTICLE)),
            ("1932-6203", ("issn", "1932-6203")),
            ("19326203", ("issn", "1932-6203")),
            ("ISSN:1874-949x", ("issn", "1874-949X")),
            ("eISSN: 1932-6203", ("issn", "1932-6203")),
            (DOI, ("doi", DOI)),
            (f"doi:{DOI}", ("doi", DOI)),
            (f"https://doi.org/{DOI}", ("doi", DOI)),
            ("PLoS ONE", None),
            ("journal:nothex", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert DOAJAdapter.parse_id(raw) == expected


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_journals(self, adapter):
        mock = router({"search/journals/PLoS ONE": fx.JOURNAL_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_journals("PLoS ONE", limit=5)
        assert [c.primary_id for c in concepts] == [f"journal:{PLOS}"]
        assert concepts[0].primary_label == "PLoS ONE"
        assert concepts[0].concept_type == ConceptType.UNKNOWN
        assert mock.call_args.kwargs["params"] == {"page": 1, "pageSize": 5}
        assert "search/journals/PLoS%20ONE" in mock.call_args.args[0]

    @pytest.mark.asyncio
    async def test_query_is_encoded_as_a_path_segment(self, adapter):
        mock = router({'search/articles/doi:"10.1371/x"': fx.EMPTY_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_articles('doi:"10.1371/x"')
        url = mock.call_args.args[0]
        assert url.endswith("search/articles/doi%3A%2210.1371%2Fx%22")

    @pytest.mark.asyncio
    async def test_search_articles(self, adapter):
        mock = router({"search/articles/long covid": fx.ARTICLE_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_articles("long covid", limit=500)
        assert [c.primary_id for c in concepts] == [f"article:{ARTICLE}"]
        assert concepts[0].concept_type == ConceptType.CITATION
        assert mock.call_args.kwargs["params"]["pageSize"] == 100  # API cap

    @pytest.mark.asyncio
    async def test_search_concepts_journals_then_articles(self, adapter):
        mock = router(
            {
                "search/journals/long covid": fx.JOURNAL_SEARCH,
                "search/articles/long covid": fx.ARTICLE_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("long covid", limit=8)
        assert [c.primary_id for c in concepts] == [f"journal:{PLOS}", f"article:{ARTICLE}"]
        pages = {
            c.args[0].split("/search/")[1].split("/")[0]: c.kwargs["params"]
            for c in mock.call_args_list
        }
        assert pages["journals"]["pageSize"] == 2  # limit // 4
        assert pages["articles"]["pageSize"] == 8

    @pytest.mark.asyncio
    async def test_search_concepts_limit_one_returns_one(self, adapter):
        mock = router(
            {
                "search/journals/fatigue": fx.JOURNAL_SEARCH,
                "search/articles/fatigue": fx.ARTICLE_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("fatigue", limit=1)
        assert [c.primary_id for c in concepts] == [f"journal:{PLOS}"]

    @pytest.mark.asyncio
    async def test_search_concepts_zero_journals_is_honest(self, adapter):
        mock = router(
            {
                "search/journals/long covid": fx.EMPTY_SEARCH,
                "search/articles/long covid": fx.ARTICLE_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            concepts = await adapter.search_concepts("long covid")
        assert [c.primary_id for c in concepts] == [f"article:{ARTICLE}"]

    @pytest.mark.asyncio
    async def test_search_concepts_resolves_issn_and_doi(self, adapter):
        mock = router(
            {
                "search/journals/issn:1932-6203": fx.JOURNAL_SEARCH,
                f'search/articles/doi:"{DOI}"': fx.ARTICLE_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            by_issn = await adapter.search_concepts("1932-6203")
            by_doi = await adapter.search_concepts(f"https://doi.org/{DOI}")
        assert [c.primary_id for c in by_issn] == [f"journal:{PLOS}"]
        assert [c.primary_id for c in by_doi] == [f"article:{ARTICLE}"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query, limit", [("", 5), ("  ", 5), (None, 5), ("fatigue", 0)])
    async def test_empty_query_or_zero_limit(self, adapter, query, limit):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts(query, limit) == []
            assert await adapter.search_journals(query or "", limit) == []
            assert await adapter.search_articles(query or "", limit) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_unusable_query_never_reaches_the_server(self, adapter):
        mock = AsyncMock()
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_journals("(((") == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_query_is_sanitized_before_sending(self, adapter):
        mock = router({"search/journals/COVID 19 long review": fx.EMPTY_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_journals("COVID-19: long (review") == []
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_limit_truncates_and_dedupes(self, adapter):
        doubled = copy.deepcopy(fx.JOURNAL_SEARCH)
        other = copy.deepcopy(fx.JOURNAL_KARDIO)
        doubled["results"] = [fx.JOURNAL_PLOS, fx.JOURNAL_PLOS, other, {"id": "x"}, "junk"]
        mock = router({"search/journals/x": doubled})
        with patch.object(adapter, "_make_request", new=mock):
            assert len(await adapter.search_journals("x", 10)) == 2
            assert len(await adapter.search_journals("x", 1)) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response",
        [fx.EMPTY_SEARCH, {"results": None}, {"results": "oops"}, [1], None, RuntimeError("x")],
    )
    async def test_empty_and_error_responses(self, adapter, response):
        mock = router({"search/journals/x": response, "search/articles/x": response})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_journals("x") == []
            assert await adapter.search_articles("x") == []
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_journal_details_state_policies_faithfully(self, adapter):
        mock = router({f"journals/{PLOS}": fx.JOURNAL_PLOS})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(f"journal:{PLOS}")
        data = concept.source_data[KnowledgeSource.DOAJ]
        assert concept.primary_id == f"journal:{PLOS}"
        assert data["eissn"] == "1932-6203"
        assert data["pissn"] is None
        assert data["publisher"] == "Public Library of Science (PLoS)"
        assert data["publisher_country"] == "US"
        assert data["apc"]["has_apc"] is True
        assert data["apc"]["max"] == [{"price": 2477, "currency": "USD"}]
        assert data["licenses"][0]["type"] == "CC BY"
        assert data["licenses"][0]["BY"] is True and data["licenses"][0]["NC"] is False
        assert data["peer_review"] == ["Single anonymous peer review"]
        assert data["ticked"] is True
        assert data["seal"] is None  # not exposed by the public API: never invented
        assert data["url"] == f"https://doaj.org/toc/{PLOS}"
        assert "license:CC BY" in concept.categories
        assert "apc:yes" in concept.categories
        assert {i.identifier for i in concept.identifiers} >= {"ISSN:1932-6203"}

    @pytest.mark.asyncio
    async def test_journal_without_apc(self, adapter):
        mock = router({f"journals/{KARDIO}": fx.JOURNAL_KARDIO})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(KARDIO)
        data = concept.source_data[KnowledgeSource.DOAJ]
        assert data["apc"]["has_apc"] is False
        assert data["in_doaj"] is True
        assert data["waiver"] is False
        assert "apc:no" in concept.categories
        assert "Kardiochirurgia i Torakochirurgia Polska" in concept.synonyms
        assert data["licenses"][0]["type"] == "CC BY-NC-SA"
        assert data["licenses"][0]["NC"] is True and data["licenses"][0]["SA"] is True
        assert data["publication_time_weeks"] == 16
        assert data["preservation"] == ["PMC"]

    @pytest.mark.asyncio
    async def test_article_by_doi(self, adapter):
        upper = DOI.upper()
        mock = router(
            {
                f'search/articles/doi:"{upper}"': fx.EMPTY_SEARCH,  # matching is case-sensitive
                f'search/articles/doi:"{DOI}"': fx.ARTICLE_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(f"doi:{upper}")
        assert mock.call_count == 2
        data = concept.source_data[KnowledgeSource.DOAJ]
        assert concept.primary_id == f"article:{ARTICLE}"
        assert data["doi"] == DOI
        assert data["journal"] == "PLoS ONE"
        assert data["journal_issns"] == ["1932-6203"]
        assert data["year"] == "2025"
        assert data["fulltext_urls"] == [f"https://doi.org/{DOI}"]
        assert data["authors"][0]["name"] == "Gregory Vallée"
        assert concept.definitions[0].startswith("This is a 3.5-year")
        assert "year:2025" in concept.categories
        assert any(i.identifier == f"DOI:{DOI}" for i in concept.identifiers)

    @pytest.mark.asyncio
    async def test_journal_by_issn(self, adapter):
        mock = router({"search/journals/issn:1932-6203": fx.JOURNAL_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details("ISSN:1932-6203")
        assert concept.primary_id == f"journal:{PLOS}"

    @pytest.mark.asyncio
    async def test_bare_id_tries_journal_then_article(self, adapter):
        mock = router(
            {f"journals/{ARTICLE}": NotFound("no"), f"articles/{ARTICLE}": fx.ARTICLE_PLOS}
        )
        with patch.object(adapter, "_make_request", new=mock):
            concept = await adapter.get_concept_details(ARTICLE)
        assert concept.primary_id == f"article:{ARTICLE}"
        assert [c.args[0].rsplit("/", 2)[-2] for c in mock.call_args_list] == [
            "journals",
            "articles",
        ]

    @pytest.mark.asyncio
    async def test_unknown_inputs_return_none(self, adapter):
        mock = router(
            {
                f"journals/{PLOS}": NotFound("no"),
                f"articles/{PLOS}": {"error": "x"},
                "search/journals/issn:1000-0000": fx.EMPTY_SEARCH,
                'search/articles/doi:"10.9999/none"': fx.EMPTY_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_concept_details(PLOS) is None
            assert await adapter.get_concept_details("1000-0000") is None
            assert await adapter.get_concept_details("10.9999/none") is None
            assert await adapter.get_concept_details("not an id") is None

    def test_records_without_titles_are_skipped(self, adapter):
        assert adapter._journal_to_concept({"id": PLOS, "bibjson": {}}) is None
        assert adapter._article_to_concept({"id": ARTICLE, "bibjson": {"title": ""}}) is None
        assert adapter._journal_to_concept({"bibjson": {"title": "x"}}) is None

    def test_conversion_errors_are_swallowed(self, adapter):
        assert (
            adapter._journal_to_concept({"id": PLOS, "bibjson": {"title": "T", "apc": 5}}) is None
        )
        assert (
            adapter._article_to_concept({"id": ARTICLE, "bibjson": {"title": "T", "link": 5}})
            is None
        )


class TestRelationships:
    @pytest.mark.asyncio
    async def test_journal_edges(self, adapter):
        mock = router({"search/journals/issn:1932-6203": fx.JOURNAL_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships("1932-6203")
        assert [(e["relation_label"], e["related_id"]) for e in edges] == [
            ("has_subject", "LCC:R"),
            ("has_subject", "LCC:Q"),
            ("has_license", "CC BY"),
            ("published_by", "Public Library of Science (PLoS)"),
        ]
        licence = edges[2]
        assert licence["url"] == "https://creativecommons.org/licenses/by/4.0/"
        assert licence["attribution"] is True and licence["non_commercial"] is False
        assert all(e["source"] == "DOAJ" for e in edges)

    @pytest.mark.asyncio
    async def test_limit_caps_subjects_and_licences(self, adapter):
        mock = router({f"journals/{PLOS}": fx.JOURNAL_PLOS})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(PLOS, limit=1)
        labels = [e["relation_label"] for e in edges]
        assert labels == ["has_subject", "has_license", "published_by"]
        assert await adapter.get_relationships(PLOS, limit=0) == []

    @pytest.mark.asyncio
    async def test_article_published_in_resolves_the_journal(self, adapter):
        mock = router(
            {
                f"articles/{ARTICLE}": fx.ARTICLE_PLOS,
                "search/journals/issn:1932-6203": fx.JOURNAL_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(f"article:{ARTICLE}")
        first = edges[0]
        assert first["relation_label"] == "published_in"
        assert first["related_id"] == f"journal:{PLOS}"
        assert first["journal_in_doaj"] is True
        assert first["related_name"] == "PLoS ONE"
        assert [e["related_id"] for e in edges[1:]] == ["LCC:R", "LCC:Q"]

    @pytest.mark.asyncio
    async def test_article_whose_journal_left_doaj(self, adapter):
        mock = router(
            {
                f"articles/{ARTICLE}": fx.ARTICLE_PLOS,
                "search/journals/issn:1932-6203": fx.EMPTY_SEARCH,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(f"article:{ARTICLE}")
        assert edges[0]["related_id"] == "ISSN:1932-6203"
        assert edges[0]["journal_in_doaj"] is False
        assert edges[0]["related_name"] == "PLoS ONE"

    @pytest.mark.asyncio
    async def test_article_without_issn_falls_back_to_the_title(self, adapter):
        article = copy.deepcopy(fx.ARTICLE_PLOS)
        article["bibjson"]["journal"]["issns"] = []
        article["bibjson"]["subject"] = [{"term": None}]
        mock = router({f"articles/{ARTICLE}": article})
        with patch.object(adapter, "_make_request", new=mock):
            edges = await adapter.get_relationships(f"article:{ARTICLE}")
        assert [(e["related_id"], e["journal_in_doaj"]) for e in edges] == [("PLoS ONE", False)]

    @pytest.mark.asyncio
    async def test_failures_return_empty(self, adapter):
        mock = router(
            {f"journals/{PLOS}": RuntimeError("down"), f"articles/{PLOS}": NotFound("x")}
        )
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_relationships(PLOS) == []
            assert await adapter.get_relationships("garbage") == []
        with patch.object(adapter, "_get", new=AsyncMock(side_effect=ValueError)):
            assert await adapter.get_relationships(PLOS) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_journal_mappings(self, adapter):
        mock = router({f"journals/{KARDIO}": fx.JOURNAL_KARDIO})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings(KARDIO)
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("ISSN", "1731-5530"),
            ("EISSN", "1897-4252"),
        }
        assert all(m["fromId"] == f"journal:{KARDIO}" for m in mappings)
        assert all(m["fromSource"] == "DOAJ" and m["confidence"] == 1.0 for m in mappings)

    @pytest.mark.asyncio
    async def test_article_mappings(self, adapter):
        mock = router({f"articles/{ARTICLE}": fx.ARTICLE_PLOS})
        with patch.object(adapter, "_make_request", new=mock):
            mappings = await adapter.get_mappings(f"article:{ARTICLE}")
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("DOI", DOI),
            ("ISSN", "1932-6203"),
        }

    @pytest.mark.asyncio
    async def test_failures_return_empty(self, adapter):
        mock = router({f"journals/{PLOS}": NotFound("no"), f"articles/{PLOS}": NotFound("no")})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_mappings(PLOS) == []
            assert await adapter.get_mappings("garbage") == []
        with patch.object(adapter, "_record", new=AsyncMock(side_effect=ValueError)):
            assert await adapter.get_mappings(PLOS) == []


class TestRobustness:
    @pytest.mark.asyncio
    async def test_unexpected_exceptions_never_escape(self, adapter):
        boom = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(adapter, "_search", new=boom), patch.object(adapter, "_get", new=boom):
            assert await adapter.search_journals("x") == []
            assert await adapter.search_articles("x") == []
            assert await adapter.search_concepts("x") == []
            assert await adapter.get_concept_details(PLOS) is None
            assert await adapter.get_concept_details("1932-6203") is None

    @pytest.mark.asyncio
    async def test_search_concepts_outer_guard(self, adapter):
        boom = AsyncMock(side_effect=ValueError)
        with (
            patch.object(adapter, "search_journals", new=boom),
            patch.object(adapter, "search_articles", new=AsyncMock(return_value=[])),
        ):
            assert await adapter.search_concepts("x") == []


class TestThrottling:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        sleeps: list[float] = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        clock = {"now": 50.0}
        # replace the names inside the helper module only: patching asyncio.sleep or
        # time.monotonic themselves would also change the event loop's clock
        monkeypatch.setattr(_vocab_common, "asyncio", SimpleNamespace(sleep=fake_sleep))
        monkeypatch.setattr(_vocab_common, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
        adapter._spacer.interval = dj.MIN_INTERVAL
        mock = AsyncMock(return_value=fx.EMPTY_SEARCH)
        with patch.object(adapter, "_make_request", new=mock):
            await adapter.search_journals("a")
            await adapter.search_journals("b")
            clock["now"] += 5.0
            await adapter.search_journals("c")
        assert sleeps == [pytest.approx(dj.MIN_INTERVAL)]

    def test_interval_respects_two_requests_per_second(self):
        assert 1 / dj.MIN_INTERVAL <= 2


class TestRegistry:
    def test_registered(self):
        from knowledge_lookup.adapters import ADAPTER_CLASSES

        assert ADAPTER_CLASSES[KnowledgeSource.DOAJ] is DOAJAdapter
