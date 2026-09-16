"""
Unit tests for the MCP server (``knowledge_lookup.mcp_server``).

Tools, resources and prompts are exercised through the SDK's in-memory
``Client`` against a server whose ``CentralKnowledgeLookup`` is replaced by a
fake, so nothing touches the network.
"""

import json
from typing import get_args
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import Client

from knowledge_lookup.adapters import ADAPTER_CLASSES
from knowledge_lookup.core.term_expansion import ExpansionTrace
from knowledge_lookup.mcp_server import server as server_module
from knowledge_lookup.mcp_server.server import (
    CHARACTER_LIMIT,
    ServerSettings,
    _parse_args,
    create_server,
    settings_from_args,
)
from knowledge_lookup.mcp_server.sources import (
    DEFAULT_SEARCH_SOURCES,
    SOURCE_CATALOG,
    SourceName,
    route_identifier,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupResult, UnifiedConcept

pytestmark = pytest.mark.unit

KS = KnowledgeSource


def _concept(
    concept_id,
    label,
    *,
    score=0.9,
    source=KS.OLS,
    concept_type=ConceptType.DISEASE,
    definitions=None,
    synonyms=None,
    identifiers=(),
):
    concept = UnifiedConcept(
        primary_id=concept_id,
        primary_label=label,
        concept_type=concept_type,
        confidence_score=score,
        definitions=definitions or [],
        synonyms=synonyms or [],
    )
    concept.sources = [source]
    for ident_source, ident in identifiers:
        concept.add_identifier(ident_source, ident)
    return concept


class FakeLookup:
    """Stands in for CentralKnowledgeLookup; ``results`` maps query -> concepts."""

    def __init__(self, available=(KS.OLS, KS.MONDO, KS.HPO, KS.HGNC, KS.UNIPROT, KS.OXO)):
        self.adapters = {}
        for source in available:
            adapter = MagicMock(name=source.value)
            adapter.get_concept_details = AsyncMock(return_value=None)
            adapter.get_mappings_for_concepts = AsyncMock(return_value={})
            self.adapters[source] = adapter
        self.results: dict[str, list] = {}
        self.errors: dict[str, str] = {}
        self.search_concepts = AsyncMock(side_effect=self._search)
        self.get_concept_details = AsyncMock(return_value=None)
        self.health_tracker = MagicMock()
        self.health_tracker.get_health.return_value = None
        self.close = AsyncMock()

    async def _search(self, query, concept_types=None, sources=None, max_results=50):
        result = LookupResult(
            query=query, concepts=list(self.results.get(query, []))[:max_results]
        )
        for source, message in self.errors.items():
            result.add_error(source, message)
        return result


@pytest.fixture
def fake():
    return FakeLookup()


@pytest.fixture
def server(fake):
    return create_server(ServerSettings(), lookup_factory=lambda _settings: fake)


async def _call(server, tool, arguments=None):
    async with Client(server) as client:
        return await client.call_tool(tool, arguments or {})


def _text(result) -> str:
    return result.content[0].text


# ---------------------------------------------------------------------------
# Tool listing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tools_are_read_only_with_input_and_output_schemas(server):
    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        instructions = client.instructions

    assert set(tools) == {
        "biomed_search_concepts",
        "biomed_get_concept",
        "biomed_find_mappings",
        "biomed_list_sources",
        "biomed_validate_curie",
    }
    for tool in tools.values():
        assert tool.description and tool.title
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True
        assert "properties" in tool.output_schema
        assert "ctx" not in tool.input_schema.get("properties", {})

    assert tools["biomed_search_concepts"].input_schema["required"] == ["query"]
    assert tools["biomed_search_concepts"].annotations.open_world_hint is True
    assert tools["biomed_validate_curie"].annotations.open_world_hint is False
    assert "biomed_search_concepts" in instructions


# ---------------------------------------------------------------------------
# biomed_search_concepts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_ranked_concise_page_with_text_mirror(server, fake):
    fake.results["seizure"] = [
        _concept(
            "HP:0001250",
            "Seizure",
            score=0.7,
            source=KS.HPO,
            definitions=["A seizure is an intermittent abnormality of nervous system physiology."],
            synonyms=["Seizure", "Seizures", "Epileptic seizure"],
        ),
        _concept(
            "MONDO:0005027",
            "epilepsy",
            score=0.95,
            source=KS.MONDO,
            identifiers=[(KS.OLS, "DOID:1826")],
        ),
    ]

    result = await _call(
        server, "biomed_search_concepts", {"query": "seizure", "sources": ["hpo", "Mondo"]}
    )

    assert not result.is_error, _text(result)
    data = result.structured_content
    assert [c["id"] for c in data["concepts"]] == ["MONDO:0005027", "HP:0001250"]
    assert data["total"] == 2 and data["count"] == 2 and data["has_more"] is False
    assert data["sources_searched"] == ["HPO", "MONDO"]
    seizure = data["concepts"][1]
    assert seizure["synonyms"] == ["Seizures", "Epileptic seizure"]  # label itself dropped
    assert seizure["definition"].startswith("A seizure")
    assert "xrefs" not in data["concepts"][0]  # concise format
    assert "source_errors" not in data  # empty fields are omitted
    assert json.loads(_text(result)) == data

    kwargs = fake.search_concepts.await_args.kwargs
    assert kwargs["sources"] == [KS.HPO, KS.MONDO]
    assert kwargs["max_results"] == 10


@pytest.mark.asyncio
async def test_search_detailed_includes_xrefs(server, fake):
    fake.results["epilepsy"] = [
        _concept(
            "MONDO:0005027",
            "epilepsy",
            identifiers=[(KS.OLS, "DOID:1826")],
            definitions=["def one", "def two"],
        )
    ]

    result = await _call(
        server, "biomed_search_concepts", {"query": "epilepsy", "response_format": "detailed"}
    )

    concept = result.structured_content["concepts"][0]
    assert concept["definitions"] == ["def one", "def two"]
    assert {"id": "DOID:1826", "source": "OLS", "label": "epilepsy"} in concept["xrefs"]


@pytest.mark.asyncio
async def test_search_defaults_to_available_default_sources(server, fake):
    await _call(server, "biomed_search_concepts", {"query": "BRCA1"})

    expected = [s for s in DEFAULT_SEARCH_SOURCES if s in fake.adapters]
    assert fake.search_concepts.await_args.kwargs["sources"] == expected


@pytest.mark.asyncio
async def test_search_passes_concept_type_filter(server, fake):
    await _call(server, "biomed_search_concepts", {"query": "x", "concept_types": ["disease"]})

    assert fake.search_concepts.await_args.kwargs["concept_types"] == [ConceptType.DISEASE]


@pytest.mark.asyncio
async def test_search_skips_unavailable_sources_with_warning(server, fake):
    result = await _call(
        server, "biomed_search_concepts", {"query": "x", "sources": ["HPO", "UMLS"]}
    )

    data = result.structured_content
    assert data["sources_searched"] == ["HPO"]
    assert any("UMLS requires" in w and "UMLS_API_KEY" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_search_errors_when_no_requested_source_is_available(server):
    result = await _call(server, "biomed_search_concepts", {"query": "x", "sources": ["UMLS"]})

    assert result.is_error
    assert "Available sources" in _text(result) and "HPO" in _text(result)


@pytest.mark.asyncio
async def test_search_rejects_unknown_source_name(server):
    result = await _call(server, "biomed_search_concepts", {"query": "x", "sources": ["NOPE"]})

    assert result.is_error
    assert "validation error" in _text(result)


@pytest.mark.asyncio
async def test_search_reports_partial_source_failures(server, fake):
    fake.results["asthma"] = [_concept("MONDO:0004979", "asthma", source=KS.MONDO)]
    fake.errors = {"HPO": "Timed out after 15.0s"}

    result = await _call(
        server, "biomed_search_concepts", {"query": "asthma", "sources": ["HPO", "MONDO"]}
    )

    assert not result.is_error
    assert result.structured_content["source_errors"] == {"HPO": "Timed out after 15.0s"}


@pytest.mark.asyncio
async def test_search_paginates_from_cached_upstream_search(server, fake):
    fake.results["gene"] = [
        _concept(f"HGNC:{i}", f"gene {i:02d}", score=1 - i / 100, source=KS.HGNC)
        for i in range(15)
    ]
    args = {"query": "gene", "sources": ["HGNC", "HPO"], "limit": 5}

    async with Client(server) as client:
        first = (await client.call_tool("biomed_search_concepts", args)).structured_content
        second = (
            await client.call_tool("biomed_search_concepts", {**args, "offset": 5})
        ).structured_content
        assert fake.search_concepts.await_count == 1  # page 2 served from the cache
        third = (
            await client.call_tool("biomed_search_concepts", {**args, "offset": 10})
        ).structured_content

    assert fake.search_concepts.await_count == 2  # page 3 needed a deeper search
    assert first["has_more"] and first["next_offset"] == 5
    assert [c["id"] for c in second["concepts"]] == [f"HGNC:{i}" for i in range(5, 10)]
    assert [c["id"] for c in third["concepts"]] == [f"HGNC:{i}" for i in range(10, 15)]


@pytest.mark.asyncio
async def test_search_without_results_warns_and_is_not_cached(server, fake):
    async with Client(server) as client:
        result = await client.call_tool("biomed_search_concepts", {"query": "zzz"})
        await client.call_tool("biomed_search_concepts", {"query": "zzz"})

    assert result.structured_content["concepts"] == []
    assert any("No concepts matched" in w for w in result.structured_content["warnings"])
    assert fake.search_concepts.await_count == 2


@pytest.mark.asyncio
async def test_search_truncates_oversized_pages(server, fake):
    long_definition = "word " * 280
    fake.results["big"] = [
        _concept(
            f"HP:{i:07d}",
            f"term {i}",
            score=1 - i / 100,
            source=KS.HPO,
            definitions=[f"{long_definition}{j}" for j in range(3)],
        )
        for i in range(50)
    ]

    result = await _call(
        server,
        "biomed_search_concepts",
        {"query": "big", "sources": ["HPO"], "limit": 50, "response_format": "detailed"},
    )

    data = result.structured_content
    assert len(_text(result)) <= CHARACTER_LIMIT
    assert 0 < data["count"] < 50
    assert data["has_more"] and data["next_offset"] == data["count"]
    assert any("Truncated" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_search_expand_synonyms_reports_expanded_terms(server, fake):
    expanded = LookupResult(
        query="COPD", concepts=[_concept("MONDO:0005002", "chronic obstructive pulmonary disease")]
    )
    trace = ExpansionTrace(
        run_id=None,
        rounds_run=2,
        stop_reason="fixed_point",
        terms_by_round=[["COPD"], ["chronic obstructive pulmonary disease"]],
    )
    with patch.object(
        server_module, "expand_and_search", AsyncMock(return_value=(expanded, trace))
    ) as mock:
        result = await _call(
            server, "biomed_search_concepts", {"query": "COPD", "expand_synonyms": True}
        )

    data = result.structured_content
    assert data["expanded_terms"] == ["chronic obstructive pulmonary disease"]
    assert data["concepts"][0]["id"] == "MONDO:0005002"
    assert mock.await_args.kwargs["persist"] is False
    fake.search_concepts.assert_not_awaited()


# ---------------------------------------------------------------------------
# biomed_get_concept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_concept_routes_curie_to_owning_source(server, fake):
    seizure = _concept("HP:0001250", "Seizure", source=KS.HPO, identifiers=[(KS.UMLS, "C0036572")])
    fake.adapters[KS.HPO].get_concept_details = AsyncMock(
        side_effect=lambda cid: seizure if cid == "HP:0001250" else None
    )

    result = await _call(server, "biomed_get_concept", {"concept_id": " HP:0001250 "})

    assert not result.is_error, _text(result)
    data = result.structured_content
    assert data["id"] == "HP:0001250" and data["resolved_via"] == "HPO"
    assert data["xrefs"][0]["id"] == "C0036572"
    fake.search_concepts.assert_not_awaited()  # routed directly, no search fallback


@pytest.mark.asyncio
async def test_get_concept_routes_bare_accession(server, fake):
    protein = _concept(
        "P38398", "BRCA1_HUMAN", source=KS.UNIPROT, concept_type=ConceptType.PROTEIN
    )
    fake.adapters[KS.UNIPROT].get_concept_details = AsyncMock(return_value=protein)

    result = await _call(server, "biomed_get_concept", {"concept_id": "P38398"})

    assert result.structured_content["resolved_via"] == "UNIPROT"
    fake.adapters[KS.UNIPROT].get_concept_details.assert_awaited_with("P38398")


@pytest.mark.asyncio
async def test_get_concept_not_found_is_an_actionable_error(server, fake):
    result = await _call(server, "biomed_get_concept", {"concept_id": "HP:9999999"})

    assert result.is_error
    assert "biomed_search_concepts" in _text(result)
    # routed sources failed -> exact-ID search in OLS, never the all-adapter fan-out
    assert fake.search_concepts.await_args.kwargs["sources"] == [KS.OLS]
    fake.get_concept_details.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_concept_falls_back_to_exact_id_search_in_ols(server, fake):
    fake.results["EFO:0000400"] = [
        _concept("EFO_0000401", "not it", score=0.99),
        _concept("EFO_0000400", "diabetes mellitus", score=0.5),
    ]

    result = await _call(server, "biomed_get_concept", {"concept_id": "EFO:0000400"})

    data = result.structured_content
    assert data["id"] == "EFO:0000400"  # OLS underscore form shown as a CURIE
    assert data["label"] == "diabetes mellitus"
    assert data["resolved_via"] == "OLS"


@pytest.mark.asyncio
async def test_get_concept_with_unavailable_forced_source(server):
    result = await _call(
        server, "biomed_get_concept", {"concept_id": "C0011849", "source": "umls"}
    )

    assert result.is_error
    assert "UMLS_API_KEY" in _text(result)


# ---------------------------------------------------------------------------
# biomed_find_mappings
# ---------------------------------------------------------------------------


def _diabetes_fixture(fake):
    fake.adapters[KS.MONDO].get_concept_details = AsyncMock(
        return_value=_concept(
            "MONDO:0005148",
            "type 2 diabetes mellitus",
            source=KS.MONDO,
            identifiers=[(KS.UMLS, "C0011860")],
        )
    )
    fake.adapters[KS.OXO].get_mappings_for_concepts = AsyncMock(
        return_value={
            "MONDO:0005148": [
                {
                    "curie": "NCIT:C26747",
                    "label": "Type 2 Diabetes Mellitus",
                    "targetPrefix": "NCIT",
                    "distance": 2,
                },
                {
                    "curie": "MESH:D003924",
                    "label": "Diabetes Mellitus, Type 2",
                    "targetPrefix": "MESH",
                    "distance": 1,
                },
                {"curie": "UMLS:C0011860", "label": "dup", "targetPrefix": "UMLS", "distance": 1},
            ]
        }
    )


@pytest.mark.asyncio
async def test_find_mappings_merges_concept_xrefs_with_oxo(server, fake):
    _diabetes_fixture(fake)

    result = await _call(server, "biomed_find_mappings", {"concept_id": "MONDO:0005148"})

    data = result.structured_content
    assert data["label"] == "type 2 diabetes mellitus"
    assert [m["id"] for m in data["mappings"]] == [
        "C0011860",
        "MESH:D003924",
        "UMLS:C0011860",
        "NCIT:C26747",
    ]
    assert fake.adapters[KS.OXO].get_mappings_for_concepts.await_args.kwargs["distance"] == 1


@pytest.mark.asyncio
async def test_find_mappings_filters_by_target_prefix(server, fake):
    _diabetes_fixture(fake)

    result = await _call(
        server,
        "biomed_find_mappings",
        {"concept_id": "MONDO:0005148", "target_prefixes": ["mesh"]},
    )

    assert [m["id"] for m in result.structured_content["mappings"]] == ["MESH:D003924"]


@pytest.mark.asyncio
async def test_find_mappings_unknown_concept_errors_without_fanout(server, fake):
    result = await _call(server, "biomed_find_mappings", {"concept_id": "MONDO:9999999"})

    assert result.is_error
    fake.get_concept_details.assert_not_awaited()


# ---------------------------------------------------------------------------
# biomed_list_sources / biomed_validate_curie
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sources_reports_availability_and_requirements(server, fake):
    open_breaker = MagicMock()
    open_breaker.circuit_state.value = "OPEN"
    fake.health_tracker.get_health.side_effect = lambda s: open_breaker if s is KS.HPO else None

    result = await _call(server, "biomed_list_sources")

    data = result.structured_content
    by_name = {s["name"]: s for s in data["sources"]}
    assert data["available_count"] == len(fake.adapters)
    assert set(by_name) == {s.value for s in SOURCE_CATALOG}
    assert by_name["UMLS"]["available"] is False and "UMLS_API_KEY" in by_name["UMLS"]["requires"]
    assert by_name["HPO"]["in_default_search"] is True
    assert by_name["HPO"]["circuit_state"] == "open"
    assert data["sources"][0]["available"] is True  # available sources listed first


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        (
            "hp:0001250",
            {
                "valid": True,
                "curie": "HP:0001250",
                "resolvable_via": "HPO",
                "uri": "http://purl.obolibrary.org/obo/HP_0001250",
            },
        ),
        (
            "http://purl.obolibrary.org/obo/MONDO_0005148",
            {"valid": True, "curie": "MONDO:0005148"},
        ),
        ("MONDO:5148", {"valid": False, "curie": "MONDO:5148"}),
        ("foo:bar", {"valid": False}),
        ("P38398", {"valid": False, "resolvable_via": "UNIPROT"}),
    ],
)
async def test_validate_curie(server, identifier, expected):
    pytest.importorskip("bioregistry")

    result = await _call(server, "biomed_validate_curie", {"identifier": identifier})

    data = result.structured_content
    assert {k: data.get(k) for k in expected} == expected
    if not data["valid"]:
        assert data["message"]


# ---------------------------------------------------------------------------
# Resources and prompts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resources_expose_sources_and_concepts(server, fake):
    fake.adapters[KS.HPO].get_concept_details = AsyncMock(
        return_value=_concept("HP:0001250", "Seizure", source=KS.HPO)
    )

    async with Client(server) as client:
        static = [str(r.uri) for r in (await client.list_resources()).resources]
        templates = [
            t.uri_template for t in (await client.list_resource_templates()).resource_templates
        ]
        concept = await client.read_resource("biomed://concept/HP:0001250")
        sources = await client.read_resource("biomed://sources")

    assert "biomed://sources" in static
    assert "biomed://concept/{concept_id}" in templates
    assert json.loads(concept.contents[0].text)["label"] == "Seizure"
    assert json.loads(sources.contents[0].text)["available_count"] == len(fake.adapters)


@pytest.mark.asyncio
async def test_prompts_embed_arguments(server):
    async with Client(server) as client:
        names = {p.name for p in (await client.list_prompts()).prompts}
        prompt = await client.get_prompt("normalize_terms", {"terms": "seizure, T2D"})

    assert names == {"normalize_terms", "annotate_text"}
    assert "seizure, T2D" in prompt.messages[0].content.text


# ---------------------------------------------------------------------------
# Lifecycle, routing and configuration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backend_start_failure_is_reported_and_retried(fake):
    calls = []

    def flaky_factory(_settings):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("adapter boom")
        return fake

    server = create_server(ServerSettings(), lookup_factory=flaky_factory)
    async with Client(server) as client:
        failed = await client.call_tool("biomed_list_sources", {})
        recovered = await client.call_tool("biomed_list_sources", {})

    assert failed.is_error and "failed to start" in _text(failed)
    assert not recovered.is_error
    assert len(calls) == 2
    fake.close.assert_awaited()


@pytest.mark.parametrize(
    ("identifier", "first", "contains"),
    [
        (
            "HP:0001250",
            (KS.HPO, "HP:0001250"),
            (KS.OLS, "http://purl.obolibrary.org/obo/HP_0001250"),
        ),
        ("UniProtKB:P38398", (KS.UNIPROT, "P38398"), None),
        ("CHEBI:15365", (KS.OLS, "http://purl.obolibrary.org/obo/CHEBI_15365"), None),
        ("C0011849", (KS.UMLS, "C0011849"), None),
        ("R-HSA-1640170", (KS.REACTOME, "R-HSA-1640170"), None),
        ("ENSG00000012048", (KS.ENSEMBL, "ENSG00000012048"), None),
        (
            "http://purl.obolibrary.org/obo/MONDO_0005148",
            (KS.OLS, "http://purl.obolibrary.org/obo/MONDO_0005148"),
            None,
        ),
    ],
)
def test_route_identifier(identifier, first, contains):
    routes = route_identifier(identifier)

    assert routes[0] == first
    if contains:
        assert contains in routes


def test_route_identifier_unknown_shape_has_no_routes():
    assert route_identifier("not an identifier") == []


def test_route_identifier_sends_each_adapter_its_id_form():
    assert (KS.HPO, "0001250") not in route_identifier("HP:0001250")
    assert route_identifier("UMLS:C0011849") == [(KS.UMLS, "C0011849")]
    # DOID maps to OLS, which only resolves IRIs
    assert route_identifier("DOID:9351") == [(KS.OLS, "http://purl.obolibrary.org/obo/DOID_9351")]


def test_display_id_uses_curie_form_for_obo_style_ids():
    from knowledge_lookup.mcp_server.schemas import display_id

    assert display_id("MONDO_0005148") == "MONDO:0005148"
    assert display_id("http://purl.obolibrary.org/obo/HP_0001250") == "HP:0001250"
    assert display_id("http://www.ebi.ac.uk/efo/EFO_0000400") == "EFO:0000400"
    assert display_id("R-HSA-1640170") == "R-HSA-1640170"
    assert (
        display_id("http://dbpedia.org/resource/Foo_123") == "http://dbpedia.org/resource/Foo_123"
    )


@pytest.mark.asyncio
async def test_get_concept_matches_ols_iri_results_by_short_form(server, fake):
    fake.results["EFO:0000400"] = [
        _concept(
            "http://www.ebi.ac.uk/efo/EFO_0000400",
            "diabetes mellitus",
            identifiers=[(KS.OLS, "EFO_0000400")],
        )
    ]

    result = await _call(server, "biomed_get_concept", {"concept_id": "EFO:0000400"})

    data = result.structured_content
    assert data["id"] == "EFO:0000400" and data["resolved_via"] == "OLS"


# ---------------------------------------------------------------------------
# Thread isolation for adapters that block the event loop
# ---------------------------------------------------------------------------


class _BlockingAdapter:
    """Mimics an adapter calling a synchronous client inside a coroutine."""

    source = KS.CHEMBL

    def __init__(self):
        self.closed = False

    def get_rate_limit(self):
        return 2.0

    async def search_concepts(self, query, limit=20):
        import time

        time.sleep(0.6)
        return [query]

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_threaded_adapter_keeps_blocking_calls_off_the_event_loop():
    import asyncio
    import time

    from knowledge_lookup.mcp_server.isolation import ThreadedAdapter

    adapter = _BlockingAdapter()
    wrapped = ThreadedAdapter(adapter)
    try:
        started = time.monotonic()
        search = asyncio.ensure_future(wrapped.search_concepts("aspirin", 5))
        await asyncio.sleep(0.01)
        loop_stall = time.monotonic() - started
        assert await search == ["aspirin"]
        assert loop_stall < 0.3  # the loop kept running while the adapter blocked for 0.6s
        assert wrapped.get_rate_limit() == 2.0  # plain attributes pass through
    finally:
        await wrapped.close()

    assert adapter.closed
    wrapped._thread.join(timeout=2)
    assert not wrapped._thread.is_alive()


@pytest.mark.asyncio
async def test_threaded_adapter_timeouts_fire_while_the_adapter_blocks():
    import asyncio

    from knowledge_lookup.mcp_server.isolation import ThreadedAdapter

    wrapped = ThreadedAdapter(_BlockingAdapter())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(wrapped.search_concepts("slow"), timeout=0.05)
    finally:
        await wrapped.close()


def test_build_lookup_isolates_blocking_adapters():
    import asyncio

    from knowledge_lookup.mcp_server.isolation import ThreadedAdapter

    hpo = MagicMock()
    lookup = MagicMock()
    lookup.adapters = {KS.CHEMBL: _BlockingAdapter(), KS.HPO: hpo}
    with patch.object(server_module, "CentralKnowledgeLookup", return_value=lookup) as cls:
        built = server_module._build_lookup(ServerSettings(timeout_per_source=7.0))

    assert cls.call_args.args[0].timeout_per_source == 7.0
    assert isinstance(built.adapters[KS.CHEMBL], ThreadedAdapter)
    assert built.adapters[KS.HPO] is hpo
    asyncio.run(built.adapters[KS.CHEMBL].close())


def test_source_names_cover_every_adapter():
    names = set(get_args(SourceName))
    assert names == {s.value for s in SOURCE_CATALOG}
    assert {s.value for s in ADAPTER_CLASSES} <= names
    assert set(DEFAULT_SEARCH_SOURCES) <= set(SOURCE_CATALOG)


def test_settings_from_env():
    settings = ServerSettings.from_env(
        {
            "KNOWLEDGE_LOOKUP_MCP_DEFAULT_SOURCES": "hpo, go",
            "KNOWLEDGE_LOOKUP_MCP_ENABLED_SOURCES": "HPO,GENEONTOLOGY,OXO",
            "KNOWLEDGE_LOOKUP_MCP_TIMEOUT": "5",
            "KNOWLEDGE_LOOKUP_MCP_PERSIST_EXPANSIONS": "true",
        }
    )

    assert settings.default_sources == [KS.HPO, KS.GENEONTOLOGY]
    assert settings.enabled_sources == [KS.HPO, KS.GENEONTOLOGY, KS.OXO]
    assert settings.timeout_per_source == 5.0
    assert settings.persist_expansions is True


def test_cli_flags_override_environment(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_LOOKUP_MCP_TIMEOUT", "20")
    monkeypatch.delenv("KNOWLEDGE_LOOKUP_MCP_DEFAULT_SOURCES", raising=False)

    settings = settings_from_args(_parse_args(["--default-sources", "MONDO", "--timeout", "3"]))

    assert settings.default_sources == [KS.MONDO]
    assert settings.timeout_per_source == 3.0


def test_cli_rejects_unknown_source():
    with pytest.raises(SystemExit, match="Valid sources"):
        settings_from_args(_parse_args(["--default-sources", "NOPE"]))


@pytest.mark.parametrize(
    ("argv", "expected_call"),
    [
        ([], (("stdio",), {})),
        (
            ["--transport", "streamable-http", "--port", "9001"],
            (("streamable-http",), {"host": "127.0.0.1", "port": 9001, "stateless_http": True}),
        ),
    ],
)
def test_run_selects_transport(argv, expected_call):
    fake_server = MagicMock()
    with (
        patch.object(server_module, "create_server", return_value=fake_server),
        patch.object(server_module.logging, "basicConfig"),  # keep root logging untouched
    ):
        server_module.run(argv)

    args, kwargs = expected_call
    fake_server.run.assert_called_once_with(*args, **kwargs)


def test_package_main_delegates_to_server_run():
    from knowledge_lookup import mcp_server

    with patch.object(server_module, "run") as run:
        mcp_server.main(["--log-level", "ERROR"])

    run.assert_called_once_with(["--log-level", "ERROR"])
