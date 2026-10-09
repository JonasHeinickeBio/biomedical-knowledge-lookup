"""Unit tests for IMPCAdapter (IMPC Solr cores); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import impc_adapter
from knowledge_lookup.adapters.impc_adapter import IMPCAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.impc_responses import (
    EMPTY,
    GENE_BRCA1,
    GENE_FBN1,
    GENE_FIBRILLIN,
    GENE_INS,
    GP_FBN1_GROUPED,
    GP_SPLEEN_GROUPED,
    MP_LETHARGY,
    MP_SPLEEN_MORPHOLOGY,
    MP_SPLEEN_WEIGHT,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(impc_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return IMPCAdapter(lookup_config)


def router(genes=GENE_FBN1, mp=MP_SPLEEN_WEIGHT, gp=None, calls=None):
    """Fake ``_solr`` answering by core; ``calls`` records ``(core, params)``."""

    async def fake(core, params):
        if calls is not None:
            calls.append((core, dict(params)))
        if core == "gene":
            if isinstance(genes, Exception):
                raise genes
            return copy.deepcopy(genes)
        if core == "mp":
            if isinstance(mp, Exception):
                raise mp
            return copy.deepcopy(mp)
        if core == "genotype-phenotype":
            if isinstance(gp, Exception):
                raise gp
            return copy.deepcopy(gp if gp is not None else EMPTY)
        raise AssertionError(f"unexpected core {core}")

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.IMPC
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("MGI:95489", ("mgi", "MGI:95489")),
            ("mgi: 95489", ("mgi", "MGI:95489")),
            ("MP:0004952", ("mp", "MP:0004952")),
            ("mp:4952", ("mp", "MP:0004952")),
            ("Fbn1", ("symbol", "Fbn1")),
            ("  FBN1 ", ("symbol", "FBN1")),
            ("H2-K1", ("symbol", "H2-K1")),
            ("", None),
            ("   ", None),
            ("two words", None),
            ("HP:0001250", None),
            ("MGI:abc", None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert IMPCAdapter._parse_id(raw) == expected

    def test_quote_escapes(self):
        assert impc_adapter._quote('a"b\\c') == '"a\\"b\\\\c"'

    def test_as_list(self):
        assert impc_adapter._as_list(None) == []
        assert impc_adapter._as_list("x") == ["x"]
        assert impc_adapter._as_list(["x"]) == ["x"]


class FakeResponse:
    def __init__(self, text, status=200):
        self._text = text
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def get(self, url, params=None):
        self.requests.append((url, params))
        return self.response


class TestSolrHelper:
    @pytest.mark.asyncio
    async def test_parses_text_plain_json(self, adapter):
        session = FakeSession(FakeResponse('{"response": {"docs": [{"a": 1}]}}'))
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            data = await adapter._solr("gene", {"q": "x"})
        url, params = session.requests[0]
        assert url == "https://www.ebi.ac.uk/mi/impc/solr/gene/select"
        assert params == {"wt": "json", "q": "x"}
        assert adapter._docs(data) == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_non_dict_json_is_empty(self, adapter):
        session = FakeSession(FakeResponse("[1, 2]"))
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            assert await adapter._solr("gene", {}) == {}

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, adapter):
        session = FakeSession(FakeResponse("boom", status=500))
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            with patch.object(
                adapter, "_call_with_retry", AsyncMock(side_effect=RuntimeError("HTTP 500"))
            ):
                with pytest.raises(RuntimeError):
                    await adapter._solr("gene", {})

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(impc_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(impc_adapter.asyncio, "sleep", fake_sleep)
        session = FakeSession(FakeResponse("{}"))
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            await adapter._solr("gene", {})
            await adapter._solr("gene", {})
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6

    def test_docs_and_groups_tolerate_junk(self, adapter):
        assert adapter._docs({}) == []
        assert adapter._docs({"response": {"docs": ["x", {"a": 1}]}}) == [{"a": 1}]
        assert adapter._groups({}, "f") == ([], 0)
        groups, n = adapter._groups(
            {"grouped": {"f": {"groups": [{"doclist": {"docs": []}}]}}}, "f"
        )
        assert groups == [] and n == 0


class TestSearch:
    @pytest.mark.asyncio
    async def test_human_symbol_uses_lowercase_fields(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(calls=calls, mp=EMPTY)):
            results = await adapter.search_concepts("FBN1", limit=5)
        assert [c.primary_id for c in results] == ["MGI:95489"]
        gene_q = calls[0][1]["q"]
        assert '"fbn1"' in gene_q and "human_gene_symbol_lowercase" in gene_q
        assert "marker_symbol_lowercase" in gene_q and "synonym_lowercase" in gene_q
        concept = results[0]
        assert concept.primary_label == "Fbn1"
        assert concept.concept_type == ConceptType.GENE
        assert concept.synonyms[:2] == ["fibrillin 1", "FBN1"]
        assert "Human ortholog: FBN1" in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.IMPC]
        assert data["human_gene_symbol"] == ["FBN1"]
        assert data["phenotyping_data_available"] is True
        assert "mortality/aging" in data["significant_top_level_mp_terms"]
        assert "translational" in data["evidence_note"]
        assert "datasets_raw_data" not in calls[0][1]["fl"]

    @pytest.mark.asyncio
    async def test_exact_matches_rank_first(self, adapter):
        with patch.object(adapter, "_solr", router(genes=GENE_FIBRILLIN, mp=EMPTY)):
            results = await adapter.search_concepts("FBN1", limit=5)
        assert [c.primary_label for c in results] == ["Fbn1", "Fbn2"]
        with patch.object(adapter, "_solr", router(genes=GENE_FIBRILLIN, mp=EMPTY)):
            results = await adapter.search_concepts("fbn2", limit=5)
        assert results[0].primary_label == "Fbn2"

    @pytest.mark.asyncio
    async def test_name_fallback_when_symbol_misses(self, adapter):
        calls = []

        async def fake(core, params):
            calls.append((core, params["q"]))
            if core == "gene" and "marker_name" in params["q"]:
                return copy.deepcopy(GENE_FIBRILLIN)
            return copy.deepcopy(EMPTY)

        with patch.object(adapter, "_solr", fake):
            results = await adapter.search_concepts("fibrillin", limit=5)
        assert len(results) == 2
        assert calls[1] == ("gene", 'marker_name:"fibrillin"')

    @pytest.mark.asyncio
    async def test_multiword_query_skips_symbol_clause(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(calls=calls, genes=EMPTY, mp=EMPTY)):
            await adapter.search_concepts("breast cancer", limit=5)
        assert calls[0][1]["q"] == 'marker_name:"breast cancer"'

    @pytest.mark.asyncio
    async def test_very_short_query_skips_name_and_phenotype(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(calls=calls, genes=EMPTY, mp=EMPTY)):
            assert await adapter.search_concepts("ab", limit=5) == []
        assert [c[0] for c in calls] == ["gene"]  # symbol lookup only

    @pytest.mark.asyncio
    async def test_mgi_id_query(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(calls=calls, mp=EMPTY)):
            results = await adapter.search_concepts("mgi:95489", limit=5)
        assert results[0].primary_id == "MGI:95489"
        assert calls[0][1]["q"] == 'mgi_accession_id:"MGI:95489"'
        assert all(c[0] != "mp" or "MGI" not in c[1]["q"] for c in calls)

    @pytest.mark.asyncio
    async def test_phenotype_text_search(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(genes=EMPTY, calls=calls)):
            results = await adapter.search_concepts("increased spleen weight", limit=5)
        assert [c.primary_id for c in results] == ["MP:0004952"]
        mp_params = [c[1] for c in calls if c[0] == "mp"][0]
        assert mp_params["defType"] == "edismax" and mp_params["qf"] == "mixSynQf"
        assert mp_params["q.op"] == "AND"
        concept = results[0]
        assert concept.concept_type == ConceptType.PHENOTYPE
        assert concept.synonyms == ["increased splenic weight"]
        assert concept.parents == ["MP:0000691", "MP:0004951"]
        assert "immune system phenotype" in concept.categories
        assert concept.definitions[0].startswith("greater than average weight")

    @pytest.mark.asyncio
    async def test_special_characters_are_stripped_from_text_query(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(genes=EMPTY, mp=MP_LETHARGY, calls=calls)):
            await adapter.search_concepts("lethargy:(AND) {x}", limit=5)
        mp_q = [c[1]["q"] for c in calls if c[0] == "mp"][0]
        assert not any(ch in mp_q for ch in ":(){}")

    @pytest.mark.asyncio
    async def test_mp_id_query(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(calls=calls)):
            results = await adapter.search_concepts("MP:0004952", limit=5)
        assert [c.primary_id for c in results] == ["MP:0004952"]
        assert [c[0] for c in calls] == ["mp"]  # no gene query for an MP id

    @pytest.mark.asyncio
    async def test_genes_before_phenotypes_and_limit(self, adapter):
        with patch.object(adapter, "_solr", router(genes=GENE_FIBRILLIN, mp=MP_LETHARGY)):
            results = await adapter.search_concepts("fbn", limit=3)
        assert [c.primary_id for c in results] == ["MGI:95490", "MGI:95489", "MP:0005202"]
        calls = []
        with patch.object(adapter, "_solr", router(genes=GENE_FIBRILLIN, calls=calls)):
            results = await adapter.search_concepts("fbn", limit=2)
        assert len(results) == 2
        assert all(c[0] == "gene" for c in calls)  # limit reached by genes: no mp query

    @pytest.mark.asyncio
    async def test_rows_capped(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(calls=calls)):
            await adapter.search_concepts("FBN1", limit=500)
        assert calls[0][1]["rows"] == impc_adapter._MAX_SEARCH

    @pytest.mark.asyncio
    async def test_dedupes_repeated_documents(self, adapter):
        dup = copy.deepcopy(GENE_FBN1)
        dup["response"]["docs"].append(copy.deepcopy(dup["response"]["docs"][0]))
        with patch.object(adapter, "_solr", router(genes=dup, mp=EMPTY)):
            assert len(await adapter.search_concepts("FBN1", limit=5)) == 1

    @pytest.mark.asyncio
    async def test_documents_without_ids_are_skipped(self, adapter):
        bad = {"response": {"docs": [{"marker_symbol": "X"}, {"mgi_accession_id": "MGI:1"}]}}
        mp_bad = {"response": {"docs": [{"mp_id": "MP:1"}, {"mp_term": "x"}]}}
        with patch.object(adapter, "_solr", router(genes=bad, mp=mp_bad)):
            assert await adapter.search_concepts("something", limit=5) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("FBN1", 0), (None, 5)])
    async def test_empty_input(self, adapter, query, limit):
        with patch.object(adapter, "_solr", AsyncMock(side_effect=AssertionError("no call"))):
            assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_gene_failure_still_searches_phenotypes(self, adapter):
        with patch.object(adapter, "_solr", router(genes=RuntimeError("boom"))):
            results = await adapter.search_concepts("lethargy", limit=5)
        assert [c.primary_id for c in results] == ["MP:0004952"]

    @pytest.mark.asyncio
    async def test_all_failures_return_empty(self, adapter):
        with patch.object(
            adapter, "_solr", router(genes=RuntimeError("boom"), mp=RuntimeError("boom"))
        ):
            assert await adapter.search_concepts("FBN1", limit=5) == []

    @pytest.mark.asyncio
    async def test_empty_responses(self, adapter):
        with patch.object(adapter, "_solr", router(genes=EMPTY, mp=EMPTY)):
            assert await adapter.search_concepts("zzzzzz", limit=5) == []


class TestDetails:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("cid", ["MGI:95489", "Fbn1", "FBN1"])
    async def test_gene(self, adapter, cid):
        with patch.object(adapter, "_solr", router()):
            concept = await adapter.get_concept_details(cid)
        assert concept.primary_id == "MGI:95489"
        assert concept.identifiers[0].url == "https://www.mousephenotype.org/data/genes/MGI:95489"

    @pytest.mark.asyncio
    async def test_phenotype(self, adapter):
        with patch.object(adapter, "_solr", router()):
            concept = await adapter.get_concept_details("mp:4952")
        assert concept.primary_id == "MP:0004952"
        assert concept.source_data[KnowledgeSource.IMPC]["kind"] == "phenotype"

    @pytest.mark.asyncio
    async def test_gene_without_phenotyping_data(self, adapter):
        with patch.object(adapter, "_solr", router(genes=GENE_BRCA1)):
            concept = await adapter.get_concept_details("Brca1")
        data = concept.source_data[KnowledgeSource.IMPC]
        assert data["phenotyping_data_available"] is False
        assert concept.semantic_types == []

    @pytest.mark.asyncio
    async def test_gene_without_name_or_ortholog(self, adapter):
        doc = {"response": {"docs": [{"mgi_accession_id": "MGI:1", "marker_symbol": "Abc1"}]}}
        with patch.object(adapter, "_solr", router(genes=doc)):
            concept = await adapter.get_concept_details("Abc1")
        assert concept.definitions == [""]
        assert concept.synonyms == []

    @pytest.mark.asyncio
    async def test_not_found_and_invalid(self, adapter):
        with patch.object(adapter, "_solr", router(genes=EMPTY, mp=EMPTY)):
            assert await adapter.get_concept_details("Nope1") is None
            assert await adapter.get_concept_details("MP:9999999") is None
        assert await adapter.get_concept_details("not an id") is None
        assert await adapter.get_concept_details("") is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self, adapter):
        with patch.object(adapter, "_solr", router(genes=RuntimeError("boom"))):
            assert await adapter.get_concept_details("Fbn1") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_human_ortholog_mapping(self, adapter):
        with patch.object(adapter, "_solr", router()):
            mappings = await adapter.get_mappings("MGI:95489")
        assert mappings == [
            {
                "fromId": "MGI:95489",
                "toId": "FBN1",
                "fromSource": "MGI",
                "toSource": "HGNC",
                "mappingType": "ortholog",
                "confidence": 0.9,
            }
        ]

    @pytest.mark.asyncio
    async def test_duplicate_human_symbols_collapse(self, adapter):
        doc = copy.deepcopy(GENE_FBN1)
        doc["response"]["docs"][0]["human_gene_symbol"] = ["FBN1", "FBN1", "FBN2"]
        with patch.object(adapter, "_solr", router(genes=doc)):
            mappings = await adapter.get_mappings("Fbn1")
        assert [m["toId"] for m in mappings] == ["FBN1", "FBN2"]

    @pytest.mark.asyncio
    async def test_phenotypes_and_invalid_have_no_mappings(self, adapter):
        with patch.object(adapter, "_solr", AsyncMock(side_effect=AssertionError("no call"))):
            assert await adapter.get_mappings("MP:0004952") == []
            assert await adapter.get_mappings("two words") == []

    @pytest.mark.asyncio
    async def test_not_found_and_error(self, adapter):
        with patch.object(adapter, "_solr", router(genes=EMPTY)):
            assert await adapter.get_mappings("Nope1") == []
        with patch.object(adapter, "_solr", router(genes=RuntimeError("boom"))):
            assert await adapter.get_mappings("Fbn1") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_gene_phenotypes(self, adapter):
        calls = []
        with patch.object(adapter, "_solr", router(gp=GP_FBN1_GROUPED, calls=calls)):
            edges = await adapter.get_relationships("Fbn1")
        assert edges[0]["relation_label"] == "ortholog_of" and edges[0]["related_id"] == "FBN1"
        phenotypes = [e for e in edges if e["relation_label"] == "has_phenotype"]
        assert [e["related_id"] for e in phenotypes] == ["MP:0011110", "MP:0004952", "MP:0000219"]
        spleen = phenotypes[1]
        assert spleen["p_value"] == pytest.approx(1.456e-30, rel=1e-3)
        assert spleen["zygosities"] == ["heterozygote", "homozygote"]
        assert spleen["sexes"] == ["female", "male"]
        assert spleen["n_calls"] == 2 and spleen["effect_size"] == pytest.approx(0.1258, rel=1e-3)
        assert spleen["total_phenotypes"] == 5
        assert phenotypes[0]["p_value"] == 0.0  # underflow kept as the strongest call
        gp_params = [c[1] for c in calls if c[0] == "genotype-phenotype"][0]
        assert gp_params["q"] == 'marker_accession_id:"MGI:95489"'
        assert gp_params["sort"] == "p_value asc"
        assert gp_params["group.field"] == "mp_term_id" and gp_params["rows"] == 25

    @pytest.mark.asyncio
    async def test_gene_without_phenotyping_data_has_only_ortholog_edge(self, adapter):
        with patch.object(adapter, "_solr", router(genes=GENE_BRCA1, gp=EMPTY)):
            edges = await adapter.get_relationships("Brca1")
        assert [e["relation_label"] for e in edges] == ["ortholog_of"]

    @pytest.mark.asyncio
    async def test_human_symbol_resolves_best_match(self, adapter):
        with patch.object(adapter, "_solr", router(genes=GENE_INS, gp=GP_FBN1_GROUPED)):
            edges = await adapter.get_relationships("INS")
        assert edges[0]["from_symbol"] == "Ins2" and edges[0]["related_species"] == "Homo sapiens"

    @pytest.mark.asyncio
    async def test_gene_without_accession_id(self, adapter):
        doc = {"response": {"docs": [{"marker_symbol": "X", "human_gene_symbol": ["XX"]}]}}
        with patch.object(adapter, "_solr", router(genes=doc)):
            edges = await adapter.get_relationships("X")
        assert [e["related_id"] for e in edges] == ["XX"]

    @pytest.mark.asyncio
    async def test_phenotype_genes_include_descendants(self, adapter):
        calls = []
        with patch.object(
            adapter, "_solr", router(mp=MP_SPLEEN_MORPHOLOGY, gp=GP_SPLEEN_GROUPED, calls=calls)
        ):
            edges = await adapter.get_relationships("MP:0000689")
        parents = [e for e in edges if e["relation_label"] == "is_a"]
        assert [e["related_id"] for e in parents] == ["MP:0002396", "MP:0002722"]
        assert parents[1]["related_name"] == "abnormal immune system organ morphology"
        genes = [e for e in edges if e["relation_label"] == "phenotype_of"]
        assert [e["related_name"] for e in genes] == ["Fbxo25", "C9orf72"]
        assert genes[1]["annotated_term_name"] == "increased spleen weight"
        assert genes[0]["total_genes"] == 858
        gp_q = [c[1]["q"] for c in calls if c[0] == "genotype-phenotype"][0]
        assert 'intermediate_mp_term_id:"MP:0000689"' in gp_q

    @pytest.mark.asyncio
    async def test_phenotype_unknown_term_still_lists_genes(self, adapter):
        with patch.object(adapter, "_solr", router(mp=EMPTY, gp=GP_SPLEEN_GROUPED)):
            edges = await adapter.get_relationships("MP:0000689")
        assert all(e["relation_label"] == "phenotype_of" for e in edges)

    @pytest.mark.asyncio
    async def test_parent_names_shorter_than_ids(self, adapter):
        mp = {"response": {"docs": [{"mp_id": "MP:1", "parent_mp_id": ["MP:2", "MP:3"]}]}}
        with patch.object(adapter, "_solr", router(mp=mp)):
            edges = await adapter.get_relationships("MP:0000001")
        assert [e["related_name"] for e in edges] == ["", ""]

    @pytest.mark.asyncio
    async def test_invalid_unknown_and_errors(self, adapter):
        assert await adapter.get_relationships("two words") == []
        with patch.object(adapter, "_solr", router(genes=EMPTY)):
            assert await adapter.get_relationships("Nope1") == []
        with patch.object(adapter, "_solr", router(gp=RuntimeError("boom"))):
            assert await adapter.get_relationships("Fbn1") == []
