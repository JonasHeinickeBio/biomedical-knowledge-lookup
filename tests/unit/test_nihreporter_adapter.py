"""Unit tests for NIHReporterAdapter (trimmed real responses, no network)."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import nihreporter_adapter as nr
from knowledge_lookup.adapters.nihreporter_adapter import NIHReporterAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig
from tests.fixtures import nihreporter_responses as fx

pytestmark = pytest.mark.unit

CORE = "R01AI170850"


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(nr, "MIN_REQUEST_INTERVAL", 0.0)


@pytest.fixture
def adapter():
    return NIHReporterAdapter(LookupConfig())


def patched(adapter, *responses):
    """Patch ``_make_request`` with a sequence of responses (the last one repeats)."""
    mock = AsyncMock(side_effect=list(responses))
    return patch.object(adapter, "_make_request", new=mock), mock


def body(mock, index=-1):
    return mock.call_args_list[index].kwargs["json_data"]


def url(mock, index=-1):
    return mock.call_args_list[index].args[0]


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.NIHREPORTER
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("R01AI170850", ("core", "R01AI170850")),
            ("r01ai170850", ("core", "R01AI170850")),
            ("NIHREPORTER:R01AI170850", ("core", "R01AI170850")),
            ("5R01AI170850-05", ("project", "5R01AI170850-05")),
            ("1R01NS131967-01A1", ("project", "1R01NS131967-01A1")),
            ("3U54GM104940-08S1", ("project", "3U54GM104940-08S1")),
            ("11391125", ("appl", "11391125")),
            ("APPL:11391125", ("appl", "11391125")),
            ("NIHREPORTER:applid:11391125", ("appl", "11391125")),
            ("*R01AI170850*", None),
            ("R01", None),
            ("myalgic encephalomyelitis", None),
            ("", None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert NIHReporterAdapter.parse_id(raw) == expected

    def test_core_of(self):
        assert NIHReporterAdapter.core_of("5R01AI170850-05") == CORE
        assert NIHReporterAdapter.core_of(CORE) == CORE
        assert NIHReporterAdapter.core_of("nonsense") is None
        assert NIHReporterAdapter.core_of(None) is None


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_concepts(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_MECFS)
        with ctx:
            results = await adapter.search_concepts("myalgic encephalomyelitis", limit=4)
        assert [c.primary_id for c in results] == [
            "R01NS131967",
            "U54AI178855",
            "R01NS133905",
            "R01AI170850",
        ]
        assert url(mock) == nr.PROJECTS_URL
        sent = body(mock)
        assert (
            sent["criteria"]["advanced_text_search"]["search_text"] == "myalgic encephalomyelitis"
        )
        assert sent["limit"] == 12  # 4 hits x OVERFETCH
        assert sent["sort_field"] == "fiscal_year" and sent["sort_order"] == "desc"
        assert "Terms" not in sent["include_fields"]  # 6-7 KB per record
        first = results[0]
        assert first.concept_type == ConceptType.STUDY
        assert first.primary_label.startswith("Non-Invasive Multi-Modal")
        assert "fiscal_year:2026" in first.categories
        assert "institute:NINDS" in first.categories
        data = first.source_data[KnowledgeSource.NIHREPORTER]
        assert data["applications"][0]["fiscal_year"] == 2026

    @pytest.mark.asyncio
    async def test_limit_is_respected_and_capped(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_MECFS)
        with ctx:
            results = await adapter.search_concepts("fatigue", limit=2)
        assert len(results) == 2
        ctx, mock = patched(adapter, fx.SEARCH_MECFS)
        with ctx:
            await adapter.search_concepts("fatigue", limit=5000)
        assert body(mock)["limit"] == nr.MAX_FETCH

    @pytest.mark.asyncio
    async def test_fiscal_years_of_one_grant_are_merged(self, adapter):
        data = copy.deepcopy(fx.SEARCH_MECFS)
        older = copy.deepcopy(data["results"][0])
        older["fiscal_year"] = 2024
        older["appl_id"] = 1
        older["project_num"] = "1R01NS131967-01"
        data["results"].append(older)
        ctx, _ = patched(adapter, data)
        with ctx:
            results = await adapter.search_concepts("myalgic encephalomyelitis", limit=20)
        ids = [c.primary_id for c in results]
        assert ids.count("R01NS131967") == 1
        merged = next(c for c in results if c.primary_id == "R01NS131967")
        applications = merged.source_data[KnowledgeSource.NIHREPORTER]["applications"]
        assert [a["fiscal_year"] for a in applications] == [2026, 2024]

    @pytest.mark.asyncio
    async def test_search_projects_options(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_RECOVER_2023)
        with ctx:
            results = await adapter.search_projects(
                "long covid RECOVER", 3, fiscal_years=[2023], sort="award_amount"
            )
        sent = body(mock)
        assert sent["criteria"]["fiscal_years"] == [2023]
        assert sent["sort_field"] == "award_amount"
        assert [c.primary_id for c in results] == ["UG3OD023305", "U54GM104940", "U54GM115516"]
        categories = results[0].source_data[KnowledgeSource.NIHREPORTER]["spending_categories"]
        assert "Coronaviruses" in categories
        assert "rcdc:Clinical Research" in results[0].categories
        ctx, mock = patched(adapter, fx.SEARCH_RECOVER_2023)
        with ctx:
            await adapter.search_projects("long covid", 3, sort="relevance")
        assert "sort_field" not in body(mock)

    @pytest.mark.asyncio
    async def test_empty_and_invalid_queries_make_no_request(self, adapter):
        ctx, mock = patched(adapter, fx.SEARCH_MECFS)
        with ctx:
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("   ", 5) == []
            assert await adapter.search_concepts("fatigue", 0) == []
            assert await adapter.search_projects("fatigue", -1) == []
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_hits_and_errors(self, adapter):
        ctx, _ = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.search_concepts("zzzz", 5) == []
        ctx, _ = patched(adapter, RuntimeError("down"))
        with ctx:
            assert await adapter.search_concepts("fatigue", 5) == []
        ctx, _ = patched(adapter, ["not", "a", "dict"])
        with ctx:
            assert await adapter.search_concepts("fatigue", 5) == []
        ctx, _ = patched(adapter, {"results": "nope"})
        with ctx:
            assert await adapter.search_concepts("fatigue", 5) == []

    @pytest.mark.asyncio
    async def test_records_without_core_or_title_are_skipped(self, adapter):
        data = {
            "results": [
                {"project_title": "No ids", "appl_id": 1},
                {"core_project_num": "R01AI000001", "project_num": "5R01AI000001-01"},
                "junk",
                {"project_num": "5R01AI000002-01", "project_title": "Core derived from number"},
            ]
        }
        ctx, _ = patched(adapter, data)
        with ctx:
            results = await adapter.search_concepts("anything", 5)
        assert [c.primary_id for c in results] == ["R01AI000002"]

    @pytest.mark.asyncio
    async def test_identifier_query_resolves_to_details(self, adapter):
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850)
        with ctx:
            results = await adapter.search_concepts(CORE, limit=5)
        assert [c.primary_id for c in results] == [CORE]
        assert body(mock)["criteria"] == {"project_nums": [CORE]}
        ctx, _ = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.search_concepts("R01XX999999", 5) == []

    @pytest.mark.asyncio
    async def test_bare_number_is_searched_as_text(self, adapter):
        ctx, mock = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            await adapter.search_concepts("2019", 5)
        assert "advanced_text_search" in body(mock)["criteria"]


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_by_core_number(self, adapter):
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850)
        with ctx:
            concept = await adapter.get_concept_details(CORE)
        assert mock.await_count == 1
        sent = body(mock)
        assert sent["criteria"] == {"project_nums": [CORE]}
        assert "Terms" not in sent["include_fields"] and "PrefTerms" in sent["include_fields"]
        assert concept.primary_id == CORE
        assert concept.concept_type == ConceptType.STUDY
        assert (
            concept.primary_label == "Long COVID as a putative subtype of chronic fatigue syndrome"
        )
        assert concept.semantic_types == ["R01"]
        assert concept.definitions and "SARS-CoV-2" in concept.definitions[0]
        assert any(i.identifier == "APPL:11391125" for i in concept.identifiers)
        data = concept.source_data[KnowledgeSource.NIHREPORTER]
        assert data["core_project_num"] == CORE
        assert data["project_num"] == "5R01AI170850-05"  # FY2026 base award, not the S1 supplement
        assert data["fiscal_year"] == 2026
        assert data["award_amount"] == 348246
        assert data["institute"]["abbreviation"] == "NIAID"
        assert data["organization"]["name"] == "MASSACHUSETTS GENERAL HOSPITAL"
        assert data["project_start_date"] == "2022-08-18"
        assert [a["project_num"] for a in data["applications"]] == [
            "5R01AI170850-05",
            "5R01AI170850-04",
            "3R01AI170850-04S1",
        ]

    @pytest.mark.asyncio
    async def test_empty_fields_fall_back_to_earlier_fiscal_year(self, adapter):
        # the FY2026 record has no RCDC categories yet; FY2025 does
        ctx, _ = patched(adapter, fx.PROJECTS_R01AI170850)
        with ctx:
            concept = await adapter.get_concept_details(CORE)
        data = concept.source_data[KnowledgeSource.NIHREPORTER]
        assert "Chronic Fatigue Syndrome (ME/CFS)" in data["spending_categories"]
        assert (
            "Post-Acute Sequelae of SARS-CoV-2 infection (PASC) including Long COVID"
            in (data["spending_categories"])
        )
        assert data["terms"][0] == "2019-nCoV"

    @pytest.mark.asyncio
    async def test_only_names_of_investigators_are_kept(self, adapter):
        ctx, _ = patched(adapter, fx.PROJECTS_R01AI170850)
        with ctx:
            concept = await adapter.get_concept_details(CORE)
        pis = concept.source_data[KnowledgeSource.NIHREPORTER]["principal_investigators"]
        assert pis and set(pis[0]) == {"name", "is_contact_pi"}
        assert pis[0]["name"].startswith("Test Investigator")
        dumped = str(concept.source_data)
        assert "profile_id" not in dumped and "program_officers" not in dumped

    @pytest.mark.asyncio
    async def test_details_by_full_project_number_resolves_the_core_first(self, adapter):
        ctx, mock = patched(adapter, fx.PROJECT_BY_FULL_NUMBER, fx.PROJECTS_R01AI170850)
        with ctx:
            concept = await adapter.get_concept_details("5R01AI170850-05")
        assert mock.await_count == 2
        assert body(mock, 0)["criteria"] == {"project_nums": ["5R01AI170850-05"]}
        assert body(mock, 1)["criteria"] == {"project_nums": [CORE]}
        assert concept.primary_id == CORE

    @pytest.mark.asyncio
    async def test_details_by_application_id(self, adapter):
        ctx, mock = patched(adapter, fx.PROJECT_BY_FULL_NUMBER, fx.PROJECTS_R01AI170850)
        with ctx:
            concept = await adapter.get_concept_details("APPL:11391125")
        assert body(mock, 0)["criteria"] == {"appl_ids": [11391125]}
        assert concept.primary_id == CORE

    @pytest.mark.asyncio
    async def test_unknown_and_invalid_ids(self, adapter):
        ctx, mock = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.get_concept_details("R01XX999999") is None
            assert await adapter.get_concept_details("5R01XX999999-01") is None
            assert await adapter.get_concept_details("99999999") is None
        assert mock.await_count == 3
        ctx, mock = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.get_concept_details("not an id") is None
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("*R01AI170850*") is None
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_core_without_number_in_response_and_foreign_records(self, adapter):
        no_core = {"results": [{"project_num": "garbage", "appl_id": 1}]}
        ctx, _ = patched(adapter, no_core)
        with ctx:
            assert await adapter.get_concept_details("5R01AI170850-05") is None
        other = {"results": [{"core_project_num": "R01AI000001", "project_title": "Other"}]}
        ctx, _ = patched(adapter, other)
        with ctx:
            assert await adapter.get_concept_details(CORE) is None  # records of another grant

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, adapter):
        ctx, _ = patched(adapter, RuntimeError("HTTP 400 Invalid project number"))
        with ctx:
            assert await adapter.get_concept_details(CORE) is None

    @pytest.mark.asyncio
    async def test_record_without_title_gives_no_concept(self, adapter):
        record = copy.deepcopy(fx.PROJECTS_R01AI170850["results"][0])
        record["project_title"] = " "
        ctx, _ = patched(adapter, {"results": [record]})
        with ctx:
            assert await adapter.get_concept_details(CORE) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships(self, adapter):
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850, fx.PUBLICATIONS_R01AI170850)
        with ctx:
            rels = await adapter.get_relationships(CORE)
        assert url(mock, 1) == nr.PUBLICATIONS_URL
        assert body(mock, 1) == {
            "criteria": {"core_project_nums": [CORE]},
            "offset": 0,
            "limit": nr.DEFAULT_PUBLICATION_LIMIT,
        }
        by_label: dict[str, list[dict]] = {}
        for rel in rels:
            assert rel["source"] == "NIHREPORTER"
            by_label.setdefault(rel["relation_label"], []).append(rel)
        assert [r["related_id"] for r in by_label["has_publication"]] == [
            "PMID:39962082",
            "PMID:40399555",
            "PMID:37982563",
            "PMID:38413574",
            "PMID:37301713",
        ]
        funder = by_label["funded_by"][0]
        assert funder["related_id"] == "NIHREPORTER:IC:AI"
        assert funder["related_name"] == "National Institute of Allergy and Infectious Diseases"
        assert funder["administering"] is True
        names = {r["related_name"] for r in by_label["has_spending_category"]}
        assert "Chronic Fatigue Syndrome (ME/CFS)" in names
        assert by_label["has_spending_category"][0]["related_id"].startswith("NIHREPORTER:RCDC:")
        assert by_label["has_term"][0]["related_id"] == "NIHREPORTER:TERM:2019-nCoV"
        org = by_label["conducted_at"][0]
        assert org["related_name"] == "MASSACHUSETTS GENERAL HOSPITAL"
        assert org["related_id"].startswith("NIHREPORTER:ORG:")

    @pytest.mark.asyncio
    async def test_co_funding_institutes_and_term_cap(self, adapter):
        data = copy.deepcopy(fx.PROJECTS_R01AI170850)
        record = data["results"][0]
        record["agency_ic_fundings"].append(
            {"fy": 2026, "code": "NS", "name": "NINDS", "abbreviation": "NINDS"}
        )
        record["agency_ic_fundings"].append({"fy": 2026, "code": "AI"})  # already administering
        record["agency_ic_fundings"].append("junk")
        record["pref_terms"] = ";".join(f"term{i}" for i in range(80))
        ctx, _ = patched(adapter, data, fx.EMPTY_RESULT)
        with ctx:
            rels = await adapter.get_relationships(CORE)
        funders = [r for r in rels if r["relation_label"] == "funded_by"]
        assert [(r["related_id"], r["administering"]) for r in funders] == [
            ("NIHREPORTER:IC:AI", True),
            ("NIHREPORTER:IC:NS", False),
        ]
        assert len([r for r in rels if r["relation_label"] == "has_term"]) == nr.MAX_TERMS
        assert not [r for r in rels if r["relation_label"] == "has_publication"]

    @pytest.mark.asyncio
    async def test_publication_limit_and_dedup(self, adapter):
        pubs = copy.deepcopy(fx.PUBLICATIONS_R01AI170850)
        pubs["results"].append(dict(pubs["results"][0], applid=1))  # same PMID, another year
        pubs["results"].append({"coreproject": "OTHER", "pmid": 1, "applid": 2})
        pubs["results"].append({"coreproject": CORE, "pmid": None, "applid": 2})
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850, pubs)
        with ctx:
            rels = await adapter.get_relationships(CORE, limit=3)
        assert body(mock, 1)["limit"] == 3
        assert [r["related_id"] for r in rels if r["relation_label"] == "has_publication"] == [
            "PMID:39962082",
            "PMID:40399555",
            "PMID:37982563",
        ]
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850)
        with ctx:
            rels = await adapter.get_relationships(CORE, limit=0)
        assert mock.await_count == 1
        assert rels
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850, fx.PUBLICATIONS_R01AI170850)
        with ctx:
            await adapter.get_relationships(CORE, limit=10_000)
        assert body(mock, 1)["limit"] == nr.MAX_PUBLICATION_LIMIT

    @pytest.mark.asyncio
    async def test_failed_publication_request_keeps_structural_edges(self, adapter):
        ctx, _ = patched(adapter, fx.PROJECTS_R01AI170850, RuntimeError("timeout"))
        with ctx:
            rels = await adapter.get_relationships(CORE)
        labels = {r["relation_label"] for r in rels}
        assert "funded_by" in labels and "has_publication" not in labels

    @pytest.mark.asyncio
    async def test_unknown_invalid_and_error(self, adapter):
        ctx, _ = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.get_relationships("R01XX999999") == []
        ctx, mock = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.get_relationships("nonsense") == []
        mock.assert_not_called()
        ctx, _ = patched(adapter, RuntimeError("down"))
        with ctx:
            assert await adapter.get_relationships(CORE) == []

    @pytest.mark.asyncio
    async def test_record_with_sparse_structure(self, adapter):
        sparse = {
            "results": [
                {
                    "core_project_num": CORE,
                    "project_num": "5R01AI170850-05",
                    "project_title": "Sparse",
                    "fiscal_year": 2026,
                    "agency_ic_admin": {"code": "AI"},
                    "organization": {"org_name": "SOMEWHERE"},
                }
            ]
        }
        ctx, _ = patched(adapter, sparse, fx.EMPTY_RESULT)
        with ctx:
            rels = await adapter.get_relationships(CORE)
        assert [r["relation_label"] for r in rels] == ["funded_by"]  # org has no id: skipped
        assert rels[0]["related_name"] == "AI"


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        ctx, mock = patched(adapter, fx.PROJECTS_R01AI170850, fx.PUBLICATIONS_R01AI170850)
        with ctx:
            mappings = await adapter.get_mappings(CORE)
        assert url(mock, 1) == nr.PUBLICATIONS_URL
        assert all(m["fromId"] == CORE and m["fromSource"] == "NIHREPORTER" for m in mappings)
        assert {
            "fromId",
            "toId",
            "fromSource",
            "toSource",
            "mappingType",
            "confidence",
        } == set(mappings[0])
        pairs = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("NIH_PROJECT_NUMBER", "5R01AI170850-05") in pairs
        assert ("NIH_PROJECT_NUMBER", "3R01AI170850-04S1") in pairs
        assert ("NIH_APPLICATION_ID", "11391125") in pairs
        assert ("PMID", "39962082") in pairs
        assert len(pairs) == len(mappings)  # de-duplicated
        kinds = {m["toSource"]: m["mappingType"] for m in mappings}
        assert kinds["NIH_APPLICATION_ID"] == "exact" and kinds["PMID"] == "related"

    @pytest.mark.asyncio
    async def test_mappings_from_full_number_and_edge_cases(self, adapter):
        ctx, mock = patched(
            adapter,
            fx.PROJECT_BY_FULL_NUMBER,
            fx.PROJECTS_R01AI170850,
            fx.PUBLICATIONS_R01AI170850,
        )
        with ctx:
            mappings = await adapter.get_mappings("5R01AI170850-05")
        assert mock.await_count == 3
        assert mappings[0]["fromId"] == CORE
        ctx, _ = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.get_mappings("R01XX999999") == []
        ctx, mock = patched(adapter, fx.EMPTY_RESULT)
        with ctx:
            assert await adapter.get_mappings("garbage") == []
        mock.assert_not_called()
        ctx, _ = patched(adapter, RuntimeError("down"))
        with ctx:
            assert await adapter.get_mappings(CORE) == []

    @pytest.mark.asyncio
    async def test_mappings_skip_empty_values(self, adapter):
        data = {
            "results": [
                {"core_project_num": CORE, "project_title": "T", "project_num": None, "appl_id": 5}
            ]
        }
        ctx, _ = patched(adapter, data, fx.EMPTY_RESULT)
        with ctx:
            mappings = await adapter.get_mappings(CORE)
        assert [(m["toSource"], m["toId"]) for m in mappings] == [("NIH_APPLICATION_ID", "5")]


class TestHelpers:
    def test_latest_prefers_newest_year_then_base_award(self):
        records = [
            {"appl_id": 1, "project_num": "5R01AI170850-04", "fiscal_year": 2025},
            {"appl_id": 3, "project_num": "3R01AI170850-05S1", "fiscal_year": 2026},
            {"appl_id": 2, "project_num": "5R01AI170850-05", "fiscal_year": 2026},
        ]
        assert NIHReporterAdapter._latest(records)["appl_id"] == 2

    def test_latest_fills_missing_fields_from_earlier_years(self):
        records = [
            {"appl_id": 2, "fiscal_year": 2026, "pref_terms": None},
            {"appl_id": 1, "fiscal_year": 2025, "pref_terms": "a;b"},
        ]
        merged = NIHReporterAdapter._latest(records)
        assert merged["appl_id"] == 2 and merged["pref_terms"] == "a;b"
        assert merged["abstract_text"] is None

    def test_split_helpers(self):
        assert NIHReporterAdapter._categories({"spending_categories_desc": "A; B;; A"}) == [
            "A",
            "B",
        ]
        assert NIHReporterAdapter._categories({}) == []
        assert NIHReporterAdapter._terms({"pref_terms": "x;y; x"}) == ["x", "y"]
        assert NIHReporterAdapter._terms({}) == []
        assert nr._clean_date("2024-01-02T00:00:00") == "2024-01-02"
        assert nr._clean_date(None) is None

    def test_conversion_error_returns_none(self, adapter):
        assert adapter._project_to_concept("R01AI170850", []) is None
        assert (
            adapter._project_to_concept(
                "R01AI170850", [{"project_title": "T", "fiscal_year": "x"}]
            )
            is None
        )


class TestUnexpectedErrors:
    """Interface methods never raise, even when an internal helper does."""

    @pytest.mark.asyncio
    async def test_methods_swallow_internal_errors(self, adapter):
        boom = AsyncMock(side_effect=ValueError("boom"))
        with patch.object(adapter, "_search_projects", new=boom):
            assert await adapter.search_projects("fatigue", 5) == []
        with patch.object(adapter, "search_projects", new=boom):
            assert await adapter.search_concepts("fatigue", 5) == []
        with patch.object(adapter, "_project_records", new=boom):
            assert await adapter.get_concept_details(CORE) is None
            assert await adapter.get_relationships(CORE) == []
            assert await adapter.get_mappings(CORE) == []


class TestThrottling:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        monkeypatch.setattr(nr, "MIN_REQUEST_INTERVAL", 1.0)
        sleeps: list[float] = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        clock = iter([100.0, 100.0, 100.2, 100.2, 105.0, 105.0])
        # patch the module's own references only: the event loop uses the real ones
        monkeypatch.setattr(nr, "asyncio", SimpleNamespace(Lock=asyncio.Lock, sleep=fake_sleep))
        monkeypatch.setattr(nr, "time", SimpleNamespace(monotonic=lambda: next(clock)))
        ctx, mock = patched(adapter, fx.EMPTY_RESULT, fx.EMPTY_RESULT, fx.EMPTY_RESULT)
        with ctx:
            await adapter._post(nr.PROJECTS_URL, {})
            await adapter._post(nr.PROJECTS_URL, {})  # 0.2 s after the first: must wait
            await adapter._post(nr.PROJECTS_URL, {})  # 4.8 s after the second: no wait
        assert mock.await_count == 3
        assert len(sleeps) == 1
        assert 0.7 < sleeps[0] <= nr.MIN_REQUEST_INTERVAL + 1e-6
