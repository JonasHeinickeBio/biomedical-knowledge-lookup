"""Unit tests for iterative term expansion (synonyms + abbreviation/long-form).

All tests mock `CentralKnowledgeLookup.search_concepts` — no real network
calls — following the same approach as the rest of this test suite's
adapter-boundary mocks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge_lookup.core.expansion_store import (
    ORIGIN_ABBREVIATION,
    ORIGIN_LONG_FORM,
    ORIGIN_ORIGINAL,
    ORIGIN_SYNONYM,
    STOP_FIXED_POINT,
    STOP_MAX_ROUNDS,
    ExpansionStore,
)
from knowledge_lookup.core.term_expansion import (
    expand_and_search,
    merge_concept_fields,
    merge_concept_results,
)
from knowledge_lookup.models import KnowledgeSource, LookupResult, UnifiedConcept

pytestmark = pytest.mark.unit


def _concept(
    label: str, synonyms: list[str] | None = None, concept_id: str | None = None
) -> UnifiedConcept:
    c = UnifiedConcept(
        primary_id=concept_id or f"id:{label.lower().replace(' ', '_')}",
        primary_label=label,
        sources=[KnowledgeSource.OLS],
    )
    if synonyms:
        c.synonyms = list(synonyms)
    return c


def _result(query: str, concepts: list[UnifiedConcept]) -> LookupResult:
    r = LookupResult(query=query)
    r.concepts = concepts
    r.sources_succeeded = [KnowledgeSource.OLS]
    r.execution_time = 0.01
    return r


def _mock_lookup(search_side_effect) -> MagicMock:
    """A CentralKnowledgeLookup stand-in with a mocked search_concepts()."""
    lookup = MagicMock()
    lookup.search_concepts = AsyncMock(side_effect=search_side_effect)
    lookup.adapters = {KnowledgeSource.OLS: MagicMock()}
    lookup.config = MagicMock()
    return lookup


class TestMergeHelpers:
    def test_merge_concept_results_dedupes_by_label(self):
        target: list = [_concept("Diabetes")]
        merge_concept_results(target, [_concept("diabetes")])  # case-insensitive dup
        assert len(target) == 1

    def test_merge_concept_results_keeps_distinct_labels(self):
        target: list = [_concept("Diabetes")]
        merge_concept_results(target, [_concept("Hypertension")])
        assert len(target) == 2

    def test_merge_concept_fields_merges_synonyms_case_insensitively(self):
        target = _concept("Diabetes", synonyms=["DM"])
        source = _concept("Diabetes", synonyms=["dm", "Diabetes Mellitus"])
        merge_concept_fields(target, source)
        assert target.synonyms == ["DM", "Diabetes Mellitus"]

    def test_merge_concept_fields_merges_identifiers_without_duplicating(self):
        target = _concept("Diabetes")
        target.add_identifier(KnowledgeSource.MONDO, "MONDO:1")
        source = _concept("Diabetes")
        source.add_identifier(KnowledgeSource.MONDO, "MONDO:1")  # duplicate
        source.add_identifier(KnowledgeSource.UMLS, "C0011849")
        merge_concept_fields(target, source)
        assert len(target.identifiers) == 2


class TestExpandAndSearch:
    @pytest.mark.asyncio
    async def test_round_zero_only_when_no_synonyms_found(self):
        lookup = _mock_lookup(lambda query, **kw: _result(query, [_concept("Plain result")]))

        result, trace = await expand_and_search(
            lookup, "plain term", abbreviation_sources=[], persist=False
        )

        assert lookup.search_concepts.await_count == 1
        assert trace.rounds_run == 1
        assert trace.stop_reason == STOP_FIXED_POINT
        assert trace.terms_by_round == [["plain term"]]
        assert len(result.concepts or []) == 1

    @pytest.mark.asyncio
    async def test_discovers_synonym_and_searches_next_round(self):
        async def side_effect(query, **kw):
            if query == "copd":
                return _result(
                    query, [_concept("COPD", synonyms=["chronic obstructive pulmonary disease"])]
                )
            return _result(query, [_concept("Chronic obstructive pulmonary disease")])

        lookup = _mock_lookup(side_effect)

        result, trace = await expand_and_search(
            lookup, "copd", abbreviation_sources=[], persist=False
        )

        assert trace.rounds_run == 2
        assert trace.terms_by_round[0] == ["copd"]
        assert trace.terms_by_round[1] == ["chronic obstructive pulmonary disease"]
        # different labels -> two distinct concepts kept (merge_concept_results
        # only collapses exact-label duplicates, not semantically-equivalent ones)
        assert len(result.concepts or []) == 2

    @pytest.mark.asyncio
    async def test_stops_at_max_rounds_even_with_more_to_discover(self):
        call_count = 0

        async def side_effect(query, **kw):
            nonlocal call_count
            call_count += 1
            # every result offers a brand-new synonym, so this would never
            # reach a fixed point on its own
            return _result(
                query, [_concept(f"concept {call_count}", synonyms=[f"synonym {call_count}"])]
            )

        lookup = _mock_lookup(side_effect)

        _, trace = await expand_and_search(
            lookup, "start", max_rounds=2, abbreviation_sources=[], persist=False
        )

        assert trace.rounds_run == 2
        assert trace.stop_reason == STOP_MAX_ROUNDS

    @pytest.mark.asyncio
    async def test_already_tried_terms_are_not_repeated(self):
        async def side_effect(query, **kw):
            # every round "discovers" the original query again as a synonym
            return _result(query, [_concept(query, synonyms=["start"])])

        lookup = _mock_lookup(side_effect)

        _, trace = await expand_and_search(lookup, "start", abbreviation_sources=[], persist=False)

        assert lookup.search_concepts.await_count == 1
        assert trace.stop_reason == STOP_FIXED_POINT

    @pytest.mark.asyncio
    async def test_max_terms_per_round_caps_fan_out(self):
        async def side_effect(query, **kw):
            if query == "seed":
                synonyms = [f"term{i}" for i in range(20)]
                return _result(query, [_concept("Seed concept", synonyms=synonyms)])
            return _result(query, [_concept(f"result for {query}")])

        lookup = _mock_lookup(side_effect)

        _, trace = await expand_and_search(
            lookup,
            "seed",
            max_rounds=2,
            max_terms_per_round=3,
            abbreviation_sources=[],
            persist=False,
        )

        assert len(trace.terms_by_round[1]) == 3

    @pytest.mark.asyncio
    async def test_abbreviation_source_contributes_terms(self):
        class StubAbbreviationSource:
            async def expand(self, term: str) -> list[tuple[str, str]]:
                if term == "COPD":
                    return [("chronic obstructive pulmonary disease", ORIGIN_LONG_FORM)]
                return []

        async def side_effect(query, **kw):
            if query == "COPD":
                return _result(query, [_concept("COPD")])
            return _result(query, [_concept("Chronic obstructive pulmonary disease")])

        lookup = _mock_lookup(side_effect)

        _, trace = await expand_and_search(
            lookup, "COPD", abbreviation_sources=[StubAbbreviationSource()], persist=False
        )

        assert trace.terms_by_round[1] == ["chronic obstructive pulmonary disease"]

    @pytest.mark.asyncio
    async def test_abbreviation_candidates_are_stored_but_never_searched(self):
        """A discovered abbreviation (origin=ORIGIN_ABBREVIATION) must never
        be fed back into a search — short abbreviations are prone to
        colliding with unrelated concepts (e.g. "PEM" -> pemphigoid instead
        of post-exertional malaise) — but it must still be recorded for the
        durable audit trail."""

        class StubAbbreviationSource:
            async def expand(self, term: str) -> list[tuple[str, str]]:
                if term == "Post-Exertional Malaise":
                    return [("PEM", ORIGIN_ABBREVIATION)]
                return []

        lookup = _mock_lookup(
            lambda query, **kw: _result(query, [_concept("Post-Exertional Malaise")])
        )

        result, trace = await expand_and_search(
            lookup,
            "post-exertional malaise",
            abbreviation_sources=[StubAbbreviationSource()],
            persist=False,
        )

        # Only round 0 (the original query) is ever searched — "PEM" is
        # never turned into a search.
        assert lookup.search_concepts.await_count == 1
        assert trace.rounds_run == 1
        assert trace.stop_reason == STOP_FIXED_POINT
        assert "pem" not in [t.lower() for t in trace.all_terms_tried]
        assert len(result.concepts or []) == 1

    @pytest.mark.asyncio
    async def test_abbreviation_candidates_are_persisted_despite_not_searched(self, tmp_path):
        store = ExpansionStore(tmp_path / "history.db")

        class StubAbbreviationSource:
            async def expand(self, term: str) -> list[tuple[str, str]]:
                if term == "Post-Exertional Malaise":
                    return [("PEM", ORIGIN_ABBREVIATION)]
                return []

        lookup = _mock_lookup(
            lambda query, **kw: _result(query, [_concept("Post-Exertional Malaise")])
        )

        _, trace = await expand_and_search(
            lookup,
            "post-exertional malaise",
            abbreviation_sources=[StubAbbreviationSource()],
            store=store,
        )

        terms = store.get_terms(trace.run_id)
        assert [(t["term"], t["origin"]) for t in terms] == [
            ("post-exertional malaise", ORIGIN_ORIGINAL),
            ("PEM", ORIGIN_ABBREVIATION),
        ]

    @pytest.mark.asyncio
    async def test_a_failing_search_does_not_abort_the_round(self):
        async def side_effect(query, **kw):
            if query == "bad":
                raise RuntimeError("boom")
            return _result(query, [_concept("ok")])

        lookup = _mock_lookup(side_effect)
        lookup.adapters = {KnowledgeSource.OLS: MagicMock()}

        # round 0 = ["bad"], which raises; expansion should still finish cleanly
        result, trace = await expand_and_search(
            lookup, "bad", abbreviation_sources=[], persist=False
        )

        assert trace.stop_reason == STOP_FIXED_POINT
        assert result.errors  # the failure was recorded, not swallowed silently

    @pytest.mark.asyncio
    async def test_persists_every_round_to_the_store(self, tmp_path):
        store = ExpansionStore(tmp_path / "history.db")

        async def side_effect(query, **kw):
            if query == "mi":
                return _result(query, [_concept("MI", synonyms=["myocardial infarction"])])
            return _result(query, [_concept("Myocardial infarction")])

        lookup = _mock_lookup(side_effect)

        _, trace = await expand_and_search(lookup, "mi", abbreviation_sources=[], store=store)

        assert trace.run_id is not None
        run = store.get_run(trace.run_id)
        assert run["original_query"] == "mi"
        assert run["stop_reason"] == STOP_FIXED_POINT

        terms = store.get_terms(trace.run_id)
        assert [(t["term"], t["origin"]) for t in terms] == [
            ("mi", ORIGIN_ORIGINAL),
            ("myocardial infarction", ORIGIN_SYNONYM),
        ]

    @pytest.mark.asyncio
    async def test_persist_false_does_not_touch_the_store(self, tmp_path):
        db_path = tmp_path / "should_not_exist.db"
        lookup = _mock_lookup(lambda query, **kw: _result(query, [_concept("x")]))

        _, trace = await expand_and_search(lookup, "x", abbreviation_sources=[], persist=False)

        assert trace.run_id is None
        assert not db_path.exists()


class _RecordingAbbreviationSource:
    """Records every label it is asked about and how many calls overlap."""

    def __init__(self, delay: float = 0.0) -> None:
        self.asked: list[str] = []
        self.delay = delay
        self.in_flight = 0
        self.peak = 0

    async def expand(self, term: str) -> list[tuple[str, str]]:
        import asyncio

        self.asked.append(term)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        await asyncio.sleep(self.delay)
        self.in_flight -= 1
        return []


def _lookup_finding(n_concepts: int) -> MagicMock:
    return _mock_lookup(
        lambda query, **kw: _result(query, [_concept(f"concept {i}") for i in range(n_concepts)])
    )


class TestAbbreviationLookupBounds:
    """Regression: every concept was sent to the abbreviation source, one at a time, uncapped."""

    @pytest.mark.asyncio
    async def test_lookups_per_round_are_capped(self):
        source = _RecordingAbbreviationSource()

        await expand_and_search(
            _lookup_finding(30),
            "seed",
            abbreviation_sources=[source],
            max_abbreviation_lookups=4,
            persist=False,
        )

        assert source.asked == ["concept 0", "concept 1", "concept 2", "concept 3"]

    @pytest.mark.asyncio
    async def test_default_cap(self):
        from knowledge_lookup.core.term_expansion import DEFAULT_MAX_ABBREVIATION_LOOKUPS

        source = _RecordingAbbreviationSource()

        await expand_and_search(
            _lookup_finding(30), "seed", abbreviation_sources=[source], persist=False
        )

        assert len(source.asked) == DEFAULT_MAX_ABBREVIATION_LOOKUPS

    @pytest.mark.asyncio
    async def test_lookups_run_concurrently_within_the_limit(self):
        from knowledge_lookup.core.term_expansion import ABBREVIATION_LOOKUP_CONCURRENCY

        source = _RecordingAbbreviationSource(delay=0.02)

        await expand_and_search(
            _lookup_finding(10), "seed", abbreviation_sources=[source], persist=False
        )

        assert len(source.asked) == 10
        assert source.peak == ABBREVIATION_LOOKUP_CONCURRENCY

    @pytest.mark.asyncio
    async def test_each_label_is_asked_once_per_run(self):
        async def side_effect(query, **kw):
            if query == "copd":
                return _result(
                    query, [_concept("COPD", synonyms=["chronic obstructive pulmonary disease"])]
                )
            return _result(query, [_concept("Chronic obstructive pulmonary disease")])

        source = _RecordingAbbreviationSource()

        _, trace = await expand_and_search(
            _mock_lookup(side_effect), "copd", abbreviation_sources=[source], persist=False
        )

        assert trace.rounds_run == 2
        assert sorted(source.asked) == ["COPD", "Chronic obstructive pulmonary disease"]

    @pytest.mark.asyncio
    async def test_cached_answers_still_feed_later_rounds(self):
        """A long form offered in round 0 but cut by max_terms_per_round comes back later."""

        class LongForms:
            def __init__(self) -> None:
                self.calls = 0

            async def expand(self, term: str) -> list[tuple[str, str]]:
                self.calls += 1
                if term == "Seed":
                    return [("long form a", ORIGIN_LONG_FORM), ("long form b", ORIGIN_LONG_FORM)]
                return []

        async def side_effect(query, **kw):
            return _result(query, [_concept("Seed" if query == "seed" else f"hit {query}")])

        source = LongForms()

        _, trace = await expand_and_search(
            _mock_lookup(side_effect),
            "seed",
            abbreviation_sources=[source],
            max_rounds=3,
            max_terms_per_round=1,
            persist=False,
        )

        assert trace.terms_by_round == [["seed"], ["long form a"], ["long form b"]]
        assert source.calls == 3  # "Seed", "hit long form a", "hit long form b"
