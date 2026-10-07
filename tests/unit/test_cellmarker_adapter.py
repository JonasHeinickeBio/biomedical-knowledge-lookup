"""Unit tests for CellMarkerAdapter and the stdlib xlsx reader; no network."""

import asyncio
import csv
import gzip
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from xml.sax.saxutils import escape

import pytest

from knowledge_lookup.adapters import cellmarker_adapter as cm
from knowledge_lookup.adapters._xlsx import _column_index, iter_xlsx_rows
from knowledge_lookup.adapters.cellmarker_adapter import CellMarkerAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.cellmarker_responses import HEADER_2_0, ROWS_2_0, TSV_3_0

pytestmark = pytest.mark.unit

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
RNS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _col(i: int) -> str:
    name = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        name = chr(65 + rem) + name
    return name


def write_xlsx(path: Path, rows, *, inline=False, with_workbook=True, second_sheet=True) -> Path:
    """Build a tiny but structurally real xlsx (shared strings or inline strings)."""
    shared: list[str] = []
    index: dict[str, int] = {}
    body = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            if value == "":
                continue  # real files omit empty cells
            ref = f"{_col(c)}{r}"
            if isinstance(value, int | float):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            elif inline:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            else:
                if value not in index:
                    index[value] = len(shared)
                    shared.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{index[value]}</v></c>')
        body.append(f'<row r="{r}">{"".join(cells)}</row>')
    sheet = f"<worksheet {NS}><sheetData>{''.join(body)}</sheetData></worksheet>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        if with_workbook:
            z.writestr(
                "xl/workbook.xml",
                f'<workbook {NS} {RNS}><sheets><sheet name="Data" sheetId="1" r:id="rId9"/>'
                f'<sheet name="Other" sheetId="2" r:id="rId8"/></sheets></workbook>',
            )
            z.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId8" Type="t" Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="rId9" Type="t" Target="/xl/worksheets/sheet2.xml"/>'
                "</Relationships>",
            )
        if not inline:
            sst = "".join(f"<si><t>{escape(s)}</t></si>" for s in shared)
            z.writestr("xl/sharedStrings.xml", f"<sst {NS}>{sst}</sst>")
        # sheet1 is a decoy: the workbook lists the real data sheet first (sheet2.xml)
        decoy = f'<worksheet {NS}><sheetData><row r="1"><c r="A1"><v>1</v></c></row></sheetData></worksheet>'
        if with_workbook and second_sheet:
            z.writestr("xl/worksheets/sheet1.xml", decoy)
            z.writestr("xl/worksheets/sheet2.xml", sheet)
        else:
            z.writestr("xl/worksheets/sheet1.xml", sheet)
    return path


def write_tsv(path: Path, header, rows, delimiter="\t") -> Path:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


@pytest.fixture
def xlsx_path(tmp_path):
    return write_xlsx(tmp_path / "Cell_marker_Human.xlsx", [HEADER_2_0, *ROWS_2_0])


@pytest.fixture
def adapter(lookup_config, xlsx_path, monkeypatch):
    monkeypatch.setenv(cm.CELLMARKER_PATH_ENV, str(xlsx_path))
    return CellMarkerAdapter(lookup_config)


# ----------------------------------------------------------------------
# xlsx reader
# ----------------------------------------------------------------------


class TestXlsxReader:
    def test_shared_and_numeric_cells_with_gaps(self, tmp_path):
        rows = [["a", "", "c"], ["", "é & <b>", 42], ["x"]]
        path = write_xlsx(tmp_path / "t.xlsx", rows)
        assert list(iter_xlsx_rows(path)) == [["a", "", "c"], ["", "é & <b>", "42"], ["x"]]

    def test_inline_strings_and_missing_shared_strings(self, tmp_path):
        path = write_xlsx(tmp_path / "t.xlsx", [["h1", "h2"], ["v", 7]], inline=True)
        assert list(iter_xlsx_rows(path)) == [["h1", "h2"], ["v", "7"]]

    def test_first_sheet_follows_workbook_order(self, tmp_path):
        path = write_xlsx(tmp_path / "t.xlsx", [["real", "data"]])
        assert list(iter_xlsx_rows(path)) == [["real", "data"]]  # not the decoy sheet1.xml

    def test_fallback_without_workbook(self, tmp_path):
        path = write_xlsx(tmp_path / "t.xlsx", [["a", "b"]], with_workbook=False)
        assert list(iter_xlsx_rows(path)) == [["a", "b"]]

    def test_rich_text_and_bad_shared_index(self, tmp_path):
        path = tmp_path / "rich.xlsx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(
                "xl/sharedStrings.xml",
                f"<sst {NS}><si><r><t>ab</t></r><r><t>cd</t></r></si></sst>",
            )
            z.writestr(
                "xl/worksheets/sheet1.xml",
                f'<worksheet {NS}><sheetData><row><c t="s"><v>0</v></c>'
                f'<c r="C1" t="s"><v>99</v></c><c r="D1" t="s"><v>x</v></c>'
                f'<c t="inlineStr"/></row></sheetData></worksheet>',
            )
        # ref-less first cell, bad index -> "", non-int index -> "", empty inline string
        assert list(iter_xlsx_rows(path)) == [["abcd", "", "", "", ""]]

    def test_no_sheet_is_an_error(self, tmp_path):
        path = tmp_path / "empty.xlsx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("xl/workbook.xml", "<workbook/>")
        with pytest.raises(ValueError):
            list(iter_xlsx_rows(path))

    def test_broken_workbook_falls_back(self, tmp_path):
        path = tmp_path / "broken.xlsx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("xl/workbook.xml", "<not-xml")
            z.writestr(
                "xl/worksheets/sheet3.xml",
                f'<worksheet {NS}><sheetData><row><c r="A1"><v>1</v></c></row></sheetData></worksheet>',
            )
        assert list(iter_xlsx_rows(path)) == [["1"]]

    def test_column_index(self):
        assert [_column_index(r) for r in ("A1", "B7", "Z1", "AA3", "??")] == [0, 1, 25, 26, 0]


# ----------------------------------------------------------------------
# Adapter
# ----------------------------------------------------------------------


class TestBasics:
    def test_source_and_availability(self, lookup_config, monkeypatch, tmp_path):
        monkeypatch.delenv(cm.CELLMARKER_PATH_ENV, raising=False)
        monkeypatch.delenv(cm.CELLMARKER_URL_ENV, raising=False)
        adapter = CellMarkerAdapter(lookup_config)
        assert adapter.get_source() == KnowledgeSource.CELLMARKER
        assert adapter.is_available() is False  # no built-in download location
        monkeypatch.setenv(cm.CELLMARKER_URL_ENV, "https://example.org/Cell_marker_Human.xlsx")
        assert adapter.is_available() is True
        monkeypatch.delenv(cm.CELLMARKER_URL_ENV)
        monkeypatch.setenv(cm.CELLMARKER_PATH_ENV, str(tmp_path / "missing.xlsx"))
        assert adapter.is_available() is False
        present = tmp_path / "present.xlsx"
        present.write_bytes(b"x")
        monkeypatch.setenv(cm.CELLMARKER_PATH_ENV, str(present))
        assert adapter.is_available() is True

    def test_construction_never_touches_data(self, lookup_config, monkeypatch):
        monkeypatch.delenv(cm.CELLMARKER_PATH_ENV, raising=False)
        with patch.object(CellMarkerAdapter, "_dataset_path", AsyncMock()) as fetch:
            CellMarkerAdapter(lookup_config)
        fetch.assert_not_called()

    def test_helpers(self):
        assert cm._digits("31982413.0") == "31982413"
        assert cm._digits("abc") == "" and cm._digits(None) == ""
        assert cm._cl_curie("CL_0000084") == "CL:0000084"
        assert cm._cl_curie("cl:0000084") == "CL:0000084"
        assert cm._cl_curie("None") == "" and cm._cl_curie("CL_12") == ""
        assert cm._clean("  NA ") == "" and cm._clean(" x ") == "x"


class TestSearch:
    @pytest.mark.asyncio
    async def test_gene_symbol_search(self, adapter):
        results = await adapter.search_concepts("CD4")
        assert results[0].primary_id == "CD4"
        assert results[0].concept_type == ConceptType.GENE
        ids = [c.primary_id for c in results]
        assert "CL:0000084" not in ids or ids.index("CD4") < ids.index("CL:0000084")
        gene = results[0]
        assert any(
            i.source == KnowledgeSource.NCBI and i.identifier == "920" for i in gene.identifiers
        )
        assert any(
            i.source == KnowledgeSource.UNIPROT and i.identifier == "P01730"
            for i in gene.identifiers
        )
        assert gene.source_data[KnowledgeSource.CELLMARKER]["cell_type_count"] == 1

    @pytest.mark.asyncio
    async def test_alias_search_finds_symbol(self, adapter):
        results = await adapter.search_concepts("CD16")
        assert results[0].primary_id == "FCGR3A"
        assert "CD16" in results[0].synonyms
        results = await adapter.search_concepts("pd-1")
        assert results[0].primary_id == "PDCD1"

    @pytest.mark.asyncio
    async def test_cell_name_search(self, adapter):
        results = await adapter.search_concepts("natural killer cell")
        assert results[0].primary_id == "CL:0000623"
        assert results[0].concept_type == ConceptType.CELL_TYPE
        assert any(
            i.source == KnowledgeSource.CELLONTOLOGY and i.identifier == "CL:0000623"
            for i in results[0].identifiers
        )
        assert results[0].confidence_score > 0.8

    @pytest.mark.asyncio
    async def test_substring_and_prefix_matching_and_order(self, adapter):
        results = await adapter.search_concepts("t cell")
        assert [c.primary_id for c in results][:2] == ["CL:0000084", "CellMarker:Exhausted T cell"]
        results = await adapter.search_concepts("killer")
        assert results[0].primary_id == "CL:0000623"
        results = await adapter.search_concepts("KLR")  # gene prefix
        assert results[0].primary_id == "KLRD1"
        assert results[0].confidence_score < 0.7

    @pytest.mark.asyncio
    async def test_search_by_cl_id(self, adapter):
        results = await adapter.search_concepts("CL_0000236")
        assert results[0].primary_label == "B cell"

    @pytest.mark.asyncio
    async def test_limit_and_empty(self, adapter):
        assert len(await adapter.search_concepts("cell", limit=2)) == 2
        assert await adapter.search_concepts("") == []
        assert await adapter.search_concepts("CD4", limit=0) == []
        assert await adapter.search_concepts("zzzz-no-such-thing") == []

    @pytest.mark.asyncio
    async def test_short_queries_do_not_substring_match(self, adapter):
        assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_cell_details(self, adapter):
        cell = await adapter.get_concept_details("CL:0000084")
        assert cell.primary_label == "T cell"
        data = cell.source_data[KnowledgeSource.CELLMARKER]
        assert data["species"] == ["Human", "Mouse"]
        assert set(data["top_markers"]) == {"CD4", "CD3E", "CD8A"}
        assert data["top_markers"][0] == "CD4"  # most PMIDs
        assert data["marker_count"] == 3 and data["pmid_count"] == 4
        assert data["conditions"] == ["Breast cancer"] and "UBERON:0000178" in data["uberon_ids"]
        assert {"Peripheral blood", "Lymph node", "Spleen", "Breast"} == set(data["tissues"])
        assert "tissue: Lymph node" in cell.categories
        for alias in ("CL_0000084", "cl:0000084", "T cell", "t cell"):
            assert (await adapter.get_concept_details(alias)).primary_id == "CL:0000084"

    @pytest.mark.asyncio
    async def test_cell_without_cl_id(self, adapter):
        cell = await adapter.get_concept_details("CellMarker:Exhausted T cell")
        assert cell.primary_id == "CellMarker:Exhausted T cell"
        assert not any(i.source == KnowledgeSource.CELLONTOLOGY for i in cell.identifiers)
        assert (
            await adapter.get_concept_details("exhausted t cell")
        ).primary_label == "Exhausted T cell"

    @pytest.mark.asyncio
    async def test_gene_details_by_symbol_alias_and_entrez(self, adapter):
        for ident in ("FCGR3A", "fcgr3a", "CD16", "NCBIGene:2215", "GeneID:2215", "2215"):
            gene = await adapter.get_concept_details(ident)
            assert gene.primary_id == "FCGR3A", ident
        assert gene.primary_label == "Fc fragment of IgG receptor IIIb"
        assert gene.semantic_types == ["protein_coding"]
        data = gene.source_data[KnowledgeSource.CELLMARKER]
        assert data["cell_type_count"] == 3 and data["record_count"] == 3
        assert set(data["top_cell_types"]) == {"Macrophage", "Natural killer cell", "Monocyte"}
        assert {i.identifier for i in gene.identifiers if i.source == KnowledgeSource.UNIPROT} == {
            "O75015",
            "A0A0X1",  # noqa: E501
        }

    @pytest.mark.asyncio
    async def test_unknown_and_empty(self, adapter):
        for ident in ("", "  ", "CL:9999999", "99999999", "NOTAGENE", "CellMarker:nothing"):
            assert await adapter.get_concept_details(ident) is None

    @pytest.mark.asyncio
    async def test_marker_without_symbol_is_kept(self, adapter):
        gene = await adapter.get_concept_details("RP11-620J15.3")
        assert gene is not None and gene.identifiers[0].identifier == "RP11-620J15.3"
        assert not any(i.source == KnowledgeSource.NCBI for i in gene.identifiers)


class TestRelationships:
    @pytest.mark.asyncio
    async def test_cell_to_markers(self, adapter):
        rels = await adapter.get_relationships("CL:0000084")
        assert [r["related_name"] for r in rels][0] == "CD4"
        cd4 = rels[0]
        assert cd4["relation_label"] == "has_marker"
        assert cd4["related_id"] == "NCBIGene:920"
        assert cd4["source"] == "CellMarker"
        assert cd4["species"] == ["Human", "Mouse"]
        assert cd4["tissue_count"] == 3 and set(cd4["tissues"]) == {
            "Peripheral blood",
            "Lymph node",
            "Spleen",
        }
        assert cd4["pmid_count"] == 3 and cd4["record_count"] == 4
        assert cd4["pmids"] == ["10000001", "10000002", "10000003"]
        assert cd4["evidence_types"] == ["Experiment", "Review"]
        assert len(await adapter.get_relationships("CL:0000084", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_marker_to_cells(self, adapter):
        rels = await adapter.get_relationships("CD16")
        assert {r["relation_label"] for r in rels} == {"is_marker_of"}
        assert {r["related_name"] for r in rels} == {
            "Macrophage",
            "Natural killer cell",
            "Monocyte",
        }
        assert {r["related_id"] for r in rels} == {"CL:0000235", "CL:0000623", "CL:0000576"}

    @pytest.mark.asyncio
    async def test_marker_without_gene_id_uses_symbol_reference(self, adapter):
        rels = await adapter.get_relationships("CellMarker:Exhausted T cell")
        assert {r["related_id"] for r in rels} == {"NCBIGene:5133", "RP11-620J15.3"}

    @pytest.mark.asyncio
    async def test_edge_cases(self, adapter):
        assert await adapter.get_relationships("CL:9999999") == []
        assert await adapter.get_relationships("CD4", limit=0) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_cell_mapping_to_cl(self, adapter):
        assert await adapter.get_mappings("T cell") == [
            {
                "fromId": "CL:0000084",
                "toId": "CL:0000084",
                "fromSource": "CellMarker",
                "toSource": "CL",
                "mappingType": "xref",
                "confidence": 0.95,
            }
        ]
        assert await adapter.get_mappings("CellMarker:Exhausted T cell") == []

    @pytest.mark.asyncio
    async def test_gene_mappings(self, adapter):
        mappings = await adapter.get_mappings("CD16")
        assert {(m["toSource"], m["toId"]) for m in mappings} == {
            ("NCBIGene", "2215"),
            ("UniProt", "O75015"),
            ("UniProt", "A0A0X1"),  # noqa: E501
        }
        assert all(m["fromId"] == "NCBIGene:2215" for m in mappings)
        assert await adapter.get_mappings("nonsense") == []


# ----------------------------------------------------------------------
# Data loading: formats, persistence, download, failures
# ----------------------------------------------------------------------


class TestDataLoading:
    @pytest.mark.asyncio
    async def test_tsv_csv_and_gz_with_3_0_headers(self, lookup_config, tmp_path, monkeypatch):
        tsv = tmp_path / "human_cell_marker.txt"
        tsv.write_text(TSV_3_0, encoding="utf-8")
        gz = tmp_path / "human_cell_marker.txt.gz"
        gz.write_bytes(gzip.compress(TSV_3_0.encode()))
        csv_path = write_csv_from_tsv(tmp_path / "human.csv")
        for path in (tsv, gz, csv_path):
            monkeypatch.setenv(cm.CELLMARKER_PATH_ENV, str(path))
            adapter = CellMarkerAdapter(lookup_config)
            gene = await adapter.get_concept_details("FANCL")
            assert gene.identifiers[1].identifier == "55120"  # "55120.0" float cleaned
            cell = await adapter.get_concept_details("CL:0011026")
            data = cell.source_data[KnowledgeSource.CELLMARKER]
            assert data["marker_count"] == 2 and data["pmid_count"] == 1
            assert "Progenitor cell" == cell.primary_label

    @pytest.mark.asyncio
    async def test_unusable_tables(self, lookup_config, tmp_path, monkeypatch):
        empty = tmp_path / "empty.tsv"
        empty.write_text("")
        wrong = write_tsv(tmp_path / "wrong.tsv", ["a", "b"], [["1", "2"]])
        for path in (empty, wrong):
            monkeypatch.setenv(cm.CELLMARKER_PATH_ENV, str(path))
            adapter = CellMarkerAdapter(lookup_config)
            assert await adapter.search_concepts("CD4") == []
            assert await adapter.get_concept_details("CD4") is None
            assert await adapter.get_relationships("CD4") == []
            assert await adapter.get_mappings("CD4") == []

    @pytest.mark.asyncio
    async def test_missing_override_path(self, lookup_config, tmp_path, monkeypatch):
        monkeypatch.setenv(cm.CELLMARKER_PATH_ENV, str(tmp_path / "nope.xlsx"))
        adapter = CellMarkerAdapter(lookup_config)
        assert await adapter.search_concepts("CD4") == []

    @pytest.mark.asyncio
    async def test_index_persisted_reused_and_rebuilt(self, adapter, xlsx_path):
        await adapter.search_concepts("CD4")
        index_file = xlsx_path.with_name(xlsx_path.name + ".index.json.gz")
        assert index_file.exists()
        # second adapter: reads the persisted index instead of re-parsing the xlsx
        with patch.object(cm, "build_index", side_effect=AssertionError("re-parsed")):
            fresh = CellMarkerAdapter(adapter.config)
            assert (await fresh.get_concept_details("CL:0000084")).primary_label == "T cell"
        before = (await adapter.get_concept_details("CL:0000084")).source_data
        # stale signature (data file changed) -> rebuilt
        write_xlsx(xlsx_path, [HEADER_2_0, ROWS_2_0[5]])
        rebuilt = CellMarkerAdapter(adapter.config)
        data = (await rebuilt.get_concept_details("CL:0000084")).source_data[
            KnowledgeSource.CELLMARKER
        ]
        assert data["marker_count"] == 1 and before != data
        # corrupt index -> rebuilt
        index_file.write_bytes(b"not gzip")
        again = CellMarkerAdapter(adapter.config)
        assert await again.get_concept_details("CD4") is not None

    @pytest.mark.asyncio
    async def test_persistence_failure_is_not_fatal(self, adapter, xlsx_path):
        with patch("gzip.open", side_effect=OSError("read-only")):
            index = cm.load_index(xlsx_path)
        assert index.genes
        assert not xlsx_path.with_name(xlsx_path.name + ".index.json.gz").exists()

    @pytest.mark.asyncio
    async def test_concurrent_calls_load_once(self, adapter):
        with patch.object(cm, "load_index", wraps=cm.load_index) as loader:
            await asyncio.gather(*(adapter.search_concepts("CD4") for _ in range(5)))
        assert loader.call_count == 1

    @pytest.mark.asyncio
    async def test_failed_load_is_reported_and_retried(self, lookup_config, monkeypatch):
        monkeypatch.delenv(cm.CELLMARKER_PATH_ENV, raising=False)
        adapter = CellMarkerAdapter(lookup_config)
        with patch.object(adapter, "_dataset_path", AsyncMock(side_effect=OSError("offline"))):
            assert await adapter.search_concepts("CD4") == []
        assert adapter._index is None


XLSX_URL = "https://example.org/files/Cell_marker_Human.xlsx"


class TestDownload:
    """The dataset is fetched lazily through the dataset cache; the network call is faked."""

    @pytest.mark.asyncio
    async def test_without_a_path_or_url_nothing_is_fetched(self, lookup_config):
        with patch("knowledge_lookup.utils.dataset_cache._fetch") as fetch:
            adapter = CellMarkerAdapter(lookup_config)
            assert await adapter.search_concepts("CD4") == []
        fetch.assert_not_called()

    @pytest.fixture(autouse=True)
    def _cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path / "cache"))
        monkeypatch.delenv(cm.CELLMARKER_PATH_ENV, raising=False)
        monkeypatch.delenv(cm.CELLMARKER_URL_ENV, raising=False)

    @pytest.mark.asyncio
    async def test_xlsx_download_is_lazy_cached_and_not_unpacked(
        self, lookup_config, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(cm.CELLMARKER_URL_ENV, XLSX_URL)
        source = write_xlsx(tmp_path / "remote.xlsx", [HEADER_2_0, *ROWS_2_0])
        calls = []

        async def fake_fetch(url, dest, timeout, headers):
            calls.append(url)
            dest.write_bytes(source.read_bytes())

        with patch("knowledge_lookup.utils.dataset_cache._fetch", fake_fetch):
            adapter = CellMarkerAdapter(lookup_config)
            assert calls == []  # nothing at construction
            assert (await adapter.search_concepts("CD4"))[0].primary_id == "CD4"
            other = CellMarkerAdapter(lookup_config)
            assert await other.get_concept_details("CL:0000084") is not None
        assert calls == [XLSX_URL]  # downloaded once, then fresh in the cache
        cached = tmp_path / "cache" / "Cell_marker_Human.xlsx"
        assert (
            zipfile.is_zipfile(cached) and "xl/workbook.xml" in zipfile.ZipFile(cached).namelist()
        )

    @pytest.mark.asyncio
    async def test_failed_refresh_uses_stale_copy_and_failure_without_copy(
        self, lookup_config, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(cm.CELLMARKER_URL_ENV, XLSX_URL)
        source = write_xlsx(tmp_path / "remote.xlsx", [HEADER_2_0, *ROWS_2_0])
        cached = tmp_path / "cache" / "Cell_marker_Human.xlsx"
        cached.parent.mkdir()
        cached.write_bytes(source.read_bytes())
        import os

        os.utime(cached, (1, 1))  # ancient -> stale

        async def failing_fetch(url, dest, timeout, headers):
            raise OSError("offline")

        with patch("knowledge_lookup.utils.dataset_cache._fetch", failing_fetch):
            adapter = CellMarkerAdapter(lookup_config)
            assert await adapter.get_concept_details("CL:0000084") is not None
            cached.unlink()
            adapter = CellMarkerAdapter(lookup_config)
            assert await adapter.get_concept_details("CL:0000084") is None

    @pytest.mark.asyncio
    async def test_custom_url_zip_of_tsv_goes_through_ensure_dataset(
        self, lookup_config, tmp_path, monkeypatch
    ):
        archive = tmp_path / "human_cell_marker.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("human_cell_marker.txt", TSV_3_0)
        monkeypatch.setenv(
            cm.CELLMARKER_URL_ENV, "http://example.invalid/file/human_cell_marker.zip"
        )

        async def fake_fetch(url, dest, timeout, headers):
            dest.write_bytes(archive.read_bytes())

        with patch("knowledge_lookup.utils.dataset_cache._fetch", fake_fetch):
            adapter = CellMarkerAdapter(lookup_config)
            gene = await adapter.get_concept_details("FANCL")
        assert gene is not None


def write_csv_from_tsv(path: Path) -> Path:
    rows = list(csv.reader(io.StringIO(TSV_3_0), delimiter="\t"))
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    return path


def test_index_json_round_trip_is_json_serialisable(xlsx_path):
    index = cm.build_index(xlsx_path)
    restored = cm._Index.from_json(json.loads(json.dumps(index.to_json([1, 2]))))
    assert restored.rows == index.rows and set(restored.genes) == set(index.genes)
    assert restored.cells["CL:0000084"].markers["CD4"].pmids == [10000001, 10000002, 10000003]
