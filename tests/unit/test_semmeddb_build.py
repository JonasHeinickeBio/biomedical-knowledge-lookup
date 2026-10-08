"""Tests for the SemMedDB SQLite builder (MySQL dump / CSV / TSV -> indexed SQLite)."""

import gzip
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knowledge_lookup import __main__ as main
from knowledge_lookup.adapters import _semmeddb_build as build
from knowledge_lookup.adapters import semmeddb_adapter as adapter_module
from knowledge_lookup.adapters.semmeddb_adapter import SemMedDBAdapter
from knowledge_lookup.models import LookupConfig

pytestmark = pytest.mark.unit

CREATE = """CREATE TABLE `PREDICATION` (
  `PREDICATION_ID` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `SENTENCE_ID` bigint(20) unsigned NOT NULL,
  `PMID` varchar(20) DEFAULT NULL,
  `PREDICATE` varchar(50) DEFAULT NULL,
  `SUBJECT_CUI` varchar(255) DEFAULT NULL,
  `SUBJECT_NAME` varchar(999) DEFAULT NULL,
  `SUBJECT_SEMTYPE` varchar(4) DEFAULT NULL,
  `SUBJECT_NOVELTY` tinyint(4) DEFAULT NULL,
  `OBJECT_CUI` varchar(255) DEFAULT NULL,
  `OBJECT_NAME` varchar(999) DEFAULT NULL,
  `OBJECT_SEMTYPE` varchar(4) DEFAULT NULL,
  `OBJECT_NOVELTY` tinyint(4) DEFAULT NULL,
  PRIMARY KEY (`PREDICATION_ID`),
  KEY `idx_pmid` (`PMID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# (id, sentence, pmid, predicate, s_cui, s_name, s_type, s_nov, o_cui, o_name, o_type, o_nov)
TRICKY_ROWS = (
    "(1,10,'111','TREATS','C0004057','Aspirin','phsu',1,'C0018681','Headache','sosy',1),"
    "(2,11,'112','CAUSES','C0015674','Fatigue Syndrome, Chronic','dsyn',1,'C0020295',"
    "'Hodgkin\\'s \"quoted\" (disease); a,b','dsyn',0),"
    "(3,12,'113','ASSOCIATED_WITH','C0079189','IL-6 \\\\ back\\nslash','aapp',NULL,'C0015672',"
    "'Fatigue','sosy',-1),"
    "(4,13,'114','INTERACTS_WITH','C0000001','O''Neil','gngm',1,'C0000002','','gngm',1)"
)
DUMP = (
    "-- MySQL dump 10.13  Distrib 8.0.36\n"
    "/*!40101 SET NAMES utf8mb4 */;\n"
    "DROP TABLE IF EXISTS `PREDICATION`;\n"
    + CREATE
    + "LOCK TABLES `PREDICATION` WRITE;\n"
    + f"INSERT INTO `PREDICATION` VALUES {TRICKY_ROWS};\n"
    + "INSERT INTO `PREDICATION` VALUES "
    + "(5,14,'115','PREDISPOSES','C0000003','x','dsyn',1,'C0000004','y','dsyn',1);\n"
    + "UNLOCK TABLES;\n"
    + "INSERT INTO `CITATIONS` VALUES ('999','not a predication',1);\n"
)


def rows_of(db: Path) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT * FROM PREDICATION ORDER BY PREDICATION_ID").fetchall()
    finally:
        conn.close()


def write(path: Path, text: str) -> Path:
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="utf-8", newline="")
    return path


class TestMysqlDump:
    def test_parses_escapes_nulls_and_ignores_other_tables(self, tmp_path):
        dump = write(tmp_path / "semmed.sql", DUMP)
        stats = build.build_predication_db([dump], tmp_path / "out.sqlite")
        assert stats.rows == 5 and stats.skipped == 0
        rows = {r[0]: r for r in rows_of(tmp_path / "out.sqlite")}
        assert rows["1"][5] == "Aspirin"
        assert rows["2"][5] == "Fatigue Syndrome, Chronic"
        assert rows["2"][9] == 'Hodgkin\'s "quoted" (disease); a,b'  # \' and ", ( ) ; ,
        assert rows["3"][5] == "IL-6 \\ back\nslash"  # \\ and \n
        assert rows["3"][7] is None  # NULL
        assert rows["3"][11] == "-1"  # negative number kept as text
        assert rows["4"][5] == "O'Neil"  # '' escape
        assert rows["4"][9] == ""  # empty string is not NULL in a dump
        assert "999" not in {r[0] for r in rows.values()}  # CITATIONS row ignored

    def test_gzipped_dump_and_adapter_ready_schema(self, tmp_path):
        dump = write(tmp_path / "semmed.sql.gz", DUMP)
        build.build_predication_db([dump], tmp_path / "out.sqlite")
        conn = sqlite3.connect(tmp_path / "out.sqlite")
        indexes = {r[1] for r in conn.execute("PRAGMA index_list(PREDICATION)")}
        columns = [r[1] for r in conn.execute("PRAGMA table_info(PREDICATION)")]
        conn.close()
        assert {"idx_pred_subject_cui", "idx_pred_object_cui", "idx_pred_pmid"} <= indexes
        assert columns == list(build.PREDICATION_COLUMNS)

    def test_explicit_column_list_in_insert_is_honoured(self, tmp_path):
        text = (
            "INSERT INTO `PREDICATION` (`PMID`,`PREDICATE`,`SUBJECT_CUI`,`SUBJECT_NAME`,"
            "`SUBJECT_SEMTYPE`,`OBJECT_CUI`,`OBJECT_NAME`,`OBJECT_SEMTYPE`) VALUES "
            "('1','TREATS','C1','a','dsyn','C2','b','sosy');\n"
        )
        build.build_predication_db([write(tmp_path / "d.sql", text)], tmp_path / "o.sqlite")
        conn = sqlite3.connect(tmp_path / "o.sqlite")
        got = conn.execute("SELECT PMID, SUBJECT_NAME, OBJECT_NAME FROM PREDICATION").fetchall()
        conn.close()
        assert got == [("1", "a", "b")]

    def test_create_table_column_order_is_used(self, tmp_path):
        text = (
            "CREATE TABLE `PREDICATION` (\n"
            "  `PMID` varchar(20),\n  `PREDICATE` varchar(50),\n  `SUBJECT_CUI` varchar(9),\n"
            "  `SUBJECT_NAME` varchar(99),\n  `SUBJECT_SEMTYPE` varchar(4),\n"
            "  `OBJECT_CUI` varchar(9),\n  `OBJECT_NAME` varchar(99),\n"
            "  `OBJECT_SEMTYPE` varchar(4)\n) ENGINE=InnoDB;\n"
            "INSERT INTO `PREDICATION` VALUES ('1','TREATS','C1','a','dsyn','C2','b','sosy');\n"
        )
        build.build_predication_db([write(tmp_path / "d.sql", text)], tmp_path / "o.sqlite")
        conn = sqlite3.connect(tmp_path / "o.sqlite")
        assert conn.execute("SELECT SUBJECT_NAME FROM PREDICATION").fetchone() == ("a",)
        conn.close()

    def test_sniffs_dump_without_sql_extension(self, tmp_path):
        path = write(tmp_path / "semmed_dump.dat", DUMP)
        assert build.detect_format(path) == "dump"
        assert build.detect_format(write(tmp_path / "x.tsv", "a\tb\n")) == "delimited"
        assert build.detect_format(write(tmp_path / "y.dat", "a\tb\n1\t2\n")) == "delimited"

    def test_unescape_helper(self):
        assert build._unescape_sql("plain") == "plain"
        assert build._unescape_sql("a\\tb\\0c") == "a\tb\0c"
        assert build._unescape_sql("100\\%") == "100\\%"  # MySQL keeps the backslash here
        assert build._unescape_sql("x\\qy") == "xqy"


class TestDelimited:
    HEADER = ",".join(build.PREDICATION_COLUMNS)
    ROW = '1,10,111,TREATS,C0004057,Aspirin,phsu,1,C0018681,"Head, ache",sosy,\\N'

    def test_csv_with_header_nulls_and_quotes(self, tmp_path):
        src = write(tmp_path / "p.csv.gz", f"{self.HEADER}\n{self.ROW}\n")
        stats = build.build_predication_db([src], tmp_path / "o.sqlite")
        assert stats.rows == 1
        (row,) = rows_of(tmp_path / "o.sqlite")
        assert row[9] == "Head, ache" and row[11] is None

    def test_headerless_tsv(self, tmp_path):
        src = write(tmp_path / "p.tsv", "1\t10\t111\tTREATS\tC1\ta\tphsu\t1\tC2\tb\tsosy\t1\n")
        assert build.build_predication_db([src], tmp_path / "o.sqlite").rows == 1

    def test_multiple_sources_are_appended_and_realigned(self, tmp_path):
        a = write(tmp_path / "a.csv", f"{self.HEADER}\n{self.ROW}\n")
        reordered = ",".join(reversed(build.PREDICATION_COLUMNS))
        row_b = ",".join(reversed(self.ROW.replace('"Head, ache"', "x").split(",")))
        b = write(tmp_path / "b.csv", f"{reordered}\n{row_b}\n")
        stats = build.build_predication_db([a, b], tmp_path / "o.sqlite")
        assert stats.rows == 2

    def test_mostly_garbled_file_is_rejected(self, tmp_path):
        good = self.ROW.replace("1,10,111", "1,10,111")
        lines = [good] + ["garbled,line"] * 2000
        src = write(tmp_path / "bad.csv", f"{self.HEADER}\n" + "\n".join(lines) + "\n")
        with pytest.raises(ValueError, match="malformed"):
            build.build_predication_db([src], tmp_path / "o.sqlite")
        assert not (tmp_path / "o.sqlite").exists()
        assert not (tmp_path / "o.sqlite.part").exists()

    def test_a_few_bad_lines_are_skipped_and_counted(self, tmp_path):
        src = write(tmp_path / "p.csv", f"{self.HEADER}\n{self.ROW}\ngarbled,line\n")
        stats = build.build_predication_db([src], tmp_path / "o.sqlite")
        assert (stats.rows, stats.skipped) == (1, 1)


class TestBuildBehaviour:
    def test_refuses_to_overwrite_unless_asked(self, tmp_path):
        src = write(tmp_path / "semmed.sql", DUMP)
        out = tmp_path / "out.sqlite"
        build.build_predication_db([src], out)
        with pytest.raises(FileExistsError):
            build.build_predication_db([src], out)
        assert build.build_predication_db([src], out, overwrite=True).rows == 5

    def test_missing_required_columns_and_empty_inputs(self, tmp_path):
        wrong = write(tmp_path / "w.csv", "A,B\n1,2\n")
        with pytest.raises(ValueError):
            build.build_predication_db([wrong], tmp_path / "o1.sqlite")
        no_rows = write(tmp_path / "n.sql", "CREATE TABLE `OTHER` (\n  `A` int\n);\n")
        with pytest.raises(ValueError, match="no PREDICATION rows"):
            build.build_predication_db([no_rows], tmp_path / "o2.sqlite")
        with pytest.raises(ValueError, match="no source files"):
            build.build_predication_db([], tmp_path / "o3.sqlite")
        assert not list(tmp_path.glob("*.part"))

    def test_progress_callback_is_called(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "INSERT_BATCH", 2)
        calls = []
        src = write(tmp_path / "semmed.sql", DUMP)
        build.build_predication_db(
            [src],
            tmp_path / "o.sqlite",
            progress=lambda r, s: calls.append((r, s)),
            progress_every=2,
        )
        assert calls and calls[-1] == (5, 0)


class TestAdapterIntegration:
    @pytest.mark.asyncio
    async def test_adapter_queries_a_database_built_from_a_dump(self, tmp_path, monkeypatch):
        out = tmp_path / "semmeddb.sqlite"
        build.build_predication_db([write(tmp_path / "semmed.sql.gz", DUMP)], out)
        monkeypatch.setenv("SEMMEDDB_PATH", str(out))
        adapter = SemMedDBAdapter(LookupConfig())
        assert adapter.is_available() is True
        found = await adapter.search_concepts("aspirin")
        assert found and found[0].primary_id == "C0004057"
        rels = await adapter.get_relationships("C0004057")
        assert any(r["related_id"] == "C0018681" for r in rels)

    def test_small_dump_is_imported_lazily_but_a_huge_export_is_refused(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path / "cache"))
        export = write(tmp_path / "semmed.sql", DUMP)
        monkeypatch.setenv("SEMMEDDB_PATH", str(export))
        adapter = SemMedDBAdapter(LookupConfig())
        assert adapter.is_available() is True  # small enough to import on first use

        monkeypatch.setattr(adapter_module, "MAX_LAZY_IMPORT_BYTES", 10)  # now "too large"
        assert adapter.is_available() is False

    @pytest.mark.asyncio
    async def test_huge_export_returns_nothing_and_points_to_the_builder(
        self, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(tmp_path / "cache"))
        export = write(tmp_path / "semmed.sql", DUMP)
        monkeypatch.setenv("SEMMEDDB_PATH", str(export))
        monkeypatch.setattr(adapter_module, "MAX_LAZY_IMPORT_BYTES", 10)
        adapter = SemMedDBAdapter(LookupConfig())
        with caplog.at_level("ERROR"):
            assert await adapter.search_concepts("aspirin") == []
        assert "semmeddb-build" in caplog.text


class TestCli:
    def test_build_command_end_to_end(self, tmp_path):
        src = write(tmp_path / "semmed.sql.gz", DUMP)
        out = tmp_path / "semmeddb.sqlite"
        result = CliRunner().invoke(main.app, ["semmeddb-build", str(src), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert "5 predications" in result.output and "SEMMEDDB_PATH" in result.output
        assert len(rows_of(out)) == 5

    def test_existing_output_needs_force_and_bad_input_fails_cleanly(self, tmp_path):
        src = write(tmp_path / "semmed.sql", DUMP)
        out = tmp_path / "o.sqlite"
        runner = CliRunner()
        assert runner.invoke(main.app, ["semmeddb-build", str(src), "-o", str(out)]).exit_code == 0
        again = runner.invoke(main.app, ["semmeddb-build", str(src), "-o", str(out)])
        assert again.exit_code == 1 and "--force" in again.output
        assert (
            runner.invoke(
                main.app, ["semmeddb-build", str(src), "-o", str(out), "--force"]
            ).exit_code
            == 0
        )
        bad = write(tmp_path / "bad.csv", "A,B\n1,2\n")
        failed = runner.invoke(
            main.app, ["semmeddb-build", str(bad), "-o", str(tmp_path / "x.sqlite")]
        )
        assert failed.exit_code == 1 and "Error" in failed.output


class TestMaxRows:
    def test_stops_after_the_requested_number_of_rows(self, tmp_path):
        src = write(tmp_path / "semmed.sql", DUMP)
        stats = build.build_predication_db([src], tmp_path / "o.sqlite", max_rows=3)
        assert stats.rows == 3 and len(rows_of(tmp_path / "o.sqlite")) == 3

    def test_limit_spans_multiple_sources(self, tmp_path):
        a = write(tmp_path / "a.sql", DUMP)
        b = write(tmp_path / "b.sql", DUMP)
        stats = build.build_predication_db([a, b], tmp_path / "o.sqlite", max_rows=7)
        assert stats.rows == 7

    def test_cli_max_rows(self, tmp_path):
        src = write(tmp_path / "semmed.sql", DUMP)
        out = tmp_path / "o.sqlite"
        result = CliRunner().invoke(
            main.app, ["semmeddb-build", str(src), "-o", str(out), "--max-rows", "2"]
        )
        assert result.exit_code == 0 and len(rows_of(out)) == 2


# ---------------------------------------------------------------------------------------
# Precomputed CONCEPT / TRIPLE tables
# ---------------------------------------------------------------------------------------

# (pmid, predicate, s_cui, s_name, s_type, o_cui, o_name, o_type): repeated triples with
# several PMIDs, a hub concept, two names for one CUI, a negated predicate
AGG_ROWS = [
    ("1", "TREATS", "C0004057", "Aspirin", "phsu", "C0018681", "Headache", "sosy"),
    ("2", "TREATS", "C0004057", "Aspirin", "phsu", "C0018681", "Headache", "sosy"),
    ("2", "TREATS", "C0004057", "Aspirin", "phsu", "C0018681", "Headache", "sosy"),  # same PMID
    ("3", "TREATS", "C0004057", "ASA", "phsu", "C0018681", "Headache", "sosy"),
    ("4", "NEG_TREATS", "C0004057", "Aspirin", "phsu", "C0015674", "Chronic fatigue", "dsyn"),
    ("5", "CAUSES", "C0004057", "Aspirin", "phsu", "C0151744", "Myocardial ischemia", "dsyn"),
    ("6", "ASSOCIATED_WITH", "C0015674", "Chronic fatigue", "dsyn", "C0079189", "IL-6", "aapp"),
    ("7", "ASSOCIATED_WITH", "C0015674", "Chronic fatigue", "dsyn", "C0079189", "IL-6", "aapp"),
    ("8", "AFFECTS", "C0079189", "IL-6", "aapp", "C0004057", "Aspirin", "phsu"),
]


def agg_csv(tmp_path: Path) -> Path:
    header = "PMID,PREDICATE,SUBJECT_CUI,SUBJECT_NAME,SUBJECT_SEMTYPE,OBJECT_CUI,OBJECT_NAME,OBJECT_SEMTYPE"
    return write(
        tmp_path / "agg.csv", header + "\n" + "\n".join(",".join(r) for r in AGG_ROWS) + "\n"
    )


def build_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = agg_csv(tmp_path)
    with_agg, without = tmp_path / "with.sqlite", tmp_path / "without.sqlite"
    build.build_predication_db([src], with_agg)
    build.build_predication_db([src], without, aggregates=False)
    return with_agg, without


def tables(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


class TestAggregateTables:
    def test_default_build_creates_the_lookup_tables(self, tmp_path):
        with_agg, without = build_pair(tmp_path)
        assert {"PREDICATION", "CONCEPT", "TRIPLE"} <= tables(with_agg)
        assert tables(without) == {"PREDICATION"}

    def test_concept_and_triple_contents(self, tmp_path):
        with_agg, _ = build_pair(tmp_path)
        conn = sqlite3.connect(with_agg)
        concept = {
            (r[0], r[1], r[3]): (r[4], r[5])
            for r in conn.execute("SELECT CUI, NAME, SEMTYPE, SIDE, N, P FROM CONCEPT")
        }
        assert concept[("C0004057", "Aspirin", "s")] == (5, 4)  # 5 rows; PMIDs 1, 2, 2, 4, 5
        assert concept[("C0004057", "ASA", "s")] == (1, 1)
        assert concept[("C0004057", "Aspirin", "o")] == (1, 1)
        triple = conn.execute(
            "SELECT PMIDS, PREDS FROM TRIPLE WHERE SUBJECT_CUI='C0004057' AND PREDICATE='TREATS'"
            " AND OBJECT_CUI='C0018681'"
        ).fetchone()
        assert triple == (3, 4)  # PMIDs 1, 2, 3 over four sentences
        conn.close()

    @pytest.mark.asyncio
    async def test_adapter_answers_are_identical_with_and_without_the_tables(
        self, tmp_path, monkeypatch
    ):
        with_agg, without = build_pair(tmp_path)

        async def everything(db: Path):
            monkeypatch.setenv("SEMMEDDB_PATH", str(db))
            adapter = SemMedDBAdapter(LookupConfig())
            found = await adapter.search_concepts("asp")
            rels = await adapter.get_relationships("C0004057")
            return (
                [(c.primary_id, c.primary_label) for c in found],
                sorted(
                    (r["relation_label"], r["related_id"], r["direction"], r["pmid_count"])
                    for r in rels
                ),
                await adapter.get_mappings("C0004057"),
                await adapter.get_mappings("C9999999"),
                (await adapter.get_concept_details("C0015674")).primary_label,
                await adapter.get_concept_details("C9999999"),
                await adapter.get_supporting_pmids("C0004057", "TREATS", "C0018681"),
            )

        fast, slow = await everything(with_agg), await everything(without)
        assert fast == slow
        assert fast[1][0][3] >= 1 and len(fast[1]) >= 4  # real content, not two empty answers

    @pytest.mark.asyncio
    async def test_predicate_filter_works_on_the_triple_table(self, tmp_path, monkeypatch):
        with_agg, _ = build_pair(tmp_path)
        monkeypatch.setenv("SEMMEDDB_PATH", str(with_agg))
        rels = await SemMedDBAdapter(LookupConfig()).get_relationships(
            "C0004057", predicates=["treats"]
        )
        assert rels and {r["relation_label"] for r in rels} == {"TREATS"}

    @pytest.mark.asyncio
    async def test_substring_search_policy(self, tmp_path, monkeypatch):
        with_agg, without = build_pair(tmp_path)
        monkeypatch.setattr(adapter_module, "SUBSTRING_SCAN_MAX_ROWS", 0)
        # a mid-word query ('fatigue' inside 'Chronic fatigue') needs the substring pass
        monkeypatch.setenv("SEMMEDDB_PATH", str(with_agg))
        with_tables = await SemMedDBAdapter(LookupConfig()).search_concepts("fatigue")
        assert [c.primary_id for c in with_tables] == ["C0015674"]  # cheap on CONCEPT
        monkeypatch.setenv("SEMMEDDB_PATH", str(without))
        raw = await SemMedDBAdapter(LookupConfig()).search_concepts("fatigue")
        assert raw == []  # full-table substring scan refused on a "big" database

    def test_no_aggregates_flag_on_the_cli(self, tmp_path):
        out = tmp_path / "o.sqlite"
        result = CliRunner().invoke(
            main.app,
            ["semmeddb-build", str(agg_csv(tmp_path)), "-o", str(out), "--no-aggregates"],
        )
        assert result.exit_code == 0 and tables(out) == {"PREDICATION"}
