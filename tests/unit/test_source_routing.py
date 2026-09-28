"""Unit tests for concept-type-aware source routing."""

from __future__ import annotations

import pytest

from knowledge_lookup.core.source_routing import (
    TYPE_SOURCE_MAP,
    options_for_concept_type,
    route_sources,
)
from knowledge_lookup.models import ConceptType, KnowledgeSource

pytestmark = pytest.mark.unit

ALL = list(KnowledgeSource)


class TestRouteSources:
    def test_none_returns_all_available(self):
        avail = [KnowledgeSource.KEGG, KnowledgeSource.DRUGBANK]
        assert route_sources(None, avail) == avail

    def test_unknown_returns_all_available(self):
        avail = [KnowledgeSource.KEGG, KnowledgeSource.DRUGBANK]
        assert route_sources(ConceptType.UNKNOWN, avail) == avail

    def test_unmapped_type_returns_all_available(self):
        avail = [KnowledgeSource.KEGG, KnowledgeSource.DRUGBANK]
        assert route_sources(ConceptType.ORGAN, avail) == avail

    def test_gene_narrows_to_gene_sources(self):
        avail = [KnowledgeSource.KEGG, KnowledgeSource.UNIPROT, KnowledgeSource.DRUGBANK]
        assert route_sources(ConceptType.GENE, avail) == [
            KnowledgeSource.KEGG,
            KnowledgeSource.UNIPROT,
        ]

    def test_drug_narrows_to_drug_sources(self):
        avail = [KnowledgeSource.KEGG, KnowledgeSource.UNIPROT, KnowledgeSource.DRUGBANK]
        assert route_sources(ConceptType.DRUG, avail) == [
            KnowledgeSource.KEGG,
            KnowledgeSource.DRUGBANK,
        ]

    def test_order_follows_available_sources(self):
        avail = [KnowledgeSource.UNIPROT, KnowledgeSource.KEGG]
        assert route_sources(ConceptType.GENE, avail) == [
            KnowledgeSource.UNIPROT,
            KnowledgeSource.KEGG,
        ]

    def test_empty_intersection_falls_back_to_all(self):
        # DrugBank-only availability for a gene term has no overlap
        avail = [KnowledgeSource.DRUGBANK]
        assert route_sources(ConceptType.GENE, avail) == avail

    def test_study_family_collapse(self):
        avail = [KnowledgeSource.EUROPEPMC, KnowledgeSource.DRUGBANK]
        assert route_sources(ConceptType.CLINICAL_TRIAL, avail) == [KnowledgeSource.EUROPEPMC]

    def test_every_mapped_source_is_a_real_member(self):
        for sources in TYPE_SOURCE_MAP.values():
            for source in sources:
                assert source in ALL


class TestOptionsForConceptType:
    def test_gene_selects_gene_database(self):
        assert options_for_concept_type(ConceptType.GENE) == {
            KnowledgeSource.KEGG: {"databases": ["gene", "pathway"]}
        }

    def test_drug_selects_drug_databases(self):
        assert options_for_concept_type(ConceptType.DRUG) == {
            KnowledgeSource.KEGG: {"databases": ["drug", "compound"]}
        }

    def test_unclassified_returns_empty(self):
        assert options_for_concept_type(None) == {}
        assert options_for_concept_type(ConceptType.UNKNOWN) == {}
        assert options_for_concept_type(ConceptType.DISEASE) == {}
