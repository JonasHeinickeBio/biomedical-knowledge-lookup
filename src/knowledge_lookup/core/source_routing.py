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
from collections.abc import Iterable

from ..models import ConceptType, KnowledgeSource

logger = logging.getLogger(__name__)


def as_concept_type(value: object) -> ConceptType | None:
    """Best-effort coerce a concept's ``concept_type`` (enum member or raw
    string after model regen) to a :class:`ConceptType`, or ``None`` when it
    is empty/unrecognised — routing then treats the term as unclassified."""
    if value is None or value == "":
        return None
    if isinstance(value, ConceptType):
        return value
    try:
        return ConceptType(str(value).upper())
    except ValueError:
        return None


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


#: Generalist sources worth asking for *every* concept when cross-referencing:
#: broad ontology/knowledge-graph services that carry identifiers for most types.
GENERAL_XREF_SOURCES: tuple[KnowledgeSource, ...] = (
    KnowledgeSource.OLS,
    KnowledgeSource.UMLS,
    KnowledgeSource.BIOPORTAL,
    KnowledgeSource.WIKIDATA,
)

#: The fixed cross-reference set the agent workflow used before type-aware
#: selection existed; still used for concepts whose type is unknown.
LEGACY_XREF_SOURCES: tuple[KnowledgeSource, ...] = (
    *GENERAL_XREF_SOURCES,
    KnowledgeSource.MONDO,
    KnowledgeSource.HPO,
)

#: Specialist sources eligible for cross-referencing, most authoritative first
#: (this order decides which ones survive the per-label cap). Literature sources
#: (Europe PMC, E-utilities) are deliberately absent: they return papers, not
#: identifiers for a concept.
_SPECIALIST_XREF_ORDER: tuple[KnowledgeSource, ...] = (
    KnowledgeSource.MONDO,
    KnowledgeSource.HPO,
    KnowledgeSource.HGNC,
    KnowledgeSource.UNIPROT,
    KnowledgeSource.ENSEMBL,
    KnowledgeSource.MYGENEINFO,
    KnowledgeSource.CHEMBL,
    KnowledgeSource.PUBCHEM,
    KnowledgeSource.DRUGBANK,
    KnowledgeSource.UNICHEM,
    KnowledgeSource.KEGG,
    KnowledgeSource.REACTOME,
    KnowledgeSource.WIKIPATHWAYS,
    KnowledgeSource.QUICKGO,
    KnowledgeSource.GENEONTOLOGY,
    KnowledgeSource.OPENTARGETS,
    KnowledgeSource.OMIM,
    KnowledgeSource.DISGENET,
    KnowledgeSource.STRING,
    KnowledgeSource.INTERPRO,
    KnowledgeSource.PFAM,
    KnowledgeSource.PDB,
    KnowledgeSource.DBPEDIA,
)

#: Upper bound on cross-reference sources queried per concept label. Every
#: adapter call sleeps for its rate limit, so this keeps one label's fan-out small.
MAX_XREF_SOURCES_PER_LABEL = 8


def cross_reference_sources(
    concept_type: ConceptType | None,
    available_sources: Iterable[KnowledgeSource],
    *,
    limit: int = MAX_XREF_SOURCES_PER_LABEL,
) -> list[KnowledgeSource]:
    """Sources to ask when cross-referencing one concept of *concept_type*.

    The generalists (:data:`GENERAL_XREF_SOURCES`) come first, then the
    specialists :data:`TYPE_SOURCE_MAP` lists for the type, in
    ``_SPECIALIST_XREF_ORDER`` — so a gene is cross-referenced against HGNC,
    UniProt and Ensembl and a drug against ChEMBL, PubChem and DrugBank rather
    than a fixed disease-oriented set. Unknown or unmapped types get
    :data:`LEGACY_XREF_SOURCES`. Only sources in *available_sources* are
    returned, at most *limit* of them.
    """
    available = set(available_sources)
    mapped = (
        _sources_for_type(concept_type)
        if concept_type is not None and concept_type != ConceptType.UNKNOWN
        else None
    )
    ordered: list[KnowledgeSource] = list(GENERAL_XREF_SOURCES)
    if mapped is None:
        ordered.extend(s for s in LEGACY_XREF_SOURCES if s not in ordered)
    else:
        ordered.extend(s for s in _SPECIALIST_XREF_ORDER if s in mapped and s not in ordered)
    return [s for s in ordered if s in available][: max(0, limit)]


__all__ = [
    "TYPE_SOURCE_MAP",
    "as_concept_type",
    "GENERAL_XREF_SOURCES",
    "LEGACY_XREF_SOURCES",
    "MAX_XREF_SOURCES_PER_LABEL",
    "route_sources",
    "cross_reference_sources",
    "options_for_concept_type",
]
