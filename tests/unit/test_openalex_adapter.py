"""Unit tests for OpenAlexAdapter (trimmed real responses, no network)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.openalex_adapter import (
    OpenAlexAdapter,
    reconstruct_abstract,
    short_id,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import openalex_responses as fx

pytestmark = pytest.mark.unit

DAVIS = "W4316014106"  # Long COVID review, no abstract in OpenAlex
JAMA = "W4378212766"  # PASC definition, abstract present


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OPENALEX_MAILTO", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)


@pytest.fixture
def adapter():
    return OpenAlexAdapter(LookupConfig())


def patched(adapter, *responses):
    mock = AsyncMock(side_effect=list(responses)) if len(responses) > 1 else AsyncMock()
    if len(responses) == 1:
        mock.return_value = responses[0]
    return patch.object(adapter, "_make_request", new=mock), mock


def router(routes):
    """Fake ``_make_request`` answering by URL suffix (``works/W..``, ``works``, ``topics``)."""

    async def fake(url, params=None, **kwargs):
        key = url.split("api.openalex.org/")[1]
        if params and "filter" in params:
            key += "?" + params["filter"].split(":")[0]
        value = routes[key]
        if isinstance(value, Exception):
            raise value
        return value

    return AsyncMock(side_effect=fake)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.OPENALEX
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("W4316014106", ("work", "W4316014106")),
            ("w4316014106", ("work", "W4316014106")),
            ("OPENALEX:W4316014106", ("work", "W4316014106")),
            ("https://openalex.org/W4316014106", ("work", "W4316014106")),
            ("10.1038/S41579-022-00846-2", ("work", "doi:10.1038/s41579-022-00846-2")),
            ("doi:10.1038/s41579-022-00846-2", ("work", "doi:10.1038/s41579-022-00846-2")),
            (
                "https://doi.org/10.1038/s41579-022-00846-2",
                ("work", "doi:10.1038/s41579-022-00846-2"),
            ),
            ("PMID:36639608", ("work", "pmid:36639608")),
            ("pmid:36639608", ("work", "pmid:36639608")),
            ("36639608", ("work", "pmid:36639608")),
            ("https://pubmed.ncbi.nlm.nih.gov/36639608/", ("work", "pmid:36639608")),
            ("mag:3143129303", ("work", "mag:3143129303")),
            ("T11368", ("topic", "T11368")),
            ("https://openalex.org/topics/T11368", ("topic", "T11368")),
            ("", None),
            ("not an id", None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert OpenAlexAdapter.parse_id(raw) == expected

    def test_short_id(self):
        assert short_id("https://openalex.org/W1/") == "W1"
        assert short_id(None) == ""

    def test_reconstruct_abstract(self):
        assert reconstruct_abstract({"b": [1], "a": [0], "c": [2, 3]}) == "a b c c"
        assert reconstruct_abstract(None) == ""
        assert reconstruct_abstract({}) == ""
        assert reconstruct_abstract({"x": "bad", "y": ["bad"], "z": [0]}) == "z"
        text = reconstruct_abstract(fx.WORK_WITH_ABSTRACT["abstract_inverted_index"])
        assert text.startswith("Importance: SARS-CoV-2 infection is associated")


class TestRequestParameters:
    @pytest.mark.asyncio
    async def test_nothing_extra_is_sent_by_default(self, adapter):
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            await adapter.get_concept_details(DAVIS)
        params = mock.call_args.kwargs["params"]
        assert set(params) == {"select"}

    @pytest.mark.asyncio
    async def test_mailto_only_from_environment(self, adapter, monkeypatch):
        monkeypatch.setenv("OPENALEX_MAILTO", "someone@example.org")
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            await adapter.get_concept_details(DAVIS)
        assert mock.call_args.kwargs["params"]["mailto"] == "someone@example.org"

    @pytest.mark.asyncio
    async def test_api_key_from_environment(self, monkeypatch):
        monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
        adapter = OpenAlexAdapter(LookupConfig())
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            await adapter.get_concept_details(DAVIS)
        assert mock.call_args.kwargs["params"]["api_key"] == "test-key"


class TestDetails:
    @pytest.mark.asyncio
    async def test_work_without_abstract(self, adapter):
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            concept = await adapter.get_concept_details("PMID:36639608")
        assert mock.call_args.args[0].endswith("/works/pmid:36639608")
        assert concept.primary_id == DAVIS
        assert concept.concept_type == ConceptType.CITATION
        assert concept.definitions == []
        assert "year:2023" in concept.categories
        assert "journal:Nature Reviews Microbiology" in concept.categories
        assert "oa:bronze" in concept.categories
        assert "long COVID" in concept.synonyms
        assert concept.semantic_types == ["review"]
        ids = {i.identifier for i in concept.identifiers}
        assert {DAVIS, "DOI:10.1038/s41579-022-00846-2", "PMID:36639608"} <= ids
        data = concept.source_data[KnowledgeSource.OPENALEX]
        assert data["cited_by_count"] == 4347
        assert data["topics"][0]["name"] == "Long-Term Effects of COVID-19"
        assert data["topics"][0]["score"] == pytest.approx(1.0, abs=0.01)
        assert data["open_access"]["is_oa"] is True
        assert data["abstract"] is None
        assert data["url"] == f"https://openalex.org/{DAVIS}"

    @pytest.mark.asyncio
    async def test_work_with_abstract_and_pmcid(self, adapter):
        record = copy.deepcopy(fx.WORK_WITH_ABSTRACT)
        record["ids"]["pmcid"] = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10278225"
        ctx, mock = patched(adapter, record)
        with ctx:
            concept = await adapter.get_concept_details("https://doi.org/10.1001/JAMA.2023.8823")
        assert mock.call_args.args[0].endswith("/works/doi:10.1001/jama.2023.8823")
        assert concept.definitions[0].startswith("Importance: SARS-CoV-2")
        assert "PMC10278225" in {i.identifier for i in concept.identifiers}
        assert concept.source_data[KnowledgeSource.OPENALEX]["pmcid"] == "PMC10278225"

    @pytest.mark.asyncio
    async def test_topic_details(self, adapter):
        ctx, mock = patched(adapter, fx.TOPIC)
        with ctx:
            concept = await adapter.get_concept_details("T11368")
        assert mock.call_args.args[0].endswith("/topics/T11368")
        assert concept.primary_id == "T11368"
        assert concept.concept_type == ConceptType.UNKNOWN
        assert "field:Medicine" in concept.categories
        assert "long COVID" in concept.synonyms
        assert concept.definitions[0].startswith("This cluster of papers")
        data = concept.source_data[KnowledgeSource.OPENALEX]
        assert data["domain"] == "Health Sciences"
        assert data["wikipedia"].startswith("https://en.wikipedia.org/")

    @pytest.mark.asyncio
    async def test_not_found_and_invalid_ids(self, adapter):
        err = AsyncMock(side_effect=OSError("404"))
        with patch.object(adapter, "_make_request", new=err):
            assert await adapter.get_concept_details("W1") is None
            assert await adapter.get_concept_details("T1") is None
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            assert await adapter.get_concept_details("garbage") is None
            assert await adapter.get_concept_details("") is None
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_object_payload(self, adapter):
        ctx, _ = patched(adapter, ["not", "a", "dict"])
        with ctx:
            assert await adapter.get_concept_details(DAVIS) is None

    @pytest.mark.asyncio
    async def test_records_without_id_or_title(self, adapter):
        assert adapter._work_to_concept({"id": "https://openalex.org/W1"}) is None
        assert adapter._work_to_concept({"display_name": "x"}) is None
        assert adapter._topic_to_concept({"id": "https://openalex.org/T1"}) is None
        minimal = adapter._work_to_concept({"id": "https://openalex.org/W9", "title": "Only"})
        assert minimal.primary_label == "Only"
        assert minimal.source_data[KnowledgeSource.OPENALEX]["authors"] == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_works(self, adapter):
        ctx, mock = patched(adapter, fx.WORK_SEARCH)
        with ctx:
            results = await adapter.search_works("long covid", limit=5)
        params = mock.call_args.kwargs["params"]
        assert params["search"] == "long covid" and params["per-page"] == 5
        assert "abstract_inverted_index" in params["select"]
        assert [c.primary_id for c in results] == [JAMA, DAVIS]

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, adapter):
        ctx, _ = patched(adapter, fx.WORK_SEARCH)
        with ctx:
            results = await adapter.search_works("long covid", limit=1)
        assert [c.primary_id for c in results] == [JAMA]

    @pytest.mark.asyncio
    async def test_limit_is_capped_and_empty_inputs(self, adapter):
        ctx, mock = patched(adapter, {"results": []})
        with ctx:
            assert await adapter.search_works("x", limit=5000) == []
            assert mock.call_args.kwargs["params"]["per-page"] == 100
            mock.reset_mock()
            assert await adapter.search_works("", 5) == []
            assert await adapter.search_works("x", 0) == []
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("x", 0) == []
            assert await adapter.search_topics("", 3) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_filters_and_sort(self, adapter):
        ctx, mock = patched(adapter, fx.WORK_SEARCH)
        with ctx:
            await adapter.search_works(
                "fatigue",
                3,
                {
                    "year": 2024,
                    "oa": True,
                    "type": ["article", "review"],
                    "bad key!": "x",
                    "language": "",
                    "topic": "T11368",
                },
                sort="cited_by_count:desc",
            )
        params = mock.call_args.kwargs["params"]
        assert params["filter"] == (
            "publication_year:2024,open_access.is_oa:true,type:article|review,topics.id:T11368"
        )
        assert params["sort"] == "cited_by_count:desc"

    def test_unsafe_filter_values_are_dropped(self):
        text = OpenAlexAdapter._filter_text({"type": "a,b", "year": "2020&x=1", "oa": False})
        assert text == "open_access.is_oa:false"

    @pytest.mark.asyncio
    async def test_search_topics(self, adapter):
        ctx, mock = patched(adapter, fx.TOPIC_SEARCH)
        with ctx:
            results = await adapter.search_topics("fatigue", 3)
        assert mock.call_args.args[0].endswith("/topics")
        assert [c.primary_id for c in results] == ["T11368"]

    @pytest.mark.asyncio
    async def test_search_concepts_combines_works_and_topics(self, adapter):
        mock = router({"works": fx.WORK_SEARCH, "topics": fx.TOPIC_SEARCH})
        with patch.object(adapter, "_make_request", new=mock):
            results = await adapter.search_concepts("long covid", limit=3)
        assert [c.primary_id for c in results] == [JAMA, DAVIS, "T11368"]
        with patch.object(adapter, "_make_request", new=mock):
            results = await adapter.search_concepts("long covid", limit=2)
        assert [c.primary_id for c in results] == [JAMA, "T11368"]

    @pytest.mark.asyncio
    async def test_search_concepts_resolves_ids_directly(self, adapter):
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            results = await adapter.search_concepts("doi:10.1038/s41579-022-00846-2")
        assert [c.primary_id for c in results] == [DAVIS]
        assert mock.call_count == 1
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("x"))):
            assert await adapter.search_concepts("PMID:36639608") == []

    @pytest.mark.asyncio
    async def test_bare_digits_are_search_text(self, adapter):
        mock = router({"works": {"results": []}, "topics": {"results": []}})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.search_concepts("2019") == []
        assert mock.call_count == 2

    @pytest.mark.asyncio
    async def test_failures_return_empty(self, adapter):
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("429"))):
            assert await adapter.search_concepts("long covid") == []
            assert await adapter.search_works("x") == []
            assert await adapter.search_topics("x") == []
        for bad in ([], {"results": "oops"}, {"error": "x"}):
            with patch.object(adapter, "_make_request", new=AsyncMock(return_value=bad)):
                assert await adapter.search_works("x") == []

    @pytest.mark.asyncio
    async def test_duplicates_and_junk_rows_are_dropped(self, adapter):
        rows = {"results": [fx.WORK_NO_ABSTRACT, fx.WORK_NO_ABSTRACT, "junk", {"id": "x"}]}
        ctx, _ = patched(adapter, rows)
        with ctx:
            assert len(await adapter.search_works("x")) == 1


class TestRelationships:
    @pytest.mark.asyncio
    async def test_work_relationships(self, adapter):
        mock = router(
            {
                f"works/{DAVIS}": {
                    "id": f"https://openalex.org/{DAVIS}",
                    "referenced_works": fx.WORK_NO_ABSTRACT["referenced_works"],
                    "topics": fx.WORK_NO_ABSTRACT["topics"],
                },
                "works?openalex": fx.REFERENCED_BRIEF_LIST,
                "works?cites": fx.CITING_LIST,
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            rels = await adapter.get_relationships(DAVIS, limit=3)
        by_label: dict[str, list] = {}
        for rel in rels:
            by_label.setdefault(rel["relation_label"], []).append(rel)
        assert [r["related_id"] for r in by_label["has_topic"]][0] == "T11368"
        assert by_label["has_topic"][0]["field"] == "Medicine"
        assert len(by_label["cites"]) == 3
        assert by_label["cites"][0]["related_id"] == "W1970188154"
        assert by_label["cites"][1]["related_name"] == fx.REFERENCED_BRIEF_LIST["results"][0][
            "display_name"
        ] or by_label["cites"][1]["related_name"].startswith("W")
        assert [r["related_id"] for r in by_label["cited_by"]] == [
            JAMA,
            "W4387012832",
            "W4382918478",
        ]
        assert by_label["cited_by"][0]["total_citing"] == 4224
        assert by_label["cited_by"][0]["cited_by_count"] == 888
        assert all(r["source"] == "OPENALEX" for r in rels)
        calls = [c.kwargs["params"] for c in mock.call_args_list]
        citing_call = next(p for p in calls if p.get("filter", "").startswith("cites:"))
        assert citing_call["per-page"] == 3 and citing_call["sort"] == "cited_by_count:desc"
        batch_call = next(p for p in calls if p.get("filter", "").startswith("openalex:"))
        assert batch_call["filter"].count("|") == 2

    @pytest.mark.asyncio
    async def test_limit_zero_skips_citation_calls(self, adapter):
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            rels = await adapter.get_relationships("pmid:36639608", limit=0)
        assert mock.call_count == 1
        assert {r["relation_label"] for r in rels} == {"has_topic"}

    @pytest.mark.asyncio
    async def test_unresolved_reference_names_fall_back_to_id(self, adapter):
        record = {
            "id": f"https://openalex.org/{DAVIS}",
            "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W1"],
            "topics": [],
        }
        mock = router(
            {
                f"works/{DAVIS}": record,
                "works?openalex": {"results": "x"},
                "works?cites": {"results": []},
            }
        )
        with patch.object(adapter, "_make_request", new=mock):
            rels = await adapter.get_relationships(DAVIS, limit=5)
        assert rels == [
            {
                "relation_label": "cites",
                "related_id": "W1",
                "related_name": "W1",
                "source": "OPENALEX",
                "year": None,
            }
        ]

    @pytest.mark.asyncio
    async def test_topic_relationships(self, adapter):
        ctx, _ = patched(adapter, fx.TOPIC)
        with ctx:
            rels = await adapter.get_relationships("T11368", limit=2)
        labels = [(r["relation_label"], r["related_id"]) for r in rels]
        assert labels[:3] == [
            ("part_of", "subfield:2728"),
            ("part_of", "field:27"),
            ("part_of", "domain:4"),
        ]
        assert [r for r in labels if r[0] == "sibling_topic"] == [
            ("sibling_topic", "T10085"),
            ("sibling_topic", "T10420"),
        ]

    @pytest.mark.asyncio
    async def test_referenced_and_citing_helpers(self, adapter):
        rels = [
            {"relation_label": "cites", "related_id": "W1"},
            {"relation_label": "cited_by", "related_id": "W2"},
        ]
        with patch.object(adapter, "get_relationships", new=AsyncMock(return_value=rels)):
            assert await adapter.get_referenced_works("W9") == [rels[0]]
            assert await adapter.get_citing_works("W9") == [rels[1]]

    @pytest.mark.asyncio
    async def test_errors_and_invalid_ids(self, adapter):
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("x"))):
            assert await adapter.get_relationships(DAVIS) == []
            assert await adapter.get_relationships("T1") == []
        ctx, mock = patched(adapter, fx.WORK_NO_ABSTRACT)
        with ctx:
            assert await adapter.get_relationships("garbage") == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_citing_list_with_bad_payload(self, adapter):
        with patch.object(adapter, "_get", new=AsyncMock(return_value={"results": "x"})):
            assert await adapter._citing_edges(DAVIS, 5) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_work_mappings(self, adapter):
        record = {
            "id": f"https://openalex.org/{DAVIS}",
            "ids": {
                "openalex": f"https://openalex.org/{DAVIS}",
                "doi": "https://doi.org/10.1038/s41579-022-00846-2",
                "pmid": "https://pubmed.ncbi.nlm.nih.gov/36639608",
                "pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9839201",
                "mag": "4316014106",
            },
        }
        ctx, mock = patched(adapter, record)
        with ctx:
            mappings = await adapter.get_mappings("doi:10.1038/s41579-022-00846-2")
        assert mock.call_args.kwargs["params"]["select"] == "id,ids"
        assert {m["toSource"]: m["toId"] for m in mappings} == {
            "DOI": "10.1038/s41579-022-00846-2",
            "PMID": "36639608",
            "PMCID": "PMC9839201",
            "MAG": "4316014106",
        }
        assert all(
            set(m) == {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"}
            and m["fromId"] == DAVIS
            for m in mappings
        )

    @pytest.mark.asyncio
    async def test_topic_mappings(self, adapter):
        ctx, _ = patched(adapter, {"id": "https://openalex.org/T11368", "ids": fx.TOPIC["ids"]})
        with ctx:
            mappings = await adapter.get_mappings("T11368")
        assert [m["toSource"] for m in mappings] == ["Wikipedia"]

    @pytest.mark.asyncio
    async def test_mapping_failures(self, adapter):
        with patch.object(adapter, "_make_request", new=AsyncMock(side_effect=OSError("x"))):
            assert await adapter.get_mappings(DAVIS) == []
        ctx, mock = patched(adapter, {})
        with ctx:
            assert await adapter.get_mappings("garbage") == []
            assert await adapter.get_mappings(DAVIS) == []
        assert mock.call_count == 1


class TestDefensiveBranches:
    @pytest.mark.asyncio
    async def test_unexpected_exceptions_do_not_escape(self, adapter):
        boom = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(adapter, "_get", new=boom):
            assert await adapter.search_works("x") == []
            assert await adapter.search_topics("x") == []
            assert await adapter.search_concepts("x") == []
            assert await adapter.get_concept_details(DAVIS) is None
            assert await adapter.get_relationships(DAVIS) == []
            assert await adapter.get_mappings(DAVIS) == []

    def test_malformed_records_do_not_raise(self, adapter):
        bad_work = {
            "id": "https://openalex.org/W1",
            "title": "t",
            "authorships": [{"author": "x"}],
        }
        assert adapter._work_to_concept(bad_work) is None
        bad_topic = {"id": "https://openalex.org/T1", "display_name": "t", "subfield": "x"}
        assert adapter._topic_to_concept(bad_topic) is None

    @pytest.mark.asyncio
    async def test_work_without_references_makes_no_batch_call(self, adapter):
        record = {"id": f"https://openalex.org/{DAVIS}", "referenced_works": [], "topics": []}
        mock = router({f"works/{DAVIS}": record, "works?cites": {"results": []}})
        with patch.object(adapter, "_make_request", new=mock):
            assert await adapter.get_relationships(DAVIS, limit=5) == []
        assert mock.call_count == 2  # singleton + citing list, no batch lookup

    @pytest.mark.asyncio
    async def test_topic_relationships_not_found(self, adapter):
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            assert await adapter.get_relationships("T1") == []
