"""Tests for the agentic expansion features of the LangGraph workflow.

Covers query classification, type-aware cross-reference sources, the autonomous
follow-up loop, the focused lookup pass, relationship harvesting and literature
evidence.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.agents.nodes import followup as followup_mod
from knowledge_lookup.agents.nodes._edges import merge_edges
from knowledge_lookup.agents.nodes.classify import (
    _parse_llm_types,
    classify_node,
    infer_concept_types,
)
from knowledge_lookup.agents.routing import route_after_detail_gather, route_after_followup
from knowledge_lookup.agents.state import (
    LookupWorkflowState,
    dict_to_lookup_result,
    lookup_result_to_dict,
    make_step,
)
from knowledge_lookup.core.source_routing import (
    LEGACY_XREF_SOURCES,
    MAX_XREF_SOURCES_PER_LABEL,
    as_concept_type,
    cross_reference_sources,
)
from knowledge_lookup.models import (
    ConceptIdentifier,
    ConceptType,
    KnowledgeSource,
    LookupResult,
    UnifiedConcept,
)

_NO_LLM = {"backend": None, "api_key": None, "base_url": None, "model": None}


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Keep every test off the network: no LLM backend is configured."""
    monkeypatch.setattr("knowledge_lookup.agents.config.load_llm_config", lambda: dict(_NO_LLM))


def _concept(
    label: str,
    *,
    cid: str | None = None,
    sources: list[KnowledgeSource] | None = None,
    concept_type: ConceptType | None = None,
    synonyms: list[str] | None = None,
    children: list[str] | None = None,
    parents: list[str] | None = None,
    identifiers: list[ConceptIdentifier] | None = None,
) -> UnifiedConcept:
    concept = UnifiedConcept(
        primary_id=cid or f"http://test.org/{label.lower().replace(' ', '_')}",
        primary_label=label,
        confidence_score=0.8,
        sources=sources or [KnowledgeSource.OLS],
    )
    if concept_type is not None:
        concept.concept_type = concept_type
    concept.synonyms = synonyms
    concept.children = children
    concept.parents = parents
    if identifiers:
        concept.identifiers = identifiers
    return concept


def _result(
    concepts: list[UnifiedConcept],
    *,
    queried: list[KnowledgeSource] | None = None,
    failed: list[KnowledgeSource] | None = None,
) -> dict:
    result = LookupResult(query="q", sources_queried=queried or [KnowledgeSource.OLS])
    result.concepts = concepts
    result.sources_succeeded = [KnowledgeSource.OLS]
    result.sources_failed = failed
    return lookup_result_to_dict(result)


def _state(**overrides: Any) -> LookupWorkflowState:
    state: LookupWorkflowState = {
        "query": "seizure",
        "original_query": "seizure",
        "max_results": 20,
        "source_filter": None,
        "concept_type_filter": None,
        "export_formats": ["json"],
        "export_path": None,
        "lookup_result": None,
        "iteration": 1,
        "max_iterations": 3,
        "auto_approve_threshold": 0.8,
        "status": "searching",
        "errors": [],
        "expanded_search_terms": ["seizure"],
        "max_auto_rounds": 1,
        "auto_round": 0,
        "steps": [],
    }  # type: ignore[typeddict-item]
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# ---------------------------------------------------------------------------
# Type-aware cross-reference sources
# ---------------------------------------------------------------------------


class TestCrossReferenceSources:
    ALL = list(KnowledgeSource)

    def test_gene_gets_gene_resources(self):
        sources = cross_reference_sources(ConceptType.GENE, self.ALL)
        assert sources[:4] == [
            KnowledgeSource.OLS,
            KnowledgeSource.UMLS,
            KnowledgeSource.BIOPORTAL,
            KnowledgeSource.WIKIDATA,
        ]
        assert KnowledgeSource.HGNC in sources
        assert KnowledgeSource.UNIPROT in sources
        assert KnowledgeSource.CHEMBL not in sources

    def test_drug_gets_chemistry_resources(self):
        sources = cross_reference_sources(ConceptType.DRUG, self.ALL)
        assert KnowledgeSource.CHEMBL in sources
        assert KnowledgeSource.PUBCHEM in sources
        assert KnowledgeSource.HGNC not in sources

    @pytest.mark.parametrize("concept_type", [None, ConceptType.UNKNOWN])
    def test_unknown_type_keeps_the_legacy_set(self, concept_type):
        assert cross_reference_sources(concept_type, self.ALL) == list(LEGACY_XREF_SOURCES)

    def test_only_available_sources_and_cap(self):
        available = [KnowledgeSource.OLS, KnowledgeSource.HGNC]
        assert cross_reference_sources(ConceptType.GENE, available) == available
        capped = cross_reference_sources(ConceptType.DISEASE, self.ALL)
        assert len(capped) == MAX_XREF_SOURCES_PER_LABEL
        assert len(cross_reference_sources(ConceptType.DISEASE, self.ALL, limit=2)) == 2

    def test_literature_sources_are_never_cross_references(self):
        for ct in (ConceptType.DISEASE, ConceptType.GENE, ConceptType.DRUG, None):
            sources = cross_reference_sources(ct, self.ALL)
            assert KnowledgeSource.EUROPEPMC not in sources
            assert KnowledgeSource.EUTILS not in sources

    def test_as_concept_type(self):
        assert as_concept_type("gene") == ConceptType.GENE
        assert as_concept_type(ConceptType.DRUG) == ConceptType.DRUG
        assert as_concept_type("nonsense") is None
        assert as_concept_type(None) is None
        assert as_concept_type("") is None

    def test_detail_gather_queries_type_suited_sources(self):
        from knowledge_lookup.agents.nodes.detail_gather import detail_gather_node

        calls: list[tuple[str, KnowledgeSource]] = []

        async def search(query, sources, **kwargs):
            calls.append((query, sources[0]))
            return LookupResult(query=query)

        instance = MagicMock()
        instance.search_concepts = search
        instance.close = AsyncMock()

        def factory(config, auto_initialize):
            instance.adapters = dict.fromkeys(config.enabled_sources or [], object())
            return instance

        gene = _concept("TP53", concept_type=ConceptType.GENE, sources=[KnowledgeSource.HGNC])
        drug = _concept("aspirin", concept_type=ConceptType.DRUG, sources=[KnowledgeSource.CHEMBL])
        state = _state(lookup_result=_result([gene, drug]))

        with patch(
            "knowledge_lookup.agents.nodes.detail_gather.CentralKnowledgeLookup",
            MagicMock(side_effect=factory),
        ):
            result = asyncio.run(detail_gather_node(state))

        by_label: dict[str, set[KnowledgeSource]] = {}
        for label, source in calls:
            by_label.setdefault(label, set()).add(source)
        assert KnowledgeSource.HGNC in by_label["TP53"]
        assert KnowledgeSource.UNIPROT in by_label["TP53"]
        assert KnowledgeSource.CHEMBL not in by_label["TP53"]
        assert KnowledgeSource.CHEMBL in by_label["aspirin"]
        assert KnowledgeSource.HGNC not in by_label["aspirin"]
        assert result["steps"][0]["agent"] == "DetailGatherAgent"


class TestDetailGatherIsIncremental:
    @staticmethod
    def _run(state):
        from knowledge_lookup.agents.nodes.detail_gather import detail_gather_node

        searched: list[str] = []

        async def search(query, sources, **kwargs):
            searched.append(query)
            return LookupResult(query=query)

        instance = MagicMock()
        instance.search_concepts = search
        instance.close = AsyncMock()

        def factory(config, auto_initialize):
            instance.adapters = dict.fromkeys(config.enabled_sources or [], object())
            return instance

        with patch(
            "knowledge_lookup.agents.nodes.detail_gather.CentralKnowledgeLookup",
            MagicMock(side_effect=factory),
        ):
            return asyncio.run(detail_gather_node(state)), set(searched)

    def test_records_the_labels_it_cross_referenced(self):
        state = _state(lookup_result=_result([_concept("Seizure"), _concept("Fit")]))
        update, searched = self._run(state)
        assert searched == {"Seizure", "Fit"}
        assert update["xref_labels"] == ["fit", "seizure"]

    def test_umls_identifiers_from_cross_references_are_stored_as_bare_cuis(self):
        """OLS-style xrefs say "UMLS:C..."; the UMLS API answers that with 404."""
        from knowledge_lookup.agents.nodes.detail_gather import detail_gather_node

        found = _concept("Seizure", cid="HP:0001250", sources=[KnowledgeSource.HPO])
        found.identifiers = [
            ConceptIdentifier(source=KnowledgeSource.UMLS, identifier="UMLS:C0036572", label="x")
        ]

        async def search(query, sources, **kwargs):
            if sources[0] != KnowledgeSource.OLS:
                return LookupResult(query=query)
            return LookupResult(query=query, concepts=[found])

        instance = MagicMock()
        instance.search_concepts = search
        instance.close = AsyncMock()

        def factory(config, auto_initialize):
            instance.adapters = dict.fromkeys(config.enabled_sources or [], object())
            return instance

        state = _state(lookup_result=_result([_concept("Seizure")]))
        with patch(
            "knowledge_lookup.agents.nodes.detail_gather.CentralKnowledgeLookup",
            MagicMock(side_effect=factory),
        ):
            update = asyncio.run(detail_gather_node(state))

        enriched = dict_to_lookup_result(update["lookup_result"])
        umls_ids = [
            i.identifier
            for c in enriched.concepts
            for i in c.identifiers or []
            if i.source == KnowledgeSource.UMLS
        ]
        assert umls_ids == ["C0036572"]

    def test_second_pass_only_searches_new_labels(self):
        state = _state(
            lookup_result=_result([_concept("Seizure"), _concept("Convulsion")]),
            xref_labels=["seizure"],
        )
        update, searched = self._run(state)
        assert searched == {"Convulsion"}
        assert update["xref_labels"] == ["convulsion", "seizure"]

    def test_nothing_new_builds_no_adapters(self):
        state = _state(lookup_result=_result([_concept("Seizure")]), xref_labels=["Seizure"])
        update, searched = self._run(state)
        assert searched == set()
        assert update["steps"][0]["action"] == "skip"
        assert "already cross-referenced" in update["steps"][0]["detail"]
        assert "xref_labels" not in update

    def test_labels_that_timed_out_are_retried_next_pass(self, monkeypatch):
        from knowledge_lookup.agents.nodes.detail_gather import detail_gather_node

        monkeypatch.setattr("knowledge_lookup.agents.nodes._limits.DETAIL_GATHER_TIMEOUT", 0.2)

        async def slow(*args, **kwargs):
            await asyncio.sleep(30)

        instance = MagicMock()
        instance.search_concepts = slow
        instance.close = AsyncMock()

        def factory(config, auto_initialize):
            instance.adapters = dict.fromkeys(config.enabled_sources or [], object())
            return instance

        state = _state(lookup_result=_result([_concept("Seizure")]))
        with patch(
            "knowledge_lookup.agents.nodes.detail_gather.CentralKnowledgeLookup",
            MagicMock(side_effect=factory),
        ):
            update = asyncio.run(detail_gather_node(state))
        assert update["xref_labels"] == []


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassify:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("HP:0001250", [ConceptType.PHENOTYPE]),
            ("GO:0006915", [ConceptType.BIOLOGICAL_PROCESS]),
            ("ENSG00000141510", [ConceptType.GENE]),
            ("P04637", [ConceptType.PROTEIN]),
            ("R-HSA-109581", [ConceptType.PATHWAY]),
            ("CHEMBL25", [ConceptType.DRUG]),
            ("TP53", [ConceptType.GENE]),
            ("imatinib", [ConceptType.DRUG]),
            ("trastuzumab", [ConceptType.DRUG]),
            ("type 2 diabetes mellitus", [ConceptType.DISEASE]),
            ("apoptosis signaling pathway", [ConceptType.PATHWAY]),
            ("insulin receptor", [ConceptType.PROTEIN]),
            ("headache", [ConceptType.SYMPTOM]),
            ("BRCA1, imatinib", [ConceptType.GENE, ConceptType.DRUG]),
            ("BRCA1, TP53", [ConceptType.GENE]),
        ],
    )
    def test_rules(self, query, expected):
        assert infer_concept_types(query) == expected

    @pytest.mark.parametrize("query", ["COPD", "xyzzy", "", "  ,  "])
    def test_ambiguous_or_empty_queries_infer_nothing(self, query):
        assert infer_concept_types(query) == []

    def test_node_uses_rules(self):
        update = asyncio.run(classify_node(_state(query="TP53", original_query="TP53")))
        assert update["inferred_concept_types"] == ["GENE"]
        assert update["steps"][0]["agent"] == "ClassifyAgent"
        assert "by rules" in update["steps"][0]["detail"]

    def test_node_prefers_the_concept_type_filter(self):
        state = _state(
            query="TP53", original_query="TP53", concept_type_filter=["disease", "bogus"]
        )
        update = asyncio.run(classify_node(state))
        assert update["inferred_concept_types"] == ["DISEASE"]

    def test_node_falls_back_to_the_llm(self):
        llm = AsyncMock(return_value='Sure: ["gene", "PROTEIN", "nonsense", "UNKNOWN"]')
        state = _state(query="EGFR", original_query="EGFR")
        with patch("knowledge_lookup.agents.nodes.classify.call_llm", llm):
            update = asyncio.run(classify_node(state))
        assert update["inferred_concept_types"] == ["GENE", "PROTEIN"]
        assert "by LLM" in update["steps"][0]["detail"]

    def test_llm_calls_leave_room_for_reasoning_models(self):
        """A budget of tens of tokens makes reasoning models return no content at all."""
        from knowledge_lookup.agents.config import SHORT_REPLY_MAX_TOKENS

        llm = AsyncMock(return_value='["GENE"]')
        with patch("knowledge_lookup.agents.nodes.classify.call_llm", llm):
            asyncio.run(classify_node(_state(query="EGFR", original_query="EGFR")))
        assert llm.await_args.kwargs["max_tokens"] == SHORT_REPLY_MAX_TOKENS >= 500

        llm = AsyncMock(return_value='["fits"]')
        with patch.object(followup_mod, "call_llm", llm):
            asyncio.run(followup_mod.plan_probes(_state(lookup_result=_result([])), ["empty"]))
        assert llm.await_args.kwargs["max_tokens"] == SHORT_REPLY_MAX_TOKENS

    def test_node_without_llm_or_rule_infers_nothing(self):
        update = asyncio.run(classify_node(_state(query="COPD", original_query="COPD")))
        assert update["inferred_concept_types"] == []
        assert "No concept type inferred" in update["steps"][0]["detail"]

    def test_parse_llm_types_is_forgiving(self):
        assert _parse_llm_types(None) == []
        assert _parse_llm_types("no list here") == []
        assert _parse_llm_types("[not json]") == []
        assert _parse_llm_types('["DRUG","DRUG","GENE","PATHWAY","DISEASE"]') == [
            ConceptType.DRUG,
            ConceptType.GENE,
            ConceptType.PATHWAY,
        ]


# ---------------------------------------------------------------------------
# followup: diagnosis, planning, routing
# ---------------------------------------------------------------------------


class TestDiagnose:
    def test_empty(self):
        assert followup_mod.diagnose(_state(lookup_result=_result([]))) == ["empty"]
        assert followup_mod.diagnose(_state(lookup_result=None)) == ["empty"]

    def test_thin(self):
        state = _state(lookup_result=_result([_concept("a"), _concept("b")]))
        assert followup_mod.diagnose(state) == ["thin"]

    def test_healthy_results_have_no_gap(self):
        concepts = [_concept(f"c{i}") for i in range(4)]
        assert followup_mod.diagnose(_state(lookup_result=_result(concepts))) == []

    def test_failed_sources(self):
        concepts = [_concept(f"c{i}") for i in range(4)]
        result = _result(concepts, failed=[KnowledgeSource.HPO])
        assert followup_mod.diagnose(_state(lookup_result=result)) == ["failed_sources"]

    def test_single_source_only_counts_when_several_were_queried(self):
        concepts = [_concept(f"c{i}") for i in range(4)]
        several = _result(concepts, queried=[KnowledgeSource.OLS, KnowledgeSource.HPO])
        assert followup_mod.diagnose(_state(lookup_result=several)) == ["single_source"]
        # the caller chose one source: nothing to diversify
        one_choice = _state(lookup_result=several, source_filter=["OLS"])
        assert followup_mod.diagnose(one_choice) == []

    def test_thin_threshold_respects_a_small_max_results(self):
        state = _state(lookup_result=_result([_concept("a")]), max_results=1)
        assert followup_mod.diagnose(state) == []


class TestNeedsFollowup:
    def test_budget(self):
        thin = _result([_concept("a")])
        assert followup_mod.needs_followup(_state(lookup_result=thin))
        assert not followup_mod.needs_followup(_state(lookup_result=thin, max_auto_rounds=0))
        assert not followup_mod.needs_followup(_state(lookup_result=thin, auto_round=1))
        no_budget_key = _state(lookup_result=thin)
        del no_budget_key["max_auto_rounds"]
        assert not followup_mod.needs_followup(no_budget_key)  # old callers: loop is off

    def test_failed_run_is_left_alone(self):
        assert not followup_mod.needs_followup(_state(lookup_result=_result([]), status="failed"))

    def test_routing(self):
        assert route_after_detail_gather(_state(lookup_result=_result([]))) == "followup"
        healthy = _result([_concept(f"c{i}") for i in range(4)])
        assert route_after_detail_gather(_state(lookup_result=healthy)) == "enrichment"
        assert route_after_followup({"followup_pending": True}) == "lookup"  # type: ignore[arg-type]
        assert route_after_followup({"followup_pending": False}) == "enrichment"  # type: ignore[arg-type]
        assert route_after_followup({}) == "enrichment"  # type: ignore[arg-type]


class TestFollowupNode:
    def test_plans_synonyms_hierarchy_and_edges(self):
        concept = _concept(
            "Seizure",
            synonyms=["Fit", "Convulsion", "seizure"],  # last one is the query itself
            children=["Focal seizure"],
            parents=["http://x.org/bare-iri", "Neurological sign"],
        )
        edges = [
            {
                "source_concept_label": "Seizure",
                "relation_label": "associated_with",
                "related_name": "Epilepsy",
                "searched": False,
            },
            {"related_name": "Already searched", "searched": True},
            {"related_name": "", "related_id": "hsa:1", "searched": False},
        ]
        state = _state(lookup_result=_result([concept]), relationship_edges=edges)

        update = asyncio.run(followup_mod.followup_node(state))

        terms = [p["term"] for p in update["followup_probes"]]
        assert terms == [
            "Fit",
            "Convulsion",
            "Focal seizure",
            "Neurological sign",
            "Epilepsy",
        ]
        assert update["followup_pending"] is True
        assert update["auto_round"] == 1
        assert update["expanded_search_terms"][0] == "seizure"
        assert set(terms) <= set(update["expanded_search_terms"])  # remembered as tried
        assert update["steps"][0]["agent"] == "FollowupAgent"
        assert "thin" in update["steps"][0]["detail"]

    def test_never_repeats_a_tried_term_and_caps_the_round(self):
        concept = _concept("Seizure", synonyms=[f"syn {i}" for i in range(3)] + ["Already Tried"])
        many = [
            _concept(f"seizure variant {i}", synonyms=[f"extra {i}a", f"extra {i}b"])
            for i in range(4)
        ]
        state = _state(
            lookup_result=_result([concept, *many]),
            expanded_search_terms=["seizure", "already tried"],
        )
        probes = asyncio.run(followup_mod.plan_probes(state, ["thin"]))
        terms = [p["term"] for p in probes]
        assert "Already Tried" not in terms
        assert len(terms) == followup_mod.MAX_FOLLOWUP_TERMS

    def test_does_not_harvest_from_concepts_unrelated_to_the_query(self):
        state = _state(
            query="Dravet syndrome",
            original_query="Dravet syndrome",
            expanded_search_terms=["Dravet syndrome"],
            lookup_result=_result(
                [
                    _concept(
                        "Barrett syndrome", synonyms=["Barrett oesophagus"]
                    ),  # only 'syndrome'
                    _concept(
                        "Severe myoclonic epilepsy of infancy",
                        synonyms=["Dravet's syndrome", "SMEI"],
                    ),
                ]
            ),
        )
        probes = asyncio.run(followup_mod.plan_probes(state, ["thin"]))
        terms = [p["term"] for p in probes]
        assert "Barrett oesophagus" not in terms
        assert "SMEI" in terms  # reached through the synonym that matches the query

    def test_abbreviation_query_matches_its_long_form_through_a_synonym(self):
        concept = _concept(
            "Chronic obstructive pulmonary disease", synonyms=["COPD", "chronic bronchitis"]
        )
        state = _state(
            query="COPD",
            original_query="COPD",
            expanded_search_terms=["COPD"],
            lookup_result=_result([concept]),
        )
        terms = [p["term"] for p in asyncio.run(followup_mod.plan_probes(state, ["thin"]))]
        assert terms == ["chronic bronchitis"]

    def test_identifier_queries_are_not_filtered(self):
        state = _state(
            query="HP:0001250",
            original_query="HP:0001250",
            expanded_search_terms=["HP:0001250"],
            lookup_result=_result([_concept("Seizure", synonyms=["Fit"])]),
        )
        terms = [p["term"] for p in asyncio.run(followup_mod.plan_probes(state, ["thin"]))]
        assert terms == ["Fit"]

    def test_retries_failed_sources_within_the_callers_selection(self):
        concepts = [_concept(f"c{i}") for i in range(4)]
        result = _result(concepts, failed=[KnowledgeSource.HPO, KnowledgeSource.MONDO])
        state = _state(lookup_result=result, source_filter=["hpo", "ols"])

        probes = asyncio.run(followup_mod.plan_probes(state, ["failed_sources"]))

        assert probes == [
            {"term": "seizure", "sources": ["HPO"], "reason": "retry failed source(s) HPO"}
        ]

    def test_llm_suggestions_only_for_empty_or_thin_results(self):
        llm = AsyncMock(return_value='["fits", "Epileptic seizure", "seizure", "fits"]')
        with patch.object(followup_mod, "call_llm", llm):
            empty = asyncio.run(
                followup_mod.plan_probes(_state(lookup_result=_result([])), ["empty"])
            )
            healthy_gap = asyncio.run(
                followup_mod.plan_probes(
                    _state(
                        lookup_result=_result(
                            [_concept(f"c{i}") for i in range(4)], failed=[KnowledgeSource.HPO]
                        )
                    ),
                    ["failed_sources"],
                )
            )
        assert [p["term"] for p in empty] == ["fits", "Epileptic seizure"]
        assert all(p["reason"] == "LLM suggestion" for p in empty)
        assert all(p["reason"] != "LLM suggestion" for p in healthy_gap)
        assert llm.await_count == 1  # not asked for the failed-source gap

    def test_nothing_to_try_ends_the_loop(self):
        state = _state(lookup_result=_result([]))
        update = asyncio.run(followup_mod.followup_node(state))
        assert update["followup_pending"] is False
        assert update["followup_probes"] == []
        assert update["auto_round"] == 1
        assert update["steps"][0]["action"] == "no_action"
        assert route_after_followup({**state, **update}) == "enrichment"  # type: ignore[arg-type]

    def test_term_list_parsing(self):
        assert followup_mod._parse_term_list(None) == []
        assert followup_mod._parse_term_list("[broken") == []
        assert followup_mod._parse_term_list('x ["a", 3, " ", "b"]') == ["a", "b"]


# ---------------------------------------------------------------------------
# lookup: focused follow-up pass
# ---------------------------------------------------------------------------


def _fake_lookup(adapters, by_term, calls):
    async def search(query, concept_types=None, sources=None, max_results=50, parallel=True):
        calls.append((query, sources))
        result = LookupResult(query=query, sources_queried=sources or list(adapters))
        for concept in by_term.get(query, []):
            result.add_concepts([concept], KnowledgeSource.OLS)
        return result

    instance = MagicMock()
    instance.adapters = dict.fromkeys(adapters, object())
    instance.search_concepts = search
    instance.close = AsyncMock()
    return MagicMock(return_value=instance)


class TestFocusedLookup:
    def test_followup_pass_merges_into_existing_and_keeps_the_iteration(self):
        from knowledge_lookup.agents.nodes.lookup import lookup_node

        calls: list = []
        ckl = _fake_lookup(
            [KnowledgeSource.OLS, KnowledgeSource.HPO],
            {"Fit": [_concept("Fit disorder")]},
            calls,
        )
        state = _state(
            lookup_result=_result([_concept("Seizure")]),
            followup_pending=True,
            followup_probes=[
                {"term": "Fit", "sources": None, "reason": "synonym"},
                {"term": "seizure", "sources": ["HPO"], "reason": "retry"},
            ],
            auto_round=1,
            errors=["earlier warning"],
            iteration=1,
        )

        with patch("knowledge_lookup.agents.nodes.lookup.CentralKnowledgeLookup", ckl):
            update = asyncio.run(lookup_node(state))

        assert sorted(q for q, _ in calls) == ["Fit", "seizure"]  # only the probes
        assert dict(calls)["seizure"] == [KnowledgeSource.HPO]
        assert "iteration" not in update  # a follow-up does not use up max_iterations
        assert update["followup_pending"] is False
        assert update["followup_probes"] == []
        assert update["errors"][0] == "earlier warning"
        merged = dict_to_lookup_result(update["lookup_result"])
        assert merged is not None
        assert {c.primary_label for c in merged.concepts or []} == {"Seizure", "Fit disorder"}
        assert update["steps"][0]["action"] == "followup_search"

    def test_probe_sources_outside_the_callers_selection_are_ignored(self):
        from knowledge_lookup.agents.nodes.lookup import lookup_node

        calls: list = []
        ckl = _fake_lookup([KnowledgeSource.OLS], {}, calls)
        state = _state(
            lookup_result=_result([_concept("Seizure")]),
            source_filter=["OLS"],
            followup_pending=True,
            followup_probes=[{"term": "Fit", "sources": ["HPO", "bogus"], "reason": "x"}],
        )
        with patch("knowledge_lookup.agents.nodes.lookup.CentralKnowledgeLookup", ckl):
            asyncio.run(lookup_node(state))
        assert calls == [("Fit", [KnowledgeSource.OLS])]

    def test_a_normal_pass_is_unchanged(self):
        from knowledge_lookup.agents.nodes.lookup import lookup_node

        calls: list = []
        ckl = _fake_lookup([KnowledgeSource.OLS], {"seizure": [_concept("Seizure")]}, calls)
        state = _state(expanded_search_terms=["seizure"], iteration=0)
        with patch("knowledge_lookup.agents.nodes.lookup.CentralKnowledgeLookup", ckl):
            update = asyncio.run(lookup_node(state))
        assert update["iteration"] == 1
        assert update["steps"][0]["action"] == "search"
        assert "followup_pending" not in update


# ---------------------------------------------------------------------------
# expand: keeps relationship edges; refine: resets the follow-up budget
# ---------------------------------------------------------------------------


class TestExpandAndRefine:
    def test_expand_keeps_relationship_edges(self):
        from knowledge_lookup.agents.nodes.expand import expand_node
        from knowledge_lookup.core.term_expansion import ExpansionTrace

        edge = {
            "source_concept_id": "hsa:7157",
            "relation_label": "pathway",
            "related_id": "hsa04115",
            "related_name": "p53 signaling pathway",
            "searched": True,
        }
        trace = ExpansionTrace(
            run_id=None,
            rounds_run=1,
            stop_reason="fixed_point",
            terms_by_round=[["TP53"]],
            relationships=[edge],
        )
        state = _state(
            query="TP53",
            expanded_search_terms=["TP53"],
            relationship_edges=[{**edge, "searched": False}],
        )
        with (
            patch(
                "knowledge_lookup.agents.nodes.expand.expand_and_search",
                new=AsyncMock(return_value=(LookupResult(query="TP53"), trace)),
            ),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as ckl,
        ):
            ckl.return_value.close = AsyncMock()
            update = asyncio.run(expand_node(state))

        assert update["relationship_edges"] == [edge]  # merged, searched flag OR-ed
        assert "1 relationship edge" in update["steps"][0]["detail"]

    def test_expand_without_edges_does_not_touch_the_key(self):
        from knowledge_lookup.agents.nodes.expand import expand_node
        from knowledge_lookup.core.term_expansion import ExpansionTrace

        trace = ExpansionTrace(
            run_id=None, rounds_run=1, stop_reason="fixed_point", terms_by_round=[["a"]]
        )
        with (
            patch(
                "knowledge_lookup.agents.nodes.expand.expand_and_search",
                new=AsyncMock(return_value=(LookupResult(query="a"), trace)),
            ),
            patch("knowledge_lookup.agents.nodes.expand.CentralKnowledgeLookup") as ckl,
        ):
            ckl.return_value.close = AsyncMock()
            update = asyncio.run(expand_node(_state(query="a", expanded_search_terms=["a"])))
        assert "relationship_edges" not in update

    def test_refine_restarts_the_followup_budget(self):
        from knowledge_lookup.agents.nodes.refine import refine_node

        state = _state(
            refinement_notes=["focal"], auto_round=1, followup_pending=True, iteration=1
        )
        update = asyncio.run(refine_node(state))
        assert update["auto_round"] == 0
        assert update["followup_pending"] is False
        assert update["followup_probes"] == []

    def test_merge_edges(self):
        a = {"source_concept_id": "1", "relation_label": "Pathway", "related_id": "x"}
        b = {**a, "relation_label": "pathway", "searched": True}
        c = {"source_concept_id": "1", "relation_label": "pathway", "related_id": "y"}
        merged = merge_edges([a], [b, c])
        assert len(merged) == 2
        assert merged[0]["searched"] is True
        assert merged[1] == c


# ---------------------------------------------------------------------------
# relationships
# ---------------------------------------------------------------------------


class TestRelationshipsNode:
    def test_off_by_default(self):
        from knowledge_lookup.agents.nodes.relationships import relationships_node

        update = asyncio.run(relationships_node(_state(lookup_result=_result([_concept("a")]))))
        assert update["steps"][0]["action"] == "skip"
        assert "relationship_edges" not in update

    def test_skips_when_no_concept_has_a_relationship_source(self):
        from knowledge_lookup.agents.nodes.relationships import relationships_node

        concept = _concept("a", sources=[KnowledgeSource.HPO])
        state = _state(include_relationships=True, lookup_result=_result([concept]))
        update = asyncio.run(relationships_node(state))
        assert update["steps"][0]["action"] == "skip"
        assert "relationship-capable" in update["steps"][0]["detail"]

    def test_harvests_edges_including_identifier_only_sources(self):
        from knowledge_lookup.agents.nodes.relationships import (
            concept_sources,
            relationships_node,
        )
        from knowledge_lookup.core.term_expansion import RelatedTerm

        concept = _concept(
            "TP53",
            cid="hsa:7157",
            sources=[KnowledgeSource.KEGG],
            identifiers=[
                ConceptIdentifier(source=KnowledgeSource.STRING, identifier="TP53", label="TP53")
            ],
        )
        assert concept_sources(concept) == {KnowledgeSource.KEGG, KnowledgeSource.STRING}

        built: dict[str, Any] = {}

        def fake_ckl(config, auto_initialize):
            built["sources"] = config.enabled_sources
            instance = MagicMock()
            instance.close = AsyncMock()
            return instance

        class FakeHarvester:
            def __init__(self, lookup, **kwargs):
                built["kwargs"] = kwargs

            async def expand(self, c):
                return [
                    RelatedTerm(
                        "p53 signaling pathway", ConceptType.PATHWAY, "pathway", "hsa04115"
                    ),
                    RelatedTerm("", None, "interaction", "ENSP1"),
                ]

        state = _state(
            include_relationships=True,
            lookup_result=_result([concept]),
            relationship_edges=[{"source_concept_id": "old", "related_id": "o"}],
        )
        with (
            patch(
                "knowledge_lookup.agents.nodes.relationships.CentralKnowledgeLookup",
                MagicMock(side_effect=fake_ckl),
            ),
            patch(
                "knowledge_lookup.agents.nodes.relationships.AdapterRelationshipSource",
                FakeHarvester,
            ),
        ):
            update = asyncio.run(relationships_node(state))

        assert set(built["sources"]) == {KnowledgeSource.KEGG, KnowledgeSource.STRING}
        assert built["kwargs"]["include_identifier_sources"] is True
        edges = update["relationship_edges"]
        assert len(edges) == 3  # the existing edge plus two new ones
        new = edges[1]
        assert new["source_concept_label"] == "TP53"
        assert new["related_name"] == "p53 signaling pathway"
        assert new["concept_type"] == "PATHWAY"
        assert edges[2]["related_name"] is None
        assert "2 new edge(s) (1 with a named target)" in update["steps"][0]["detail"]

    def test_adapter_source_can_include_identifier_sources(self):
        from knowledge_lookup.core.term_expansion import AdapterRelationshipSource

        string_adapter = MagicMock()
        string_adapter.get_relationships = AsyncMock(
            return_value=[
                {"related_id": "EGFR", "related_name": "EGFR", "relation_label": "interaction"}
            ]
        )
        lookup = MagicMock(adapters={KnowledgeSource.STRING: string_adapter})
        concept = _concept(
            "TP53",
            sources=[KnowledgeSource.KEGG],
            identifiers=[
                ConceptIdentifier(source=KnowledgeSource.STRING, identifier="TP53", label="TP53")
            ],
        )
        default = asyncio.run(AdapterRelationshipSource(lookup).expand(concept))
        widened = asyncio.run(
            AdapterRelationshipSource(lookup, include_identifier_sources=True).expand(concept)
        )
        assert default == []
        assert [t.term for t in widened] == ["EGFR"]
        string_adapter.get_relationships.assert_awaited_once_with("TP53")


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


class TestEvidenceNode:
    def test_off_by_default(self):
        from knowledge_lookup.agents.nodes.evidence import evidence_node

        update = asyncio.run(evidence_node(_state(lookup_result=_result([_concept("a")]))))
        assert update["steps"][0]["action"] == "skip"
        assert "literature_evidence" not in update

    def test_attaches_papers(self):
        from knowledge_lookup.agents.nodes.evidence import evidence_node

        paper = _concept("Seizure outcomes in children", cid="PMID:1")
        paper.categories = ["journal:Brain", "year:2021", "authors:Doe J"]
        queries: list[str] = []

        async def search(query, sources, max_results, parallel):
            queries.append(query)
            return LookupResult(query=query, concepts=[paper] if "Seizure" in query else [])

        instance = MagicMock(adapters={KnowledgeSource.EUROPEPMC: object()})
        instance.search_concepts = search
        instance.close = AsyncMock()
        state = _state(
            include_evidence=True,
            lookup_result=_result([_concept("Seizure"), _concept("Other")]),
        )
        with patch(
            "knowledge_lookup.agents.nodes.evidence.CentralKnowledgeLookup",
            MagicMock(return_value=instance),
        ):
            update = asyncio.run(evidence_node(state))

        assert sorted(queries) == ['"Other"', '"Seizure"']
        assert update["literature_evidence"] == [
            {
                "concept": "Seizure",
                "concept_id": "http://test.org/seizure",
                "papers": [
                    {
                        "id": "PMID:1",
                        "title": "Seizure outcomes in children",
                        "year": "2021",
                        "journal": "Brain",
                    }
                ],
            }
        ]
        assert "1 paper(s) for 1/2 concept(s)" in update["steps"][0]["detail"]

    def test_skips_when_europepmc_is_unavailable(self):
        from knowledge_lookup.agents.nodes.evidence import evidence_node

        instance = MagicMock(adapters={})
        instance.close = AsyncMock()
        state = _state(include_evidence=True, lookup_result=_result([_concept("a")]))
        with patch(
            "knowledge_lookup.agents.nodes.evidence.CentralKnowledgeLookup",
            MagicMock(return_value=instance),
        ):
            update = asyncio.run(evidence_node(state))
        assert update["steps"][0]["action"] == "skip"


# ---------------------------------------------------------------------------
# reporting: aggregate + export
# ---------------------------------------------------------------------------


class TestReporting:
    def test_aggregate_shows_edges_and_evidence_to_the_reviewer(self):
        from knowledge_lookup.agents.nodes.aggregate import aggregate_node

        state = _state(
            lookup_result=_result([_concept("TP53")]),
            relationship_edges=[
                {
                    "source_concept_label": "TP53",
                    "relation_label": "pathway",
                    "related_name": "p53 signaling pathway",
                    "related_source": "KEGG",
                }
            ],
            literature_evidence=[
                {
                    "concept": "TP53",
                    "papers": [{"title": "p53 review", "year": "2020", "journal": "Cell"}],
                }
            ],
        )
        context = asyncio.run(aggregate_node(state))["aggregated_context"]
        assert "## Relationship Network (1 edge(s))" in context
        assert "TP53 --pathway--> p53 signaling pathway [KEGG]" in context
        assert "## Literature Evidence (Europe PMC)" in context
        assert "p53 review (Cell, 2020)" in context

    def test_aggregate_is_unchanged_without_the_new_data(self):
        from knowledge_lookup.agents.nodes.aggregate import aggregate_node

        context = asyncio.run(aggregate_node(_state(lookup_result=_result([_concept("a")]))))[
            "aggregated_context"
        ]
        assert "Relationship Network" not in context
        assert "Literature Evidence" not in context

    def test_json_export_carries_the_expansion_output(self, tmp_path):
        from knowledge_lookup.agents.nodes.export import export_node

        edges = [{"source_concept_label": "TP53", "related_name": "x"}]
        state = _state(
            lookup_result=_result([_concept("TP53")]),
            export_path=str(tmp_path),
            inferred_concept_types=["GENE"],
            auto_round=1,
            relationship_edges=edges,
            literature_evidence=[{"concept": "TP53", "papers": []}],
        )
        update = asyncio.run(export_node(state))
        data = json.loads(open(update["export_paths"][0]).read())
        assert data["expansion"]["inferred_concept_types"] == ["GENE"]
        assert data["expansion"]["auto_rounds"] == 1
        assert data["expansion"]["relationship_edges"] == edges


# ---------------------------------------------------------------------------
# the compiled graph
# ---------------------------------------------------------------------------


@pytest.fixture
def stubbed_graph(monkeypatch):
    """Graph whose network nodes are stubs: the first lookup is thin, a follow-up adds more."""
    from knowledge_lookup.agents import graph as graph_module

    lookups: list[dict[str, Any]] = []

    async def passthrough(state):
        return {"steps": [make_step("Stub", "noop")]}

    async def fake_lookup(state):
        followup = bool(state.get("followup_pending"))
        lookups.append({"followup": followup, "probes": state.get("followup_probes")})
        concepts = [_concept("Seizure", synonyms=["Fit", "Convulsion"])]
        if followup:
            concepts += [_concept(f"Related {i}") for i in range(3)]
        update: dict[str, Any] = {
            "lookup_result": _result(concepts),
            "status": "searching",
            "steps": [make_step("Stub", "lookup")],
        }
        if followup:
            update["followup_pending"] = False
            update["followup_probes"] = []
        else:
            update["iteration"] = state["iteration"] + 1
        return update

    for name in ("expand_node", "detail_gather_node", "enrichment_node"):
        monkeypatch.setattr(graph_module, name, passthrough)
    monkeypatch.setattr(graph_module, "lookup_node", fake_lookup)
    return lookups


class TestGraph:
    def test_graph_has_the_new_nodes_and_loop(self):
        from knowledge_lookup.agents.graph import build_workflow_graph

        graph = build_workflow_graph().get_graph()
        names = set(graph.nodes)
        assert {"classify", "followup", "relationships", "evidence"} <= names
        edges = {(e.source, e.target) for e in graph.edges}
        assert ("quality_gate", "followup") not in edges  # the decision comes after detail_gather
        assert ("quality_gate", "detail_gather") in edges
        assert ("detail_gather", "followup") in edges
        assert ("detail_gather", "enrichment") in edges
        assert ("followup", "lookup") in edges
        assert ("followup", "enrichment") in edges
        assert ("enrichment", "relationships") in edges
        assert ("relationships", "evidence") in edges

    def test_thin_results_trigger_one_autonomous_followup(self, stubbed_graph, tmp_path):
        from knowledge_lookup.agents.runners import run_workflow

        result = asyncio.run(
            run_workflow("seizure", export_path=str(tmp_path), auto_approve_threshold=0.0)
        )

        assert result["status"] == "completed"
        assert [x["followup"] for x in stubbed_graph] == [False, True]
        assert {p["term"] for p in stubbed_graph[1]["probes"]} == {"Fit", "Convulsion"}
        assert result["auto_rounds"] == 1
        assert result["iteration"] == 1  # the follow-up did not use up max_iterations
        assert result["inferred_concept_types"] == ["SYMPTOM"]
        agents = [s["agent"] for s in result["steps"]]
        assert agents.count("FollowupAgent") == 1
        assert agents.index("ClassifyAgent") < agents.index("FollowupAgent")
        # the planner runs after cross-referencing, which runs again after the follow-up
        assert agents.index("FollowupAgent") > agents.index("Stub")  # detail_gather stub ran first
        assert agents.count("Stub") >= 4
        assert len(result["result"].concepts) == 4

    def test_max_auto_rounds_zero_disables_the_loop(self, stubbed_graph, tmp_path):
        from knowledge_lookup.agents.runners import run_workflow

        result = asyncio.run(
            run_workflow(
                "seizure",
                export_path=str(tmp_path),
                auto_approve_threshold=0.0,
                max_auto_rounds=0,
            )
        )
        assert [x["followup"] for x in stubbed_graph] == [False]
        assert result["auto_rounds"] == 0
        assert "FollowupAgent" not in [s["agent"] for s in result["steps"]]

    def test_initial_state_defaults(self):
        from knowledge_lookup.agents.runners import _initial_state

        state = _initial_state(
            "q",
            max_results=5,
            sources=None,
            concept_types=None,
            export_formats=None,
            export_path=None,
            max_iterations=3,
            auto_approve_threshold=0.8,
        )
        assert state["max_auto_rounds"] == 1
        assert state["auto_round"] == 0
        assert state["xref_labels"] == []
        assert state["include_evidence"] is False
        assert state["relationship_edges"] == []
        assert state["literature_evidence"] == []
        assert state["inferred_concept_types"] == []
