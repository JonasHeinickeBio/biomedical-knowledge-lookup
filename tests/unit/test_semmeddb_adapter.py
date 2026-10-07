"""Unit tests for SemMedDBAdapter.

SemMedDB cannot be queried publicly (UMLS licence + large dump), so every test builds a tiny
synthetic SQLite database in ``tmp_path`` that follows the PREDICATION schema. The CUIs and
triples are illustrative (ME/CFS themed), not real SemMedDB content.
"""

import csv
import gzip
import io
import sqlite3

import pytest

from knowledge_lookup import LookupConfig
from knowledge_lookup.adapters import semmeddb_adapter as mod
from knowledge_lookup.adapters.semmeddb_adapter import (
    PREDICATION_COLUMNS,
    SemMedDBAdapter,
    import_predication_export,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource

pytestmark = pytest.mark.unit

CFS, FATIGUE, HYDRO, RITUX, IL6 = "C0015674", "C0015672", "C0020268", "C0393022", "C0021760"

# (PMID, PREDICATE, SUBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE, OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE)
TRIPLES = [
    (101, "TREATS", HYDRO, "Hydrocortisone", "phsu", CFS, "Chronic fatigue syndrome", "dsyn"),
    (101, "TREATS", HYDRO, "Hydrocortisone", "phsu", CFS, "Chronic fatigue syndrome", "dsyn"),
    (102, "TREATS", HYDRO, "Hydrocortisone", "phsu", CFS, "Chronic fatigue syndrome", "dsyn"),
    (103, "TREATS", HYDRO, "Hydrocortisone", "phsu", CFS, "Chronic fatigue syndrome", "dsyn"),
    (104, "TREATS", RITUX, "Rituximab", "phsu", CFS, "Chronic fatigue syndrome", "dsyn"),
    (107, "NEG_TREATS", RITUX, "Rituximab", "phsu", CFS, "Chronic fatigue syndrome", "dsyn"),
    (
        101,
        "ASSOCIATED_WITH",
        CFS,
        "Chronic fatigue syndrome",
        "dsyn",
        IL6,
        "Interleukin-6",
        "aapp",
    ),
    (
        105,
        "ASSOCIATED_WITH",
        CFS,
        "Chronic fatigue syndrome",
        "dsyn",
        IL6,
        "Interleukin-6",
        "aapp",
    ),
    (106, "ASSOCIATED_WITH", FATIGUE, "Fatigue", "sosy", CFS, "Chronic fatigue syndrome", "dsyn"),
    (
        108,
        "ASSOCIATED_WITH",
        CFS,
        "Fatigue Syndrome, Chronic",
        "dsyn",
        IL6,
        "Interleukin-6",
        "aapp",
    ),
    (109, "CAUSES", "C0000001", "Fatigue_x", "patf", FATIGUE, "Fatigue", "sosy"),
    (110, "CAUSES", "C0000002", "FatigueXx", "patf", FATIGUE, "Fatigue", "sosy"),
]


def _build_db(path, rows=TRIPLES, columns=PREDICATION_COLUMNS):
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE PREDICATION ({', '.join(columns)})")
    conn.executemany(
        f"INSERT INTO PREDICATION ({', '.join(columns)}) VALUES ({','.join('?' * len(columns))})",
        [
            tuple(
                {
                    "PREDICATION_ID": i,
                    "SENTENCE_ID": i,
                    "PMID": pmid,
                    "PREDICATE": pred,
                    "SUBJECT_CUI": scui,
                    "SUBJECT_NAME": sname,
                    "SUBJECT_SEMTYPE": sty,
                    "SUBJECT_NOVELTY": 1,
                    "OBJECT_CUI": ocui,
                    "OBJECT_NAME": oname,
                    "OBJECT_SEMTYPE": oty,
                    "OBJECT_NOVELTY": 1,
                }[c]
                for c in columns
            )
            for i, (pmid, pred, scui, sname, sty, ocui, oname, oty) in enumerate(rows, 1)
        ],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def db_path(tmp_path):
    return _build_db(tmp_path / "semmeddb.sqlite")


@pytest.fixture
def adapter(db_path, monkeypatch):
    monkeypatch.setenv("SEMMEDDB_PATH", str(db_path))
    return SemMedDBAdapter(LookupConfig())


@pytest.fixture
def no_path_adapter(monkeypatch):
    monkeypatch.delenv("SEMMEDDB_PATH", raising=False)
    monkeypatch.delenv("SEMMEDDB_API_KEY", raising=False)
    return SemMedDBAdapter(LookupConfig())


class TestAvailability:
    def test_source(self, adapter):
        assert adapter.get_source() == KnowledgeSource.SEMMEDDB

    def test_available_when_file_exists(self, adapter):
        assert adapter.is_available() is True

    def test_unavailable_without_path(self, no_path_adapter):
        assert no_path_adapter.is_available() is False

    def test_unavailable_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SEMMEDDB_PATH", str(tmp_path / "nope.sqlite"))
        assert SemMedDBAdapter(LookupConfig()).is_available() is False

    def test_directory_is_not_a_database(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SEMMEDDB_PATH", str(tmp_path))
        assert SemMedDBAdapter(LookupConfig()).is_available() is False

    def test_config_api_key_holds_the_path(self, db_path, monkeypatch):
        monkeypatch.delenv("SEMMEDDB_PATH", raising=False)
        config = LookupConfig(api_keys={"semmeddb": str(db_path)})
        assert SemMedDBAdapter(config).is_available() is True

    def test_oserror_is_unavailable(self, adapter, monkeypatch):
        def boom(self):
            raise OSError("denied")

        monkeypatch.setattr(mod.Path, "is_file", boom)
        assert adapter.is_available() is False

    @pytest.mark.asyncio
    async def test_everything_empty_without_database(self, no_path_adapter):
        a = no_path_adapter
        assert await a.search_concepts("fatigue") == []
        assert await a.get_concept_details(CFS) is None
        assert await a.get_relationships(CFS) == []
        assert await a.get_mappings(CFS) == []
        assert await a.get_supporting_pmids(HYDRO, "TREATS", CFS) == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_by_name_prefix_ranks_by_predications(self, adapter):
        concepts = await adapter.search_concepts("chronic fatigue", limit=5)
        assert [c.primary_id for c in concepts] == [CFS]
        cfs = concepts[0]
        assert cfs.primary_label == "Chronic fatigue syndrome"
        assert cfs.concept_type == ConceptType.DISEASE
        assert cfs.sources == [KnowledgeSource.SEMMEDDB]
        assert cfs.confidence_score == 0.7
        assert cfs.semantic_types == ["dsyn"]
        stats = cfs.source_data[KnowledgeSource.SEMMEDDB]
        # prefix "chronic fatigue" skips the "Fatigue Syndrome, Chronic" row (1 subject pred)
        assert stats["predication_count"] == 9
        assert stats["predications_as_subject"] == 2
        assert stats["predications_as_object"] == 7

    @pytest.mark.asyncio
    async def test_search_exact_name_first_and_synonyms(self, adapter):
        concepts = await adapter.search_concepts("Fatigue", limit=10)
        ids = [c.primary_id for c in concepts]
        assert ids[0] == FATIGUE  # exact name match outranks bigger prefix matches
        assert CFS in ids
        cfs = next(c for c in concepts if c.primary_id == CFS)
        assert "Fatigue Syndrome, Chronic" in cfs.synonyms

    @pytest.mark.asyncio
    async def test_search_substring_fallback_and_switch(self, adapter):
        found = await adapter.search_concepts("syndrome", limit=5)
        assert CFS in [c.primary_id for c in found]
        adapter.allow_substring_search = False
        assert await adapter.search_concepts("syndrome", limit=5) == []

    @pytest.mark.asyncio
    async def test_search_by_cui_forms(self, adapter):
        for query in (CFS, f"UMLS:{CFS}", f"cui:{CFS.lower()}"):
            concepts = await adapter.search_concepts(query)
            assert [c.primary_id for c in concepts] == [CFS]

    @pytest.mark.asyncio
    async def test_search_limit(self, adapter):
        assert len(await adapter.search_concepts("fatigue", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_like_wildcards_are_escaped(self, adapter):
        # "_" must not act as a wildcard (would also match FatigueXx), "%" must not match all
        concepts = await adapter.search_concepts("Fatigue_x", limit=10)
        assert [c.primary_id for c in concepts] == ["C0000001"]
        assert await adapter.search_concepts("%", limit=10) == []

    @pytest.mark.asyncio
    async def test_sql_injection_is_inert(self, adapter):
        assert await adapter.search_concepts("x'; DROP TABLE PREDICATION; --") == []
        assert len(await adapter.search_concepts(CFS)) == 1  # table still there

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,limit", [("", 5), ("   ", 5), ("fatigue", 0)])
    async def test_search_invalid_input(self, adapter, query, limit):
        assert await adapter.search_concepts(query, limit) == []

    @pytest.mark.asyncio
    async def test_search_no_match(self, adapter):
        assert await adapter.search_concepts("zzzzqqq") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_details(self, adapter):
        concept = await adapter.get_concept_details(CFS)
        assert concept.primary_id == CFS
        assert concept.primary_label == "Chronic fatigue syndrome"
        assert any(i.identifier == CFS and i.source == "UMLS" for i in concept.identifiers)
        assert concept.source_data[KnowledgeSource.SEMMEDDB]["pmid_count"] >= 5

    @pytest.mark.asyncio
    async def test_details_semantic_type_mapping(self, adapter):
        assert (await adapter.get_concept_details(HYDRO)).concept_type == ConceptType.DRUG
        assert (await adapter.get_concept_details(IL6)).concept_type == ConceptType.PROTEIN
        assert (await adapter.get_concept_details(FATIGUE)).concept_type == ConceptType.SYMPTOM

    @pytest.mark.asyncio
    async def test_details_unknown_semtype(self, tmp_path, monkeypatch):
        rows = [(1, "AFFECTS", "C1111111", "Thing", "zzzz", "C2222222", "Other", None)]
        monkeypatch.setenv("SEMMEDDB_PATH", str(_build_db(tmp_path / "u.sqlite", rows)))
        concept = await SemMedDBAdapter(LookupConfig()).get_concept_details("C1111111")
        assert concept.concept_type == ConceptType.UNKNOWN
        other = await SemMedDBAdapter(LookupConfig()).get_concept_details("C2222222")
        assert other.concept_type == ConceptType.UNKNOWN and other.semantic_types == []

    @pytest.mark.asyncio
    async def test_details_missing_and_invalid(self, adapter):
        assert await adapter.get_concept_details("C9999999") is None
        assert await adapter.get_concept_details("fatigue") is None
        assert await adapter.get_concept_details("") is None


class TestRelationships:
    @pytest.mark.asyncio
    async def test_both_directions_grouped_and_ranked(self, adapter):
        rels = await adapter.get_relationships(CFS)
        top = rels[0]
        assert top == {
            "relation_label": "TREATS",
            "related_id": HYDRO,
            "related_name": "Hydrocortisone",
            "source": "SemMedDB",
            "direction": "incoming",
            "related_semtype": "phsu",
            "pmid_count": 3,  # PMIDs 101, 102, 103 (PMID 101 counted once)
            "predication_count": 4,
            "negated": False,
        }
        by_key = {(r["relation_label"], r["related_id"], r["direction"]): r for r in rels}
        out = by_key[("ASSOCIATED_WITH", IL6, "outgoing")]
        assert out["pmid_count"] == 3  # 101, 105, 108
        assert out["predication_count"] == 3
        assert by_key[("NEG_TREATS", RITUX, "incoming")]["negated"] is True
        assert by_key[("ASSOCIATED_WITH", FATIGUE, "incoming")]["pmid_count"] == 1
        counts = [r["pmid_count"] for r in rels]
        assert counts == sorted(counts, reverse=True)

    @pytest.mark.asyncio
    async def test_limit_and_predicate_filter(self, adapter):
        assert len(await adapter.get_relationships(CFS, limit=2)) == 2
        rels = await adapter.get_relationships(CFS, predicates=["treats", " "])
        assert {r["relation_label"] for r in rels} == {"TREATS"}
        assert {r["related_id"] for r in rels} == {HYDRO, RITUX}

    @pytest.mark.asyncio
    async def test_relationships_empty_and_invalid(self, adapter):
        assert await adapter.get_relationships("C9999999") == []
        assert await adapter.get_relationships("not a cui") == []
        assert await adapter.get_relationships(CFS, limit=0) == []

    @pytest.mark.asyncio
    async def test_supporting_pmids(self, adapter):
        assert await adapter.get_supporting_pmids(HYDRO, "treats", CFS) == ["103", "102", "101"]
        assert await adapter.get_supporting_pmids(HYDRO, "TREATS", CFS, limit=1) == ["103"]
        assert await adapter.get_supporting_pmids(HYDRO, "CAUSES", CFS) == []
        assert await adapter.get_supporting_pmids("bad", "TREATS", CFS) == []
        assert await adapter.get_supporting_pmids(HYDRO, "", CFS) == []
        assert await adapter.get_supporting_pmids(HYDRO, "TREATS", CFS, limit=0) == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_mapping_to_umls(self, adapter):
        assert await adapter.get_mappings(f"UMLS:{CFS}") == [
            {
                "fromId": CFS,
                "toId": CFS,
                "fromSource": "SemMedDB",
                "toSource": "UMLS",
                "mappingType": "exact",
                "confidence": 1.0,
            }
        ]

    @pytest.mark.asyncio
    async def test_mapping_absent_or_invalid(self, adapter):
        assert await adapter.get_mappings("C9999999") == []
        assert await adapter.get_mappings("nope") == []


class TestReadOnlyAndErrors:
    @pytest.mark.asyncio
    async def test_connection_is_read_only(self, adapter, db_path):
        db = await adapter._resolve_db()
        conn = mod._open_ro(db)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM PREDICATION")
        conn.close()
        check = sqlite3.connect(db_path)
        assert check.execute("SELECT COUNT(*) FROM PREDICATION").fetchone()[0] == len(TRIPLES)
        check.close()

    @pytest.mark.asyncio
    async def test_query_timeout_aborts(self, adapter):
        adapter.query_timeout = -1.0  # deadline already passed -> first progress tick aborts

        def slow(conn):
            return conn.execute(
                "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 5000000) "
                "SELECT COUNT(*) FROM c"
            ).fetchall()

        with pytest.raises(sqlite3.OperationalError):
            await adapter._run(slow)

    @pytest.mark.asyncio
    async def test_methods_swallow_errors(self, adapter, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("db exploded")

        monkeypatch.setattr(SemMedDBAdapter, "_rows_for_cui", staticmethod(boom))
        monkeypatch.setattr(SemMedDBAdapter, "_rows_for_name", boom)
        monkeypatch.setattr(SemMedDBAdapter, "_triple_rows", staticmethod(boom))
        monkeypatch.setattr(SemMedDBAdapter, "_exists", staticmethod(boom))
        assert await adapter.search_concepts("fatigue") == []
        assert await adapter.search_concepts(CFS) == []
        assert await adapter.get_concept_details(CFS) is None
        assert await adapter.get_relationships(CFS) == []
        assert await adapter.get_mappings(CFS) == []
        monkeypatch.setattr(adapter, "_run", boom)
        assert await adapter.get_supporting_pmids(HYDRO, "TREATS", CFS) == []

    @pytest.mark.asyncio
    async def test_wrong_schema_is_rejected(self, tmp_path, monkeypatch):
        path = tmp_path / "bad.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE PREDICATION (PMID, PREDICATE)")
        conn.commit()
        conn.close()
        monkeypatch.setenv("SEMMEDDB_PATH", str(path))
        a = SemMedDBAdapter(LookupConfig())
        assert a.is_available() is True  # file exists...
        assert await a.search_concepts("fatigue") == []  # ...but is unusable
        assert await a._resolve_db() is None

    @pytest.mark.asyncio
    async def test_unrelated_file_is_rejected(self, tmp_path, monkeypatch):
        path = tmp_path / "notes.bin"
        path.write_bytes(b"hello")
        monkeypatch.setenv("SEMMEDDB_PATH", str(path))
        assert await SemMedDBAdapter(LookupConfig())._resolve_db() is None

    @pytest.mark.asyncio
    async def test_corrupt_sqlite_is_rejected(self, tmp_path, monkeypatch):
        path = tmp_path / "corrupt.sqlite"
        path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
        monkeypatch.setenv("SEMMEDDB_PATH", str(path))
        assert await SemMedDBAdapter(LookupConfig())._resolve_db() is None

    @pytest.mark.asyncio
    async def test_resolved_db_is_cached(self, adapter):
        first = await adapter._resolve_db()
        assert await adapter._resolve_db() == first


class TestExportImport:
    def _rows_as_text(self, delimiter, header):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
        if header:
            writer.writerow(PREDICATION_COLUMNS)
        for i, (pmid, pred, scui, sname, sty, ocui, oname, oty) in enumerate(TRIPLES, 1):
            writer.writerow([i, i, pmid, pred, scui, sname, sty, 1, ocui, oname, oty, "\\N"])
        return buffer.getvalue()

    def test_import_tsv_with_header(self, tmp_path):
        src = tmp_path / "pred.tsv"
        src.write_text(self._rows_as_text("\t", True))
        dest = tmp_path / "out.sqlite"
        assert import_predication_export(src, dest) == len(TRIPLES)
        conn = sqlite3.connect(dest)
        assert conn.execute("SELECT COUNT(*) FROM PREDICATION").fetchone()[0] == len(TRIPLES)
        assert conn.execute("SELECT OBJECT_NOVELTY FROM PREDICATION LIMIT 1").fetchone() == (None,)
        names = {r[1] for r in conn.execute("PRAGMA index_list(PREDICATION)")}
        assert {"idx_pred_subject_cui", "idx_pred_object_cui"} <= names
        conn.close()
        assert not (tmp_path / "out.sqlite.part").exists()

    def test_import_headerless_gz_csv_skips_bad_lines(self, tmp_path):
        text = self._rows_as_text(",", False) + "garbled,line\n"
        src = tmp_path / "pred.csv.gz"
        with gzip.open(src, "wt", encoding="utf-8") as handle:
            handle.write(text)
        dest = tmp_path / "out.sqlite"
        assert import_predication_export(src, dest) == len(TRIPLES)

    def test_import_flushes_in_batches(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "_IMPORT_BATCH", 5)
        src = tmp_path / "pred.tsv"
        src.write_text(self._rows_as_text("\t", True))
        assert import_predication_export(src, tmp_path / "out.sqlite") == len(TRIPLES)

    def test_sqlite_sniffing_and_row_grouping_helpers(self, tmp_path):
        assert mod._is_sqlite_file(tmp_path / "missing") is False
        rows = [(None, "x", "dsyn", "s", 1, 1), ("C1", None, "dsyn", "s", 1, 1)]
        assert SemMedDBAdapter._group_rows(rows) == {}

    def test_import_errors_leave_no_database(self, tmp_path):
        empty = tmp_path / "empty.tsv"
        empty.write_text("")
        with pytest.raises(ValueError, match="empty"):
            import_predication_export(empty, tmp_path / "a.sqlite")
        bad = tmp_path / "bad.tsv"
        bad.write_text("PMID\tPREDICATE\n1\tTREATS\n")
        with pytest.raises(ValueError, match="required"):
            import_predication_export(bad, tmp_path / "b.sqlite")
        assert not list(tmp_path.glob("*.sqlite*"))

    @pytest.mark.asyncio
    async def test_adapter_imports_export_lazily_into_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / "cache"
        monkeypatch.setenv("KNOWLEDGE_LOOKUP_DATA_DIR", str(cache))
        src = tmp_path / "pred.tsv"
        src.write_text(self._rows_as_text("\t", True))
        monkeypatch.setenv("SEMMEDDB_PATH", str(src))
        a = SemMedDBAdapter(LookupConfig())
        assert a.is_available() is True
        assert not cache.exists()  # nothing imported at construction time
        concepts = await a.search_concepts("rituximab")
        assert [c.primary_id for c in concepts] == [RITUX]
        built = list(cache.glob("semmeddb_*.sqlite"))
        assert len(built) == 1
        # a second adapter reuses the imported file instead of re-importing
        mtime = built[0].stat().st_mtime_ns
        b = SemMedDBAdapter(LookupConfig())
        assert (await b.get_concept_details(HYDRO)).primary_label == "Hydrocortisone"
        assert built[0].stat().st_mtime_ns == mtime
