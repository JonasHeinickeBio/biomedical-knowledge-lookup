"""Unit tests for ExpansionStore — durable, queryable term-expansion history."""

from __future__ import annotations

import pytest
from knowledge_lookup.core.expansion_store import (
    ORIGIN_ORIGINAL,
    ORIGIN_SYNONYM,
    STOP_FIXED_POINT,
    ExpansionStore,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path) -> ExpansionStore:
    return ExpansionStore(tmp_path / "expansion_history.db")


class TestExpansionStore:
    def test_start_run_returns_incrementing_ids(self, store):
        run1 = store.start_run("diabetes")
        run2 = store.start_run("hypertension")
        assert run1 != run2
        assert run2 > run1

    def test_record_and_get_terms(self, store):
        run_id = store.start_run("copd")
        store.record_terms(run_id, 0, [("copd", ORIGIN_ORIGINAL, None)])
        store.record_terms(
            run_id,
            1,
            [
                ("chronic obstructive pulmonary disease", ORIGIN_SYNONYM, "C0024117"),
                ("emphysema", ORIGIN_SYNONYM, "C0024117"),
            ],
        )

        terms = store.get_terms(run_id)
        assert [t["term"] for t in terms] == [
            "copd",
            "chronic obstructive pulmonary disease",
            "emphysema",
        ]
        assert terms[0]["round"] == 0
        assert terms[0]["origin"] == ORIGIN_ORIGINAL
        assert terms[0]["origin_concept_id"] is None
        assert terms[1]["round"] == 1
        assert terms[1]["origin_concept_id"] == "C0024117"

    def test_record_terms_with_empty_list_is_a_noop(self, store):
        run_id = store.start_run("x")
        store.record_terms(run_id, 0, [])
        assert store.get_terms(run_id) == []

    def test_finish_run_updates_metadata(self, store):
        run_id = store.start_run("asthma")
        store.finish_run(run_id, rounds_run=2, stop_reason=STOP_FIXED_POINT)

        run = store.get_run(run_id)
        assert run is not None
        assert run["rounds_run"] == 2
        assert run["stop_reason"] == STOP_FIXED_POINT
        assert run["completed_at"] is not None

    def test_get_run_missing_id_returns_none(self, store):
        assert store.get_run(999999) is None

    def test_find_runs_for_query_most_recent_first(self, store):
        first = store.start_run("mi")
        store.finish_run(first, 1, STOP_FIXED_POINT)
        second = store.start_run("mi")
        store.finish_run(second, 1, STOP_FIXED_POINT)
        store.start_run("unrelated query")

        runs = store.find_runs_for_query("mi")
        assert [r["id"] for r in runs] == [second, first]

    def test_durable_across_reopen(self, tmp_path):
        """The whole point of this store over the evictable cache: data
        survives a fresh instantiation against the same file, not just the
        lifetime of one ExpansionStore object."""
        db_path = tmp_path / "durable.db"
        store1 = ExpansionStore(db_path)
        run_id = store1.start_run("persistent term")
        store1.record_terms(run_id, 0, [("persistent term", ORIGIN_ORIGINAL, None)])
        store1.finish_run(run_id, 1, STOP_FIXED_POINT)
        del store1

        store2 = ExpansionStore(db_path)
        run = store2.get_run(run_id)
        assert run is not None
        assert run["original_query"] == "persistent term"
        assert len(store2.get_terms(run_id)) == 1

    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "expansion.db"
        store = ExpansionStore(nested)
        assert nested.exists()
        run_id = store.start_run("q")
        assert store.get_run(run_id) is not None
