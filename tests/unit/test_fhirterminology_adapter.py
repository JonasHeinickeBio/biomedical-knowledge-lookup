"""Unit tests for FHIRTerminologyAdapter (HTTP mocked with trimmed real server responses)."""

import copy
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fixtures import fhirterminology_responses as fx

from knowledge_lookup.adapters import fhirterminology_adapter as mod
from knowledge_lookup.adapters.fhirterminology_adapter import (
    FHIRTerminologyAdapter,
    SystemSpec,
    resolve_system,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit

SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"
ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "FHIR_TERMINOLOGY_URL",
        "FHIR_TERMINOLOGY_SYSTEMS",
        "FHIR_TERMINOLOGY_TOKEN",
        "FHIR_TERMINOLOGY_USER",
        "FHIR_TERMINOLOGY_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def adapter(lookup_config):
    a = FHIRTerminologyAdapter(lookup_config)
    a._min_interval = 0.0
    return a


class FakeServer:
    """Stands in for ``_request``: routes by (method, path, system/url) to canned answers."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def __call__(self, method, path, params=None, body=None):
        self.calls.append((method, path, params, body))
        p = dict(params or [])
        if body:
            include = body["parameter"][0]["resource"]["compose"]["include"][0]
            key = (method, path, include["system"])
        else:
            key = (method, path, p.get("system") or p.get("url") or "")
        answer = self.routes.get(key)
        if isinstance(answer, Exception):
            raise answer
        return answer if answer is not None else (404, fx.OUTCOME_CODE_NOT_FOUND_404)

    def patch(self, adapter):
        return patch.object(adapter, "_request", new=AsyncMock(side_effect=self))


def _lookup_route(system, data, status=200):
    answer = data if isinstance(data, Exception) else (status, data)
    return (("GET", "CodeSystem/$lookup", system), answer)


def server(*routes):
    return FakeServer(dict(routes))


# ----------------------------------------------------------------------
# Systems, identifiers, configuration
# ----------------------------------------------------------------------


class TestSystems:
    @pytest.mark.parametrize(
        "token,uri,version",
        [
            ("loinc", LOINC, None),
            ("LOINC", LOINC, None),
            ("SNOMED CT", SNOMED, None),
            ("snomed-ct", SNOMED, None),
            ("ICD-10-GM", "http://fhir.de/CodeSystem/bfarm/icd-10-gm", None),
            ("icd10gm@2020", "http://fhir.de/CodeSystem/bfarm/icd-10-gm", "2020"),
            ("atc@2025.0.0", "http://www.whocc.no/atc", "2025.0.0"),
            ("http://example.org/cs", "http://example.org/cs", None),
            ("http://example.org/cs@1.0", "http://example.org/cs", "1.0"),
            ("urn:oid:2.16.840", "urn:oid:2.16.840", None),
            ("loinc@", LOINC, None),
        ],
    )
    def test_resolve_system(self, token, uri, version):
        assert resolve_system(token) == SystemSpec(uri, version)

    @pytest.mark.parametrize("token", ["", "  ", "nonsense", None])
    def test_resolve_system_unknown(self, token):
        assert resolve_system(token) is None

    def test_all_aliases_have_uri_and_type(self):
        for alias, (uri, ctype) in mod._SYSTEMS.items():
            assert resolve_system(alias).uri == uri
            assert isinstance(ctype, ConceptType)

    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.FHIRTERMINOLOGY
        assert adapter.is_available() is True

    def test_default_and_custom_base_url(self, lookup_config, monkeypatch):
        assert FHIRTerminologyAdapter(lookup_config).base_url == "https://tx.fhir.org/r4"
        monkeypatch.setenv("FHIR_TERMINOLOGY_URL", " https://r4.ontoserver.csiro.au/fhir/ ")
        assert (
            FHIRTerminologyAdapter(lookup_config).base_url == "https://r4.ontoserver.csiro.au/fhir"
        )

    def test_parse_concept_id_forms(self, adapter):
        assert adapter._parse_concept_id("loinc|2093-3") == (SystemSpec(LOINC), "2093-3")
        assert adapter._parse_concept_id(f"{SNOMED}|84229001") == (SystemSpec(SNOMED), "84229001")
        assert adapter._parse_concept_id(" icd10gm | G93.3 ") == (
            SystemSpec("http://fhir.de/CodeSystem/bfarm/icd-10-gm"),
            "G93.3",
        )
        spec, code = adapter._parse_concept_id("atc|N02BA01|2025.0.0")
        assert (spec.uri, spec.version, code) == ("http://www.whocc.no/atc", "2025.0.0", "N02BA01")
        spec, code = adapter._parse_concept_id("atc@2024|N02BA01")
        assert spec.version == "2024"

    @pytest.mark.parametrize(
        "cid", ["", "   ", None, "|", "loinc|", "nonsense|1", "a|b|c|d", "2093-3"]
    )
    def test_parse_concept_id_invalid(self, adapter, cid):
        assert adapter._parse_concept_id(cid) is None

    def test_bare_code_uses_single_configured_system(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_SYSTEMS", "icd10gm@2020")
        spec, code = adapter._parse_concept_id("G93.3")
        assert (spec.version, code) == ("2020", "G93.3")

    def test_bare_code_needs_exactly_one_system(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_SYSTEMS", "loinc,snomed")
        assert adapter._parse_concept_id("2093-3") is None

    def test_configured_version_is_applied_to_unpinned_ids(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_SYSTEMS", "atc@2025.0.0, loinc")
        spec, _ = adapter._parse_concept_id("atc|N02")
        assert spec.version == "2025.0.0"
        spec, _ = adapter._parse_concept_id("atc|N02|2024")  # an explicit version wins
        assert spec.version == "2024"
        spec, _ = adapter._parse_concept_id("loinc|2093-3")
        assert spec.version is None

    def test_format_id_prefers_alias(self):
        assert FHIRTerminologyAdapter._format_id(LOINC, "1") == "loinc|1"
        assert FHIRTerminologyAdapter._format_id(SNOMED, "1") == "snomed|1"
        assert FHIRTerminologyAdapter._format_id("http://x.org/cs", "1") == "http://x.org/cs|1"

    def test_search_systems_resolution(self, adapter, monkeypatch, caplog):
        assert [s.uri for s in adapter._search_systems(None)] == [SNOMED, ICD10CM, LOINC]
        monkeypatch.setenv("FHIR_TERMINOLOGY_SYSTEMS", "atc, atc, bogus")
        with caplog.at_level(logging.WARNING):
            assert [s.uri for s in adapter._search_systems(None)] == ["http://www.whocc.no/atc"]
        assert "bogus" in caplog.text
        assert [s.uri for s in adapter._search_systems("loinc,snomed")] == [LOINC, SNOMED]
        assert [s.uri for s in adapter._search_systems(["hpo"])] == [
            "http://purl.obolibrary.org/obo/hp.owl"
        ]

    def test_source_name(self):
        assert FHIRTerminologyAdapter._source_name(LOINC) == "LOINC"
        assert FHIRTerminologyAdapter._source_name(SNOMED) == "SNOMEDCT"
        assert FHIRTerminologyAdapter._source_name("http://www.whocc.no/atc") == "ATC"
        assert FHIRTerminologyAdapter._source_name("http://read.info/readv2") == (
            "http://read.info/readv2"
        )


class TestAuth:
    def test_no_credentials_by_default(self, adapter):
        assert adapter._auth_headers() == {}

    def test_bearer_token(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_TOKEN", " s3cret ")
        assert adapter._auth_headers() == {"Authorization": "Bearer s3cret"}

    def test_basic_needs_user_and_password(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_USER", "mii")
        assert adapter._auth_headers() == {}
        monkeypatch.setenv("FHIR_TERMINOLOGY_PASSWORD", "pw")
        # base64("mii:pw")
        assert adapter._auth_headers() == {"Authorization": "Basic bWlpOnB3"}

    def test_password_alone_is_ignored(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_PASSWORD", "pw")
        assert adapter._auth_headers() == {}

    def test_token_wins_over_basic(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_TOKEN", "t")
        monkeypatch.setenv("FHIR_TERMINOLOGY_USER", "mii")
        monkeypatch.setenv("FHIR_TERMINOLOGY_PASSWORD", "pw")
        assert adapter._auth_headers() == {"Authorization": "Bearer t"}

    def test_token_from_config_api_keys(self):
        config = LookupConfig(api_keys={"fhir_terminology_token": "from-config"})
        a = FHIRTerminologyAdapter(config)
        assert a._auth_headers() == {"Authorization": "Bearer from-config"}

    def test_credentials_refused_over_plain_http(self, lookup_config, monkeypatch, caplog):
        monkeypatch.setenv("FHIR_TERMINOLOGY_URL", "http://tx.example.org/fhir")
        monkeypatch.setenv("FHIR_TERMINOLOGY_TOKEN", "t")
        with caplog.at_level(logging.WARNING):
            assert FHIRTerminologyAdapter(lookup_config)._auth_headers() == {}
        assert "not https" in caplog.text

    def test_plain_http_is_allowed_for_localhost(self, lookup_config, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_URL", "http://localhost:8080/fhir")
        monkeypatch.setenv("FHIR_TERMINOLOGY_TOKEN", "t")
        assert FHIRTerminologyAdapter(lookup_config)._auth_headers() == {
            "Authorization": "Bearer t"
        }


# ----------------------------------------------------------------------
# HTTP layer
# ----------------------------------------------------------------------


def _response(status, data=None, raises=None):
    resp = MagicMock()
    resp.status = status
    resp.raise_for_status = MagicMock(side_effect=raises)
    if isinstance(data, Exception):
        resp.json = AsyncMock(side_effect=data)
    else:
        resp.json = AsyncMock(return_value=data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _session(*responses):
    session = MagicMock()
    session.request = MagicMock(side_effect=list(responses))
    return session


class TestRequest:
    @pytest.mark.asyncio
    async def test_get_sends_fhir_accept_and_params(self, adapter):
        session = _session(_response(200, {"resourceType": "Parameters"}))
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            status, data = await adapter._request("GET", "CodeSystem/$lookup", [("code", "1")])
        assert (status, data) == (200, {"resourceType": "Parameters"})
        args, kwargs = session.request.call_args
        assert args == ("GET", "https://tx.fhir.org/r4/CodeSystem/$lookup")
        assert kwargs["params"] == [("code", "1")]
        assert kwargs["headers"] == {"Accept": "application/fhir+json"}
        assert kwargs["json"] is None

    @pytest.mark.asyncio
    async def test_post_and_auth_header(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_TOKEN", "t")
        session = _session(_response(200, {"resourceType": "ValueSet"}))
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            await adapter._request("POST", "ValueSet/$expand", body={"a": 1})
        kwargs = session.request.call_args.kwargs
        assert kwargs["json"] == {"a": 1}
        assert kwargs["headers"]["Authorization"] == "Bearer t"

    @pytest.mark.asyncio
    async def test_client_errors_return_status_and_body(self, adapter):
        session = _session(_response(422, fx.OUTCOME_UNKNOWN_SYSTEM_422))
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            status, data = await adapter._request("GET", "CodeSystem/$lookup")
        assert status == 422 and data["resourceType"] == "OperationOutcome"
        session.request.return_value.__aenter__.return_value.raise_for_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_json_body_gives_none(self, adapter):
        session = _session(_response(200, ValueError("not json")))
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            assert await adapter._request("GET", "metadata") == (200, None)

    @pytest.mark.asyncio
    async def test_json_array_body_gives_none(self, adapter):
        session = _session(_response(200, [1, 2]))
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            assert await adapter._request("GET", "metadata") == (200, None)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [429, 500, 503])
    async def test_server_errors_raise_after_retries(self, adapter, status):
        error = RuntimeError(f"HTTP {status}")
        session = _session(*[_response(status, None, raises=error) for _ in range(6)])
        with patch.object(adapter, "_get_session", new=AsyncMock(return_value=session)):
            with pytest.raises(RuntimeError):
                await adapter._request("GET", "metadata")
        assert session.request.call_count > 1  # retried before giving up

    @pytest.mark.asyncio
    async def test_throttle_waits_between_requests(self, lookup_config):
        a = FHIRTerminologyAdapter(lookup_config)
        a._min_interval = 0.5
        with patch("asyncio.sleep", new=AsyncMock()) as sleep:
            await a._throttle()
            await a._throttle()
        sleep.assert_awaited_once()
        assert 0 < sleep.await_args.args[0] <= 0.5 + 1e-6


# ----------------------------------------------------------------------
# Capabilities, code system listing, validate-code
# ----------------------------------------------------------------------


class TestServerInfo:
    @pytest.mark.asyncio
    async def test_capabilities(self, adapter):
        with patch.object(
            adapter, "_request", new=AsyncMock(return_value=(200, fx.METADATA_TXFHIR))
        ) as req:
            info = await adapter.get_capabilities()
        assert req.await_args.args[:2] == ("GET", "metadata")
        assert info["software"] == "FHIRsmith"
        assert info["fhir_version"] == "4.0.1"
        assert info["resources"] == ["CodeSystem", "ValueSet", "ConceptMap"]
        assert info["server"].startswith("FHIR Server running at")

    @pytest.mark.asyncio
    async def test_capabilities_failures(self, adapter):
        with patch.object(adapter, "_request", new=AsyncMock(return_value=(404, None))):
            assert await adapter.get_capabilities() == {}
        with patch.object(adapter, "_request", new=AsyncMock(side_effect=RuntimeError("down"))):
            assert await adapter.get_capabilities() == {}

    @pytest.mark.asyncio
    async def test_list_code_systems(self, adapter):
        with patch.object(
            adapter, "_request", new=AsyncMock(return_value=(200, fx.CODESYSTEM_BUNDLE))
        ) as req:
            systems = await adapter.list_code_systems(title=" ICD ", url="http://x", limit=3)
        params = req.await_args.args[2]
        assert ("title", "ICD") in params and ("url", "http://x") in params
        assert ("_count", "3") in params
        assert len(systems) == 3
        assert systems[1]["url"] == ICD10CM
        assert set(systems[0]) == {"url", "version", "name", "title"}

    @pytest.mark.asyncio
    async def test_list_code_systems_failures(self, adapter):
        assert await adapter.list_code_systems(limit=0) == []
        with patch.object(adapter, "_request", new=AsyncMock(return_value=(500, None))):
            assert await adapter.list_code_systems() == []
        with patch.object(adapter, "_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.list_code_systems() == []

    @pytest.mark.asyncio
    async def test_validate_code(self, adapter):
        with patch.object(
            adapter, "_request", new=AsyncMock(return_value=(200, fx.VALIDATE_CODE_OK))
        ) as req:
            result = await adapter.validate_code("snomed|84229001", display="Fatigue")
        params = req.await_args.args[2]
        assert ("url", SNOMED) in params and ("code", "84229001") in params
        assert ("display", "Fatigue") in params
        assert result == {"valid": True, "display": "Fatigue", "message": None}

    @pytest.mark.asyncio
    async def test_validate_code_invalid_and_versioned(self, adapter):
        with patch.object(
            adapter, "_request", new=AsyncMock(return_value=(200, fx.VALIDATE_CODE_BAD))
        ) as req:
            result = await adapter.validate_code("atc|X|2025.0.0")
        assert ("version", "2025.0.0") in req.await_args.args[2]
        assert result["valid"] is False and "Unknown code" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_code_unusable(self, adapter):
        assert await adapter.validate_code("nonsense") is None
        with patch.object(adapter, "_request", new=AsyncMock(return_value=(404, None))):
            assert await adapter.validate_code("snomed|1") is None
        no_result = {"resourceType": "Parameters", "parameter": []}
        with patch.object(adapter, "_request", new=AsyncMock(return_value=(200, no_result))):
            assert await adapter.validate_code("snomed|1") is None
        with patch.object(adapter, "_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.validate_code("snomed|1") is None


# ----------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------


def _inline_route(system, data=None, status=200):
    answer = data if isinstance(data, Exception) else (status, data)
    return (("POST", "ValueSet/$expand", system), answer)


def _implicit_route(system, data=None, status=200):
    answer = data if isinstance(data, Exception) else (status, data)
    return (("GET", "ValueSet/$expand", f"{system}?fhir_vs"), answer)


class TestSearch:
    @pytest.mark.asyncio
    async def test_implicit_value_set_is_used_first(self, adapter):
        srv = server(_implicit_route(SNOMED, fx.EXPAND_SNOMED_FATIGUE))
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("fatigue", limit=5, systems="snomed")
        assert [c.primary_id for c in concepts] == [
            "snomed|84229001",
            "snomed|139126000",
            "snomed|22171002",
        ]
        method, path, params, body = srv.calls[0]
        assert (method, path, body) == ("GET", "ValueSet/$expand", None)
        assert dict(params) == {"url": f"{SNOMED}?fhir_vs", "filter": "fatigue", "count": "5"}
        assert len(srv.calls) == 1

    @pytest.mark.asyncio
    async def test_inline_fallback_and_remembered_mode(self, adapter):
        srv = server(
            _implicit_route(LOINC, fx.OUTCOME_IMPLICIT_VS_MISSING_404, status=404),
            _inline_route(LOINC, fx.EXPAND_LOINC_INLINE),
        )
        with srv.patch(adapter):
            first = await adapter.search_concepts("fatigue", limit=2, systems="loinc")
            second = await adapter.search_concepts("fatigue", limit=2, systems="loinc")
        assert [c.primary_id for c in first] == ["loinc|LA19104-1", "loinc|LA19105-8"]
        assert len(second) == 2
        methods = [c[0] for c in srv.calls]
        assert methods == ["GET", "POST", "POST"]  # the second search skips the doomed GET
        body = srv.calls[1][3]
        assert body["resourceType"] == "Parameters"
        include = body["parameter"][0]["resource"]["compose"]["include"]
        assert include == [{"system": LOINC}]
        assert {"name": "filter", "valueString": "fatigue"} in body["parameter"]
        assert {"name": "count", "valueInteger": 2} in body["parameter"]

    @pytest.mark.asyncio
    async def test_pinned_version_posts_inline_directly(self, adapter):
        gm = "http://fhir.de/CodeSystem/bfarm/icd-10-gm"
        srv = server(_inline_route(gm, fx.EXPAND_ICD10GM_2020))
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("Müdigkeit", systems="icd10gm@2020")
        assert [c.primary_id for c in concepts] == ["icd10gm|G93.3"]
        assert [c[0] for c in srv.calls] == ["POST"]
        include = srv.calls[0][3]["parameter"][0]["resource"]["compose"]["include"][0]
        assert include == {"system": gm, "version": "2020"}

    @pytest.mark.asyncio
    async def test_default_systems_are_interleaved_within_limit(self, adapter):
        srv = server(
            _implicit_route(SNOMED, fx.EXPAND_SNOMED_FATIGUE),
            _implicit_route(ICD10CM, {}, status=422),
            _inline_route(
                ICD10CM,
                {
                    "resourceType": "ValueSet",
                    "expansion": {
                        "contains": [
                            {"system": ICD10CM, "code": "G93.3", "display": "Postviral fatigue"},
                            {"system": ICD10CM, "code": "R53.83", "display": "Other fatigue"},
                        ]
                    },
                },
            ),
            _implicit_route(LOINC, {}, status=422),
            _inline_route(LOINC, fx.EXPAND_LOINC_INLINE),
        )
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("fatigue", limit=5)
        ids = [c.primary_id for c in concepts]
        assert ids[:3] == ["snomed|84229001", "icd10cm|G93.3", "loinc|LA19104-1"]
        assert len(ids) == 5 and len(set(ids)) == 5

    @pytest.mark.asyncio
    async def test_env_systems_are_used(self, adapter, monkeypatch):
        monkeypatch.setenv("FHIR_TERMINOLOGY_SYSTEMS", "snomed")
        srv = server(_implicit_route(SNOMED, fx.EXPAND_SNOMED_FATIGUE))
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("fatigue", limit=2)
        assert len(concepts) == 2 and len(srv.calls) == 1

    @pytest.mark.asyncio
    async def test_inactive_and_designations_in_search_results(self, adapter):
        hpo = "http://purl.obolibrary.org/obo/hp.owl"
        srv = server(_inline_route(hpo, fx.EXPAND_HPO_DESIGNATIONS))
        with srv.patch(adapter):
            (concept,) = await adapter.search_concepts("fatigue", systems="hpo@20201207")
        assert concept.primary_id == "hpo|HP:0012378"
        assert concept.concept_type == "PHENOTYPE"
        assert any(i.source == "HPO" for i in concept.identifiers)
        data = concept.source_data[KnowledgeSource.FHIRTERMINOLOGY]
        assert data["system"] == hpo and data["inactive"] is False

        srv = server(_implicit_route(SNOMED, fx.EXPAND_SNOMED_FATIGUE))
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("fatigue", systems="snomed")
        inactive = [c for c in concepts if "inactive" in c.categories]
        assert [c.primary_id for c in inactive] == ["snomed|139126000"]

    @pytest.mark.asyncio
    async def test_unknown_system_is_skipped(self, adapter):
        srv = server(
            _implicit_route("http://fhir.de/CodeSystem/bfarm/ops", {}, status=422),
            _inline_route("http://fhir.de/CodeSystem/bfarm/ops", {}, status=422),
            _implicit_route(SNOMED, fx.EXPAND_SNOMED_FATIGUE),
        )
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("fatigue", limit=2, systems="ops,snomed")
        assert [c.primary_id for c in concepts] == ["snomed|84229001", "snomed|139126000"]

    @pytest.mark.asyncio
    async def test_auth_failure_does_not_try_inline_fallback(self, adapter, caplog):
        srv = server(_implicit_route(SNOMED, fx.OUTCOME_CODE_NOT_FOUND_404, status=401))
        with srv.patch(adapter), caplog.at_level(logging.WARNING):
            assert await adapter.search_concepts("fatigue", systems="snomed") == []
        assert len(srv.calls) == 1
        assert "requires authentication" in caplog.text

    @pytest.mark.asyncio
    async def test_inline_failure_returns_empty(self, adapter):
        srv = server(
            _implicit_route(SNOMED, {}, status=404), _inline_route(SNOMED, {}, status=500)
        )
        with srv.patch(adapter):
            assert await adapter.search_concepts("fatigue", systems="snomed") == []

    @pytest.mark.asyncio
    async def test_network_errors_return_empty(self, adapter):
        err = RuntimeError("down")
        srv = server(_implicit_route(SNOMED, err))
        with srv.patch(adapter):
            assert await adapter.search_concepts("fatigue", systems="snomed") == []
        srv = server(_inline_route(SNOMED, err))
        with srv.patch(adapter):
            assert await adapter.search_concepts("fatigue", systems="snomed@1") == []

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_empty(self, adapter):
        with patch.object(adapter, "_expand", new=AsyncMock(side_effect=ValueError("boom"))):
            assert await adapter.search_concepts("fatigue", systems="snomed") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), (None, 5), ("fatigue", 0)])
    async def test_empty_query_or_limit(self, adapter, query, limit):
        with patch.object(adapter, "_request", new=AsyncMock()) as req:
            assert await adapter.search_concepts(query, limit=limit) == []
        req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_query_with_system_and_code_returns_that_concept(self, adapter):
        srv = server(_lookup_route(SNOMED, fx.LOOKUP_SNOMED_FATIGUE))
        with srv.patch(adapter):
            concepts = await adapter.search_concepts("snomed|84229001")
        assert [c.primary_id for c in concepts] == ["snomed|84229001"]
        with server(_lookup_route(SNOMED, None, status=404)).patch(adapter):
            assert await adapter.search_concepts("snomed|0000") == []

    @pytest.mark.asyncio
    async def test_count_is_capped(self, adapter):
        srv = server(_implicit_route(SNOMED, fx.EXPAND_SNOMED_FATIGUE))
        with srv.patch(adapter):
            await adapter.search_concepts("fatigue", limit=5000, systems="snomed")
        assert dict(srv.calls[0][2])["count"] == "200"

    def test_expansion_designations_become_unique_synonyms(self, adapter):
        item = {
            "system": SNOMED,
            "code": "1",
            "display": "Fatigue",
            "designation": [{"value": "Tiredness"}, {"value": "Tiredness"}, {"value": "Fatigue"}],
        }
        concept = adapter._convert_expansion_item(item, SystemSpec(SNOMED))
        assert concept.synonyms == ["Tiredness"]

    def test_expansion_item_without_code_is_dropped(self, adapter):
        assert adapter._convert_expansion_item({"display": "x"}, SystemSpec(SNOMED)) is None
        assert adapter._convert_expansion_item("bad", SystemSpec(SNOMED)) is None  # type: ignore


# ----------------------------------------------------------------------
# Details
# ----------------------------------------------------------------------


class TestDetails:
    @pytest.mark.asyncio
    async def test_snomed_details(self, adapter):
        srv = server(_lookup_route(SNOMED, fx.LOOKUP_SNOMED_FATIGUE))
        with srv.patch(adapter):
            concept = await adapter.get_concept_details(f"{SNOMED}|84229001")
        params = srv.calls[0][2]
        assert ("system", SNOMED) in params and ("code", "84229001") in params
        assert [v for k, v in params if k == "property"] == ["*", "parent", "child"]
        assert concept.primary_id == "snomed|84229001"
        assert concept.primary_label == "Fatigue"
        assert concept.concept_type == "SYMPTOM"  # from the "(finding)" semantic tag
        assert concept.semantic_types == ["finding"]
        assert concept.definitions[0].startswith("Fatigue refers to a lack of energy")
        assert "Weariness" in concept.synonyms
        assert "Fatigue (finding)" in concept.synonyms
        assert "Tiredness" not in concept.synonyms  # inactive description
        assert not any(s.startswith("Fatigue refers") for s in concept.synonyms)
        assert concept.parents == ["snomed|359752005", "snomed|105721009"]
        assert "snomed|224960004" in concept.children
        assert {i.source for i in concept.identifiers} == {"FHIRTERMINOLOGY", "SNOMEDCT"}
        assert "system:snomed" in concept.categories
        assert any(c.startswith("version:http://snomed.info/sct/9000") for c in concept.categories)
        data = concept.source_data[KnowledgeSource.FHIRTERMINOLOGY]
        assert data["server"] == "https://tx.fhir.org/r4"
        assert data["parents"][0] == {"code": "359752005", "display": "Energy and stamina finding"}
        assert concept.sources == [KnowledgeSource.FHIRTERMINOLOGY]

    @pytest.mark.asyncio
    async def test_snomed_disorder_type_and_ontoserver_shape(self, adapter):
        srv = server(_lookup_route(SNOMED, fx.LOOKUP_SNOMED_CFS_ONTOSERVER))
        with srv.patch(adapter):
            concept = await adapter.get_concept_details("snomed|52702003")
        assert concept.concept_type == "DISEASE"
        assert concept.semantic_types == ["disorder"]
        # Ontoserver returns parents without names and adds a 'subproperty' group (skipped)
        assert concept.parents == ["snomed|84229001", "snomed|128283000"]
        assert concept.children == []
        assert (
            "609096000" not in concept.source_data[KnowledgeSource.FHIRTERMINOLOGY]["properties"]
        )
        assert "CFS - Chronic fatigue syndrome" in concept.synonyms

    @pytest.mark.asyncio
    async def test_loinc_details_keep_german_and_skip_other_languages(self, adapter):
        srv = server(_lookup_route(LOINC, fx.LOOKUP_LOINC_CHOLESTEROL))
        with srv.patch(adapter):
            concept = await adapter.get_concept_details("loinc|2093-3")
        assert concept.concept_type == "OBSERVATION"
        assert "Cholesterol [Masse/Volumen] in Serum oder Plasma" in concept.synonyms
        assert "Cholest SerPl-mCnc" in concept.synonyms
        assert all(s.isascii() or "ä" in s or "ö" in s for s in concept.synonyms)
        assert {i.source for i in concept.identifiers} == {"FHIRTERMINOLOGY", "LOINC"}
        props = concept.source_data[KnowledgeSource.FHIRTERMINOLOGY]["properties"]
        assert props["EXAMPLE_UNITS"] == ["mg/dL"]
        assert "RELATEDNAMES2" not in props
        assert "parent" not in props

    @pytest.mark.asyncio
    async def test_icd10gm_and_hpo(self, adapter):
        gm = "http://fhir.de/CodeSystem/bfarm/icd-10-gm"
        hpo = "http://purl.obolibrary.org/obo/hp.owl"
        srv = server(
            _lookup_route(gm, fx.LOOKUP_ICD10GM_G933), _lookup_route(hpo, fx.LOOKUP_HPO_FATIGUE)
        )
        with srv.patch(adapter):
            icd = await adapter.get_concept_details("icd10gm|G93.3")
            hp = await adapter.get_concept_details("hpo|HP:0012378")
        assert icd.primary_label == "Chronisches Müdigkeitssyndrom [Chronic fatigue syndrome]"
        assert icd.concept_type == "DISEASE" and icd.parents == ["icd10gm|G93"]
        assert icd.definitions == []  # definition equal to the label is not repeated
        assert any(i.source == "ICD10GM" for i in icd.identifiers)
        assert hp.concept_type == "PHENOTYPE"
        assert len(hp.children) == 4 and hp.parents == ["hpo|HP:0025142"]

    @pytest.mark.asyncio
    async def test_pinned_version_is_sent(self, adapter):
        atc = "http://www.whocc.no/atc"
        srv = server(_lookup_route(atc, fx.LOOKUP_ICD10CM_G9332))
        with srv.patch(adapter):
            await adapter.get_concept_details("atc|N02BA01|2025.0.0")
        assert ("version", "2025.0.0") in srv.calls[0][2]

    @pytest.mark.asyncio
    async def test_inactive_concept_is_flagged(self, adapter):
        data = copy.deepcopy(fx.LOOKUP_ICD10CM_G9332)
        for p in data["parameter"]:
            if p["name"] == "property" and p["part"][0]["valueCode"] == "inactive":
                p["part"][1]["valueBoolean"] = True
        srv = server(_lookup_route(ICD10CM, data))
        with srv.patch(adapter):
            concept = await adapter.get_concept_details("icd10cm|G93.32")
        assert "inactive" in concept.categories

    @pytest.mark.asyncio
    async def test_label_falls_back_to_code(self, adapter):
        data = {"resourceType": "Parameters", "parameter": [{"name": "name", "valueString": "x"}]}
        srv = server(_lookup_route(SNOMED, data))
        with srv.patch(adapter):
            concept = await adapter.get_concept_details("snomed|1")
        assert concept.primary_label == "1" and concept.concept_type == "UNKNOWN"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,body",
        [
            (404, fx.OUTCOME_CODE_NOT_FOUND_404),
            (422, fx.OUTCOME_UNKNOWN_SYSTEM_422),
            (422, fx.OUTCOME_ATC_AMBIGUOUS_422),
            (401, None),
            (200, {"resourceType": "OperationOutcome"}),
            (200, None),
        ],
    )
    async def test_error_answers_give_none(self, adapter, status, body):
        srv = server(_lookup_route(SNOMED, body, status=status))
        with srv.patch(adapter):
            assert await adapter.get_concept_details("snomed|1") is None

    @pytest.mark.asyncio
    async def test_network_error_and_bad_ids(self, adapter):
        srv = server(_lookup_route(SNOMED, RuntimeError("down")))
        with srv.patch(adapter):
            assert await adapter.get_concept_details("snomed|1") is None
        with patch.object(adapter, "_request", new=AsyncMock()) as req:
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("nonsense|1") is None
        req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_conversion_error_gives_none(self, adapter):
        srv = server(_lookup_route(SNOMED, fx.LOOKUP_SNOMED_FATIGUE))
        with (
            srv.patch(adapter),
            patch.object(adapter, "_convert_lookup", side_effect=ValueError("boom")),
        ):
            assert await adapter.get_concept_details("snomed|84229001") is None

    @pytest.mark.asyncio
    async def test_auth_failure_is_logged(self, adapter, caplog):
        srv = server(_lookup_route(SNOMED, None, status=401))
        with srv.patch(adapter), caplog.at_level(logging.WARNING):
            await adapter.get_concept_details("snomed|1")
        assert "FHIR_TERMINOLOGY_TOKEN" in caplog.text


# ----------------------------------------------------------------------
# Relationships and mappings
# ----------------------------------------------------------------------


class TestRelationships:
    @pytest.mark.asyncio
    async def test_is_a_and_has_subtype(self, adapter):
        srv = server(_lookup_route(SNOMED, fx.LOOKUP_SNOMED_FATIGUE))
        with srv.patch(adapter):
            edges = await adapter.get_relationships("snomed|84229001")
        parents = [e for e in edges if e["relation_label"] == "is_a"]
        children = [e for e in edges if e["relation_label"] == "has_subtype"]
        assert [e["related_id"] for e in parents] == ["snomed|359752005", "snomed|105721009"]
        assert parents[0]["related_name"] == "Energy and stamina finding"
        assert len(children) == 5 and children[0]["related_name"] == "Tired"
        assert all(e["source"] == "FHIR terminology" for e in edges)

    @pytest.mark.asyncio
    async def test_edges_without_names_use_the_code_and_dedupe(self, adapter):
        data = copy.deepcopy(fx.LOOKUP_HPO_FATIGUE)
        child = next(
            p
            for p in data["parameter"]
            if p["name"] == "property" and p["part"][0]["valueCode"] == "child"
        )
        data["parameter"].append(copy.deepcopy(child))  # duplicated child
        srv = server(_lookup_route("http://purl.obolibrary.org/obo/hp.owl", data))
        with srv.patch(adapter):
            edges = await adapter.get_relationships("hpo|HP:0012378")
        assert [e["related_id"] for e in edges if e["relation_label"] == "has_subtype"] == [
            "hpo|HP:0030973",
            "hpo|HP:0012431",
            "hpo|HP:0033236",
            "hpo|HP:0012432",
        ]
        assert edges[0]["related_name"] == "HP:0025142"

    @pytest.mark.asyncio
    async def test_relationship_failures(self, adapter):
        assert await adapter.get_relationships("nonsense") == []
        srv = server(_lookup_route(SNOMED, None, status=404))
        with srv.patch(adapter):
            assert await adapter.get_relationships("snomed|1") == []
        srv = server(_lookup_route(SNOMED, fx.LOOKUP_SNOMED_FATIGUE))
        with (
            srv.patch(adapter),
            patch.object(adapter, "_parse_lookup", side_effect=ValueError("x")),
        ):
            assert await adapter.get_relationships("snomed|84229001") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_translate_matches(self, adapter):
        route = (("GET", "ConceptMap/$translate", SNOMED), (200, fx.TRANSLATE_SNOMED_ONTOSERVER))
        srv = server(route)
        with srv.patch(adapter):
            mappings = await adapter.get_mappings("snomed|52702003")
        params = srv.calls[0][2]
        assert ("system", SNOMED) in params and ("code", "52702003") in params
        assert not any(k == "targetsystem" for k, _ in params)
        assert set(mappings[0]) >= {
            "fromId",
            "toId",
            "fromSource",
            "toSource",
            "mappingType",
            "confidence",
        }
        by_id = {(m["toId"], m["conceptMap"]): m for m in mappings}
        am = by_id[
            (
                "http://hl7.org/fhir/sid/icd-10-am|G93.3",
                "http://aehrc.com/fhir/ConceptMap/aehrc-snomap-starter",
            )
        ]
        assert (am["mappingType"], am["confidence"], am["fromId"]) == (
            "broadMatch",
            0.7,
            "snomed|52702003",
        )
        assert am["fromSource"] == "SNOMEDCT"
        meddra = next(m for m in mappings if m["toId"].endswith("mdr|10008874"))
        assert meddra["mappingType"] == "exactMatch" and meddra["toLabel"].startswith("Chronic")
        # the same Read code from three different ConceptMaps is kept per map, not per code
        assert len([m for m in mappings if m["toId"].endswith("Eu46000")]) == 3

    @pytest.mark.asyncio
    async def test_target_system_filter(self, adapter):
        route = (("GET", "ConceptMap/$translate", SNOMED), (200, fx.TRANSLATE_NO_CONCEPTMAP))
        srv = server(route)
        with srv.patch(adapter):
            assert await adapter.get_mappings("snomed|1", target_system="icd10cm") == []
        assert ("targetsystem", ICD10CM) in srv.calls[0][2]
        with patch.object(adapter, "_request", new=AsyncMock()) as req:
            assert await adapter.get_mappings("snomed|1", target_system="nonsense") == []
        req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_version_is_sent(self, adapter):
        route = (("GET", "ConceptMap/$translate", SNOMED), (200, fx.TRANSLATE_NO_CONCEPTMAP))
        srv = server(route)
        with srv.patch(adapter):
            await adapter.get_mappings("snomed|1|20250201")
        assert ("version", "20250201") in srv.calls[0][2]

    @pytest.mark.asyncio
    async def test_r5_relationship_codes_and_skipped_relations(self, adapter):
        def match(relation_name, relation, code, system="http://x.org/cs"):
            return {
                "name": "match",
                "part": [
                    {"name": relation_name, "valueCode": relation},
                    {"name": "concept", "valueCoding": {"system": system, "code": code}},
                ],
            }

        data = {
            "resourceType": "Parameters",
            "parameter": [
                {"name": "result", "valueBoolean": True},
                match("relationship", "source-is-narrower-than-target", "A"),
                match("relationship", "source-is-broader-than-target", "B"),
                match("relationship", "not-related-to", "C"),
                match("equivalence", "disjoint", "D"),
                match("equivalence", "weird", "E", system=""),
                match("equivalence", "weird", "E", system=""),  # same code from the same map
                {"name": "match", "part": [{"name": "equivalence", "valueCode": "equal"}]},
                {"name": "message", "valueString": "ignored"},
            ],
        }
        route = (("GET", "ConceptMap/$translate", SNOMED), (200, data))
        srv = server(route)
        with srv.patch(adapter):
            mappings = await adapter.get_mappings("snomed|1")
        assert [(m["toId"], m["mappingType"]) for m in mappings] == [
            ("http://x.org/cs|A", "broadMatch"),
            ("http://x.org/cs|B", "narrowMatch"),
            ("E", "relatedMatch"),
        ]

    @pytest.mark.asyncio
    async def test_mapping_failures(self, adapter):
        assert await adapter.get_mappings("nonsense") == []
        route = (("GET", "ConceptMap/$translate", SNOMED), (404, None))
        srv = server(route)
        with srv.patch(adapter):
            assert await adapter.get_mappings("snomed|1") == []
        srv = server((("GET", "ConceptMap/$translate", SNOMED), RuntimeError("x")))
        with srv.patch(adapter):
            assert await adapter.get_mappings("snomed|1") == []
        bad = {"resourceType": "Parameters", "parameter": [{"name": "match", "part": "oops"}]}
        srv = server((("GET", "ConceptMap/$translate", SNOMED), (200, bad)))
        with srv.patch(adapter):
            assert await adapter.get_mappings("snomed|1") == []


class TestOutcomeText:
    def test_outcome_text_variants(self):
        f = FHIRTerminologyAdapter._outcome_text
        assert f(None) == ""
        assert f({"issue": []}) == ""
        assert f({"issue": [{"details": {"text": "boom"}}]}) == "boom"
        assert f({"issue": [{"diagnostics": "diag"}]}) == "diag"
        assert f({"issue": [{"severity": "info"}]}) == ""
