"""Unit tests for LoincAdapter (mock-only: the LOINC FHIR server needs a login)."""

import base64
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fixtures import loinc_responses as fx

from knowledge_lookup.adapters.loinc_adapter import (
    LOINC_COPYRIGHT_NOTICE,
    LoincAdapter,
    _coding_text,
    _flatten_contains,
    _param_value,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


class HttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


class ContentTypeError(Exception):
    """Same class name as aiohttp's error for a non-JSON (login page) answer."""


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("LOINC_USERNAME", raising=False)
    monkeypatch.delenv("LOINC_PASSWORD", raising=False)
    monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, service: None)


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv("LOINC_USERNAME", "someone")
    monkeypatch.setenv("LOINC_PASSWORD", "pw")
    return LoincAdapter(LookupConfig())


class TestAvailability:
    def test_source(self, adapter):
        assert adapter.get_source() == KnowledgeSource.LOINC

    def test_needs_both_credentials(self, monkeypatch):
        assert LoincAdapter(LookupConfig()).is_available() is False
        monkeypatch.setenv("LOINC_USERNAME", "someone")
        assert LoincAdapter(LookupConfig()).is_available() is False
        monkeypatch.setenv("LOINC_PASSWORD", "pw")
        assert LoincAdapter(LookupConfig()).is_available() is True

    def test_config_keys(self, monkeypatch):
        keys = {"loinc_username": "u", "loinc_password": "p"}
        monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, s: keys.get(s))
        assert LoincAdapter(LookupConfig()).is_available() is True

    def test_basic_auth_header(self, adapter):
        headers = adapter._headers()
        assert headers["Authorization"] == "Basic " + base64.b64encode(b"someone:pw").decode()
        assert headers["Accept"] == "application/fhir+json"


class TestHelpers:
    def test_param_value(self):
        assert _param_value({"name": "x", "valueString": "a"}) == "a"
        assert _param_value({"name": "x"}) is None

    def test_coding_text(self):
        assert _coding_text({"code": "LP1", "display": "Cholesterol"}) == ("LP1", "Cholesterol")
        assert _coding_text({"code": "LP1"}) == ("LP1", "LP1")
        assert _coding_text("CHEM") == ("CHEM", "CHEM")
        assert _coding_text(None) == ("", "")

    def test_flatten_contains(self):
        items = [{"code": "a", "contains": [{"code": "b"}]}, "x", {"code": "c"}]
        assert [i["code"] for i in _flatten_contains(items)] == ["a", "b", "c"]
        assert _flatten_contains(None) == []

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2093-3", "2093-3"),
            (" loinc:718-7 ", "718-7"),
            ("LP15099-2", "LP15099-2"),
            ("cholesterol", None),
            ("2093", None),
            ("", None),
        ],
    )
    def test_normalise_code(self, raw, expected):
        assert LoincAdapter._normalise_code(raw) == expected


class TestSearch:
    @pytest.mark.asyncio
    async def test_expand_request_and_parsing(self, adapter):
        request = AsyncMock(return_value=fx.EXPAND_CHOLESTEROL)
        with patch.object(adapter, "_make_request", request):
            concepts = await adapter.search_concepts("cholesterol", limit=10)

        url, params, headers = request.await_args.args
        parsed = urlparse(url)
        assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
            "https://fhir.loinc.org/ValueSet/$expand"
        )
        assert parse_qs(parsed.query) == {
            "url": ["http://loinc.org/vs"],
            "filter": ["cholesterol"],
            "count": ["10"],
        }
        assert params is None
        assert headers["Authorization"].startswith("Basic ")

        # nested entry flattened, duplicate / code-less / display-less / junk dropped
        assert [c.primary_id for c in concepts] == ["2093-3", "2091-7", "13457-7"]
        first = concepts[0]
        assert first.primary_label == "Cholesterol [Mass/volume] in Serum or Plasma"
        assert first.concept_type == ConceptType.OBSERVATION
        assert first.sources == [KnowledgeSource.LOINC]
        assert LOINC_COPYRIGHT_NOTICE in first.source_data[KnowledgeSource.LOINC]["copyright"]

    @pytest.mark.asyncio
    async def test_limit(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.EXPAND_CHOLESTEROL)):
            assert len(await adapter.search_concepts("cholesterol", limit=2)) == 2
            assert await adapter.search_concepts("cholesterol", limit=0) == []

    @pytest.mark.asyncio
    async def test_empty_blank_and_bad_payloads(self, adapter):
        for payload in (fx.EXPAND_EMPTY, {}, [], None):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("zzz") == []
        assert await adapter.search_concepts("  ") == []

    @pytest.mark.asyncio
    async def test_code_query_uses_lookup(self, adapter):
        request = AsyncMock(return_value=fx.LOOKUP_2093_3)
        with patch.object(adapter, "_make_request", request):
            concepts = await adapter.search_concepts("2093-3")
        assert [c.primary_id for c in concepts] == ["2093-3"]
        assert "CodeSystem/$lookup" in request.await_args.args[0]

    @pytest.mark.asyncio
    async def test_code_query_not_found(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.OPERATION_OUTCOME)):
            assert await adapter.search_concepts("0000-0") == []

    @pytest.mark.asyncio
    async def test_unicode_query_is_url_encoded(self, adapter):
        request = AsyncMock(return_value=fx.EXPAND_EMPTY)
        with patch.object(adapter, "_make_request", request):
            await adapter.search_concepts("Hämoglobin & Eisen")
        query = parse_qs(urlparse(request.await_args.args[0]).query)
        assert query["filter"] == ["Hämoglobin & Eisen"]


class TestAuthErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [401, 403])
    async def test_rejected_credentials(self, adapter, caplog, status):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(status))):
            with caplog.at_level("ERROR"):
                assert await adapter.search_concepts("cholesterol") == []
                assert await adapter.get_concept_details("2093-3") is None
                assert await adapter.get_relationships("2093-3") == []
        assert "LOINC_USERNAME" in caplog.text
        assert "pw" not in caplog.text.replace("LOINC_PASSWORD", "")  # secrets never logged

    @pytest.mark.asyncio
    async def test_html_login_page(self, adapter, caplog):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=ContentTypeError("html"))
        ):
            with caplog.at_level("ERROR"):
                assert await adapter.search_concepts("cholesterol") == []
        assert "login page" in caplog.text

    @pytest.mark.asyncio
    async def test_server_error(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(500))):
            assert await adapter.search_concepts("cholesterol") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_lookup_request(self, adapter):
        request = AsyncMock(return_value=fx.LOOKUP_2093_3)
        with patch.object(adapter, "_make_request", request):
            await adapter.get_concept_details("LOINC:2093-3")
        parsed = urlparse(request.await_args.args[0])
        assert parsed.path == "/CodeSystem/$lookup"
        query = parse_qs(parsed.query)
        assert query["system"] == ["http://loinc.org"]
        assert query["code"] == ["2093-3"]
        assert {"COMPONENT", "SYSTEM", "METHOD_TYP", "CLASS"} <= set(query["property"])

    @pytest.mark.asyncio
    async def test_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.LOOKUP_2093_3)):
            concept = await adapter.get_concept_details("2093-3")
        assert concept.primary_id == "2093-3"
        assert concept.primary_label == "Cholesterol [Mass/volume] in Serum or Plasma"
        assert concept.concept_type == ConceptType.OBSERVATION
        assert concept.synonyms == ["Cholest SerPl-mCnc", "Total cholesterol"]
        assert concept.definitions == ["Total cholesterol in serum or plasma."]
        assert concept.categories == ["class:CHEM"]
        assert concept.semantic_types == ["specimen:Ser/Plas"]
        assert concept.confidence_score == 1.0
        data = concept.source_data[KnowledgeSource.LOINC]
        assert data["version"] == "2.78"
        assert data["long_common_name"] == "Cholesterol [Mass/volume] in Serum or Plasma"
        assert data["properties"]["COMPONENT"] == "Cholesterol"
        assert data["properties"]["SCALE_TYP"] == "Qn"
        assert data["properties"]["STATUS"] == "ACTIVE"
        assert data["copyright"] == LOINC_COPYRIGHT_NOTICE

    @pytest.mark.asyncio
    async def test_display_only_response(self, adapter):
        payload = {
            "resourceType": "Parameters",
            "parameter": [{"name": "display", "valueString": "X"}],
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            concept = await adapter.get_concept_details("1-1")
        assert concept.primary_label == "X"
        assert concept.synonyms == []

    @pytest.mark.asyncio
    async def test_distinct_display_becomes_synonym(self, adapter):
        payload = {
            "parameter": [
                {"name": "display", "valueString": "Display name"},
                {
                    "name": "designation",
                    "part": [
                        {"name": "use", "valueCoding": {"code": "LONG_COMMON_NAME"}},
                        {"name": "value", "valueString": "Long common name"},
                    ],
                },
            ]
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
            concept = await adapter.get_concept_details("1-1")
        assert concept.primary_label == "Long common name"
        assert concept.synonyms == ["Display name"]

    @pytest.mark.asyncio
    async def test_invalid_unknown_and_empty(self, adapter):
        request = AsyncMock(return_value=fx.OPERATION_OUTCOME)
        with patch.object(adapter, "_make_request", request):
            assert await adapter.get_concept_details("0000-0") is None
            assert await adapter.get_concept_details("not a code") is None
            assert await adapter.get_concept_details("") is None
        for payload in ({}, [], {"parameter": []}, {"parameter": ["x"]}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.get_concept_details("2093-3") is None

    @pytest.mark.asyncio
    async def test_lookup_cached_between_details_and_relationships(self, adapter):
        request = AsyncMock(return_value=fx.LOOKUP_2093_3)
        with patch.object(adapter, "_make_request", request):
            await adapter.get_concept_details("2093-3")
            await adapter.get_relationships("2093-3")
        assert request.await_count == 1


class TestRelationships:
    @pytest.mark.asyncio
    async def test_parts_as_typed_edges(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.LOOKUP_2093_3)):
            rels = await adapter.get_relationships("2093-3")
        assert {(r["relation_label"], r["related_id"], r["related_name"]) for r in rels} == {
            ("has_component", "LP-SYN-1", "Cholesterol"),
            ("has_property", "LP-SYN-2", "MCnc"),
            ("has_time_aspect", "LP-SYN-3", "Pt"),
            ("has_system", "LP-SYN-4", "Ser/Plas"),
            ("has_scale", "LP-SYN-5", "Qn"),
            ("has_method", "LP-SYN-6", "Photometry"),
            ("has_class", "CHEM", "CHEM"),
        }  # STATUS / DefinitionDescription are not relationships; duplicate part dropped
        assert all(r["source"] == "LOINC" for r in rels)
        assert len(rels) == 7

    @pytest.mark.asyncio
    async def test_hierarchy_properties(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(return_value=fx.LOOKUP_WITH_HIERARCHY)
        ):
            rels = await adapter.get_relationships("57698-3")
        assert {(r["relation_label"], r["related_id"]) for r in rels} == {
            ("is_a", "LP-SYN-PARENT"),
            ("has_subtype", "2093-3"),
        }

    @pytest.mark.asyncio
    async def test_failures(self, adapter):
        assert await adapter.get_relationships("nope") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(401))):
            assert await adapter.get_relationships("2093-3") == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value=fx.OPERATION_OUTCOME)):
            assert await adapter.get_relationships("0000-0") == []
