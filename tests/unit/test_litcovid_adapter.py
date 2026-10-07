"""Unit tests for LitCovidAdapter (trimmed real responses, no network)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import litcovid_adapter as lc
from knowledge_lookup.adapters.litcovid_adapter import LitCovidAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import litcovid_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_pauses(monkeypatch):
    monkeypatch.setattr(lc, "PAGE_PAUSE", 0)


@pytest.fixture
def adapter():
    return LitCovidAdapter(LookupConfig())


def patched(adapter, *responses):
    """Patch ``_make_request`` with a sequence of responses (or one for every call)."""
    mock = AsyncMock(side_effect=list(responses)) if len(responses) > 1 else AsyncMock()
    if len(responses) == 1:
        mock.return_value = responses[0]
    return patch.object(adapter, "_make_request", new=mock), mock


def sent_text(mock, index=-1):
    return mock.call_args_list[index].kwargs["params"]["text"]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.LITCOVID
        assert adapter.is_available() is True
        assert adapter.min_request_timeout == 60.0

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("PMID:34316076", "34316076"),
            ("pmid:34316076", "34316076"),
            ("34316076", "34316076"),
            (" LITCOVID:PMID:34316076 ", "34316076"),
            ("PMC9878254", None),
            ("abc", None),
            ("", None),
        ],
    )
    def test_normalize_pmid(self, raw, expected):
        assert LitCovidAdapter.normalize_pmid(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("LITCOVID:TOPIC:Case Report", "Case Report"),
            ("topic:treatment", "Treatment"),
            ("case_report", "Case Report"),
            ("Epidemic-Forecasting", "Epidemic Forecasting"),
            ("Nonsense", None),
            ("", None),
        ],
    )
    def test_normalize_topic(self, raw, expected):
        assert LitCovidAdapter.normalize_topic(raw) == expected


class TestBuildQuery:
    def test_multiword_becomes_phrase(self):
        assert LitCovidAdapter.build_query("long covid") == '"long covid"'

    def test_single_word_and_operators_pass_through(self):
        assert LitCovidAdapter.build_query("fatigue") == "fatigue"
        assert LitCovidAdapter.build_query("long AND covid") == "long AND covid"
        assert LitCovidAdapter.build_query('"post-acute sequelae"') == '"post-acute sequelae"'
        assert LitCovidAdapter.build_query("topics:Diagnosis") == "topics:Diagnosis"

    def test_filters(self):
        query = LitCovidAdapter.build_query(
            "long covid",
            {
                "topic": "case report",
                "country": ["Germany", "France"],
                "bogus": "x",
                "journal": "",
            },
        )
        assert query == (
            '"long covid" AND topics:"Case Report" AND (countries:"Germany" OR countries:"France")'
        )

    def test_filters_only_and_empty(self):
        assert LitCovidAdapter.build_query("", {"condition": "LongCovid"}) == (
            'e_condition:"LongCovid"'
        )
        assert LitCovidAdapter.build_query("", None) == ""


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_concepts(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            results = await adapter.search_concepts("long covid", limit=3)
        assert [c.primary_id for c in results] == [
            "PMID:34316076",
            "PMID:35474919",
            "PMID:36972723",
        ]
        assert sent_text(mock) == '"long covid"'
        first = results[0]
        assert first.concept_type == ConceptType.CITATION
        assert first.primary_label == "Long COVID."
        assert "journal:Nat Immunol" in first.categories
        assert "year:2021" in first.categories
        assert "condition:LongCovid" in first.categories
        data = first.source_data[KnowledgeSource.LITCOVID]
        assert data["journal"] == "Nat Immunol" and data["year"] == "2021"
        assert data["entities"] == {"condition": ["LongCovid"]}
        assert data["url"] == "https://pubmed.ncbi.nlm.nih.gov/34316076/"

    @pytest.mark.asyncio
    async def test_limit_is_respected_and_pages_are_walked(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID, fx.SEARCH_LONG_COVID_PAGE2)
        with ctx:
            results = await adapter.search_articles("long covid", limit=5)
        assert len(results) == 5
        assert mock.call_count == 2
        assert mock.call_args_list[1].kwargs["params"]["page"] == 2
        assert "page" not in mock.call_args_list[0].kwargs["params"]
        assert len({c.primary_id for c in results}) == 5

    @pytest.mark.asyncio
    async def test_limit_smaller_than_page(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            results = await adapter.search_articles("long covid", limit=2)
        assert len(results) == 2
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_stops_on_last_page(self, adapter):
        last = copy.deepcopy(fx.SEARCH_LONG_COVID)
        last["total_pages"] = 1
        ctx, mock = patched(adapter, last)
        with ctx:
            results = await adapter.search_articles("long covid", limit=50)
        assert len(results) == 3
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_filters_and_sort(self, adapter):
        ctx, mock = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            results = await adapter.search_articles(
                "post-acute sequelae", 5, {"topic": "Treatment"}, sort="date"
            )
        assert results == []
        assert sent_text(mock) == '"post-acute sequelae" AND topics:"Treatment"'
        assert mock.call_args.kwargs["params"]["sort"] == "date desc"

    @pytest.mark.asyncio
    async def test_empty_inputs_make_no_request(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            assert await adapter.search_articles("", 5) == []
            assert await adapter.search_articles("x", 0) == []
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("x", 0) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_limit_is_capped(self, adapter):
        ctx, mock = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            await adapter.search_articles("covid", limit=10_000)
        assert mock.call_count == 1  # empty first page ends the loop

    @pytest.mark.asyncio
    async def test_search_concepts_adds_matching_topics(self, adapter):
        ctx, _ = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            results = await adapter.search_concepts("treatment", limit=5)
        assert [c.primary_id for c in results] == ["LITCOVID:TOPIC:Treatment"]
        assert results[0].categories == ["LitCovid topic"]

    @pytest.mark.asyncio
    async def test_relaxed_retry_when_phrase_finds_nothing(self, adapter):
        ctx, mock = patched(adapter, fx.EMPTY_RESPONSE, fx.SEARCH_LONG_COVID)
        with ctx:
            results = await adapter.search_concepts("fatigue long covid", limit=2)
        assert len(results) == 2
        assert sent_text(mock, 0) == '"fatigue long covid"'
        assert sent_text(mock, 1) == "fatigue AND long AND covid"

    @pytest.mark.asyncio
    async def test_pmid_query_resolves_single_article(self, adapter):
        ctx, mock = patched(adapter, fx.SINGLE_ARTICLE_WITH_DRUGS)
        with ctx:
            results = await adapter.search_concepts("PMID:39472619")
        assert [c.primary_id for c in results] == ["PMID:39472619"]
        assert sent_text(mock) == "pmid:39472619"

    @pytest.mark.asyncio
    async def test_pmid_query_not_found(self, adapter):
        ctx, _ = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            assert await adapter.search_concepts("99999999999") == []

    @pytest.mark.asyncio
    async def test_records_without_title_or_pmid_are_skipped(self, adapter):
        bad = {"results": [{"pmid": 1}, {"title": "no id"}, {"pmid": 2, "title": "ok"}]}
        ctx, _ = patched(adapter, bad)
        with ctx:
            results = await adapter.search_articles("x", 10)
        assert [c.primary_id for c in results] == ["PMID:2"]


class TestErrors:
    @pytest.mark.asyncio
    async def test_request_failure_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("down"))):
            assert await adapter.search_concepts("long covid") == []
            assert await adapter.get_concept_details("PMID:1") is None
            assert await adapter.get_relationships("PMID:1") == []
            assert await adapter.get_mappings("PMID:1") == []
            assert await adapter.get_topic_counts() == {}

    @pytest.mark.asyncio
    async def test_unexpected_payload(self, adapter):
        for payload in ([], {"results": "oops"}, {"detail": "x"}):
            with patch.object(adapter, "_make_request", new=AsyncMock(return_value=payload)):
                assert await adapter.search_articles("long covid") == []
                assert await adapter.get_concept_details("1") is None

    @pytest.mark.asyncio
    async def test_unexpected_exceptions_do_not_escape(self, adapter):
        with patch.object(adapter, "_fetch_page", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_articles("a") == []
            assert await adapter.search_concepts("a b") == []
            assert await adapter.get_concept_details("PMID:1") is None
            assert await adapter.get_relationships("PMID:1") == []
            assert await adapter.get_mappings("PMID:1") == []

    @pytest.mark.asyncio
    async def test_invalid_ids_make_no_request(self, adapter):
        ctx, mock = patched(adapter, fx.SINGLE_ARTICLE_WITH_DRUGS)
        with ctx:
            assert await adapter.get_concept_details("not-an-id") is None
            assert await adapter.get_mappings("not-an-id") == []
            assert await adapter.get_relationships("not-an-id") == []
        mock.assert_not_called()


class TestDetails:
    @pytest.mark.asyncio
    async def test_article_details_include_facet_drugs(self, adapter):
        ctx, mock = patched(adapter, fx.SINGLE_ARTICLE_WITH_DRUGS)
        with ctx:
            concept = await adapter.get_concept_details("39472619")
        assert sent_text(mock) == "pmid:39472619"
        assert concept.primary_id == "PMID:39472619"
        assert concept.sources == [KnowledgeSource.LITCOVID]
        entities = concept.source_data[KnowledgeSource.LITCOVID]["entities"]
        assert entities["drug"] == ["Ritonavir", "nirmatrelvir and ritonavir drug combination"]
        assert entities["strain"] == ["Omicron"]
        assert "topic:Treatment" in concept.categories
        assert "country:United Arab Emirates" in concept.categories
        pmc = [i for i in concept.identifiers if i.identifier.startswith("PMC")]
        assert pmc and pmc[0].source == KnowledgeSource.EUROPEPMC

    @pytest.mark.asyncio
    async def test_details_by_pmcid(self, adapter):
        ctx, mock = patched(adapter, fx.SINGLE_ARTICLE_WITH_DRUGS)
        with ctx:
            assert await adapter.get_concept_details("pmc11522512") is not None
        assert sent_text(mock) == "pmcid:PMC11522512"

    @pytest.mark.asyncio
    async def test_details_not_found(self, adapter):
        ctx, _ = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            assert await adapter.get_concept_details("PMID:99999999999") is None

    @pytest.mark.asyncio
    async def test_facets_without_drugs_or_malformed(self, adapter):
        record = copy.deepcopy(fx.SINGLE_ARTICLE_WITH_DRUGS)
        record["facets"] = "garbage"
        ctx, _ = patched(adapter, record)
        with ctx:
            concept = await adapter.get_concept_details("39472619")
        assert "drug" not in concept.source_data[KnowledgeSource.LITCOVID]["entities"]

    @pytest.mark.asyncio
    async def test_topic_details(self, adapter):
        ctx, mock = patched(adapter, fx.TOPIC_DIAGNOSIS_COUNT)
        with ctx:
            concept = await adapter.get_concept_details("LITCOVID:TOPIC:Diagnosis")
        assert sent_text(mock) == 'topics:"Diagnosis"'
        assert concept.primary_label == "Diagnosis"
        assert concept.source_data[KnowledgeSource.LITCOVID] == {
            "topic": "Diagnosis",
            "article_count": 80725,
        }

    @pytest.mark.asyncio
    async def test_year_falls_back_to_date(self, adapter):
        record = {"pmid": 5, "title": "t", "date": "2020-03-01T12:00:00Z"}
        assert (
            adapter._article_to_concept(record).source_data[KnowledgeSource.LITCOVID]["year"]
            == "2020"
        )
        assert (
            adapter._article_to_concept({"pmid": 5, "title": "t"}).source_data[
                KnowledgeSource.LITCOVID
            ]["year"]
            == ""
        )


class TestRelationships:
    @pytest.mark.asyncio
    async def test_article_relationships(self, adapter):
        ctx, _ = patched(adapter, fx.SINGLE_ARTICLE_WITH_DRUGS)
        with ctx:
            rels = await adapter.get_relationships("PMID:39472619")
        labels = [(r["relation_label"], r["related_id"]) for r in rels]
        assert ("has_topic", "LITCOVID:TOPIC:Treatment") in labels
        assert ("annotated_with_condition", "LITCOVID:CONDITION:LongCovid") in labels
        assert ("mentions_drug", "LITCOVID:DRUG:Ritonavir") in labels
        assert ("mentions_strain", "LITCOVID:STRAIN:Omicron") in labels
        assert all(
            set(r) >= {"relation_label", "related_id", "related_name", "source"} for r in rels
        )
        assert len(labels) == len(set(labels))

    @pytest.mark.asyncio
    async def test_variants_and_cap(self, adapter):
        record = copy.deepcopy(fx.SINGLE_ARTICLE_WITH_VARIANTS)
        record["results"][0]["e_variants"] = [f"rs{i}" for i in range(80)]
        ctx, _ = patched(adapter, record)
        with ctx:
            rels = await adapter.get_relationships("35330457")
        variants = [r for r in rels if r["relation_label"] == "mentions_variant"]
        assert len(variants) == 50
        assert variants[0]["entity_type"] == "variant"

    @pytest.mark.asyncio
    async def test_article_not_found(self, adapter):
        ctx, _ = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            assert await adapter.get_relationships("PMID:99999999999") == []

    @pytest.mark.asyncio
    async def test_topic_relationships_list_newest_articles(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_LONG_COVID)
        with ctx:
            rels = await adapter.get_relationships("topic:Case Report")
        assert sent_text(mock) == 'topics:"Case Report"'
        assert mock.call_args.kwargs["params"]["sort"] == "date desc"
        assert {r["relation_label"] for r in rels} == {"has_article"}
        assert rels[0]["related_id"] == "PMID:34316076"


class TestMappingsAndCounts:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        ctx, _ = patched(adapter, fx.SINGLE_ARTICLE_WITH_DRUGS)
        with ctx:
            mappings = await adapter.get_mappings("PMID:39472619")
        assert {m["toSource"]: m["toId"] for m in mappings} == {
            "PubMed": "39472619",
            "PMC": "PMC11522512",
        }
        assert all(
            set(m) == {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"}
            for m in mappings
        )

    @pytest.mark.asyncio
    async def test_mappings_without_pmcid_and_not_found(self, adapter):
        record = copy.deepcopy(fx.SINGLE_ARTICLE_WITH_DRUGS)
        del record["results"][0]["pmcid"]
        ctx, _ = patched(adapter, record)
        with ctx:
            assert [m["toSource"] for m in await adapter.get_mappings("39472619")] == ["PubMed"]
        ctx, _ = patched(adapter, fx.EMPTY_RESPONSE)
        with ctx:
            assert await adapter.get_mappings("39472619") == []

    @pytest.mark.asyncio
    async def test_topic_counts(self, adapter):
        async def fake(url, params=None, **kwargs):
            topic = params["text"].split('"')[1]
            return {"results": [], "count": len(topic)}

        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=fake)):
            counts = await adapter.get_topic_counts()
        assert counts == {t: len(t) for t in lc.TOPICS}

    @pytest.mark.asyncio
    async def test_topic_counts_with_query_and_partial_failure(self, adapter):
        calls = []

        async def fake(url, params=None, **kwargs):
            calls.append(params["text"])
            if "Mechanism" in params["text"]:
                raise OSError("boom")
            return {"results": [], "count": 7}

        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=fake)):
            counts = await adapter.get_topic_counts(query="long covid")
        assert "Mechanism" not in counts and counts["Treatment"] == 7
        assert all(c.startswith('"long covid" AND topics:') for c in calls)
