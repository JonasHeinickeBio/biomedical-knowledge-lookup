"""
Real-world (live API) tests for the KEGG adapter.

These exercise the enhanced KEGG adapter against the public KEGG REST service
(https://rest.kegg.jp) using Coenzyme Q10 (CoQ10 / ubiquinone-10, KEGG C11378)
as a concrete biomedical query. They are marked ``network`` and ``slow`` so that
offline runs (``-m "not slow"`` or ``-m unit``) skip them.
"""

import pytest
from knowledge_lookup.adapters.kegg_adapter import KEGGAdapter
from knowledge_lookup.models import ConceptType, LookupConfig

# CoQ10 is catalogued by KEGG as "Ubiquinone-10" (compound C11378).
# KEGG's ``find`` matches the full names but not the "CoQ10" abbreviation.
COQ10_ID = "C11378"
COQ10_QUERIES = ("ubiquinone-10", "Coenzyme Q10")


@pytest.fixture
def adapter():
    return KEGGAdapter(LookupConfig())


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.slow
class TestKEGGCoQ10RealWorld:
    """End-to-end checks for a real CoQ10 lookup against the live KEGG API."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", COQ10_QUERIES)
    async def test_find_coq10_compound(self, adapter, query):
        """CoQ10 is retrievable by its synonym and the full ubiquinone name."""
        try:
            results = await adapter.search_concepts(query, databases=["compound"], limit=10)
            ids = {concept.primary_id for concept in results}
            assert COQ10_ID in ids
            concept = next(c for c in results if c.primary_id == COQ10_ID)
            assert concept.concept_type == ConceptType.CHEMICAL
            assert "ubiquinone" in concept.primary_label.lower()
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_coq10_details_and_synonyms(self, adapter):
        """The C11378 entry exposes the Coenzyme Q10 synonym and source link."""
        try:
            concept = await adapter.get_concept_details(COQ10_ID)
            assert concept is not None
            assert concept.primary_label == "Ubiquinone-10"
            assert concept.concept_type == ConceptType.CHEMICAL
            # NAME field carries the common synonyms used in practice.
            synonyms = {s.lower() for s in (concept.synonyms or [])}
            assert "coenzyme q10" in synonyms or "ubidecarenone" in synonyms
            assert concept.identifiers, "expected a KEGG identifier to be attached"
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_coq10_cross_references(self, adapter):
        """DBLINKS cross-references resolve to external identifier sources."""
        try:
            mappings = await adapter.get_mappings(COQ10_ID)
            targets = {m["toSource"] for m in mappings}
            assert mappings, "expected at least one DBLINKS cross-reference"
            assert "PubChem" in targets
            for mapping in mappings:
                assert mapping["fromSource"] == "KEGG"
                assert mapping["fromId"] == COQ10_ID
                assert mapping["toId"]
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_gene_to_pathway_relationships(self, adapter):
        """Gene ``link`` relationships resolve to KEGG pathway entries."""
        try:
            # hsa:3939 (LDHA) is a well-connected glycolysis gene.
            relationships = await adapter.get_relationships("hsa:3939")
            assert relationships, "expected gene-to-pathway links for a metabolic gene"
            assert all(r["related_id"].startswith("path:") for r in relationships)
            assert all(r["relation_label"] == "in_pathway" for r in relationships)
        finally:
            await adapter.close()
