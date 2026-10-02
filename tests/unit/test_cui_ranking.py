"""Tests for choosing and ordering a concept's UMLS CUI.

The workflow used to report an arbitrary CUI: cross-referenced ids were collected in
sets (a different iteration order every run) and the review kept the *last* UMLS
identifier. The first UMLS identifier is now the preferred one and the order is fixed.
"""

from __future__ import annotations

import asyncio
import itertools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_lookup.agents.nodes._cui import preferred_umls_cui, rank_umls_identifiers
from knowledge_lookup.agents.nodes.detail_gather import best_label_hit
from knowledge_lookup.agents.state import dict_to_lookup_result, lookup_result_to_dict
from knowledge_lookup.models import (
    ConceptIdentifier,
    KnowledgeSource,
    LookupResult,
    UnifiedConcept,
)

U = KnowledgeSource.UMLS


def _ident(cui: str, label: str | None = None, source: KnowledgeSource = U) -> ConceptIdentifier:
    return ConceptIdentifier(source=source, identifier=cui, label=label)


def _concept(label: str, identifiers: list[ConceptIdentifier]) -> UnifiedConcept:
    concept = UnifiedConcept(
        primary_id=f"http://test.org/{label}",
        primary_label=label,
        confidence_score=0.8,
        sources=[KnowledgeSource.OLS],
    )
    concept.identifiers = identifiers
    return concept


def _umls_ids(concept: UnifiedConcept) -> list[str]:
    return [i.identifier for i in concept.identifiers or [] if i.source == U]


class TestPreferredUmlsCui:
    def test_first_umls_identifier_as_a_bare_cui(self):
        idents = [_ident("X1", source=KnowledgeSource.OLS), _ident("UMLS:C0079419"), _ident("C2")]
        assert preferred_umls_cui(idents) == "C0079419"

    def test_serialized_dicts_work_too(self):
        dicts = [{"source": "OLS", "identifier": "x"}, {"source": "UMLS", "identifier": "umls:C1"}]
        assert preferred_umls_cui(dicts) == "C1"

    @pytest.mark.parametrize("identifiers", [None, [], [_ident("X", source=KnowledgeSource.OLS)]])
    def test_none_without_a_umls_identifier(self, identifiers):
        assert preferred_umls_cui(identifiers) is None


class TestRankUmlsIdentifiers:
    def test_own_record_beats_the_label_hit_beats_the_rest(self):
        concept = _concept(
            "TP53",
            [_ident("C0000009"), _ident("C0000005", "TP53"), _ident("C0000002")],
        )
        rank_umls_identifiers(concept, hit_cui="C0000007", hit_label="TP53 gene")
        assert _umls_ids(concept) == ["C0000005", "C0000007", "C0000002", "C0000009"]

    def test_label_hit_comes_first_when_the_concept_has_no_record_of_its_own(self):
        concept = _concept("TP53", [_ident("C0000009"), _ident("C0000002")])
        rank_umls_identifiers(concept, hit_cui="C0000007", hit_label="Tumor protein p53")
        assert _umls_ids(concept) == ["C0000007", "C0000002", "C0000009"]
        added = concept.identifiers[0]
        assert added.label == "Tumor protein p53"
        assert added.url.endswith("/C0000007")

    def test_hit_is_added_even_when_the_concept_had_no_umls_identifier(self):
        concept = _concept("TP53", [_ident("OLS:1", source=KnowledgeSource.OLS)])
        rank_umls_identifiers(concept, hit_cui="C1", hit_label="TP53")
        assert [i.source for i in concept.identifiers] == [KnowledgeSource.OLS, U]
        assert preferred_umls_cui(concept.identifiers) == "C1"

    def test_order_does_not_depend_on_the_input_order(self):
        cuis = ["C0000003", "C0000001", "C0000002", "C0000004"]
        results = set()
        for perm in itertools.permutations(cuis):
            concept = _concept("x", [_ident(c) for c in perm])
            rank_umls_identifiers(concept)
            results.add(tuple(_umls_ids(concept)))
        assert results == {tuple(sorted(cuis))}

    def test_curie_forms_are_normalised_and_deduplicated(self):
        concept = _concept("x", [_ident("UMLS:C1"), _ident("C1"), _ident("umls:C2")])
        rank_umls_identifiers(concept)
        assert _umls_ids(concept) == ["C1", "C2"]

    def test_is_idempotent_and_keeps_other_sources_first(self):
        concept = _concept(
            "x", [_ident("C2"), _ident("A", source=KnowledgeSource.OLS), _ident("C1")]
        )
        rank_umls_identifiers(concept, hit_cui="C2", hit_label="x")
        first = [(i.source, i.identifier) for i in concept.identifiers]
        rank_umls_identifiers(concept, hit_cui="C2", hit_label="x")
        assert [(i.source, i.identifier) for i in concept.identifiers] == first
        assert first[0] == (KnowledgeSource.OLS, "A")

    def test_unlabelled_cross_references_are_never_mistaken_for_the_concepts_own_record(self):
        concept = _concept("TP53", [_ident("C0000001", None), _ident("C0000009", "TP53")])
        rank_umls_identifiers(concept)
        assert _umls_ids(concept)[0] == "C0000009"


class TestBestLabelHit:
    @staticmethod
    def _hit(label, cid):
        return MagicMock(primary_label=label, primary_id=cid)

    def test_prefers_an_exact_label_match_over_search_rank(self):
        hits = [self._hit("TP53 gene", "C1"), self._hit("  tp53 ", "C2")]
        assert best_label_hit("TP53", hits).primary_id == "C2"

    def test_falls_back_to_the_top_hit_and_skips_hits_without_an_id(self):
        hits = [
            self._hit("noise", None),
            self._hit("Tumor protein p53", "C3"),
            self._hit("x", "C4"),
        ]
        assert best_label_hit("TP53", hits).primary_id == "C3"
        assert best_label_hit("TP53", []) is None


class TestDetailGatherPicksTheUmlsMatch:
    @staticmethod
    def _run(xref_order, umls_hits):
        from knowledge_lookup.agents.nodes.detail_gather import detail_gather_node

        async def search(query, sources, **kwargs):
            source = sources[0]
            if source == U:
                found = []
                for label, cui in umls_hits:
                    c = UnifiedConcept(primary_id=cui, primary_label=label, sources=[U])
                    c.identifiers = [_ident(cui, label)]
                    found.append(c)
                return LookupResult(query=query, concepts=found)
            if source == KnowledgeSource.OLS:
                c = UnifiedConcept(
                    primary_id="http://x/ols", primary_label="TP53 (OLS)", sources=[source]
                )
                c.identifiers = [_ident(f"UMLS:{cui}") for cui in xref_order]
                return LookupResult(query=query, concepts=[c])
            return LookupResult(query=query)

        instance = MagicMock()
        instance.search_concepts = search
        instance.close = AsyncMock()

        def factory(config, auto_initialize):
            instance.adapters = dict.fromkeys(config.enabled_sources or [], object())
            return instance

        concept = UnifiedConcept(
            primary_id="HGNC:11998", primary_label="TP53", sources=[KnowledgeSource.HGNC]
        )
        concept.concept_type = "GENE"
        base = LookupResult(query="TP53")
        base.concepts = [concept]
        state = {
            "query": "TP53",
            "max_results": 5,
            "lookup_result": lookup_result_to_dict(base),
            "steps": [],
        }
        with patch(
            "knowledge_lookup.agents.nodes.detail_gather.CentralKnowledgeLookup",
            MagicMock(side_effect=factory),
        ):
            update = asyncio.run(detail_gather_node(state))
        return dict_to_lookup_result(update["lookup_result"]).concepts[0]

    def test_exact_label_umls_hit_wins_over_cross_referenced_cuis(self):
        concept = self._run(
            xref_order=["C0000009", "C0000001", "C0000005"],
            umls_hits=[("TP53 gene", "C0000002"), ("TP53", "C0000007")],
        )
        assert preferred_umls_cui(concept.identifiers) == "C0000007"
        assert _umls_ids(concept)[1:] == ["C0000001", "C0000002", "C0000005", "C0000009"]

    def test_the_same_cui_whatever_order_the_sources_answered_in(self):
        picks = {
            tuple(
                _umls_ids(
                    self._run(
                        xref_order=list(perm),
                        umls_hits=[("TP53", "C0000007")],
                    )
                )
            )
            for perm in itertools.permutations(["C0000009", "C0000001", "C0000005"])
        }
        assert len(picks) == 1
        assert next(iter(picks))[0] == "C0000007"


class TestConsumersAgree:
    def _result(self):
        concept = _concept("TP53", [_ident("UMLS:C0000007", "TP53"), _ident("C0000009")])
        result = LookupResult(query="TP53")
        result.concepts = [concept]
        return result

    def test_review_concept_map_takes_the_preferred_cui_not_the_last_one(self):
        from knowledge_lookup.agents.nodes.review import _rule_based_concept_map

        concept_map, _ = _rule_based_concept_map(self._result())
        assert concept_map[0]["umls_cui"] == "C0000007"

    def test_export_helpers_agree(self):
        from knowledge_lookup.agents.nodes.export import _get_umls_cui, _get_umls_cui_from_dict

        result = self._result()
        concept = result.concepts[0]
        assert _get_umls_cui(concept) == "C0000007"
        assert _get_umls_cui_from_dict(concept.model_dump(mode="json")) == "C0000007"

    def test_aggregate_agrees(self):
        from knowledge_lookup.agents.nodes.aggregate import _build_concept_report

        report = _build_concept_report(self._result().concepts[0], 1)
        assert "UMLS CUI:    C0000007" in report
