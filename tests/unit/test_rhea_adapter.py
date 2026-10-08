"""Unit tests for RheaAdapter (Rhea search TSV/JSON + SPARQL); no network."""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import rhea_adapter
from knowledge_lookup.adapters.rhea_adapter import RheaAdapter, _split
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures import rhea_responses as fx

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(rhea_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return RheaAdapter(lookup_config)


class Router:
    """Fake ``_make_request_text``: search requests by (query, format), SPARQL by marker."""

    def __init__(self, search=None, sparql=None):
        self.search = search or {}
        self.sparql = sparql or {}
        self.search_calls: list[dict] = []
        self.sparql_calls: list[str] = []

    async def __call__(self, url, params=None, headers=None):
        if url == rhea_adapter.RHEA_SEARCH_URL:
            self.search_calls.append(params)
            for key in (
                (params["query"], params["format"], params["columns"]),
                (params["query"], params["format"]),
                (params["query"],),
                params["format"],
            ):
                if key in self.search:
                    return self._value(self.search[key])
            return fx.EMPTY_JSON if params["format"] == "json" else fx.EMPTY_TSV
        assert url == rhea_adapter.RHEA_SPARQL_URL
        assert headers == {"Accept": "application/sparql-results+json"}
        query = params["query"]
        self.sparql_calls.append(query)
        for marker, value in self.sparql.items():
            if marker in query:
                return self._value(value)
        return fx.sparql()

    @staticmethod
    def _value(value):
        if isinstance(value, Exception):
            raise value
        return value

    def patched(self, adapter):
        return patch.object(adapter, "_make_request_text", self)


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.RHEA
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("RHEA:23444", "23444"),
            ("rhea:23444", "23444"),
            ("RHEA_23444", "23444"),
            ("23444", "23444"),
            ("  23444 ", "23444"),
            ("RHEA:0023444", "23444"),
            ("https://www.rhea-db.org/rhea/23444", "23444"),
            ("http://rdf.rhea-db.org/23444", "23444"),
            ("CHEBI:16651", None),
            ("lactate", None),
            ("", None),
            (None, None),
        ],
    )
    def test_number_normalisation(self, raw, expected):
        assert RheaAdapter._number(raw) == expected

    @pytest.mark.parametrize(
        "text,query",
        [
            ("23444", "RHEA:23444"),
            ("RHEA:23444", "RHEA:23444"),
            ("chebi:16651", "CHEBI:16651"),
            ("CHEBI_16651", "CHEBI:16651"),
            ("EC:1.1.1.27", "ec:1.1.1.27"),
            ("1.1.1.27", "ec:1.1.1.27"),
            ("EC 3.5.1.-", "ec:3.5.1.-"),
            ("lactate", "lactate"),
            ("NAD(+) lactate", "NAD lactate"),
            ('a"b:c', "a b c"),
            ("(((", ""),
        ],
    )
    def test_search_query_translation(self, text, query):
        assert RheaAdapter._search_query(text) == query

    def test_split(self):
        assert _split("a; b ;;c") == ["a", "b", "c"]
        assert _split("a,b;c", ";,") == ["a", "b", "c"]
        assert _split("") == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_text_search_parses_tsv_and_deduplicates(self, adapter):
        router = Router(search={("lactate", "tsv"): fx.SEARCH_LACTATE})
        with router.patched(adapter):
            result = await adapter.search_concepts("lactate", 10)
        assert [c.primary_id for c in result] == ["RHEA:19909", "RHEA:23444"]
        first = result[1]
        assert first.concept_type == ConceptType.MOLECULAR_FUNCTION
        assert first.primary_label == "(S)-lactate + NAD(+) = pyruvate + NADH + H(+)"
        assert first.categories == ["EC:1.1.1.27"]
        assert first.identifiers[0].url == "https://www.rhea-db.org/rhea/23444"
        data = first.source_data[KnowledgeSource.RHEA]
        assert data["chebi_ids"][0] == "CHEBI:16651" and data["ec"] == ["EC:1.1.1.27"]
        params = router.search_calls[0]
        assert params["columns"] == "rhea-id,equation,ec,chebi-id" and params["limit"] == 10

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, adapter):
        router = Router(search={("lactate", "tsv"): fx.SEARCH_LACTATE})
        with router.patched(adapter):
            assert len(await adapter.search_concepts("lactate", 1)) == 1

    @pytest.mark.asyncio
    async def test_chebi_ec_and_id_queries(self, adapter):
        router = Router(search={("lactate", "tsv"): fx.SEARCH_LACTATE})
        router.search = {("CHEBI:16651", "tsv"): fx.SEARCH_LACTATE}
        with router.patched(adapter):
            by_chebi = await adapter.search_concepts("CHEBI:16651")
            await adapter.search_concepts("EC:1.1.1.27")
            await adapter.search_concepts("23444")
        assert len(by_chebi) == 2
        assert [c["query"] for c in router.search_calls] == [
            "CHEBI:16651",
            "ec:1.1.1.27",
            "RHEA:23444",
            "RHEA:23444",  # empty id search retries as a (variant) detail lookup
        ]

    @pytest.mark.asyncio
    async def test_variant_id_falls_back_to_sparql(self, adapter):
        router = Router(
            sparql={
                "VALUES ?m": fx.MASTER_23444,
                "rh:23446 ?p ?o": fx.INFO_RL,
            }
        )
        with router.patched(adapter):
            result = await adapter.search_concepts("RHEA:23446")
        assert [c.primary_id for c in result] == ["RHEA:23446"]

    @pytest.mark.asyncio
    async def test_unknown_id_and_miss(self, adapter):
        router = Router()
        with router.patched(adapter):
            assert await adapter.search_concepts("RHEA:99999999") == []
            assert await adapter.search_concepts("zzzzqq") == []

    @pytest.mark.asyncio
    async def test_empty_blank_and_bad_limit(self, adapter):
        router = Router()
        with router.patched(adapter):
            assert await adapter.search_concepts("   ") == []
            assert await adapter.search_concepts("x", 0) == []
            assert await adapter.search_concepts("((") == []
        assert router.search_calls == []

    @pytest.mark.asyncio
    async def test_html_error_page_and_exceptions_return_empty(self, adapter):
        router = Router(search={("lactate", "tsv"): fx.HTML_ERROR})
        with router.patched(adapter):
            assert await adapter.search_concepts("lactate") == []
        router = Router(search={("lactate", "tsv"): RuntimeError("boom")})
        with router.patched(adapter):
            assert await adapter.search_concepts("lactate") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_master_reaction(self, adapter):
        router = Router(
            search={
                ("RHEA:23444", "tsv"): fx.DETAIL_LACTATE,
                ("RHEA:23444", "json"): fx.STATUS_JSON,
            }
        )
        with router.patched(adapter):
            c = await adapter.get_concept_details("RHEA:23444")
        assert c.primary_id == "RHEA:23444"
        assert c.categories == ["EC:1.1.1.27"]
        assert c.definitions == ["Reaction of the lactate cycle."]
        ids = {(i.source, i.identifier) for i in c.identifiers}
        assert ("KEGG", "R00703") in ids and ("GO", "GO:0004459") in ids
        assert ("REACTOME", "R-HSA-70510.8") in ids and ("REACTOME", "R-HSA-71849.9") in ids
        data = c.source_data[KnowledgeSource.RHEA]
        assert data["uniprot_count"] == 14021
        assert data["status"] == "approved" and data["balanced"] is True
        assert data["metacyc"] == ["L-LACTATE-DEHYDROGENASE-RXN"]
        assert data["pubmed"][0] == "11821921"
        assert data["chebi_names"][0] == "(S)-lactate"
        assert "transport reaction" not in c.semantic_types
        assert [p["columns"] for p in router.search_calls][0].startswith("rhea-id,equation,chebi")

    @pytest.mark.asyncio
    async def test_transport_flag_and_failed_status_lookup(self, adapter):
        router = Router(
            search={
                ("RHEA:23444", "tsv"): fx.DETAIL_LACTATE,
                ("RHEA:23444", "json"): fx.STATUS_TRANSPORT_JSON,
            }
        )
        with router.patched(adapter):
            c = await adapter.get_concept_details("23444")
        assert "transport reaction" in c.semantic_types and not c.definitions
        router = Router(
            search={
                ("RHEA:23444", "tsv"): fx.DETAIL_LACTATE,
                ("RHEA:23444", "json"): RuntimeError("down"),
            }
        )
        with router.patched(adapter):
            c = await adapter.get_concept_details("23444")
        assert c.primary_id == "RHEA:23444" and "status" not in c.source_data[KnowledgeSource.RHEA]

    @pytest.mark.asyncio
    async def test_directional_variant_uses_sparql(self, adapter):
        router = Router(sparql={"VALUES ?m": fx.MASTER_23444, "rh:23446 ?p ?o": fx.INFO_RL})
        with router.patched(adapter):
            c = await adapter.get_concept_details("RHEA:23446")
        assert c.primary_id == "RHEA:23446"
        assert c.primary_label == "pyruvate + NADH + H(+) => (S)-lactate + NAD(+)"
        assert c.parents == ["RHEA:23444"]
        assert "directional reaction" in c.semantic_types
        data = c.source_data[KnowledgeSource.RHEA]
        assert data["direction"] == "R-L" and data["master"] == "RHEA:23444"
        assert data["status"] == "approved"

    @pytest.mark.asyncio
    async def test_bidirectional_variant_without_master(self, adapter):
        router = Router(sparql={"rh:23447 ?p ?o": fx.INFO_BIDI})
        with router.patched(adapter):
            c = await adapter.get_concept_details("23447")
        assert c.parents is None or c.parents == []
        assert c.source_data[KnowledgeSource.RHEA]["direction"] == "bidirectional"

    @pytest.mark.asyncio
    async def test_unknown_inputs(self, adapter):
        router = Router(sparql={"rh:1 ?p ?o": fx.INFO_MASTER})
        with router.patched(adapter):
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("lactate") is None
            # unknown id: empty SPARQL answer
            assert await adapter.get_concept_details("RHEA:99999999") is None
            # a master id that the TSV search somehow misses is not described by SPARQL
            assert await adapter.get_concept_details("RHEA:1") is None

    @pytest.mark.asyncio
    async def test_errors_return_none(self, adapter):
        router = Router(search={("RHEA:23444", "tsv"): RuntimeError("boom")})
        with router.patched(adapter):
            assert await adapter.get_concept_details("RHEA:23444") is None


class TestRelationships:
    def _router(self, **extra):
        sparql = {
            "rh:23444 ?p ?o": fx.INFO_MASTER,
            "VALUES ?side": fx.PARTICIPANTS,
        }
        sparql.update(extra)
        return Router(search={("RHEA:23444", "tsv"): fx.GO_TSV}, sparql=sparql)

    @pytest.mark.asyncio
    async def test_master_reaction(self, adapter):
        router = self._router()
        with router.patched(adapter):
            rels = await adapter.get_relationships("RHEA:23444")
        labels = [r["relation_label"] for r in rels]
        assert labels == [
            "has_substrate",
            "has_substrate",
            "has_product",
            "has_product",
            "has_product",
            "has_product",
            "has_ec_number",
            "is_a",
            "has_directional_variant",
            "has_directional_variant",
            "has_bidirectional_variant",
            "has_go_term",
        ]
        substrates = [r for r in rels if r["relation_label"] == "has_substrate"]
        assert [(r["related_id"], r["related_name"]) for r in substrates] == [
            ("CHEBI:16651", "(S)-lactate"),
            ("CHEBI:57540", "NAD(+)"),
        ]
        assert all(r["side"] == "L" and r["stoichiometry"] == 1 for r in substrates)
        products = {r["related_id"]: r for r in rels if r["relation_label"] == "has_product"}
        assert products["CHEBI:15361"]["stoichiometry"] == 2
        assert products["POLYMER:9999"]["stoichiometry"] == "N"
        assert "CHEBI:1" not in products and "CHEBI:2" not in products
        ec = next(r for r in rels if r["relation_label"] == "has_ec_number")
        assert ec["related_id"] == "EC:1.1.1.27"
        parent = next(r for r in rels if r["relation_label"] == "is_a")
        assert parent["related_id"] == "RHEA:34555" and parent["related_name"].startswith("a (2S)")
        variants = {
            r["related_id"]: r["direction"] for r in rels if "variant" in r["relation_label"]
        }
        assert variants == {
            "RHEA:23445": "L-R",
            "RHEA:23446": "R-L",
            "RHEA:23447": "bidirectional",
        }
        go = rels[-1]
        assert go["related_id"] == "GO:0004459" and go["related_name"].endswith("activity")
        assert all(r["source"] == "Rhea" for r in rels)

    @pytest.mark.asyncio
    async def test_limit(self, adapter):
        with self._router().patched(adapter):
            assert len(await adapter.get_relationships("RHEA:23444", 3)) == 3

    @pytest.mark.asyncio
    async def test_r_l_variant_swaps_sides(self, adapter):
        router = self._router(**{"rh:23446 ?p ?o": fx.INFO_RL, "VALUES ?m": fx.MASTER_23444})
        with router.patched(adapter):
            rels = await adapter.get_relationships("RHEA:23446")
        assert rels[0] == {
            "relation_label": "variant_of",
            "related_id": "RHEA:23444",
            "related_name": "",
            "source": "Rhea",
            "direction": "R-L",
        }
        substrates = {r["related_id"] for r in rels if r["relation_label"] == "has_substrate"}
        products = {r["related_id"] for r in rels if r["relation_label"] == "has_product"}
        assert "CHEBI:57945" in substrates and "CHEBI:16651" in products
        assert "has_go_term" not in {r["relation_label"] for r in rels}

    @pytest.mark.asyncio
    async def test_l_r_and_bidirectional_variants_keep_sides(self, adapter):
        router = self._router(**{"rh:23445 ?p ?o": fx.INFO_LR, "VALUES ?m": fx.MASTER_23444})
        with router.patched(adapter):
            lr = await adapter.get_relationships("23445")
        assert lr[0]["direction"] == "L-R"
        assert any(
            r["related_id"] == "CHEBI:16651" and r["relation_label"] == "has_substrate" for r in lr
        )
        router = self._router(**{"rh:23447 ?p ?o": fx.INFO_BIDI, "VALUES ?m": fx.MASTER_23444})
        with router.patched(adapter):
            bidi = await adapter.get_relationships("23447")
        assert bidi[0]["direction"] == "bidirectional"
        assert any(
            r["related_id"] == "CHEBI:16651" and r["relation_label"] == "has_substrate"
            for r in bidi
        )

    @pytest.mark.asyncio
    async def test_variant_without_master_has_no_participants(self, adapter):
        router = Router(sparql={"rh:23446 ?p ?o": fx.INFO_RL})
        with router.patched(adapter):
            rels = await adapter.get_relationships("RHEA:23446")
        assert [r["relation_label"] for r in rels] == ["is_a"]

    @pytest.mark.asyncio
    async def test_go_failure_is_ignored(self, adapter):
        router = self._router()
        router.search = {("RHEA:23444", "tsv"): RuntimeError("boom")}
        with router.patched(adapter):
            rels = await adapter.get_relationships("RHEA:23444")
        assert "has_go_term" not in {r["relation_label"] for r in rels}
        assert "has_substrate" in {r["relation_label"] for r in rels}

    @pytest.mark.asyncio
    async def test_go_cell_without_go_id_and_missing_row(self, adapter):
        router = self._router()
        router.search = {("RHEA:23444", "tsv"): fx.EMPTY_TSV}
        with router.patched(adapter):
            rels = await adapter.get_relationships("RHEA:23444")
        assert "has_go_term" not in {r["relation_label"] for r in rels}

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        router = Router(sparql={"rh:23444 ?p ?o": RuntimeError("timeout")})
        with router.patched(adapter):
            assert await adapter.get_relationships("lactate") == []
            assert await adapter.get_relationships("RHEA:23444", 0) == []
            assert await adapter.get_relationships("RHEA:23444") == []
            assert await adapter.get_relationships("RHEA:99999999") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_master_reaction(self, adapter):
        router = Router(search={("RHEA:23444", "tsv"): fx.DETAIL_LACTATE})
        with router.patched(adapter):
            maps = await adapter.get_mappings("RHEA:23444")
        pairs = [(m["toSource"], m["toId"]) for m in maps]
        assert pairs == [
            ("EC", "EC:1.1.1.27"),
            ("KEGG", "R00703"),
            ("MetaCyc", "L-LACTATE-DEHYDROGENASE-RXN"),
            ("Reactome", "R-HSA-70510.8"),
            ("Reactome", "R-HSA-6807826.6"),
            ("Reactome", "R-HSA-71849.9"),
            ("GO", "GO:0004459"),
            ("UniProt", "rhea:23444"),
        ]
        assert all(m["fromId"] == "RHEA:23444" and m["fromSource"] == "RHEA" for m in maps)
        uniprot = maps[-1]
        assert uniprot["mappingType"] == "enzyme_count" and uniprot["count"] == 14021
        assert {m["mappingType"] for m in maps[:-1]} == {"xref"}

    @pytest.mark.asyncio
    async def test_multiple_ecs_and_optional_databases(self, adapter):
        router = Router(search={("RHEA:10028", "tsv"): fx.DETAIL_MULTI_EC})
        with router.patched(adapter):
            maps = await adapter.get_mappings("10028")
        pairs = [(m["toSource"], m["toId"]) for m in maps]
        assert ("EC", "EC:1.4.3.7") in pairs and ("EC", "EC:1.4.3.15") in pairs
        assert ("EcoCyc", "D-GLUTAMATE-OXIDASE-RXN") in pairs and ("M-CSA", "12") in pairs
        assert ("GO", "GO:0008445") in pairs
        assert not any(m["toSource"] == "UniProt" for m in maps)  # zero enzymes: no mapping

    @pytest.mark.asyncio
    async def test_variant_maps_via_master(self, adapter):
        router = Router(
            search={("RHEA:23444", "tsv"): fx.DETAIL_LACTATE},
            sparql={"VALUES ?m": fx.MASTER_23444},
        )
        with router.patched(adapter):
            maps = await adapter.get_mappings("RHEA:23446")
        assert maps and all(m["fromId"] == "RHEA:23446" for m in maps)
        assert maps[-1]["toId"] == "rhea:23444"

    @pytest.mark.asyncio
    async def test_unknown_and_errors(self, adapter):
        router = Router()
        with router.patched(adapter):
            assert await adapter.get_mappings("lactate") == []
            assert await adapter.get_mappings("RHEA:99999999") == []
        router = Router(search={("RHEA:23444", "tsv"): RuntimeError("boom")})
        with router.patched(adapter):
            assert await adapter.get_mappings("RHEA:23444") == []


class TestTransport:
    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(rhea_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(rhea_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value=fx.EMPTY_TSV)):
            await adapter._tsv("x", "rhea-id", 1)
            await adapter._tsv("y", "rhea-id", 1)
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6

    @pytest.mark.asyncio
    async def test_row_cap_and_none_body(self, adapter):
        mock = AsyncMock(return_value=None)
        with patch.object(adapter, "_make_request_text", mock):
            assert await adapter._tsv("x", "rhea-id", 5000) == []
            assert await adapter._sparql("SELECT * WHERE {}") == []
        assert mock.call_args_list[0].args[1]["limit"] == rhea_adapter._MAX_ROWS
