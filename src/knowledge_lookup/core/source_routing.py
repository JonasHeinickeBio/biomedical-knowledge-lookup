"""
Concept-type-aware source routing for lookups and term expansion.

``CentralKnowledgeLookup.search_concepts`` fans a query out to *every*
configured source with the same options. That is the right default for a
first pass, but it wastes effort during **iterative term expansion**: a gene
symbol like ``TP53`` is better sent to gene/protein resources (UniProt,
Ensembl, MyGene, HGNC, KEGG ``gene``) than to DrugBank, and a drug name is
better sent to chemical/drug resources (ChEMBL, DrugBank, PubChem, KEGG
``drug``/``compound``) than to the gene-only corners of the catalogue.

This module provides a small, curated, dependency-free routing table:

- :func:`route_sources` narrows a set of *available* sources down to the ones
  useful for a given :class:`~knowledge_lookup.models.ConceptType`, falling
  back to the full set for ``UNKNOWN``/unmapped types so routing can only ever
  *sharpen* a search, never silently drop the last source.
- :func:`options_for_concept_type` returns adapter-specific keyword options
  (currently only KEGG's ``databases`` selection) keyed by
  :class:`~knowledge_lookup.models.KnowledgeSource`, so a gene term actually
  reaches KEGG's gene records instead of only its disease/drug defaults.

The router is intentionally conservative: it never invents sources that are not
already available and never overrides a caller's explicit source selection —
that policy lives in the caller (see ``term_expansion.expand_and_search``).
"""

from __future__ import annotations

import logging

from ..models import ConceptType, KnowledgeSource

logger = logging.getLogger(__name__)

#: Curated ``ConceptType`` -> sources that are useful for it.
#:
#: Only sources that actually exist in :class:`KnowledgeSource` appear here.
#: Anything not listed (including ``UNKNOWN``) routes to "use whatever is
#: available", which is exactly the pre-routing behaviour.
TYPE_SOURCE_MAP: dict[ConceptType, frozenset[KnowledgeSource]] = {
    ConceptType.GENE: frozenset(
        {
            KnowledgeSource.KEGG,
            KnowledgeSource.UNIPROT,
            KnowledgeSource.ENSEMBL,
            KnowledgeSource.MYGENEINFO,
            KnowledgeSource.HGNC,
            KnowledgeSource.NCBI,
            KnowledgeSource.EUTILS,
            KnowledgeSource.GO,
            KnowledgeSource.GENEONTOLOGY,
            KnowledgeSource.QUICKGO,
            KnowledgeSource.STRING,
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.WIKIPATHWAYS,
            KnowledgeSource.UMLS,
            KnowledgeSource.OLS,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.PROTEIN: frozenset(
        {
            KnowledgeSource.UNIPROT,
            KnowledgeSource.INTERPRO,
            KnowledgeSource.PFAM,
            KnowledgeSource.PDB,
            KnowledgeSource.KEGG,
            KnowledgeSource.QUICKGO,
            KnowledgeSource.STRING,
            KnowledgeSource.ENSEMBL,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.DRUG: frozenset(
        {
            KnowledgeSource.DRUGBANK,
            KnowledgeSource.CHEMBL,
            KnowledgeSource.PUBCHEM,
            KnowledgeSource.UNICHEM,
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.KEGG,
            KnowledgeSource.UMLS,
            KnowledgeSource.WIKIDATA,
            KnowledgeSource.EUTILS,
        }
    ),
    ConceptType.CHEMICAL: frozenset(
        {
            KnowledgeSource.PUBCHEM,
            KnowledgeSource.CHEMBL,
            KnowledgeSource.UNICHEM,
            KnowledgeSource.KEGG,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.METABOLITE: frozenset(
        {
            KnowledgeSource.KEGG,
            KnowledgeSource.PUBCHEM,
            KnowledgeSource.CHEMBL,
            KnowledgeSource.UNICHEM,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.BIOMARKER: frozenset(
        {
            KnowledgeSource.UNIPROT,
            KnowledgeSource.UMLS,
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.DISEASE: frozenset(
        {
            KnowledgeSource.MONDO,
            KnowledgeSource.OMIM,
            KnowledgeSource.UMLS,
            KnowledgeSource.OLS,
            KnowledgeSource.EBIOLS,
            KnowledgeSource.DISGENET,
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.HPO,
            KnowledgeSource.CLINVAR,
            KnowledgeSource.NCBI,
            KnowledgeSource.EUTILS,
            KnowledgeSource.WIKIDATA,
            KnowledgeSource.DBPEDIA,
        }
    ),
    ConceptType.GENE_DISEASE_ASSOCIATION: frozenset(
        {
            KnowledgeSource.DISGENET,
            KnowledgeSource.OPENTARGETS,
            KnowledgeSource.MYGENEINFO,
            KnowledgeSource.ENSEMBL,
            KnowledgeSource.OMIM,
        }
    ),
    ConceptType.PHENOTYPE: frozenset(
        {
            KnowledgeSource.HPO,
            KnowledgeSource.MONDO,
            KnowledgeSource.UMLS,
            KnowledgeSource.OLS,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.SYMPTOM: frozenset(
        {
            KnowledgeSource.HPO,
            KnowledgeSource.UMLS,
            KnowledgeSource.MONDO,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.PATHWAY: frozenset(
        {
            KnowledgeSource.KEGG,
            KnowledgeSource.REACTOME,
            KnowledgeSource.WIKIPATHWAYS,
            KnowledgeSource.QUICKGO,
            KnowledgeSource.GO,
            KnowledgeSource.GENEONTOLOGY,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.BIOLOGICAL_PROCESS: frozenset(
        {
            KnowledgeSource.GO,
            KnowledgeSource.GENEONTOLOGY,
            KnowledgeSource.QUICKGO,
            KnowledgeSource.REACTOME,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.PHYSIOLOGICAL_PROCESS: frozenset(
        {
            KnowledgeSource.GO,
            KnowledgeSource.GENEONTOLOGY,
            KnowledgeSource.QUICKGO,
            KnowledgeSource.REACTOME,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.MOLECULAR_FUNCTION: frozenset(
        {
            KnowledgeSource.GO,
            KnowledgeSource.GENEONTOLOGY,
            KnowledgeSource.QUICKGO,
            KnowledgeSource.INTERPRO,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.CELL_TYPE: frozenset(
        {
            KnowledgeSource.UMLS,
            KnowledgeSource.OLS,
            KnowledgeSource.WIKIDATA,
            KnowledgeSource.DBPEDIA,
        }
    ),
    ConceptType.ANATOMICAL_ENTITY: frozenset(
        {
            KnowledgeSource.UMLS,
            KnowledgeSource.OLS,
            KnowledgeSource.WIKIDATA,
            KnowledgeSource.DBPEDIA,
        }
    ),
    ConceptType.TREATMENT: frozenset(
        {
            KnowledgeSource.UMLS,
            KnowledgeSource.MONDO,
            KnowledgeSource.DRUGBANK,
            KnowledgeSource.WIKIDATA,
        }
    ),
    ConceptType.PROCEDURE: frozenset(
        {
            KnowledgeSource.UMLS,
            KnowledgeSource.MONDO,
            KnowledgeSource.WIKIDATA,
        }
    ),
}

#: Broad "study / literature" family - many study subtypes share sources, so we
#: collapse them to one entry at lookup time rather than repeat the set.
_STUDY_SOURCES = frozenset(
    {
        KnowledgeSource.EUROPEPMC,
        KnowledgeSource.EUTILS,
        KnowledgeSource.CLINVAR,
        KnowledgeSource.WIKIDATA,
    }
)

#: Study-flavoured concept types routed to :data:`_STUDY_SOURCES`.
_STUDY_TYPES = frozenset(
    {
        ConceptType.STUDY,
        ConceptType.CLINICAL_STUDY,
        ConceptType.LABORATORY_STUDY,
        ConceptType.OBSERVATIONAL_STUDY,
        ConceptType.COHORT_STUDY,
        ConceptType.CASE_STUDY,
        ConceptType.CASE_CONTROL_STUDY,
        ConceptType.RANDOMIZED_CONTROLLED_TRIAL,
        ConceptType.CLINICAL_TRIAL,
        ConceptType.META_ANALYSIS,
        ConceptType.SYSTEMATIC_REVIEW,
        ConceptType.INTERVENTIONAL_STUDY,
        ConceptType.DIAGNOSTIC_TRIAL,
        ConceptType.COMMUNITY_TRIAL,
        ConceptType.RETROSPECTIVE_COHORT_STUDY,
        ConceptType.PROSPECTIVE_COHORT_STUDY,
        ConceptType.EVIDENCE,
        ConceptType.REFERENCE,
        ConceptType.CITATION,
    }
)


def _sources_for_type(concept_type: ConceptType) -> frozenset[KnowledgeSource] | None:
    """Direct or family-collapsed source set for *concept_type*, or ``None``."""
    if concept_type in TYPE_SOURCE_MAP:
        return TYPE_SOURCE_MAP[concept_type]
    if concept_type in _STUDY_TYPES:
        return _STUDY_SOURCES
    return None


def route_sources(
    concept_type: ConceptType | None,
    available_sources: list[KnowledgeSource],
) -> list[KnowledgeSource]:
    """Narrow *available_sources* to those useful for *concept_type*.

    Returns *available_sources* unchanged when *concept_type* is ``None``,
    ``ConceptType.UNKNOWN``, unmapped, or when the intersection would be empty
    (e.g. the caller only configured sources this type has no affinity for) -
    routing must never leave a search with nothing to query.

    Order follows *available_sources* so behaviour is deterministic.
    """
    if concept_type is None or concept_type == ConceptType.UNKNOWN:
        return list(available_sources)

    mapped = _sources_for_type(concept_type)
    if mapped is None:
        return list(available_sources)

    routed = [source for source in available_sources if source in mapped]
    if not routed:
        logger.debug(
            "route_sources: no overlap for %s among %s; using all available",
            concept_type,
            [s.value for s in available_sources],
        )
        return list(available_sources)
    return routed


def options_for_concept_type(
    concept_type: ConceptType | None,
) -> dict[KnowledgeSource, dict[str, object]]:
    """Adapter-specific keyword options for *concept_type*.

    Keyed by :class:`KnowledgeSource`; each inner dict is passed as keyword
    arguments to that adapter's ``search_concepts`` (and silently dropped by
    adapters whose signature does not accept them - see
    ``CentralKnowledgeLookup._search_single_source``).

    Currently this only tunes KEGG's ``databases`` selection so a gene term
    actually reaches KEGG gene records rather than the historical
    disease/drug-only default.
    """
    if concept_type == ConceptType.GENE:
        return {KnowledgeSource.KEGG: {"databases": ["gene", "pathway"]}}
    if concept_type == ConceptType.PATHWAY:
        return {KnowledgeSource.KEGG: {"databases": ["pathway"]}}
    if concept_type == ConceptType.DRUG:
        return {KnowledgeSource.KEGG: {"databases": ["drug", "compound"]}}
    if concept_type == ConceptType.CHEMICAL:
        return {KnowledgeSource.KEGG: {"databases": ["compound", "reaction"]}}
    if concept_type == ConceptType.METABOLITE:
        return {KnowledgeSource.KEGG: {"databases": ["compound", "reaction", "pathway"]}}
    return {}


__all__ = [
    "TYPE_SOURCE_MAP",
    "route_sources",
    "options_for_concept_type",
]
