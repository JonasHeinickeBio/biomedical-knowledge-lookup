"""Unit tests for MedlinePlusAdapter (health-topic web service + MedlinePlus Connect); no network.

``tests/fixtures/medlineplus_responses.py`` holds real answers (site lists dropped and long
summaries cut so the file stays small). Hand-built XML/JSON covers failure shapes.
"""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import _vocab_common, medlineplus_adapter
from knowledge_lookup.adapters.medlineplus_adapter import CODE_SYSTEMS, MedlinePlusAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.medlineplus_responses import RECORDED, request_key

pytestmark = pytest.mark.unit

ME_CFS = "myalgicencephalomyelitischronicfatiguesyndrome"
EMPTY_WS = "<nlmSearchResult><term>x</term><count>0</count></nlmSearchResult>"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(medlineplus_adapter.EMAIL_ENV, raising=False)
    monkeypatch.setattr(medlineplus_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    ad = MedlinePlusAdapter(lookup_config)
    ad._ws_spacer.interval = 0.0
    ad._connect_spacer.interval = 0.0
    return ad


def replay(overrides=None):
    """Fake for ``_make_request`` / ``_make_request_text`` answering from the recordings."""
    overrides = overrides or {}

    async def fake(url, params=None, headers=None, json_data=None):
        key = request_key(url, params)
        if key in overrides:
            value = overrides[key]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        if key not in RECORDED:
            raise AssertionError(f"unrecorded request: {key}")
        return copy.deepcopy(RECORDED[key])

    return fake


def patched(adapter, overrides=None):
    fake = replay(overrides)
    return (
        patch.object(adapter, "_make_request_text", AsyncMock(side_effect=fake)),
        patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)),
    )


def ws_key(term, db="healthTopics", retmax=10):
    params = {"tool": "biomedical-knowledge-lookup", "db": db, "term": term}
    params |= {"retmax": retmax, "rettype": "topic"}
    return request_key(medlineplus_adapter.WS_URL, params)


def connect_key(system, code, language=None):
    params = {
        "mainSearchCriteria.v.cs": CODE_SYSTEMS[system][0],
        "mainSearchCriteria.v.c": code,
        "knowledgeResponseType": "application/json",
    }
    if language:
        params["informationRecipient.languageCode.c"] = language
    return request_key(medlineplus_adapter.CONNECT_URL, params)


def topic_xml(*topics):
    """Minimal rettype=topic answer: topics = [(slug, title, extra_xml)]."""
    docs = "".join(
        f'<document rank="{i}" url="https://medlineplus.gov/{slug}.html"><content name="healthTopic">'
        f'<health-topic title="{title}" url="https://medlineplus.gov/{slug}.html" id="{i + 1}" '
        f'language="English">{extra}</health-topic></content></document>'
        for i, (slug, title, extra) in enumerate(topics)
    )
    return f"<nlmSearchResult><count>{len(topics)}</count><list>{docs}</list></nlmSearchResult>"


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.MEDLINEPLUS
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "url,slug",
        [
            ("https://medlineplus.gov/fatigue.html", "fatigue"),
            (
                "https://medlineplus.gov/fatigue.html?utm_source=mplusconnect&utm_medium=x",
                "fatigue",
            ),
            ("medlineplus.gov/Fatigue.HTML", "fatigue"),
            ("https://medlineplus.gov/spanish/fatiga.html", "spanish/fatiga"),
            (
                "https://medlineplus.gov/lab-tests/sodium-blood-test?utm=1",
                "lab-tests/sodium-blood-test",
            ),
            ("https://medlineplus.gov/", None),
            ("", None),
        ],
    )
    def test_slug_from_url(self, url, slug):
        assert MedlinePlusAdapter.slug_from_url(url) == slug

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("fatigue", ("slug", "fatigue")),
            ("Fatigue", ("slug", "fatigue")),
            ("MEDLINEPLUS:fatigue", ("slug", "fatigue")),
            ("medlineplus:spanish/fatiga", ("slug", "spanish/fatiga")),
            ("spanish/fatiga", ("slug", "spanish/fatiga")),
            ("https://medlineplus.gov/fatigue.html?utm_source=x", ("slug", "fatigue")),
            ("medlineplus.gov/fatigue.html", ("slug", "fatigue")),
            ("ICD10CM:G93.32", ("code", "ICD10CM", "G93.32")),
            ("icd-10-cm:g93.32", ("code", "ICD10CM", "G93.32")),
            ("ICD10:G93.32", ("code", "ICD10CM", "G93.32")),
            ("G93.32", ("code", "ICD10CM", "G93.32")),
            ("g93.32", ("code", "ICD10CM", "G93.32")),
            ("U09.9", ("code", "ICD10CM", "U09.9")),
            ("SNOMEDCT:52702003", ("code", "SNOMEDCT", "52702003")),
            ("SNOMED CT:52702003", ("code", "SNOMEDCT", "52702003")),
            ("snomedct_us:52702003", ("code", "SNOMEDCT", "52702003")),
            ("ICD9CM:780.71", ("code", "ICD9CM", "780.71")),
            ("LOINC:2951-2", ("code", "LOINC", "2951-2")),
            ("2951-2", ("code", "LOINC", "2951-2")),
            ("RxNorm:861004", ("code", "RXNORM", "861004")),
            ("RXCUI:861004", ("code", "RXNORM", "861004")),
            ("NDC:0093-7214", ("code", "NDC", "0093-7214")),
        ],
    )
    def test_parse_id(self, adapter, raw, expected):
        assert adapter._parse_id(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "  ",
            None,
            "MEDLINEPLUS:89",  # numeric topic ids cannot be resolved by the service
            "89",
            "MEDLINEPLUS:",
            "nonsense words",
            "lab-tests/sodium-blood-test",
            "https://medlineplus.gov/lab-tests/sodium-blood-test",
            "BOGUS:123",
            "ICD10CM:bad code!",
            "https://",
        ],
    )
    def test_parse_id_rejects(self, adapter, raw):
        assert adapter._parse_id(raw) is None

    def test_code_systems_carry_the_verified_oids(self):
        assert CODE_SYSTEMS["ICD10CM"][0] == "2.16.840.1.113883.6.90"
        assert CODE_SYSTEMS["SNOMEDCT"][0] == "2.16.840.1.113883.6.96"
        assert CODE_SYSTEMS["LOINC"][0] == "2.16.840.1.113883.6.1"
        assert CODE_SYSTEMS["RXNORM"][0] == "2.16.840.1.113883.6.88"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_topic_concepts(self, adapter):
        text, js = patched(adapter)
        with text as req, js:
            results = await adapter.search_concepts("chronic fatigue syndrome", limit=3)
        url, params = req.call_args.args
        assert url == "https://wsearch.nlm.nih.gov/ws/query"
        assert params == {
            "tool": "biomedical-knowledge-lookup",
            "db": "healthTopics",
            "term": "chronic fatigue syndrome",
            "retmax": 3,
            "rettype": "topic",
        }
        assert [c.primary_id for c in results] == [
            f"MEDLINEPLUS:{ME_CFS}",
            "MEDLINEPLUS:fatigue",
            "MEDLINEPLUS:postcovidconditionslongcovid",
        ]
        cfs = results[0]
        assert cfs.primary_label == "Myalgic Encephalomyelitis/Chronic Fatigue Syndrome"
        assert cfs.concept_type == ConceptType.DISEASE
        assert cfs.categories == ["Bones, Joints and Muscles", "Infections"]
        assert {"CFS", "ME/CFS", "SEID", "Chronic fatigue syndrome"} <= set(cfs.synonyms)
        assert cfs.primary_label not in cfs.synonyms
        # patient-facing summary as plain text, not HTML
        assert cfs.definitions[0].startswith("What is myalgic encephalomyelitis/chronic fatigue")
        assert "<" not in cfs.definitions[0] and "&lt;" not in cfs.definitions[0]
        assert cfs.related == ["MEDLINEPLUS:fatigue"]
        identifiers = {(str(i.source), i.identifier) for i in cfs.identifiers}
        assert ("MEDLINEPLUS", "89") in identifiers and ("MESH", "D015673") in identifiers
        data = cfs.source_data[KnowledgeSource.MEDLINEPLUS]
        assert data["topic_id"] == "89" and data["url"].endswith(f"{ME_CFS}.html")
        assert "patients" in data["audience"] and "Courtesy of MedlinePlus" in data["attribution"]
        assert data["primary_institute"]["name"].startswith("National Institute of Neurological")
        assert results[1].concept_type == ConceptType.SYMPTOM  # topic group "Symptoms"

    @pytest.mark.asyncio
    async def test_no_hits(self, adapter):
        text, js = patched(adapter)
        with text, js:
            assert await adapter.search_concepts("zzzzqqqq", limit=3) == []

    @pytest.mark.asyncio
    async def test_limit_cap_and_trimming(self, adapter):
        xml = topic_xml(*[(f"t{i}", f"Topic {i}", "") for i in range(6)])
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=xml)) as req:
            two = await adapter.search_concepts("x", limit=2)
            await adapter.search_concepts("x", limit=500)
        assert [c.primary_id for c in two] == ["MEDLINEPLUS:t0", "MEDLINEPLUS:t1"]
        assert req.call_args_list[0].args[1]["retmax"] == 2
        assert req.call_args_list[1].args[1]["retmax"] == medlineplus_adapter.MAX_RESULTS

    @pytest.mark.asyncio
    async def test_email_only_from_environment(self, adapter, monkeypatch):
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=EMPTY_WS)) as req:
            await adapter.search_concepts("x")
            assert "email" not in req.call_args.args[1]
            monkeypatch.setenv(medlineplus_adapter.EMAIL_ENV, "dev@example.org")
            await adapter.search_concepts("x")
        assert req.call_args.args[1]["email"] == "dev@example.org"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("  ", 5), (None, 5), ("x", 0), ("x", -2)])
    async def test_invalid_input_makes_no_request(self, adapter, query, limit):
        with patch.object(adapter, "_make_request_text", AsyncMock()) as req:
            assert await adapter.search_concepts(query, limit) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_topics_and_broken_documents(self, adapter):
        xml = topic_xml(("a", "Topic A", ""), ("a", "Topic A again", ""), ("b", "Topic B", ""))
        xml = xml.replace("</list>", '<document url="u"><content name="x"/></document></list>')
        xml = xml.replace(
            "</list>",
            '<document url="u"><content name="healthTopic"><health-topic title="" url="https://medlineplus.gov/c.html"/></content></document></list>',
        )
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=xml)):
            results = await adapter.search_concepts("x")
        assert [c.primary_id for c in results] == ["MEDLINEPLUS:a", "MEDLINEPLUS:b"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body",
        [
            "not xml at all",
            "",
            '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><nlmSearchResult/>',
        ],
    )
    async def test_unusable_bodies(self, adapter, body):
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=body)):
            assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        with patch.object(adapter, "_make_request_text", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.search_concepts("x") == []


class TestConceptType:
    @pytest.mark.parametrize(
        "group,expected",
        [
            ("Symptoms", ConceptType.SYMPTOM),
            ("Drug Therapy", ConceptType.TREATMENT),
            ("Surgery and Rehabilitation", ConceptType.TREATMENT),
            ("Diagnostic Tests", ConceptType.PROCEDURE),
            ("Infections", ConceptType.DISEASE),
            ("", ConceptType.DISEASE),
        ],
    )
    @pytest.mark.asyncio
    async def test_type_follows_the_topic_group(self, adapter, group, expected):
        extra = (
            f'<group id="1" url="https://medlineplus.gov/g.html">{group}</group>' if group else ""
        )
        xml = topic_xml(("t", "Topic", extra))
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=xml)):
            (concept,) = await adapter.search_concepts("t")
        assert concept.concept_type == expected


class TestDetailsBySlug:
    @pytest.mark.asyncio
    async def test_slug_picks_the_exact_topic_from_ranked_hits(self, adapter):
        text, js = patched(adapter)
        with text as req, js:
            concept = await adapter.get_concept_details("fatigue")
        # the answer lists ME/CFS too; only the exact URL slug is returned
        assert concept.primary_id == "MEDLINEPLUS:fatigue"
        assert concept.concept_type == ConceptType.SYMPTOM
        assert req.call_args.args[1]["term"] == "fatigue" and req.call_args.args[1]["retmax"] == 10
        assert req.call_count == 1

    @pytest.mark.asyncio
    async def test_url_and_curie_forms(self, adapter):
        text, js = patched(adapter)
        with text, js:
            a = await adapter.get_concept_details(f"MEDLINEPLUS:{ME_CFS}")
            b = await adapter.get_concept_details(f"https://medlineplus.gov/{ME_CFS}.html?utm=x")
        assert a.primary_id == b.primary_id == f"MEDLINEPLUS:{ME_CFS}"

    @pytest.mark.asyncio
    async def test_spanish_slug_uses_the_spanish_database(self, adapter):
        text, js = patched(adapter)
        with text as req, js:
            concept = await adapter.get_concept_details("spanish/fatigue")
        assert concept.primary_id == "MEDLINEPLUS:spanish/fatigue"
        assert concept.primary_label == "Fatiga"
        params = req.call_args.args[1]
        assert params["db"] == "healthTopicsSpanish" and params["term"] == "fatigue"

    @pytest.mark.asyncio
    async def test_falls_back_to_the_quoted_url_query(self, adapter):
        other = topic_xml(("other", "Other", ""))
        found = topic_xml(("target", "Target", ""))
        answers = {ws_key("target"): other, ws_key('"medlineplus.gov/target.html"'): found}
        text, js = patched(adapter, answers)
        with text as req, js:
            concept = await adapter.get_concept_details("target")
        assert concept.primary_id == "MEDLINEPLUS:target" and req.call_count == 2

    @pytest.mark.asyncio
    async def test_unknown_slug(self, adapter):
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=EMPTY_WS)) as req:
            assert await adapter.get_concept_details("nosuchtopic") is None
        assert req.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw", ["", "MEDLINEPLUS:89", "nonsense words", "lab-tests/x"])
    async def test_unrecognised_ids_make_no_request(self, adapter, raw):
        with patch.object(adapter, "_make_request_text", AsyncMock()) as req:
            assert await adapter.get_concept_details(raw) is None
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        with patch.object(adapter, "_make_request_text", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("fatigue") is None


class TestDetailsByCode:
    @pytest.mark.asyncio
    async def test_icd10cm_code_gives_the_me_cfs_topic(self, adapter):
        text, js = patched(adapter)
        with text, js as connect:
            concept = await adapter.get_concept_details("ICD10CM:G93.32")
        params = connect.call_args.args[1]
        assert params["mainSearchCriteria.v.cs"] == "2.16.840.1.113883.6.90"
        assert params["mainSearchCriteria.v.c"] == "G93.32"
        assert params["knowledgeResponseType"] == "application/json"
        assert "informationRecipient.languageCode.c" not in params
        assert concept.primary_id == f"MEDLINEPLUS:{ME_CFS}"
        assert concept.source_data[KnowledgeSource.MEDLINEPLUS]["matched_code"] == "ICD10CM:G93.32"
        assert concept.related == ["MEDLINEPLUS:fatigue"]  # full topic record, not just the entry

    @pytest.mark.asyncio
    async def test_snomed_ct_code(self, adapter):
        text, js = patched(adapter)
        with text, js:
            concept = await adapter.get_concept_details("SNOMEDCT:52702003")
        assert concept.primary_id == f"MEDLINEPLUS:{ME_CFS}"

    @pytest.mark.asyncio
    async def test_concepts_for_code_returns_all_pages(self, adapter):
        text, js = patched(adapter)
        with text, js:
            concepts = await adapter.concepts_for_code("icd10cm", "G93.31")
        assert [c.primary_id for c in concepts] == [
            "MEDLINEPLUS:fatigue",
            "MEDLINEPLUS:neurologicdiseases",
            "MEDLINEPLUS:viralinfections",
        ]
        assert all(
            c.source_data[KnowledgeSource.MEDLINEPLUS]["matched_code"] == "ICD10CM:G93.31"
            for c in concepts
        )

    @pytest.mark.asyncio
    async def test_lab_test_pages_stay_connect_entries(self, adapter):
        text, js = patched(adapter)
        with text as ws, js:
            concepts = await adapter.concepts_for_code("LOINC", "2951-2")
        ws.assert_not_called()  # not health topics: no web-service lookup
        assert [c.primary_id for c in concepts] == [
            "MEDLINEPLUS:lab-tests/electrolyte-panel",
            "MEDLINEPLUS:lab-tests/sodium-blood-test",
        ]
        panel = concepts[0]
        assert panel.primary_label == "Electrolyte Panel"
        assert panel.concept_type == ConceptType.OBSERVATION
        assert panel.categories == ["lab-tests"]
        assert panel.definitions[0].startswith("What is an electrolyte panel?")
        data = panel.source_data[KnowledgeSource.MEDLINEPLUS]
        assert data["url"] == "https://medlineplus.gov/lab-tests/electrolyte-panel"
        assert data["matched_code"] == "LOINC:2951-2"

    @pytest.mark.asyncio
    async def test_drug_code_gives_a_drug_page_and_a_topic(self, adapter):
        text, js = patched(adapter)
        with text, js:
            concepts = await adapter.concepts_for_code("RXNORM", "861004")
            first = await adapter.get_concept_details("RXNORM:861004")
        assert concepts[0].primary_id == "MEDLINEPLUS:druginfo/meds/a696005"
        assert concepts[0].concept_type == ConceptType.DRUG and concepts[0].categories == [
            "druginfo"
        ]
        assert concepts[1].primary_id == "MEDLINEPLUS:diabetesmedicines"
        assert first.primary_id == concepts[0].primary_id

    @pytest.mark.asyncio
    async def test_code_without_a_page(self, adapter):
        text, js = patched(adapter)
        with text, js:
            assert await adapter.get_concept_details("ICD10CM:ZZZ99") is None

    @pytest.mark.asyncio
    async def test_spanish_language_parameter(self, adapter):
        answer = {"feed": {"entry": []}}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=answer)) as req:
            await adapter.concepts_for_code("ICD10CM", "E11.9", language="es")
            await adapter.concepts_for_code("ICD10CM", "E11.9", language="en")
        assert req.call_args_list[0].args[1]["informationRecipient.languageCode.c"] == "es"
        assert "informationRecipient.languageCode.c" not in req.call_args_list[1].args[1]

    @pytest.mark.asyncio
    async def test_failed_topic_lookup_falls_back_to_the_connect_entry(self, adapter):
        overrides = {ws_key(ME_CFS): RuntimeError("down")}
        text, js = patched(adapter, overrides)
        with text, js:
            concept = await adapter.get_concept_details("ICD10CM:G93.32")
        assert concept.primary_id == f"MEDLINEPLUS:{ME_CFS}"
        assert concept.related == [] and concept.definitions  # entry summary only
        assert concept.concept_type == ConceptType.DISEASE

    @pytest.mark.asyncio
    async def test_unknown_page_in_the_topic_database_falls_back_to_the_entry(self, adapter):
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=EMPTY_WS)):
            with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
                concepts = await adapter.concepts_for_code("ICD10CM", "G93.32")
        assert [c.primary_id for c in concepts] == [f"MEDLINEPLUS:{ME_CFS}"]
        assert concepts[0].related == []

    @pytest.mark.asyncio
    async def test_invalid_input_and_errors(self, adapter):
        assert await adapter.concepts_for_code("BOGUS", "1") == []
        assert await adapter.concepts_for_code("ICD10CM", "bad code!") == []
        assert await adapter.concepts_for_code("ICD10CM", "") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.concepts_for_code("ICD10CM", "G93.32") == []
            assert await adapter.get_concept_details("ICD10CM:G93.32") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body",
        [
            None,
            {},
            {"feed": None},
            {"feed": {"entry": None}},
            {"feed": {"entry": ["junk", {"title": {"_value": "No link"}, "link": []}]}},
            {
                "feed": {
                    "entry": [
                        {"title": {"_value": ""}, "link": [{"href": "https://x.gov/a.html"}]}
                    ]
                }
            },
        ],
    )
    async def test_unexpected_connect_bodies(self, adapter, body):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            assert await adapter.concepts_for_code("ICD10CM", "G93.32") == []

    @pytest.mark.asyncio
    async def test_duplicate_entries_are_collapsed(self, adapter):
        entry = {
            "title": {"_value": "Diabetes"},
            "link": [{"href": "https://medlineplus.gov/lab-tests/x?utm=1"}],
            "summary": {"_value": "<p>text</p>"},
        }
        body = {"feed": {"entry": [entry, copy.deepcopy(entry)]}}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            concepts = await adapter.concepts_for_code("LOINC", "1-1")
        assert len(concepts) == 1 and concepts[0].definitions == ["text"]


class TestRelationships:
    @pytest.mark.asyncio
    async def test_topic_relationships(self, adapter):
        text, js = patched(adapter)
        with text, js:
            rels = await adapter.get_relationships(ME_CFS)
        assert [(r["relation_label"], r["related_id"], r["related_name"]) for r in rels] == [
            ("related_topic", "MEDLINEPLUS:fatigue", "Fatigue"),
            ("member_of_group", "MEDLINEPLUS_GROUP:10", "Bones, Joints and Muscles"),
            ("member_of_group", "MEDLINEPLUS_GROUP:12", "Infections"),
            (
                "has_translation",
                f"MEDLINEPLUS:spanish/{ME_CFS}",
                "Encefalomielitis miálgica/Síndrome de fatiga crónica",
            ),
            (
                "primary_institute",
                "http://www.ninds.nih.gov/",
                "National Institute of Neurological Disorders and Stroke",
            ),
        ]
        assert all(r["source"] == "MEDLINEPLUS" for r in rels)
        assert rels[1]["url"] == "https://medlineplus.gov/bonesjointsandmuscles.html"
        assert rels[3]["language"] == "Spanish"

    @pytest.mark.asyncio
    async def test_relationships_by_code(self, adapter):
        text, js = patched(adapter)
        with text, js:
            rels = await adapter.get_relationships("ICD10CM:G93.32")
        assert rels[0]["related_id"] == "MEDLINEPLUS:fatigue"

    @pytest.mark.asyncio
    async def test_unknown_and_failures(self, adapter):
        assert await adapter.get_relationships("MEDLINEPLUS:89") == []
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=EMPTY_WS)):
            assert await adapter.get_relationships("nosuchtopic") == []
        with patch.object(adapter, "_make_request_text", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("fatigue") == []

    @pytest.mark.asyncio
    async def test_topic_without_links(self, adapter):
        with patch.object(
            adapter, "_make_request_text", AsyncMock(return_value=topic_xml(("lone", "Lone", "")))
        ):
            assert await adapter.get_relationships("lone") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_topic_mesh_mappings(self, adapter):
        text, js = patched(adapter)
        with text, js:
            maps = await adapter.get_mappings("postcovidconditionslongcovid")
        assert [(m["toSource"], m["toId"], m["toName"]) for m in maps] == [
            ("MESH", "D000094024", "Post-Acute COVID-19 Syndrome"),
            ("MESH", "D000086382", "COVID-19"),
        ]
        for m in maps:
            assert {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            } <= set(m)
            assert m["fromId"] == "MEDLINEPLUS:postcovidconditionslongcovid"
            assert m["mappingType"] == "mesh_heading"

    @pytest.mark.asyncio
    async def test_code_mappings_include_the_connect_match(self, adapter):
        text, js = patched(adapter)
        with text, js:
            maps = await adapter.get_mappings("ICD10CM:G93.32")
        assert maps[0] == {
            "fromId": "ICD10CM:G93.32",
            "toId": f"MEDLINEPLUS:{ME_CFS}",
            "fromSource": "ICD10CM",
            "toSource": "MEDLINEPLUS",
            "mappingType": "connect_match",
            "confidence": 0.9,
        }
        assert [(m["toSource"], m["toId"]) for m in maps[1:]] == [("MESH", "D015673")]

    @pytest.mark.asyncio
    async def test_unknown_and_failures(self, adapter):
        assert await adapter.get_mappings("nonsense words") == []
        text, js = patched(adapter)
        with text, js:
            assert await adapter.get_mappings("ICD10CM:ZZZ99") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("ICD10CM:G93.32") == []


class TestSpacing:
    @pytest.mark.asyncio
    async def test_requests_are_spaced_per_service(self, adapter, monkeypatch):
        adapter._ws_spacer.interval = 0.05
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(_vocab_common.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=EMPTY_WS)):
            await adapter.search_concepts("x")
            await adapter.search_concepts("x")
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6
