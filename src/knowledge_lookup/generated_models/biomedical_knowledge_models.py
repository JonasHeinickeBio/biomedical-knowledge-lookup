from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
)

metamodel_version = "1.11.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_name=True,
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        use_enum_values=True,
        strict=False,
    )


class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key: str):
        return getattr(self.root, key)

    def __getitem__(self, key: str):
        return self.root[key]

    def __setitem__(self, key: str, value):
        self.root[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta(
    {
        "default_prefix": "biok",
        "description": "LinkML schema for biomedical knowledge lookup data models",
        "id": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
        "name": "biomedical_knowledge_schema",
        "prefixes": {
            "biok": {
                "prefix_prefix": "biok",
                "prefix_reference": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/",
            },
            "biop": {
                "prefix_prefix": "biop",
                "prefix_reference": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/",
            },
            "linkml": {"prefix_prefix": "linkml", "prefix_reference": "https://w3id.org/linkml/"},
            "pymodels": {
                "prefix_prefix": "pymodels",
                "prefix_reference": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/pydantic/",
            },
            "xsd": {
                "prefix_prefix": "xsd",
                "prefix_reference": "http://www.w3.org/2001/XMLSchema#",
            },
        },
        "source_file": "linkml/biomedical_knowledge_schema.yaml",
        "types": {
            "boolean": {
                "base": "bool",
                "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
                "name": "boolean",
                "uri": "xsd:boolean",
            },
            "datetime": {
                "base": "datetime",
                "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
                "name": "datetime",
                "uri": "xsd:dateTime",
            },
            "float": {
                "base": "float",
                "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
                "name": "float",
                "uri": "xsd:float",
            },
            "integer": {
                "base": "int",
                "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
                "name": "integer",
                "uri": "xsd:integer",
            },
            "string": {
                "base": "str",
                "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
                "name": "string",
                "uri": "xsd:string",
            },
            "uri": {
                "base": "str",
                "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema",
                "name": "uri",
                "uri": "xsd:anyURI",
            },
        },
    }
)


class KnowledgeSource(str, Enum):
    """
    Enumeration of supported knowledge sources
    """

    UMLS = "UMLS"
    """
    Unified Medical Language System
    """
    OLS = "OLS"
    """
    Ontology Lookup Service
    """
    BIOPORTAL = "BIOPORTAL"
    """
    BioPortal
    """
    BIOONTOLOGY = "BIOONTOLOGY"
    """
    Bioontology
    """
    OXO = "OXO"
    """
    Ontology X-References Ontology
    """
    WIKIDATA = "WIKIDATA"
    """
    Wikidata
    """
    DBPEDIA = "DBPEDIA"
    """
    DBpedia
    """
    TYTO = "TYTO"
    """
    Tyto
    """
    ZOOMA = "ZOOMA"
    """
    ZOOMA
    """
    BIOLINKER = "BIOLINKER"
    """
    Biolinker
    """
    NCBI = "NCBI"
    """
    NCBI
    """
    UNIPROT = "UNIPROT"
    """
    UniProt
    """
    ENSEMBL = "ENSEMBL"
    """
    Ensembl
    """
    PUBCHEM = "PUBCHEM"
    """
    PubChem
    """
    CHEMBL = "CHEMBL"
    """
    ChEMBL
    """
    UNICHEM = "UNICHEM"
    """
    UniChem
    """
    MONDO = "MONDO"
    """
    MONDO
    """
    DISGENET = "DISGENET"
    """
    DisGeNET
    """
    OPENTARGETS = "OPENTARGETS"
    """
    OpenTargets
    """
    REACTOME = "REACTOME"
    """
    Reactome
    """
    DRUGBANK = "DRUGBANK"
    """
    DrugBank
    """
    GO = "GO"
    """
    Gene Ontology
    """
    GENEONTOLOGY = "GENEONTOLOGY"
    """
    Gene Ontology
    """
    HPO = "HPO"
    """
    Human Phenotype Ontology
    """
    OBOFOUNDRY = "OBOFOUNDRY"
    """
    OBO Foundry
    """
    EBIOLS = "EBIOLS"
    """
    EBI Ontology Lookup Service
    """
    KEGG = "KEGG"
    """
    KEGG
    """
    QUICKGO = "QUICKGO"
    """
    QuickGO
    """
    MYGENEINFO = "MYGENEINFO"
    """
    MyGene.info
    """
    HGNC = "HGNC"
    """
    HGNC
    """
    EUTILS = "EUTILS"
    """
    EUtils
    """
    EUROPEPMC = "EUROPEPMC"
    """
    Europe PMC
    """
    OMIM = "OMIM"
    """
    OMIM
    """
    CLINVAR = "CLINVAR"
    """
    ClinVar
    """
    COSMIC = "COSMIC"
    """
    COSMIC
    """
    PDB = "PDB"
    """
    Protein Data Bank
    """
    INTERPRO = "INTERPRO"
    """
    InterPro
    """
    PFAM = "PFAM"
    """
    Pfam
    """
    STRING = "STRING"
    """
    STRING
    """


class ConceptType(str, Enum):
    """
    Types of biological concepts based on AID-PAIS ontology
    """

    DISEASE = "DISEASE"
    """
    A disease or disorder
    """
    SYMPTOM = "SYMPTOM"
    """
    A symptom
    """
    PHENOTYPE = "PHENOTYPE"
    """
    A phenotype
    """
    TREATMENT = "TREATMENT"
    """
    A treatment
    """
    DEMOGRAPHIC = "DEMOGRAPHIC"
    """
    A demographic feature
    """
    CASE_DEFINITION = "CASE_DEFINITION"
    """
    A case definition
    """
    PROGNOSIS = "PROGNOSIS"
    """
    A prognosis
    """
    MOLECULAR_ENTITY = "MOLECULAR_ENTITY"
    """
    A molecular entity
    """
    GENE = "GENE"
    """
    A gene
    """
    PROTEIN = "PROTEIN"
    """
    A protein
    """
    CYTOKINE = "CYTOKINE"
    """
    A cytokine
    """
    METABOLITE = "METABOLITE"
    """
    A metabolite
    """
    BIOMARKER = "BIOMARKER"
    """
    A biomarker
    """
    GENE_DISEASE_ASSOCIATION = "GENE_DISEASE_ASSOCIATION"
    """
    A gene-disease association
    """
    CHEMICAL = "CHEMICAL"
    """
    A chemical
    """
    DRUG = "DRUG"
    """
    A drug
    """
    ANATOMICAL_ENTITY = "ANATOMICAL_ENTITY"
    """
    An anatomical entity
    """
    ORGAN_SYSTEM = "ORGAN_SYSTEM"
    """
    An organ system
    """
    ORGAN = "ORGAN"
    """
    An organ
    """
    TISSUE = "TISSUE"
    """
    A tissue
    """
    CELL_TYPE = "CELL_TYPE"
    """
    A cell type
    """
    CELLULAR_COMPONENT = "CELLULAR_COMPONENT"
    """
    A cellular component
    """
    PROCEDURE = "PROCEDURE"
    """
    A procedure
    """
    BIOLOGICAL_PROCESS = "BIOLOGICAL_PROCESS"
    """
    A biological process
    """
    PHYSIOLOGICAL_PROCESS = "PHYSIOLOGICAL_PROCESS"
    """
    A physiological process
    """
    PATHOPHYSIOLOGICAL_PROCESS = "PATHOPHYSIOLOGICAL_PROCESS"
    """
    A pathophysiological process
    """
    MOLECULAR_FUNCTION = "MOLECULAR_FUNCTION"
    """
    A molecular function
    """
    OBSERVATION = "OBSERVATION"
    """
    An observation
    """
    ASSAY = "ASSAY"
    """
    An assay
    """
    EVIDENCE = "EVIDENCE"
    """
    Evidence
    """
    REFERENCE = "REFERENCE"
    """
    A reference
    """
    CITATION = "CITATION"
    """
    A citation
    """
    STUDY = "STUDY"
    """
    A study
    """
    CLINICAL_STUDY = "CLINICAL_STUDY"
    """
    A clinical study
    """
    LABORATORY_STUDY = "LABORATORY_STUDY"
    """
    A laboratory study
    """
    OBSERVATIONAL_STUDY = "OBSERVATIONAL_STUDY"
    """
    An observational study
    """
    COHORT_STUDY = "COHORT_STUDY"
    """
    A cohort study
    """
    CASE_STUDY = "CASE_STUDY"
    """
    A case study
    """
    CASE_CONTROL_STUDY = "CASE_CONTROL_STUDY"
    """
    A case-control study
    """
    RANDOMIZED_CONTROLLED_TRIAL = "RANDOMIZED_CONTROLLED_TRIAL"
    """
    A randomized controlled trial
    """
    CLINICAL_TRIAL = "CLINICAL_TRIAL"
    """
    A clinical trial
    """
    META_ANALYSIS = "META_ANALYSIS"
    """
    A meta-analysis
    """
    SYSTEMATIC_REVIEW = "SYSTEMATIC_REVIEW"
    """
    A systematic review
    """
    INTERVENTIONAL_STUDY = "INTERVENTIONAL_STUDY"
    """
    An interventional study
    """
    DIAGNOSTIC_TRIAL = "DIAGNOSTIC_TRIAL"
    """
    A diagnostic trial
    """
    COMMUNITY_TRIAL = "COMMUNITY_TRIAL"
    """
    A community trial
    """
    RETROSPECTIVE_COHORT_STUDY = "RETROSPECTIVE_COHORT_STUDY"
    """
    A retrospective cohort study
    """
    PROSPECTIVE_COHORT_STUDY = "PROSPECTIVE_COHORT_STUDY"
    """
    A prospective cohort study
    """
    PERSON = "PERSON"
    """
    A person
    """
    ORGANISM = "ORGANISM"
    """
    An organism
    """
    PATHWAY = "PATHWAY"
    """
    A pathway
    """
    ANATOMY = "ANATOMY"
    """
    Anatomy
    """
    UNKNOWN = "UNKNOWN"
    """
    Unknown concept type
    """


class ConfidenceLevel(str, Enum):
    """
    Confidence level for concept agreement
    """

    high = "high"
    """
    High confidence
    """
    medium = "medium"
    """
    Medium confidence
    """
    low = "low"
    """
    Low confidence
    """
    disputed = "disputed"
    """
    Disputed
    """


class ConceptIdentifier(ConfiguredBaseModel):
    """
    Represents an identifier for a concept in a specific knowledge source
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    source: KnowledgeSource = Field(
        default=...,
        description="""The knowledge source""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ConceptIdentifier", "ConceptMapping", "SourceAnnotation"]
            }
        },
    )
    identifier: str = Field(
        default=...,
        description="""The identifier string""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptIdentifier"]}},
    )
    label: str | None = Field(
        default=None,
        description="""The label for the concept""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptIdentifier"]}},
    )
    url: str | None = Field(
        default=None,
        description="""The URL to the concept in the source""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptIdentifier"]}},
    )


class ConceptMapping(ConfiguredBaseModel):
    """
    Represents a mapping between two concept identifiers
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    from_concept: ConceptIdentifier = Field(
        default=...,
        description="""The source concept identifier""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptMapping"]}},
    )
    to_concept: ConceptIdentifier = Field(
        default=...,
        description="""The target concept identifier""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptMapping"]}},
    )
    mapping_type: str | None = Field(
        default=None,
        description="""Type of mapping (exact, narrow, broad, related)""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptMapping"]}},
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for the mapping""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptMapping"]}},
    )
    source: str | None = Field(
        default=None,
        description="""Source of the mapping""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ConceptIdentifier", "ConceptMapping", "SourceAnnotation"]
            }
        },
    )


class UnifiedConcept(ConfiguredBaseModel):
    """
    Unified representation of a biological concept across multiple knowledge sources
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    primary_id: str = Field(
        default=...,
        description="""Primary identifier for the concept""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    primary_label: str = Field(
        default=...,
        description="""Primary label for the concept""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    concept_type: ConceptType | None = Field(
        default=None,
        description="""Type of concept""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    identifiers: list[ConceptIdentifier] | None = Field(
        default=None,
        description="""List of cross-reference identifiers""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    mappings: list[ConceptMapping] | None = Field(
        default=None,
        description="""List of concept mappings""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    labels: list[str] | None = Field(
        default=None,
        description="""Labels in different languages""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    synonyms: list[str] | None = Field(
        default=None,
        description="""List of synonyms""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    definitions: list[str] | None = Field(
        default=None,
        description="""List of definitions""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    semantic_types: list[str] | None = Field(
        default=None,
        description="""List of semantic types""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    categories: list[str] | None = Field(
        default=None,
        description="""List of categories""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    parents: list[str] | None = Field(
        default=None,
        description="""List of parent concept IDs""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    children: list[str] | None = Field(
        default=None,
        description="""List of child concept IDs""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    related: list[str] | None = Field(
        default=None,
        description="""List of related concept IDs""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    sources: list[KnowledgeSource] | None = Field(
        default=None,
        description="""Set of knowledge sources""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    confidence_score: float | None = Field(
        default=None,
        description="""Confidence score for the concept""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last update""",
        json_schema_extra={"linkml_meta": {"domain_of": ["UnifiedConcept"]}},
    )


class LookupResult(ConfiguredBaseModel):
    """
    Result of a knowledge lookup operation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    query: str = Field(
        default=...,
        description="""The original query string""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )
    concepts: list[UnifiedConcept] | None = Field(
        default=None,
        description="""List of matching concepts""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult", "SourceAnnotation"]}},
    )
    total_found: int | None = Field(
        default=None,
        description="""Total number of concepts found""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )
    sources_queried: list[KnowledgeSource] | None = Field(
        default=None,
        description="""List of sources that were queried""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )
    sources_succeeded: list[KnowledgeSource] | None = Field(
        default=None,
        description="""List of sources that succeeded""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )
    sources_failed: list[KnowledgeSource] | None = Field(
        default=None,
        description="""List of sources that failed""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )
    execution_time: float | None = Field(
        default=None,
        description="""Execution time in seconds""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )
    errors: list[str] | None = Field(
        default=None,
        description="""Dictionary of errors per source""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult"]}},
    )


class LookupConfig(ConfiguredBaseModel):
    """
    Configuration for knowledge lookup operations
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    enabled_sources: list[KnowledgeSource] | None = Field(
        default=None,
        description="""List of enabled knowledge sources""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    max_results_per_source: int | None = Field(
        default=None,
        description="""Maximum results per source""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    timeout_per_source: float | None = Field(
        default=None,
        description="""Timeout per source in seconds""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    parallel_queries: bool | None = Field(
        default=None,
        description="""Whether to run queries in parallel""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    min_confidence_threshold: float | None = Field(
        default=None,
        description="""Minimum confidence threshold""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    preferred_languages: list[str] | None = Field(
        default=None,
        description="""List of preferred languages""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    concept_types: list[ConceptType] | None = Field(
        default=None,
        description="""List of preferred concept types""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    rate_limits: list[float] | None = Field(
        default=None,
        description="""Rate limits per source (requests per second)""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    enable_deduplication: bool | None = Field(
        default=None,
        description="""Whether to enable deduplication""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    similarity_threshold: float | None = Field(
        default=None,
        description="""Similarity threshold for deduplication""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    merge_similar_concepts: bool | None = Field(
        default=None,
        description="""Whether to merge similar concepts""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    enable_ontology_mapping: bool | None = Field(
        default=None,
        description="""Whether to enable ontology mapping""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )
    api_keys: list[str] | None = Field(
        default=None,
        description="""API keys for external services""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupConfig"]}},
    )


class SourceAnnotation(ConfiguredBaseModel):
    """
    Annotation from a single knowledge source
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    source: KnowledgeSource = Field(
        default=...,
        description="""The knowledge source""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ConceptIdentifier", "ConceptMapping", "SourceAnnotation"]
            }
        },
    )
    concepts: list[UnifiedConcept] | None = Field(
        default=None,
        description="""List of annotated concepts""",
        json_schema_extra={"linkml_meta": {"domain_of": ["LookupResult", "SourceAnnotation"]}},
    )
    surface_forms: list[str] | None = Field(
        default=None,
        description="""List of surface forms found""",
        json_schema_extra={"linkml_meta": {"domain_of": ["SourceAnnotation"]}},
    )
    positions: list[str] | None = Field(
        default=None,
        description="""List of position dictionaries""",
        json_schema_extra={"linkml_meta": {"domain_of": ["SourceAnnotation"]}},
    )
    processing_time: float | None = Field(
        default=None,
        description="""Processing time in seconds""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SourceAnnotation", "MultiSourceAnnotationResult"]}
        },
    )
    error: str | None = Field(
        default=None,
        description="""Error message if any""",
        json_schema_extra={"linkml_meta": {"domain_of": ["SourceAnnotation"]}},
    )


class ConceptAgreement(ConfiguredBaseModel):
    """
    Agreement analysis for a concept across sources
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    primary_concept: UnifiedConcept = Field(
        default=...,
        description="""The primary concept""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptAgreement"]}},
    )
    agreeing_sources: list[KnowledgeSource] | None = Field(
        default=None,
        description="""Set of sources that agree""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptAgreement"]}},
    )
    disagreeing_sources: list[KnowledgeSource] | None = Field(
        default=None,
        description="""Set of sources that disagree""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptAgreement"]}},
    )
    alternative_concepts: list[UnifiedConcept] | None = Field(
        default=None,
        description="""List of alternative concepts""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptAgreement"]}},
    )
    confidence_level: ConfidenceLevel | None = Field(
        default=None,
        description="""Confidence level based on source agreement""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptAgreement"]}},
    )
    consensus_score: float | None = Field(
        default=None,
        description="""Consensus score""",
        json_schema_extra={"linkml_meta": {"domain_of": ["ConceptAgreement"]}},
    )


class MultiSourceAnnotationResult(ConfiguredBaseModel):
    """
    Complete annotation result from multiple sources
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "from_schema": "https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema"
        }
    )

    sentence: str = Field(
        default=...,
        description="""The original sentence""",
        json_schema_extra={"linkml_meta": {"domain_of": ["MultiSourceAnnotationResult"]}},
    )
    source_annotations: list[SourceAnnotation] | None = Field(
        default=None,
        description="""Annotations from each source""",
        json_schema_extra={"linkml_meta": {"domain_of": ["MultiSourceAnnotationResult"]}},
    )
    consensus_concepts: list[ConceptAgreement] | None = Field(
        default=None,
        description="""Consensus concepts""",
        json_schema_extra={"linkml_meta": {"domain_of": ["MultiSourceAnnotationResult"]}},
    )
    discrepancies: list[str] | None = Field(
        default=None,
        description="""List of discrepancies""",
        json_schema_extra={"linkml_meta": {"domain_of": ["MultiSourceAnnotationResult"]}},
    )
    overall_confidence: float | None = Field(
        default=None,
        description="""Overall confidence score""",
        json_schema_extra={"linkml_meta": {"domain_of": ["MultiSourceAnnotationResult"]}},
    )
    processing_time: float | None = Field(
        default=None,
        description="""Total processing time in seconds""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SourceAnnotation", "MultiSourceAnnotationResult"]}
        },
    )
    annotation_stats: str | None = Field(
        default=None,
        description="""Annotation statistics""",
        json_schema_extra={"linkml_meta": {"domain_of": ["MultiSourceAnnotationResult"]}},
    )


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ConceptIdentifier.model_rebuild()
ConceptMapping.model_rebuild()
UnifiedConcept.model_rebuild()
LookupResult.model_rebuild()
LookupConfig.model_rebuild()
SourceAnnotation.model_rebuild()
ConceptAgreement.model_rebuild()
MultiSourceAnnotationResult.model_rebuild()
