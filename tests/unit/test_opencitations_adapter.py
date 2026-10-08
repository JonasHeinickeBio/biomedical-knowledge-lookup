"""Unit tests for OpenCitationsAdapter (trimmed real responses, no network)."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import opencitations_adapter as oc
from knowledge_lookup.adapters.opencitations_adapter import OpenCitationsAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import opencitations_responses as fx

pytestmark = pytest.mark.unit

DOI = "10.1038/s41586-020-2012-7"


class HttpError(Exception):
    """Stand-in for ``aiohttp.ClientResponseError`` (which needs a real request object)."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


@pytest.fixture(autouse=True)
def _clean_env_and_sleep(monkeypatch):
    monkeypatch.delenv(oc.TOKEN_ENV, raising=False)
    monkeypatch.setattr(oc.asyncio, "sleep", AsyncMock())


@pytest.fixture
def adapter():
    return OpenCitationsAdapter(LookupConfig())


def routed(adapter, routes):
    """Patch ``_make_request``: first route whose key is a substring of the URL answers."""
    calls: list[tuple[str, dict | None, dict | None]] = []

    async def fake(url, params=None, headers=None, json_data=None):
        calls.append((url, params, headers))
        for key, value in routes:
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return copy.deepcopy(value)
        raise AssertionError(f"unexpected request {url}")

    return patch.object(adapter, "_make_request", new=fake), calls


FULL = [
    ("/meta/v1/metadata/", fx.META),
    ("/citation-count/", fx.CITATION_COUNT),
    ("/reference-count/", fx.REFERENCE_COUNT),
    ("/references/", fx.REFERENCES),
    ("/citations/", fx.CITATIONS),
]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.OPENCITATIONS
        assert adapter.is_available() is True
        assert adapter.min_request_timeout >= 60

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (DOI, f"doi:{DOI}"),
            (f"doi:{DOI}", f"doi:{DOI}"),
            (f"DOI:{DOI.upper()}", f"doi:{DOI}"),
            (f"https://doi.org/{DOI}", f"doi:{DOI}"),
            ("32015507", "pmid:32015507"),
            ("PMID:32015507", "pmid:32015507"),
            ("pmid: 32015507", "pmid:32015507"),
            ("omid:br/06130344922", "omid:br/06130344922"),
            ("br/06130344922", "omid:br/06130344922"),
            ("long covid", None),
            ("10.1/short", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert OpenCitationsAdapter.normalize_id(raw) == expected

    def test_parse_helpers(self):
        ids = oc._parse_ids("omid:br/1 doi:10.1/x pmid:7 pmid:8")
        assert ids == {"omid": ["br/1"], "doi": ["10.1/x"], "pmid": ["7", "8"]}
        assert oc._parse_ids(None) == {}
        assert oc._duration_years("P6Y3M4D") == pytest.approx(6.26, abs=0.01)
        assert oc._duration_years("P5Y") == 5.0
        assert oc._duration_years("P1M") == pytest.approx(0.08, abs=0.01)
        assert oc._duration_years("garbage") is None
        assert oc._duration_years("P") is None
        assert OpenCitationsAdapter._parse_venue(
            "Nature [issn:0028-0836 issn:1476-4687 omid:br/6]"
        ) == (
            "Nature",
            ["0028-0836", "1476-4687"],
        )
        assert OpenCitationsAdapter._parse_venue("Plain venue") == ("Plain venue", [])
        assert OpenCitationsAdapter._parse_venue(None) == ("", [])
        assert OpenCitationsAdapter._parse_people("Zhou, Peng [omid:ra/1]; Yang, X; ") == [
            "Zhou, Peng",
            "Yang, X",
        ]


class TestAuth:
    @pytest.mark.asyncio
    async def test_no_token_means_empty_headers(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            await adapter.get_concept_details(DOI)
        assert all(not headers for _, _, headers in calls)

    @pytest.mark.asyncio
    async def test_token_from_env_is_sent_in_authorization_header(self, adapter, monkeypatch):
        monkeypatch.setenv(oc.TOKEN_ENV, " tok-123 ")
        ctx, calls = routed(adapter, FULL)
        with ctx:
            await adapter.get_concept_details(DOI)
        assert {h["authorization"] for _, _, h in calls} == {"tok-123"}

    @pytest.mark.asyncio
    async def test_token_from_config_api_keys(self):
        adapter = OpenCitationsAdapter(LookupConfig(api_keys={"opencitations": "cfg-token"}))
        assert adapter._auth_headers() == {"authorization": "cfg-token"}

    def test_blank_token_is_ignored(self, adapter, monkeypatch):
        monkeypatch.setenv(oc.TOKEN_ENV, "   ")
        assert adapter._auth_headers() == {}


class TestSearchAndDetails:
    @pytest.mark.asyncio
    async def test_search_resolves_identifier(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            results = await adapter.search_concepts(f"https://doi.org/{DOI}", limit=5)
        assert [c.primary_id for c in results] == [DOI]
        assert calls[0][0] == f"{oc.META_URL}/doi:{DOI}"

    @pytest.mark.asyncio
    async def test_text_queries_return_nothing_and_make_no_request(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            assert await adapter.search_concepts("long covid") == []
            assert await adapter.search_concepts("") == []
            assert await adapter.search_concepts(DOI, limit=0) == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_details(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            concept = await adapter.get_concept_details("pmid:32015507")
        assert [c[0] for c in calls] == [
            f"{oc.META_URL}/pmid:32015507",
            f"{oc.INDEX_URL}/citation-count/pmid:32015507",
            f"{oc.INDEX_URL}/reference-count/pmid:32015507",
        ]
        assert concept.primary_id == DOI  # resolved from the Meta record
        assert concept.concept_type == ConceptType.CITATION
        assert concept.primary_label.startswith("A Pneumonia Outbreak")
        assert "venue:Nature" in concept.categories
        assert "year:2020" in concept.categories
        assert "type:journal article" in concept.categories
        assert any(i.identifier == "32015507" for i in concept.identifiers)
        data = concept.source_data[KnowledgeSource.OPENCITATIONS]
        assert data["citation_count"] == 19265
        assert data["reference_count"] == 14
        assert data["license"] == "CC0 1.0"
        assert "lag" in data["note"]
        assert data["ids"]["openalex"] == ["W3004280078"]
        assert data["authors"][0] == "Zhou, Peng"
        assert data["issn"][0] == "0028-0836"
        assert data["publisher"].startswith("Springer Science")

    @pytest.mark.asyncio
    async def test_unknown_work_is_none(self, adapter):
        ctx, _ = routed(
            adapter,
            [
                ("/meta/", []),
                ("/citation-count/", [{"count": "0"}]),
                ("/reference-count/", [{"count": "0"}]),
            ],
        )
        with ctx:
            assert await adapter.get_concept_details("doi:10.9999/nope") is None

    @pytest.mark.asyncio
    async def test_work_missing_in_meta_but_with_citations_uses_the_queried_id(self, adapter):
        ctx, _ = routed(
            adapter,
            [
                ("/meta/", []),
                ("/citation-count/", [{"count": "5"}]),
                ("/reference-count/", [{"count": "x"}]),
            ],
        )
        with ctx:
            concept = await adapter.get_concept_details("doi:10.9999/Known")
        assert concept.primary_id == "10.9999/known"
        assert concept.primary_label == "10.9999/known"
        data = concept.source_data[KnowledgeSource.OPENCITATIONS]
        assert data["citation_count"] == 5 and data["reference_count"] is None

    @pytest.mark.asyncio
    async def test_omid_only_work_keeps_omid_as_primary_id(self, adapter):
        meta = [{"id": "omid:br/06130344922", "title": "T"}]
        ctx, _ = routed(adapter, [("/meta/", meta), ("/count/", [{"count": "1"}])])
        with ctx:
            concept = await adapter.get_concept_details("omid:br/06130344922")
        assert concept.primary_id == "omid:br/06130344922"

    @pytest.mark.asyncio
    async def test_invalid_id_and_errors(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            assert await adapter.get_concept_details("nonsense") is None
            assert await adapter.get_relationships("nonsense") == []
            assert await adapter.get_mappings("nonsense") == []
            assert await adapter.get_citations("nonsense") == []
            assert await adapter.get_references("nonsense") == []
        assert calls == []
        for method in ("get_concept_details", "get_relationships", "get_mappings"):
            with (
                patch.object(adapter, "_meta", side_effect=RuntimeError("x")),
                patch.object(adapter, "_get_rows", side_effect=RuntimeError("x")),
            ):
                result = await getattr(adapter, method)(DOI)
            assert result in (None, [])
        with patch.object(adapter, "get_concept_details", side_effect=RuntimeError("x")):
            assert await adapter.search_concepts(DOI) == []

    @pytest.mark.asyncio
    async def test_http_errors_give_none(self, adapter):
        ctx, _ = routed(adapter, [("/", HttpError(500))])
        with ctx:
            assert await adapter.get_concept_details(DOI) is None
        ctx, _ = routed(adapter, [("/", HttpError(404))])
        with ctx:
            assert await adapter.get_concept_details(DOI) is None
        ctx, _ = routed(adapter, [("/", {"not": "a list"})])
        with ctx:
            assert await adapter.get_concept_details(DOI) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_references_and_citations(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            edges = await adapter.get_relationships(DOI)
        cites = [e for e in edges if e["relation_label"] == "cites"]
        cited_by = [e for e in edges if e["relation_label"] == "cited_by"]
        assert len(cites) == 3 and len(cited_by) == 1
        first = cites[0]
        assert first["related_id"] == "10.1038/nature12711"
        assert first["oci"] == "06130344922-06110355954"
        assert first["creation"] == "2020-02-03"
        assert first["timespan"] == "P6Y3M4D"
        assert first["timespan_years"] == pytest.approx(6.26, abs=0.01)
        assert first["journal_self_citation"] is True
        assert first["author_self_citation"] is False
        assert first["source"] == "OPENCITATIONS"
        assert first["other_ids"]["pmid"] == ["24172901"]
        citing = cited_by[0]
        assert citing["related_id"] == "10.2174/0126667975312229240903074835"
        assert citing["creation"] == "2026-10"
        references_call = next(c for c in calls if "/references/" in c[0])
        assert references_call[1] == {"sort": "desc(creation)"}

    @pytest.mark.asyncio
    async def test_small_citation_list_has_no_date_filter(self, adapter):
        ctx, calls = routed(adapter, [("/citation-count/", [{"count": "12"}])] + FULL)
        with ctx:
            await adapter.get_citations(DOI)
        params = next(c[1] for c in calls if "/citations/" in c[0])
        assert "filter" not in params

    @pytest.mark.asyncio
    async def test_highly_cited_work_is_restricted_by_date(self, adapter):
        routes = [("/citation-count/", [{"count": str(oc.BULK_CAP + 1)}])] + FULL
        ctx, calls = routed(adapter, routes)
        with ctx:
            await adapter.get_citations(DOI)
        params = next(c[1] for c in calls if "/citations/" in c[0])
        assert params["sort"] == "desc(creation)"
        assert params["filter"].startswith("creation:>20") and params["filter"].endswith("-12")

    @pytest.mark.asyncio
    async def test_edge_cap_and_dedup(self, adapter):
        rows = [
            {
                "oci": f"1-{i}",
                "citing": "omid:br/1 doi:10.1/a",
                "cited": f"omid:br/{i} doi:10.1234/P{i % 150}",
                "creation": "2020",
                "timespan": "P1Y",
                "journal_sc": "no",
                "author_sc": "yes",
            }
            for i in range(300)
        ]
        ctx, _ = routed(adapter, [("/references/", rows)])
        with ctx:
            capped = await adapter.get_references(DOI)
            few = await adapter.get_references(DOI, limit=5)
            none = await adapter.get_references(DOI, limit=0)
        assert len(capped) == oc.MAX_EDGES
        assert len({e["related_id"] for e in capped}) == oc.MAX_EDGES
        assert capped[0]["related_id"] == "10.1234/p0"  # DOIs lower-cased
        assert capped[0]["author_self_citation"] is True
        assert len(few) == 5 and none == []

    @pytest.mark.asyncio
    async def test_related_id_falls_back_to_pmid_then_omid_and_skips_empty(self, adapter):
        rows = [
            {"oci": "a", "cited": "omid:br/1 pmid:99"},
            {"oci": "b", "cited": "omid:br/2"},
            {"oci": "c", "cited": "issn:0000-0000"},
            {"oci": "d"},
            {"oci": "e", "cited": "omid:br/2"},  # duplicate
        ]
        ctx, _ = routed(adapter, [("/references/", rows)])
        with ctx:
            edges = await adapter.get_references(DOI)
        assert [e["related_id"] for e in edges] == ["pmid:99", "omid:br/2"]
        assert edges[0]["timespan_years"] is None and edges[0]["journal_self_citation"] is False

    @pytest.mark.asyncio
    async def test_failed_requests_give_empty_lists(self, adapter):
        ctx, _ = routed(adapter, [("/", HttpError(500))])
        with ctx:
            assert await adapter.get_relationships(DOI) == []

    @pytest.mark.asyncio
    async def test_count_failure_still_fetches_citations(self, adapter):
        ctx, calls = routed(
            adapter, [("/citation-count/", HttpError(500)), ("/citations/", fx.CITATIONS)]
        )
        with ctx:
            edges = await adapter.get_citations(DOI)
        assert len(edges) == 1
        assert "filter" not in next(c[1] for c in calls if "/citations/" in c[0])


class TestMappings:
    @pytest.mark.asyncio
    async def test_ids_and_issns(self, adapter):
        ctx, calls = routed(adapter, FULL)
        with ctx:
            mappings = await adapter.get_mappings(f"doi:{DOI}")
        pairs = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("PubMed", "32015507") in pairs
        assert ("OPENALEX", "W3004280078") in pairs
        assert ("OMID", "br/06130344922") in pairs
        assert ("ISSN", "0028-0836") in pairs
        assert ("DOI", DOI) not in pairs  # the queried id is not repeated
        assert len(calls) == 1
        for m in mappings:
            assert m["fromId"] == DOI and m["fromSource"] == "OPENCITATIONS"
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
        assert (
            next(m for m in mappings if m["toSource"] == "ISSN")["mappingType"] == "container_id"
        )

    @pytest.mark.asyncio
    async def test_pmid_query_includes_the_doi_but_not_the_pmid(self, adapter):
        ctx, _ = routed(adapter, FULL)
        with ctx:
            mappings = await adapter.get_mappings("pmid:32015507")
        pairs = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("PubMed", "32015507") not in pairs
        assert ("DOI", DOI) not in pairs  # fromId already is the DOI
        assert ("OPENALEX", "W3004280078") in pairs

    @pytest.mark.asyncio
    async def test_omid_query_maps_to_doi(self, adapter):
        ctx, _ = routed(adapter, FULL)
        with ctx:
            mappings = await adapter.get_mappings("omid:br/06130344922")
        assert ("OMID", "br/06130344922") not in {(m["toSource"], m["toId"]) for m in mappings}
        assert all(m["fromId"] == DOI for m in mappings)

    @pytest.mark.asyncio
    async def test_unknown_id(self, adapter):
        ctx, _ = routed(adapter, [("/meta/", [])])
        with ctx:
            assert await adapter.get_mappings("doi:10.9999/nope") == []

    @pytest.mark.asyncio
    async def test_meta_without_doi_uses_queried_id_and_dedups(self, adapter):
        meta = [{"id": "pmid:5 pmid:5 omid:br/9 unknown:1", "venue": "V [issn:1111-1111]"}]
        ctx, _ = routed(adapter, [("/meta/", meta)])
        with ctx:
            mappings = await adapter.get_mappings("omid:br/9")
        assert [(m["fromId"], m["toSource"], m["toId"]) for m in mappings] == [
            ("br/9", "PubMed", "5"),
            ("br/9", "ISSN", "1111-1111"),
        ]


class TestThrottle:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        clock = [10.0]
        monkeypatch.setattr(oc.time, "monotonic", lambda: clock[0])
        slept: list[float] = []

        async def fake_sleep(delay):
            slept.append(delay)
            clock[0] += delay

        monkeypatch.setattr(oc.asyncio, "sleep", fake_sleep)
        ctx, _ = routed(adapter, FULL)
        with ctx:
            await adapter.get_concept_details(DOI)  # three requests
        assert len(slept) == 2
        assert all(s == pytest.approx(oc.REQUEST_INTERVAL, abs=1e-6) for s in slept)
