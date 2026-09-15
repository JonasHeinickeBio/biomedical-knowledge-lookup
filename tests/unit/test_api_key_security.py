"""
Regression tests: API keys must never end up in request URLs or in log output.

HTTP client errors embed the request URL, so a key sent as a query parameter
leaks into every log line that formats the exception.
"""

import logging
from unittest.mock import AsyncMock, patch
from urllib.parse import quote

import aiohttp
import pytest

from knowledge_lookup.adapters.bioontology_adapter import BioOntologyAdapter
from knowledge_lookup.adapters.bioportal_adapter import BioPortalAdapter, infer_bioportal_ontology
from knowledge_lookup.adapters.omim_adapter import OMIMAdapter
from knowledge_lookup.adapters.umls_adapter import UMLSAdapter
from knowledge_lookup.base import KnowledgeSourceAdapter
from knowledge_lookup.models import LookupConfig

pytestmark = pytest.mark.unit

KEY = "sekret-test-key-123"
AUTH = {"Authorization": f"apikey token={KEY}"}


def _request_parts(call) -> tuple[str, dict, dict]:
    """(url, params, headers) of one recorded `_make_request(url, params, headers)` call."""
    bound = dict(zip(["url", "params", "headers", "json_data"], call.args, strict=False))
    bound.update(call.kwargs)
    return bound.get("url", ""), bound.get("params") or {}, bound.get("headers") or {}


def _assert_key_only_in_header(call) -> None:
    url, params, headers = _request_parts(call)
    assert KEY not in url
    assert KEY not in str(params)
    assert headers.get("Authorization") == AUTH["Authorization"]


# ---------------------------------------------------------------------------
# BioPortal
# ---------------------------------------------------------------------------


@pytest.fixture
def bioportal():
    return BioPortalAdapter(LookupConfig(api_keys={"bioportal": KEY}))


@pytest.mark.asyncio
async def test_bioportal_search_sends_key_in_header_only(bioportal):
    bioportal._make_request = AsyncMock(return_value={"collection": []})

    await bioportal.search_concepts("asthma")

    _assert_key_only_in_header(bioportal._make_request.await_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("iri", "acronym"),
    [
        ("http://purl.bioontology.org/ontology/MESH/D003924", "MESH"),
        ("http://purl.bioontology.org/ontology/LNC/LA10552-0", "LOINC"),
        ("http://purl.obolibrary.org/obo/DOID_9352", "DOID"),
    ],
)
async def test_bioportal_details_url_uses_acronym_and_encoded_iri(bioportal, iri, acronym):
    bioportal._make_request = AsyncMock(return_value={"@id": iri, "prefLabel": "x"})

    concept = await bioportal.get_concept_details(iri)

    call = bioportal._make_request.await_args
    url, _, _ = _request_parts(call)
    assert url == (
        f"https://data.bioontology.org/ontologies/{acronym}/classes/{quote(iri, safe='')}"
    )
    assert concept is not None
    _assert_key_only_in_header(call)


@pytest.mark.asyncio
async def test_bioportal_details_accepts_explicit_ontology_and_self_links(bioportal):
    bioportal._make_request = AsyncMock(return_value={"@id": "x", "prefLabel": "x"})
    iri = "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#C2985"

    await bioportal.get_concept_details(iri, ontology="NCIT")
    self_link = f"https://data.bioontology.org/ontologies/NCIT/classes/{quote(iri, safe='')}"
    await bioportal.get_concept_details(self_link)

    urls = [_request_parts(call)[0] for call in bioportal._make_request.await_args_list]
    assert urls == [self_link, self_link]


def test_infer_bioportal_ontology():
    assert infer_bioportal_ontology("http://purl.bioontology.org/ontology/SNOMEDCT/73211009") == (
        "SNOMEDCT"
    )
    assert infer_bioportal_ontology("http://purl.obolibrary.org/obo/hp_0001250") == "HP"
    assert infer_bioportal_ontology("http://example.org/thing/1") is None


@pytest.mark.asyncio
async def test_bioportal_error_logs_are_redacted(bioportal, caplog):
    bioportal._make_request = AsyncMock(
        side_effect=aiohttp.ClientError(
            f"401, url='https://data.bioontology.org/search?apikey={KEY}'"
        )
    )

    with caplog.at_level(logging.DEBUG):
        await bioportal.search_concepts("asthma")
        await bioportal.get_concept_details("http://purl.obolibrary.org/obo/DOID_9352")

    assert "BioPortal search failed" in caplog.text
    assert KEY not in caplog.text


# ---------------------------------------------------------------------------
# BioOntology
# ---------------------------------------------------------------------------


@pytest.fixture
def bioontology():
    return BioOntologyAdapter(LookupConfig(api_keys={"bioontology": KEY}))


@pytest.mark.asyncio
async def test_bioontology_requests_carry_key_in_header_only(bioontology):
    base = AsyncMock(return_value={"collection": []})
    with patch.object(KnowledgeSourceAdapter, "_make_request", new=base):
        await bioontology.search_concepts("asthma")
        await bioontology.annotate("asthma attack")
        await bioontology.fetch_api_endpoints()
        await bioontology.get_concept_details(
            "http://purl.obolibrary.org/obo/DOID_9352", fetch_related=False
        )
        # a caller-supplied apikey parameter is stripped as well
        await bioontology._make_request("https://data.bioontology.org/x", {"apikey": KEY})

    assert base.await_count == 5
    for call in base.await_args_list:
        _assert_key_only_in_header(call)
    detail_url = _request_parts(base.await_args_list[3])[0]
    assert "/ontologies/DOID/classes/" in detail_url  # ontology inferred from the IRI


@pytest.mark.asyncio
async def test_bioontology_does_not_log_params_headers_or_keys(bioontology, caplog):
    failure = aiohttp.ClientError(f"404, url='https://data.bioontology.org/x?apikey={KEY}'")
    with (
        patch.object(KnowledgeSourceAdapter, "_make_request", new=AsyncMock(side_effect=failure)),
        caplog.at_level(logging.DEBUG),
    ):
        await bioontology.search_concepts("asthma")
        await bioontology.get_analytics(month=1, year=2026)

    assert "API request failed" in caplog.text
    assert KEY not in caplog.text


@pytest.mark.asyncio
async def test_bioontology_batch_annotate_annotates_every_text(bioontology):
    bioontology.annotate = AsyncMock(side_effect=lambda text, **_: [{"text": text}])

    result = await bioontology.batch_annotate(["asthma", "melanoma"], ontologies="MESH")

    assert result == [[{"text": "asthma"}], [{"text": "melanoma"}]]
    assert bioontology.annotate.await_args_list[1].kwargs["ontologies"] == "MESH"


@pytest.mark.asyncio
async def test_bioontology_get_analytics_sends_its_filters(bioontology):
    base = AsyncMock(return_value={})
    with patch.object(KnowledgeSourceAdapter, "_make_request", new=base):
        await bioontology.get_analytics(ontology="MESH", month=3, year=2026)

    _, params, _ = _request_parts(base.await_args)
    assert params["ontology"] == "MESH" and params["month"] == 3 and params["year"] == 2026


# ---------------------------------------------------------------------------
# OMIM (key stays a query parameter, so logs must be redacted)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_omim_error_logs_are_redacted(caplog):
    adapter = OMIMAdapter(LookupConfig(api_keys={"omim": KEY}))
    adapter._make_request = AsyncMock(
        side_effect=aiohttp.ClientError(f"400, url='https://api.omim.org/api/entry?apiKey={KEY}'")
    )

    with caplog.at_level(logging.DEBUG):
        await adapter.search_concepts("huntington")
        await adapter.get_concept_details("OMIM:143100")

    assert "OMIM search failed" in caplog.text
    assert KEY not in caplog.text


# ---------------------------------------------------------------------------
# LookupConfig.get_api_key and UMLS key lookup
# ---------------------------------------------------------------------------


def test_get_api_key_never_hands_one_string_key_to_every_service(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    # Another module may already have loaded a real .env into os.environ
    for service in ("omim", "bioportal"):
        monkeypatch.delenv(f"{service.upper()}_API_KEY", raising=False)
        monkeypatch.delenv(f"{service}_api_key", raising=False)
    config = LookupConfig()

    # Compare booleans only, so a failure can never print a real key
    object.__setattr__(config, "api_keys", "a-bioportal-key")  # generated str field
    assert (config.get_api_key("omim") is None) is True

    object.__setattr__(config, "api_keys", '{"omim": "omim-key"}')
    assert (config.get_api_key("omim") == "omim-key") is True
    assert (config.get_api_key("bioportal") is None) is True


def test_umls_adapter_reads_legacy_umls_api_key_tu(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key

    monkeypatch.setattr(LookupConfig, "get_api_key", lambda self, service: None)
    monkeypatch.setattr(UMLSAdapter, "_get_client_class", lambda self: FakeClient)
    monkeypatch.setenv("UMLS_API_KEY_TU", "legacy-umls-key")

    adapter = UMLSAdapter(LookupConfig())

    assert captured["api_key"] == "legacy-umls-key"
    assert adapter.is_available()
