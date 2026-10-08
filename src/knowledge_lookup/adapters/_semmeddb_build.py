"""Build the SQLite database the SemMedDB adapter reads from NLM's downloads.

NLM distributes SemMedDB (VER43, the final release: 37.2 M citations, 130.5 M predications)
behind a free UTS login as MySQL dumps (``semmedVER43_2024_R_PREDICATION.sql.gz``) and as CSV
exports (``..._PREDICATION.csv.gz``). Neither is directly queryable without a MySQL server,
so this module streams one or more of those files into a single indexed SQLite file with a
``PREDICATION`` table, which :class:`~knowledge_lookup.adapters.semmeddb_adapter.
SemMedDBAdapter` then opens read-only.

Supported inputs (``.gz`` optional for all):

* **MySQL dump** (``.sql``): ``INSERT INTO `PREDICATION` VALUES (...),(...);`` statements as
  written by ``mysqldump`` (extended inserts, ``\\'`` and ``''`` quote escaping, ``NULL``,
  optional column lists, column order taken from ``CREATE TABLE``). Statements for other
  tables are ignored, so the whole dump of the database can be passed in.
* **CSV / TSV** (``.csv``, ``.tsv``, ``.txt``): with or without a header row; ``\\N`` and empty
  fields become NULL.

Everything is streamed: memory use does not depend on the file size. The output is written to
``<dest>.part`` and renamed when complete, so an interrupted build never leaves a half-built
database behind. Indexes are created after loading (much faster than maintaining them while
inserting).
"""

import csv
import gzip
import logging
import re
import sqlite3
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Canonical column order of the PREDICATION table (used when a file carries no column names).
PREDICATION_COLUMNS = (
    "PREDICATION_ID",
    "SENTENCE_ID",
    "PMID",
    "PREDICATE",
    "SUBJECT_CUI",
    "SUBJECT_NAME",
    "SUBJECT_SEMTYPE",
    "SUBJECT_NOVELTY",
    "OBJECT_CUI",
    "OBJECT_NAME",
    "OBJECT_SEMTYPE",
    "OBJECT_NOVELTY",
)
REQUIRED_COLUMNS = {
    "PMID",
    "PREDICATE",
    "SUBJECT_CUI",
    "SUBJECT_NAME",
    "SUBJECT_SEMTYPE",
    "OBJECT_CUI",
    "OBJECT_NAME",
    "OBJECT_SEMTYPE",
}

TABLE = "PREDICATION"
INSERT_BATCH = 100_000
PROGRESS_EVERY = 1_000_000
#: A build aborts when more than this fraction of rows is malformed (wrong CSV dialect, ...).
MAX_BAD_FRACTION = 0.005
_MIN_ROWS_FOR_BAD_CHECK = 1_000

Row = list[str | None]
ProgressCallback = Callable[[int, int], None]  # (rows loaded, rows skipped)


@dataclass
class BuildStats:
    rows: int = 0
    skipped: int = 0
    seconds: float = 0.0
    index_seconds: float = 0.0
    aggregate_seconds: float = 0.0


# ----------------------------------------------------------------------------------------
# MySQL dump parsing
# ----------------------------------------------------------------------------------------

_INSERT_RE = re.compile(
    r"^INSERT\s+(?:IGNORE\s+)?INTO\s+`?(\w+)`?\s*(\([^)]*\))?\s*VALUES\s*", re.IGNORECASE
)
_CREATE_RE = re.compile(r"^CREATE\s+TABLE\s+(?:IF NOT EXISTS\s+)?`?(\w+)`?\s*\(", re.IGNORECASE)
_COLUMN_DEF_RE = re.compile(r"^\s*`(\w+)`\s+\w+")
# One parenthesised tuple: quoted strings (with \x and '' escapes) or anything but ( ) '.
# Possessive quantifiers (Python 3.11+) consume whole runs without backtracking: about 4x
# faster than matching one character at a time, which matters for 130 million rows.
_TUPLE_RE = re.compile(r"\(((?:[^()']++|'(?:[^'\\]++|\\.|'')*+')*+)\)")
# One field inside a tuple: a quoted string (group 1) or an unquoted token (group 2)
_FIELD_RE = re.compile(r"'((?:[^'\\]++|\\.|'')*+)'|([^,]+)")
_ESCAPE_RE = re.compile(r"\\(.)|''", re.DOTALL)
_MYSQL_ESCAPES = {
    "0": "\0",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "b": "\b",
    "Z": "\x1a",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "%": "\\%",  # MySQL keeps the backslash for \% and \_ (they are LIKE wildcards)
    "_": "\\_",
}


def _unescape_sql(text: str) -> str:
    if "\\" not in text and "''" not in text:
        return text

    def repl(match: re.Match[str]) -> str:
        char = match.group(1)
        return "'" if char is None else _MYSQL_ESCAPES.get(char, char)

    return _ESCAPE_RE.sub(repl, text)


def _tuple_values(inner: str) -> Row:
    """Split the inside of one ``(...)`` tuple into Python values (``NULL`` -> ``None``).

    This runs once per row (130 million times for the full table), so plain fields stay on
    an inline fast path and only strings that really contain an escape call the unescaper.
    """
    values: Row = []
    append = values.append
    for quoted, bare in _FIELD_RE.findall(inner):
        if bare:
            append(None if bare == "NULL" else bare.strip())
        elif "\\" in quoted:
            append(_unescape_sql(quoted))
        elif "''" in quoted:
            append(quoted.replace("''", "'"))
        else:
            append(quoted)  # a plain quoted string (possibly empty)
    return values


def iter_mysql_dump(path: Path, table: str = TABLE) -> Iterator[tuple[list[str], Row]]:
    """Yield ``(column names, row)`` for every row of ``table`` in a ``mysqldump`` file.

    Column names come from an explicit ``INSERT INTO t (a, b) VALUES`` list if present, else
    from the table's ``CREATE TABLE`` statement, else the canonical PREDICATION order.
    """
    wanted = table.upper()
    created: list[str] | None = None
    in_create = False
    with _open_text(path) as handle:
        for line in handle:
            if in_create:
                column = _COLUMN_DEF_RE.match(line)
                if column:
                    assert created is not None
                    created.append(column.group(1).upper())
                elif line.lstrip().startswith(")"):
                    in_create = False
                continue
            if line.startswith("CREATE"):
                match = _CREATE_RE.match(line)
                if match and match.group(1).upper() == wanted:
                    created, in_create = [], True
                continue
            if not line.startswith("INSERT"):
                continue
            head = _INSERT_RE.match(line)
            if head is None or head.group(1).upper() != wanted:
                continue
            if head.group(2):
                columns = [c.strip(" `\t\n").upper() for c in head.group(2)[1:-1].split(",")]
            else:
                columns = created or []
            for tuple_match in _TUPLE_RE.finditer(line, head.end()):
                row = _tuple_values(tuple_match.group(1))
                yield (columns or list(PREDICATION_COLUMNS[: len(row)])), row


# ----------------------------------------------------------------------------------------
# CSV / TSV parsing
# ----------------------------------------------------------------------------------------


def iter_delimited(path: Path) -> Iterator[tuple[list[str], Row]]:
    """Yield ``(column names, row)`` from a CSV/TSV export (header optional)."""
    stem = path.name.lower().removesuffix(".gz")
    delimiter = "," if stem.endswith(".csv") else "\t"
    with _open_text(path) as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        first = next(reader, None)
        if first is None:
            raise ValueError(f"{path} is empty")
        names = [c.strip().upper() for c in first]
        rows: Iterator[list[str]]
        if "PREDICATE" in names:
            columns, rows = names, reader
        else:
            columns = list(PREDICATION_COLUMNS[: len(first)])
            rows = chain([first], reader)
        for fields in rows:
            yield columns, [None if v in ("\\N", "") else v for v in fields]


def _open_text(path: Path) -> Any:
    opener: Callable[..., Any] = gzip.open if path.suffix.lower() == ".gz" else open
    return opener(path, "rt", encoding="utf-8", errors="replace", newline="")


def detect_format(path: Path) -> str:
    """``"dump"`` for a MySQL dump, ``"delimited"`` for CSV/TSV."""
    stem = path.name.lower().removesuffix(".gz")
    if stem.endswith(".sql"):
        return "dump"
    if stem.endswith((".csv", ".tsv", ".txt")):
        return "delimited"
    with _open_text(path) as handle:  # unknown extension: sniff the first lines
        head = handle.read(4096)
    return (
        "dump"
        if re.search(r"^(INSERT INTO|CREATE TABLE|-- MySQL dump)", head, re.M)
        else ("delimited")
    )


# ----------------------------------------------------------------------------------------
# Building
# ----------------------------------------------------------------------------------------


def create_indexes(conn: sqlite3.Connection) -> None:
    """Indexes the adapter's queries rely on."""
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_pred_subject_cui ON PREDICATION (SUBJECT_CUI);
        CREATE INDEX IF NOT EXISTS idx_pred_object_cui ON PREDICATION (OBJECT_CUI);
        CREATE INDEX IF NOT EXISTS idx_pred_subject_name
            ON PREDICATION (SUBJECT_NAME COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_pred_object_name
            ON PREDICATION (OBJECT_NAME COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_pred_pmid ON PREDICATION (PMID);
        """
    )


def create_aggregates(conn: sqlite3.Connection) -> None:
    """Precompute the small tables that keep lookups fast on the full 130M-row table.

    * ``CONCEPT(CUI, NAME, SEMTYPE, SIDE, N, P)``: one row per concept name, semantic type
      and role (``s`` subject / ``o`` object) with its predication count ``N`` and distinct
      PMID count ``P``. Name search (prefix *and* substring), concept details and existence
      checks read this table instead of aggregating millions of PREDICATION rows.
    * ``TRIPLE(SUBJECT_CUI, PREDICATE, OBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE, OBJECT_NAME,
      OBJECT_SEMTYPE, PMIDS, PREDS)``: one row per distinct triple with its supporting PMID and
      sentence counts, indexed best-supported first so a hub concept's top relationships are
      an index range scan. Without it, a concept with millions of predications is aggregated
      on every call.
    * a composite (subject, object, predicate) index for the supporting-PMID lookup.
    """
    conn.executescript(
        """
        DROP TABLE IF EXISTS CONCEPT;
        CREATE TABLE CONCEPT AS
            SELECT SUBJECT_CUI AS CUI, SUBJECT_NAME AS NAME, SUBJECT_SEMTYPE AS SEMTYPE,
                   's' AS SIDE, COUNT(*) AS N, COUNT(DISTINCT PMID) AS P
            FROM PREDICATION GROUP BY SUBJECT_CUI, SUBJECT_NAME, SUBJECT_SEMTYPE
            UNION ALL
            SELECT OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE, 'o', COUNT(*), COUNT(DISTINCT PMID)
            FROM PREDICATION GROUP BY OBJECT_CUI, OBJECT_NAME, OBJECT_SEMTYPE;
        CREATE INDEX idx_concept_cui ON CONCEPT (CUI);
        CREATE INDEX idx_concept_name ON CONCEPT (NAME COLLATE NOCASE);

        DROP TABLE IF EXISTS TRIPLE;
        CREATE TABLE TRIPLE AS
            SELECT SUBJECT_CUI, PREDICATE, OBJECT_CUI,
                   MIN(SUBJECT_NAME) AS SUBJECT_NAME, MIN(SUBJECT_SEMTYPE) AS SUBJECT_SEMTYPE,
                   MIN(OBJECT_NAME) AS OBJECT_NAME, MIN(OBJECT_SEMTYPE) AS OBJECT_SEMTYPE,
                   COUNT(DISTINCT PMID) AS PMIDS, COUNT(*) AS PREDS
            FROM PREDICATION GROUP BY SUBJECT_CUI, PREDICATE, OBJECT_CUI;
        CREATE INDEX idx_triple_subject ON TRIPLE (SUBJECT_CUI, PMIDS DESC, PREDS DESC);
        CREATE INDEX idx_triple_object ON TRIPLE (OBJECT_CUI, PMIDS DESC, PREDS DESC);

        CREATE INDEX IF NOT EXISTS idx_pred_triple
            ON PREDICATION (SUBJECT_CUI, OBJECT_CUI, PREDICATE);
        """
    )


def build_predication_db(
    sources: Sequence[Path],
    dest: Path,
    *,
    overwrite: bool = False,
    progress: ProgressCallback | None = None,
    progress_every: int = PROGRESS_EVERY,
    max_rows: int | None = None,
    aggregates: bool = True,
) -> BuildStats:
    """Stream ``sources`` into a new SQLite file at ``dest`` and index it.

    ``max_rows`` stops after that many rows: a quick way to check on the first part of a
    huge download that the format is understood before committing to a build that takes hours.
    ``aggregates`` also precomputes the CONCEPT and TRIPLE tables (see
    :func:`create_aggregates`); skip them only for quick experiments, lookups on the full
    table are slow without them.

    Raises:
        FileExistsError: ``dest`` exists and ``overwrite`` is false.
        ValueError: a source has no PREDICATION rows, lacks required columns, or more than
            :data:`MAX_BAD_FRACTION` of its rows are malformed (usually the wrong CSV dialect).
    """
    if dest.exists() and not overwrite:
        raise FileExistsError(f"{dest} already exists (use overwrite)")
    if not sources:
        raise ValueError("no source files given")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    part.unlink(missing_ok=True)

    stats = BuildStats()
    started = time.monotonic()
    conn = sqlite3.connect(part)
    try:
        # Throw-away build database: durability is irrelevant, speed is not.
        conn.executescript(
            "PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; "
            "PRAGMA cache_size = -1000000; PRAGMA page_size = 8192;"
        )
        insert = ""
        columns: list[str] = []
        batch: list[Row] = []

        def flush() -> None:
            if batch:
                conn.executemany(insert, batch)
                stats.rows += len(batch)
                batch.clear()

        for source in sources:
            if max_rows is not None and stats.rows >= max_rows:
                break
            before = stats.rows
            rows_iter = (
                iter_mysql_dump(source)
                if detect_format(source) == "dump"
                else iter_delimited(source)
            )
            for names, row in rows_iter:
                if not columns:
                    columns = list(names)
                    missing = REQUIRED_COLUMNS - set(columns)
                    if missing:
                        raise ValueError(
                            f"{source} lacks required PREDICATION columns: {sorted(missing)}"
                        )
                    col_sql = ", ".join(f'"{c}"' for c in columns)
                    conn.execute(f"CREATE TABLE PREDICATION ({col_sql})")
                    insert = (
                        f"INSERT INTO PREDICATION ({col_sql}) "
                        f"VALUES ({','.join('?' * len(columns))})"
                    )
                if names != columns and len(row) == len(names):
                    # a later file with the same columns in another order: realign
                    lookup = dict(zip(names, row, strict=True))
                    row = [lookup.get(c) for c in columns]
                if len(row) != len(columns):
                    stats.skipped += 1  # truncated/garbled line: never abort a long build
                    continue
                batch.append(row)
                if max_rows is not None and stats.rows + len(batch) >= max_rows:
                    break
                if len(batch) >= INSERT_BATCH:
                    flush()
                    if progress and stats.rows % progress_every < INSERT_BATCH:
                        progress(stats.rows, stats.skipped)
            flush()
            if stats.rows == before:
                raise ValueError(f"{source} contains no {TABLE} rows")
        total = stats.rows + stats.skipped
        if total >= _MIN_ROWS_FOR_BAD_CHECK and stats.skipped / total > MAX_BAD_FRACTION:
            raise ValueError(
                f"{stats.skipped} of {total} rows were malformed; the file is probably not in "
                "the expected format (try the .sql.gz dump instead of a CSV export)"
            )
        if progress:
            progress(stats.rows, stats.skipped)
        indexing = time.monotonic()
        create_indexes(conn)
        conn.commit()
        stats.index_seconds = time.monotonic() - indexing
        if aggregates:
            aggregating = time.monotonic()
            create_aggregates(conn)
            conn.commit()
            stats.aggregate_seconds = time.monotonic() - aggregating
    except Exception:
        conn.close()
        part.unlink(missing_ok=True)
        raise
    conn.close()
    part.replace(dest)
    stats.seconds = time.monotonic() - started
    return stats
