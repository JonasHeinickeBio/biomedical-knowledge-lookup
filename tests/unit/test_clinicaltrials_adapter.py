"""Unit tests for ClinicalTrialsAdapter (HTTP mocked with trimmed real responses)."""

from unittest.mock import AsyncMock, patch

import pytest
from fixtures import clinicaltrials_responses as fx

from knowledge_lookup.adapters.clinicaltrials_adapter import ClinicalTrialsAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter(lookup_config):
    a = ClinicalTrialsAdapter(lookup_config)
    a._min_interval = 0.0
    return a


def _mock(value=None, side_effect=None):
    return patch.object(
        ClinicalTrialsAdapter,
        "_make_request",
        new=AsyncMock(return_value=value, side_effect=side_effect),
    )


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CLINICALTRIALS
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("NCT07753122", "NCT07753122"),
            ("nct07753122", "NCT07753122"),
            ("ClinicalTrials:NCT07753122", "NCT07753122"),
            ("NCT:NCT07753122", "NCT07753122"),
            (" ctgov:nct07753122 ", "NCT07753122"),
            ("NCT123", None),
            ("", None),
            ("PMID:123", None),
        ],
    )
    def test_normalize_nct(self, raw, expected):
        assert ClinicalTrialsAdapter._normalize_nct(raw) == expected

    @pytest.mark.asyncio
    async def test_throttle_waits_between_requests(self, lookup_config):
        a = ClinicalTrialsAdapter(lookup_config)
        a._min_interval = 0.05
        with _mock({}) as m, patch("asyncio.sleep", new=AsyncMock()) as sleep:
            await a._get("/studies", {})
            await a._get("/studies", {})
        assert m.await_count == 2
        sleep.assert_awaited()


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_concepts_free_text(self, adapter):
        with _mock(fx.SEARCH_PAGE_1) as m:
            concepts = await adapter.search_concepts("long covid", limit=2)
        url, params = m.await_args.args[0], m.await_args.args[1]
        assert url == "https://clinicaltrials.gov/api/v2/studies"
        assert params["query.term"] == "long covid"
        assert params["pageSize"] == 2
        assert "NCTId" in params["fields"] and "ConditionMeshId" in params["fields"]
        assert [c.primary_id for c in concepts] == ["NCT07770022", "NCT07298005"]
        assert concepts[0].concept_type == ConceptType.OBSERVATIONAL_STUDY
        assert concepts[1].concept_type == ConceptType.CLINICAL_TRIAL
        assert concepts[0].sources == [KnowledgeSource.CLINICALTRIALS]

    @pytest.mark.asyncio
    async def test_search_by_condition_and_status(self, adapter):
        with _mock(fx.SEARCH_PAGE_2) as m:
            concepts = await adapter.search_by_condition(
                "ME/CFS", limit=5, status=["recruiting", "NOT_YET_RECRUITING"]
            )
        params = m.await_args.args[1]
        assert params["query.cond"] == "ME/CFS"
        assert params["filter.overallStatus"] == "RECRUITING,NOT_YET_RECRUITING"
        assert "query.term" not in params
        assert len(concepts) == 2

    @pytest.mark.asyncio
    async def test_search_by_intervention_single_status(self, adapter):
        with _mock(fx.SEARCH_PAGE_2) as m:
            await adapter.search_by_intervention("naltrexone", limit=1, status="RECRUITING")
        params = m.await_args.args[1]
        assert params["query.intr"] == "naltrexone"
        assert params["filter.overallStatus"] == "RECRUITING"
        assert params["pageSize"] == 1

    @pytest.mark.asyncio
    async def test_search_paginates_with_token_and_dedups(self, adapter):
        with _mock(side_effect=[fx.SEARCH_PAGE_1, fx.SEARCH_PAGE_2]) as m:
            concepts = await adapter.search_concepts("covid", limit=10)
        assert m.await_count == 2
        assert m.await_args_list[1].args[1]["pageToken"] == fx.SEARCH_PAGE_1["nextPageToken"]
        # NCT07298005 appears on both pages -> only once
        assert [c.primary_id for c in concepts] == ["NCT07770022", "NCT07298005", "NCT07753122"]

    @pytest.mark.asyncio
    async def test_search_stops_when_limit_reached(self, adapter):
        with _mock(fx.SEARCH_PAGE_1) as m:
            concepts = await adapter.search_concepts("covid", limit=1)
        assert m.await_count == 1 and len(concepts) == 1

    @pytest.mark.asyncio
    async def test_search_page_size_capped_and_pages_capped(self, adapter):
        endless = {"studies": [], "nextPageToken": "t"}
        with _mock(endless) as m:
            await adapter.search_concepts("covid", limit=500)
        assert m.await_args_list[0].args[1]["pageSize"] == 100
        assert m.await_count == 5  # _MAX_PAGES

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("  ", 5), ("covid", 0), ("covid", -1)])
    async def test_search_invalid_input(self, adapter, query, limit):
        with _mock({"studies": []}) as m:
            assert await adapter.search_concepts(query, limit) == []
        m.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_empty_malformed_error(self, adapter):
        with _mock({"studies": []}):
            assert await adapter.search_concepts("zzz") == []
        with _mock(["not a dict"]):
            assert await adapter.search_concepts("zzz") == []
        with _mock({"studies": None}):
            assert await adapter.search_concepts("zzz") == []
        with _mock(side_effect=RuntimeError("down")):
            assert await adapter.search_concepts("zzz") == []

    @pytest.mark.asyncio
    async def test_search_skips_unusable_studies(self, adapter):
        page = {"studies": [{"protocolSection": {}}, "junk", fx.STUDY_POST_COVID_DRUG]}
        with _mock(page):
            concepts = await adapter.search_concepts("covid")
        assert [c.primary_id for c in concepts] == ["NCT07298005"]


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_fields(self, adapter):
        with _mock(fx.STUDY_ME_CFS_HYDROGEN) as m:
            concept = await adapter.get_concept_details("ClinicalTrials:nct07753122")
        assert m.await_args.args[0].endswith("/studies/NCT07753122")
        assert concept.primary_id == "NCT07753122"
        assert concept.primary_label.startswith("Controlled Trial of Hydrogen Water")
        assert concept.concept_type == ConceptType.CLINICAL_TRIAL
        assert concept.definitions[0].startswith("This is a 16-week")
        assert concept.synonyms == [
            "Randomized Controlled Trial of Moderate Dose Hydrogen Water as a Treatment for "
            "ME/CFS",
            "ME/CFS",
        ]
        assert "status:RECRUITING" in concept.categories
        assert "phase:NA" in concept.categories
        assert "condition:Chronic Fatigue Syndrome (CFS)" in concept.categories
        assert concept.semantic_types == ["INTERVENTIONAL"]
        data = concept.source_data[KnowledgeSource.CLINICALTRIALS]
        assert data["conditions"] == ["Chronic Fatigue Syndrome (CFS)"]
        assert data["phases"] == ["NA"]
        assert data["status"] == "RECRUITING"
        assert data["enrollment"] == 80 and data["enrollment_type"] == "ESTIMATED"
        assert data["start_date"] == "2026-08-15" and data["completion_date"] == "2027-07"
        assert data["sponsor"] == "Fred Friedberg"
        assert data["interventions"][0]["type"] == "DIETARY_SUPPLEMENT"
        assert data["condition_mesh"] == [{"id": "D015673", "term": "Fatigue Syndrome, Chronic"}]
        assert data["url"] == "https://clinicaltrials.gov/study/NCT07753122"

    @pytest.mark.asyncio
    async def test_details_other_study_type(self, adapter):
        with _mock(fx.STUDY_EXPANDED_ACCESS):
            concept = await adapter.get_concept_details("NCT01111111")
        assert concept.concept_type == ConceptType.CLINICAL_STUDY

    @pytest.mark.asyncio
    async def test_details_invalid_missing_and_error(self, adapter):
        with _mock(fx.STUDY_ME_CFS_HYDROGEN) as m:
            assert await adapter.get_concept_details("not-an-nct") is None
        m.assert_not_awaited()
        with _mock({"detail": "no protocolSection"}):
            assert await adapter.get_concept_details("NCT07753122") is None
        with _mock(["list"]):
            assert await adapter.get_concept_details("NCT07753122") is None
        with _mock(side_effect=RuntimeError("404")):
            assert await adapter.get_concept_details("NCT01234567") is None
        # a record without id/title cannot become a concept
        with _mock({"protocolSection": {"identificationModule": {"nctId": "NCT07753122"}}}):
            assert await adapter.get_concept_details("NCT07753122") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships(self, adapter):
        with _mock(fx.STUDY_ME_CFS_HYDROGEN):
            rels = await adapter.get_relationships("NCT07753122")
        conds = [r for r in rels if r["relation_label"] == "studies_condition"]
        ivs = [r for r in rels if r["relation_label"] == "tests_intervention"]
        assert [(r["related_id"], r.get("derived")) for r in conds] == [
            ("Chronic Fatigue Syndrome (CFS)", None),
            ("MESH:D015673", True),
        ]
        assert conds[1]["related_name"] == "Fatigue Syndrome, Chronic"
        assert [r["related_id"] for r in ivs] == [
            "Placebo condition",
            "Molecular hydrogen (magnesium tablet) 3x a day",
            "MESH:D006859",
        ]
        assert ivs[0]["related_type"] == "DIETARY_SUPPLEMENT"
        assert ivs[0]["arm_groups"] == ["Placebo condition"]
        assert ivs[0]["description"].startswith("16 week")
        assert ivs[2]["related_type"] == "intervention" and ivs[2]["derived"] is True
        assert all(r["source"] == "ClinicalTrials.gov" for r in rels)

    @pytest.mark.asyncio
    async def test_relationships_without_interventions_dedup(self, adapter):
        study = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT07770022", "briefTitle": "x"},
                "conditionsModule": {"conditions": ["Long Covid", "Long Covid", ""]},
                "armsInterventionsModule": {
                    "interventions": [{"name": "Rest"}, {"name": "Rest"}, {"type": "DRUG"}]
                },
            }
        }
        with _mock(study):
            rels = await adapter.get_relationships("NCT07770022")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [
            ("studies_condition", "Long Covid"),
            ("tests_intervention", "Rest"),
        ]
        assert rels[1]["related_type"] == "OTHER"

    @pytest.mark.asyncio
    async def test_relationships_edge_cases(self, adapter):
        assert await adapter.get_relationships("garbage") == []
        with _mock(side_effect=RuntimeError("x")):
            assert await adapter.get_relationships("NCT07753122") == []
        with (
            patch.object(ClinicalTrialsAdapter, "_parse_study", side_effect=ValueError("bad")),
            _mock(fx.STUDY_ME_CFS_HYDROGEN),
        ):
            assert await adapter.get_relationships("NCT07753122") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings(self, adapter):
        with _mock(fx.STUDY_ME_CFS_HYDROGEN):
            maps = await adapter.get_mappings("NCT07753122")
        assert maps == [
            {
                "fromId": "NCT07753122",
                "toId": "MESH:D015673",
                "fromSource": "ClinicalTrials.gov",
                "toSource": "MeSH",
                "mappingType": "condition_mesh",
                "confidence": 0.8,
            },
            {
                "fromId": "NCT07753122",
                "toId": "MESH:D006859",
                "fromSource": "ClinicalTrials.gov",
                "toSource": "MeSH",
                "mappingType": "intervention_mesh",
                "confidence": 0.8,
            },
        ]

    @pytest.mark.asyncio
    async def test_mappings_edge_cases(self, adapter):
        assert await adapter.get_mappings("nope") == []
        with _mock(side_effect=RuntimeError("x")):
            assert await adapter.get_mappings("NCT07753122") == []
        with (
            patch.object(ClinicalTrialsAdapter, "_parse_study", side_effect=ValueError("bad")),
            _mock(fx.STUDY_ME_CFS_HYDROGEN),
        ):
            assert await adapter.get_mappings("NCT07753122") == []
