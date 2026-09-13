"""
Durable, queryable persistence for term-expansion runs.

Unlike ``cache/cache.py`` (LRU-evicting, TTL-expiring — the right tool for
speeding up repeat lookups), this store never evicts on its own: every term
discovered by :func:`knowledge_lookup.core.term_expansion.expand_and_search`
is written here permanently, so "what did we try for X, and why" stays
answerable long after any cache entry for the same query would have expired.

Follows the same SQLite pattern already established by
``knowledge_lookup.umls.cache.UMLSCache`` (WAL mode, one connection per
operation, thread-safe via a lock, ``~/.cache/knowledge-lookup/`` on disk).
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

_DEFAULT_DB_PATH = Path.home() / ".cache" / "knowledge-lookup" / "expansion_history.db"
_SCHEMA_VERSION = 1

# origin values recorded per discovered term
ORIGIN_ORIGINAL = "original"
ORIGIN_SYNONYM = "synonym"
ORIGIN_ABBREVIATION = "abbreviation"
ORIGIN_LONG_FORM = "long_form"

# stop_reason values recorded per finished run
STOP_MAX_ROUNDS = "max_rounds"
STOP_FIXED_POINT = "fixed_point"


class ExpansionStore:
    """SQLite-backed durable record of term-expansion runs.

    Parameters
    ----------
    db_path :
        Path to the SQLite database file. Created automatically (with
        parent directories) if it doesn't exist yet.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path or _DEFAULT_DB_PATH)
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_run(self, original_query: str) -> int:
        """Record the start of a new expansion run; returns its run id."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO expansion_runs (original_query, started_at) VALUES (?, ?)",
                    (original_query, _now()),
                )
                conn.commit()
                assert cur.lastrowid is not None  # noqa: S101 - INSERT always assigns a rowid
                return cur.lastrowid
            finally:
                conn.close()

    def record_terms(
        self, run_id: int, round_num: int, terms: list[tuple[str, str, str | None]]
    ) -> None:
        """Record terms discovered in one round.

        Parameters
        ----------
        run_id :
            The run id returned by :meth:`start_run`.
        round_num :
            0 for the original query's round, 1+ for each expansion round.
        terms :
            ``(term, origin, origin_concept_id)`` tuples, where *origin* is
            one of ``ORIGIN_ORIGINAL`` / ``ORIGIN_SYNONYM`` /
            ``ORIGIN_ABBREVIATION`` / ``ORIGIN_LONG_FORM``, and
            *origin_concept_id* is the concept the term was harvested from
            (``None`` for the original query itself).
        """
        if not terms:
            return
        with self._lock:
            conn = self._connect()
            try:
                conn.executemany(
                    "INSERT INTO expansion_terms "
                    "(run_id, round, term, origin, origin_concept_id, discovered_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (run_id, round_num, term, origin, origin_concept_id, _now())
                        for term, origin, origin_concept_id in terms
                    ],
                )
                conn.commit()
            finally:
                conn.close()

    def finish_run(self, run_id: int, rounds_run: int, stop_reason: str) -> None:
        """Mark a run complete.

        ``stop_reason`` is ``STOP_MAX_ROUNDS`` or ``STOP_FIXED_POINT``.
        """
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE expansion_runs SET completed_at = ?, rounds_run = ?, "
                    "stop_reason = ? WHERE id = ?",
                    (_now(), rounds_run, stop_reason, run_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        """Fetch one run's metadata."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT id, original_query, started_at, completed_at, rounds_run, "
                    "stop_reason FROM expansion_runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def get_terms(self, run_id: int) -> list[dict[str, Any]]:
        """Fetch every term discovered during a run, in round order."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT round, term, origin, origin_concept_id, discovered_at "
                    "FROM expansion_terms WHERE run_id = ? ORDER BY round, id",
                    (run_id,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def find_runs_for_query(self, original_query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Find past runs for the same original query (most recent first)."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, original_query, started_at, completed_at, rounds_run, "
                    "stop_reason FROM expansion_runs WHERE original_query = ? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (original_query, limit),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                f"""
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;

                CREATE TABLE IF NOT EXISTS expansion_runs (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_query TEXT NOT NULL,
                    started_at     TEXT NOT NULL,
                    completed_at   TEXT,
                    rounds_run     INTEGER,
                    stop_reason    TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_runs_query ON expansion_runs(original_query);

                CREATE TABLE IF NOT EXISTS expansion_terms (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id             INTEGER NOT NULL REFERENCES expansion_runs(id),
                    round              INTEGER NOT NULL,
                    term               TEXT NOT NULL,
                    origin             TEXT NOT NULL,
                    origin_concept_id  TEXT,
                    discovered_at      TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_terms_run ON expansion_terms(run_id);

                CREATE TABLE IF NOT EXISTS _meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
                INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', '{_SCHEMA_VERSION}');
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn


def _now() -> str:
    return datetime.now().isoformat()
