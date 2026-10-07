"""Unit tests for MedGenAdapter (NCBI MedGen via E-utilities); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import medgen_adapter
from knowledge_lookup.adapters.medgen_adapter import MedGenAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.medgen_responses import (
    DOC_CFS,
    DOC_ERROR,
    DOC_FATIGUE,
    DOC_HBOC,
    DOC_MARFAN,
    DOC_WARFARIN,
    ESEARCH_CFS,
    ESEARCH_EMPTY,
)

pytestmark = pytest.mark.unit


def esummary(*docs):
    return {
        "header": {"type": "esummary", "version": "0.3"},
        "result": {"uids": [d["uid"] for d in docs], **{d["uid"]: copy.deepcopy(d) for d in docs}},
    }


@pytest.fixture(autouse=True)
def no_throttle_delay(monkeypatch):
    monkeypatch.setattr(medgen_adapter, "_MIN_INTERVAL_KEYLESS", 0.0)
    monkeypatch.setattr(medgen_adapter, "_MIN_INTERVAL_KEYED", 0.0)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return MedGenAdapter(lookup_config)


def router(summaries=None, esearch=None):
    """Fake ``_make_request`` answering esearch / esummary by URL."""
    summaries = summaries or {}

    async def fake(url, params=None, headers=None, json_data=None):
        if url.endswith("esearch.fcgi"):
            if isinstance(esearch, Exception):
                raise esearch
            if esearch is not None:
                return copy.deepcopy(esearch)
            # default: a CUI term finds the fixture concept carrying that CUI
            for uid, doc in summaries.items():
                if doc.get("conceptid") == params["term"]:
                    return {"esearchresult": {"idlist": [uid]}}
            return copy.deepcopy(ESEARCH_CFS)
        if url.endswith("esummary.fcgi"):
            ids = params["id"].split(",")
            docs = [summaries[i] for i in ids if i in summaries]
            return esummary(*docs) if docs else {"result": {"uids": []}}
        raise AssertionError(f"unexpected URL {url}")

    return fake


ALL = {"5130": DOC_CFS, "44287": DOC_MARFAN, "382914": DOC_HBOC, "41971": DOC_FATIGUE}


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.MEDGEN
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("C0015674", ("cui", "C0015674")),
            ("c0015674", ("cui", "C0015674")),
            ("UMLS:C0015674", ("cui", "C0015674")),
            ("MedGen:C0015674", ("cui", "C0015674")),
            ("CUI:C0015674", ("cui", "C0015674")),
            ("CN123456", ("cui", "CN123456")),
            ("5130", ("uid", "5130")),
            ("MedGen:5130", ("uid", "5130")),
            ("MEDGEN_5130", ("uid", "5130")),
            ("  5130 ", ("uid", "5130")),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert MedGenAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", "  ", "chronic fatigue", "HP:0012378", "C12", None])
    def test_invalid_ids(self, raw):
        assert MedGenAdapter._parse_id(raw) is None

    def test_concept_type_mapping(self):
        assert MedGenAdapter._concept_type("T047") == ConceptType.DISEASE
        assert MedGenAdapter._concept_type("T184") == ConceptType.SYMPTOM
        assert MedGenAdapter._concept_type("T033") == ConceptType.PHENOTYPE
        assert MedGenAdapter._concept_type("") == ConceptType.DISEASE


class TestRequests:
    @pytest.mark.asyncio
    async def test_keyless_request_params(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._eutils("esearch", {"term": "x"})
        url, params = req.call_args.args
        assert url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        assert params["db"] == "medgen" and params["retmode"] == "json"
        assert "api_key" not in params and "email" not in params

    @pytest.mark.asyncio
    async def test_api_key_and_email_from_environment(self, adapter, monkeypatch):
        monkeypatch.setenv("NCBI_API_KEY", "test-key")
        monkeypatch.setenv("NCBI_EMAIL", "dev@example.org")
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._eutils("esearch", {"term": "x"})
        params = req.call_args.args[1]
        assert params["api_key"] == "test-key" and params["email"] == "dev@example.org"

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(medgen_adapter, "_MIN_INTERVAL_KEYLESS", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(medgen_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._eutils("esearch", {})
            await adapter._eutils("esearch", {})
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_concepts_in_relevance_order(self, adapter):
        fake = router({"5130": DOC_CFS})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)) as req:
            results = await adapter.search_concepts("chronic fatigue syndrome", limit=5)
        search_params = req.call_args_list[0].args[1]
        assert search_params["sort"] == "relevance" and search_params["retmax"] == 5
        assert [c.primary_id for c in results] == ["C0015674"]
        cfs = results[0]
        assert cfs.primary_label == "Myalgic encephalomeyelitis/chronic fatigue syndrome"
        assert cfs.concept_type == ConceptType.DISEASE
        assert cfs.semantic_types == ["Disease or Syndrome"]
        assert any(i.identifier == "MedGen:5130" for i in cfs.identifiers)
        assert "Chronic Fatigue Syndromes" in cfs.synonyms
        # the preferred title is not repeated as a synonym
        assert cfs.primary_label not in cfs.synonyms
        # doubled SQL apostrophes of the raw definition are collapsed
        assert "six months' duration" in cfs.definitions[0]
        assert cfs.confidence_score > 0.5

    @pytest.mark.asyncio
    async def test_search_respects_limit_and_cap(self, adapter):
        esearch = {"esearchresult": {"idlist": ["5130", "44287", "382914"]}}
        fake = router(ALL, esearch=esearch)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)) as req:
            results = await adapter.search_concepts("syndrome", limit=2)
            await adapter.search_concepts("syndrome", limit=500)
        assert len(results) == 2
        assert req.call_args_list[0].args[1]["retmax"] == 2
        assert any(
            c.args[1].get("retmax") == medgen_adapter._MAX_SEARCH
            for c in req.call_args_list
            if c.args[0].endswith("esearch.fcgi")
        )

    @pytest.mark.asyncio
    async def test_search_by_cui_and_uid_uses_details(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            by_cui = await adapter.search_concepts("C0015674")
            by_uid = await adapter.search_concepts("5130")
        assert [c.primary_id for c in by_cui] == ["C0015674"]
        assert [c.primary_id for c in by_uid] == ["C0015674"]

    @pytest.mark.asyncio
    async def test_search_unknown_cui(self, adapter):
        fake = router(ALL, esearch=ESEARCH_EMPTY)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.search_concepts("C9999999") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("diabetes", 0), (None, 5)])
    async def test_search_empty_inputs(self, adapter, query, limit):
        assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_search_empty_and_malformed_responses(self, adapter):
        for esearch in (ESEARCH_EMPTY, {}, {"esearchresult": None}):
            fake = router(ALL, esearch=esearch)
            with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
                assert await adapter.search_concepts("nothing here") == []
        for summary in ([], {"result": None}, {"result": {"uids": ["1"], "1": DOC_ERROR}}):
            with patch.object(
                adapter,
                "_make_request",
                AsyncMock(side_effect=[ESEARCH_CFS, summary]),
            ):
                assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_search_skips_duplicates_and_unusable_documents(self, adapter):
        no_title = {"uid": "9", "conceptid": "C1"}
        summary = {
            "result": {
                "uids": ["5130", "5130", "9"],
                "5130": copy.deepcopy(DOC_CFS),
                "9": no_title,
            }
        }
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=[ESEARCH_CFS, summary])):
            results = await adapter.search_concepts("x")
        assert [c.primary_id for c in results] == ["C0015674"]

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await adapter.search_concepts("diabetes") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_for_cui_in_every_form(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            for raw in ("C0015674", "UMLS:C0015674", "MedGen:5130", "5130"):
                concept = await adapter.get_concept_details(raw)
                assert concept is not None and concept.primary_id == "C0015674", raw

    @pytest.mark.asyncio
    async def test_details_content_with_genes_and_vocabularies(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            marfan = await adapter.get_concept_details("44287")
        assert marfan.primary_id == "C0024796"
        data = marfan.source_data[KnowledgeSource.MEDGEN]
        assert data["uid"] == "44287" and data["semantic_type_id"] == "T047"
        assert data["associated_genes"] == [{"gene_id": "2200", "symbol": "FBN1"}]
        assert data["omim"] == ["154700"]
        assert {"MSH", "OMIM", "ORDO", "MONDO"} <= set(data["source_vocabularies"])
        assert data["definition_sources"] == ["GeneReviews"]
        assert marfan.parents == [] and marfan.children == []

    @pytest.mark.asyncio
    async def test_details_symptom_type(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            fatigue = await adapter.get_concept_details("C0015672")
        assert fatigue.concept_type == ConceptType.SYMPTOM

    @pytest.mark.asyncio
    async def test_details_cui_must_match_hit(self, adapter):
        # esearch finds a concept that merely mentions the CUI: it is not returned
        fake = router(ALL, esearch={"esearchresult": {"idlist": ["44287"]}})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.get_concept_details("C0015674") is None

    @pytest.mark.asyncio
    async def test_details_suppressed_marker(self, adapter):
        doc = copy.deepcopy(DOC_CFS)
        doc["suppressed"] = "1"
        fake = router({"5130": doc})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            concept = await adapter.get_concept_details("5130")
        assert "suppressed" in concept.categories

    @pytest.mark.asyncio
    async def test_details_malformed_meta_and_missing_fields(self, adapter):
        broken = copy.deepcopy(DOC_CFS)
        broken["conceptmeta"] = "<Names><Name>unclosed"
        fake = router({"5130": broken})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            concept = await adapter.get_concept_details("5130")
        assert concept is not None and concept.synonyms == []
        assert concept.definitions  # the top-level definition still survives
        assert MedGenAdapter._parse_meta({"conceptmeta": ""}) is None
        assert MedGenAdapter._parse_meta({}) is None
        assert adapter._doc_to_concept({"uid": "1"}) is None
        assert adapter._doc_to_concept({"title": "x"}) is None
        by_uid = adapter._doc_to_concept({"uid": "7", "title": "x"})
        assert by_uid.primary_id == "7"

    @pytest.mark.asyncio
    async def test_details_synonym_cap(self, adapter, monkeypatch):
        monkeypatch.setattr(medgen_adapter, "_MAX_SYNONYMS", 3)
        fake = router({"5130": DOC_CFS})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            concept = await adapter.get_concept_details("5130")
        assert len(concept.synonyms) == 3

    @pytest.mark.asyncio
    async def test_details_invalid_id_missing_and_error(self, adapter):
        assert await adapter.get_concept_details("") is None
        assert await adapter.get_concept_details("HP:0012378") is None
        fake = router({}, esearch=ESEARCH_EMPTY)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.get_concept_details("5130") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("5130") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_for_cfs(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            mappings = await adapter.get_mappings("C0015674")
        by_to = {m["toId"]: m for m in mappings}
        assert set(by_to) == {
            "MESH:D015673",
            "NCIT:C3037",
            "SNOMEDCT_US:52702003",
            "GTR:GTRT000046815",
            "MONDO:0005404",
            "Orphanet:1983",
        }
        assert by_to["MESH:D015673"] == {
            "fromId": "C0015674",
            "toId": "MESH:D015673",
            "fromSource": "MEDGEN",
            "toSource": "MESH",
            "mappingType": "xref",
            "confidence": 0.9,
            "label": "Fatigue Syndrome, Chronic",  # the MH (preferred) term wins
            "source_vocabulary": "MSH",
        }

    @pytest.mark.asyncio
    async def test_mappings_omim_hpo_and_genereviews(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            marfan = {m["toId"] for m in await adapter.get_mappings("44287")}
            hboc = {m["toId"] for m in await adapter.get_mappings("C2676676")}
            fatigue = {m["toId"] for m in await adapter.get_mappings("41971")}
        assert {"OMIM:154700", "Orphanet:558", "Orphanet:284963", "GeneReviews:NBK1335"} <= marfan
        assert {"OMIM:604370", "MONDO:0011450"} <= hboc
        # HPO ids carry their own prefix once; UMLS-internal OMIM pseudo ids are dropped
        assert "HP:0012378" in fatigue
        assert not any(t.startswith("OMIM:") for t in fatigue)

    @pytest.mark.asyncio
    async def test_mappings_omim_list_fallback_and_unknown_vocabulary(self, adapter):
        doc = {
            "uid": "1",
            "conceptid": "C1111111",
            "title": "x",
            "conceptmeta": (
                '<Names><Name SAB="ICD10CM" CODE="G93.32" TTY="PT">ME</Name>'
                '<Name SAB="MSH" TTY="PT">no id</Name></Names>'
                "<OMIM><MIM>123456</MIM><MIM>bad</MIM></OMIM>"
            ),
        }
        fake = router({"1": doc})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            targets = {m["toId"] for m in await adapter.get_mappings("1")}
        assert targets == {"ICD10CM:G93.32", "OMIM:123456"}

    @pytest.mark.asyncio
    async def test_mappings_failures(self, adapter):
        assert await adapter.get_mappings("") == []
        fake = router({}, esearch=ESEARCH_EMPTY)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.get_mappings("C0015674") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("C0015674") == []
        broken = copy.deepcopy(DOC_CFS)
        broken["conceptmeta"] = "<oops"
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router({"5130": broken}))
        ):
            assert await adapter.get_mappings("5130") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_relationships_marfan(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("C0024796", limit=100)
        by_label: dict[str, list[dict]] = {}
        for rel in rels:
            by_label.setdefault(rel["relation_label"], []).append(rel)
        gene = by_label["has_associated_gene"][0]
        assert gene["related_id"] == "NCBIGene:2200" and gene["related_name"] == "FBN1"
        assert gene["chromosome"] == "15" and gene["cytogenetic_location"] == "15q21.1"
        feature = by_label["has_clinical_feature"][0]
        assert feature["related_id"].startswith("HP:") and feature["cui"].startswith("C")
        assert feature["semantic_type"] and feature["medgen_uid"]
        assert by_label["has_mode_of_inheritance"][0]["related_name"] == (
            "Autosomal dominant inheritance"
        )
        assert all(r["source"] == "MEDGEN" for r in rels)
        labels = [r["relation_label"] for r in rels]
        assert labels.index("has_associated_gene") < labels.index("has_clinical_feature")

    @pytest.mark.asyncio
    async def test_relationships_pharmacologic_response_and_limit(self, adapter):
        fake = router({"148193": DOC_WARFARIN})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("148193")
            capped = await adapter.get_relationships("148193", limit=1)
        drug = next(r for r in rels if r["relation_label"] == "has_pharmacologic_response")
        assert drug["related_name"] == "Warfarin" and drug["related_id"] == "C0043031"
        assert len(capped) == 1

    @pytest.mark.asyncio
    async def test_relationships_related_disorders_and_dedup(self, adapter):
        doc = {
            "uid": "2",
            "conceptid": "C2222222",
            "title": "x",
            "conceptmeta": (
                '<AssociatedGenes><Gene gene_id="1">A</Gene><Gene gene_id="1">A</Gene>'
                "<Gene>nogene</Gene></AssociatedGenes>"
                '<RelatedDisorders><RelatedDisorder uid="9" CUI="C0005859">'
                "<Name>Bloom syndrome</Name><SemanticType>Disease or Syndrome</SemanticType>"
                "</RelatedDisorder></RelatedDisorders>"
            ),
        }
        fake = router({"2": doc})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("2")
        assert [(r["relation_label"], r["related_id"]) for r in rels] == [
            ("has_associated_gene", "NCBIGene:1"),
            ("related_disorder", "C0005859"),
        ]

    @pytest.mark.asyncio
    async def test_relationships_none_for_cfs_and_edge_cases(self, adapter):
        fake = router(ALL)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.get_relationships("C0015674") == []
        assert await adapter.get_relationships("not an id") == []
        assert await adapter.get_relationships("C0015674", limit=0) == []
        fake = router({}, esearch=ESEARCH_EMPTY)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.get_relationships("C0015674") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("C0015674") == []
