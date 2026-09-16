"""Tests for the LangGraph agent workflow."""

from __future__ import annotations

import asyncio
import json
import tempfile

import pytest
from langgraph.graph import END

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

    def test_route_after_review_zero_max_iterations_is_not_default(self):
        """max_iterations=0 means no refinement rounds, not the default of 3."""
        state = _make_state(review_score=0.3, iteration=0, max_iterations=0)
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


# ---------------------------------------------------------------------------
# Expand node tests (term expansion is mocked — see test_term_expansion.py
# for the core expand_and_search logic itself)
# ---------------------------------------------------------------------------


class TestExpandNode:
    def test_expand_node_adds_discovered_terms(self):
        from unittest.mock import AsyncMock, patch

        from knowledge_lookup.agents.nodes.expand import expand_node
        from knowledge_lookup.core.term_expansion import ExpansionTrace

        state = _make_state(query="copd", expanded_search_terms=["copd"])
        trace = ExpansionTrace(
            run_id=1,
            rounds_run=2,
            stop_reason="fixed_point",
            terms_by_round=[["copd"], ["chronic obstructive pulmonary disease"]],
        )

        with (
            patch(
                "knowledge_lookup.agents.nodes.expand.expand_and_search",
                new=AsyncMock(return_value=(_make_lookup_result(), trace)),
            ),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as mock_ckl,
        ):
            mock_ckl.return_value.close = AsyncMock()
            result = asyncio.run(expand_node(state))

        assert result["expanded_search_terms"] == [
            "copd",
            "chronic obstructive pulmonary disease",
        ]
        assert len(result["steps"]) == 1
        assert result["steps"][0]["agent"] == "ExpandAgent"
        assert "1 new term" in result["steps"][0]["detail"]

    def test_expand_node_does_not_duplicate_existing_terms(self):
        from unittest.mock import AsyncMock, patch

        from knowledge_lookup.agents.nodes.expand import expand_node
        from knowledge_lookup.core.term_expansion import ExpansionTrace

        state = _make_state(
            query="diabetes",
            expanded_search_terms=["diabetes", "Diabetes"],  # preprocess variant, same term
        )
        trace = ExpansionTrace(
            run_id=1, rounds_run=1, stop_reason="fixed_point", terms_by_round=[["diabetes"]]
        )

        with (
            patch(
                "knowledge_lookup.agents.nodes.expand.expand_and_search",
                new=AsyncMock(return_value=(_make_lookup_result(), trace)),
            ),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as mock_ckl,
        ):
            mock_ckl.return_value.close = AsyncMock()
            result = asyncio.run(expand_node(state))

        assert result["expanded_search_terms"] == ["diabetes", "Diabetes"]
        assert "0 new term" in result["steps"][0]["detail"]

    def test_expand_node_falls_back_to_query_when_no_expanded_terms(self):
        from unittest.mock import AsyncMock, patch

        from knowledge_lookup.agents.nodes.expand import expand_node
        from knowledge_lookup.core.term_expansion import ExpansionTrace

        state = _make_state(query="aspirin", expanded_search_terms=[])
        trace = ExpansionTrace(
            run_id=None, rounds_run=1, stop_reason="fixed_point", terms_by_round=[["aspirin"]]
        )

        with (
            patch(
                "knowledge_lookup.agents.nodes.expand.expand_and_search",
                new=AsyncMock(return_value=(_make_lookup_result(), trace)),
            ),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as mock_ckl,
        ):
            mock_ckl.return_value.close = AsyncMock()
            result = asyncio.run(expand_node(state))

        assert result["expanded_search_terms"] == ["aspirin"]

    def test_expand_node_reports_error_without_raising(self):
        from unittest.mock import AsyncMock, patch

        from knowledge_lookup.agents.nodes.expand import expand_node

        state = _make_state(query="x", expanded_search_terms=["x"])

        with (
            patch(
                "knowledge_lookup.agents.nodes.expand.expand_and_search",
                new=AsyncMock(side_effect=RuntimeError("network down")),
            ),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as mock_ckl,
        ):
            mock_ckl.return_value.close = AsyncMock()
            result = asyncio.run(expand_node(state))

        assert "expanded_search_terms" not in result
        assert result["steps"][0]["action"] == "error"
        assert "network down" in result["steps"][0]["detail"]


# ---------------------------------------------------------------------------
# Runners: pause at the approval gate, then resume the same thread
# ---------------------------------------------------------------------------


_NO_LLM = {"backend": None, "api_key": None, "base_url": None, "model": None}


@pytest.fixture
def stub_network_nodes(monkeypatch):
    """Replace the graph's network nodes with deterministic stubs.

    The stubbed lookup returns one low-confidence concept, so the rule-based
    review scores it below the default auto-approve threshold (0.8) and the
    workflow pauses at the approval gate.
    """
    from knowledge_lookup.agents import graph as graph_module

    lookups: list[str] = []

    async def passthrough(state):
        return {"steps": [make_step("Stub", "noop")]}

    async def fake_lookup(state):
        lookups.append(state["query"])
        result = LookupResult(query=state["query"], sources_queried=[KnowledgeSource.HPO])
        result.add_concepts(
            [_make_concept("Seizure", "HP:0001250", 0.1, [KnowledgeSource.HPO])],
            KnowledgeSource.HPO,
        )
        return {
            "lookup_result": lookup_result_to_dict(result),
            "iteration": state["iteration"] + 1,
            "status": "searching",
            "steps": [make_step("Stub", "lookup")],
        }

    for name in ("expand_node", "detail_gather_node", "enrichment_node"):
        monkeypatch.setattr(graph_module, name, passthrough)
    monkeypatch.setattr(graph_module, "lookup_node", fake_lookup)
    monkeypatch.setattr(
        "knowledge_lookup.agents.nodes.review.load_llm_config", lambda: dict(_NO_LLM)
    )
    return lookups


class TestRunnersPauseResume:
    def test_run_workflow_reports_awaiting_approval(self, stub_network_nodes, tmp_path):
        from knowledge_lookup.agents.runners import run_workflow

        result = asyncio.run(run_workflow("seizure", export_path=str(tmp_path)))

        assert result["status"] == "awaiting_approval"
        assert result["approval_request"]["action"] == "approve_lookup_results"
        assert result["approval_request"]["query"] == "seizure"
        assert result["export_paths"] == []
        assert list(tmp_path.iterdir()) == []

    def test_resume_workflow_approves_the_paused_thread(self, stub_network_nodes, tmp_path):
        from knowledge_lookup.agents.runners import resume_workflow, run_workflow

        async def scenario():
            paused = await run_workflow("seizure", export_path=str(tmp_path))
            resumed = await resume_workflow(paused["thread_id"], {"approved": True})
            return paused, resumed

        paused, resumed = asyncio.run(scenario())

        assert paused["status"] == "awaiting_approval"
        assert resumed["thread_id"] == paused["thread_id"]
        assert resumed["status"] == "completed"
        assert resumed["approval_request"] is None
        assert len(resumed["export_paths"]) == 1
        assert resumed["export_paths"][0].startswith(str(tmp_path))
        assert any(s["action"] == "approved" for s in resumed["steps"])

    def test_refinement_pauses_again_then_rejection_stops(self, stub_network_nodes, tmp_path):
        from knowledge_lookup.agents.runners import resume_workflow, run_workflow

        async def scenario():
            paused = await run_workflow("seizure", export_path=str(tmp_path), max_iterations=3)
            refined = await resume_workflow(
                paused["thread_id"], {"approved": False, "refine": True, "notes": "focal"}
            )
            stopped = await resume_workflow(
                paused["thread_id"], {"approved": False, "refine": False}
            )
            return refined, stopped

        refined, stopped = asyncio.run(scenario())

        assert refined["status"] == "awaiting_approval"
        assert refined["iteration"] == 2
        assert len(stub_network_nodes) == 2  # searched again after refinement
        assert stopped["status"] == "completed"
        assert stopped["export_paths"] == []

    def test_resume_unknown_thread_raises(self, stub_network_nodes):
        from knowledge_lookup.agents.runners import resume_workflow

        with pytest.raises(ValueError, match="No workflow paused"):
            asyncio.run(resume_workflow("no-such-thread", {"approved": True}))

    def test_injected_checkpointer_is_used_for_resume(self, stub_network_nodes, tmp_path):
        from langgraph.checkpoint.memory import InMemorySaver

        from knowledge_lookup.agents.runners import resume_workflow, run_workflow

        saver = InMemorySaver()

        async def scenario():
            paused = await run_workflow("seizure", export_path=str(tmp_path), checkpointer=saver)
            with pytest.raises(ValueError):
                # not in the default checkpointer
                await resume_workflow(paused["thread_id"], {"approved": True})
            return await resume_workflow(
                paused["thread_id"], {"approved": True}, checkpointer=saver
            )

        assert asyncio.run(scenario())["status"] == "completed"

    def test_finished_run_is_dropped_from_default_checkpointer(self, stub_network_nodes, tmp_path):
        from knowledge_lookup.agents.runners import get_default_checkpointer, run_workflow

        result = asyncio.run(
            run_workflow("seizure", export_path=str(tmp_path), auto_approve_threshold=0.0)
        )

        assert result["status"] == "completed"
        config = {"configurable": {"thread_id": result["thread_id"]}}
        assert get_default_checkpointer().get_tuple(config) is None


# ---------------------------------------------------------------------------
# Runtime safeguards: time budgets, concurrency caps, source filter
# ---------------------------------------------------------------------------


def _slow_lookup_class(adapters):
    """A CentralKnowledgeLookup stand-in whose searches never finish in time."""
    from unittest.mock import AsyncMock, MagicMock

    async def slow_search(*args, **kwargs):
        await asyncio.sleep(30)

    instance = MagicMock()
    instance.adapters = dict.fromkeys(adapters, object())
    instance.search_concepts = slow_search
    instance.close = AsyncMock()
    return MagicMock(return_value=instance)


class TestLimits:
    def test_resolve_sources(self):
        from knowledge_lookup.agents.nodes._limits import resolve_sources

        assert resolve_sources(None) is None
        assert resolve_sources(["hpo", "GO", "bogus", "HPO"]) == [
            KnowledgeSource.HPO,
            KnowledgeSource.GENEONTOLOGY,
        ]

    def test_gather_bounded_cancels_at_deadline(self):
        import time

        from knowledge_lookup.agents.nodes._limits import gather_bounded

        async def fast():
            return "ok"

        async def slow():
            await asyncio.sleep(30)

        async def boom():
            raise RuntimeError("x")

        start = time.monotonic()
        results, unfinished = asyncio.run(gather_bounded([fast, slow, boom], timeout=0.2))

        assert time.monotonic() - start < 5
        assert results[0] == "ok"
        assert results[1] is None
        assert isinstance(results[2], RuntimeError)
        assert unfinished == 1

    def test_gather_bounded_caps_concurrency(self):
        from knowledge_lookup.agents.nodes._limits import gather_bounded

        running = 0
        peak = 0

        async def work():
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1

        results, unfinished = asyncio.run(gather_bounded([work] * 10, timeout=5, concurrency=3))

        assert unfinished == 0
        assert len(results) == 10
        assert peak == 3


class TestNodeSafeguards:
    def test_expand_node_searches_only_selected_sources(self):
        from unittest.mock import AsyncMock, patch

        from knowledge_lookup.agents.nodes.expand import expand_node
        from knowledge_lookup.core.term_expansion import ExpansionTrace

        trace = ExpansionTrace(
            run_id=1, rounds_run=1, stop_reason="fixed_point", terms_by_round=[["seizure"]]
        )
        expand = AsyncMock(return_value=(_make_lookup_result(), trace))
        state = _make_state(query="seizure", source_filter=["hpo"], max_results=7)

        with (
            patch("knowledge_lookup.agents.nodes.expand.expand_and_search", new=expand),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as mock_ckl,
        ):
            mock_ckl.return_value.close = AsyncMock()
            asyncio.run(expand_node(state))

        assert mock_ckl.call_args.kwargs["config"].enabled_sources == [KnowledgeSource.HPO]
        assert expand.call_args.kwargs["abbreviation_sources"] == []  # no UMLS calls
        assert expand.call_args.kwargs["max_results"] == 7

    def test_expand_node_times_out(self, monkeypatch):
        import time
        from unittest.mock import AsyncMock, patch

        from knowledge_lookup.agents.nodes.expand import expand_node

        async def never_finishes(*args, **kwargs):
            await asyncio.sleep(30)

        monkeypatch.setattr("knowledge_lookup.agents.nodes._limits.EXPAND_TIMEOUT", 0.2)
        state = _make_state(query="seizure", expanded_search_terms=["seizure"])

        start = time.monotonic()
        with (
            patch("knowledge_lookup.agents.nodes.expand.expand_and_search", new=never_finishes),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as mock_ckl,
        ):
            mock_ckl.return_value.close = AsyncMock()
            result = asyncio.run(expand_node(state))

        assert time.monotonic() - start < 5
        assert result["steps"][0]["action"] == "timeout"
        assert "expanded_search_terms" not in result

    def test_lookup_node_is_bounded_by_its_budget(self, monkeypatch):
        import time
        from unittest.mock import patch

        from knowledge_lookup.agents.nodes.lookup import lookup_node

        monkeypatch.setattr("knowledge_lookup.agents.nodes._limits.LOOKUP_TIMEOUT", 0.2)
        ckl = _slow_lookup_class([KnowledgeSource.HPO])
        state = _make_state(
            query="seizure", source_filter=["HPO"], expanded_search_terms=["seizure", "fits"]
        )

        start = time.monotonic()
        with patch("knowledge_lookup.agents.nodes.lookup.CentralKnowledgeLookup", ckl):
            result = asyncio.run(lookup_node(state))

        assert time.monotonic() - start < 5
        assert ckl.call_args.kwargs["config"].enabled_sources == [KnowledgeSource.HPO]
        assert result["iteration"] == 1
        assert any("not finished" in e for e in result["errors"])

    def test_lookup_node_does_not_fall_back_to_all_sources(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from knowledge_lookup.agents.nodes.lookup import lookup_node

        instance = MagicMock(adapters={})
        instance.search_concepts = AsyncMock()
        instance.close = AsyncMock()
        state = _make_state(query="seizure", source_filter=["HPO"])

        with patch(
            "knowledge_lookup.agents.nodes.lookup.CentralKnowledgeLookup",
            MagicMock(return_value=instance),
        ):
            result = asyncio.run(lookup_node(state))

        instance.search_concepts.assert_not_called()
        assert any("None of the requested sources" in e for e in result["errors"])

    def test_filter_node_keeps_top_max_results(self):
        from knowledge_lookup.agents.nodes import filter_node

        concepts = [_make_concept(f"finding {i}", confidence=i / 100) for i in range(30)]
        state = _make_state(
            lookup_result=lookup_result_to_dict(_make_lookup_result(concepts=concepts)),
            max_results=5,
        )

        result = asyncio.run(filter_node(state))

        kept = dict_to_lookup_result(result["lookup_result"]).concepts
        assert [c.primary_label for c in kept] == [f"finding {i}" for i in (29, 28, 27, 26, 25)]

    def test_detail_gather_node_is_bounded_by_its_budget(self, monkeypatch):
        import time
        from unittest.mock import patch

        from knowledge_lookup.agents.nodes.detail_gather import _CROSS_SOURCES, detail_gather_node

        monkeypatch.setattr("knowledge_lookup.agents.nodes._limits.DETAIL_GATHER_TIMEOUT", 0.2)
        ckl = _slow_lookup_class([KnowledgeSource.OLS, KnowledgeSource.HPO])
        concepts = [_make_concept(f"c{i}") for i in range(20)]
        state = _make_state(
            lookup_result=lookup_result_to_dict(_make_lookup_result(concepts=concepts))
        )

        start = time.monotonic()
        with patch("knowledge_lookup.agents.nodes.detail_gather.CentralKnowledgeLookup", ckl):
            result = asyncio.run(detail_gather_node(state))

        assert time.monotonic() - start < 5
        assert ckl.call_args.kwargs["config"].enabled_sources == list(_CROSS_SOURCES)
        assert "20 label(s) not finished" in result["steps"][0]["detail"]

    def test_enrichment_node_skips_without_umls(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from knowledge_lookup.agents.nodes.enrichment import enrichment_node

        instance = MagicMock(adapters={})
        instance.search_concepts = AsyncMock()
        instance.close = AsyncMock()
        state = _make_state(
            lookup_result=lookup_result_to_dict(_make_lookup_result(concepts=[_make_concept("x")]))
        )

        with patch(
            "knowledge_lookup.agents.nodes.enrichment.CentralKnowledgeLookup",
            MagicMock(return_value=instance),
        ) as ckl:
            result = asyncio.run(enrichment_node(state))

        instance.search_concepts.assert_not_called()
        assert ckl.call_args.kwargs["config"].enabled_sources == [KnowledgeSource.UMLS]
        assert result["steps"][0]["action"] == "skip"

    def test_enrichment_node_is_bounded_by_its_budget(self, monkeypatch):
        import time
        from unittest.mock import patch

        from knowledge_lookup.agents.nodes.enrichment import enrichment_node

        monkeypatch.setattr("knowledge_lookup.agents.nodes._limits.ENRICHMENT_TIMEOUT", 0.2)
        ckl = _slow_lookup_class([KnowledgeSource.UMLS])
        concepts = [_make_concept(f"c{i}") for i in range(20)]
        state = _make_state(
            lookup_result=lookup_result_to_dict(_make_lookup_result(concepts=concepts))
        )

        start = time.monotonic()
        with patch("knowledge_lookup.agents.nodes.enrichment.CentralKnowledgeLookup", ckl):
            result = asyncio.run(enrichment_node(state))

        assert time.monotonic() - start < 5
        assert "20 search(es) not finished" in result["steps"][0]["detail"]

    def test_review_does_not_retry_without_llm(self, monkeypatch):
        import time

        monkeypatch.setattr(
            "knowledge_lookup.agents.nodes.review.load_llm_config", lambda: dict(_NO_LLM)
        )
        state = _make_state(
            lookup_result=lookup_result_to_dict(_make_lookup_result(concepts=[_make_concept("x")]))
        )

        start = time.monotonic()
        result = asyncio.run(review_node(state))

        assert time.monotonic() - start < 1
        assert result["steps"][0]["agent"] == "ReviewAgent(Rule)"

    def test_workflow_with_unresponsive_sources_finishes(self, monkeypatch, tmp_path):
        """End to end: hanging sources cannot stall the workflow past its budgets."""
        import time

        from knowledge_lookup.agents.runners import run_workflow

        async def never_finishes(*args, **kwargs):
            await asyncio.sleep(30)

        for name in ("EXPAND", "LOOKUP", "DETAIL_GATHER", "ENRICHMENT"):
            monkeypatch.setattr(f"knowledge_lookup.agents.nodes._limits.{name}_TIMEOUT", 0.2)
        monkeypatch.setattr(
            "knowledge_lookup.agents.nodes.expand.expand_and_search", never_finishes
        )
        for module in ("expand", "lookup", "detail_gather", "enrichment"):
            monkeypatch.setattr(
                f"knowledge_lookup.agents.nodes.{module}.CentralKnowledgeLookup",
                _slow_lookup_class([KnowledgeSource.HPO, KnowledgeSource.UMLS]),
            )
        monkeypatch.setattr(
            "knowledge_lookup.agents.nodes.review.load_llm_config", lambda: dict(_NO_LLM)
        )

        start = time.monotonic()
        result = asyncio.run(
            run_workflow(
                "seizure",
                sources=["HPO"],
                export_path=str(tmp_path),
                auto_approve_threshold=0.0,
            )
        )

        assert time.monotonic() - start < 10
        assert result["status"] == "completed"
        assert any("not finished" in e for e in result["errors"])


_SUGGESTION = "Check failed source health and consider retrying"


class TestRefineNode:
    """Regression: refine rewrote `query` (with review suggestions appended), but lookup
    kept searching the `expanded_search_terms` from the first pass."""

    def test_refine_rebuilds_search_terms_from_the_notes(self):
        from knowledge_lookup.agents.nodes.refine import refine_node

        state = _make_state(
            query="seizure",
            iteration=1,
            expanded_search_terms=["seizure", "Epileptic seizure"],
            refinement_notes=["focal"],
            review_suggestions=[_SUGGESTION],
        )

        result = asyncio.run(refine_node(state))

        assert result["query"] == "seizure focal"
        assert "seizure focal" in result["expanded_search_terms"]
        assert "seizure" not in result["expanded_search_terms"]
        assert "Epileptic seizure" not in result["expanded_search_terms"]
        assert _SUGGESTION in result["steps"][0]["detail"]

    def test_review_suggestions_never_reach_the_query(self):
        from knowledge_lookup.agents.nodes.refine import refine_node

        state = _make_state(
            query="seizure",
            iteration=1,
            expanded_search_terms=["seizure", "Epileptic seizure"],
            review_suggestions=[_SUGGESTION, "Try a more specific query"],
        )

        result = asyncio.run(refine_node(state))

        assert result["query"] == "seizure"
        assert result["status"] == "searching"
        assert "expanded_search_terms" not in result  # the same terms are searched again

    def test_kept_notes_are_not_appended_twice(self):
        from knowledge_lookup.agents.nodes.refine import refine_node

        state = _make_state(
            query="seizure focal",
            iteration=2,
            expanded_search_terms=["seizure focal"],
            refinement_notes=["focal"],
        )

        result = asyncio.run(refine_node(state))

        assert result["query"] == "seizure focal"
        assert "expanded_search_terms" not in result

    def test_lookup_after_refine_searches_the_refined_terms(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from knowledge_lookup.agents.nodes.lookup import lookup_node
        from knowledge_lookup.agents.nodes.refine import refine_node

        state = _make_state(
            query="seizure",
            iteration=1,
            source_filter=["HPO"],
            expanded_search_terms=["seizure", "Epileptic seizure"],
            refinement_notes=["focal"],
            review_suggestions=[_SUGGESTION],
        )
        state.update(asyncio.run(refine_node(state)))

        instance = MagicMock(adapters={KnowledgeSource.HPO: MagicMock()})
        instance.search_concepts = AsyncMock(
            side_effect=lambda query, **kw: LookupResult(query=query)
        )
        instance.close = AsyncMock()
        with patch(
            "knowledge_lookup.agents.nodes.lookup.CentralKnowledgeLookup",
            MagicMock(return_value=instance),
        ):
            asyncio.run(lookup_node(state))

        searched = [c.kwargs["query"] for c in instance.search_concepts.await_args_list]
        assert "seizure focal" in searched
        assert "seizure" not in searched
        assert "Epileptic seizure" not in searched
        assert not any("Check failed" in q for q in searched)
