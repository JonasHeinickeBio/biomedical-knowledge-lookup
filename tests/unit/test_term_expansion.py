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
    ORIGIN_RELATIONSHIP,
    ORIGIN_SYNONYM,
    STOP_FIXED_POINT,
    STOP_MAX_ROUNDS,
    ExpansionStore,
)
from knowledge_lookup.core.term_expansion import (
    AdapterRelationshipSource,
    RelatedTerm,
    _infer_related_concept_type,
    expand_and_search,
    merge_concept_fields,
    merge_concept_results,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupResult, UnifiedConcept

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


class TestSourceAwareRouting:
    """Routing narrows *where* each term is searched, by its concept type."""

    def _typed_concept(
        self, label: str, concept_type: ConceptType, synonyms: list[str] | None = None
    ) -> UnifiedConcept:
        c = _concept(label, synonyms=synonyms)
        c.concept_type = concept_type
        return c

    def _multi_lookup(self, side_effect) -> MagicMock:
        lookup = MagicMock()
        lookup.search_concepts = AsyncMock(side_effect=side_effect)
        lookup.adapters = {
            KnowledgeSource.KEGG: MagicMock(),
            KnowledgeSource.UNIPROT: MagicMock(),
            KnowledgeSource.DRUGBANK: MagicMock(),
        }
        lookup.config = MagicMock()
        return lookup

    @pytest.mark.asyncio
    async def test_routed_synonym_uses_type_sources_and_options(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(
                    query,
                    [self._typed_concept("TP53", ConceptType.GENE, synonyms=["tumor protein p53"])],
                )
            return _result(query, [self._typed_concept("Tumor protein p53", ConceptType.GENE)])

        lookup = self._multi_lookup(side_effect)

        await expand_and_search(lookup, "tp53", abbreviation_sources=[], persist=False)

        # round 0 (seed, unclassified) fans out to every available source
        seed_call = lookup.search_concepts.await_args_list[0].kwargs
        assert seed_call["sources"] == [
            KnowledgeSource.KEGG,
            KnowledgeSource.UNIPROT,
            KnowledgeSource.DRUGBANK,
        ]
        assert seed_call["source_options"] == {}

        # round 1 inherits the GENE type from the concept that produced it:
        # DrugBank is dropped and KEGG is told to search gene records
        syn_call = lookup.search_concepts.await_args_list[1].kwargs
        assert syn_call["sources"] == [KnowledgeSource.KEGG, KnowledgeSource.UNIPROT]
        assert syn_call["source_options"] == {KnowledgeSource.KEGG: {"databases": ["gene", "pathway"]}}

    @pytest.mark.asyncio
    async def test_explicit_sources_disable_routing(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(
                    query,
                    [self._typed_concept("TP53", ConceptType.GENE, synonyms=["tumor protein p53"])],
                )
            return _result(query, [self._typed_concept("Tumor protein p53", ConceptType.GENE)])

        lookup = self._multi_lookup(side_effect)

        await expand_and_search(
            lookup,
            "tp53",
            sources=[KnowledgeSource.DRUGBANK],
            abbreviation_sources=[],
            persist=False,
        )

        for call in lookup.search_concepts.await_args_list:
            assert call.kwargs["sources"] == [KnowledgeSource.DRUGBANK]
            assert call.kwargs["source_options"] is None

    @pytest.mark.asyncio
    async def test_route_false_passes_sources_through_unchanged(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(
                    query,
                    [self._typed_concept("TP53", ConceptType.GENE, synonyms=["tumor protein p53"])],
                )
            return _result(query, [self._typed_concept("Tumor protein p53", ConceptType.GENE)])

        lookup = self._multi_lookup(side_effect)

        await expand_and_search(
            lookup, "tp53", route=False, abbreviation_sources=[], persist=False
        )

        for call in lookup.search_concepts.await_args_list:
            assert call.kwargs["sources"] is None


class _StubRelationshipSource:
    """A RelationshipSource stand-in returning canned edges per concept id."""

    def __init__(self, edges_by_id: dict[str, list[RelatedTerm]]):
        self._edges_by_id = edges_by_id
        self.asked: list[str] = []

    async def expand(self, concept) -> list[RelatedTerm]:
        self.asked.append(concept.primary_id)
        return list(self._edges_by_id.get(concept.primary_id, []))


class _RaisingRelationshipSource:
    async def expand(self, concept) -> list[RelatedTerm]:
        raise RuntimeError("relationship backend down")


def _pathway_term(name: str = "Cell cycle") -> RelatedTerm:
    return RelatedTerm(
        term=name,
        concept_type=ConceptType.PATHWAY,
        relation_label="gene_pathway",
        related_id="path:hsa04110",
        source="KEGG_PATHWAY",
    )


class TestRelationshipConceptTypeInference:
    def test_pathway_hint_maps_to_pathway(self):
        assert (
            _infer_related_concept_type(
                {"relation_label": "gene_pathway", "source": "KEGG_PATHWAY"}, ConceptType.GENE
            )
            == ConceptType.PATHWAY
        )

    def test_interaction_maps_to_protein(self):
        assert (
            _infer_related_concept_type({"relation_label": "interaction", "source": "STRING"}, None)
            == ConceptType.PROTEIN
        )

    def test_gene_label_maps_to_gene(self):
        assert (
            _infer_related_concept_type({"relation_label": "maps_to_gene", "source": ""}, None)
            == ConceptType.GENE
        )

    def test_unknown_falls_back_to_source_type(self):
        assert (
            _infer_related_concept_type(
                {"relation_label": "parent", "source": "UMLS"}, ConceptType.DISEASE
            )
            == ConceptType.DISEASE
        )


class TestAdapterRelationshipSource:
    @pytest.mark.asyncio
    async def test_normalizes_edges_from_matching_adapter(self):
        adapter = MagicMock()
        adapter.get_relationships = AsyncMock(
            return_value=[
                {
                    "relation_label": "gene_pathway",
                    "related_id": "path:hsa04110",
                    "related_name": "Cell cycle",
                    "source": "KEGG_PATHWAY",
                }
            ]
        )
        lookup = MagicMock()
        lookup.adapters = {KnowledgeSource.KEGG: adapter}

        concept = UnifiedConcept(
            primary_id="KEGG:hsa:7157",
            primary_label="TP53",
            sources=[KnowledgeSource.KEGG],
            concept_type=ConceptType.GENE,
        )

        terms = await AdapterRelationshipSource(lookup).expand(concept)
        adapter.get_relationships.assert_awaited_once_with("KEGG:hsa:7157")
        assert len(terms) == 1
        assert terms[0].term == "Cell cycle"
        assert terms[0].concept_type == ConceptType.PATHWAY
        assert terms[0].related_id == "path:hsa04110"

    @pytest.mark.asyncio
    async def test_skips_adapters_without_get_relationships(self):
        class _NoRels:  # no get_relationships attribute at all
            pass

        lookup = MagicMock()
        lookup.adapters = {KnowledgeSource.OLS: _NoRels()}
        concept = UnifiedConcept(
            primary_id="ols:x", primary_label="X", sources=[KnowledgeSource.OLS]
        )
        assert await AdapterRelationshipSource(lookup).expand(concept) == []

    @pytest.mark.asyncio
    async def test_degrades_on_adapter_error(self):
        adapter = MagicMock()
        adapter.get_relationships = AsyncMock(side_effect=RuntimeError("boom"))
        lookup = MagicMock()
        lookup.adapters = {KnowledgeSource.KEGG: adapter}
        concept = UnifiedConcept(
            primary_id="KEGG:hsa:7157", primary_label="TP53", sources=[KnowledgeSource.KEGG]
        )
        assert await AdapterRelationshipSource(lookup).expand(concept) == []

    @pytest.mark.asyncio
    async def test_requires_primary_id(self):
        lookup = MagicMock()
        lookup.adapters = {}
        concept = UnifiedConcept(primary_id="", primary_label="X", sources=[])
        assert await AdapterRelationshipSource(lookup).expand(concept) == []


class TestRelationshipExpansion:
    @pytest.mark.asyncio
    async def test_off_by_default_records_no_edges(self):
        async def side_effect(query, **kw):
            return _result(query, [_concept("TP53", synonyms=["tumor protein p53"])])

        lookup = _mock_lookup(side_effect)
        _, trace = await expand_and_search(lookup, "tp53", abbreviation_sources=[], persist=False)
        assert trace.relationships == []

    @pytest.mark.asyncio
    async def test_named_relationship_target_searched_next_round(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(query, [_concept("TP53")])
            return _result(query, [])  # "cell cycle" converges

        lookup = _mock_lookup(side_effect)
        source = _StubRelationshipSource({"id:tp53": [_pathway_term()]})

        _, trace = await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[source],
            persist=False,
        )

        assert trace.terms_by_round == [["tp53"], ["Cell cycle"]]
        assert trace.rounds_run == 2
        assert lookup.search_concepts.await_args_list[1].args[0] == "Cell cycle"
        assert len(trace.relationships) == 1
        assert trace.relationships[0]["searched"] is True
        assert trace.relationships[0]["related_name"] == "Cell cycle"
        assert trace.relationships[0]["concept_type"] == ConceptType.PATHWAY.value

    @pytest.mark.asyncio
    async def test_nameless_edge_recorded_but_not_searched(self):
        async def side_effect(query, **kw):
            return _result(query, [_concept("TP53")])

        lookup = _mock_lookup(side_effect)
        nameless = RelatedTerm(
            term="",
            concept_type=ConceptType.PATHWAY,
            relation_label="gene_pathway",
            related_id="path:hsa04110",
            source="KEGG_PATHWAY",
        )
        source = _StubRelationshipSource({"id:tp53": [nameless]})

        _, trace = await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[source],
            persist=False,
        )

        assert trace.rounds_run == 1  # no searchable term to grow into
        assert lookup.search_concepts.await_count == 1
        assert trace.relationships[0]["searched"] is False
        assert trace.relationships[0]["related_name"] is None

    @pytest.mark.asyncio
    async def test_each_concept_asked_once_across_rounds(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(query, [_concept("TP53")])
            return _result(query, [_concept("TP53")])  # same concept resurfaces

        lookup = _mock_lookup(side_effect)
        source = _StubRelationshipSource({"id:tp53": [_pathway_term()]})

        await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[source],
            persist=False,
        )

        assert source.asked.count("id:tp53") == 1

    @pytest.mark.asyncio
    async def test_max_relationship_concepts_caps_queries_per_round(self):
        async def side_effect(query, **kw):
            return _result(query, [_concept("TP53"), _concept("MYC")])

        lookup = _mock_lookup(side_effect)
        source = _StubRelationshipSource({})

        await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[source],
            max_relationship_concepts=1,
            persist=False,
        )

        assert len(source.asked) == 1
        assert source.asked == ["id:tp53"]

    @pytest.mark.asyncio
    async def test_failing_relationship_source_does_not_abort(self):
        async def side_effect(query, **kw):
            return _result(query, [_concept("TP53")])

        lookup = _mock_lookup(side_effect)
        _, trace = await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[_RaisingRelationshipSource()],
            persist=False,
        )
        assert trace.relationships == []
        assert trace.rounds_run == 1

    @pytest.mark.asyncio
    async def test_synonym_wins_capped_slot_over_relationship(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(query, [_concept("TP53", synonyms=["tumor protein p53"])])
            return _result(query, [])

        lookup = _mock_lookup(side_effect)
        source = _StubRelationshipSource({"id:tp53": [_pathway_term()]})

        _, trace = await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[source],
            max_terms_per_round=1,
            persist=False,
        )

        # the synonym fills the single capped slot; the relationship edge is
        # still recorded but flagged unsearched (dropped by the cap)
        assert trace.terms_by_round[1] == ["tumor protein p53"]
        assert trace.relationships[0]["searched"] is False

    @pytest.mark.asyncio
    async def test_relationship_edges_persisted_to_store(self):
        async def side_effect(query, **kw):
            if query == "tp53":
                return _result(query, [_concept("TP53")])
            return _result(query, [])

        lookup = _mock_lookup(side_effect)
        source = _StubRelationshipSource({"id:tp53": [_pathway_term()]})
        store = ExpansionStore()

        _, trace = await expand_and_search(
            lookup,
            "tp53",
            abbreviation_sources=[],
            relationship_sources=[source],
            store=store,
            persist=True,
        )

        edges = store.get_relationship_edges(trace.run_id)
        assert len(edges) == 1
        assert edges[0]["related_id"] == "path:hsa04110"
        assert edges[0]["searched"] == 1
        terms = store.get_terms(trace.run_id)
        rel_terms = [t for t in terms if t["origin"] == ORIGIN_RELATIONSHIP]
        assert [t["term"] for t in rel_terms] == ["Cell cycle"]
