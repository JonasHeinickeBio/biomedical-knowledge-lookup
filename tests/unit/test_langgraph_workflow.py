"""Tests for the LangGraph agent workflow."""

from __future__ import annotations

import asyncio
import json
import tempfile

from knowledge_lookup.agents.graph import build_workflow_graph
from knowledge_lookup.agents.nodes import approval_node, export_node, review_node
from knowledge_lookup.agents.routing import (
    route_after_approval,
    route_after_refine,
    route_after_review,
)
from knowledge_lookup.agents.state import (
    LookupWorkflowState,
    dict_to_lookup_result,
    lookup_result_to_dict,
    make_step,
)
from knowledge_lookup.models import KnowledgeSource, LookupResult, UnifiedConcept
from langgraph.graph import END

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_concept(
    label: str,
    concept_id: str | None = None,
    confidence: float = 0.8,
    sources: list[KnowledgeSource] | None = None,
) -> UnifiedConcept:
    """Create a test UnifiedConcept."""
    return UnifiedConcept(
        primary_id=concept_id or f"http://test.org/{label.lower().replace(' ', '_')}",
        primary_label=label,
        confidence_score=confidence,
        sources=sources or [KnowledgeSource.OLS],
    )


def _make_lookup_result(
    query: str = "test query",
    concepts: list[UnifiedConcept] | None = None,
    sources_queried: list[KnowledgeSource] | None = None,
    sources_succeeded: list[KnowledgeSource] | None = None,
) -> LookupResult:
    """Create a test LookupResult."""
    result = LookupResult(query=query)
    result.concepts = concepts or []
    result.sources_queried = sources_queried or [KnowledgeSource.OLS, KnowledgeSource.UMLS]
    result.sources_succeeded = sources_succeeded or [KnowledgeSource.OLS]
    result.sources_failed = None
    return result


def _make_state(**overrides) -> LookupWorkflowState:
    """Create a test LookupWorkflowState with sensible defaults."""
    state: LookupWorkflowState = {
        "query": "test query",
        "max_results": 50,
        "source_filter": None,
        "concept_type_filter": None,
        "export_formats": ["json"],
        "export_path": None,
        "lookup_result": None,
        "review_score": None,
        "review_summary": None,
        "review_strengths": [],
        "review_weaknesses": [],
        "review_suggestions": [],
        "review_concept_map": [],
        "review_llm_explanation": None,
        "aggregated_context": None,
        "refinement_notes": [],
        "iteration": 0,
        "max_iterations": 3,
        "retry_count": 0,
        "auto_approve_threshold": 0.8,
        "status": "pending",
        "errors": [],
        "final_result": None,
        "export_paths": [],
        "steps": [],
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_lookup_result_roundtrip(self):
        result = _make_lookup_result(
            concepts=[_make_concept("insulin")],
        )
        d = lookup_result_to_dict(result)
        restored = dict_to_lookup_result(d)
        assert restored is not None
        assert restored.query == "test query"
        assert len(restored.concepts) == 1
        assert restored.concepts[0].primary_label == "insulin"

    def testdict_to_lookup_result_none(self):
        assert dict_to_lookup_result(None) is None

    def testmake_step(self):
        step = make_step("TestAgent", "test_action", "detail here", extra="value")
        assert step["agent"] == "TestAgent"
        assert step["action"] == "test_action"
        assert step["detail"] == "detail here"
        assert step["extra"] == "value"
        assert "timestamp" in step


# ---------------------------------------------------------------------------
# Review node tests
# ---------------------------------------------------------------------------


class TestReviewNode:
    def test_review_with_no_results(self):
        state = _make_state()
        result = asyncio.run(review_node(state))
        assert result["review_score"] == 0.0
        assert "No lookup results" in result["review_summary"]
        assert len(result["review_weaknesses"]) > 0

    def test_review_with_good_results(self):
        concepts = [_make_concept("concept1"), _make_concept("concept2")]
        lookup_result = _make_lookup_result(concepts=concepts)
        state = _make_state(
            lookup_result=lookup_result_to_dict(lookup_result),
        )
        result = asyncio.run(review_node(state))
        assert result["review_score"] > 0
        assert len(result["review_strengths"]) > 0

    def test_review_with_high_yield(self):
        concepts = [_make_concept(f"c{i}") for i in range(20)]
        lookup_result = _make_lookup_result(concepts=concepts)
        state = _make_state(
            lookup_result=lookup_result_to_dict(lookup_result),
            max_results=20,
        )
        result = asyncio.run(review_node(state))
        # Score should be high with many results from good sources
        assert result["review_score"] is not None
        assert result["review_score"] > 0.3

    def test_review_source_diversity(self):
        concepts = [
            _make_concept("c1", sources=[KnowledgeSource.OLS]),
            _make_concept("c2", sources=[KnowledgeSource.UMLS]),
            _make_concept("c3", sources=[KnowledgeSource.WIKIDATA]),
        ]
        lookup_result = _make_lookup_result(
            concepts=concepts,
            sources_succeeded=[
                KnowledgeSource.OLS,
                KnowledgeSource.UMLS,
                KnowledgeSource.WIKIDATA,
            ],
        )
        state = _make_state(lookup_result=lookup_result_to_dict(lookup_result))
        result = asyncio.run(review_node(state))
        # Multiple sources should give diversity bonus
        diversity_found = any("diversity" in s.lower() for s in result["review_strengths"])
        assert diversity_found


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


class TestRouting:
    def test_route_after_review_auto_approve(self):
        state = _make_state(review_score=0.9, auto_approve_threshold=0.8, iteration=1)
        assert route_after_review(state) == "prune"

    def test_route_after_review_needs_approval(self):
        state = _make_state(review_score=0.5, auto_approve_threshold=0.8, iteration=1)
        assert route_after_review(state) == "approval"

    def test_route_after_review_max_iterations(self):
        state = _make_state(review_score=0.3, iteration=3, max_iterations=3)
        assert route_after_review(state) == "prune"

    def test_route_after_approval_approved(self):
        state = _make_state(status="exporting")
        assert route_after_approval(state) == "prune"

    def test_route_after_approval_refine(self):
        state = _make_state(status="refining")
        assert route_after_approval(state) == "refine"

    def test_route_after_approval_rejected(self):
        state = _make_state(status="completed")
        assert route_after_approval(state) == END

    def test_route_after_refine_continues(self):
        state = _make_state(status="searching", iteration=1, max_iterations=3)
        assert route_after_refine(state) == "lookup"

    def test_route_after_refine_max_iterations(self):
        state = _make_state(status="searching", iteration=3, max_iterations=3)
        assert route_after_refine(state) == "prune"


# ---------------------------------------------------------------------------
# Export node tests
# ---------------------------------------------------------------------------


class TestExportNode:
    def test_export_no_results(self):
        state = _make_state()
        result = asyncio.run(export_node(state))
        assert result["status"] == "completed"
        assert result["export_paths"] == []

    def test_export_json(self):
        concepts = [_make_concept("test concept")]
        lookup_result = _make_lookup_result(concepts=concepts)
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(
                final_result=lookup_result_to_dict(lookup_result),
                export_formats=["json"],
                export_path=tmpdir,
            )
            result = asyncio.run(export_node(state))
            assert result["status"] == "completed"
            assert len(result["export_paths"]) == 1
            assert result["export_paths"][0].endswith(".json")
            # Verify content
            with open(result["export_paths"][0]) as f:
                data = json.load(f)
            assert data["query"] == "test query"

    def test_export_csv(self):
        concepts = [_make_concept("concept1"), _make_concept("concept2")]
        lookup_result = _make_lookup_result(concepts=concepts)
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(
                final_result=lookup_result_to_dict(lookup_result),
                export_formats=["csv"],
                export_path=tmpdir,
            )
            result = asyncio.run(export_node(state))
            assert result["status"] == "completed"
            assert len(result["export_paths"]) == 1
            assert result["export_paths"][0].endswith(".csv")


# ---------------------------------------------------------------------------
# Graph construction tests
# ---------------------------------------------------------------------------


class TestGraphConstruction:
    def test_build_graph(self):
        graph = build_workflow_graph()
        # Compiled graph should have nodes
        assert hasattr(graph, "nodes") or hasattr(graph, "get_graph")

    def test_build_graph_with_checkpointer(self):
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()
        graph = build_workflow_graph(checkpointer=checkpointer)
        assert graph is not None


# ---------------------------------------------------------------------------
# Approval node tests (with mock interrupt)
# ---------------------------------------------------------------------------


class TestApprovalNode:
    def test_approval_node_presents_review(self):
        """Test that approval_node uses interrupt to present results."""
        from unittest.mock import patch

        lookup_result = _make_lookup_result(
            concepts=[_make_concept("insulin", confidence=0.9)],
        )
        state = _make_state(
            lookup_result=lookup_result_to_dict(lookup_result),
            review_score=0.85,
            review_summary="Good results",
            review_strengths=["High confidence"],
            review_weaknesses=[],
            review_suggestions=[],
            iteration=1,
        )

        # Mock interrupt to capture what's presented
        with patch("knowledge_lookup.agents.nodes.approval.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {"approved": True, "refine": False}
            result = approval_node(state)

            # Verify interrupt was called with proper payload
            mock_interrupt.assert_called_once()
            payload = mock_interrupt.call_args[0][0]
            assert payload["action"] == "approve_lookup_results"
            assert payload["query"] == "test query"
            assert len(payload["concept_preview"]) == 1
            assert result["status"] == "exporting"

    def test_approval_rejection(self):
        from unittest.mock import patch

        state = _make_state(
            lookup_result=lookup_result_to_dict(_make_lookup_result()),
        )

        with patch("knowledge_lookup.agents.nodes.approval.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {"approved": False, "refine": False}
            result = approval_node(state)
            assert result["status"] == "completed"
            assert result["final_result"] is None
