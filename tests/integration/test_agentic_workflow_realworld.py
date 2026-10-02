"""
Real-world (live API) tests for the agentic expansion features of the workflow.

Every test talks to live services using the credentials in the project's
``.env`` (loaded below; the file is git-ignored and values are never printed):

* ``BLABLADOR_API_KEY`` (or another LLM backend) - classify / follow-up
  suggestions and the review step
* ``UMLS_API_KEY`` - UMLS enrichment and relationships
* ``BIOPORTAL_API_KEY`` - BioPortal cross-references
* HGNC, OLS, HPO, MONDO, KEGG, STRING, Ensembl and Europe PMC need no key

They are marked ``integration``, ``network`` and ``slow``; offline runs
(``-m "not slow"``) skip them. Assertions target structural invariants, not exact
live counts, and a test skips (with the reason) when an upstream service gave
nothing back, so an outage does not read as a regression. Run with::

    poetry run pytest tests/integration/test_agentic_workflow_realworld.py -m network -s
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

from knowledge_lookup import create_knowledge_lookup  # noqa: E402
from knowledge_lookup.agents import run_workflow  # noqa: E402
from knowledge_lookup.agents.config import (  # noqa: E402
    SHORT_REPLY_MAX_TOKENS,
    call_llm,
    load_llm_config,
)
from knowledge_lookup.agents.nodes import (  # noqa: E402
    classify_node,
    detail_gather_node,
    evidence_node,
    followup_node,
    lookup_node,
)
from knowledge_lookup.agents.nodes.followup import diagnose, plan_probes  # noqa: E402
from knowledge_lookup.agents.state import (  # noqa: E402
    dict_to_lookup_result,
    lookup_result_to_dict,
)
from knowledge_lookup.models import KnowledgeSource  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.slow]

# Free-text of the form ``tests/unit/test_agentic_expansion._state`` builds.
_BASE_STATE = {
    "max_results": 20,
    "source_filter": None,
    "concept_type_filter": None,
    "export_formats": ["json"],
    "export_path": None,
    "lookup_result": None,
    "iteration": 0,
    "max_iterations": 3,
    "auto_approve_threshold": 0.0,
    "status": "pending",
    "errors": [],
    "steps": [],
    "max_auto_rounds": 1,
    "auto_round": 0,
    "followup_pending": False,
    "followup_probes": [],
    "relationship_edges": [],
    "include_relationships": False,
    "include_evidence": False,
    "literature_evidence": [],
}


def _state(query: str, **overrides):
    state = {
        **_BASE_STATE,
        "query": query,
        "original_query": query,
        "expanded_search_terms": [query],
    }
    state.update(overrides)
    return state


def _need_llm() -> None:
    if not load_llm_config()["api_key"]:
        pytest.skip("no LLM backend configured in .env (BLABLADOR/OPENAI/ANTHROPIC key)")


def _need_env(name: str) -> None:
    if not os.getenv(name):
        pytest.skip(f"{name} not set in .env")


async def _search(query: str, sources: list[KnowledgeSource], max_results: int = 20):
    """Live search through the library; skip when the upstream returns nothing."""
    lookup = create_knowledge_lookup()
    try:
        result = await lookup.search_concepts(query, sources=sources, max_results=max_results)
    finally:
        await lookup.close()
    if not result.concepts:
        pytest.skip(f"{sources} returned nothing for {query!r} (upstream outage?)")
    return result


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassifyLive:
    @pytest.mark.asyncio
    async def test_rules_need_no_network(self):
        update = await classify_node(_state("TP53"))
        assert update["inferred_concept_types"] == ["GENE"]

    @pytest.mark.asyncio
    async def test_llm_fallback_classifies_an_ambiguous_symbol(self):
        """``EGFR`` has no digit, so no rule fires and the configured LLM decides."""
        _need_llm()
        update = await classify_node(_state("EGFR"))
        types = update["inferred_concept_types"]
        if not types:
            pytest.skip("LLM gave no usable answer")
        assert set(types) & {"GENE", "PROTEIN"}, types
        assert "by LLM" in update["steps"][0]["detail"]


# ---------------------------------------------------------------------------
# type-aware cross-references
# ---------------------------------------------------------------------------


class TestTypeAwareCrossReferences:
    @pytest.mark.asyncio
    async def test_a_gene_is_cross_referenced_in_gene_resources(self):
        result = await _search("TP53", [KnowledgeSource.HGNC], max_results=3)
        gene = next(
            (c for c in result.concepts if (c.primary_label or "").upper() == "TP53"), None
        )
        if gene is None:
            pytest.skip("HGNC did not return TP53 itself")
        before = {str(getattr(i.source, "value", i.source)) for i in gene.identifiers or []}

        state = _state("TP53", lookup_result=lookup_result_to_dict(result))
        update = await detail_gather_node(state)

        enriched = dict_to_lookup_result(update["lookup_result"])
        tp53 = next(c for c in enriched.concepts if (c.primary_label or "").upper() == "TP53")
        after = {str(getattr(i.source, "value", i.source)) for i in tp53.identifiers or []}
        gained = after - before
        print(f"\n  TP53 gained identifiers from: {sorted(gained)}")
        assert gained, f"no cross-references added; step: {update['steps'][0]['detail']}"
        # at least one generalist and at least one gene-specific resource answered
        assert gained & {"OLS", "UMLS", "BIOPORTAL", "WIKIDATA"}, gained
        assert gained & {"UNIPROT", "ENSEMBL", "HGNC", "KEGG", "STRING", "OPENTARGETS"}, gained


# ---------------------------------------------------------------------------
# autonomous follow-up
# ---------------------------------------------------------------------------


async def _no_llm_answer(*args, **kwargs):
    return None


# Natural queries rarely leave a gap (live lookups return 5-20 concepts), so the
# gap below is staged: a real lookup is trimmed to its first concept, as if
# filtering had been harsh (it keeps the exact-match concept with the most synonyms/hierarchy). Everything after that - the synonyms and hierarchy the
# plan is built from, and the focused search that runs it - is real data.
_STAGED_QUERIES = ["TP53", "BRCA1", "EGFR"]


class TestFollowupLive:
    @pytest.mark.asyncio
    async def test_thin_result_is_widened_by_a_focused_pass(self, monkeypatch):
        # Deterministic path: terms come from the real concept's synonyms and
        # hierarchy, not from the LLM (that path has its own test below).
        monkeypatch.setattr("knowledge_lookup.agents.nodes.followup.call_llm", _no_llm_answer)
        sources = ["UNIPROT", "OLS"]  # UniProt records carry synonyms; disease hits are lean
        for query in _STAGED_QUERIES:
            state = _state(query, source_filter=sources, max_results=20, iteration=0)
            state.update(await lookup_node(state))
            found = dict_to_lookup_result(state["lookup_result"])
            if not found.concepts:
                continue
            matching = [
                c
                for c in found.concepts
                if query.lower()
                in {str(n).lower() for n in (c.primary_label, *(c.synonyms or []))}
            ]
            if not matching:
                continue
            richest = max(
                matching,
                key=lambda c: len(c.synonyms or []) + len(c.children or []) + len(c.parents or []),
            )
            found.concepts = [richest]  # stage the gap
            state["lookup_result"] = lookup_result_to_dict(found)
            gaps = diagnose(state)
            assert "thin" in gaps, gaps
            probes = await plan_probes(state, gaps)
            if probes:
                break
        else:
            pytest.skip("no staged query had synonyms or hierarchy to follow up on")

        before = {c.primary_label for c in found.concepts}
        planned = await followup_node(state)
        assert planned["followup_pending"] is True
        terms = [p["term"] for p in planned["followup_probes"]]
        print(f"\n  {query!r}: gaps={gaps}, probes={terms}")
        assert query.lower() not in {t.lower() for t in terms}  # never re-searches the query

        state.update(planned)
        iteration = state["iteration"]
        focused = await lookup_node(state)

        after = {c.primary_label for c in dict_to_lookup_result(focused["lookup_result"]).concepts}
        print(f"  concepts {len(before)} -> {len(after)}")
        assert "iteration" not in focused  # no max_iterations used
        assert state["iteration"] == iteration
        assert focused["followup_pending"] is False
        assert before <= after  # merged, nothing lost
        assert len(after) > len(before), f"follow-up found nothing new for {query!r}"

    @pytest.mark.asyncio
    async def test_disease_followup_is_built_from_cross_referenced_synonyms(self, monkeypatch):
        """Why the decision sits after detail_gather: raw disease hits carry no synonyms."""
        monkeypatch.setattr("knowledge_lookup.agents.nodes.followup.call_llm", _no_llm_answer)
        query = "Dravet syndrome"
        state = _state(query, source_filter=["HPO", "OLS", "MONDO"], max_results=20)
        state.update(await lookup_node(state))

        def exact(result):
            return [
                c
                for c in result.concepts
                if query.lower()
                in {str(n).lower() for n in (c.primary_label, *(c.synonyms or []))}
            ]

        raw = dict_to_lookup_result(state["lookup_result"])
        if not exact(raw):
            pytest.skip(f"no exact {query!r} concept in the search results")
        raw_synonyms = sum(len(c.synonyms or []) for c in exact(raw))

        state.update(await detail_gather_node(state))
        gathered = dict_to_lookup_result(state["lookup_result"])
        best = max(exact(gathered), key=lambda c: len(c.synonyms or []))
        print(
            f"\n  synonyms on the exact match: {raw_synonyms} before -> {len(best.synonyms or [])} after"
        )
        if not best.synonyms:
            pytest.skip("cross-reference sources added no synonyms for this concept")

        gathered.concepts = [best]  # stage the gap
        state["lookup_result"] = lookup_result_to_dict(gathered)
        gaps = diagnose(state)
        assert "thin" in gaps, gaps
        probes = await plan_probes(state, gaps)
        terms = [p["term"] for p in probes]
        print(f"  probes built from them: {terms}")
        assert terms, f"no probes although the concept has synonyms {best.synonyms[:5]}"
        assert all("Barrett" not in t for t in terms)  # stays on topic

        # a second cross-reference pass over the merged result only pays for new labels
        state.update(await followup_node(state))
        merged = await lookup_node(state)
        state.update(merged)
        second = await detail_gather_node(state)
        done_before = len(state.get("xref_labels") or [])
        print(f"  xref labels remembered: {done_before} -> {len(second.get('xref_labels', []))}")
        assert set(state.get("xref_labels") or []) <= set(second.get("xref_labels", []))

    @pytest.mark.asyncio
    async def test_llm_recovers_a_misspelled_query(self):
        """No result for the typo -> the LLM suggests a spelling -> the focused pass finds it."""
        _need_llm()
        state = _state("seizuure", source_filter=["HPO"], max_results=10)
        state.update(await lookup_node(state))
        if dict_to_lookup_result(state["lookup_result"]).concepts:
            pytest.skip("HPO matched the typo itself; nothing to recover")
        assert diagnose(state) == ["empty"]

        planned = await followup_node(state)
        if not planned["followup_pending"]:
            pytest.skip("LLM suggested no usable term")
        terms = [p["term"] for p in planned["followup_probes"]]
        print(f"\n  LLM suggested: {terms}")
        assert all(p["reason"] == "LLM suggestion" for p in planned["followup_probes"])

        state.update(planned)
        focused = await lookup_node(state)
        found = dict_to_lookup_result(focused["lookup_result"]).concepts
        assert found, f"none of {terms} found anything in HPO"


# ---------------------------------------------------------------------------
# literature evidence
# ---------------------------------------------------------------------------


class TestEvidenceLive:
    @pytest.mark.asyncio
    async def test_europepmc_papers_for_a_concept(self):
        result = await _search("TP53", [KnowledgeSource.HGNC], max_results=1)
        state = _state("TP53", include_evidence=True, lookup_result=lookup_result_to_dict(result))
        update = None
        for _ in range(3):  # Europe PMC answers 503 now and then
            update = await evidence_node(state)
            if update.get("literature_evidence"):
                break
        if not update or not update.get("literature_evidence"):
            pytest.skip(f"Europe PMC returned no papers: {update['steps'][0]['detail']}")
        entry = update["literature_evidence"][0]
        print(f"\n  {entry['concept']}: {[p['title'][:60] for p in entry['papers']]}")
        assert 1 <= len(entry["papers"]) <= 3
        assert all(p["id"] and p["title"] for p in entry["papers"])


# ---------------------------------------------------------------------------
# the whole workflow
# ---------------------------------------------------------------------------


class TestKEGGLive:
    @pytest.mark.asyncio
    async def test_query_with_a_comma_is_searched_not_rejected(self):
        """KEGG's find endpoint answers 400 to commas; the adapter now cleans the query."""
        lookup = create_knowledge_lookup()
        try:
            adapter = lookup.adapters.get(KnowledgeSource.KEGG)
            if adapter is None:
                pytest.skip("KEGG adapter not available")
            plain = await adapter.search_concepts("TP53 protein", databases=["gene"], limit=5)
            if not plain:
                pytest.skip("KEGG returned nothing for the plain query (outage?)")
            with_comma = await adapter.search_concepts(
                "TP53, protein", databases=["gene"], limit=5
            )
        finally:
            await lookup.close()
        assert with_comma, "the comma made KEGG return nothing"
        assert [c.primary_id for c in with_comma] == [c.primary_id for c in plain]
        print(f"\n  KEGG 'TP53, protein' -> {[c.primary_label for c in with_comma[:3]]}")


class TestRankingLive:
    @pytest.mark.asyncio
    async def test_the_exact_gene_ranks_first(self):
        from knowledge_lookup.agents.nodes import filter_node

        sources = ["HGNC", "OLS", "UNIPROT"]
        state = _state("TP53", source_filter=sources, max_results=8)
        state.update(await lookup_node(state))
        before = [c.primary_label for c in dict_to_lookup_result(state["lookup_result"]).concepts]
        if "TP53" not in before:
            pytest.skip(f"no concept labelled TP53 in the live results: {before[:6]}")
        state.update(await filter_node(state))
        after = [c.primary_label for c in dict_to_lookup_result(state["lookup_result"]).concepts]
        print(f"\n  before filter: {before[:5]}\n  after filter:  {after[:5]}")
        assert after[0] == "TP53"


class TestUMLSLive:
    @pytest.mark.asyncio
    async def test_curie_prefixed_cui_is_accepted(self):
        """Cross-reference sources write "UMLS:C..."; the API itself only knows the bare CUI."""
        _need_env("UMLS_API_KEY")
        lookup = create_knowledge_lookup()
        try:
            adapter = lookup.adapters.get(KnowledgeSource.UMLS)
            if adapter is None:
                pytest.skip("UMLS adapter not available")
            bare = await adapter.get_relationships("C0079419", limit=3)
            if not bare:
                pytest.skip("UMLS returned no relations for C0079419 (outage?)")
            for form in ("UMLS:C0079419", "umls:C0079419"):
                prefixed = await adapter.get_relationships(form, limit=3)
                assert [r["related_id"] for r in prefixed] == [r["related_id"] for r in bare], form
        finally:
            await lookup.close()


class TestWholeWorkflowLive:
    @pytest.mark.asyncio
    async def test_gene_query_exercises_every_stage(self, tmp_path: Path, caplog):
        _need_llm()
        _need_env("UMLS_API_KEY")
        caplog.set_level("ERROR")
        result = await run_workflow(
            "TP53",
            sources=["HGNC", "OLS", "UMLS"],
            max_results=8,
            auto_approve_threshold=0.0,  # never pause for approval
            include_relationships=True,
            include_evidence=True,
            max_auto_rounds=1,
            export_path=str(tmp_path),
        )
        for step in result["steps"]:
            print(f"  {step['agent']:18} {step['action']:14} {step['detail'][:110]}")

        assert result["status"] == "completed", result["errors"]
        assert result["inferred_concept_types"] == ["GENE"]
        agents = [s["agent"] for s in result["steps"]]
        for expected in (
            "ClassifyAgent",
            "ExpandAgent",
            "LookupAgent",
            "QualityGateAgent",
            "DetailGatherAgent",
            "EnrichAgent",
            "RelationshipAgent",
            "EvidenceAgent",
            "AggregateAgent",
            "ExportAgent",
        ):
            assert expected in agents, f"{expected} did not run: {agents}"
        assert result["result"] is not None and result["result"].concepts

        # no UMLS relationship lookup used a "UMLS:C..." id or got a 404 for one
        # (a 5xx is an upstream outage, not this bug)
        bad = [
            r.getMessage()[:120]
            for r in caplog.records
            if "get_relationships failed" in r.getMessage()
            and ("'UMLS:" in r.getMessage() or "status 404" in r.getMessage())
        ]
        assert not bad, bad

        # relationships: real edges from real adapters
        edges = result["relationship_edges"]
        assert edges, "no relationship edges harvested for TP53"
        assert all(e["related_id"] for e in edges)
        assert any(e.get("related_name") for e in edges)

        # the review saw them, and the export carries them
        assert result["llm_explanation"] or result["review_summary"]
        data = json.loads(Path(result["export_paths"][0]).read_text())
        assert data["expansion"]["inferred_concept_types"] == ["GENE"]
        assert data["expansion"]["relationship_edges"] == edges
        assert data["concepts"], "export has no concepts"

    @pytest.mark.asyncio
    async def test_opting_out_restores_the_linear_flow(self, tmp_path: Path):
        result = await run_workflow(
            "seizure",
            sources=["HPO"],
            max_results=5,
            auto_approve_threshold=0.0,
            max_auto_rounds=0,
            export_path=str(tmp_path),
        )
        assert result["status"] == "completed", result["errors"]
        assert result["auto_rounds"] == 0
        agents = [s["agent"] for s in result["steps"]]
        assert "FollowupAgent" not in agents
        skipped = {s["agent"] for s in result["steps"] if s["action"] == "skip"}
        assert {"RelationshipAgent", "EvidenceAgent"} <= skipped


def test_llm_backend_is_reachable():
    """The .env LLM answers a trivial prompt (so the LLM-dependent tests above mean something)."""
    import asyncio

    _need_llm()
    reply = asyncio.run(
        call_llm('Reply with only the JSON list ["ok"].', max_tokens=SHORT_REPLY_MAX_TOKENS)
    )
    if reply is None:
        pytest.skip("LLM backend configured but did not answer (quota/outage?)")
    assert "ok" in reply.lower()
