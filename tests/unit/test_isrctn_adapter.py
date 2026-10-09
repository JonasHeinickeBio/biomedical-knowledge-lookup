"""Unit tests for ISRCTNAdapter (HTTP mocked with trimmed real registry responses)."""

import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

import pytest
from fixtures import isrctn_responses as fx

from knowledge_lookup.adapters.isrctn_adapter import ISRCTNAdapter
from knowledge_lookup.models import KnowledgeSource

pytestmark = pytest.mark.unit

TODAY = "2026-10-09"


@pytest.fixture
def adapter(lookup_config):
    a = ISRCTNAdapter(lookup_config)
    a._min_interval = 0.0
    with patch.object(ISRCTNAdapter, "_today", staticmethod(lambda: TODAY)):
        yield a


def _mock(value=None, side_effect=None):
    return patch.object(
        ISRCTNAdapter,
        "_make_request_text",
        new=AsyncMock(return_value=value, side_effect=side_effect),
    )


def _data(concept):
    return concept.source_data[KnowledgeSource.ISRCTN]


def _trial_xml(body="", title="A title", isrctn="ISRCTN11111111", trial_attrs=True):
    attrs = f' publicIdentifierCanonical="{isrctn}"' if trial_attrs else ""
    return (
        '<allTrials totalCount="1" xmlns="http://www.67bricks.com/isrctn"><fullTrial>'
        f"<trial{attrs}><isrctn>11111111</isrctn>"
        f"<trialDescription><title>{title}</title>{body}</trialDescription>"
        "</trial></fullTrial></allTrials>"
    )


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ISRCTN
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ISRCTN54285094", "ISRCTN54285094"),
            ("isrctn54285094", "ISRCTN54285094"),
            ("ISRCTN:54285094", "ISRCTN54285094"),
            (" ISRCTN 54285094 ", "ISRCTN54285094"),
            ("ISRCTN-54285094", "ISRCTN54285094"),
            ("54285094", None),
            ("ISRCTN5428509", None),
            ("ISRCTN542850941", None),
            ("NCT01234567", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_id(self, raw, expected):
        assert ISRCTNAdapter._normalize_id(raw) == expected

    def test_today_is_an_iso_date(self):
        assert len(ISRCTNAdapter._today()) == 10

    @pytest.mark.asyncio
    async def test_throttle_waits_between_requests(self, lookup_config):
        a = ISRCTNAdapter(lookup_config)
        a._min_interval = 0.5
        with _mock(fx.EMPTY_RESULT) as m, patch("asyncio.sleep", new=AsyncMock()) as sleep:
            await a._query("fatigue", 5)
            await a._query("fatigue", 5)
        assert m.await_count == 2
        sleep.assert_awaited_once()
        assert 0 < sleep.await_args.args[0] <= 0.5 + 1e-6


class TestStatus:
    @pytest.mark.parametrize(
        "start,end,start_override,override,expected",
        [
            ("2027-01-11", "2027-07-31", "", "", ("Not yet recruiting", True)),
            ("2026-05-01", "2028-01-01", "", "", ("Recruiting", True)),
            ("2026-05-01", "", "", "", ("Recruiting", True)),
            ("2024-01-01", "2025-12-31", "", "", ("No longer recruiting", True)),
            ("2026-10-09", "2026-10-09", "", "", ("Recruiting", True)),  # boundaries are inclusive
            ("2024-01-01", "2025-12-31", "", "Stopped", ("Stopped", False)),
            ("2027-01-01", "", "Suspended", "", ("Suspended", False)),
            ("", "", "", "", (None, True)),
        ],
    )
    def test_derive_status(self, start, end, start_override, override, expected):
        assert (
            ISRCTNAdapter._derive_status(start, end, start_override, override, TODAY) == expected
        )


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_parameters_and_results(self, adapter):
        with _mock(fx.SEARCH_MECFS) as m:
            concepts = await adapter.search_concepts("  ME/CFS ", limit=5)
        args = m.await_args.args
        assert args[0] == "https://www.isrctn.com/api/query/format/default"
        assert args[1] == {"q": "ME/CFS", "limit": 5}
        assert [c.primary_id for c in concepts] == [
            "ISRCTN15375673",
            "ISRCTN16025168",
            "ISRCTN16132141",
        ]
        first = concepts[0]
        assert first.concept_type == "OBSERVATIONAL_STUDY"
        assert concepts[1].concept_type == "CLINICAL_TRIAL"
        assert first.primary_label.startswith("Long Covid and myalgic encephalomyelitis")
        assert first.sources == [KnowledgeSource.ISRCTN]
        assert first.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_concept_fields(self, adapter):
        with _mock(fx.SEARCH_MECFS):
            concepts = await adapter.search_concepts("ME/CFS")
        first = concepts[0]
        data = _data(first)
        assert data["url"] == "https://www.isrctn.com/ISRCTN15375673"
        assert data["status"] == "Recruiting" and data["status_derived"] is True
        assert data["recruitment_start"] == "2026-05-01"
        assert data["study_design"]["primary"] == "Observational"
        assert data["study_design"]["secondary"] == "Cohort study"
        assert "United Kingdom" in data["countries"]
        assert data["sponsors"][0]["name"] == "University of Leeds"
        assert "status:Recruiting" in first.categories
        assert any(c.startswith("condition:Long Covid") for c in first.categories)
        assert first.semantic_types == ["Observational", "Cohort study"]
        assert first.definitions  # plain-English summary or hypothesis
        assert data["primary_outcomes"] and data["primary_outcomes"][0]["measure"]

    @pytest.mark.asyncio
    async def test_contact_details_are_not_extracted(self, adapter):
        with _mock(fx.RECORD_GEFAPIXANT):
            (concept,) = await adapter.search_concepts("gefapixant")
        text = repr(_data(concept)).lower()
        assert "@" not in text and "telephone" not in text and "forename" not in text

    @pytest.mark.asyncio
    async def test_legacy_record_without_structured_outcomes(self, adapter):
        with _mock(fx.RECORD_PACE):
            (pace,) = await adapter.search_concepts("PACE")
        data = _data(pace)
        assert pace.synonyms and pace.synonyms[0].startswith("PACE: Pacing")
        assert data["status"] == "No longer recruiting"
        assert data["primary_outcomes"][0]["measure"].startswith("1. Is APT")
        assert data["target_enrolment"] == "600"
        assert data["publication_stage"] == "Results"
        assert "phase:Not Applicable" in pace.categories

    @pytest.mark.asyncio
    async def test_limit_slices_results_and_is_capped(self, adapter):
        with _mock(fx.SEARCH_MECFS) as m:
            concepts = await adapter.search_concepts("ME/CFS", limit=2)
            assert len(concepts) == 2
            await adapter.search_concepts("ME/CFS", limit=5000)
        assert m.await_args.args[1]["limit"] == 100

    @pytest.mark.asyncio
    async def test_duplicates_are_removed(self, adapter):
        doubled = (
            fx.RECORD_PACE.replace("</allTrials>", "")
            + fx.RECORD_PACE[fx.RECORD_PACE.index("<fullTrial>") :]
        )
        with _mock(doubled):
            concepts = await adapter.search_concepts("PACE", limit=10)
        assert [c.primary_id for c in concepts] == ["ISRCTN54285094"]

    @pytest.mark.asyncio
    async def test_empty_and_invalid_input(self, adapter):
        with _mock(fx.EMPTY_RESULT) as m:
            assert await adapter.search_concepts("zzzz") == []
            assert await adapter.search_concepts("") == []
            assert await adapter.search_concepts("   ") == []
            assert await adapter.search_concepts("fatigue", limit=0) == []
            assert await adapter.search_concepts(None) == []
        assert m.await_count == 1  # only the first query reached the API

    @pytest.mark.asyncio
    async def test_errors_return_empty(self, adapter):
        with _mock(side_effect=RuntimeError("down")):
            assert await adapter.search_concepts("fatigue") == []
        with _mock("<html>Internal server error</html>"):
            assert await adapter.search_concepts("fatigue") == []

    @pytest.mark.asyncio
    async def test_records_without_id_or_title_are_skipped(self, adapter):
        no_title = _trial_xml(title="")
        with _mock(no_title):
            assert await adapter.search_concepts("x") == []
        no_trial = (
            '<allTrials totalCount="1" xmlns="http://www.67bricks.com/isrctn">'
            "<fullTrial/></allTrials>"
        )
        with _mock(no_trial):
            assert await adapter.search_concepts("x") == []
        no_id = _trial_xml(trial_attrs=False)
        with _mock(no_id):
            (concept,) = await adapter.search_concepts("x")
        assert concept.primary_id == "ISRCTN11111111"  # rebuilt from <isrctn>

    @pytest.mark.asyncio
    async def test_study_design_fallbacks(self, adapter):
        other = _trial_xml().replace(
            "</trial>",
            "<trialDesign><primaryStudyDesign>Other</primaryStudyDesign></trialDesign></trial>",
        )
        with _mock(other):
            (concept,) = await adapter.search_concepts("x")
        assert concept.concept_type == "CLINICAL_STUDY"

    @pytest.mark.asyncio
    async def test_not_provided_summary_falls_back_to_hypothesis(self, adapter):
        body = (
            "<plainEnglishSummary>Not provided at time of registration</plainEnglishSummary>"
            "<studyHypothesis>Exercise reduces fatigue.</studyHypothesis>"
        )
        with _mock(_trial_xml(body)):
            (concept,) = await adapter.search_concepts("x")
        assert concept.definitions == ["Exercise reduces fatigue."]
        assert _data(concept)["summary"] == ""

    @pytest.mark.asyncio
    async def test_conversion_error_gives_none(self, adapter):
        assert adapter._convert_trial_to_concept({"isrctn": "ISRCTN1"}) is None


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_query_by_id(self, adapter):
        with _mock(fx.RECORD_PACE) as m:
            concept = await adapter.get_concept_details("ISRCTN:54285094")
        assert m.await_args.args[1] == {"q": "ISRCTN54285094", "limit": 3}
        assert concept.primary_id == "ISRCTN54285094"
        assert concept.primary_label.startswith("A randomised controlled trial of adaptive pacing")
        assert concept.concept_type == "CLINICAL_TRIAL"

    @pytest.mark.asyncio
    async def test_details_pick_the_exact_id(self, adapter):
        # the free-text query can also return records that merely mention the id
        with _mock(fx.SEARCH_MECFS):
            concept = await adapter.get_concept_details("ISRCTN16132141")
            assert concept.primary_id == "ISRCTN16132141"
            assert await adapter.get_concept_details("ISRCTN99999999") is None

    @pytest.mark.asyncio
    async def test_unknown_id_and_errors(self, adapter):
        with _mock(fx.EMPTY_RESULT):
            assert await adapter.get_concept_details("ISRCTN99999999") is None
        with _mock(side_effect=RuntimeError("down")):
            assert await adapter.get_concept_details("ISRCTN54285094") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", "NCT01234567", "54285094", "ISRCTN1"])
    async def test_invalid_ids_make_no_request(self, adapter, bad):
        with _mock(fx.EMPTY_RESULT) as m:
            assert await adapter.get_concept_details(bad) is None
            assert await adapter.get_relationships(bad) == []
            assert await adapter.get_mappings(bad) == []
        m.assert_not_awaited()


class TestRelationships:
    @pytest.mark.asyncio
    async def test_pace_relationships(self, adapter):
        with _mock(fx.RECORD_PACE):
            edges = await adapter.get_relationships("ISRCTN54285094")
        by_label: dict[str, list[dict]] = {}
        for e in edges:
            by_label.setdefault(e["relation_label"], []).append(e)
        assert [e["related_id"] for e in by_label["studies_condition"]] == [
            "Symptoms and general pathology",
            "Chronic fatigue syndrome (CFS)",
            "Mental and Behavioural Disorders",
        ]
        assert [e["related_type"] for e in by_label["studies_condition"]] == [
            "condition",
            "condition",
            "condition_category",
        ]
        assert by_label["studies_condition"][1]["derived"] is True
        (iv,) = by_label["tests_intervention"]
        assert iv["related_type"] == "Other" and iv["phase"] == "Not Applicable"
        assert len(iv["related_id"]) <= 120 and "\n" not in iv["related_id"]
        (sponsor,) = by_label["has_sponsor"]
        assert sponsor["related_id"].startswith("ROR:")
        assert sponsor["related_name"].startswith("Queen Mary University of London")
        assert len(by_label["funded_by"]) == 4
        assert all(e["source"] == "ISRCTN" for e in edges)
        assert {"relation_label", "related_id", "related_name", "source"} <= set(edges[0])

    @pytest.mark.asyncio
    async def test_drug_names_and_multiline_conditions(self, adapter):
        with _mock(fx.RECORD_CPMS_NCT):
            edges = await adapter.get_relationships("ISRCTN62918594")
        conditions = [e["related_id"] for e in edges if e["related_type"] == "condition"]
        assert "Bladder Cancer" in conditions and "Cervical Cancer" in conditions
        assert all("\n" not in c for c in conditions)
        drugs = [e for e in edges if e["relation_label"] == "tests_intervention"]
        assert [d["related_id"] for d in drugs] == ["HMBD-001"]
        assert drugs[0]["related_type"] == "Drug" and drugs[0]["description"]
        sponsor = next(e for e in edges if e["relation_label"] == "has_sponsor")
        assert sponsor["commercial_status"]

    @pytest.mark.asyncio
    async def test_sponsor_without_ror_uses_name(self, adapter):
        body = ""
        xml = (
            _trial_xml(body)
            .replace(
                "</trial>",
                "<parties><sponsorId>s1</sponsorId><funderId>f1</funderId><funderId>f2</funderId></parties></trial>",
            )
            .replace(
                "</fullTrial>",
                '<sponsor id="s1"><organisation>Acme Ltd</organisation>'
                "<commercialStatus>Commercial</commercialStatus></sponsor>"
                '<funder id="f1"><name>Wellcome</name></funder>'
                '<funder id="f2"><name/></funder></fullTrial>',
            )
        )
        with _mock(xml):
            edges = await adapter.get_relationships("ISRCTN11111111")
        assert [(e["relation_label"], e["related_id"]) for e in edges] == [
            ("has_sponsor", "Acme Ltd"),
            ("funded_by", "Wellcome"),
        ]

    @pytest.mark.asyncio
    async def test_intervention_without_text_or_duplicates(self, adapter):
        body = ""
        xml = _trial_xml(body).replace(
            "</trial>",
            "<interventions>"
            "<intervention><description/><interventionType>Other</interventionType></intervention>"
            "<intervention><description>Walk daily</description><interventionType/></intervention>"
            "<intervention><description>Walk daily</description><interventionType/></intervention>"
            "</interventions></trial>",
        )
        with _mock(xml):
            edges = await adapter.get_relationships("ISRCTN11111111")
        assert [(e["related_id"], e["related_type"]) for e in edges] == [("Walk daily", "Other")]

    @pytest.mark.asyncio
    async def test_failures(self, adapter):
        with _mock(fx.EMPTY_RESULT):
            assert await adapter.get_relationships("ISRCTN99999999") == []
        with (
            _mock(fx.RECORD_PACE),
            patch.object(ISRCTNAdapter, "_fetch", new=AsyncMock(return_value={"isrctn": "x"})),
        ):
            assert await adapter.get_relationships("ISRCTN54285094") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_registry_numbers(self, adapter):
        with _mock(fx.RECORD_CPMS_NCT):
            mappings = await adapter.get_mappings("ISRCTN62918594")
        got = {(m["toSource"], m["toId"]): m for m in mappings}
        assert got[("CLINICALTRIALS", "NCT05057013")]["mappingType"] == "same_study"
        assert got[("EudraCT", "2020-005891-36")]["confidence"] == 1.0
        assert ("CTIS", "2020-005891-36-00") in got
        assert got[("IRAS", "IRAS:298897")]["mappingType"] == "secondary_id"
        assert ("CPMS", "CPMS:49816") in got
        assert got[("Protocol serial number", "CRUKD/22/002")]["mappingType"] == "protocol_number"
        assert got[("DOI", "10.1186/ISRCTN62918594")]["mappingType"] == "doi"
        # NCT is listed twice in the record (dedicated field and secondary number)
        assert len([m for m in mappings if m["toId"] == "NCT05057013"]) == 1
        for m in mappings:
            assert m["fromId"] == "ISRCTN62918594" and m["fromSource"] == "ISRCTN"
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }

    @pytest.mark.asyncio
    async def test_protocol_number_only_record(self, adapter):
        with _mock(fx.RECORD_PACE):
            mappings = await adapter.get_mappings("ISRCTN54285094")
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("Protocol serial number", "G0200434"),
            ("DOI", "10.1186/ISRCTN54285094"),
        }

    @pytest.mark.asyncio
    async def test_protocol_serial_without_secondary_numbers(self, adapter):
        xml = _trial_xml().replace(
            "</trial>",
            "<externalRefs><doi/><protocolSerialNumber>ABC-1</protocolSerialNumber>"
            "<irasNumber>123</irasNumber></externalRefs></trial>",
        )
        with _mock(xml):
            mappings = await adapter.get_mappings("ISRCTN11111111")
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("IRAS", "IRAS:123"),
            ("Protocol", "ABC-1"),
        }

    @pytest.mark.asyncio
    async def test_failures(self, adapter):
        with _mock(fx.EMPTY_RESULT):
            assert await adapter.get_mappings("ISRCTN99999999") == []
        with patch.object(ISRCTNAdapter, "_fetch", new=AsyncMock(return_value={"isrctn": "x"})):
            assert await adapter.get_mappings("ISRCTN54285094") == []


class TestFixturesAreWellFormed:
    @pytest.mark.parametrize("name", ["SEARCH_MECFS", "RECORD_PACE", "EMPTY_RESULT"])
    def test_fixture_parses(self, name):
        root = ET.fromstring(getattr(fx, name))
        assert root.tag.endswith("allTrials")
