"""Unit tests for PanelAppAdapter (Genomics England PanelApp REST API); no network."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import panelapp_adapter
from knowledge_lookup.adapters.panelapp_adapter import PanelAppAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.panelapp_responses import (
    BRCA1_GENE_RECORDS,
    HGNC_FETCH_BRCA1,
    PANEL_158_AMBER_GENES,
    PANEL_158_DETAIL,
    PANEL_158_GREEN_GENES,
    PANEL_158_RED_GENES,
    PANELS_PAGE,
)

pytestmark = pytest.mark.unit

BASE = panelapp_adapter.PANELAPP_DEFAULT_BASE
EMPTY = {"count": 0, "next": None, "previous": None, "results": []}


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(panelapp_adapter, "_MIN_INTERVAL", 0.0)
    monkeypatch.delenv("PANELAPP_API_BASE", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return PanelAppAdapter(lookup_config)


def router(
    panels=PANELS_PAGE,
    genes=BRCA1_GENE_RECORDS,
    detail=PANEL_158_DETAIL,
    by_level=None,
    hgnc=HGNC_FETCH_BRCA1,
):
    """Fake ``_make_request`` answering by URL; panel gene pages by ``confidence_level``."""
    levels = by_level or {
        "3": PANEL_158_GREEN_GENES,
        "2": PANEL_158_AMBER_GENES,
        "1": PANEL_158_RED_GENES,
    }

    async def fake(url, params=None, headers=None, json_data=None):
        if url.startswith("https://rest.genenames.org/fetch/hgnc_id/"):
            if isinstance(hgnc, Exception):
                raise hgnc
            return copy.deepcopy(hgnc)
        path = url.removeprefix(BASE + "/")
        if path == "panels/":
            if isinstance(panels, Exception):
                raise panels
            return copy.deepcopy(panels)
        if path == "genes/":
            if isinstance(genes, Exception):
                raise genes
            if params["entity_name"] != "BRCA1":
                return copy.deepcopy(EMPTY)
            return copy.deepcopy(genes)
        if path.endswith("/genes/"):
            if isinstance(by_level, Exception):
                raise by_level
            return copy.deepcopy(levels.get(params["confidence_level"], EMPTY))
        if path.startswith("panels/"):
            if isinstance(detail, Exception):
                raise detail
            return copy.deepcopy(detail)
        raise AssertionError(f"unexpected URL {url}")

    return fake


def patched(adapter, **kwargs):
    return patch.object(adapter, "_make_request", AsyncMock(side_effect=router(**kwargs)))


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.PANELAPP
        assert adapter.is_available() is True

    def test_default_base_and_site(self, adapter):
        assert adapter.base_url == BASE
        assert adapter.site_url == "https://panelapp.genomicsengland.co.uk"

    def test_base_url_override_strips_slash(self, lookup_config, monkeypatch):
        monkeypatch.setenv("PANELAPP_API_BASE", "https://panelapp-aus.org/api/v1/")
        aus = PanelAppAdapter(lookup_config)
        assert aus.base_url == "https://panelapp-aus.org/api/v1"
        assert aus.site_url == "https://panelapp-aus.org"

    @pytest.mark.parametrize("bad", ["http://panelapp.example.org/api/v1", "ftp://x", "nonsense"])
    def test_non_https_base_is_rejected(self, lookup_config, monkeypatch, bad):
        monkeypatch.setenv("PANELAPP_API_BASE", bad)
        assert PanelAppAdapter(lookup_config).base_url == BASE

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("158", ("panel", "158")),
            ("panelapp:158", ("panel", "158")),
            ("PANEL:158", ("panel", "158")),
            ("HGNC:1100", ("hgnc", "1100")),
            ("hgnc: 1100", ("hgnc", "1100")),
            ("BRCA1", ("symbol", "BRCA1")),
            ("  brca1 ", ("symbol", "BRCA1")),
            ("symbol:il6", ("symbol", "IL6")),
            ("HLA-DRB1", ("symbol", "HLA-DRB1")),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert PanelAppAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "two words", "!!", None])
    def test_unsupported_ids(self, raw):
        assert PanelAppAdapter._parse_id(raw) is None

    def test_level_normalisation(self):
        assert panelapp_adapter._normalise_level("green") == "3"
        assert panelapp_adapter._normalise_level("RED") == "1"
        assert panelapp_adapter._normalise_level(2) == "2"
        assert panelapp_adapter._normalise_level(None) is None
        assert panelapp_adapter._normalise_level("purple") is None
        assert panelapp_adapter._level_name("3") == "green"
        assert panelapp_adapter._level_name(None) == "none"


class TestSearch:
    @pytest.mark.asyncio
    async def test_panel_search_ranks_name_hits_before_disorder_hits(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("ataxia", limit=10)
        ids = [c.primary_id for c in results]
        # 477 / 20 / 1213 have "ataxia" in the name; the biggest panel first within a score
        assert ids == ["477", "20", "1213"]
        assert all(c.concept_type == ConceptType.DISEASE for c in results)
        assert results[0].confidence_score == 0.8
        assert results[0].source_data[KnowledgeSource.PANELAPP]["stats"]["number_of_genes"] == 330

    @pytest.mark.asyncio
    async def test_search_matches_relevant_disorders_with_lower_score(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("ovarian cancer", limit=10)
        assert [c.primary_id for c in results] == ["158"]
        assert results[0].confidence_score == 0.6

    @pytest.mark.asyncio
    async def test_search_exact_name_scores_highest(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("hereditary ataxia", limit=10)
        assert results[0].primary_id == "20" and results[0].confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_search_adds_exact_gene_symbol_first(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("brca1", limit=5)
        assert results[0].primary_id == "HGNC:1100"
        assert results[0].concept_type == ConceptType.GENE
        assert results[0].confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_search_respects_limit_and_blank(self, adapter):
        with patched(adapter):
            assert len(await adapter.search_concepts("ataxia", limit=1)) == 1
            assert await adapter.search_concepts("ataxia", limit=0) == []
            assert await adapter.search_concepts("   ") == []
            assert await adapter.search_concepts("") == []

    @pytest.mark.asyncio
    async def test_search_no_match(self, adapter):
        with patched(adapter):
            assert await adapter.search_concepts("zzzz nothing") == []

    @pytest.mark.asyncio
    async def test_search_survives_gene_lookup_failure(self, adapter):
        with patched(adapter, genes=RuntimeError("boom")):
            results = await adapter.search_concepts("ataxia", limit=5)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_survives_panel_list_failure(self, adapter):
        with patched(adapter, panels=RuntimeError("boom")):
            results = await adapter.search_concepts("brca1")
        assert [c.primary_id for c in results] == ["HGNC:1100"]
        with patched(adapter, panels=RuntimeError("boom"), genes=RuntimeError("boom")):
            assert await adapter.search_concepts("brca1") == []

    @pytest.mark.asyncio
    async def test_multi_word_query_skips_gene_lookup(self, adapter):
        with patched(adapter) as req:
            await adapter.search_concepts("breast cancer", limit=5)
        urls = [call.args[0] for call in req.call_args_list]
        assert not any(u.endswith("/genes/") for u in urls)


class TestPanelList:
    @pytest.mark.asyncio
    async def test_list_is_cached_between_searches(self, adapter):
        with patched(adapter) as req:
            await adapter.search_concepts("ataxia")
            await adapter.search_concepts("ataxia telangiectasia")
        panel_calls = [c for c in req.call_args_list if c.args[0].endswith("/panels/")]
        assert len(panel_calls) == 1

    @pytest.mark.asyncio
    async def test_list_expires(self, adapter, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr(
            panelapp_adapter, "time", SimpleNamespace(monotonic=lambda: clock["now"])
        )
        with patched(adapter) as req:
            await adapter._panel_list()
            clock["now"] += panelapp_adapter._PANEL_LIST_TTL - 1
            await adapter._panel_list()
            clock["now"] += 2
            await adapter._panel_list()
        assert len(req.call_args_list) == 2

    @pytest.mark.asyncio
    async def test_list_follows_pages_and_dedupes(self, adapter):
        page1 = {**PANELS_PAGE, "next": "https://x/?page=2", "results": PANELS_PAGE["results"][:2]}
        page2 = {"count": 4, "next": None, "results": PANELS_PAGE["results"][1:]}

        async def fake(url, params=None, headers=None, json_data=None):
            return copy.deepcopy(page1 if params["page"] == 1 else page2)

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)) as req:
            panels = await adapter._panel_list()
        assert [p["id"] for p in panels] == [477, 1213, 20, 158]
        assert req.call_count == 2

    @pytest.mark.asyncio
    async def test_get_returns_empty_dict_for_non_dict(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=[1, 2])):
            assert await adapter._get("panels/") == {}

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(panelapp_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(panelapp_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._get("a")
            await adapter._get("b")
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6


class TestGeneRecords:
    @pytest.mark.asyncio
    async def test_gene_records_follow_pages(self, adapter):
        page1 = {**BRCA1_GENE_RECORDS, "next": "https://x/?page=2"}
        page2 = {"count": 4, "next": None, "results": BRCA1_GENE_RECORDS["results"][:1]}
        seen_params = []

        async def fake(url, params=None, headers=None, json_data=None):
            seen_params.append(dict(params))
            return copy.deepcopy(page1 if "page" not in params else page2)

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            records = await adapter._gene_records("brca1")
        assert len(records) == 5
        assert seen_params[0] == {"entity_name": "BRCA1"} and seen_params[1]["page"] == 2

    @pytest.mark.asyncio
    async def test_non_gene_entities_are_dropped(self, adapter):
        str_rec = {**BRCA1_GENE_RECORDS["results"][0], "entity_type": "str"}
        page = {"count": 1, "next": None, "results": [str_rec, "junk"]}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=page)):
            assert await adapter._gene_records("BRCA1") == []

    @pytest.mark.asyncio
    async def test_hgnc_symbol_is_cached(self, adapter):
        with patched(adapter) as req:
            assert await adapter._hgnc_symbol("1100") == "BRCA1"
            assert await adapter._hgnc_symbol("1100") == "BRCA1"
        assert req.call_count == 1

    @pytest.mark.asyncio
    async def test_hgnc_symbol_missing(self, adapter):
        with patched(adapter, hgnc={"response": {"numFound": 0, "docs": []}}):
            assert await adapter._hgnc_symbol("999999") is None
        with patched(adapter, hgnc={"response": {"docs": [{"hgnc_id": "HGNC:1"}]}}):
            assert await adapter._hgnc_symbol("1") is None


class TestDetails:
    @pytest.mark.asyncio
    async def test_gene_details_by_hgnc_id(self, adapter):
        with patched(adapter) as req:
            concept = await adapter.get_concept_details("HGNC:1100")
        assert concept.primary_id == "HGNC:1100" and concept.primary_label == "BRCA1"
        assert concept.concept_type == ConceptType.GENE
        assert concept.confidence_score == 0.95
        assert "RNF53" in concept.synonyms
        assert concept.definitions == ["BRCA1, DNA repair associated"]
        data = concept.source_data[KnowledgeSource.PANELAPP]
        assert data["n_panels"] == 4
        assert data["confidence_counts"] == {"green": 2, "amber": 1, "red": 1}
        assert data["ensembl_id"] == "ENSG00000012048" and data["omim_gene"] == ["113705"]
        assert any("MONOALLELIC" in m for m in data["green_modes_of_inheritance"])
        # symbol resolution went through HGNC, then the genes endpoint with the upper-case symbol
        assert req.call_args_list[-1].args[1] == {"entity_name": "BRCA1"}

    @pytest.mark.asyncio
    async def test_gene_details_by_symbol_needs_no_hgnc_call(self, adapter):
        with patched(adapter) as req:
            concept = await adapter.get_concept_details("brca1")
        assert concept.primary_id == "HGNC:1100"
        assert all("genenames" not in c.args[0] for c in req.call_args_list)

    @pytest.mark.asyncio
    async def test_panel_details(self, adapter):
        with patched(adapter):
            concept = await adapter.get_concept_details("panelapp:158")
        assert concept.primary_id == "158" and concept.primary_label == "Familial breast cancer"
        assert "Familial breast and or ovarian cancer" in concept.synonyms
        assert "Tumour syndromes" in concept.categories
        assert "version 1.28" in concept.definitions[0]
        data = concept.source_data[KnowledgeSource.PANELAPP]
        assert data["gene_confidence_counts"] == {"green": 2, "amber": 1, "red": 2}
        assert data["stats"]["number_of_genes"] == 27
        assert data["types"] == ["rare-disease-100k"]

    @pytest.mark.asyncio
    async def test_details_unknown_and_invalid(self, adapter):
        with patched(adapter):
            assert await adapter.get_concept_details("FAKEGENE") is None
            assert await adapter.get_concept_details("") is None
            assert await adapter.get_concept_details("not valid!") is None
        with patched(adapter, hgnc={"response": {"docs": []}}):
            assert await adapter.get_concept_details("HGNC:999999") is None

    @pytest.mark.asyncio
    async def test_details_never_raise(self, adapter):
        with patched(adapter, detail=RuntimeError("boom")):
            assert await adapter.get_concept_details("158") is None
        with patched(adapter, genes=RuntimeError("boom")):
            assert await adapter.get_concept_details("BRCA1") is None

    @pytest.mark.asyncio
    async def test_panel_without_name_is_skipped(self, adapter):
        with patched(adapter, detail={"id": 5, "name": ""}):
            assert await adapter.get_concept_details("5") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_gene_mappings(self, adapter):
        with patched(adapter):
            mappings = await adapter.get_mappings("HGNC:1100")
        by_target = {m["toSource"]: m for m in mappings}
        assert set(by_target) == {"HGNC.SYMBOL", "ENSEMBL", "OMIM"}
        assert by_target["ENSEMBL"]["toId"] == "ENSG00000012048"
        assert by_target["OMIM"]["toId"] == "OMIM:113705"
        assert by_target["HGNC.SYMBOL"]["toId"] == "HGNC.SYMBOL:BRCA1"
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "HGNC:1100" and m["fromSource"] == "HGNC"

    @pytest.mark.asyncio
    async def test_mappings_empty_cases(self, adapter):
        with patched(adapter):
            assert await adapter.get_mappings("158") == []
            assert await adapter.get_mappings("") == []
            assert await adapter.get_mappings("FAKEGENE") == []
        with patched(adapter, genes=RuntimeError("boom")):
            assert await adapter.get_mappings("BRCA1") == []

    def test_ensembl_prefers_newest_grch38_then_grch37(self):
        gene_data = {
            "ensembl_genes": {
                "GRch38": {"90": {"ensembl_id": "ENSG_OLD"}, "99": {"ensembl_id": "ENSG_NEW"}}
            }
        }
        assert PanelAppAdapter._ensembl_id(gene_data) == "ENSG_NEW"
        only37 = {"ensembl_genes": {"GRch37": {"82": {"ensembl_id": "ENSG37"}}}}
        assert PanelAppAdapter._ensembl_id(only37) == "ENSG37"
        assert PanelAppAdapter._ensembl_id({}) is None

    @pytest.mark.asyncio
    async def test_mappings_without_gene_data(self, adapter):
        bare = {"count": 1, "next": None, "results": [{"entity_type": "gene", "panel": {"id": 1}}]}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=bare)):
            assert await adapter.get_mappings("BRCA1") == []


class TestGeneRelationships:
    @pytest.mark.asyncio
    async def test_panels_ordered_green_first_with_evidence(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("BRCA1", limit=10)
        panels = [r for r in rels if r["relation_label"] == "listed_in_panel"]
        assert [r["confidence_level"] for r in panels] == ["green", "green", "amber", "red"]
        assert [r["related_id"] for r in panels[:2]] == ["399", "158"]  # by name within green
        first = panels[1]
        assert first["related_name"] == "Familial breast cancer"
        assert first["source"] == "PANELAPP" and first["panel_version"] == "1.28"
        assert first["mode_of_inheritance"].startswith("MONOALLELIC")
        assert first["publications"] == [] and first["phenotypes"]

    @pytest.mark.asyncio
    async def test_phenotypes_skip_red_and_prefer_omim(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("BRCA1", limit=10)
        phenotypes = [r for r in rels if r["relation_label"] == "associated_with_phenotype"]
        assert phenotypes[0]["related_id"] == "OMIM:604370"
        names = [p["related_name"] for p in phenotypes]
        assert "Non-medullary thyroid cancer" not in names  # red entry
        assert len(names) == len({n.casefold() for n in names})
        assert "Prostate cancer, MONDO:0008315" in names  # amber is kept

    @pytest.mark.asyncio
    async def test_limit_applies_per_relation_type(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("BRCA1", limit=1)
        labels = [r["relation_label"] for r in rels]
        assert labels.count("listed_in_panel") == 1
        assert labels.count("associated_with_phenotype") == 1

    @pytest.mark.asyncio
    async def test_evidence_level_filter(self, adapter):
        with patched(adapter):
            amber = await adapter.get_relationships("BRCA1", limit=10, evidence_level="amber")
            red = await adapter.get_relationships("BRCA1", evidence_level=1)
        assert {r["confidence_level"] for r in amber} == {"amber"}
        assert [r["relation_label"] for r in red] == ["listed_in_panel"]  # red phenotypes skipped

    @pytest.mark.asyncio
    async def test_duplicate_panels_collapse(self, adapter):
        dup = copy.deepcopy(BRCA1_GENE_RECORDS)
        dup["results"].append(copy.deepcopy(dup["results"][0]))
        with patched(adapter, genes=dup):
            rels = await adapter.get_relationships("BRCA1", limit=10)
        ids = [r["related_id"] for r in rels if r["relation_label"] == "listed_in_panel"]
        assert len(ids) == len(set(ids)) == 4

    @pytest.mark.asyncio
    async def test_invalid_inputs(self, adapter):
        with patched(adapter):
            assert await adapter.get_relationships("BRCA1", limit=0) == []
            assert await adapter.get_relationships("BRCA1", evidence_level="purple") == []
            assert await adapter.get_relationships("") == []
            assert await adapter.get_relationships("FAKEGENE") == []
        with patched(adapter, genes=RuntimeError("boom")):
            assert await adapter.get_relationships("BRCA1") == []


class TestPanelRelationships:
    @pytest.mark.asyncio
    async def test_genes_best_evidence_first_then_disorders(self, adapter):
        with patched(adapter) as req:
            rels = await adapter.get_relationships("158", limit=10)
        genes = [r for r in rels if r["relation_label"] == "has_gene"]
        assert [(r["related_name"], r["confidence_level"]) for r in genes] == [
            ("ATM", "green"),
            ("BARD1", "green"),
            ("ATRIP", "amber"),
            ("AR", "red"),
            ("BRIP1", "red"),
        ]
        assert genes[0]["related_id"] == "HGNC:795"
        assert genes[0]["mode_of_inheritance"] and genes[0]["publications"] == ["19781682"]
        disorders = [r for r in rels if r["relation_label"] == "has_relevant_disorder"]
        assert [d["related_name"] for d in disorders] == ["Familial breast and or ovarian cancer"]
        assert disorders[0]["is_test_directory_code"] is False
        levels = [c.args[1]["confidence_level"] for c in req.call_args_list]
        assert levels == ["3", "2", "1"]

    @pytest.mark.asyncio
    async def test_limit_stops_before_lower_levels(self, adapter):
        with patched(adapter) as req:
            rels = await adapter.get_relationships("158", limit=2)
        assert [r["related_name"] for r in rels if r["relation_label"] == "has_gene"] == [
            "ATM",
            "BARD1",
        ]
        assert [c.args[1]["confidence_level"] for c in req.call_args_list] == ["3"]

    @pytest.mark.asyncio
    async def test_evidence_level_filter(self, adapter):
        with patched(adapter) as req:
            rels = await adapter.get_relationships("158", limit=10, evidence_level="green")
        assert {r["confidence_level"] for r in rels if r["relation_label"] == "has_gene"} == {
            "green"
        }
        assert len(req.call_args_list) == 1

    @pytest.mark.asyncio
    async def test_empty_level_falls_back_to_panel_metadata(self, adapter):
        with patched(adapter, by_level={"3": EMPTY, "2": EMPTY, "1": EMPTY}) as req:
            rels = await adapter.get_relationships("158", limit=5, evidence_level="amber")
        assert [r["relation_label"] for r in rels] == ["has_relevant_disorder"]
        assert req.call_args_list[-1].args[0].endswith("/panels/158/")

    @pytest.mark.asyncio
    async def test_metadata_failure_is_tolerated(self, adapter):
        with patched(
            adapter, by_level={"3": EMPTY, "2": EMPTY, "1": EMPTY}, detail=RuntimeError("boom")
        ):
            assert await adapter.get_relationships("158", evidence_level="green") == []

    @pytest.mark.asyncio
    async def test_test_directory_codes_are_flagged(self, adapter):
        detail = {**PANEL_158_DETAIL, "relevant_disorders": ["R295", "GT65", "Ataxia"]}
        none = {"3": EMPTY, "2": EMPTY, "1": EMPTY}
        with patched(adapter, by_level=none, detail=detail):
            rels = await adapter.get_relationships("158")
        flags = {r["related_name"]: r["is_test_directory_code"] for r in rels}
        assert flags == {"R295": True, "GT65": True, "Ataxia": False}

    @pytest.mark.asyncio
    async def test_paging_inside_one_level(self, adapter):
        page1 = {**PANEL_158_GREEN_GENES, "next": "https://x/?page=2"}
        page2 = {
            "count": 3,
            "next": None,
            "results": [PANEL_158_AMBER_GENES["results"][0]],
        }

        async def fake(url, params=None, headers=None, json_data=None):
            if params["confidence_level"] != "3":
                return copy.deepcopy(EMPTY)
            return copy.deepcopy(page1 if "page" not in params else page2)

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("158", limit=10, evidence_level="green")
        assert [r["related_name"] for r in rels if r["relation_label"] == "has_gene"] == [
            "ATM",
            "BARD1",
            "ATRIP",
        ]

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self, adapter):
        with patched(adapter, by_level=RuntimeError("boom")):
            assert await adapter.get_relationships("158") == []
