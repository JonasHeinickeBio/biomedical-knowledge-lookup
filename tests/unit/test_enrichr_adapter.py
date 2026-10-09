"""Unit tests for EnrichrAdapter (Enrichr gene-set enrichment); no network."""

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import enrichr_adapter
from knowledge_lookup.adapters.enrichr_adapter import DEFAULT_LIBRARIES, EnrichrAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.enrichr_responses import (
    ADD_LIST,
    DATASET_STATISTICS,
    ENRICH_GO,
    ENRICH_HPO,
    ENRICH_KEGG,
    GENEMAP_BRCA1,
    GENEMAP_EMPTY,
    LIBRARY_TEXT_KEGG,
)

pytestmark = pytest.mark.unit

GENES = "IL6 TNF IL1B CXCL8 CRP IFNG IL10"


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(enrichr_adapter, "_MIN_INTERVAL", 0.0)
    monkeypatch.delenv("ENRICHR_LIBRARIES", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return EnrichrAdapter(lookup_config)


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
    def __init__(self, text=ADD_LIST, status=200):
        self.response = FakeResponse(text, status)
        self.posts = []

    def post(self, url, data=None):
        self.posts.append((url, data))
        return self.response


def text_router(enrich=None, library=LIBRARY_TEXT_KEGG, genemap=GENEMAP_BRCA1, calls=None):
    """Fake ``_get_text``: JSON for enrich / genemap / datasetStatistics, text for libraries."""
    enrich = enrich or {
        "KEGG_2026": ENRICH_KEGG,
        "Human_Phenotype_Ontology": ENRICH_HPO,
        "GO_Biological_Process_2025": ENRICH_GO,
    }

    async def fake(path, params):
        if calls is not None:
            calls.append((path, dict(params)))
        if path == "enrich":
            payload = enrich.get(params["backgroundType"], {})
            if isinstance(payload, Exception):
                raise payload
            return json.dumps(payload.get(params["backgroundType"], {}) and payload or {})
        if path == "geneSetLibrary":
            if isinstance(library, Exception):
                raise library
            return library
        if path == "genemap":
            if isinstance(genemap, Exception):
                raise genemap
            return json.dumps(genemap)
        if path == "datasetStatistics":
            return json.dumps(DATASET_STATISTICS)
        raise AssertionError(f"unexpected path {path}")

    return fake


@pytest.fixture
def uploaded(adapter):
    """Adapter whose upload is faked: returns list id 139566674 and records the gene lists."""
    adapter.uploads = []

    async def fake_upload(genes):
        adapter.uploads.append(list(genes))
        return 139566674

    adapter._upload = fake_upload
    return adapter


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.ENRICHR
        assert adapter.is_available() is True

    def test_default_and_env_libraries(self, lookup_config, monkeypatch):
        assert EnrichrAdapter(lookup_config).libraries == DEFAULT_LIBRARIES
        monkeypatch.setenv("ENRICHR_LIBRARIES", " KEGG_2026 , Reactome_2022,KEGG_2026,bad name!,")
        assert EnrichrAdapter(lookup_config).libraries == ("KEGG_2026", "Reactome_2022")
        monkeypatch.setenv("ENRICHR_LIBRARIES", " , ")
        assert EnrichrAdapter(lookup_config).libraries == DEFAULT_LIBRARIES

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("BRCA1", ["BRCA1"]),
            ("brca1, tp53;atm\nchek2", ["BRCA1", "TP53", "ATM", "CHEK2"]),
            ("IL6  il6 TNF", ["IL6", "TNF"]),
            ("Trp53 Cdkn1a", ["TRP53", "CDKN1A"]),
            ("HLA-DRB1 daf-2", ["HLA-DRB1", "DAF-2"]),
            ("", None),
            ("   ", None),
            (None, None),
            ("long covid", None),  # plain lower-case words are not gene symbols
            ("tnf crp", None),
            ("il6 tnf", ["IL6", "TNF"]),  # one gene-like token is enough
            ("IL6 bad|symbol", None),
            ("x" * 40, None),
        ],
    )
    def test_parse_genes(self, query, expected):
        assert EnrichrAdapter._parse_genes(query) == expected

    def test_parse_genes_truncates(self, caplog):
        query = " ".join(f"G{i}" for i in range(enrichr_adapter.MAX_GENES + 50))
        with caplog.at_level(logging.WARNING):
            genes = EnrichrAdapter._parse_genes(query)
        assert len(genes) == enrichr_adapter.MAX_GENES
        assert "truncated" in caplog.text and "G0" not in caplog.text

    def test_library_types(self):
        assert enrichr_adapter._library_type("GO_Biological_Process_2025") == (
            ConceptType.BIOLOGICAL_PROCESS
        )
        assert enrichr_adapter._library_type("GO_Molecular_Function_2025") == (
            ConceptType.MOLECULAR_FUNCTION
        )
        assert enrichr_adapter._library_type("GO_Cellular_Component_2025") == (
            ConceptType.CELLULAR_COMPONENT
        )
        for name in ("KEGG_2026", "Reactome_Pathways_2024", "WikiPathways_2024_Human"):
            assert enrichr_adapter._library_type(name) == ConceptType.PATHWAY
        for name in ("Human_Phenotype_Ontology", "MGI_Mammalian_Phenotype_Level_4_2024"):
            assert enrichr_adapter._library_type(name) == ConceptType.PHENOTYPE
        for name in ("Jensen_DISEASES_Curated_2025", "OMIM_Disease", "DisGeNET"):
            assert enrichr_adapter._library_type(name) == ConceptType.DISEASE
        assert enrichr_adapter._library_type("ChEA_2022") == ConceptType.UNKNOWN

    @pytest.mark.parametrize(
        "cid,expected",
        [
            ("KEGG_2026::MALARIA", ("KEGG_2026", "MALARIA")),
            ("Human_Phenotype_Ontology::Abnormality (HP:0001697)", None),
            ("BRCA1", None),
            ("KEGG_2026::", None),
            ("bad lib::x", None),
            ("", None),
        ],
    )
    def test_split_id(self, cid, expected):
        result = EnrichrAdapter._split_id(cid)
        if cid.startswith("Human_Phenotype"):
            assert result == ("Human_Phenotype_Ontology", "Abnormality (HP:0001697)")
        else:
            assert result == expected


class TestUpload:
    @pytest.mark.asyncio
    async def test_multipart_form_and_cache(self, adapter):
        session = FakeSession()
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            first = await adapter._upload(["IL6", "TNF"])
            second = await adapter._upload(["IL6", "TNF"])
            other = await adapter._upload(["IL6"])
        assert first == second == other == 139566674
        assert len(session.posts) == 2  # identical lists are uploaded once
        url, form = session.posts[0]
        assert url == "https://maayanlab.cloud/Enrichr/addList"
        assert form.is_multipart  # the urlencoded form is rejected with HTTP 400
        fields = {f[0]["name"]: f[2] for f in form._fields}
        assert fields["list"] == "IL6\nTNF"
        assert fields["description"] == enrichr_adapter._UPLOAD_DESCRIPTION
        assert "IL6" not in fields["description"]

    @pytest.mark.asyncio
    async def test_unusable_answer_gives_none(self, adapter):
        for text in ("{}", "[]", '{"userListId": "x"}'):
            session = FakeSession(text)
            with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
                assert await adapter._upload(["IL6"]) is None
        assert adapter._list_ids == {}

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, adapter):
        session = FakeSession("x", status=400)
        with patch.object(adapter, "_get_session", AsyncMock(return_value=session)):
            with pytest.raises(RuntimeError):
                await adapter._upload(["IL6"])

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(enrichr_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(enrichr_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request_text", AsyncMock(return_value="{}")):
            await adapter._get_json("a", {})
            await adapter._get_json("b", {})
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6


class TestEnrich:
    @pytest.mark.asyncio
    async def test_rows_sorted_filtered_and_limited(self, uploaded):
        calls = []
        with patch.object(uploaded, "_get_text", text_router(calls=calls)):
            rows = await uploaded.enrich(GENES, ["KEGG_2026", "Human_Phenotype_Ontology"], 2)
        assert uploaded.uploads == [["IL6", "TNF", "IL1B", "CXCL8", "CRP", "IFNG", "IL10"]]
        assert [(r["library"], r["term"]) for r in rows] == [
            ("KEGG_2026", "MALARIA"),
            ("KEGG_2026", "AMOEBIASIS"),
            ("Human_Phenotype_Ontology", "Abnormality of the pericardium (HP:0001697)"),
        ]
        malaria = rows[0]
        assert malaria["adjusted_p_value"] == pytest.approx(1.1118e-13, rel=1e-3)
        assert malaria["p_value"] == pytest.approx(1.249e-15, rel=1e-3)
        assert malaria["odds_ratio"] == pytest.approx(2720.3, rel=1e-3)
        assert malaria["combined_score"] == pytest.approx(93351.0, rel=1e-3)
        assert malaria["n_overlap"] == 6 and malaria["n_input_genes"] == 7
        assert malaria["term_id"] is None
        assert rows[2]["term_id"] == "HP:0001697"
        assert calls[0] == ("enrich", {"userListId": 139566674, "backgroundType": "KEGG_2026"})

    @pytest.mark.asyncio
    async def test_malformed_rows_are_dropped(self, uploaded):
        with patch.object(uploaded, "_get_text", text_router()):
            rows = await uploaded.enrich("IL6 TNF", ["KEGG_2026"], 50)
        assert [r["term"] for r in rows] == ["MALARIA", "AMOEBIASIS", "WEAK TERM"]
        assert rows[2]["n_overlap"] == 1

    @pytest.mark.asyncio
    async def test_list_input_and_default_libraries(self, uploaded):
        calls = []
        with patch.object(uploaded, "_get_text", text_router(calls=calls)):
            await uploaded.enrich(["il6", "tnf"], None, 1)
        assert uploaded.uploads == [["IL6", "TNF"]]
        assert [c[1]["backgroundType"] for c in calls] == list(DEFAULT_LIBRARIES)

    @pytest.mark.asyncio
    async def test_unknown_library_yields_nothing(self, uploaded):
        with patch.object(uploaded, "_get_text", text_router()):
            assert await uploaded.enrich("IL6 TNF", ["NoSuchLib_2099", "bad name!"], 5) == []

    @pytest.mark.asyncio
    async def test_failing_library_is_skipped(self, uploaded):
        enrich = {
            "KEGG_2026": RuntimeError("boom"),
            "Human_Phenotype_Ontology": ENRICH_HPO,
        }
        with patch.object(uploaded, "_get_text", text_router(enrich=enrich)):
            rows = await uploaded.enrich("IL6 TNF", ["KEGG_2026", "Human_Phenotype_Ontology"], 5)
        assert {r["library"] for r in rows} == {"Human_Phenotype_Ontology"}

    @pytest.mark.asyncio
    async def test_non_dict_enrich_answer(self, uploaded):
        async def fake(path, params):
            return "[1, 2]"

        with patch.object(uploaded, "_get_text", fake):
            assert await uploaded.enrich("IL6 TNF", ["KEGG_2026"], 5) == []

    @pytest.mark.asyncio
    async def test_duplicate_libraries_queried_once(self, uploaded):
        calls = []
        with patch.object(uploaded, "_get_text", text_router(calls=calls)):
            await uploaded.enrich("IL6 TNF", ["KEGG_2026", "KEGG_2026"], 5)
        assert len(calls) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("genes,limit", [("", 5), ("long covid", 5), ([], 5), ("IL6", 0)])
    async def test_nothing_is_sent_for_bad_input(self, adapter, genes, limit):
        with patch.object(adapter, "_upload", AsyncMock(side_effect=AssertionError("no upload"))):
            assert await adapter.enrich(genes, None, limit) == []

    @pytest.mark.asyncio
    async def test_upload_failures(self, adapter):
        with patch.object(adapter, "_upload", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.enrich("IL6 TNF") == []
        with patch.object(adapter, "_upload", AsyncMock(return_value=None)):
            assert await adapter.enrich("IL6 TNF") == []

    @pytest.mark.asyncio
    async def test_genes_never_logged_at_info(self, uploaded, caplog):
        enrich = {"KEGG_2026": RuntimeError("boom"), "Human_Phenotype_Ontology": ENRICH_HPO}
        with caplog.at_level(logging.DEBUG, logger="knowledge_lookup.adapters.enrichr_adapter"):
            with patch.object(uploaded, "_get_text", text_router(enrich=enrich)):
                await uploaded.enrich("IL6 TNF CRP", ["KEGG_2026", "Human_Phenotype_Ontology"])
                await uploaded.search_concepts("IL6 TNF CRP", 3)
        assert caplog.text  # something was logged
        for gene in ("IL6", "TNF", "CRP"):
            assert gene not in caplog.text


class TestSearch:
    @pytest.mark.asyncio
    async def test_interleaves_libraries(self, uploaded):
        uploaded.libraries = (
            "KEGG_2026",
            "Human_Phenotype_Ontology",
            "GO_Biological_Process_2025",
        )
        with patch.object(uploaded, "_get_text", text_router()):
            results = await uploaded.search_concepts(GENES, limit=4)
        assert [c.primary_id for c in results] == [
            "KEGG_2026::MALARIA",
            "Human_Phenotype_Ontology::Abnormality of the pericardium (HP:0001697)",
            "GO_Biological_Process_2025::Regulation of Interleukin-6 Production (GO:0032675)",
            "KEGG_2026::AMOEBIASIS",
        ]

    @pytest.mark.asyncio
    async def test_concept_fields(self, uploaded):
        uploaded.libraries = (
            "KEGG_2026",
            "Human_Phenotype_Ontology",
            "GO_Biological_Process_2025",
        )
        with patch.object(uploaded, "_get_text", text_router()):
            results = await uploaded.search_concepts(GENES, limit=3)
        kegg, hpo, go = results
        assert kegg.concept_type == ConceptType.PATHWAY and kegg.primary_label == "MALARIA"
        assert hpo.concept_type == ConceptType.PHENOTYPE
        assert go.concept_type == ConceptType.BIOLOGICAL_PROCESS
        assert kegg.categories == ["KEGG_2026"] and kegg.semantic_types == ["gene set"]
        assert kegg.confidence_score == 0.9
        assert "adjusted p = 1.11e-13" in kegg.definitions[0]
        assert kegg.identifiers[0].url == "https://maayanlab.cloud/Enrichr/"
        data = kegg.source_data[KnowledgeSource.ENRICHR]
        assert data["library"] == "KEGG_2026" and data["n_input_genes"] == 7
        assert data["overlapping_genes"] == ["IL10", "IL6", "CXCL8", "IFNG", "IL1B", "TNF"]
        assert "over-representation" in data["evidence_note"]
        assert hpo.source_data[KnowledgeSource.ENRICHR]["term_id"] == "HP:0001697"

    @pytest.mark.asyncio
    async def test_weak_terms_get_low_confidence(self, uploaded):
        uploaded.libraries = ("KEGG_2026",)
        with patch.object(uploaded, "_get_text", text_router()):
            results = await uploaded.search_concepts("IL6 TNF", limit=10)
        assert [c.primary_label for c in results][-1] == "WEAK TERM"
        assert results[-1].confidence_score == 0.4

    @pytest.mark.asyncio
    async def test_per_library_share_of_limit(self, uploaded):
        calls = []
        with patch.object(uploaded, "_get_text", text_router(calls=calls)):
            results = await uploaded.search_concepts(GENES, limit=7)
        assert len(calls) == len(DEFAULT_LIBRARIES)
        assert len(results) <= 7

    @pytest.mark.asyncio
    async def test_free_text_is_not_uploaded(self, adapter):
        with patch.object(adapter, "_upload", AsyncMock(side_effect=AssertionError("no upload"))):
            assert await adapter.search_concepts("long covid fatigue", 5) == []
            assert await adapter.search_concepts("", 5) == []
            assert await adapter.search_concepts("IL6", 0) == []

    @pytest.mark.asyncio
    async def test_no_rows_gives_empty(self, uploaded):
        with patch.object(uploaded, "_get_text", text_router(enrich={"none": {}})):
            assert await uploaded.search_concepts("IL6 TNF", 5) == []


class TestLibraries:
    @pytest.mark.asyncio
    async def test_list_libraries(self, adapter):
        with patch.object(adapter, "_get_text", text_router()):
            libs = await adapter.list_libraries()
        assert [lib["libraryName"] for lib in libs] == ["Genome_Browser_PWMs", "KEGG_2026"]

    @pytest.mark.asyncio
    async def test_list_libraries_errors(self, adapter):
        with patch.object(adapter, "_get_text", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.list_libraries() == []
        with patch.object(adapter, "_get_text", AsyncMock(return_value="[]")):
            assert await adapter.list_libraries() == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_term_members(self, adapter):
        calls = []
        with patch.object(adapter, "_get_text", text_router(calls=calls)):
            concept = await adapter.get_concept_details("KEGG_2026::MALARIA")
            again = await adapter.get_concept_details("KEGG_2026::AMOEBIASIS")
        assert concept.primary_id == "KEGG_2026::MALARIA"
        assert concept.concept_type == ConceptType.PATHWAY
        data = concept.source_data[KnowledgeSource.ENRICHR]
        assert data["genes"] == ["ACKR1", "SOS1", "THBS3", "IL6", "TLR2"]
        assert data["n_genes"] == 5 and data["truncated"] is False
        assert again.source_data[KnowledgeSource.ENRICHR]["genes"] == ["IL6", "TNF", "CXCL8"]
        assert len(calls) == 1  # the library is downloaded once and cached

    @pytest.mark.asyncio
    async def test_weights_and_broken_lines(self, adapter):
        with patch.object(adapter, "_get_text", text_router()):
            concept = await adapter.get_concept_details("KEGG_2026::WEIGHTED TERM")
            assert await adapter.get_concept_details("KEGG_2026::BROKEN LINE") is None
        assert concept.source_data[KnowledgeSource.ENRICHR]["genes"] == ["IL6", "TNF"]

    @pytest.mark.asyncio
    async def test_case_insensitive_term_and_term_id(self, adapter):
        text = "Abnormality of the pericardium (HP:0001697)\t\tIL6\tIL10\n"
        with patch.object(adapter, "_get_text", text_router(library=text)):
            concept = await adapter.get_concept_details(
                "Human_Phenotype_Ontology::abnormality of the PERICARDIUM (hp:0001697)"
            )
        assert concept.primary_label == "Abnormality of the pericardium (HP:0001697)"
        assert concept.source_data[KnowledgeSource.ENRICHR]["term_id"] == "HP:0001697"

    @pytest.mark.asyncio
    async def test_member_list_truncated(self, adapter):
        genes = "\t".join(f"G{i}" for i in range(enrichr_adapter._MAX_MEMBERS + 10))
        with patch.object(adapter, "_get_text", text_router(library=f"BIG\t\t{genes}\n")):
            concept = await adapter.get_concept_details("KEGG_2026::BIG")
        data = concept.source_data[KnowledgeSource.ENRICHR]
        assert len(data["genes"]) == enrichr_adapter._MAX_MEMBERS and data["truncated"] is True
        assert data["n_genes"] == enrichr_adapter._MAX_MEMBERS + 10

    @pytest.mark.asyncio
    async def test_not_found_invalid_and_errors(self, adapter):
        with patch.object(adapter, "_get_text", text_router()):
            assert await adapter.get_concept_details("KEGG_2026::NO SUCH TERM") is None
        assert await adapter.get_concept_details("BRCA1") is None
        assert await adapter.get_concept_details("") is None
        with patch.object(adapter, "_get_text", text_router(library=RuntimeError("boom"))):
            assert await adapter.get_concept_details("Other_2026::MALARIA") is None

    @pytest.mark.asyncio
    async def test_library_cache_is_bounded(self, adapter):
        with patch.object(adapter, "_get_text", text_router()):
            for name in ("A_1", "B_2", "C_3", "D_4"):
                await adapter._library_terms(name)
        assert len(adapter._library_cache) == enrichr_adapter._MAX_CACHED_LIBRARIES
        assert "A_1" not in adapter._library_cache


class TestRelationships:
    @pytest.mark.asyncio
    async def test_gene_memberships_limited_to_configured_libraries(self, adapter):
        adapter.libraries = ("KEGG_2026", "Human_Phenotype_Ontology", "Reactome_2022")
        calls = []
        with patch.object(adapter, "_get_text", text_router(calls=calls)):
            edges = await adapter.get_relationships("brca1")
            again = await adapter.get_relationships("BRCA1")
        assert calls == [("genemap", {"gene": "BRCA1", "json": "true", "setup": "false"})]
        assert edges == again
        assert [e["related_id"] for e in edges] == [
            "KEGG_2026::UBIQUITIN MEDIATED PROTEOLYSIS",
            "KEGG_2026::PI3K-AKT SIGNALING PATHWAY",
            "KEGG_2026::HOMOLOGOUS RECOMBINATION",
            "Human_Phenotype_Ontology::Abnormality of the peritoneum (HP:0002585)",
            "Human_Phenotype_Ontology::Constipation (HP:0002019)",
        ]
        assert all(e["relation_label"] == "member_of" and e["source"] == "ENRICHR" for e in edges)
        assert edges[0]["library"] == "KEGG_2026" and edges[0]["terms_in_library"] == 3

    @pytest.mark.asyncio
    async def test_per_library_cap(self, adapter, monkeypatch):
        adapter.libraries = ("KEGG_2026",)
        monkeypatch.setattr(enrichr_adapter, "_MAX_TERMS_PER_LIBRARY", 2)
        with patch.object(adapter, "_get_text", text_router()):
            edges = await adapter.get_relationships("BRCA1")
        assert len(edges) == 2 and edges[0]["terms_in_library"] == 3

    @pytest.mark.asyncio
    async def test_unknown_gene_and_odd_answers(self, adapter):
        with patch.object(adapter, "_get_text", text_router(genemap=GENEMAP_EMPTY)):
            assert await adapter.get_relationships("NOTAGENE123") == []
        with patch.object(adapter, "_get_text", text_router(genemap=[1, 2])):
            assert await adapter.get_relationships("OTHER1") == []
        with patch.object(adapter, "_get_text", text_router(genemap={"gene": "x"})):
            assert await adapter.get_relationships("OTHER2") == []

    @pytest.mark.asyncio
    async def test_term_members(self, adapter, monkeypatch):
        with patch.object(adapter, "_get_text", text_router()):
            edges = await adapter.get_relationships("KEGG_2026::MALARIA")
            lowered = await adapter.get_relationships("KEGG_2026::malaria")
            assert await adapter.get_relationships("KEGG_2026::NO SUCH TERM") == []
        assert [e["related_id"] for e in edges] == ["ACKR1", "SOS1", "THBS3", "IL6", "TLR2"]
        assert edges[0]["relation_label"] == "has_member" and edges[0]["n_members"] == 5
        assert lowered == edges

    @pytest.mark.asyncio
    async def test_invalid_and_errors(self, adapter):
        assert await adapter.get_relationships("") == []
        assert await adapter.get_relationships("not a gene!") == []
        with patch.object(adapter, "_get_text", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.get_relationships("BRCA1") == []
            assert await adapter.get_relationships("KEGG_2026::MALARIA") == []
