"""Unit tests for CrossrefAdapter (trimmed real responses, no network)."""

import copy
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from knowledge_lookup.adapters import crossref_adapter as cr
from knowledge_lookup.adapters.crossref_adapter import CrossrefAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import crossref_responses as fx

pytestmark = pytest.mark.unit

WAKEFIELD = "10.1016/s0140-6736(97)11096-0"
NATURE = "10.1038/s41586-020-2012-7"


@pytest.fixture(autouse=True)
def _clean_env_and_sleep(monkeypatch):
    monkeypatch.delenv(cr.MAILTO_ENV, raising=False)
    monkeypatch.setattr(cr.asyncio, "sleep", AsyncMock())


@pytest.fixture
def adapter():
    return CrossrefAdapter(LookupConfig())


def patched(adapter, *responses):
    """Patch ``_make_request`` with a sequence of responses (or one for every call)."""
    mock = AsyncMock(side_effect=list(responses)) if len(responses) > 1 else AsyncMock()
    if len(responses) == 1:
        mock.return_value = responses[0]
    return patch.object(adapter, "_make_request", new=mock), mock


def not_found():
    return aiohttp.ClientResponseError(None, (), status=404, message="Not Found")  # type: ignore[arg-type]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CROSSREF
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("10.1038/S41586-020-2012-7", NATURE),
            ("doi:10.1038/s41586-020-2012-7", NATURE),
            ("DOI: 10.1038/s41586-020-2012-7", NATURE),
            ("https://doi.org/10.1038/s41586-020-2012-7", NATURE),
            ("http://dx.doi.org/10.1038/s41586-020-2012-7", NATURE),
            ("https://doi.org/10.1016/S0140-6736(97)11096-0", WAKEFIELD),
            ("https://doi.org/10.1002/a%3Cb%3E", "10.1002/a<b>"),
            ("long covid", None),
            ("PMID:123", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_doi(self, raw, expected):
        assert CrossrefAdapter.normalize_doi(raw) == expected

    def test_work_url_encodes_special_characters(self):
        url = CrossrefAdapter._work_url("10.1002/a<b>#c?d", "/agency")
        assert url == "https://api.crossref.org/works/10.1002/a%3Cb%3E%23c%3Fd/agency"
        assert CrossrefAdapter._work_url(WAKEFIELD).endswith("/10.1016/s0140-6736(97)11096-0")


class TestMailtoAndThrottle:
    @pytest.mark.asyncio
    async def test_no_mailto_by_default(self, adapter):
        ctx, mock = patched(adapter, fx.NATURE_WORK)
        with ctx:
            await adapter.get_concept_details(NATURE)
        assert mock.call_args.kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_mailto_only_from_env(self, adapter, monkeypatch):
        monkeypatch.setenv(cr.MAILTO_ENV, " someone@example.org ")
        ctx, mock = patched(adapter, fx.NATURE_WORK)
        with ctx:
            await adapter.get_concept_details(NATURE)
        assert mock.call_args.kwargs["params"] == {"mailto": "someone@example.org"}

    @pytest.mark.asyncio
    async def test_search_params_do_not_leak_mailto_when_unset(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            await adapter.search_works("long covid", 2)
        assert "mailto" not in mock.call_args.kwargs["params"]

    @pytest.mark.asyncio
    async def test_requests_are_spaced_and_serialised(self, adapter, monkeypatch):
        clock = [100.0]
        monkeypatch.setattr(cr.time, "monotonic", lambda: clock[0])
        slept: list[float] = []

        async def fake_sleep(delay):
            slept.append(delay)
            clock[0] += delay

        monkeypatch.setattr(cr.asyncio, "sleep", fake_sleep)
        ctx, _ = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            await adapter.search_works("a", 1)  # first call: nothing to wait for... (last=0)
            await adapter.search_works("b", 1)  # immediately after: must wait ~LIST_INTERVAL
        assert len(slept) == 1
        assert slept[0] == pytest.approx(cr.LIST_INTERVAL, abs=1e-6)

    @pytest.mark.asyncio
    async def test_single_work_interval_is_shorter(self, adapter, monkeypatch):
        clock = [50.0]
        monkeypatch.setattr(cr.time, "monotonic", lambda: clock[0])
        slept: list[float] = []

        async def fake_sleep(delay):
            slept.append(delay)
            clock[0] += delay

        monkeypatch.setattr(cr.asyncio, "sleep", fake_sleep)
        ctx, _ = patched(adapter, fx.NATURE_WORK)
        with ctx:
            await adapter.get_concept_details(NATURE)
            await adapter.check_retraction(NATURE)
        assert slept == [pytest.approx(cr.WORK_INTERVAL, abs=1e-6)]


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_concepts(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            results = await adapter.search_concepts("long covid", limit=2)
        assert [c.primary_id for c in results] == [
            "10.36255/long-covid-public-education",
            "10.1002/9781119891338.ch1",
        ]
        first = results[0]
        assert first.concept_type == ConceptType.CITATION
        assert first.primary_label == "Long COVID: Public Education"
        assert "year:2024" in first.categories
        assert "type:book-chapter" in first.categories
        assert first.definitions and "<jats" not in first.definitions[0]
        assert first.confidence_score == 0.9
        params = mock.call_args.kwargs["params"]
        assert params["query"] == "long covid"
        assert params["rows"] == 2
        assert "select" in params and "filter" not in params
        assert mock.call_args.args[0] == cr.WORKS_URL

    @pytest.mark.asyncio
    async def test_search_limit_is_capped_and_zero_returns_empty(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            await adapter.search_concepts("x", limit=5000)
            assert mock.call_args.kwargs["params"]["rows"] == cr.MAX_ROWS
            assert await adapter.search_concepts("x", limit=0) == []
            assert await adapter.search_concepts("", limit=5) == []
            assert await adapter.search_concepts("   ", limit=5) == []

    @pytest.mark.asyncio
    async def test_search_limit_truncates_results(self, adapter):
        ctx, _ = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            assert len(await adapter.search_concepts("x", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_search_filters_and_sort(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            await adapter.search_works(
                "fatigue",
                5,
                filters={
                    "type": "journal-article",
                    "from_year": 2020,
                    "has_abstract": True,
                    "bogus": "ignored",
                    "issn": "",
                },
                sort="is-referenced-by-count",
            )
        params = mock.call_args.kwargs["params"]
        assert params["filter"] == "type:journal-article,from-pub-date:2020,has-abstract:true"
        assert params["sort"] == "is-referenced-by-count"
        assert params["order"] == "desc"

    @pytest.mark.asyncio
    async def test_filter_only_search_without_query(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_RESPONSE)
        with ctx:
            results = await adapter.search_works("", 2, filters={"update_type": "retraction"})
        assert len(results) == 2
        assert "query" not in mock.call_args.kwargs["params"]

    @pytest.mark.asyncio
    async def test_search_deduplicates_and_skips_doi_less_items(self, adapter):
        data = copy.deepcopy(fx.SEARCH_RESPONSE)
        items = data["message"]["items"]
        data["message"]["items"] = [items[0], items[0], {"title": ["no doi"]}, items[1]]
        ctx, _ = patched(adapter, data)
        with ctx:
            results = await adapter.search_concepts("x", 10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_errors_return_empty(self, adapter):
        ctx, _ = patched(adapter, RuntimeError("boom"))
        with ctx:
            assert await adapter.search_concepts("x") == []
        ctx, _ = patched(adapter, {"status": "failed", "message": []})
        with ctx:
            assert await adapter.search_concepts("x") == []
        ctx, _ = patched(adapter, ["not", "a", "dict"])
        with ctx:
            assert await adapter.search_concepts("x") == []
        ctx, _ = patched(adapter, {"status": "ok", "message": "oops"})
        with ctx:
            assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_doi_query_resolves_to_details(self, adapter):
        ctx, mock = patched(adapter, fx.NATURE_WORK)
        with ctx:
            results = await adapter.search_concepts("https://doi.org/" + NATURE)
        assert [c.primary_id for c in results] == [NATURE]
        assert mock.call_args.args[0].endswith(f"/works/{NATURE}")

    @pytest.mark.asyncio
    async def test_doi_query_not_found(self, adapter):
        ctx, _ = patched(adapter, not_found(), not_found())
        with ctx:
            assert await adapter.search_concepts("10.9999/nope") == []

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_search_concepts(self, adapter):
        with patch.object(adapter, "search_works", side_effect=RuntimeError("x")):
            assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_search_works(self, adapter):
        with patch.object(adapter, "_get", side_effect=RuntimeError("x")):
            assert await adapter.search_works("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_of_retracted_paper(self, adapter):
        ctx, _ = patched(adapter, fx.WAKEFIELD_WORK)
        with ctx:
            concept = await adapter.get_concept_details("doi:10.1016/S0140-6736(97)11096-0")
        assert concept is not None
        assert concept.primary_id == WAKEFIELD
        assert concept.primary_label.startswith("RETRACTED:")
        assert concept.concept_type == ConceptType.CITATION
        assert "retracted" in concept.categories
        assert "journal:The Lancet" in concept.categories
        data = concept.source_data[KnowledgeSource.CROSSREF]
        assert data["retracted"] is True
        assert data["update_notices"] == 2
        assert data["cited_by_count"] == 2035
        assert data["author_count"] == 3
        assert data["authors"][0] == "Wakefield, AJ"
        assert data["url"] == f"https://doi.org/{WAKEFIELD}"
        assert data["volume"] == "351"
        assert data["license"] == ["https://www.elsevier.com/tdm/userlicense/1.0/"]

    @pytest.mark.asyncio
    async def test_details_of_preprint_linked_article(self, adapter):
        ctx, _ = patched(adapter, fx.NATURE_WORK)
        with ctx:
            concept = await adapter.get_concept_details(NATURE)
        assert concept is not None
        data = concept.source_data[KnowledgeSource.CROSSREF]
        assert data["date"] == "2020-02-03"
        assert data["issn"] == ["0028-0836", "1476-4687"]
        assert data["container"] == "Nature"
        assert "retracted" not in concept.categories

    @pytest.mark.asyncio
    async def test_subtitle_becomes_synonym_and_markup_is_stripped(self, adapter):
        data = copy.deepcopy(fx.NATURE_WORK)
        data["message"]["title"] = ["A <i>novel</i>   title"]
        data["message"]["subtitle"] = ["the &amp; subtitle"]
        data["message"]["abstract"] = (
            "<jats:p>First &lt;b&gt; part.</jats:p><jats:p>Second.</jats:p>"
        )
        ctx, _ = patched(adapter, data)
        with ctx:
            concept = await adapter.get_concept_details(NATURE)
        assert concept.primary_label == "A novel title"
        assert concept.synonyms == ["A novel title: the & subtitle"]
        assert concept.definitions == ["First <b> part. Second."]

    @pytest.mark.asyncio
    async def test_minimal_work_without_title(self, adapter):
        ctx, _ = patched(adapter, {"status": "ok", "message": {"DOI": "10.1234/ABC"}})
        with ctx:
            concept = await adapter.get_concept_details("10.1234/abc")
        assert concept.primary_id == "10.1234/abc"
        assert concept.primary_label == "10.1234/abc"
        assert concept.source_data[KnowledgeSource.CROSSREF]["date"] == ""

    @pytest.mark.asyncio
    async def test_invalid_id_makes_no_request(self, adapter):
        ctx, mock = patched(adapter, fx.NATURE_WORK)
        with ctx:
            assert await adapter.get_concept_details("not a doi") is None
            assert await adapter.get_relationships("not a doi") == []
            assert await adapter.get_mappings("not a doi") == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_doi_reports_other_agency(self, adapter):
        agency = {
            "status": "ok",
            "message": {"DOI": "10.5281/zenodo.1", "agency": {"id": "datacite"}},
        }
        ctx, mock = patched(adapter, not_found(), agency)
        with ctx:
            assert await adapter.get_concept_details("10.5281/zenodo.1") is None
        assert mock.call_args.args[0].endswith("/agency")

    @pytest.mark.asyncio
    async def test_work_without_doi_in_payload(self, adapter):
        ctx, _ = patched(adapter, {"status": "ok", "message": {"title": ["x"]}})
        with ctx:
            assert await adapter.get_concept_details("10.1234/abc") is None

    @pytest.mark.asyncio
    async def test_cache_avoids_second_request(self, adapter):
        ctx, mock = patched(adapter, fx.NATURE_WORK)
        with ctx:
            await adapter.get_concept_details(NATURE)
            await adapter.get_relationships(NATURE)
            await adapter.get_mappings(NATURE)
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_is_bounded(self, adapter):
        ctx, mock = patched(adapter, fx.NATURE_WORK)
        with ctx:
            for i in range(cr.CACHE_SIZE + 3):
                await adapter.get_concept_details(f"10.1234/x{i}")
        assert len(adapter._work_cache) == cr.CACHE_SIZE

    @pytest.mark.asyncio
    async def test_conversion_error_is_swallowed(self, adapter):
        assert adapter._work_to_concept({"DOI": "10.1/x", "author": 5}) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_wakefield_notices_come_first(self, adapter):
        ctx, _ = patched(adapter, fx.WAKEFIELD_WORK)
        with ctx:
            edges = await adapter.get_relationships(WAKEFIELD)
        notices = [e for e in edges if e["relation_label"] != "cites"]
        assert [(e["relation_label"], e["related_id"]) for e in notices] == [
            ("corrected_by", "10.1016/s0140-6736(04)15715-2"),
            ("retracted_by", "10.1016/s0140-6736(10)60175-4"),
        ]
        retraction = notices[1]
        assert retraction["notice_date"] == "2010-02-06"
        assert retraction["update_type"] == "retraction"
        assert retraction["asserted_by"] == "retraction-watch"
        assert retraction["source"] == "CROSSREF"
        assert edges[: len(notices)] == notices

    @pytest.mark.asyncio
    async def test_references_keep_doi_less_entries(self, adapter):
        ctx, _ = patched(adapter, fx.WAKEFIELD_WORK)
        with ctx:
            edges = await adapter.get_relationships(WAKEFIELD)
        cites = [e for e in edges if e["relation_label"] == "cites"]
        assert len(cites) == 3
        with_doi = [e for e in cites if e["has_doi"]]
        assert [e["related_id"] for e in with_doi] == ["10.1016/0009-8981(82)90018-3"]
        no_doi = [e for e in cites if not e["has_doi"]]
        assert no_doi[0]["related_id"].startswith(f"{WAKEFIELD}#")
        assert "Diagnostic and Statistical Manual" in no_doi[0]["related_name"]
        assert all(e["total_references"] == 26 for e in cites)

    @pytest.mark.asyncio
    async def test_unstructured_reference_text_is_kept(self, adapter):
        ctx, _ = patched(adapter, fx.NATURE_WORK)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        unstructured = [e for e in edges if e.get("unstructured")]
        assert unstructured and unstructured[0]["related_name"] == unstructured[0]["unstructured"]

    @pytest.mark.asyncio
    async def test_preprint_and_addendum_edges(self, adapter):
        ctx, _ = patched(adapter, fx.NATURE_WORK)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        labels = {(e["relation_label"], e["related_id"]) for e in edges}
        assert ("has_preprint", "10.1101/2020.01.22.914952") in labels
        assert ("addendum_by", "10.1038/s41586-020-2951-z") in labels
        # has-review is not one of the exposed relation types
        assert not any(e["relation_label"] == "has_review" for e in edges)
        preprint = next(e for e in edges if e["relation_label"] == "has_preprint")
        assert preprint["id_type"] == "doi"
        assert preprint["asserted_by"] == "object"

    @pytest.mark.asyncio
    async def test_notice_points_back_to_the_retracted_paper(self, adapter):
        ctx, _ = patched(adapter, fx.RETRACTION_NOTICE)
        with ctx:
            edges = await adapter.get_relationships("10.1016/s0140-6736(10)60175-4")
        assert edges[0]["relation_label"] == "retracts"
        assert edges[0]["related_id"] == WAKEFIELD
        assert edges[0]["notice_date"] == "2010-02-06"

    @pytest.mark.asyncio
    async def test_unknown_update_types_get_generic_labels(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        work["message"]["updated-by"] = [
            {"DOI": "10.1/n1", "type": "new_edition", "updated": {"date-parts": [[2021]]}},
            {"DOI": "10.1/n1", "type": "new_edition"},  # duplicate -> dropped
            {"DOI": "10.1/n2", "type": "expression_of_concern", "label": "EoC"},
            {"type": "retraction"},  # no DOI -> dropped
            "garbage",
        ]
        work["message"]["update-to"] = [{"DOI": "10.1/n3", "type": "new_version"}]
        work["message"]["reference"] = []
        work["message"].pop("relation")
        ctx, _ = patched(adapter, work)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        assert [(e["relation_label"], e["related_id"]) for e in edges] == [
            ("new_edition_by", "10.1/n1"),
            ("expression_of_concern_by", "10.1/n2"),
            ("updates_new_version", "10.1/n3"),
        ]
        assert edges[0]["notice_date"] == "2021"

    @pytest.mark.asyncio
    async def test_relations_are_capped_and_deduplicated(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        entries = [{"id-type": "doi", "id": f"10.1/P{i}"} for i in range(40)]
        entries += [{"id-type": "doi", "id": "10.1/P0"}, {"id-type": "uri", "id": "x"}, {}, 3]
        work["message"]["relation"] = {"has-preprint": entries, "is-version-of": "garbage"}
        work["message"]["reference"] = []
        work["message"]["updated-by"] = []
        ctx, _ = patched(adapter, work)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        assert len(edges) == cr.MAX_RELATIONS
        assert edges[0]["related_id"] == "10.1/p0"  # DOIs are lower-cased

    @pytest.mark.asyncio
    async def test_non_doi_relation_ids_are_kept_verbatim(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        work["message"]["relation"] = {
            "is-preprint-of": [{"id-type": "uri", "id": "https://example.org/Paper"}]
        }
        work["message"]["reference"] = []
        work["message"]["updated-by"] = []
        ctx, _ = patched(adapter, work)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        assert edges[0]["relation_label"] == "is_preprint_of"
        assert edges[0]["related_id"] == "https://example.org/Paper"

    @pytest.mark.asyncio
    async def test_reference_cap_and_blank_references(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        work["message"]["reference"] = (
            [{"key": f"k{i}", "DOI": f"10.1/R{i}"} for i in range(150)]
            + [{"key": "empty"}]
            + ["junk"]
        )
        work["message"]["references-count"] = "n/a"
        work["message"]["updated-by"] = []
        work["message"].pop("relation")
        ctx, _ = patched(adapter, work)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        assert len(edges) == cr.MAX_REFERENCES
        assert edges[0]["related_id"] == "10.1/r0"
        assert edges[0]["total_references"] == 151  # falls back to the list length

    @pytest.mark.asyncio
    async def test_reference_composed_from_fields_when_no_unstructured(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        work["message"]["reference"] = [
            {
                "key": "a",
                "author": "Li",
                "article-title": "T",
                "journal-title": "J",
                "year": "2005",
            },
            {"key": "b", "DOI": "10.1/ONLY-DOI"},
        ]
        work["message"]["updated-by"] = []
        work["message"].pop("relation")
        ctx, _ = patched(adapter, work)
        with ctx:
            edges = await adapter.get_relationships(NATURE)
        assert edges[0]["related_name"] == "Li, T, J, 2005"
        assert edges[1]["related_name"] == "10.1/only-doi"

    @pytest.mark.asyncio
    async def test_not_found_and_errors(self, adapter):
        ctx, _ = patched(adapter, not_found())
        with ctx:
            assert await adapter.get_relationships("10.9999/x") == []
        with patch.object(adapter, "_fetch_work", side_effect=RuntimeError("x")):
            assert await adapter.get_relationships(NATURE) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_issn_and_relation_ids(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        work["message"]["ISBN"] = ["9781"]
        work["message"]["relation"] = {
            "has-preprint": [{"id-type": "doi", "id": "10.1101/x"}],
            "is-identical-to": [
                {"id-type": "pmid", "id": "32015507"},
                {"id-type": "pmid", "id": "32015507"},
                {"id-type": "arxiv", "id": "2001.1"},
                {"id-type": "pmcid", "id": ""},
            ],
        }
        ctx, _ = patched(adapter, work)
        with ctx:
            mappings = await adapter.get_mappings(NATURE)
        found = {(m["toSource"], m["toId"]) for m in mappings}
        assert found == {
            ("ISSN", "0028-0836"),
            ("ISSN", "1476-4687"),
            ("ISBN", "9781"),
            ("PMID", "32015507"),
            ("ARXIV", "2001.1"),
        }
        for m in mappings:
            assert m["fromId"] == NATURE and m["fromSource"] == "CROSSREF"
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
        assert next(m for m in mappings if m["toSource"] == "PMID")["mappingType"] == "exact"

    @pytest.mark.asyncio
    async def test_no_ids_gives_empty_list(self, adapter):
        ctx, _ = patched(adapter, {"status": "ok", "message": {"DOI": "10.1234/x"}})
        with ctx:
            assert await adapter.get_mappings("10.1234/x") == []

    @pytest.mark.asyncio
    async def test_not_found_and_errors(self, adapter):
        ctx, _ = patched(adapter, not_found())
        with ctx:
            assert await adapter.get_mappings("10.9999/x") == []
        with patch.object(adapter, "_fetch_work", side_effect=RuntimeError("x")):
            assert await adapter.get_mappings(NATURE) == []


class TestCheckRetraction:
    @pytest.mark.asyncio
    async def test_retracted_paper(self, adapter):
        ctx, mock = patched(adapter, fx.WAKEFIELD_WORK)
        with ctx:
            result = await adapter.check_retraction(
                "https://doi.org/10.1016/S0140-6736(97)11096-0"
            )
        assert result["found"] is True
        assert result["retracted"] is True
        assert result["corrected"] is True
        assert result["expression_of_concern"] is False
        assert result["title_flagged"] is True
        assert result["doi"] == WAKEFIELD
        assert {n["type"] for n in result["notices"]} == {"correction", "retraction"}
        retraction = next(n for n in result["notices"] if n["type"] == "retraction")
        assert retraction == {
            "doi": "10.1016/s0140-6736(10)60175-4",
            "type": "retraction",
            "label": "Retraction",
            "date": "2010-02-06",
            "asserted_by": "retraction-watch",
        }
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_check_bypasses_cache(self, adapter):
        ctx, mock = patched(adapter, fx.WAKEFIELD_WORK)
        with ctx:
            await adapter.get_concept_details(WAKEFIELD)
            await adapter.check_retraction(WAKEFIELD)
        assert mock.call_count == 2

    @pytest.mark.asyncio
    async def test_clean_paper_with_only_an_addendum(self, adapter):
        ctx, _ = patched(adapter, fx.NATURE_WORK)
        with ctx:
            result = await adapter.check_retraction(NATURE)
        assert result["found"] is True
        assert result["retracted"] is False
        assert result["corrected"] is True  # addendum counts as a correction-type notice
        assert result["title_flagged"] is False

    @pytest.mark.asyncio
    async def test_expression_of_concern(self, adapter):
        work = copy.deepcopy(fx.NATURE_WORK)
        work["message"]["updated-by"] = [{"DOI": "10.1/eoc", "type": "expression_of_concern"}]
        ctx, _ = patched(adapter, work)
        with ctx:
            result = await adapter.check_retraction(NATURE)
        assert result["expression_of_concern"] is True
        assert result["retracted"] is False
        assert result["notices"][0]["date"] == ""

    @pytest.mark.asyncio
    async def test_notice_lists_what_it_retracts(self, adapter):
        ctx, _ = patched(adapter, fx.RETRACTION_NOTICE)
        with ctx:
            result = await adapter.check_retraction("10.1016/s0140-6736(10)60175-4")
        assert result["is_notice_for"] == [WAKEFIELD]
        assert result["retracted"] is False

    @pytest.mark.asyncio
    async def test_unknown_doi_is_not_found_not_clean(self, adapter):
        ctx, _ = patched(adapter, not_found())
        with ctx:
            result = await adapter.check_retraction("10.9999/nope")
        assert result["found"] is False
        assert result["retracted"] is False
        assert result["notices"] == []

    @pytest.mark.asyncio
    async def test_invalid_doi_and_errors(self, adapter):
        result = await adapter.check_retraction("not a doi")
        assert result["found"] is False and result["doi"] == "not a doi"
        with patch.object(adapter, "_fetch_work", side_effect=RuntimeError("x")):
            result = await adapter.check_retraction(NATURE)
        assert result["found"] is False


class TestAgency:
    @pytest.mark.asyncio
    async def test_agency(self, adapter):
        ctx, mock = patched(adapter, fx.AGENCY_RESPONSE)
        with ctx:
            assert await adapter.doi_agency("doi:" + WAKEFIELD) == "crossref"
        assert mock.call_args.args[0].endswith("/agency")

    @pytest.mark.asyncio
    async def test_agency_unknown_and_invalid(self, adapter):
        ctx, _ = patched(adapter, not_found())
        with ctx:
            assert await adapter.doi_agency("10.9999/x") is None
        assert await adapter.doi_agency("nonsense") is None
        with patch.object(adapter, "_get", side_effect=RuntimeError("x")):
            assert await adapter.doi_agency("10.1234/x") is None


def test_date_helper_edge_cases():
    assert cr._date({"date-parts": [[2020]]}) == "2020"
    assert cr._date({"date-parts": [[2020, 2]]}) == "2020-02"
    assert cr._date({"date-parts": [[None]]}) == ""
    assert cr._date({"date-parts": []}) == ""
    assert cr._date(None) == ""
    assert cr._work_date({"created": {"date-parts": [[2019, 5, 1]]}}) == "2019-05-01"
    assert cr._first("  plain  ") == "plain"
    assert cr._first(["", "second"]) == "second"
    assert cr._first(None) == ""
