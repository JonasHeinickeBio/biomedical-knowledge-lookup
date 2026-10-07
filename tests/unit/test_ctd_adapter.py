"""Unit tests for CTDAdapter.

The adapter reads gzipped CTD bulk reports. ``write_ctd_files`` materialises small gzip files
(real excerpts, see tests/fixtures/ctd_responses.py) in a temp ``CTD_DATA_DIR`` so the real
streaming/parsing code runs; no network access happens.
"""

import gzip
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import ctd_adapter
from knowledge_lookup.adapters.ctd_adapter import CTDAdapter, _action_label, _classify, _iter_rows
from knowledge_lookup.models import KnowledgeSource
from tests.fixtures.ctd_responses import write_ctd_files

pytestmark = pytest.mark.unit


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    write_ctd_files(tmp_path)
    monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
    for var in ("CTD_DOWNLOAD_GENES", "CTD_DOWNLOAD_GENES_DISEASES"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


@pytest.fixture
def adapter(lookup_config, data_dir):
    return CTDAdapter(lookup_config)


@pytest.fixture
def full_adapter(lookup_config, tmp_path, monkeypatch):
    """Adapter whose data dir also holds the optional genes / genes-diseases files."""
    write_ctd_files(tmp_path, optional=True)
    monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
    return CTDAdapter(lookup_config)


class TestHelpers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("MESH:D001241", ("mesh", "D001241")),
            ("mesh:c534883", ("mesh", "C534883")),
            ("D001241", ("mesh", "D001241")),
            ("CTD:MESH:D001241", ("mesh", "D001241")),
            ("OMIM:264300", ("omim", "264300")),
            ("NCBIGene:672", ("gene", "672")),
            ("ncbigene:672", ("gene", "672")),
            ("GeneID:672", ("gene", "672")),
            ("50-78-2", ("cas", "50-78-2")),
            ("aspirin", None),
            ("MESH:", None),
            ("", None),
        ],
    )
    def test_classify(self, raw, expected):
        assert _classify(raw) == expected

    def test_action_label(self):
        assert _action_label("increases^expression") == "increases_expression"
        assert _action_label("affects^folding") == "affects_folding"
        assert _action_label("Decreases^Reaction ") == "decreases_reaction"

    def test_iter_rows_skips_comments_and_filters(self, tmp_path):
        path = tmp_path / "x.csv"
        path.write_text('# comment\na,b,"c,d"\nx,y,z\n', encoding="utf-8")
        assert list(_iter_rows(path, None)) == [["a", "b", "c,d"], ["x", "y", "z"]]
        assert list(_iter_rows(path, "y,z")) == [["x", "y", "z"]]
        assert list(_iter_rows(path, "A,B", lower=True)) == [["a", "b", "c,d"]]

    def test_iter_rows_tolerates_truncated_gzip(self, tmp_path):
        path = tmp_path / "t.csv.gz"
        with gzip.open(path, "wt") as handle:
            handle.write("a,b\n" * 5000)
        path.write_bytes(path.read_bytes()[:-20])  # corrupt the trailer / drop final block
        assert len(list(_iter_rows(path, None))) <= 5000  # no exception


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.CTD
        assert adapter.is_available() is True

    def test_data_dir_override_and_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
        assert CTDAdapter._data_dir() == tmp_path
        monkeypatch.delenv("CTD_DATA_DIR")
        assert CTDAdapter._data_dir().name == "ctd"


class TestDownloads:
    @pytest.mark.asyncio
    async def test_required_file_uses_ensure_dataset(self, lookup_config, tmp_path, monkeypatch):
        monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
        fake = AsyncMock(return_value=tmp_path / "CTD_chemicals.csv.gz")
        with patch.object(ctd_adapter, "ensure_dataset", fake):
            path = await CTDAdapter(lookup_config)._dataset("CTD_chemicals.csv.gz")
        assert path == tmp_path / "CTD_chemicals.csv.gz"
        kwargs = fake.call_args.kwargs
        assert fake.call_args.args[0] == "https://ctdbase.org/reports/CTD_chemicals.csv.gz"
        assert kwargs["decompress"] is False  # stay gzipped, stream on every query
        assert kwargs["cache_dir"] == tmp_path
        assert kwargs["filename"] == "CTD_chemicals.csv.gz"

    @pytest.mark.asyncio
    async def test_optional_file_needs_opt_in(self, lookup_config, tmp_path, monkeypatch):
        monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("CTD_DOWNLOAD_GENES_DISEASES", raising=False)
        fake = AsyncMock(return_value=tmp_path / "CTD_genes_diseases.csv.gz")
        adapter = CTDAdapter(lookup_config)
        with patch.object(ctd_adapter, "ensure_dataset", fake):
            assert await adapter._dataset("CTD_genes_diseases.csv.gz", required=False) is None
            fake.assert_not_awaited()
            monkeypatch.setenv("CTD_DOWNLOAD_GENES_DISEASES", "1")
            assert await adapter._dataset("CTD_genes_diseases.csv.gz", required=False)
            fake.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_optional_file_present_is_used_without_opt_in(self, full_adapter):
        path = await full_adapter._dataset("CTD_genes.csv.gz", required=False)
        assert path is not None and path.exists()

    @pytest.mark.asyncio
    async def test_download_failure_degrades(self, lookup_config, tmp_path, monkeypatch):
        monkeypatch.setenv("CTD_DATA_DIR", str(tmp_path))
        boom = AsyncMock(side_effect=OSError("network down"))
        adapter = CTDAdapter(lookup_config)
        with patch.object(ctd_adapter, "ensure_dataset", boom):
            assert await adapter.search_concepts("aspirin") == []
            assert await adapter.get_concept_details("MESH:D001241") is None
            assert await adapter.get_relationships("MESH:D001241") == []
            assert await adapter.get_mappings("MESH:D001241") == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_chemical_by_exact_name(self, adapter):
        (concept,) = await adapter.search_concepts("10074-G5")
        assert concept.primary_id == "MESH:C534883"
        assert concept.concept_type == "CHEMICAL"
        assert "ctd_chemical" in concept.categories
        assert {i.source for i in concept.identifiers} >= {
            KnowledgeSource.MESH,
            KnowledgeSource.PUBCHEM,
        }
        pubchem = next(i for i in concept.identifiers if i.source == KnowledgeSource.PUBCHEM)
        assert pubchem.identifier == "2836600"  # "CID:" prefix stripped
        assert concept.parents == ["MESH:D010069"]

    @pytest.mark.asyncio
    async def test_disease_by_name_and_synonym(self, adapter):
        concepts = await adapter.search_concepts("hydroxylase")
        assert [c.primary_id for c in concepts] == ["MESH:C537806"]
        assert concepts[0].concept_type == "DISEASE"
        by_synonym = await adapter.search_concepts("CMO I Deficiency")
        assert [c.primary_id for c in by_synonym] == ["MESH:C537806"]
        assert "OMIM:203400" in {i.identifier for i in concepts[0].identifiers}

    @pytest.mark.asyncio
    async def test_ranking_exact_before_substring_and_limit(self, adapter):
        exact = await adapter.search_concepts("hyperkinesis")
        assert exact[0].primary_label == "Hyperkinesis"
        # substring of a chemical name + a disease name ("Deficiency"): limit applies
        many = await adapter.search_concepts("deficiency", limit=10)
        assert len(many) >= 2 and all(c.concept_type == "DISEASE" for c in many)
        assert len(await adapter.search_concepts("deficiency", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_search_by_identifiers_and_cas(self, adapter):
        assert (await adapter.search_concepts("OMIM:264300"))[0].primary_id == "MESH:C537805"
        assert (await adapter.search_concepts("28227-36-3"))[
            0
        ].primary_label == "0-acetylpantolactone"
        assert (await adapter.search_concepts("NCBIGene:367"))[0].primary_id == "NCBIGene:367"
        assert await adapter.search_concepts("MESH:D999999") == []

    @pytest.mark.asyncio
    async def test_gene_symbol_via_interaction_file(self, adapter):
        concepts = await adapter.search_concepts("EPHB2")
        assert concepts[0].primary_id == "NCBIGene:2048"
        assert concepts[0].concept_type == "GENE"
        assert concepts[0].definitions == []  # no gene name without CTD_genes.csv.gz

    @pytest.mark.asyncio
    async def test_gene_symbol_via_genes_file(self, full_adapter):
        concepts = await full_adapter.search_concepts("AR")
        assert concepts[0].primary_id == "NCBIGene:367"
        assert concepts[0].definitions == ["androgen receptor"]
        assert "NR3C4" in concepts[0].synonyms
        assert KnowledgeSource.UNIPROT in {i.source for i in concepts[0].identifiers}

    @pytest.mark.asyncio
    async def test_no_results_blank_and_bad_limit(self, adapter):
        assert await adapter.search_concepts("zzzznothing") == []
        assert await adapter.search_concepts("  ") == []
        assert await adapter.search_concepts("aspirin", limit=0) == []

    @pytest.mark.asyncio
    async def test_results_are_memoised(self, adapter):
        first = await adapter.search_concepts("hydroxylase")
        with patch.object(CTDAdapter, "_dataset", AsyncMock(side_effect=AssertionError("rescan"))):
            again = await adapter.search_concepts("hydroxylase")
        assert [c.primary_id for c in again] == [c.primary_id for c in first]


class TestDetails:
    @pytest.mark.asyncio
    async def test_details_by_each_id_kind(self, adapter):
        assert (await adapter.get_concept_details("MESH:C534883")).primary_label == "10074-G5"
        assert (await adapter.get_concept_details("C534883")).primary_id == "MESH:C534883"
        disease = await adapter.get_concept_details("MESH:C537805")
        assert disease.concept_type == "DISEASE"
        assert any(
            "17-Beta Hydroxysteroid Dehydrogenase 3 Deficiency" in s for s in disease.synonyms
        )
        assert (await adapter.get_concept_details("OMIM:264300")).primary_id == "MESH:C537805"
        gene = await adapter.get_concept_details("NCBIGene:367")
        assert gene.primary_label == "AR" and gene.concept_type == "GENE"

    @pytest.mark.asyncio
    async def test_details_not_found_and_invalid(self, adapter):
        assert await adapter.get_concept_details("MESH:D999999") is None
        assert await adapter.get_concept_details("NCBIGene:1") is None
        assert await adapter.get_concept_details("OMIM:1") is None
        assert await adapter.get_concept_details("99-99-9") is None
        assert await adapter.get_concept_details("aspirin") is None

    @pytest.mark.asyncio
    async def test_unusable_rows_yield_no_concept(self, adapter):
        assert adapter._chemical_to_concept(["", "MESH:C1"]) is None
        assert adapter._disease_to_concept(["x", ""]) is None
        assert adapter._gene_to_concept(["AR", "androgen receptor", "abc"]) is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_chemical_edges_interleave_genes_and_diseases(self, adapter):
        edges = await adapter.get_relationships("MESH:C112297", limit=50)
        labels = {e["relation_label"] for e in edges}
        assert {"decreases_activity", "increases_expression", "marker_mechanism_for"} <= labels
        diseases = {e["related_id"] for e in edges if e["related_type"] == "disease"}
        assert diseases == {"MESH:D006948", "MESH:D012640"}  # curated only; inferred skipped
        marker = next(e for e in edges if e["related_id"] == "MESH:D006948")
        assert marker["direct_evidence"] == "marker/mechanism"
        assert marker["pmids"] == ["19098162"] and marker["source"] == "CTD"
        # one family must not crowd out the other
        assert [e["related_type"] for e in edges[:2]] == ["gene", "disease"]

    @pytest.mark.asyncio
    async def test_interaction_aggregation_organism_and_pmids(self, adapter):
        edges = await adapter.get_relationships("MESH:C534883", limit=50)
        genes = [e for e in edges if e["related_type"] == "gene"]
        assert all(e["relation_label"] != "interacts_with" for e in genes)
        myc = next(
            e
            for e in genes
            if e["related_id"] == "NCBIGene:4609" and e["relation_label"] == "decreases_expression"
        )
        assert myc["pmids"] == ["26036281", "32184358"] and myc["n_pmids"] == 2
        assert myc["organism"] == "Homo sapiens" and myc["organism_id"] == "9606"
        assert myc["n_interactions"] == 2
        assert "MYC protein" in myc["interaction"]
        # one edge per (gene, action, organism)
        keys = [(e["related_id"], e["relation_label"], e["organism"]) for e in genes]
        assert len(keys) == len(set(keys))
        # rows with no organism (MAX) sort after human ones
        organisms = [e["organism"] for e in genes]
        assert organisms.index(None) > organisms.index("Homo sapiens")
        assert organisms[-1] is None

    @pytest.mark.asyncio
    async def test_limit_respected(self, adapter):
        assert len(await adapter.get_relationships("MESH:C112297", limit=3)) == 3
        assert await adapter.get_relationships("MESH:C112297", limit=0) == []

    @pytest.mark.asyncio
    async def test_disease_edges_chemicals_only_without_genes_file(self, adapter):
        edges = await adapter.get_relationships("MESH:D006948")
        assert {e["related_id"] for e in edges} == {"MESH:C112297", "MESH:C425777"}
        assert {e["relation_label"] for e in edges} == {"marker_mechanism_chemical"}
        assert all(e["related_type"] == "chemical" for e in edges)

    @pytest.mark.asyncio
    async def test_disease_edges_with_genes_file(self, full_adapter):
        edges = await full_adapter.get_relationships("MESH:D006948")
        gene = next(e for e in edges if e["related_type"] == "gene")
        assert gene["relation_label"] == "has_marker_mechanism_gene"
        assert gene["related_id"] == "NCBIGene:367" and gene["pmids"] == ["11111111", "22222222"]
        edges = await full_adapter.get_relationships("MESH:D004827")
        assert edges[0]["relation_label"] == "has_therapeutic_target_gene"

    @pytest.mark.asyncio
    async def test_gene_edges(self, full_adapter):
        edges = await full_adapter.get_relationships("NCBIGene:367", limit=50)
        chem = [e for e in edges if e["related_type"] == "chemical"]
        disease = [e for e in edges if e["related_type"] == "disease"]
        assert {e["related_id"] for e in chem} == {"MESH:C534883"}
        assert {e["relation_label"] for e in disease} == {
            "marker_mechanism_for",
            "therapeutic_target_for",
        }  # the inferred (no direct evidence) row is dropped
        assert all(e["n_pmids"] == len(e["pmids"]) for e in disease)

    @pytest.mark.asyncio
    async def test_gene_edges_chemicals_only_without_optional_file(self, adapter):
        edges = await adapter.get_relationships("NCBIGene:367")
        assert edges and all(e["related_type"] == "chemical" for e in edges)

    @pytest.mark.asyncio
    async def test_unknown_and_invalid_ids(self, adapter):
        assert await adapter.get_relationships("MESH:D999999") == []
        assert await adapter.get_relationships("nonsense") == []

    @pytest.mark.asyncio
    async def test_interaction_without_actions_or_organism(self, adapter):
        rows = [["Chem", "C1", "", "GENE1", "7", "", "", "", "Chem interacts with GENE1", "", ""]]
        (edge,) = adapter._interaction_edges(rows, True)
        assert edge["relation_label"] == "interacts_with" and edge["organism"] is None
        assert adapter._interaction_edges([["", "", "", ""]], True) == []
        assert adapter._interaction_edges([["Chem", ""]], False) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_chemical_mappings(self, adapter):
        maps = await adapter.get_mappings("MESH:C534883")
        by_source = {m["toSource"]: m["toId"] for m in maps}
        assert by_source == {"MESH": "MESH:C534883", "PUBCHEM": "2836600"}
        assert all(m["fromId"] == "MESH:C534883" and m["fromSource"] == "CTD" for m in maps)
        cas = await adapter.get_mappings("28227-36-3")
        assert {m["toSource"]: m["toId"] for m in cas}["CAS"] == "28227-36-3"

    @pytest.mark.asyncio
    async def test_disease_mappings(self, adapter):
        maps = await adapter.get_mappings("MESH:C537806")
        assert {m["toId"] for m in maps} == {"MESH:C537806", "OMIM:203400", "OMIM:610600"}
        assert {m["toSource"] for m in maps} == {"MESH", "OMIM"}

    @pytest.mark.asyncio
    async def test_gene_mappings_and_failures(self, full_adapter, adapter):
        by_source = {}
        for m in await full_adapter.get_mappings("NCBIGene:367"):
            by_source.setdefault(m["toSource"], []).append(m["toId"])
        assert by_source["UNIPROT"] == ["P10275"]
        assert by_source["PHARMGKB"] == ["PA1665", "PA24"]
        assert by_source["NCBI"] == ["367"]
        assert await adapter.get_mappings("MESH:D999999") == []
        assert await adapter.get_mappings("junk") == []


def test_files_are_real_gzip(data_dir):
    names = sorted(p.name for p in Path(data_dir).iterdir())
    assert "CTD_chem_gene_ixns.csv.gz" in names
    with gzip.open(Path(data_dir) / "CTD_chemicals.csv.gz", "rt") as handle:
        assert "ChemicalName,ChemicalID" in handle.read()
