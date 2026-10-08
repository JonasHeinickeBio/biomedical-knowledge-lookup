"""Unit tests for LipidMapsAdapter (LIPID MAPS REST + SPARQL); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import lipidmaps_adapter
from knowledge_lookup.adapters.lipidmaps_adapter import (
    LipidMapsAdapter,
    _class_codes,
    _split_class,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import lipidmaps_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(lipidmaps_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return LipidMapsAdapter(lookup_config)


class Router:
    """Fake transport: REST text by URL fragment, SPARQL JSON by query fragment."""

    def __init__(self, rest=None, sparql=None, refmet=fx.REFMET):
        self.rest = rest or {}
        self.sparql = sparql or {}
        self.refmet = refmet
        self.rest_urls: list[str] = []
        self.queries: list[str] = []

    async def text(self, url, params=None, headers=None):
        self.rest_urls.append(url)
        for marker, body in self.rest.items():
            if marker in url:
                if isinstance(body, Exception):
                    raise body
                return body
        return fx.MISS_BODY

    async def json(self, url, params=None, headers=None, json_data=None):
        if "metabolomicsworkbench" in url:
            if isinstance(self.refmet, Exception):
                raise self.refmet
            return copy.deepcopy(self.refmet)
        assert headers == {"Accept": "application/json"} or "User-Agent" in (headers or {})
        query = params["query"]
        self.queries.append(query)
        for marker, body in self.sparql.items():
            if marker in query:
                if isinstance(body, Exception):
                    raise body
                return copy.deepcopy(body)
        return copy.deepcopy(fx.SPARQL_EMPTY)

    def install(self, adapter):
        return (
            patch.object(adapter, "_make_request_text", self.text),
            patch.object(adapter, "_make_request", self.json),
        )


async def _run(adapter, router, coro_fn):
    p1, p2 = router.install(adapter)
    with p1, p2:
        return await coro_fn()


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.LIPIDMAPS
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("LMGP01010005", "LMGP01010005"),
            ("lmgp01010005", "LMGP01010005"),
            ("LIPIDMAPS:LMGP01010005", "LMGP01010005"),
            ("https://www.lipidmaps.org/databases/lmsd/LMGP01010005", "LMGP01010005"),
            ("LMGP0101", None),
            ("cholesterol", None),
            ("", None),
        ],
    )
    def test_lm_id_normalisation(self, raw, expected):
        assert LipidMapsAdapter._lm_id(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("LMST0101", "ST0101"),
            ("ST0101", "ST0101"),
            ("[ST0101]", "ST0101"),
            ("LMST01", "ST01"),
            ("LMST", "ST"),
            ("ST", None),  # bare two letters is ordinary text
            ("PC", None),
            ("LMGP01010005", None),
            ("", None),
        ],
    )
    def test_class_code(self, raw, expected):
        assert LipidMapsAdapter._class_code(raw) == expected

    def test_helpers(self):
        assert _split_class("Cholesterol and derivatives [ST0101]") == (
            "Cholesterol and derivatives",
            "ST0101",
        )
        assert _split_class("plain") == ("plain", "")
        assert _class_codes("LMGP01010005") == ["LMGP0101", "LMGP01", "LMGP"]
        assert _class_codes("bad") == []

    @pytest.mark.parametrize(
        "text,route",
        [
            ("LMGP01010005", ("lm_id", "LMGP01010005")),
            ("wtjkggkopkcxll-vyobokexsa-n", ("inchi_key", "WTJKGGKOPKCXLL-VYOBOKEXSA-N")),
            ("HMDB0000067", ("hmdb_id", "HMDB0000067")),
            ("HMDB00067", ("hmdb_id", "HMDB0000067")),
            ("CHEBI:16113", ("chebi_id", "16113")),
            ("CID:5997", ("pubchem_cid", "5997")),
            ("pubchem:5997", ("pubchem_cid", "5997")),
            ("C00187", ("kegg_id", "C00187")),
            ("cholesterol", None),
        ],
    )
    def test_id_route(self, adapter, text, route):
        assert adapter._id_route(text) == route


class TestSearch:
    @pytest.mark.asyncio
    async def test_lm_id_uses_rest_lm_id(self, adapter):
        router = Router(rest={"/lm_id/LMGP01010005/all": fx.POPC_BODY})
        result = await _run(adapter, router, lambda: adapter.search_concepts("LMGP01010005"))
        assert [c.primary_id for c in result] == ["LMGP01010005"]
        assert result[0].concept_type == ConceptType.CHEMICAL
        assert router.queries == []

    @pytest.mark.asyncio
    async def test_abbreviation_rows_deduplicated_and_limited(self, adapter):
        router = Router(rest={"/abbrev/PC(34:1)/all": fx.ABBREV_ROWS_BODY})
        result = await _run(adapter, router, lambda: adapter.search_concepts("PC(34:1)"))
        assert [c.primary_id for c in result] == ["LMGP01010005", "LMGP01010576"]
        limited = await _run(adapter, router, lambda: adapter.search_concepts("PC(34:1)", 1))
        assert len(limited) == 1

    @pytest.mark.asyncio
    async def test_chain_abbreviation_tries_chains_first_and_keeps_slash_raw(self, adapter):
        router = Router(rest={"abbrev_chains/PC(16:0_18:1)": fx.ABBREV_ROWS_BODY})
        await _run(adapter, router, lambda: adapter.search_concepts("PC(16:0_18:1)"))
        assert "/abbrev_chains/PC(16:0_18:1)/all" in router.rest_urls[0]
        router = Router()
        await _run(adapter, router, lambda: adapter._rest("abbrev", "PC(16:0/20:4)"))
        assert router.rest_urls[0].endswith("/abbrev/PC(16:0/20:4)/all")
        await _run(adapter, router, lambda: adapter._rest("abbrev", "PC 34:1"))
        assert router.rest_urls[1].endswith("/abbrev/PC%2034:1/all")

    @pytest.mark.asyncio
    async def test_cross_reference_and_formula_routes(self, adapter):
        router = Router(
            rest={
                "/hmdb_id/HMDB0000067/": fx.CHOLESTEROL_BODY,
                "/formula/C27H46O/": fx.CHOLESTEROL_BODY,
            }
        )
        hmdb = await _run(adapter, router, lambda: adapter.search_concepts("HMDB0000067"))
        formula = await _run(adapter, router, lambda: adapter.search_concepts("C27H46O"))
        assert hmdb[0].primary_label == formula[0].primary_label == "Cholesterol"

    @pytest.mark.asyncio
    async def test_name_search_uses_sparql_and_collapses_duplicates(self, adapter):
        router = Router(sparql={"CONTAINS(LCASE(?name)": fx.SPARQL_NAME_SEARCH})
        result = await _run(adapter, router, lambda: adapter.search_concepts("Palmitic acid"))
        assert [c.primary_id for c in result] == ["LMFA01010001", "LMFA01010046"]
        first = result[0]
        assert first.synonyms == ["FA 16:0"]
        assert first.parents == ["Straight chain fatty acids"]
        assert first.identifiers[0].url.endswith("/lmsd/LMFA01010001")
        assert first.confidence_score == 0.8
        assert first.source_data[KnowledgeSource.LIPIDMAPS]["formula"] == "C16H32O2"
        query = router.queries[0]
        assert 'CONTAINS(LCASE(?name), "palmitic") && CONTAINS(LCASE(?name), "acid")' in query
        assert 'LCASE(?name) != "palmitic acid"' in query
        assert "LIMIT 60" in query

    @pytest.mark.asyncio
    async def test_rest_miss_falls_back_to_name_search(self, adapter):
        router = Router(sparql={"CONTAINS(LCASE(?name)": fx.SPARQL_NAME_SEARCH})
        result = await _run(adapter, router, lambda: adapter.search_concepts("PC(99:9)", 1))
        assert len(result) == 1 and router.rest_urls and router.queries

    @pytest.mark.asyncio
    async def test_unknown_field_html_is_a_miss(self, adapter):
        router = Router(rest={"/formula/": fx.UNKNOWN_FIELD_BODY})
        assert await _run(adapter, router, lambda: adapter.search_concepts("C27H46O")) == []

    @pytest.mark.asyncio
    async def test_sparql_literal_is_escaped(self, adapter):
        router = Router()
        await _run(adapter, router, lambda: adapter.search_concepts('a"b\\c'))
        assert 'a\\"b\\\\c' in router.queries[0]

    @pytest.mark.asyncio
    async def test_class_code_query_returns_class_concept(self, adapter):
        router = Router(sparql={"[ST0101]": fx.CLASS_LABELS_ST0101})
        result = await _run(adapter, router, lambda: adapter.search_concepts("LMST0101"))
        assert result[0].primary_id == "LMST0101"
        assert result[0].primary_label == "Cholesterol and derivatives"
        assert "lipid sub class" in result[0].semantic_types

    @pytest.mark.asyncio
    async def test_empty_and_bad_limit(self, adapter):
        router = Router()
        assert await _run(adapter, router, lambda: adapter.search_concepts("  ")) == []
        assert await _run(adapter, router, lambda: adapter.search_concepts("x", 0)) == []
        assert router.rest_urls == [] and router.queries == []

    @pytest.mark.asyncio
    async def test_errors_never_raise(self, adapter):
        router = Router(
            rest={"/lm_id/": RuntimeError("boom")}, sparql={"CONTAINS": RuntimeError("boom")}
        )
        assert await _run(adapter, router, lambda: adapter.search_concepts("LMGP01010005")) == []
        assert await _run(adapter, router, lambda: adapter.search_concepts("palmitic")) == []

    @pytest.mark.asyncio
    async def test_rest_error_falls_back_to_name_search(self, adapter):
        router = Router(
            rest={"/abbrev/": RuntimeError("boom")},
            sparql={"CONTAINS(LCASE(?name)": fx.SPARQL_NAME_SEARCH},
        )
        result = await _run(adapter, router, lambda: adapter.search_concepts("PC(34:1)", 2))
        assert len(result) == 2


class TestDetails:
    @pytest.mark.asyncio
    async def test_full_record(self, adapter):
        router = Router(rest={"/lm_id/LMGP01010005/all": fx.POPC_BODY})
        c = await _run(adapter, router, lambda: adapter.get_concept_details("LMGP01010005"))
        assert c.primary_id == "LMGP01010005"
        assert c.primary_label == "PC 16:0/18:1(9Z)"
        assert "POPC" in c.synonyms and "PC 34:1" in c.synonyms
        assert c.synonyms.count("PC 34:1") == 1
        assert c.categories == [
            "Glycerophospholipids",
            "Glycerophosphocholines",
            "Diacylglycerophosphocholines",
        ]
        assert c.parents == ["Diacylglycerophosphocholines"]
        assert "Diacylglycerophosphocholines (GP0101)" in c.definitions[0]
        ids = {(i.source, i.identifier) for i in c.identifiers}
        assert ("LIPIDMAPS", "LMGP01010005") in ids
        assert ("PUBCHEM", "5497103") in ids and ("CHEBI", "CHEBI:73001") in ids
        assert len(c.identifiers) == 3
        data = c.source_data[KnowledgeSource.LIPIDMAPS]
        assert data["hmdb_id"] == "HMDB0007972" and data["formula"] == "C42H82NO8P"
        assert "lipid" in c.semantic_types

    @pytest.mark.asyncio
    async def test_kegg_identifier_and_cross_reference_input(self, adapter):
        router = Router(rest={"/chebi_id/16113/": fx.CHOLESTEROL_BODY})
        c = await _run(adapter, router, lambda: adapter.get_concept_details("CHEBI:16113"))
        assert c.primary_id == "LMST01010001"
        assert ("KEGG", "C00187") in {(i.source, i.identifier) for i in c.identifiers}

    @pytest.mark.asyncio
    async def test_unknown_inputs(self, adapter):
        router = Router()
        assert await _run(adapter, router, lambda: adapter.get_concept_details("")) is None
        assert (
            await _run(adapter, router, lambda: adapter.get_concept_details("cholesterol")) is None
        )
        assert (
            await _run(adapter, router, lambda: adapter.get_concept_details("LMXX99999999"))
            is None
        )

    @pytest.mark.asyncio
    async def test_class_details_and_unknown_class(self, adapter):
        router = Router(sparql={"[ST0101]": fx.CLASS_LABELS_ST0101})
        c = await _run(adapter, router, lambda: adapter.get_concept_details("[ST0101]"))
        assert c.primary_id == "LMST0101" and "[ST0101]" in c.synonyms
        missing = await _run(adapter, Router(), lambda: adapter.get_concept_details("LMGL99"))
        assert missing is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self, adapter):
        router = Router(rest={"/lm_id/": RuntimeError("boom")})
        assert (
            await _run(adapter, router, lambda: adapter.get_concept_details("LMGP01010005"))
            is None
        )

    def test_record_without_id_or_name(self, adapter):
        assert adapter._record_to_concept({"name": "x"}) is None
        concept = adapter._record_to_concept({"lm_id": "LMFA01010001"})
        assert concept.primary_label == "LMFA01010001"
        assert adapter._sparql_row_to_concept({"s": "x/LMFA01010001"}) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_lipid_classification_path(self, adapter):
        router = Router(rest={"/classification": fx.POPC_CLASSIFICATION_BODY})
        rels = await _run(adapter, router, lambda: adapter.get_relationships("LMGP01010005"))
        assert [(r["relation_label"], r["related_id"], r["level"]) for r in rels] == [
            ("is_a", "LMGP0101", "sub_class"),
            ("is_a", "LMGP01", "main_class"),
            ("is_a", "LMGP", "core"),
        ]
        assert rels[0]["related_name"] == "Diacylglycerophosphocholines" and rels[0]["direct"]
        assert not rels[1]["direct"] and rels[2]["source"] == "LIPID MAPS"
        limited = await _run(adapter, router, lambda: adapter.get_relationships("LMGP01010005", 1))
        assert len(limited) == 1

    @pytest.mark.asyncio
    async def test_sub_class_members_deduplicated_and_capped(self, adapter):
        async def json(url, params=None, headers=None, json_data=None):
            # the members query is the only one that joins ?cat to ?s
            q = params["query"]
            return copy.deepcopy(
                fx.CLASS_MEMBERS_ST0101 if "?cat" in q else fx.CLASS_LABELS_ST0101
            )

        with patch.object(adapter, "_make_request", json):
            rels = await adapter.get_relationships("LMST0101", 25)
            capped = await adapter.get_relationships("LMST0101", 2)
        parents = [r for r in rels if r["relation_label"] == "is_a"]
        members = [r for r in rels if r["relation_label"] == "has_member"]
        assert [(p["related_id"], p["direct"]) for p in parents] == [
            ("LMST01", True),
            ("LMST", False),
        ]
        assert [m["related_id"] for m in members] == [
            "LMST01010452",
            "LMST01010535",
            "LMST01010001",
        ]
        assert len([r for r in capped if r["relation_label"] == "has_member"]) == 2

    @pytest.mark.asyncio
    async def test_main_class_lists_child_classes(self, adapter):
        async def json(url, params=None, headers=None, json_data=None):
            q = params["query"]
            return copy.deepcopy(
                fx.CLASS_CHILDREN_ST01 if 'CONTAINS(?l, "[ST01")' in q else fx.CLASS_LABELS_ST0101
            )

        with patch.object(adapter, "_make_request", json):
            rels = await adapter.get_relationships("LMST01")
        children = [r["related_id"] for r in rels if r["relation_label"] == "has_subclass"]
        assert children == ["LMST0101", "LMST0108", "LMST0104"]
        assert [r["related_id"] for r in rels if r["relation_label"] == "is_a"] == ["LMST"]

    @pytest.mark.asyncio
    async def test_bad_input_and_errors(self, adapter):
        router = Router(rest={"/classification": RuntimeError("boom")})
        assert await _run(adapter, router, lambda: adapter.get_relationships("cholesterol")) == []
        assert await _run(adapter, router, lambda: adapter.get_relationships("")) == []
        assert (
            await _run(adapter, router, lambda: adapter.get_relationships("LMGP01010005", 0)) == []
        )
        assert await _run(adapter, router, lambda: adapter.get_relationships("LMGP01010005")) == []
        empty = Router()
        assert await _run(adapter, empty, lambda: adapter.get_relationships("LMGP01010005")) == []
        failing = Router(sparql={"rdfs": RuntimeError("boom")})
        assert await _run(adapter, failing, lambda: adapter.get_relationships("LMST0101")) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_all_xrefs(self, adapter):
        router = Router(
            rest={"/lm_id/LMST01010001/all": fx.CHOLESTEROL_BODY},
            sparql={"equivalentClass": fx.EQUIVALENT_CLASSES},
        )
        maps = await _run(adapter, router, lambda: adapter.get_mappings("LMST01010001"))
        by_db = {m["toSource"]: m["toId"] for m in maps}
        assert by_db == {
            "PubChem": "5997",
            "ChEBI": "CHEBI:16113",
            "HMDB": "HMDB0000067",
            "KEGG": "C00187",
            "LipidBank": "SST9061",
            "SwissLipids": "SLM:000000287",
            "RefMet": "RM0135639",
        }
        assert all(m["fromSource"] == "LIPIDMAPS" and m["fromId"] == "LMST01010001" for m in maps)
        assert {m["mappingType"] for m in maps} == {"xref"}
        assert len(maps) == 7  # ChEBI from REST and SPARQL is not duplicated

    @pytest.mark.asyncio
    async def test_best_effort_extras_can_fail(self, adapter):
        router = Router(
            rest={"/lm_id/": fx.CHOLESTEROL_BODY},
            sparql={"equivalentClass": RuntimeError("down")},
            refmet=RuntimeError("down"),
        )
        maps = await _run(adapter, router, lambda: adapter.get_mappings("LMST01010001"))
        assert {m["toSource"] for m in maps} == {"PubChem", "ChEBI", "HMDB", "KEGG", "LipidBank"}

    @pytest.mark.asyncio
    async def test_record_without_inchikey_skips_refmet(self, adapter):
        body = fx.POPC_BODY.replace(fx.POPC["inchi_key"], "bad")
        router = Router(rest={"/lm_id/": body})
        maps = await _run(adapter, router, lambda: adapter.get_mappings("LMGP01010005"))
        assert "RefMet" not in {m["toSource"] for m in maps}

    @pytest.mark.asyncio
    async def test_bad_input_miss_and_error(self, adapter):
        router = Router(rest={"/lm_id/LMBAD": RuntimeError("boom")})
        assert await _run(adapter, router, lambda: adapter.get_mappings("nope")) == []
        assert await _run(adapter, router, lambda: adapter.get_mappings("LMGP01010005")) == []
        assert await _run(adapter, router, lambda: adapter.get_mappings("LMBA99999999")) == []
        failing = Router(rest={"/lm_id/": RuntimeError("boom")})
        assert await _run(adapter, failing, lambda: adapter.get_mappings("LMGP01010005")) == []


class TestTransport:
    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(lipidmaps_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(lipidmaps_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value="[]")):
            await adapter._rest("lm_id", "LMGP01010005")
            await adapter._rest("lm_id", "LMGP01010005")
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6

    @pytest.mark.asyncio
    async def test_rest_accepts_single_record_and_list(self, adapter):
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=fx.POPC_BODY)):
            assert len(await adapter._rest("lm_id", "x")) == 1
        with patch.object(
            adapter, "_make_request_text", AsyncMock(return_value="[" + fx.POPC_BODY + "]")
        ):
            assert len(await adapter._rest("lm_id", "x")) == 1
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=None)):
            assert await adapter._rest("lm_id", "x") == []

    @pytest.mark.asyncio
    async def test_sparql_non_dict_response(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=None)):
            assert await adapter._sparql("SELECT * WHERE {}") == []
