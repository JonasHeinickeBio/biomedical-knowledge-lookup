"""
Real-world (live API) tests for relationship-aware term expansion.

These exercise the relationship-expansion path of ``expand_and_search`` /
``CentralKnowledgeLookup.search_concepts_expanded`` against the live EMBL-EBI
OLS (https://www.ebi.ac.uk/ols4) service, which needs no API key. The concrete
biomedical thread is the *cytokine* class: a broad class term such as
"cytokine" or "interleukin" must grow its member terms (interleukin-N,
interferon, ...) through ontology ``has_narrower``/``has_broader`` edges, and
those members must actually be *searched* (not merely recorded). That reserved
slot is exactly what a synonym-rich round used to starve.

They are marked ``integration``, ``network`` and ``slow`` so offline runs
(``-m unit`` or ``-m "not slow"``) skip them. Assertions target structural
invariants (edge labels, sources, "was a relationship target searched") rather
than exact live counts, so ordinary drift in the live ontology does not flake
them.
"""

import re

import pytest
from knowledge_lookup import KnowledgeSource, create_knowledge_lookup
from knowledge_lookup.adapters.ols_adapter import OLSAdapter
from knowledge_lookup.core.term_expansion import (
    ASSOCIATIVE_RELATION_LABELS,
    TAXONOMIC_RELATION_LABELS,
    AdapterRelationshipSource,
    expand_and_search,
)
from knowledge_lookup.models import LookupConfig

# NCI Thesaurus "Interleukin" class, catalogued in OLS with interleukin-N
# children and a "Cytokine" parent. Stable identifier; the members and parent
# are what the hierarchy tests key on.
INTERLEUKIN_IRI = "http://purl.obolibrary.org/obo/NCIT_C20497"
# Member keywords that a cytokine/interleukin expansion is expected to surface.
MEMBER_KEYWORDS = ("interleukin", "interferon", "chemokine", "colony-stimulating")


def _ols_relationship_source(lookup, relation_labels):
    return AdapterRelationshipSource(
        lookup,
        relation_labels=set(relation_labels),
        allowed_sources={KnowledgeSource.OLS},
    )


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.slow
class TestTermExpansionRealWorld:
    """Live OLS checks for taxonomic (class -> member) relationship expansion."""

    @pytest.mark.asyncio
    async def test_ols_interleukin_hierarchy_edges(self):
        """OLS reports interleukin-N members and the Cytokine parent."""
        adapter = OLSAdapter(LookupConfig())
        try:
            details = await adapter.get_concept_details(INTERLEUKIN_IRI)
            assert details is not None
            assert details.primary_label.strip().lower() == "interleukin"
            children = [str(c).lower() for c in (details.children or [])]
            parents = [str(p).lower() for p in (details.parents or [])]
            assert any("interleukin-" in c for c in children), (
                f"expected interleukin-N children, got {children[:8]}"
            )
            assert any("cytokine" in p for p in parents), (
                f"expected a Cytokine parent, got {parents[:8]}"
            )

            rels = await adapter.get_relationships(INTERLEUKIN_IRI)
            assert rels, "expected has_narrower member edges for the interleukin class"
            labels = {r["relation_label"] for r in rels}
            assert labels <= set(TAXONOMIC_RELATION_LABELS)
            member_names = [
                (r.get("related_name") or "") for r in rels if r.get("related_name")
            ]
            assert any(re.match(r"interleukin-\d+", n.lower()) for n in member_names), (
                f"expected interleukin-N member edges, got {member_names[:8]}"
            )
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_adapter_relationship_source_harvests_members(self):
        """AdapterRelationshipSource resolves members via the concept's own id."""
        lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.OLS])
        try:
            result = await lookup.search_concepts(
                "Interleukin", sources=[KnowledgeSource.OLS], max_results=10
            )
            concept = next(
                (c for c in result.concepts if (c.primary_label or "").lower() == "interleukin"),
                None,
            )
            assert concept is not None, "expected an 'Interleukin' concept from OLS"

            edges = await _ols_relationship_source(lookup, TAXONOMIC_RELATION_LABELS).expand(
                concept
            )
            assert edges, "expected taxonomic edges for the interleukin concept"
            assert {e.relation_label for e in edges} <= set(TAXONOMIC_RELATION_LABELS)
            assert {(e.source or "").lower() for e in edges} <= {"ols"}
            members = [e.term.lower() for e in edges if e.term]
            assert any(m.startswith("interleukin-") for m in members), (
                f"expected interleukin-N member terms, got {members[:8]}"
            )
        finally:
            await lookup.close()

    @pytest.mark.asyncio
    async def test_associative_filter_drops_hierarchy_edges(self):
        """The associative label set (complement) drops the class/member edges."""
        lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.OLS])
        try:
            result = await lookup.search_concepts(
                "Interleukin", sources=[KnowledgeSource.OLS], max_results=10
            )
            concept = next(
                (c for c in result.concepts if (c.primary_label or "").lower() == "interleukin"),
                None,
            )
            assert concept is not None, "expected an 'Interleukin' concept from OLS"

            edges = await _ols_relationship_source(lookup, ASSOCIATIVE_RELATION_LABELS).expand(
                concept
            )
            # The interleukin class only carries taxonomic edges, so filtering
            # to associative labels must leave nothing behind.
            labels = {e.relation_label for e in edges}
            assert edges == [], f"expected no associative edges, got {sorted(labels)}"
        finally:
            await lookup.close()

    @pytest.mark.asyncio
    async def test_cytokine_expansion_searches_relationship_members(self):
        """A class term's members reach the search via the reserved slot."""
        lookup = create_knowledge_lookup(enabled_sources=[KnowledgeSource.OLS])
        try:
            base = await lookup.search_concepts(
                "cytokine", sources=[KnowledgeSource.OLS], max_results=60
            )
            base_labels = {(c.primary_label or "").lower() for c in base.concepts}

            result, trace = await expand_and_search(
                lookup,
                "cytokine",
                sources=[KnowledgeSource.OLS],
                max_results=80,
                max_rounds=2,
                max_terms_per_round=8,
                relationship_sources=[
                    _ols_relationship_source(lookup, TAXONOMIC_RELATION_LABELS)
                ],
                abbreviation_sources=[],
                persist=False,
            )

            # Relationship edges were harvested and only taxonomic OLS ones kept.
            assert trace.relationships, "expected harvested relationship edges for 'cytokine'"
            assert {r["relation_label"] for r in trace.relationships} <= set(
                TAXONOMIC_RELATION_LABELS
            )
            assert {(r.get("related_source") or "").lower() for r in trace.relationships} <= {
                "ols"
            }

            # The reserved slot let a relationship target actually get searched,
            # rather than being starved by synonyms. Its target must appear as a
            # searched term in a later round.
            searched_targets = {
                (r.get("related_name") or "").strip().lower()
                for r in trace.relationships
                if r.get("searched")
            }
            searched_targets.discard("")
            assert searched_targets, "expected a relationship target to be searched"
            later_round_terms = {
                t.strip().lower() for rnd in trace.terms_by_round[1:] for t in rnd
            }
            assert searched_targets & later_round_terms, (
                "searched relationship targets never entered a search round"
            )

            # A member term (interleukin/interferon/...) was searched this way.
            assert any(
                any(k in term for k in MEMBER_KEYWORDS) for term in searched_targets
            ), f"searched targets lacked a cytokine member: {sorted(searched_targets)[:10]}"

            # Expansion surfaced class-member concepts the plain search missed.
            expanded_labels = {(c.primary_label or "").lower() for c in result.concepts}
            new_members = {
                label
                for label in (expanded_labels - base_labels)
                if any(k in label for k in MEMBER_KEYWORDS)
            }
            assert new_members, "expansion surfaced no new cytokine-member concepts"
            assert len(result.concepts) > len(base.concepts)
        finally:
            await lookup.close()
