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


class TestRelationshipEdges:
    """The schema-version-2 ``relationship_edges`` table: durable, per-run,
    round-ordered, and recording nameless (unsearchable) edges too."""

    def test_record_and_get_edges_round_trip(self, store):
        run_id = store.start_run("tp53")
        store.record_relationship_edges(
            run_id,
            0,
            [
                {
                    "source_concept_id": "KEGG:hsa:7157",
                    "source_concept_label": "TP53",
                    "relation_label": "gene_pathway",
                    "related_id": "path:hsa04110",
                    "related_name": "Cell cycle",
                    "related_source": "KEGG_PATHWAY",
                    "concept_type": "pathway",
                    "searched": True,
                }
            ],
        )
        store.finish_run(run_id, 1, STOP_FIXED_POINT)

        edges = store.get_relationship_edges(run_id)
        assert len(edges) == 1
        edge = edges[0]
        assert edge["round"] == 0
        assert edge["source_concept_id"] == "KEGG:hsa:7157"
        assert edge["relation_label"] == "gene_pathway"
        assert edge["related_id"] == "path:hsa04110"
        assert edge["related_name"] == "Cell cycle"
        assert edge["concept_type"] == "pathway"
        assert edge["searched"] == 1

    def test_nameless_edge_recorded_as_unsearched(self, store):
        """KEGG ``link`` yields a bare accession with no name; it is still
        stored, just flagged ``searched`` false with a null name."""
        run_id = store.start_run("tp53")
        store.record_relationship_edges(
            run_id,
            0,
            [
                {
                    "source_concept_id": "KEGG:hsa:7157",
                    "source_concept_label": "TP53",
                    "relation_label": "gene_pathway",
                    "related_id": "path:hsa04110",
                    "related_name": None,
                    "related_source": "KEGG_PATHWAY",
                    "concept_type": "pathway",
                    "searched": False,
                }
            ],
        )
        edges = store.get_relationship_edges(run_id)
        assert edges[0]["related_name"] is None
        assert edges[0]["searched"] == 0

    def test_edges_ordered_by_round_then_insertion(self, store):
        run_id = store.start_run("q")
        store.record_relationship_edges(
            run_id,
            1,
            [
                {
                    "source_concept_id": "c1",
                    "relation_label": "r",
                    "related_id": "second",
                    "searched": False,
                }
            ],
        )
        store.record_relationship_edges(
            run_id,
            0,
            [
                {
                    "source_concept_id": "c0",
                    "relation_label": "r",
                    "related_id": "first",
                    "searched": False,
                }
            ],
        )
        edges = store.get_relationship_edges(run_id)
        assert [e["related_id"] for e in edges] == ["first", "second"]
        assert [e["round"] for e in edges] == [0, 1]

    def test_edges_scoped_to_run(self, store):
        run_a = store.start_run("a")
        run_b = store.start_run("b")
        store.record_relationship_edges(
            run_a,
            0,
            [{"source_concept_id": "x", "relation_label": "r", "related_id": "only-a"}],
        )
        assert store.get_relationship_edges(run_b) == []
        assert len(store.get_relationship_edges(run_a)) == 1

    def test_empty_edge_list_is_noop(self, store):
        run_id = store.start_run("q")
        store.record_relationship_edges(run_id, 0, [])
        assert store.get_relationship_edges(run_id) == []

    def test_edges_durable_across_reopen(self, tmp_path):
        db = tmp_path / "rel.db"
        s1 = ExpansionStore(db)
        run_id = s1.start_run("tp53")
        s1.record_relationship_edges(
            run_id,
            0,
            [{"source_concept_id": "c", "relation_label": "r", "related_id": "path:hsa04110"}],
        )
        del s1
        s2 = ExpansionStore(db)
        assert len(s2.get_relationship_edges(run_id)) == 1
