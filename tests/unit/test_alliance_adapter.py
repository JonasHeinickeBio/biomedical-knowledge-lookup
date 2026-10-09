"""Unit tests for AllianceGenomeAdapter (Alliance of Genome Resources API); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import alliance_adapter
from knowledge_lookup.adapters.alliance_adapter import AllianceGenomeAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.alliance_responses import (
    DISEASES_BRCA1,
    GENE_BARE,
    GENE_HGNC_BRCA1,
    GENE_ZFIN_FGF8A,
    INTERACTIONS_BRCA1,
    ORTHOLOGS_BRCA1,
    PHENOTYPES_BRCA1,
    SEARCH_BRCA1,
    SEARCH_EMPTY,
    SEARCH_SOD1_ONLY_FLY,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(alliance_adapter, "_MIN_INTERVAL", 0.0)
    monkeypatch.delenv("ALLIANCE_SPECIES", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return AllianceGenomeAdapter(lookup_config)


def router(search=SEARCH_BRCA1, gene=GENE_HGNC_BRCA1, sections=None, calls=None):
    """Fake ``_get`` answering by path; ``sections`` overrides per-suffix payloads/exceptions."""
    sections = {
        "orthologs": ORTHOLOGS_BRCA1,
        "phenotypes": PHENOTYPES_BRCA1,
        "molecular-interactions": INTERACTIONS_BRCA1,
        **(sections or {}),
    }

    async def fake(path, params=None):
        if calls is not None:
            calls.append((path, dict(params or {})))
        payload = None
        if path == "search":
            payload = search
        elif path.startswith("gene/") and path.count("/") == 1:
            payload = gene
        else:
            payload = sections[path.rsplit("/", 1)[1]]
        if isinstance(payload, Exception):
            raise payload
        return copy.deepcopy(payload)

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ALLIANCE
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("HGNC:1100", ("id", "HGNC:1100")),
            ("hgnc:1100", ("id", "HGNC:1100")),
            (" Mgi : 104537 ", ("id", "MGI:104537")),
            ("ZFIN:ZDB-GENE-990415-72", ("id", "ZFIN:ZDB-GENE-990415-72")),
            ("xenbase:XB-GENE-1006488", ("id", "Xenbase:XB-GENE-1006488")),
            ("WB:WBGene00004930", ("id", "WB:WBGene00004930")),
            ("fb:FBgn0003462", ("id", "FB:FBgn0003462")),
            ("SGD:S000003865", ("id", "SGD:S000003865")),
            ("RGD:2218", ("id", "RGD:2218")),
            ("BRCA1", ("symbol", "BRCA1")),
            ("sod-1", ("symbol", "sod-1")),
            ("NCBIGene:672", None),
            ("", None),
            ("   ", None),
            ("two words", None),
        ],
    )
    def test_parse_id(self, raw, expected):
        assert AllianceGenomeAdapter._parse_id(raw) == expected

    def test_species_default_from_env(self, lookup_config, monkeypatch):
        monkeypatch.setenv("ALLIANCE_SPECIES", "mouse")
        assert AllianceGenomeAdapter(lookup_config).default_species == "Mus musculus"
        monkeypatch.setenv("ALLIANCE_SPECIES", "Danio rerio")
        assert AllianceGenomeAdapter(lookup_config).default_species == "Danio rerio"
        monkeypatch.setenv("ALLIANCE_SPECIES", "  ")
        assert AllianceGenomeAdapter(lookup_config).default_species is None

    def test_text_helpers(self):
        assert alliance_adapter._text({"displayText": "a", "formatText": "b"}) == "a"
        assert alliance_adapter._text({"formatText": "b"}) == "b"
        assert alliance_adapter._text("c") == "c"
        assert alliance_adapter._text(None) == ""
        assert alliance_adapter._name({"name": "n"}) == "n"
        assert alliance_adapter._name(None) == ""


class FakeResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, text):
        self.text = text
        self.posts = []

    def post(self, url, params=None, json=None):
        self.posts.append((url, params, json))
        return FakeResponse(self.text)


class TestHttp:
    @pytest.mark.asyncio
    async def test_get_returns_dict_only(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"a": 1})) as req:
            assert await adapter._get("gene/HGNC:1100", {"x": 1}) == {"a": 1}
        assert req.call_args.args[0] == "https://www.alliancegenome.org/api/gene/HGNC:1100"
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[1])):
            assert await adapter._get("x") == {}

    @pytest.mark.asyncio
    async def test_post_sends_gene_id_in_body(self, adapter):
        session = FakeSession('{"results": [], "total": 0}')
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            data = await adapter._post_ids("disease", "HGNC:1100", {"limit": 2})
        url, params, body = session.posts[0]
        assert url.endswith("/api/disease") and params == {"limit": 2}
        assert body == ["HGNC:1100"]  # the body filters, the geneID query parameter does not
        assert data == {"results": [], "total": 0}

    @pytest.mark.asyncio
    async def test_post_non_dict_is_empty(self, adapter):
        session = FakeSession("[]")
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            assert await adapter._post_ids("disease", "HGNC:1100", {}) == {}

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(alliance_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(alliance_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._get("a")
            await adapter._get("b")
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6


class TestSearch:
    @pytest.mark.asyncio
    async def test_exact_symbol_then_species_order(self, adapter):
        calls = []
        with patch.object(adapter, "_get", router(calls=calls)):
            results = await adapter.search_concepts("BRCA1", limit=10)
        assert [c.primary_id for c in results] == [
            "HGNC:1100",
            "MGI:104537",
            "RGD:2218",
            "HGNC:58363",
        ]
        path, params = calls[0]
        assert path == "search"
        assert params["category"] == "gene_search_result"
        assert params["q"] == "BRCA1" and params["offset"] == 0 and "species" not in params
        human = results[0]
        assert human.concept_type == ConceptType.GENE
        assert human.categories == ["Homo sapiens"]
        assert human.synonyms == ["BRCA1 DNA repair associated", "BRCC1", "RNF53"]
        assert human.definitions == ["Enables ubiquitin protein ligase activity."]
        assert human.semantic_types == ["protein_coding_gene"]
        assert human.identifiers[0].url == "https://www.alliancegenome.org/gene/HGNC:1100"
        rat = [c for c in results if c.primary_id == "RGD:2218"][0]
        assert rat.definitions == ["Enables chromatin binding activity (MOD)."]
        assert rat.source_data[KnowledgeSource.ALLIANCE]["diseases"] == [
            "breast cancer",
            "ovarian cancer",
        ]
        bare = [c for c in results if c.primary_id == "HGNC:58363"][0]
        assert bare.definitions == [] and bare.synonyms == ["BRCA1 overlapping transcript 1"]

    @pytest.mark.asyncio
    async def test_limit_and_row_bounds(self, adapter):
        calls = []
        with patch.object(adapter, "_get", router(calls=calls)):
            results = await adapter.search_concepts("BRCA1", limit=2)
            await adapter.search_concepts("BRCA1", limit=500)
        assert len(results) == 2
        assert calls[0][1]["limit"] == 20  # floor so re-ranking sees a useful window
        assert calls[1][1]["limit"] == 50  # ceiling

    @pytest.mark.asyncio
    async def test_species_filter_and_alias(self, adapter):
        calls = []
        with patch.object(adapter, "_get", router(search=SEARCH_SOD1_ONLY_FLY, calls=calls)):
            results = await adapter.search_concepts("sod1", species="fly")
        assert calls[0][1]["species"] == "Drosophila melanogaster"
        assert results[0].primary_id == "FB:FBgn0003462"

    @pytest.mark.asyncio
    async def test_species_from_environment(self, lookup_config, monkeypatch):
        monkeypatch.setenv("ALLIANCE_SPECIES", "human")
        adapter = AllianceGenomeAdapter(lookup_config)
        calls = []
        with patch.object(adapter, "_get", router(calls=calls)):
            await adapter.search_concepts("BRCA1")
            await adapter.search_concepts("BRCA1", species="mouse")
        assert calls[0][1]["species"] == "Homo sapiens"
        assert calls[1][1]["species"] == "Mus musculus"

    @pytest.mark.asyncio
    async def test_dedupes_and_skips_unusable_hits(self, adapter):
        dup = copy.deepcopy(SEARCH_BRCA1)
        dup["results"].append(copy.deepcopy(dup["results"][1]))
        with patch.object(adapter, "_get", router(search=dup)):
            results = await adapter.search_concepts("BRCA1", limit=20)
        assert [c.primary_id for c in results].count("HGNC:1100") == 1
        assert "HGNC:1" not in [c.primary_id for c in results]  # no symbol

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("  ", 5), (None, 5), ("BRCA1", 0)])
    async def test_empty_input(self, adapter, query, limit):
        with patch.object(adapter, "_get", AsyncMock(side_effect=AssertionError("no call"))):
            assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_empty_and_error(self, adapter):
        with patch.object(adapter, "_get", router(search=SEARCH_EMPTY)):
            assert await adapter.search_concepts("zzzz") == []
        with patch.object(adapter, "_get", router(search=RuntimeError("boom"))):
            assert await adapter.search_concepts("BRCA1") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_record(self, adapter):
        calls = []
        with patch.object(adapter, "_get", router(calls=calls)):
            concept = await adapter.get_concept_details("hgnc:1100")
        assert calls[0][0] == "gene/HGNC:1100"
        assert concept.primary_id == "HGNC:1100" and concept.primary_label == "BRCA1"
        assert concept.synonyms == ["BRCA1 DNA repair associated", "BROVCA1", "IRIS"]
        assert concept.definitions == ["MOD text."]  # MOD-provided preferred
        assert concept.categories == ["Homo sapiens"]
        assert concept.semantic_types == ["protein_coding_gene"]
        data = concept.source_data[KnowledgeSource.ALLIANCE]
        assert data["location"] == {
            "chromosome": "17",
            "start": 43044292,
            "end": 43170327,
            "strand": "-",
        }
        uniprot = [x for x in data["cross_references"] if x.startswith("UniProtKB")]
        assert len(uniprot) == alliance_adapter._MAX_UNIPROT_XREFS
        assert uniprot[0] == "UniProtKB:P38398"  # canonical first
        assert "BioGRID:1" not in data["cross_references"]

    @pytest.mark.asyncio
    async def test_species_record_with_automated_description_only(self, adapter):
        with patch.object(adapter, "_get", router(gene=GENE_ZFIN_FGF8A)):
            concept = await adapter.get_concept_details("ZFIN:ZDB-GENE-990415-72")
        assert concept.definitions == ["Automated only."]
        assert concept.source_data[KnowledgeSource.ALLIANCE]["location"] == {}

    @pytest.mark.asyncio
    async def test_unwrapped_minimal_record(self, adapter):
        with patch.object(adapter, "_get", router(gene=GENE_BARE)):
            concept = await adapter.get_concept_details("MGI:1")
        assert concept.primary_label == "Abc1" and concept.definitions == []

    @pytest.mark.asyncio
    async def test_record_without_symbol_is_none(self, adapter):
        with patch.object(adapter, "_get", router(gene={"gene": {"primaryExternalId": "X:1"}})):
            assert await adapter.get_concept_details("MGI:1") is None

    @pytest.mark.asyncio
    async def test_symbol_resolves_through_search(self, adapter):
        calls = []
        with patch.object(adapter, "_get", router(calls=calls)):
            concept = await adapter.get_concept_details("brca1")
        assert [c[0] for c in calls] == ["search", "gene/HGNC:1100"]
        assert concept.primary_id == "HGNC:1100"

    @pytest.mark.asyncio
    async def test_unresolvable_inputs(self, adapter):
        with patch.object(adapter, "_get", router(search=SEARCH_EMPTY)):
            assert await adapter.get_concept_details("NOSUCH") is None
        with patch.object(adapter, "_get", AsyncMock(side_effect=AssertionError("no call"))):
            assert await adapter.get_concept_details("NCBIGene:672") is None
            assert await adapter.get_concept_details("") is None

    @pytest.mark.asyncio
    async def test_unknown_id_400_returns_none(self, adapter):
        with patch.object(adapter, "_get", router(gene=RuntimeError("400 Bad Request"))):
            assert await adapter.get_concept_details("HGNC:99999999") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_cross_references(self, adapter):
        with patch.object(adapter, "_get", router()):
            mappings = await adapter.get_mappings("HGNC:1100")
        by_source = {}
        for m in mappings:
            by_source.setdefault(m["toSource"], []).append(m["toId"])
        assert by_source["Ensembl"] == ["ENSEMBL:ENSG00000012048"]
        assert by_source["NCBI Gene"] == ["NCBI_Gene:672"]
        assert by_source["OMIM"] == ["OMIM:113705"]
        assert by_source["PANTHER"] == ["PANTHER:PTHR13763"]
        assert by_source["RGD"] == ["RGD:69132"]
        assert by_source["UniProt"][0] == "UniProtKB:P38398"
        assert len(by_source["UniProt"]) == alliance_adapter._MAX_UNIPROT_XREFS
        assert "HGNC" not in by_source  # the gene's own id is not a mapping
        assert all(
            m["fromId"] == "HGNC:1100" and m["mappingType"] == "xref" and m["confidence"] == 0.95
            for m in mappings
        )

    @pytest.mark.asyncio
    async def test_invalid_and_errors(self, adapter):
        assert await adapter.get_mappings("NCBIGene:672") == []
        with patch.object(adapter, "_get", router(gene=RuntimeError("boom"))):
            assert await adapter.get_mappings("HGNC:1100") == []
        with patch.object(adapter, "_get", router(search=SEARCH_EMPTY)):
            assert await adapter.get_mappings("NOSUCH") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_all_sections(self, adapter):
        calls = []
        with (
            patch.object(adapter, "_get", router(calls=calls)),
            patch.object(
                adapter, "_post_ids", AsyncMock(return_value=copy.deepcopy(DISEASES_BRCA1))
            ) as post,
        ):
            edges = await adapter.get_relationships("HGNC:1100")
        by_label = {}
        for edge in edges:
            by_label.setdefault(edge["relation_label"], []).append(edge)
        assert set(by_label) == {
            "ortholog_of",
            "associated_with_disease",
            "has_phenotype",
            "interacts_with",
        }
        assert all(e["source"] == "ALLIANCE" for e in edges)

        mouse, worm = by_label["ortholog_of"]
        assert mouse["related_id"] == "MGI:104537" and mouse["related_name"] == "Brca1"
        assert mouse["related_species"] == "Mus musculus"
        assert mouse["best"] is True and mouse["best_reverse"] is True
        assert mouse["methods_matched"] == 3 and mouse["methods_total"] == 4
        assert mouse["confidence"] == "high" and mouse["stringency"] == "stringent"
        assert worm["best"] is False

        diseases = by_label["associated_with_disease"]
        assert [(d["related_id"], d["association"]) for d in diseases] == [
            ("DOID:3458", "is_implicated_in"),
            ("DOID:1612", "is_marker_for"),
            ("DOID:1612", "is_implicated_in"),
        ]
        assert diseases[0]["evidence_codes"] == ["IMP"] and diseases[2]["evidence_codes"] == []
        assert diseases[0]["total_annotations"] == 30
        assert post.call_args.args[:2] == ("disease", "HGNC:1100")
        assert post.call_args.args[2]["limit"] == 10

        phenotypes = by_label["has_phenotype"]
        assert [p["related_id"] for p in phenotypes] == ["HP:0003270", "HP:0002027", ""]
        assert phenotypes[1]["n_annotations"] == 3 and len(phenotypes[1]["publications"]) == 5
        assert phenotypes[2]["related_name"] == "free text only phenotype"
        assert phenotypes[0]["total_phenotypes"] == 166

        partners = [(e["related_id"], e["related_name"]) for e in by_label["interacts_with"]]
        assert partners == [("HGNC:13666", "AAAS"), ("HGNC:20", "S")]
        assert by_label["interacts_with"][0]["total_interaction_records"] == 2499
        assert by_label["interacts_with"][0]["interaction_type"] == "physical association"

        limits = {c[0].rsplit("/", 1)[1]: c[1]["limit"] for c in calls if "/" in c[0]}
        assert limits == {"orthologs": 25, "phenotypes": 10, "molecular-interactions": 15}

    @pytest.mark.asyncio
    async def test_failing_section_is_skipped(self, adapter):
        sections = {"orthologs": RuntimeError("boom")}
        with (
            patch.object(adapter, "_get", router(sections=sections)),
            patch.object(adapter, "_post_ids", AsyncMock(side_effect=RuntimeError("boom"))),
        ):
            edges = await adapter.get_relationships("HGNC:1100")
        assert {e["relation_label"] for e in edges} == {"has_phenotype", "interacts_with"}

    @pytest.mark.asyncio
    async def test_empty_sections(self, adapter):
        empty = {"results": [], "total": 0}
        sections = dict.fromkeys(("orthologs", "phenotypes", "molecular-interactions"), empty)
        with (
            patch.object(adapter, "_get", router(sections=sections)),
            patch.object(adapter, "_post_ids", AsyncMock(return_value=empty)),
        ):
            assert await adapter.get_relationships("HGNC:1100") == []

    @pytest.mark.asyncio
    async def test_symbol_resolution_and_invalid(self, adapter):
        calls = []
        empty = {"results": [], "total": 0}
        sections = dict.fromkeys(("orthologs", "phenotypes", "molecular-interactions"), empty)
        with (
            patch.object(adapter, "_get", router(sections=sections, calls=calls)),
            patch.object(adapter, "_post_ids", AsyncMock(return_value=empty)),
        ):
            await adapter.get_relationships("BRCA1")
        assert calls[0][0] == "search" and calls[1][0] == "gene/HGNC:1100/orthologs"
        assert await adapter.get_relationships("NCBIGene:672") == []
        with patch.object(adapter, "_get", router(search=SEARCH_EMPTY)):
            assert await adapter.get_relationships("NOSUCH") == []

    @pytest.mark.asyncio
    async def test_resolution_error_returns_empty(self, adapter):
        with patch.object(adapter, "_get", router(search=RuntimeError("boom"))):
            assert await adapter.get_relationships("BRCA1") == []
