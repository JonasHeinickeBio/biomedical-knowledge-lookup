"""
SemMedDB Knowledge Source Adapter (local database)

SemMedDB holds subject-predicate-object "predications" that the SemRep NLP system
extracted from PubMed titles and abstracts (``Fatigue Syndrome, Chronic -ASSOCIATED_WITH->
Interleukin-6``), each tied to the PMID and sentence it came from. Concepts are UMLS CUIs.

There is **no public API**. The data is distributed by the NLM Lister Hill Center as a MySQL
dump and needs a free UMLS licence (https://www.nlm.nih.gov/research/umls/), and the full
PREDICATION table is large (on the order of 100 million rows). This adapter therefore reads
a *local, read-only* database that you build yourself (see ``docs/adapters/literature/
semmeddb_adapter.md`` for the recipe):

* ``SEMMEDDB_PATH`` (or ``config.api_keys['semmeddb']`` - a *file path*, not a secret) points
  to an SQLite database with a ``PREDICATION`` table. Build it once, offline, from NLM's
  download with ``knowledge-lookup semmeddb-build semmedVER43_2024_R_PREDICATION.sql.gz -o
  semmeddb.sqlite`` (MySQL dump, or the ``.csv.gz`` export; see ``_semmeddb_build``).
* A *small* TSV/CSV/SQL export may also be given directly; it is imported on first use into an
  indexed SQLite file in the dataset cache directory. Anything larger than
  :data:`MAX_LAZY_IMPORT_BYTES` (the full table is ~130 million rows) is refused with a
  pointer to the builder, because importing it would block a lookup for hours.
* ``is_available()`` is true only when a usable database (or importable small export) exists,
  so ``CentralKnowledgeLookup`` skips the source on machines without the data.

Schema (checked against the official SemMedDB database details page, lhncbc.nlm.nih.gov):
``PREDICATION(PREDICATION_ID, SENTENCE_ID, PMID, PREDICATE, SUBJECT_CUI, SUBJECT_NAME,
SUBJECT_SEMTYPE, SUBJECT_NOVELTY, OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE, OBJECT_NOVELTY)``.
Only the columns up to ``OBJECT_SEMTYPE`` (minus the novelty flags) are required.

Safety: the database is opened read-only (``mode=ro`` URI plus ``PRAGMA query_only``), all
SQL is parameterised, ``LIKE`` patterns are escaped, and each query is aborted after
``query_timeout`` seconds so an un-indexed substring search over a huge table cannot hang a
worker thread. SemMedDB output is machine-extracted (SemRep precision is roughly 70-80%
per predication), so treat counts as evidence strength, not as curated fact.
"""

import asyncio
import hashlib
import logging
import os
import re
import sqlite3
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, UnifiedConcept
from ._semmeddb_build import (
    PREDICATION_COLUMNS,  # noqa: F401  (re-exported for callers and tests)
    REQUIRED_COLUMNS,
    build_predication_db,
    create_indexes,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

SEMMEDDB_PATH_ENV = "SEMMEDDB_PATH"

_SQLITE_MAGIC = b"SQLite format 3\x00"
_CUI_RE = re.compile(r"^(?:UMLS:|CUI:|UMLS_CUI:)?(C\d{7})$", re.IGNORECASE)
_EXPORT_SUFFIXES = {".tsv", ".csv", ".txt", ".gz", ".sql"}
#: Largest export that is imported lazily on first use. Bigger files must be converted with
#: ``knowledge-lookup semmeddb-build`` (the full PREDICATION table takes hours to load).
MAX_LAZY_IMPORT_BYTES = 256 * 1024 * 1024
#: Without the CONCEPT table a ``%text%`` name search scans the whole PREDICATION table (twice).
#: That is only attempted on databases up to this many rows; bigger ones need the lookup tables
#: built by ``knowledge-lookup semmeddb-build`` (the default).
SUBSTRING_SCAN_MAX_ROWS = 5_000_000

#: UMLS semantic type abbreviations (as stored in SemMedDB) -> library concept types.
#: Unlisted types map to UNKNOWN; the abbreviation is always kept in ``semantic_types``.
_SEMTYPE_MAP: dict[str, ConceptType] = {
    **dict.fromkeys(
        ["dsyn", "neop", "mobd", "cgab", "acab", "anab", "comd", "emod", "inpo", "patf"],
        ConceptType.DISEASE,
    ),
    **dict.fromkeys(["sosy", "fndg"], ConceptType.SYMPTOM),
    **dict.fromkeys(["gngm", "gene"], ConceptType.GENE),
    **dict.fromkeys(["aapp", "enzy", "rcpt", "imft", "prot"], ConceptType.PROTEIN),
    **dict.fromkeys(["phsu", "clnd", "antb", "vita"], ConceptType.DRUG),
    **dict.fromkeys(
        ["orch", "inch", "chem", "elii", "nsba", "hops", "strd", "horm", "bacs", "carb", "lipd"],
        ConceptType.CHEMICAL,
    ),
    **dict.fromkeys(["celc", "cell"], ConceptType.CELL_TYPE),
    **dict.fromkeys(
        ["bpoc", "blor", "bsoj", "anst", "bdsu", "ffas"], ConceptType.ANATOMICAL_ENTITY
    ),
    "tisu": ConceptType.TISSUE,
    **dict.fromkeys(["topp", "diap", "lbpr", "hlca", "mbrt"], ConceptType.PROCEDURE),
    **dict.fromkeys(
        ["genf", "celf", "orgf", "ortf", "moft", "phsf"], ConceptType.BIOLOGICAL_PROCESS
    ),
    **dict.fromkeys(
        ["bact", "euka", "virs", "arch", "orgm", "humn", "mamm"], ConceptType.ORGANISM
    ),
}


def _escape_like(text: str) -> str:
    """Escape ``%``, ``_`` and the escape character itself for ``LIKE ... ESCAPE '\\'``."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _open_ro(path: Path) -> sqlite3.Connection:
    """Open ``path`` read-only. ``Path.as_uri`` percent-encodes odd characters in the path."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _is_sqlite_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(16) == _SQLITE_MAGIC
    except OSError:
        return False


def import_predication_export(source: Path, dest: Path) -> int:
    """Import a CSV/TSV/SQL export (optionally ``.gz``) of PREDICATION into a new SQLite file.

    Thin wrapper over :func:`~._semmeddb_build.build_predication_db`; returns the number of
    rows imported. Prefer ``knowledge-lookup semmeddb-build`` for full-size files.
    """
    return build_predication_db([source], dest, overwrite=True).rows


def _create_indexes(conn: sqlite3.Connection) -> None:
    """Kept for backwards compatibility; see :func:`~._semmeddb_build.create_indexes`."""
    create_indexes(conn)


class SemMedDBAdapter(KnowledgeSourceAdapter):
    """Adapter for a local SemMedDB PREDICATION database (SQLite or TSV/CSV export)."""

    #: Seconds before a running query is aborted (guards against un-indexed full scans).
    query_timeout: float = 60.0
    #: Fall back to ``%text%`` name matching when prefix matching finds too few concepts.
    #: This cannot use an index and scans the whole table; disable for huge databases.
    allow_substring_search: bool = True

    def __init__(self, config):
        super().__init__(config)
        self._import_lock = asyncio.Lock()
        self._db_path: Path | None = None  # resolved SQLite file once validated

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.SEMMEDDB

    # ------------------------------------------------------------------
    # Location and availability
    # ------------------------------------------------------------------

    def _configured_path(self) -> Path | None:
        """Path from ``config.api_keys['semmeddb']`` (a file path) or ``SEMMEDDB_PATH``."""
        raw = self.config.get_api_key("semmeddb") or os.getenv(SEMMEDDB_PATH_ENV)
        return Path(raw).expanduser() if raw else None

    def is_available(self) -> bool:
        path = self._configured_path()
        try:
            if path is None or not path.is_file():
                return False
            # A big export that has not been built yet cannot be used (see _resolve_db)
            return _is_sqlite_file(path) or self._importable(path)
        except OSError:
            return False

    @staticmethod
    def _cache_dest(export: Path) -> Path:
        from ..utils.dataset_cache import default_cache_dir

        stat = export.stat()
        tag = hashlib.sha1(f"{export.resolve()}|{stat.st_size}|{stat.st_mtime_ns}".encode())
        return default_cache_dir() / f"semmeddb_{tag.hexdigest()[:12]}.sqlite"

    def _importable(self, export: Path) -> bool:
        """An export can be used when it was imported before or is small enough to import now."""
        if export.suffix.lower() not in _EXPORT_SUFFIXES:
            return False
        return self._cache_dest(export).exists() or export.stat().st_size <= MAX_LAZY_IMPORT_BYTES

    async def _resolve_db(self) -> Path | None:
        """Return a validated SQLite file, importing a TSV/CSV export on first use."""
        if self._db_path is not None and self._db_path.is_file():
            return self._db_path
        path = self._configured_path()
        if path is None or not path.is_file():
            return None
        async with self._import_lock:
            db = path
            if not _is_sqlite_file(path):
                if path.suffix.lower() not in _EXPORT_SUFFIXES:
                    logger.error(
                        f"SemMedDB: {path} is neither an SQLite file nor a TSV/CSV/SQL export"
                    )
                    return None
                if not self._importable(path):
                    logger.error(
                        f"SemMedDB: {path} is too large to import on first use "
                        f"({path.stat().st_size / 1e6:.0f} MB). Build the database once with: "
                        f"knowledge-lookup semmeddb-build {path} -o semmeddb.sqlite "
                        f"and point {SEMMEDDB_PATH_ENV} at the result"
                    )
                    return None
                db = await asyncio.to_thread(self._ensure_imported, path)
            if not await asyncio.to_thread(self._validate, db):
                return None
            self._db_path = db
            return db

    @staticmethod
    def _ensure_imported(export: Path) -> Path:
        """Import ``export`` into the dataset cache dir, once per (path, size, mtime)."""
        dest = SemMedDBAdapter._cache_dest(export)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            logger.info(f"Importing SemMedDB export {export} -> {dest}")
            rows = import_predication_export(export, dest)
            logger.info(f"Imported {rows} SemMedDB predications")
        return dest

    @staticmethod
    def _validate(db: Path) -> bool:
        try:
            conn = _open_ro(db)
            try:
                columns = {r[1].upper() for r in conn.execute("PRAGMA table_info(PREDICATION)")}
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.error(f"SemMedDB: cannot open {db}: {e}")
            return False
        missing = REQUIRED_COLUMNS - columns
        if missing:
            logger.error(
                f"SemMedDB: {db} has no usable PREDICATION table (missing {sorted(missing)})"
            )
            return False
        return True

    async def _run(self, work: Callable[[sqlite3.Connection], T]) -> T | None:
        """Run ``work(conn)`` on a worker thread with a fresh read-only connection and a
        query deadline. Returns ``None`` when no database is available."""
        db = await self._resolve_db()
        if db is None:
            return None

        def task() -> T:
            conn = _open_ro(db)
            deadline = time.monotonic() + self.query_timeout
            conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 100_000)
            try:
                return work(conn)
            finally:
                conn.close()

        return await asyncio.to_thread(task)

    # ------------------------------------------------------------------
    # Interface methods
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search by UMLS CUI (``C0015674``, ``UMLS:C0015674``) or concept name.

        Names match case-insensitively by prefix first (fast with the recommended NOCASE
        name indexes), then by substring if ``allow_substring_search`` is set and fewer than
        ``limit`` concepts were found. Concepts are aggregated per CUI and ranked by
        predication count; the label is the CUI's most frequent name in the data.
        """
        text = (query or "").strip()
        if not text or limit <= 0:
            return []
        try:
            cui = self._normalize_cui(text)
            if cui:
                rows = await self._run(lambda c: self._rows_for_cui(c, cui))
            else:
                rows = await self._run(lambda c: self._rows_for_name(c, text, limit))
            if not rows:
                return []
            grouped = self._group_rows(rows)
            if not cui:
                lowered = text.lower()
                ordered = sorted(
                    grouped.items(),
                    key=lambda kv: (
                        not any(n.lower() == lowered for n in kv[1]["names"]),
                        -kv[1]["predications"],
                    ),
                )
            else:
                ordered = list(grouped.items())
            concepts = [self._build_concept(k, v) for k, v in ordered[:limit]]
            logger.info(f"SemMedDB search for '{query}' returned {len(concepts)} concepts")
            return concepts
        except Exception as e:
            logger.error(f"SemMedDB search failed for '{query}': {e}")
            return []

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """Get a concept by CUI with predication counts, other names and semantic types."""
        cui = self._normalize_cui(concept_id)
        if not cui:
            return None
        try:
            rows = await self._run(lambda c: self._rows_for_cui(c, cui))
            if not rows:
                return None
            grouped = self._group_rows(rows)
            return self._build_concept(cui, grouped[cui]) if cui in grouped else None
        except Exception as e:
            logger.error(f"SemMedDB get_concept_details failed for '{concept_id}': {e}")
            return None

    async def get_relationships(
        self,
        concept_id: str,
        limit: int = 50,
        predicates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return subject-predicate-object triples involving the concept, best-supported first.

        Triples are grouped by (predicate, other CUI) and ranked by the number of distinct
        supporting PMIDs (``pmid_count``; ``predication_count`` counts sentences). Both
        directions are returned: ``direction`` is ``outgoing`` when the concept is the
        subject and ``incoming`` when it is the object. ``relation_label`` is the SemMedDB
        predicate (``TREATS``, ``CAUSES``, ``ASSOCIATED_WITH``, ``INTERACTS_WITH``, ...);
        negated predications keep their ``NEG_`` prefix and carry ``negated=True``.
        ``predicates`` restricts to the given predicate names. ``limit`` caps the merged list.
        """
        cui = self._normalize_cui(concept_id)
        if not cui or limit <= 0:
            return []
        wanted = [p.strip().upper() for p in predicates or [] if p and p.strip()]
        try:
            rows = await self._run(lambda c: self._triple_rows(c, cui, limit, wanted))
            if not rows:
                return []
            relationships = [
                {
                    "relation_label": predicate,
                    "related_id": other_cui,
                    "related_name": other_name,
                    "source": "SemMedDB",
                    "direction": direction,
                    "related_semtype": semtype,
                    "pmid_count": pmids,
                    "predication_count": preds,
                    "negated": predicate.startswith("NEG_"),
                }
                for direction, predicate, other_cui, other_name, semtype, pmids, preds in rows
            ]
            relationships.sort(key=lambda r: (-r["pmid_count"], -r["predication_count"]))
            return relationships[:limit]
        except Exception as e:
            logger.warning(f"SemMedDB get_relationships failed for '{concept_id}': {e}")
            return []

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """SemMedDB concepts *are* UMLS CUIs; return the identity mapping to UMLS if the CUI
        occurs in the database (so downstream code can join with the UMLS adapter)."""
        cui = self._normalize_cui(concept_id)
        if not cui:
            return []
        try:
            exists = await self._run(lambda c: self._exists(c, cui))
            if not exists:
                return []
            return [
                {
                    "fromId": cui,
                    "toId": cui,
                    "fromSource": "SemMedDB",
                    "toSource": "UMLS",
                    "mappingType": "exact",
                    "confidence": 1.0,
                }
            ]
        except Exception as e:
            logger.warning(f"SemMedDB get_mappings failed for '{concept_id}': {e}")
            return []

    async def get_supporting_pmids(
        self,
        subject_cui: str,
        predicate: str,
        object_cui: str,
        limit: int = 20,
    ) -> list[str]:
        """Return PMIDs (newest first) supporting one subject-predicate-object triple.

        Intended for the evidence step: take a triple from :meth:`get_relationships` and
        fetch the literature behind it.
        """
        subject, obj = self._normalize_cui(subject_cui), self._normalize_cui(object_cui)
        if not subject or not obj or not predicate or limit <= 0:
            return []
        try:
            rows = await self._run(
                lambda c: c.execute(
                    "SELECT DISTINCT PMID FROM PREDICATION WHERE SUBJECT_CUI = ? "
                    "AND PREDICATE = ? AND OBJECT_CUI = ? ORDER BY CAST(PMID AS INTEGER) DESC "
                    "LIMIT ?",
                    (subject, predicate.strip().upper(), obj, limit),
                ).fetchall()
            )
            return [str(r[0]) for r in rows or [] if r[0] is not None]
        except Exception as e:
            logger.warning(f"SemMedDB get_supporting_pmids failed: {e}")
            return []

    # ------------------------------------------------------------------
    # SQL (all parameterised)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_cui(value: str) -> str | None:
        match = _CUI_RE.match((value or "").strip())
        return match.group(1).upper() if match else None

    @staticmethod
    def _has_table(conn: sqlite3.Connection, name: str) -> bool:
        """Whether the precomputed ``CONCEPT`` / ``TRIPLE`` lookup table exists."""
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
            ).fetchone()
            is not None
        )

    @classmethod
    def _exists(cls, conn: sqlite3.Connection, cui: str) -> bool:
        if cls._has_table(conn, "CONCEPT"):
            return (
                conn.execute("SELECT 1 FROM CONCEPT WHERE CUI = ? LIMIT 1", (cui,)).fetchone()
                is not None
            )
        row = conn.execute(
            "SELECT 1 FROM PREDICATION WHERE SUBJECT_CUI = ? "
            "UNION ALL SELECT 1 FROM PREDICATION WHERE OBJECT_CUI = ? LIMIT 1",
            (cui, cui),
        ).fetchone()
        return row is not None

    @classmethod
    def _rows_for_cui(cls, conn: sqlite3.Connection, cui: str) -> list[tuple]:
        """(cui, name, semtype, side, predications, pmids) per name/semtype of one CUI."""
        if cls._has_table(conn, "CONCEPT"):
            return conn.execute(
                "SELECT CUI, NAME, SEMTYPE, SIDE, N, P FROM CONCEPT WHERE CUI = ?", (cui,)
            ).fetchall()
        return conn.execute(
            "SELECT SUBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE, 's', COUNT(*), "
            "COUNT(DISTINCT PMID) FROM PREDICATION WHERE SUBJECT_CUI = ? "
            "GROUP BY SUBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE "
            "UNION ALL "
            "SELECT OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE, 'o', COUNT(*), "
            "COUNT(DISTINCT PMID) FROM PREDICATION WHERE OBJECT_CUI = ? "
            "GROUP BY OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE",
            (cui, cui),
        ).fetchall()

    def _rows_for_name(self, conn: sqlite3.Connection, text: str, limit: int) -> list[tuple]:
        """Name search: prefix match, then (when cheap enough) substring match."""
        patterns = [f"{_escape_like(text)}%"]
        if self.allow_substring_search and self._substring_search_is_cheap(conn):
            patterns.append(f"%{_escape_like(text)}%")
        use_concept = self._has_table(conn, "CONCEPT")
        rows: list[tuple] = []
        for pattern in patterns:
            if use_concept:
                rows = conn.execute(
                    "SELECT CUI, NAME, SEMTYPE, SIDE, N, P FROM CONCEPT "
                    "WHERE NAME LIKE ? ESCAPE '\\' ORDER BY N DESC LIMIT ?",
                    (pattern, limit * 10),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT cui, name, semtype, side, SUM(n), SUM(p) FROM ("
                    "SELECT SUBJECT_CUI AS cui, SUBJECT_NAME AS name, SUBJECT_SEMTYPE AS "
                    "semtype, 's' AS side, COUNT(*) AS n, COUNT(DISTINCT PMID) AS p "
                    "FROM PREDICATION WHERE SUBJECT_NAME LIKE ? ESCAPE '\\' "
                    "GROUP BY SUBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE "
                    "UNION ALL "
                    "SELECT OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE, 'o', COUNT(*), "
                    "COUNT(DISTINCT PMID) FROM PREDICATION WHERE OBJECT_NAME LIKE ? "
                    "ESCAPE '\\' GROUP BY OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE) "
                    "GROUP BY cui, name, semtype, side ORDER BY SUM(n) DESC LIMIT ?",
                    (pattern, pattern, limit * 10),
                ).fetchall()
            if len({r[0] for r in rows}) >= limit:
                break
        return rows

    @classmethod
    def _substring_search_is_cheap(cls, conn: sqlite3.Connection) -> bool:
        """A ``%text%`` search is cheap on the CONCEPT table and on small databases only."""
        if cls._has_table(conn, "CONCEPT"):
            return True
        (biggest,) = conn.execute("SELECT MAX(rowid) FROM PREDICATION").fetchone()
        return (biggest or 0) <= SUBSTRING_SCAN_MAX_ROWS

    @staticmethod
    def _triple_rows(
        conn: sqlite3.Connection, cui: str, limit: int, predicates: list[str]
    ) -> list[tuple]:
        """Top ``limit`` triples per direction as
        (direction, predicate, other_cui, other_name, other_semtype, pmids, predications)."""
        pred_sql = ""
        extra: tuple[str, ...] = ()
        if predicates:
            pred_sql = f" AND PREDICATE IN ({','.join('?' * len(predicates))})"
            extra = tuple(predicates)
        rows: list[tuple] = []
        if SemMedDBAdapter._has_table(conn, "TRIPLE"):
            for direction, own, other_cui, other_name, other_type in (
                ("outgoing", "SUBJECT_CUI", "OBJECT_CUI", "OBJECT_NAME", "OBJECT_SEMTYPE"),
                ("incoming", "OBJECT_CUI", "SUBJECT_CUI", "SUBJECT_NAME", "SUBJECT_SEMTYPE"),
            ):
                rows.extend(
                    (direction, *r)
                    for r in conn.execute(
                        f"SELECT PREDICATE, {other_cui}, {other_name}, {other_type}, PMIDS, "
                        f"PREDS FROM TRIPLE WHERE {own} = ?{pred_sql} "
                        f"ORDER BY PMIDS DESC, PREDS DESC LIMIT ?",
                        (cui, *extra, limit),
                    )
                )
            return rows
        for direction, own, other_cui, other_name, other_type in (
            ("outgoing", "SUBJECT_CUI", "OBJECT_CUI", "OBJECT_NAME", "OBJECT_SEMTYPE"),
            ("incoming", "OBJECT_CUI", "SUBJECT_CUI", "SUBJECT_NAME", "SUBJECT_SEMTYPE"),
        ):
            rows.extend(
                (direction, *r)
                for r in conn.execute(
                    f"SELECT PREDICATE, {other_cui}, MIN({other_name}), MIN({other_type}), "
                    f"COUNT(DISTINCT PMID) AS pmids, COUNT(*) AS preds FROM PREDICATION "
                    f"WHERE {own} = ?{pred_sql} GROUP BY PREDICATE, {other_cui} "
                    f"ORDER BY pmids DESC, preds DESC LIMIT ?",
                    (cui, *extra, limit),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _group_rows(rows: list[tuple]) -> dict[str, dict[str, Any]]:
        """Aggregate (cui, name, semtype, side, preds, pmids) rows into per-CUI stats.

        ``pmids`` is summed over names/sides, so it can slightly over-count a PMID that
        supports the CUI in several roles; ``predications`` is exact.
        """
        grouped: dict[str, dict[str, Any]] = {}
        for cui, name, semtype, side, preds, pmids in rows:
            if not cui or not name:
                continue
            entry = grouped.setdefault(
                cui,
                {
                    "names": Counter(),
                    "semtypes": Counter(),
                    "predications": 0,
                    "as_subject": 0,
                    "as_object": 0,
                    "pmids": 0,
                },
            )
            entry["names"][name] += preds
            if semtype:
                entry["semtypes"][semtype] += preds
            entry["predications"] += preds
            entry["as_subject" if side == "s" else "as_object"] += preds
            entry["pmids"] += pmids
        return grouped

    def _build_concept(self, cui: str, stats: dict[str, Any]) -> UnifiedConcept:
        names: Counter = stats["names"]
        semtypes: Counter = stats["semtypes"]
        label = names.most_common(1)[0][0]
        top_semtype = semtypes.most_common(1)[0][0] if semtypes else None
        concept = self._create_concept(
            cui, label, _SEMTYPE_MAP.get((top_semtype or "").lower(), ConceptType.UNKNOWN)
        )
        if concept.synonyms is not None:
            concept.synonyms.extend(n for n, _ in names.most_common() if n != label)
        if concept.semantic_types is not None:
            concept.semantic_types.extend(s for s, _ in semtypes.most_common())
        concept.add_identifier(
            "UMLS", cui, label, f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}"
        )
        concept.confidence_score = 0.7  # machine-extracted (SemRep)
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.SEMMEDDB] = {
                "cui": cui,
                "predication_count": stats["predications"],
                "predications_as_subject": stats["as_subject"],
                "predications_as_object": stats["as_object"],
                "pmid_count": stats["pmids"],
                "names": dict(names),
                "semtypes": dict(semtypes),
            }
        return concept
