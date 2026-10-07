"""Unit tests for ICD11Adapter (mock-only: the WHO API needs credentials)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fixtures import icd11_responses as fx

from knowledge_lookup.adapters import icd11_adapter
from knowledge_lookup.adapters.icd11_adapter import (
    ICD11_TOKEN_URL,
    ICD11Adapter,
    _entity_ref,
    _lang_text,
    _strip_markup,
    _terms,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

MMS_BASE = "https://id.who.int/icd/release/11/2025-01/mms"


class HttpError(Exception):
    """Stand-in for aiohttp.ClientResponseError (only ``status`` is inspected)."""

    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No ambient credentials: neither env vars nor a developer's .env file."""
    for name in (
        "ICD11_CLIENT_ID",
        "ICD11_CLIENT_SECRET",
        "ICD11_API_BASE",
        "ICD11_RELEASE",
        "ICD11_LANGUAGE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, service: None)


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("ICD11_CLIENT_ID", "client-id")
    monkeypatch.setenv("ICD11_CLIENT_SECRET", "client-secret")


@pytest.fixture
def adapter(creds):
    return ICD11Adapter(LookupConfig())


def api_router(routes):
    """Build a ``_make_request`` replacement serving ``routes`` (url suffix -> payload)."""

    async def fake(url, params=None, headers=None, json_data=None):
        for suffix, payload in routes.items():
            if url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise HttpError(404)

    return AsyncMock(side_effect=fake)


FULL_ROUTES = {
    "/mms/search": fx.SEARCH_RESPONSE,
    "/mms/codeinfo/8E49": fx.CODEINFO_8E49,
    "/mms/111111111": fx.ENTITY_8E49,
    "/mms/555555555": fx.ENTITY_8E4,
    "/mms/777777777": fx.ENTITY_8E4A,
    "/mms/222222222": fx.ENTITY_SYMPTOM_MG22,
}


class TestAvailability:
    def test_source(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ICD11

    def test_no_credentials(self):
        assert ICD11Adapter(LookupConfig()).is_available() is False

    def test_env_credentials(self, adapter):
        assert adapter.is_available() is True

    def test_only_id_is_not_enough(self, monkeypatch):
        monkeypatch.setenv("ICD11_CLIENT_ID", "x")
        assert ICD11Adapter(LookupConfig()).is_available() is False

    def test_config_credentials(self, monkeypatch):
        keys = {"icd11_client_id": "a", "icd11_client_secret": "b"}
        monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, s: keys.get(s))
        assert ICD11Adapter(LookupConfig()).is_available() is True

    def test_custom_base_needs_no_credentials(self, monkeypatch):
        monkeypatch.setenv("ICD11_API_BASE", "http://localhost/")
        adapter = ICD11Adapter(LookupConfig())
        assert adapter.is_available() is True
        assert adapter.base_url == "http://localhost"

    def test_defaults_and_overrides(self, monkeypatch, adapter):
        assert adapter.release == "2025-01"
        assert adapter.language == "en"
        monkeypatch.setenv("ICD11_RELEASE", "2026-01")
        monkeypatch.setenv("ICD11_LANGUAGE", "de")
        assert adapter.release == "2026-01"
        assert adapter.language == "de"


class TestHelpers:
    def test_strip_markup(self):
        assert _strip_markup('Postviral <em class="found">fatigue</em>') == "Postviral fatigue"
        assert _strip_markup(None) == ""

    def test_lang_text(self):
        assert _lang_text({"@language": "en", "@value": " x "}) == "x"
        assert _lang_text("y") == "y"
        assert _lang_text(None) == ""

    def test_terms_skip_deprecated_and_garbage(self):
        value = [
            {"label": {"@value": "a"}},
            {"label": {"@value": "b"}, "deprecated": True},
            "junk",
            {"label": {}},
        ]
        assert _terms(value) == ["a"]
        assert _terms(None) == []

    @pytest.mark.parametrize(
        "uri, expected",
        [
            (f"{fx.MMS}/111111111", ("111111111", None)),
            ("http://id.who.int/icd/entity/257068234", ("257068234", None)),
            (f"{fx.MMS}/1234/unspecified", ("1234", "unspecified")),
            ("http://id.who.int/icd/release/11/2025-01/mms", None),
            ("", None),
        ],
    )
    def test_entity_ref(self, uri, expected):
        assert _entity_ref(uri) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("8E49", ("code", "8E49")),
            (" 8e49 ", ("code", "8E49")),
            ("ICD11:8E49", ("code", "8E49")),
            ("ICD-11:RA02", ("code", "RA02")),
            ("8E49/XS5W", ("code", "8E49")),
            ("QA00.1", ("code", "QA00.1")),
            ("111111111", ("entity", "111111111")),
            ("http://id.who.int/icd/entity/257068234", ("entity", "257068234")),
            (f"{fx.MMS}/1234/other", ("entity", "1234/other")),
            ("", None),
            ("not a code!", None),
            ("http://id.who.int/icd/entity", None),
        ],
    )
    def test_normalise_id(self, raw, expected):
        assert ICD11Adapter._normalise_id(raw) == expected

    def test_concept_types(self):
        assert ICD11Adapter._concept_type("8E49") == ConceptType.DISEASE
        assert ICD11Adapter._concept_type("MG22") == ConceptType.SYMPTOM
        assert ICD11Adapter._concept_type("XS5W") == ConceptType.UNKNOWN
        assert ICD11Adapter._concept_type("") == ConceptType.DISEASE


class TestToken:
    @pytest.mark.asyncio
    async def test_request_token_posts_form(self, adapter):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        post_ctx = MagicMock()
        post_ctx.__aenter__ = AsyncMock(return_value=response)
        post_ctx.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.post = MagicMock(return_value=post_ctx)
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            payload = await adapter._request_token()
        assert payload == fx.TOKEN_RESPONSE
        url = session.post.call_args.args[0]
        form = session.post.call_args.kwargs["data"]
        assert url == ICD11_TOKEN_URL
        assert form == {
            "grant_type": "client_credentials",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scope": "icdapi_access",
        }

    @pytest.mark.asyncio
    async def test_token_is_cached(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        assert await adapter._get_token() == "tok-abc"
        assert await adapter._get_token() == "tok-abc"
        assert adapter._request_token.await_count == 1

    @pytest.mark.asyncio
    async def test_token_refreshed_when_expired(self, adapter, monkeypatch):
        now = [1000.0]
        monkeypatch.setattr(icd11_adapter.time, "monotonic", lambda: now[0])
        adapter._request_token = AsyncMock(
            side_effect=[
                {"access_token": "t1", "expires_in": 3600},
                {"access_token": "t2", "expires_in": 3600},
            ]
        )
        assert await adapter._get_token() == "t1"
        now[0] += 3600 - 61  # still valid (60 s safety skew)
        assert await adapter._get_token() == "t1"
        now[0] += 5  # inside the skew window: treated as expired
        assert await adapter._get_token() == "t2"
        assert adapter._request_token.await_count == 2

    @pytest.mark.asyncio
    async def test_force_refresh(self, adapter):
        adapter._request_token = AsyncMock(
            side_effect=[{"access_token": "t1"}, {"access_token": "t2"}]
        )
        assert await adapter._get_token() == "t1"
        assert await adapter._get_token(force_refresh=True) == "t2"

    @pytest.mark.asyncio
    async def test_concurrent_callers_share_one_request(self, adapter):
        async def slow_token():
            await asyncio.sleep(0.01)
            return fx.TOKEN_RESPONSE

        adapter._request_token = AsyncMock(side_effect=slow_token)
        tokens = await asyncio.gather(*(adapter._get_token() for _ in range(5)))
        assert tokens == ["tok-abc"] * 5
        assert adapter._request_token.await_count == 1

    @pytest.mark.asyncio
    async def test_token_failure_returns_none(self, adapter):
        adapter._request_token = AsyncMock(side_effect=HttpError(400))
        assert await adapter._get_token() is None

    @pytest.mark.asyncio
    async def test_token_response_without_access_token(self, adapter):
        adapter._request_token = AsyncMock(return_value={"error": "invalid_client"})
        assert await adapter._get_token() is None
        assert await adapter.search_concepts("fatigue") == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_search(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        request = api_router(FULL_ROUTES)
        with patch.object(adapter, "_make_request", request):
            concepts = await adapter.search_concepts("fatigue", limit=10)

        url, params, headers = request.await_args.args
        assert url == f"{MMS_BASE}/search"
        assert params["q"] == "fatigue"
        assert params["useFlexisearch"] == "true"
        assert params["flatResults"] == "true"
        assert headers["Authorization"] == "Bearer tok-abc"
        assert headers["API-Version"] == "v2"
        assert headers["Accept-Language"] == "en"

        # duplicate 8E49 collapsed; the code-less block falls back to its entity id
        assert [c.primary_id for c in concepts] == ["8E49", "MG22", "333333333"]
        first = concepts[0]
        assert first.primary_label == "Postviral fatigue syndrome"  # highlighting stripped
        assert first.concept_type == ConceptType.DISEASE
        assert first.confidence_score == pytest.approx(0.93)
        assert "chapter:08" in first.categories
        assert concepts[1].concept_type == ConceptType.SYMPTOM
        assert first.sources == [KnowledgeSource.ICD11]

    @pytest.mark.asyncio
    async def test_limit(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            assert len(await adapter.search_concepts("fatigue", limit=1)) == 1
            assert await adapter.search_concepts("fatigue", limit=0) == []

    @pytest.mark.asyncio
    async def test_blank_query(self, adapter):
        adapter._make_request = AsyncMock()
        assert await adapter.search_concepts("   ") == []
        adapter._make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_and_malformed_responses(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        for payload in ({"destinationEntities": []}, {}, [], {"destinationEntities": [None, {}]}):
            with patch.object(adapter, "_make_request", AsyncMock(return_value=payload)):
                assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_server_error_returns_empty(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(500))):
            assert await adapter.search_concepts("fatigue") == []

    @pytest.mark.asyncio
    async def test_release_and_language_overrides(self, adapter, monkeypatch):
        monkeypatch.setenv("ICD11_RELEASE", "2026-01")
        monkeypatch.setenv("ICD11_LANGUAGE", "de")
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        request = AsyncMock(return_value={"destinationEntities": []})
        with patch.object(adapter, "_make_request", request):
            await adapter.search_concepts("Müdigkeit")
        url, _params, headers = request.await_args.args
        assert "/release/11/2026-01/mms/search" in url
        assert headers["Accept-Language"] == "de"


class TestAuthErrors:
    @pytest.mark.asyncio
    async def test_401_refreshes_token_once_and_retries(self, adapter):
        adapter._request_token = AsyncMock(
            side_effect=[
                {"access_token": "stale", "expires_in": 3600},
                {"access_token": "fresh", "expires_in": 3600},
            ]
        )
        request = AsyncMock(side_effect=[HttpError(401), fx.SEARCH_RESPONSE])
        with patch.object(adapter, "_make_request", request):
            concepts = await adapter.search_concepts("fatigue")
        assert len(concepts) == 3
        assert request.await_count == 2
        assert request.await_args_list[0].args[2]["Authorization"] == "Bearer stale"
        assert request.await_args_list[1].args[2]["Authorization"] == "Bearer fresh"
        assert adapter._request_token.await_count == 2

    @pytest.mark.asyncio
    async def test_persistent_401_gives_up(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        request = AsyncMock(side_effect=HttpError(401))
        with patch.object(adapter, "_make_request", request):
            assert await adapter.search_concepts("fatigue") == []
            assert await adapter.get_concept_details("8E49") is None
        assert request.await_count == 4  # one retry per call, never more

    @pytest.mark.asyncio
    async def test_401_when_refresh_fails(self, adapter):
        adapter._request_token = AsyncMock(side_effect=[fx.TOKEN_RESPONSE, HttpError(400)])
        request = AsyncMock(side_effect=HttpError(401))
        with patch.object(adapter, "_make_request", request):
            assert await adapter.search_concepts("fatigue") == []
        assert request.await_count == 1

    @pytest.mark.asyncio
    async def test_non_401_error_does_not_refresh(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(403))):
            assert await adapter.search_concepts("fatigue") == []
        assert adapter._request_token.await_count == 1


class TestCustomBase:
    @pytest.mark.asyncio
    async def test_no_token_and_no_authorization_header(self, monkeypatch):
        monkeypatch.setenv("ICD11_API_BASE", "http://localhost:8080/")
        adapter = ICD11Adapter(LookupConfig())
        adapter._request_token = AsyncMock()
        request = AsyncMock(return_value=fx.SEARCH_RESPONSE)
        with patch.object(adapter, "_make_request", request):
            concepts = await adapter.search_concepts("fatigue")
        assert len(concepts) == 3
        url, _params, headers = request.await_args.args
        assert url == "http://localhost:8080/icd/release/11/2025-01/mms/search"
        assert "Authorization" not in headers
        adapter._request_token.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_401_is_not_retried(self, monkeypatch):
        monkeypatch.setenv("ICD11_API_BASE", "http://localhost")
        adapter = ICD11Adapter(LookupConfig())
        request = AsyncMock(side_effect=HttpError(401))
        with patch.object(adapter, "_make_request", request):
            assert await adapter.search_concepts("fatigue") == []
        assert request.await_count == 1


class TestDetails:
    @pytest.mark.asyncio
    async def test_by_code(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        request = api_router(FULL_ROUTES)
        with patch.object(adapter, "_make_request", request):
            concept = await adapter.get_concept_details("ICD11:8e49")
        urls = [call.args[0] for call in request.await_args_list]
        assert urls == [f"{MMS_BASE}/codeinfo/8E49", f"{MMS_BASE}/111111111"]

        assert concept.primary_id == "8E49"
        assert concept.primary_label == "Postviral fatigue syndrome"
        assert concept.definitions == [
            "A disorder characterised by prolonged fatigue following an infection."
        ]
        # index terms + inclusions, de-duplicated against the title, deprecated dropped
        assert concept.synonyms == [
            "Chronic fatigue syndrome",
            "Benign myalgic encephalomyelitis",
        ]
        assert concept.semantic_types == ["category"]
        assert concept.parents == ["555555555"]
        assert concept.children == []
        assert concept.labels == {"en": "Postviral fatigue syndrome"}
        assert concept.confidence_score == 1.0
        assert concept.source_data[KnowledgeSource.ICD11]["code"] == "8E49"

    @pytest.mark.asyncio
    async def test_by_entity_id_and_uri(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        request = api_router(FULL_ROUTES)
        with patch.object(adapter, "_make_request", request):
            by_id = await adapter.get_concept_details("111111111")
            by_uri = await adapter.get_concept_details(f"{fx.MMS}/111111111")
        assert by_id.primary_id == by_uri.primary_id == "8E49"
        assert request.await_count == 1  # second call served from the entity cache

    @pytest.mark.asyncio
    async def test_extension_code_is_unknown_type(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        routes = {
            "/codeinfo/XS5W": {"code": "XS5W", "stemId": f"{fx.MMS}/888888888"},
            "/mms/888888888": fx.ENTITY_EXTENSION,
        }
        with patch.object(adapter, "_make_request", api_router(routes)):
            concept = await adapter.get_concept_details("XS5W")
        assert concept.concept_type == ConceptType.UNKNOWN

    @pytest.mark.asyncio
    async def test_unknown_or_invalid(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            assert await adapter.get_concept_details("ZZ99") is None  # 404
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("???") is None
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"code": "A1"})):
            assert await adapter.get_concept_details("1A00") is None  # no stemId
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            assert await adapter.get_concept_details("111111111") is None  # empty entity
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"code": "A"})):
            assert await adapter.get_concept_details("222222222") is None  # no title

    @pytest.mark.asyncio
    async def test_entity_without_code_uses_entity_id(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        entity = {"title": {"@value": "Chapter 8"}, "classKind": "chapter"}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=entity)):
            concept = await adapter.get_concept_details("999999999")
        assert concept.primary_id == "999999999"


class TestRelationships:
    @pytest.mark.asyncio
    async def test_parents_and_children(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            rels = await adapter.get_relationships("555555555")
        assert {(r["relation_label"], r["related_id"]) for r in rels} == {
            ("is_a", "666666666"),  # parent page not served: falls back to the entity id
            ("has_subtype", "8E49"),
            ("has_subtype", "8E4A"),
        }
        child = next(r for r in rels if r["related_id"] == "8E49")
        assert child["related_name"] == "Postviral fatigue syndrome"
        assert child["source"] == "ICD11"

    @pytest.mark.asyncio
    async def test_child_limit(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            rels = await adapter.get_relationships("555555555", limit=1)
        assert [r["related_id"] for r in rels if r["relation_label"] == "has_subtype"] == ["8E49"]

    @pytest.mark.asyncio
    async def test_leaf_has_parent_edge(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            rels = await adapter.get_relationships("8E49")
        assert rels == [
            {
                "relation_label": "is_a",
                "related_id": "8E4",
                "related_name": "Other specified diseases of the nervous system",
                "source": "ICD11",
            }
        ]

    @pytest.mark.asyncio
    async def test_unresolvable_neighbours_and_errors(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        entity = {
            "title": {"@value": "X"},
            "code": "1A00",
            "parent": ["http://id.who.int/icd/release/11/2025-01/mms", f"{fx.MMS}/12345678"],
            "child": [],
        }

        async def fake(url, params=None, headers=None, json_data=None):
            if url.endswith("/mms/99999999"):
                return entity
            raise HttpError(500)

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("99999999")
            assert rels == [
                {
                    "relation_label": "is_a",
                    "related_id": "12345678",
                    "related_name": "12345678",
                    "source": "ICD11",
                }
            ]
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(500))):
            assert await adapter.get_relationships("77777777") == []
        assert await adapter.get_relationships("") == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            assert await adapter.get_relationships("66666666") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_foundation_mapping(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            mappings = await adapter.get_mappings("8E49")
        assert mappings == [
            {
                "fromId": "8E49",
                "toId": "http://id.who.int/icd/entity/444444444",
                "fromSource": "ICD11",
                "toSource": "ICD11",
                "mappingType": "foundation_uri",
                "confidence": 1.0,
            }
        ]

    @pytest.mark.asyncio
    async def test_no_mapping_cases(self, adapter):
        adapter._request_token = AsyncMock(return_value=fx.TOKEN_RESPONSE)
        with patch.object(adapter, "_make_request", api_router(FULL_ROUTES)):
            assert await adapter.get_mappings("MG22") == []  # entity has no source field
            assert await adapter.get_mappings("") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=HttpError(500))):
            assert await adapter.get_mappings("8E49") == []
