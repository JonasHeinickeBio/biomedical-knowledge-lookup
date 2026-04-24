"""
Knowledge Lookup Data Models

Common data structures for unified knowledge graph lookups.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class KnowledgeSource(Enum):
    """Enumeration of supported knowledge sources."""

    UMLS = "umls"
    OLS = "ols"
    BIOPORTAL = "bioportal"
    BIOONTOLOGY = "bioontology"
    OXO = "oxo"
    WIKIDATA = "wikidata"
    DBPEDIA = "dbpedia"
    TYTO = "tyto"
    ZOOMA = "zooma"
    BIOLINKER = "biolinker"
    NCBI = "ncbi"
    UNIPROT = "uniprot"
    ENSEMBL = "ensembl"
    PUBCHEM = "pubchem"
    CHEMBL = "chembl"
    UNICHEM = "unichem"
    MONDO = "mondo"
    # New open KG sources
    DISGENET = "disgenet"
    OPENTARGETS = "opentargets"
    REACTOME = "reactome"
    DRUGBANK = "drugbank"
    GO = "go"
    GENEONTOLOGY = "geneontology"
    HPO = "hpo"
    OBOFOUNDRY = "obofoundry"
    EBIOLS = "ebiols"
    KEGG = "kegg"
    QUICKGO = "quickgo"
    MYGENEINFO = "mygeneinfo"
    HGNC = "hgnc"
    EUTILS = "eutils"


class ConceptType(Enum):
    """Types of biological concepts based on AID-PAIS ontology."""

    # Clinical entities
    DISEASE = "disease"
    SYMPTOM = "symptom"
    PHENOTYPE = "phenotype"
    TREATMENT = "treatment"
    DEMOGRAPHIC = "demographic"
    CASE_DEFINITION = "case_definition"
    PROGNOSIS = "prognosis"

    # Molecular entities
    MOLECULAR_ENTITY = "molecular_entity"
    GENE = "gene"
    PROTEIN = "protein"
    CYTOKINE = "cytokine"
    METABOLITE = "metabolite"
    BIOMARKER = "biomarker"
    GENE_DISEASE_ASSOCIATION = "gene_disease_association"

    # Chemical entities
    CHEMICAL = "chemical"
    DRUG = "drug"

    # Anatomical entities
    ANATOMICAL_ENTITY = "anatomical_entity"
    ORGAN_SYSTEM = "organ_system"
    ORGAN = "organ"
    TISSUE = "tissue"
    CELL_TYPE = "cell_type"
    CELLULAR_COMPONENT = "cellular_component"

    # Procedures
    PROCEDURE = "procedure"

    # Biological processes
    BIOLOGICAL_PROCESS = "biological_process"
    PHYSIOLOGICAL_PROCESS = "physiological_process"
    PATHOPHYSIOLOGICAL_PROCESS = "pathophysiological_process"
    MOLECULAR_FUNCTION = "molecular_function"

    # Measurement and observation
    OBSERVATION = "observation"
    ASSAY = "assay"

    # Evidence and study types
    EVIDENCE = "evidence"
    REFERENCE = "reference"
    CITATION = "citation"
    STUDY = "study"
    CLINICAL_STUDY = "clinical_study"
    LABORATORY_STUDY = "laboratory_study"
    OBSERVATIONAL_STUDY = "observational_study"
    COHORT_STUDY = "cohort_study"
    CASE_STUDY = "case_study"
    CASE_CONTROL_STUDY = "case_control_study"
    RANDOMIZED_CONTROLLED_TRIAL = "randomized_controlled_trial"
    CLINICAL_TRIAL = "clinical_trial"
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    INTERVENTIONAL_STUDY = "interventional_study"
    DIAGNOSTIC_TRIAL = "diagnostic_trial"
    COMMUNITY_TRIAL = "community_trial"
    RETROSPECTIVE_COHORT_STUDY = "retrospective_cohort_study"
    PROSPECTIVE_COHORT_STUDY = "prospective_cohort_study"

    # Other entities
    PERSON = "person"
    ORGANISM = "organism"
    PATHWAY = "pathway"  # Keeping for backward compatibility
    ANATOMY = "anatomy"  # Keeping for backward compatibility

    UNKNOWN = "unknown"


@dataclass
class ConceptIdentifier:
    """Represents an identifier for a concept in a specific knowledge source."""

    source: KnowledgeSource
    identifier: str
    label: str | None = None
    url: str | None = None

    def __str__(self) -> str:
        return f"{self.source.value}:{self.identifier}"


@dataclass
class ConceptMapping:
    """Represents a mapping between two concept identifiers."""

    from_concept: ConceptIdentifier
    to_concept: ConceptIdentifier
    mapping_type: str = "exact"  # exact, narrow, broad, related
    confidence: float = 1.0
    source: str | None = None


@dataclass
class UnifiedConcept:
    """
    Unified representation of a biological concept across multiple knowledge sources.
    """

    # Primary identification
    primary_id: str
    primary_label: str
    concept_type: ConceptType = ConceptType.UNKNOWN

    # Cross-references
    identifiers: list[ConceptIdentifier] = field(default_factory=list)
    mappings: list[ConceptMapping] = field(default_factory=list)

    # Labels and descriptions
    labels: dict[str, str] = field(default_factory=dict)  # language -> label
    synonyms: list[str] = field(default_factory=list)
    definitions: list[str] = field(default_factory=list)

    # Classification
    semantic_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)

    # Relationships
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    # Metadata
    sources: set[KnowledgeSource] = field(default_factory=set)
    confidence_score: float = 0.0
    last_updated: str | None = None

    # Raw data from sources
    source_data: dict[KnowledgeSource, Any] = field(default_factory=dict)

    def add_identifier(
        self,
        source: KnowledgeSource,
        identifier: str,
        label: str | None = None,
        url: str | None = None,
    ):
        """Add a cross-reference identifier."""
        concept_id = ConceptIdentifier(source, identifier, label, url)
        self.identifiers.append(concept_id)
        self.sources.add(source)

    def add_mapping(
        self,
        target_source: KnowledgeSource,
        target_id: str,
        mapping_type: str = "exact",
        confidence: float = 1.0,
        mapping_source: str | None = None,
    ):
        """Add a mapping to another concept."""
        from_concept = ConceptIdentifier(KnowledgeSource.UMLS, self.primary_id, self.primary_label)
        to_concept = ConceptIdentifier(target_source, target_id)
        mapping = ConceptMapping(
            from_concept, to_concept, mapping_type, confidence, mapping_source
        )
        self.mappings.append(mapping)

    def get_identifier(self, source: KnowledgeSource) -> ConceptIdentifier | None:
        """Get identifier for a specific source."""
        for identifier in self.identifiers:
            if identifier.source == source:
                return identifier
        return None

    def has_source(self, source: KnowledgeSource) -> bool:
        """Check if concept has data from a specific source."""
        return source in self.sources

    def merge_with(self, other: "UnifiedConcept") -> "UnifiedConcept":
        """Merge this concept with another, combining their data."""
        # Use the concept with higher confidence as base
        base = self if self.confidence_score >= other.confidence_score else other
        merge_from = other if base == self else self

        # Create new merged concept
        merged = UnifiedConcept(
            primary_id=base.primary_id,
            primary_label=base.primary_label,
            concept_type=base.concept_type,
        )

        # Merge identifiers (avoid duplicates)
        all_identifiers = base.identifiers + merge_from.identifiers
        seen = set()
        for identifier in all_identifiers:
            key = (identifier.source, identifier.identifier)
            if key not in seen:
                merged.identifiers.append(identifier)
                seen.add(key)

        # Merge other fields
        merged.mappings = base.mappings + merge_from.mappings
        merged.labels.update(base.labels)
        merged.labels.update(merge_from.labels)
        merged.synonyms = list(set(base.synonyms + merge_from.synonyms))
        merged.definitions = list(set(base.definitions + merge_from.definitions))
        merged.semantic_types = list(set(base.semantic_types + merge_from.semantic_types))
        merged.categories = list(set(base.categories + merge_from.categories))
        merged.parents = list(set(base.parents + merge_from.parents))
        merged.children = list(set(base.children + merge_from.children))
        merged.related = list(set(base.related + merge_from.related))
        merged.sources = base.sources.union(merge_from.sources)
        merged.confidence_score = max(base.confidence_score, merge_from.confidence_score)

        # Merge source data
        merged.source_data.update(base.source_data)
        merged.source_data.update(merge_from.source_data)

        return merged


@dataclass
class LookupResult:
    """Result of a knowledge lookup operation."""

    query: str
    concepts: list[UnifiedConcept] = field(default_factory=list)
    total_found: int = 0
    sources_queried: list[KnowledgeSource] = field(default_factory=list)
    sources_succeeded: list[KnowledgeSource] = field(default_factory=list)
    sources_failed: list[KnowledgeSource] = field(default_factory=list)
    execution_time: float = 0.0
    errors: dict[KnowledgeSource, str] = field(default_factory=dict)

    def add_concepts(self, concepts: list[UnifiedConcept], source: KnowledgeSource):
        """Add concepts from a specific source."""
        self.concepts.extend(concepts)
        self.total_found += len(concepts)
        if source not in self.sources_succeeded:
            self.sources_succeeded.append(source)

    def add_error(self, source: KnowledgeSource, error: str):
        """Record an error for a specific source."""
        self.errors[source] = error
        if source not in self.sources_failed:
            self.sources_failed.append(source)

    def get_best_matches(self, limit: int = 10) -> list[UnifiedConcept]:
        """Get the best matching concepts sorted by confidence."""
        return sorted(self.concepts, key=lambda c: c.confidence_score, reverse=True)[:limit]

    def group_by_source(self) -> dict[KnowledgeSource, list[UnifiedConcept]]:
        """Group concepts by their primary source."""
        grouped: dict[KnowledgeSource, list[UnifiedConcept]] = {}
        for concept in self.concepts:
            for source in concept.sources:
                if source not in grouped:
                    grouped[source] = []
                grouped[source].append(concept)
        return grouped


@dataclass
class LookupConfig:
    """Configuration for knowledge lookup operations."""

    # Sources to query
    enabled_sources: list[KnowledgeSource] = field(default_factory=list)

    # Query parameters
    max_results_per_source: int = 20
    timeout_per_source: float = 30.0
    parallel_queries: bool = True

    # Result filtering
    min_confidence_threshold: float = 0.0
    preferred_languages: list[str] = field(default_factory=lambda: ["en"])
    concept_types: list[ConceptType] | None = None

    # Rate limiting
    rate_limits: dict[KnowledgeSource, float] = field(default_factory=dict)

    @classmethod
    def with_all_sources(cls) -> "LookupConfig":
        """Create a LookupConfig with all knowledge sources enabled."""
        return cls(enabled_sources=list(KnowledgeSource))

    # Deduplication and merging
    enable_deduplication: bool = True
    similarity_threshold: float = 0.8
    merge_similar_concepts: bool = True

    # Ontology mapping
    enable_ontology_mapping: bool = True

    # API keys for external services
    api_keys: dict[str, str] = field(default_factory=dict)

    def get_api_key(self, service: str) -> str | None:
        """Get API key for a specific service. Checks config first, then .env."""
        key = self.api_keys.get(service)
        if key:
            return key
        try:
            import os

            from dotenv import load_dotenv

            load_dotenv()
            # Try upper-case and lower-case variants
            env_key = os.getenv(f"{service.upper()}_API_KEY") or os.getenv(
                f"{service.lower()}_api_key"
            )
            return env_key
        except ImportError:
            return None

    def is_source_enabled(self, source: KnowledgeSource) -> bool:
        """Check if a source is enabled for queries."""
        return source in self.enabled_sources
