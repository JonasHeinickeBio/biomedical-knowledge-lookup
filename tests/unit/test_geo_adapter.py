"""Unit tests for GEOAdapter (GEO via NCBI E-utilities, db=gds); no network."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import geo_adapter
from knowledge_lookup.adapters.geo_adapter import GEOAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.geo_responses import (
    ELINK_TAXONOMY,
    ESEARCH_CFS,
    ESEARCH_EMPTY,
    ESUMMARY_ERROR,
    GDS_5435,
    GPL_EPIC,
    GSE_HAMSTER,
    GSE_LONGCOVID,
    GSE_ME,
    GSM_1,
)

pytestmark = pytest.mark.unit

ALL = {d["uid"]: d for d in (GSE_ME, GSE_LONGCOVID, GPL_EPIC, GSM_1, GDS_5435, GSE_HAMSTER)}
TAXA = {"Homo sapiens": "9606", "Mus musculus": "10090", "Mesocricetus auratus": "10036"}


def esummary(*docs):
    return {
        "header": {"type": "esummary", "version": "0.3"},
        "result": {"uids": [d["uid"] for d in docs], **{d["uid"]: copy.deepcopy(d) for d in docs}},
    }


@pytest.fixture(autouse=True)
def no_throttle_delay(monkeypatch):
    monkeypatch.setattr(geo_adapter, "_MIN_INTERVAL_KEYLESS", 0.0)
    monkeypatch.setattr(geo_adapter, "_MIN_INTERVAL_KEYED", 0.0)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)


@pytest.fixture
def adapter(lookup_config):
    return GEOAdapter(lookup_config)


def router(docs=None, esearch=None, elink=None):
    """Fake ``_make_request`` answering esearch / esummary / elink by URL and ``db``."""
    docs = ALL if docs is None else docs

    async def fake(url, params=None, headers=None, json_data=None):
        if url.endswith("esearch.fcgi"):
            if isinstance(esearch, Exception):
                raise esearch
            return copy.deepcopy(esearch if esearch is not None else ESEARCH_CFS)
        if url.endswith("elink.fcgi"):
            if isinstance(elink, Exception):
                raise elink
            if elink is not None:
                return copy.deepcopy(elink)
            doc = docs.get(params["id"])
            names = [t.strip() for t in (doc or {}).get("taxon", "").split(";") if t.strip()]
            links = [TAXA[n] for n in names if n in TAXA]
            return {
                "linksets": [
                    {
                        "dbfrom": "gds",
                        "ids": [params["id"]],
                        "linksetdbs": [{"dbto": "taxonomy", "links": links}] if links else [],
                    }
                ]
            }
        if url.endswith("esummary.fcgi"):
            if params["db"] == "taxonomy":
                by_id = {v: k for k, v in TAXA.items()}
                ids = params["id"].split(",")
                return {
                    "result": {
                        "uids": ids,
                        **{i: {"uid": i, "scientificname": by_id.get(i, "")} for i in ids},
                    }
                }
            found = [docs[i] for i in params["id"].split(",") if i in docs]
            return esummary(*found) if found else {"result": {"uids": []}}
        raise AssertionError(f"unexpected URL {url}")

    return fake


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.GEO
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("GSE327255", ("GSE", "GSE327255", "200327255")),
            ("gse327255", ("GSE", "GSE327255", "200327255")),
            ("GEO:GSE1", ("GSE", "GSE1", "200000001")),
            (" geo_gse0000012 ", ("GSE", "GSE12", "200000012")),
            ("GPL21145", ("GPL", "GPL21145", "100021145")),
            ("GSM9652321", ("GSM", "GSM9652321", "309652321")),
            ("GDS5435", ("GDS", "GDS5435", "5435")),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert GEOAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["", "  ", "GSE", "GSE0", "GSEabc", "PRJNA1", "12345", "SRP424803", None]
    )
    def test_invalid_ids(self, raw):
        assert GEOAdapter._parse_id(raw) is None

    def test_build_term_default_restricts_to_series_and_datasets(self):
        term = GEOAdapter.build_term("long covid OR me/cfs")
        assert term == "(long covid OR me/cfs) AND (gse[ETYP] OR gds[ETYP])"

    def test_build_term_respects_user_entry_type(self):
        assert GEOAdapter.build_term("fatigue AND gsm[ETYP]") == "fatigue AND gsm[ETYP]"
        assert (
            GEOAdapter.build_term("fatigue AND gpl[Entry Type]") == "fatigue AND gpl[Entry Type]"
        )

    @pytest.mark.parametrize(
        "entry_type,expected",
        [
            ("series", "(x) AND gse[ETYP]"),
            ("GSE", "(x) AND gse[ETYP]"),
            ("dataset", "(x) AND gds[ETYP]"),
            ("platform", "(x) AND gpl[ETYP]"),
            ("samples", "(x) AND gsm[ETYP]"),
            ("any", "x"),
            ("bogus", None),
        ],
    )
    def test_build_term_entry_type_filter(self, entry_type, expected):
        assert GEOAdapter.build_term("x", entry_type) == expected

    def test_build_term_truncates_long_queries(self):
        term = GEOAdapter.build_term("a" * 2000, "any")
        assert term is not None and len(term) == geo_adapter._MAX_QUERY_LENGTH


class TestRequests:
    @pytest.mark.asyncio
    async def test_keyless_request_params(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._eutils("esearch", {"term": "x"})
        url, params = req.call_args.args
        assert url.endswith("/esearch.fcgi")
        assert params == {"retmode": "json", "tool": "knowledge-lookup", "db": "gds", "term": "x"}

    @pytest.mark.asyncio
    async def test_elink_uses_dbfrom(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._eutils("elink", {"id": "1", "db": "taxonomy"})
        params = req.call_args.args[1]
        assert params["dbfrom"] == "gds" and params["db"] == "taxonomy"

    @pytest.mark.asyncio
    async def test_api_key_and_email_from_environment(self, adapter, monkeypatch):
        monkeypatch.setenv("NCBI_API_KEY", "test-key")
        monkeypatch.setenv("NCBI_EMAIL", "dev@example.org")
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})) as req:
            await adapter._eutils("esummary", {"id": "1"})
        params = req.call_args.args[1]
        assert params["api_key"] == "test-key" and params["email"] == "dev@example.org"

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(geo_adapter, "_MIN_INTERVAL_KEYLESS", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(geo_adapter.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(geo_adapter.time, "monotonic", lambda: 100.0)  # frozen clock
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._eutils("esearch", {})
            await adapter._eutils("esearch", {})
        assert sleeps == [pytest.approx(0.05)]

    @pytest.mark.asyncio
    async def test_keyed_interval_is_shorter(self, adapter, monkeypatch):
        monkeypatch.setattr(geo_adapter, "_MIN_INTERVAL_KEYLESS", 0.3)
        monkeypatch.setattr(geo_adapter, "_MIN_INTERVAL_KEYED", 0.01)
        monkeypatch.setenv("NCBI_API_KEY", "k")
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(geo_adapter.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(geo_adapter.time, "monotonic", lambda: 100.0)  # frozen clock
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._eutils("esearch", {})
            await adapter._eutils("esearch", {})
        assert sleeps == [pytest.approx(0.01)]

    def test_config_key_wins_over_environment(self, monkeypatch):
        monkeypatch.setenv("NCBI_API_KEY", "env-key")
        configured = GEOAdapter(LookupConfig(api_keys={"ncbi": "cfg-key"}))
        assert configured._api_key() == "cfg-key"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_series_concepts(self, adapter):
        fake = router()
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)) as req:
            results = await adapter.search_concepts("chronic fatigue syndrome", limit=5)
        search = req.call_args_list[0].args[1]
        assert search["term"] == "(chronic fatigue syndrome) AND (gse[ETYP] OR gds[ETYP])"
        assert search["retmax"] == 5 and "sort" not in search
        # only the fixture series resolve; unknown UIDs are skipped
        assert [c.primary_id for c in results] == ["GSE327255"]
        series = results[0]
        assert series.concept_type == ConceptType.STUDY
        assert series.primary_label.startswith("PTPRN2 hypomethylation")
        assert series.confidence_score == pytest.approx(0.9)
        assert series.semantic_types == [
            "GEO Series",
            "Methylation profiling by genome tiling array",
        ]
        assert series.categories == ["Homo sapiens"]

    @pytest.mark.asyncio
    async def test_search_preserves_order_and_limit(self, adapter):
        esearch = {"esearchresult": {"idlist": ["200327255", "200226260", "200292461"]}}
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(esearch=esearch))
        ):
            results = await adapter.search_concepts("long covid", limit=2)
        assert [c.primary_id for c in results] == ["GSE327255", "GSE226260"]
        assert results[0].confidence_score > results[1].confidence_score

    @pytest.mark.asyncio
    async def test_search_caps_page_size(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            await adapter.search_concepts("fatigue", limit=500)
        assert req.call_args_list[0].args[1]["retmax"] == geo_adapter._MAX_SEARCH

    @pytest.mark.asyncio
    async def test_search_entry_type_filter(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            await adapter.search_concepts("illumina", limit=3, entry_type="platform")
        assert req.call_args_list[0].args[1]["term"] == "(illumina) AND gpl[ETYP]"

    @pytest.mark.asyncio
    async def test_search_unknown_entry_type_returns_empty_without_request(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts("x", entry_type="bogus") == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_by_accession_uses_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())) as req:
            results = await adapter.search_concepts("gse226260")
        assert [c.primary_id for c in results] == ["GSE226260"]
        assert all(call.args[0].endswith("esummary.fcgi") for call in req.call_args_list)

    @pytest.mark.asyncio
    async def test_search_unknown_accession(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.search_concepts("GSE999999999") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), (None, 5), ("x", 0), ("x", -1)])
    async def test_search_empty_inputs(self, adapter, query, limit):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts(query, limit=limit) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_empty_and_malformed_responses(self, adapter):
        for esearch in (ESEARCH_EMPTY, {}, {"esearchresult": None}, []):
            with patch.object(
                adapter, "_make_request", AsyncMock(side_effect=router(esearch=esearch))
            ):
                assert await adapter.search_concepts("zzzz") == []
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"result": "boom"})):
            assert await adapter._summaries(["1"]) == []

    @pytest.mark.asyncio
    async def test_search_skips_duplicates_error_documents_and_other_entries(self, adapter):
        docs = dict(ALL)
        docs["999999999"] = ESUMMARY_ERROR["result"]["999999999"]
        docs["777"] = {"uid": "777", "accession": "XYZ1", "title": "odd", "entrytype": "XYZ"}
        esearch = {"esearchresult": {"idlist": ["200327255", "200327255", "999999999", "777"]}}
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(docs, esearch=esearch))
        ):
            results = await adapter.search_concepts("x", limit=10)
        assert [c.primary_id for c in results] == ["GSE327255"]

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        fake = router(esearch=RuntimeError("boom"))
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_series_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            concept = await adapter.get_concept_details("GSE226260")
        assert concept is not None
        assert concept.primary_id == "GSE226260"
        assert concept.confidence_score == pytest.approx(0.95)
        assert concept.identifiers[0].url.endswith("acc.cgi?acc=GSE226260")
        data = concept.source_data[KnowledgeSource.GEO]
        assert data["platforms"] == ["GPL34284", "GPL24676"]
        assert data["n_samples"] == 331
        assert data["bioproject"] == "PRJNA939253"
        assert data["sra_studies"] == ["SRP424803"]
        assert data["pubmed_ids"] == ["41388153"]
        assert data["supplementary_file_types"] == ["CSV"]
        assert data["ftp_url"].startswith("ftp://ftp.ncbi.nlm.nih.gov/geo/series/")
        assert data["geo2r_available"] is False

    @pytest.mark.asyncio
    async def test_details_accept_every_id_form(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            ids = [
                (await adapter.get_concept_details(raw)).primary_id
                for raw in ("GSE327255", "gse327255", "GEO:GSE327255")
            ]
        assert ids == ["GSE327255"] * 3

    @pytest.mark.asyncio
    async def test_dataset_platform_and_sample_types(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            gds = await adapter.get_concept_details("GDS5435")
            gpl = await adapter.get_concept_details("GPL21145")
            gsm = await adapter.get_concept_details("GSM1")
        assert gds.concept_type == ConceptType.STUDY
        assert gds.source_data[KnowledgeSource.GEO]["series"] == ["GSE54723"]
        assert gds.source_data[KnowledgeSource.GEO]["series_title"].startswith("Nutritional")
        assert gpl.concept_type == ConceptType.ASSAY
        assert gpl.source_data[KnowledgeSource.GEO]["platforms"] == []
        assert (
            gpl.source_data[KnowledgeSource.GEO]["platform_technology"] == "oligonucleotide beads"
        )
        assert gsm.concept_type == ConceptType.OBSERVATION
        assert gsm.primary_label == "Foreskin Fibroblasts"
        assert gsm.source_data[KnowledgeSource.GEO]["series"] == ["GSE506"]

    @pytest.mark.asyncio
    async def test_details_long_summary_is_capped(self, adapter):
        doc = copy.deepcopy(GSE_ME)
        doc["summary"] = "x" * 20000
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router({"200327255": doc}))
        ):
            concept = await adapter.get_concept_details("GSE327255")
        assert len(concept.definitions[0]) == geo_adapter._MAX_SUMMARY_LENGTH

    @pytest.mark.asyncio
    async def test_details_sparse_document(self, adapter):
        doc = {"uid": "200000009", "accession": "GSE9", "n_samples": "", "samples": None}
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router({"200000009": doc}))
        ):
            concept = await adapter.get_concept_details("GSE9")
        assert concept.primary_label == "GSE9"
        data = concept.source_data[KnowledgeSource.GEO]
        assert data["n_samples"] is None and data["platforms"] == [] and data["ftp_url"] is None
        assert data["geo2r_available"] is None

    @pytest.mark.asyncio
    async def test_details_invalid_missing_and_error(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.get_concept_details("nonsense") is None
            assert await adapter.get_concept_details("GSE123456789") is None
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_concept_details("GSE1") is None

    @pytest.mark.asyncio
    async def test_error_document_is_dropped(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=ESUMMARY_ERROR)):
            assert await adapter._summaries(["999999999"]) == []
            assert await adapter._summaries([]) == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_series_relationships(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            rels = await adapter.get_relationships("GSE327255")
        by_label = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)
        assert set(by_label) == {"uses_platform", "has_sample", "has_publication", "has_organism"}
        assert by_label["uses_platform"][0]["related_id"] == "GPL21145"
        assert by_label["uses_platform"][0]["related_name"] == "Infinium MethylationEPIC"
        assert [r["related_id"] for r in by_label["has_sample"]] == [
            "GSM9652301",
            "GSM9652318",
            "GSM9652321",
        ]  # sorted numerically
        assert by_label["has_sample"][0]["total_samples"] == 75
        assert by_label["has_publication"][0]["related_id"] == "PMID:42010606"
        assert by_label["has_organism"][0]["related_id"] == "NCBITaxon:9606"
        assert by_label["has_organism"][0]["related_name"] == "Homo sapiens"
        assert all(r["source"] == "GEO" for r in rels)

    @pytest.mark.asyncio
    async def test_sample_cap_applies_to_has_sample_only(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            rels = await adapter.get_relationships("GSE327255", limit=2)
        labels = [r["relation_label"] for r in rels]
        assert labels.count("has_sample") == 2
        assert "uses_platform" in labels and "has_publication" in labels

    @pytest.mark.asyncio
    async def test_multi_platform_series(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            rels = await adapter.get_relationships("GSE226260")
        assert [r["related_id"] for r in rels if r["relation_label"] == "uses_platform"] == [
            "GPL34284",
            "GPL24676",
        ]  # platform titles unknown in this fixture set -> empty names
        assert all(r["related_name"] == "" for r in rels if r["relation_label"] == "uses_platform")

    @pytest.mark.asyncio
    async def test_dataset_sample_and_platform_relationships(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            gds = await adapter.get_relationships("GDS5435")
            gsm = await adapter.get_relationships("GSM1")
            gpl = await adapter.get_relationships("GPL21145", limit=3)
        derived = [r for r in gds if r["relation_label"] == "derived_from_series"]
        assert derived[0]["related_id"] == "GSE54723"
        assert derived[0]["related_name"].startswith("Nutritional")
        assert gds[-1]["related_id"] == "NCBITaxon:10090"
        assert [r["relation_label"] for r in gsm][0] == "part_of_series"
        assert gsm[0]["related_id"] == "GSE506"
        used = [r["related_id"] for r in gpl if r["relation_label"] == "used_by_series"]
        assert used == ["GSE280206", "GSE328029", "GSE290136"]
        assert not any(r["relation_label"] == "uses_platform" for r in gpl)

    @pytest.mark.asyncio
    async def test_relationships_no_taxonomy_and_dedup(self, adapter):
        doc = copy.deepcopy(GSE_ME)
        doc["pubmedids"] = ["1", "1", "2"]
        doc["gpl"] = "21145;21145"
        elink = {"linksets": [{"ids": ["200327255"], "linksetdbs": []}]}
        fake = router({"200327255": doc, "100021145": GPL_EPIC}, elink=elink)
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("GSE327255")
        pubs = [r["related_id"] for r in rels if r["relation_label"] == "has_publication"]
        assert pubs == ["PMID:1", "PMID:2"]
        assert len([r for r in rels if r["relation_label"] == "uses_platform"]) == 1
        assert not any(r["relation_label"] == "has_organism" for r in rels)

    @pytest.mark.asyncio
    async def test_relationships_failures(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.get_relationships("nonsense") == []
            assert await adapter.get_relationships("GSE327255", limit=0) == []
            assert await adapter.get_relationships("GSE999999999") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("GSE1") == []

    @pytest.mark.asyncio
    async def test_platform_title_failure_keeps_relationships(self, adapter):
        base = router()

        async def fake(url, params=None, headers=None, json_data=None):
            if url.endswith("esummary.fcgi") and params["id"] == "100021145":
                raise RuntimeError("platform lookup down")
            return await base(url, params, headers, json_data)

        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            rels = await adapter.get_relationships("GSE327255")
        platform = next(r for r in rels if r["relation_label"] == "uses_platform")
        assert platform["related_id"] == "GPL21145" and platform["related_name"] == ""

    @pytest.mark.asyncio
    async def test_taxa_ids_only_skips_name_lookup(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(elink=ELINK_TAXONOMY))
        ) as req:
            taxa = await adapter._taxa("200226260", names=False)
        assert taxa == [("9606", "")]
        assert req.call_count == 1 and req.call_args.args[0].endswith("elink.fcgi")

    @pytest.mark.asyncio
    async def test_taxa_resolution_for_multiple_organisms(self, adapter):
        elink = {
            "linksets": [
                {"ids": ["1"], "linksetdbs": [{"dbto": "taxonomy", "links": [9606, 10090, 9606]}]}
            ]
        }
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router(elink=elink))):
            taxa = await adapter._taxa("1")
        assert taxa == [("9606", "Homo sapiens"), ("10090", "Mus musculus")]


class TestMappings:
    @pytest.mark.asyncio
    async def test_mappings_with_sra_and_bioproject(self, adapter):
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router(elink=ELINK_TAXONOMY))
        ):
            mappings = await adapter.get_mappings("GSE226260")
        by_target = {m["toId"]: m for m in mappings}
        assert set(by_target) == {
            "PMID:41388153",
            "NCBITaxon:9606",
            "BioProject:PRJNA939253",
            "SRA:SRP424803",
        }
        for m in mappings:
            assert set(m) >= {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == "GSE226260" and m["fromSource"] == "GEO"
        assert by_target["PMID:41388153"]["toSource"] == "PUBMED"
        assert by_target["NCBITaxon:9606"]["toSource"] == "NCBITAXON"
        assert by_target["SRA:SRP424803"]["toSource"] == "SRA"
        assert by_target["BioProject:PRJNA939253"]["toSource"] == "BIOPROJECT"

    @pytest.mark.asyncio
    async def test_mappings_without_optional_ids(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            mappings = await adapter.get_mappings("GSM1")
        assert [m["toId"] for m in mappings] == ["NCBITaxon:9606"]

    @pytest.mark.asyncio
    async def test_mappings_ignore_non_sra_external_relations(self, adapter):
        doc = copy.deepcopy(GSE_LONGCOVID)
        doc["extrelations"] = [
            {"relationtype": "BioSample", "targetobject": "SAMN1"},
            {"relationtype": "SRA", "targetobject": ""},
            "junk",
        ]
        doc["pubmedids"] = []
        doc["bioproject"] = ""
        with patch.object(
            adapter, "_make_request", AsyncMock(side_effect=router({"200226260": doc}))
        ):
            mappings = await adapter.get_mappings("GSE226260")
        assert [m["toId"] for m in mappings] == ["NCBITaxon:9606"]

    @pytest.mark.asyncio
    async def test_mappings_failures(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=router())):
            assert await adapter.get_mappings("nonsense") == []
            assert await adapter.get_mappings("GSE999999999") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("GSE1") == []
