"""Unit tests for CellxGeneAdapter (CZ CELLxGENE Discover API); no network."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import cellxgene_adapter
from knowledge_lookup.adapters.cellxgene_adapter import CellxGeneAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.cellxgene_responses import (
    COLLECTIONS_INDEX,
    CURATION_COLLECTION,
    CURATION_DATASET,
    DATASETS_INDEX,
    WMG_DIMENSIONS,
    WMG_MARKERS,
)

pytestmark = pytest.mark.unit

LC_COLLECTION = "35d0b748-3eed-43a5-a1c4-1dade5ec5ca0"  # severe COVID-19 / long COVID nasopharynx
LC_DATASET = "13b61a7d-5605-4948-ba48-02c588960143"  # stable dataset id (from explorer_url)
LC_VERSION = "6a6db93e-901f-4054-90e0-14af5207978a"  # id used by the portal index
NK_COLLECTION = "6c147b03-08e4-4bb7-afb7-2bcc0a814b65"
NK_DATASET = "f2b69d9b-9f75-4a76-8c50-e44774680a7d"
MOUSE_DATASET = "b09f9b6a-7c4b-4345-9298-153bdc41191a"


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(cellxgene_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return CellxGeneAdapter(lookup_config)


def router(
    datasets=DATASETS_INDEX,
    collections=COLLECTIONS_INDEX,
    curation_collection=CURATION_COLLECTION,
    curation_dataset=CURATION_DATASET,
    wmg=WMG_DIMENSIONS,
    markers=WMG_MARKERS,
):
    """Fake ``_make_request`` answering by path; ``markers`` may be a dict per tissue id."""

    async def fake(url, params=None, headers=None, json_data=None):
        path = url.removeprefix(cellxgene_adapter.CELLXGENE_BASE_URL + "/")
        if path == "dp/v1/datasets/index":
            return copy.deepcopy(datasets)
        if path == "dp/v1/collections/index":
            return copy.deepcopy(collections)
        if path == f"curation/v1/collections/{LC_COLLECTION}":
            if isinstance(curation_collection, Exception):
                raise curation_collection
            return copy.deepcopy(curation_collection)
        if path == f"curation/v1/collections/{LC_COLLECTION}/datasets/{LC_DATASET}":
            if isinstance(curation_dataset, Exception):
                raise curation_dataset
            return copy.deepcopy(curation_dataset)
        if path == "wmg/v2/primary_filter_dimensions":
            if isinstance(wmg, Exception):
                raise wmg
            return copy.deepcopy(wmg)
        if path == "wmg/v2/markers":
            if isinstance(markers, Exception):
                raise markers
            if isinstance(markers, dict) and "marker_genes" not in markers:
                return copy.deepcopy(markers.get(json_data["tissue"], {"marker_genes": []}))
            return copy.deepcopy(markers)
        raise AssertionError(f"unexpected URL {url}")

    return fake


def patched(adapter, **kwargs):
    return patch.object(adapter, "_make_request", AsyncMock(side_effect=router(**kwargs)))


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CELLXGENE
        assert adapter.is_available() is True

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (LC_DATASET, ("uuid", LC_DATASET)),
            (LC_DATASET.upper(), ("uuid", LC_DATASET)),
            (f"collection:{LC_COLLECTION}", ("uuid", LC_COLLECTION)),
            (f"cellxgene:{LC_DATASET}", ("uuid", LC_DATASET)),
            ("CL:0000623", ("term", "CL:0000623")),
            ("cl_0000623", ("term", "CL:0000623")),
            ("uberon:0000178", ("term", "UBERON:0000178")),
            ("MONDO:0100233", ("term", "MONDO:0100233")),
            ("ncbitaxon:9606", ("term", "NCBITaxon:9606")),
        ],
    )
    def test_id_parsing(self, raw, expected):
        assert CellxGeneAdapter._parse_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", "natural killer cell", "12345", "CL:abc", None])
    def test_unsupported_ids(self, raw):
        assert CellxGeneAdapter._parse_id(raw) is None

    def test_ontology_pairs(self):
        items = [
            {"label": "a", "ontology_term_id": "X:1"},
            {"label": "dup", "ontology_term_id": "X:1"},
            {"label": "b || c", "ontology_term_id": "X:2 || X:3"},
            {"label": "only", "ontology_term_id": "X:4 || X:5"},  # label count mismatch
            {"ontology_term_id": "X:6"},
            {"label": "no id"},
            "junk",
        ]
        assert cellxgene_adapter._ontology_pairs(items) == [
            ("X:1", "a"),
            ("X:2", "b"),
            ("X:3", "c"),
            ("X:4", "X:4"),
            ("X:5", "X:5"),
            ("X:6", "X:6"),
        ]
        assert cellxgene_adapter._ontology_pairs(None) == []
        assert cellxgene_adapter._term_id("not a term") == "not a term"


class TestIndex:
    @pytest.mark.asyncio
    async def test_index_is_cached_and_refreshed(self, adapter, monkeypatch):
        clock = {"now": 100.0}
        monkeypatch.setattr(
            cellxgene_adapter, "time", SimpleNamespace(monotonic=lambda: clock["now"])
        )
        with patched(adapter) as req:
            await adapter.search_concepts("covid")
            await adapter.get_concept_details("CL:0000623")
            assert req.call_count == 2  # datasets + collections index, once
            clock["now"] += cellxgene_adapter._INDEX_TTL + 1
            await adapter.search_concepts("covid")
            assert req.call_count == 4

    @pytest.mark.asyncio
    async def test_index_built_from_portal_records(self, adapter):
        with patched(adapter):
            index = await adapter._load_index()
        assert set(index.datasets) == {LC_DATASET, NK_DATASET, MOUSE_DATASET}
        assert index.versions[LC_VERSION] == LC_DATASET
        assert index.datasets[LC_DATASET]["version_id"] == LC_VERSION
        # composite "A || B" disease annotations are split into separate terms
        assert "MONDO:0007915" in index.terms and index.terms["MONDO:0007915"].kind == "disease"
        assert not any("||" in t for t in index.terms)
        assert index.terms["CL:0000623"].kind == "cell_type"
        assert index.by_collection[LC_COLLECTION] == [LC_DATASET]

    @pytest.mark.asyncio
    async def test_tombstoned_and_malformed_records_are_skipped(self, adapter):
        records = copy.deepcopy(DATASETS_INDEX)
        records[0]["tombstone"] = True
        records.append("junk")
        records.append({"collection_id": "x"})
        with patched(adapter, datasets=records):
            index = await adapter._load_index()
        assert LC_DATASET not in index.datasets and len(index.datasets) == 2

    @pytest.mark.asyncio
    async def test_dataset_without_explorer_url_uses_index_id(self, adapter):
        records = copy.deepcopy(DATASETS_INDEX)
        records[0]["explorer_url"] = None
        with patched(adapter, datasets=records):
            index = await adapter._load_index()
        assert LC_VERSION in index.datasets

    @pytest.mark.asyncio
    async def test_unexpected_index_shape_degrades(self, adapter):
        with patched(adapter, datasets={"error": "nope"}):
            assert await adapter.search_concepts("covid") == []
            assert await adapter.get_concept_details("CL:0000623") is None
            assert await adapter.get_mappings("CL:0000623") == []
            assert await adapter.get_relationships("CL:0000623") == []

    @pytest.mark.asyncio
    async def test_throttle_spaces_requests(self, adapter, monkeypatch):
        monkeypatch.setattr(cellxgene_adapter, "_MIN_INTERVAL", 0.05)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(cellxgene_adapter.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={})):
            await adapter._request("a")
            await adapter._request("b", json_data={"x": 1})
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6


class TestSearch:
    @pytest.mark.asyncio
    async def test_long_covid_finds_disease_collection_and_dataset(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("long covid", limit=10)
        by_id = {c.primary_id: c for c in results}
        assert by_id["MONDO:0100233"].concept_type == ConceptType.DISEASE
        assert by_id["MONDO:0100233"].confidence_score == 0.85
        # collection and dataset are found through their "long COVID-19" disease annotation
        assert by_id[LC_COLLECTION].concept_type == ConceptType.REFERENCE
        assert by_id[LC_COLLECTION].confidence_score == 0.65
        assert by_id[LC_DATASET].concept_type == ConceptType.ASSAY
        assert results[0].primary_id == "MONDO:0100233"  # best score first
        assert NK_DATASET not in by_id

    @pytest.mark.asyncio
    async def test_exact_label_and_name_scores(self, adapter):
        with patched(adapter):
            exact = (await adapter.search_concepts("natural killer cell", limit=3))[0]
            by_name = await adapter.search_concepts("SARS-CoV-2", limit=5)
        assert exact.primary_id == "CL:0000623" and exact.confidence_score == 0.95
        assert exact.concept_type == ConceptType.CELL_TYPE
        assert by_name[0].primary_id == LC_COLLECTION and by_name[0].confidence_score == 0.8

    @pytest.mark.asyncio
    async def test_words_match_whole_words_only(self, adapter):
        longitudinal = {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Longitudinal profiling of immune cells in COVID-19",
            "publisher_metadata": {},
        }
        with patched(adapter, collections=[*COLLECTIONS_INDEX, longitudinal]):
            long_covid = await adapter.search_concepts("long covid", limit=20)
            exact = await adapter.search_concepts("longitudinal", limit=20)
            plural = await adapter.search_concepts("immune cell", limit=20)
        assert longitudinal["id"] not in {c.primary_id for c in long_covid}
        assert [c.primary_id for c in exact] == [longitudinal["id"]]
        assert longitudinal["id"] in {c.primary_id for c in plural}  # "cell" matches "cells"

    @pytest.mark.asyncio
    async def test_dataset_name_match(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("t cells", limit=10)
        assert NK_DATASET in {c.primary_id for c in results}

    @pytest.mark.asyncio
    async def test_buckets_are_interleaved_under_a_small_limit(self, adapter):
        with patched(adapter):
            results = await adapter.search_concepts("covid", limit=3)
        kinds = {str(c.concept_type) for c in results}
        assert len(results) == 3 and len(kinds) == 3  # term + collection + dataset

    @pytest.mark.asyncio
    async def test_tissue_and_id_queries(self, adapter):
        with patched(adapter):
            tissue = (await adapter.search_concepts("blood", limit=1))[0]
            by_id = await adapter.search_concepts("CL:0000623", limit=3)
        assert tissue.primary_id == "UBERON:0000178" and tissue.concept_type == "TISSUE"
        assert by_id[0].primary_id == "CL:0000623"

    @pytest.mark.asyncio
    async def test_empty_and_limits(self, adapter):
        with patched(adapter):
            assert await adapter.search_concepts("") == []
            assert await adapter.search_concepts("  ") == []
            assert await adapter.search_concepts("covid", limit=0) == []
            assert await adapter.search_concepts("chronic fatigue syndrome") == []
            assert len(await adapter.search_concepts("cell", limit=2)) == 2


class TestDetails:
    @pytest.mark.asyncio
    async def test_collection_details_merge_curation_api(self, adapter):
        with patched(adapter) as req:
            concept = await adapter.get_concept_details(LC_COLLECTION)
        assert concept.primary_id == LC_COLLECTION and concept.concept_type == "REFERENCE"
        assert concept.confidence_score == 0.95
        assert concept.definitions and concept.definitions[0]
        data = concept.source_data[KnowledgeSource.CELLXGENE]
        assert data["doi"] == "10.1016/j.cell.2021.07.023"
        assert data["n_datasets"] == 1 and data["total_cells"] == 32588
        assert data["tissues"] == [{"id": "UBERON:0001728", "label": "nasopharynx"}]
        assert {d["label"] for d in data["diseases"]} >= {"COVID-19", "long COVID-19"}
        assert data["organisms"] == ["Homo sapiens"] and data["assays"] == ["Seq-Well S3"]
        assert data["n_cell_types"] == 6
        assert data["first_authors"] and all(isinstance(a, str) for a in data["first_authors"])
        assert any(link["url"] for link in data["links"])
        assert data["url"].endswith(f"/collections/{LC_COLLECTION}")
        assert req.call_args_list[-1].args[0].endswith(f"/curation/v1/collections/{LC_COLLECTION}")

    @pytest.mark.asyncio
    async def test_collection_details_survive_curation_failure(self, adapter):
        with patched(adapter, curation_collection=RuntimeError("503")):
            concept = await adapter.get_concept_details(LC_COLLECTION)
        assert concept is not None and "doi" not in concept.source_data[KnowledgeSource.CELLXGENE]

    @pytest.mark.asyncio
    async def test_collection_details_ignore_non_dict_curation(self, adapter):
        with patched(adapter, curation_collection=["unexpected"]):
            concept = await adapter.get_concept_details(LC_COLLECTION)
        assert concept is not None and not concept.definitions

    @pytest.mark.asyncio
    async def test_dataset_details_return_asset_urls_only(self, adapter):
        with patched(adapter) as req:
            concept = await adapter.get_concept_details(LC_DATASET)
        assert concept.concept_type == "ASSAY" and concept.primary_label == "Nasopharynx"
        data = concept.source_data[KnowledgeSource.CELLXGENE]
        assert data["collection_id"] == LC_COLLECTION
        assert data["collection_name"].startswith("Impaired local intrinsic immunity")
        assert data["cell_count"] == 32588 and data["n_donors"] == 4
        assert data["assets"][0]["url"].endswith(f"{LC_VERSION}.h5ad")
        assert data["assets"][0]["filetype"] == "H5AD" and data["assets"][0]["filesize_bytes"]
        assert data["explorer_url"].endswith(f"{LC_DATASET}.cxg/")
        assert len(data["cell_types"]) == 6 and data["n_cell_types"] == 6
        # only JSON metadata endpoints were requested, never an h5ad file
        urls = [c.args[0] for c in req.call_args_list]
        assert not any(u.endswith(".h5ad") for u in urls)
        assert urls[-1].endswith(f"/collections/{LC_COLLECTION}/datasets/{LC_DATASET}")

    @pytest.mark.asyncio
    async def test_dataset_details_accept_version_id(self, adapter):
        with patched(adapter):
            concept = await adapter.get_concept_details(LC_VERSION)
        assert concept.primary_id == LC_DATASET

    @pytest.mark.asyncio
    async def test_dataset_details_survive_curation_failure(self, adapter):
        with patched(adapter, curation_dataset=RuntimeError("403")):
            concept = await adapter.get_concept_details(LC_DATASET)
        assert concept is not None
        assert "assets" not in concept.source_data[KnowledgeSource.CELLXGENE]
        with patched(adapter, curation_dataset=["unexpected"]):
            concept = await adapter.get_concept_details(LC_DATASET)
        assert "assets" not in concept.source_data[KnowledgeSource.CELLXGENE]

    @pytest.mark.asyncio
    async def test_dataset_without_collection_skips_detail_call(self, adapter):
        records = copy.deepcopy(DATASETS_INDEX)
        records[0]["collection_id"] = ""
        with patched(adapter, datasets=records) as req:
            concept = await adapter.get_concept_details(LC_DATASET)
        assert concept is not None
        assert not any("curation/v1/collections/" in c.args[0] for c in req.call_args_list)

    @pytest.mark.asyncio
    async def test_cell_type_tissue_and_disease_details(self, adapter):
        with patched(adapter):
            nk = await adapter.get_concept_details("CL:0000623")
            blood = await adapter.get_concept_details("uberon:0000178")
            lc = await adapter.get_concept_details("MONDO:0100233")
        assert nk.primary_label == "natural killer cell" and nk.concept_type == "CELL_TYPE"
        nk_data = nk.source_data[KnowledgeSource.CELLXGENE]
        assert nk_data["n_datasets"] == 1 and nk_data["cells_in_datasets"] == 112040
        assert nk_data["top_tissues"] == [
            {"id": "UBERON:0000178", "label": "blood", "n_datasets": 1}
        ]
        assert blood.concept_type == "TISSUE" and lc.concept_type == "DISEASE"
        assert lc.source_data[KnowledgeSource.CELLXGENE]["n_collections"] == 1

    @pytest.mark.asyncio
    async def test_unknown_and_invalid_ids(self, adapter):
        with patched(adapter):
            assert await adapter.get_concept_details("CL:9999999") is None
            assert (
                await adapter.get_concept_details("00000000-0000-0000-0000-000000000000") is None
            )
            assert await adapter.get_concept_details("natural killer cell") is None
            assert await adapter.get_concept_details("") is None


class TestMappings:
    @pytest.mark.asyncio
    async def test_dataset_mappings_carry_ontology_ids(self, adapter):
        with patched(adapter):
            mappings = await adapter.get_mappings(LC_DATASET)
        pairs = {(m["toSource"], m["toId"]) for m in mappings}
        assert ("UBERON", "UBERON:0001728") in pairs
        assert ("MONDO", "MONDO:0100233") in pairs
        assert ("EFO", "EFO:0030019") in pairs
        assert ("NCBITAXON", "NCBITaxon:9606") in pairs
        assert ("CL", "CL:0000236") in pairs
        for m in mappings:
            assert set(m) == {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            }
            assert m["fromId"] == LC_DATASET and m["mappingType"] == "annotation"
        assert len({m["toId"] for m in mappings}) == len(mappings)

    @pytest.mark.asyncio
    async def test_collection_mappings_include_doi(self, adapter):
        with patched(adapter):
            mappings = await adapter.get_mappings(LC_COLLECTION)
        assert mappings[0]["toId"] == "DOI:10.1016/j.cell.2021.07.023"
        assert mappings[0]["toSource"] == "DOI" and mappings[0]["mappingType"] == "exact"
        assert any(m["toId"] == "UBERON:0001728" for m in mappings)

    @pytest.mark.asyncio
    async def test_collection_mappings_without_doi(self, adapter):
        with patched(adapter, curation_collection=RuntimeError("boom")):
            mappings = await adapter.get_mappings(LC_COLLECTION)
        assert mappings and not any(m["toSource"] == "DOI" for m in mappings)
        with patched(adapter, curation_collection=["x"]):
            assert not any(
                m["toSource"] == "DOI" for m in await adapter.get_mappings(LC_COLLECTION)
            )

    @pytest.mark.asyncio
    async def test_mappings_are_capped(self, adapter, monkeypatch):
        monkeypatch.setattr(cellxgene_adapter, "_MAX_MAPPINGS", 3)
        with patched(adapter):
            assert len(await adapter.get_mappings(LC_DATASET)) == 3

    @pytest.mark.asyncio
    async def test_term_mapping_and_unknowns(self, adapter):
        with patched(adapter):
            term = await adapter.get_mappings("CL:0000623")
            assert term == [
                {
                    "fromId": "CL:0000623",
                    "toId": "CL:0000623",
                    "fromSource": "CELLXGENE",
                    "toSource": "CL",
                    "mappingType": "exact",
                    "confidence": 1.0,
                }
            ]
            assert await adapter.get_mappings("CL:9999999") == []
            assert await adapter.get_mappings("00000000-0000-0000-0000-000000000000") == []
            assert await adapter.get_mappings("") == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_collection_edges(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships(LC_COLLECTION)
        labels = [r["relation_label"] for r in rels]
        assert labels == [
            "has_dataset",
            "has_tissue",
            "has_disease",
            "has_disease",
            "has_disease",
            "has_disease",
        ]
        dataset = rels[0]
        assert dataset["related_id"] == LC_DATASET and dataset["cell_count"] == 32588
        assert dataset["tissues"] == ["nasopharynx"] and "long COVID-19" in dataset["diseases"]
        assert all(r["source"] == "CELLXGENE" for r in rels)

    @pytest.mark.asyncio
    async def test_dataset_edges(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships(LC_VERSION, limit=2)
        by_label = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r["related_id"])
        assert by_label["part_of_collection"] == [LC_COLLECTION]
        assert by_label["has_tissue"] == ["UBERON:0001728"]
        assert by_label["uses_assay"] == ["EFO:0030019"]
        assert by_label["from_organism"] == ["NCBITaxon:9606"]
        assert len(by_label["has_cell_type"]) == 2  # capped by limit
        assert len(by_label["has_disease"]) == 2

    @pytest.mark.asyncio
    async def test_dataset_edges_without_known_collection(self, adapter):
        collections = [c for c in COLLECTIONS_INDEX if c["id"] != LC_COLLECTION]
        with patched(adapter, collections=collections):
            rels = await adapter.get_relationships(LC_DATASET)
        assert "part_of_collection" not in {r["relation_label"] for r in rels}

    @pytest.mark.asyncio
    async def test_disease_edges_answer_which_collections_study_it(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("MONDO:0100233")
        by_label = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)
        assert [r["related_id"] for r in by_label["observed_in_tissue"]] == ["UBERON:0001728"]
        collection = by_label["studied_in_collection"][0]
        assert collection["related_id"] == LC_COLLECTION
        assert collection["n_datasets"] == 1 and collection["cells"] == 32588
        assert len(by_label["contains_cell_type"]) == 6

    @pytest.mark.asyncio
    async def test_tissue_edges(self, adapter):
        with patched(adapter):
            rels = await adapter.get_relationships("UBERON:0000178", limit=3)
        labels = {r["relation_label"] for r in rels}
        assert labels == {"contains_cell_type", "studied_in_collection"}
        assert sum(r["relation_label"] == "contains_cell_type" for r in rels) == 3

    @pytest.mark.asyncio
    async def test_cell_type_edges_and_markers(self, adapter):
        with patched(adapter) as req:
            rels = await adapter.get_relationships("CL:0000623", limit=4)
        by_label = {}
        for r in rels:
            by_label.setdefault(r["relation_label"], []).append(r)
        assert [r["related_id"] for r in by_label["found_in_tissue"]] == ["UBERON:0000178"]
        dataset = by_label["found_in_dataset"][0]
        assert dataset["related_id"] == NK_DATASET and dataset["cell_count"] == 112040
        assert dataset["collection"].startswith("A bispecific CD3")
        markers = by_label["has_marker_gene"]
        assert [m["related_name"] for m in markers] == ["GNLY", "NKG7", "PRF1", "KLRD1"]
        assert markers[0]["related_id"] == "ENSG00000115523"
        assert markers[0]["tissue"] == "blood" and markers[0]["tissue_id"] == "UBERON:0000178"
        assert markers[0]["snapshot_id"] == "1762972271" and markers[0]["marker_score"] > 2
        post = next(c for c in req.call_args_list if c.args[0].endswith("wmg/v2/markers"))
        assert post.kwargs["json_data"] == {
            "celltype": "CL:0000623",
            "organism": "NCBITaxon:9606",
            "tissue": "UBERON:0000178",
            "test": "ttest",
            "n_markers": 4,
        }

    @pytest.mark.asyncio
    async def test_marker_tissue_can_be_pinned(self, adapter):
        by_tissue = {"UBERON:0002048": WMG_MARKERS}
        with patched(adapter, markers=by_tissue) as req:
            rels = await adapter.get_relationships("CL:0000623", limit=2, tissue="uberon:0002048")
        markers = [r for r in rels if r["relation_label"] == "has_marker_gene"]
        assert [m["tissue"] for m in markers] == ["lung", "lung"]
        posts = [c for c in req.call_args_list if c.args[0].endswith("wmg/v2/markers")]
        assert len(posts) == 1 and posts[0].kwargs["json_data"]["tissue"] == "UBERON:0002048"

    @pytest.mark.asyncio
    async def test_markers_fall_back_to_next_tissue_then_give_up(self, adapter):
        records = copy.deepcopy(DATASETS_INDEX)
        # NK dataset also rolled up to a second WMG tissue via an ancestor term
        records[1]["tissue_ancestors"] = ["UBERON:0002048"]
        empty = {"UBERON:0002048": WMG_MARKERS}
        with patched(adapter, datasets=records, markers=empty) as req:
            rels = await adapter.get_relationships("CL:0000623", limit=2)
        markers = [r for r in rels if r["relation_label"] == "has_marker_gene"]
        assert [m["tissue"] for m in markers] == ["lung", "lung"]
        assert sum(c.args[0].endswith("wmg/v2/markers") for c in req.call_args_list) == 2
        with patched(adapter, markers={"marker_genes": []}):
            rels = await adapter.get_relationships("CL:0000623")
        assert not [r for r in rels if r["relation_label"] == "has_marker_gene"]

    @pytest.mark.asyncio
    async def test_marker_failures_are_tolerated(self, adapter):
        with patched(adapter, markers=RuntimeError("500")):
            rels = await adapter.get_relationships("CL:0000623")
        assert "found_in_tissue" in {r["relation_label"] for r in rels}
        assert "has_marker_gene" not in {r["relation_label"] for r in rels}
        with patched(adapter, markers=["not a dict"]):
            rels = await adapter.get_relationships("CL:0000623")
        assert "has_marker_gene" not in {r["relation_label"] for r in rels}

    @pytest.mark.asyncio
    async def test_marker_symbols_fall_back_to_ensembl_ids(self, adapter):
        with patched(adapter, wmg=RuntimeError("timeout")) as req:
            rels = await adapter.get_relationships("CL:0000623", limit=2)
            await adapter.get_relationships("CL:0000623", limit=2)
        markers = [r for r in rels if r["relation_label"] == "has_marker_gene"]
        assert [m["related_name"] for m in markers] == ["ENSG00000115523", "ENSG00000105374"]
        assert markers[0]["tissue"] == "UBERON:0000178"  # tissue name unknown without WMG
        # failures are not cached: the dimensions are asked for again
        dims = [c for c in req.call_args_list if c.args[0].endswith("primary_filter_dimensions")]
        assert len(dims) == 2

    @pytest.mark.asyncio
    async def test_wmg_dimensions_are_cached(self, adapter):
        with patched(adapter) as req:
            await adapter.get_relationships("CL:0000623", limit=1)
            await adapter.get_relationships("CL:0000623", limit=1)
        dims = [c for c in req.call_args_list if c.args[0].endswith("primary_filter_dimensions")]
        assert len(dims) == 1

    @pytest.mark.asyncio
    async def test_mouse_only_cell_type_has_no_markers(self, adapter):
        with patched(adapter) as req:
            rels = await adapter.get_relationships("CL:2000075")
        assert "has_marker_gene" not in {r["relation_label"] for r in rels}
        assert not any(c.args[0].endswith("wmg/v2/markers") for c in req.call_args_list)

    @pytest.mark.asyncio
    async def test_invalid_inputs(self, adapter):
        with patched(adapter):
            assert await adapter.get_relationships(LC_COLLECTION, limit=0) == []
            assert await adapter.get_relationships("") == []
            assert await adapter.get_relationships("CL:9999999") == []
            assert await adapter.get_relationships("00000000-0000-0000-0000-000000000000") == []
