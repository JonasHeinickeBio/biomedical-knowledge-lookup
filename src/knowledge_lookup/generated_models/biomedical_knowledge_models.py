from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.11.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'biok',
     'description': 'LinkML schema for biomedical knowledge lookup data models',
     'id': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
     'name': 'biomedical_knowledge_schema',
     'prefixes': {'biok': {'prefix_prefix': 'biok',
                           'prefix_reference': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/'},
                  'biop': {'prefix_prefix': 'biop',
                           'prefix_reference': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'pymodels': {'prefix_prefix': 'pymodels',
                               'prefix_reference': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/pydantic/'},
                  'xsd': {'prefix_prefix': 'xsd',
                          'prefix_reference': 'http://www.w3.org/2001/XMLSchema#'}},
     'source_file': 'linkml/biomedical_knowledge_schema.yaml',
     'types': {'boolean': {'base': 'bool',
                           'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                           'name': 'boolean',
                           'uri': 'xsd:boolean'},
               'datetime': {'base': 'datetime',
                            'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                            'name': 'datetime',
                            'uri': 'xsd:dateTime'},
               'float': {'base': 'float',
                         'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                         'name': 'float',
                         'uri': 'xsd:float'},
               'integer': {'base': 'int',
                           'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                           'name': 'integer',
                           'uri': 'xsd:integer'},
               'json_string': {'base': 'str',
                               'description': 'A JSON-serialized string for '
                                              'complex nested data (dicts, lists '
                                              'of dicts)',
                               'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                               'name': 'json_string',
                               'uri': 'xsd:string'},
               'string': {'base': 'str',
                          'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                          'name': 'string',
                          'uri': 'xsd:string'},
               'uri': {'base': 'str',
                       'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema',
                       'name': 'uri',
                       'uri': 'xsd:anyURI'}}} )

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
    DBVAR = "DBVAR"
    """
    dbVar
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


class CircuitState(str, Enum):
    """
    State of a circuit breaker for source health tracking
    """
    CLOSED = "CLOSED"
    """
    Normal operation — requests pass through
    """
    OPEN = "OPEN"
    """
    Failing — requests are short-circuited
    """
    HALF_OPEN = "HALF_OPEN"
    """
    Probing — single test request allowed
    """


class ErrorCategory(str, Enum):
    """
    Category of an error for determining retry strategy
    """
    NETWORK_ERROR = "NETWORK_ERROR"
    """
    Connection/DNS/timeout/SSL errors — transient, retry fast
    """
    RATE_LIMITED = "RATE_LIMITED"
    """
    HTTP 429/403 quota — retry with exponential backoff
    """
    SERVER_ERROR = "SERVER_ERROR"
    """
    HTTP 5xx — server-side, retry with moderate backoff
    """
    TRANSIENT = "TRANSIENT"
    """
    Other temporary errors that might resolve on retry
    """
    CLIENT_ERROR = "CLIENT_ERROR"
    """
    HTTP 4xx (except 429) — not retryable
    """
    UNKNOWN = "UNKNOWN"
    """
    Unclassified — cautious single retry then give up
    """



class ConceptIdentifier(ConfiguredBaseModel):
    """
    Represents an identifier for a concept in a specific knowledge source
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    source: KnowledgeSource = Field(default=..., description="""The knowledge source""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier',
                       'ConceptMapping',
                       'SourceHealth',
                       'RetryInfo',
                       'SourceAnnotation']} })
    identifier: str = Field(default=..., description="""The identifier string""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier']} })
    label: Optional[str] = Field(default=None, description="""The label for the concept""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier']} })
    url: Optional[str] = Field(default=None, description="""The URL to the concept in the source""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier']} })


class ConceptMapping(ConfiguredBaseModel):
    """
    Represents a mapping between two concept identifiers
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    from_concept: ConceptIdentifier = Field(default=..., description="""The source concept identifier""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptMapping']} })
    to_concept: ConceptIdentifier = Field(default=..., description="""The target concept identifier""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptMapping']} })
    mapping_type: Optional[str] = Field(default=None, description="""Type of mapping (exact, narrow, broad, related)""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptMapping']} })
    confidence: Optional[float] = Field(default=None, description="""Confidence score for the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptMapping']} })
    source: Optional[str] = Field(default=None, description="""Source of the mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier',
                       'ConceptMapping',
                       'SourceHealth',
                       'RetryInfo',
                       'SourceAnnotation']} })


class UnifiedConcept(ConfiguredBaseModel):
    """
    Unified representation of a biological concept across multiple knowledge sources
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    primary_id: str = Field(default=..., description="""Primary identifier for the concept""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    primary_label: str = Field(default=..., description="""Primary label for the concept""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    concept_type: Optional[ConceptType] = Field(default=None, description="""Type of concept""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    identifiers: Optional[list[ConceptIdentifier]] = Field(default=None, description="""List of cross-reference identifiers""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    mappings: Optional[list[ConceptMapping]] = Field(default=None, description="""List of concept mappings""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    labels: Optional[str] = Field(default=None, description="""Labels in different languages (JSON-serialized dict of language->label)""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    synonyms: Optional[list[str]] = Field(default=None, description="""List of synonyms""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    definitions: Optional[list[str]] = Field(default=None, description="""List of definitions""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    semantic_types: Optional[list[str]] = Field(default=None, description="""List of semantic types""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    categories: Optional[list[str]] = Field(default=None, description="""List of categories""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    parents: Optional[list[str]] = Field(default=None, description="""List of parent concept IDs""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    children: Optional[list[str]] = Field(default=None, description="""List of child concept IDs""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    related: Optional[list[str]] = Field(default=None, description="""List of related concept IDs""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    sources: Optional[list[KnowledgeSource]] = Field(default=None, description="""Set of knowledge sources""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    confidence_score: Optional[float] = Field(default=None, description="""Confidence score for the concept""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    last_updated: Optional[datetime] = Field(default=None, description="""Timestamp of last update""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })
    source_data: Optional[str] = Field(default=None, description="""Raw data from sources (JSON-serialized dict of source->raw data)""", json_schema_extra = { "linkml_meta": {'domain_of': ['UnifiedConcept']} })


class SourceHealth(ConfiguredBaseModel):
    """
    Runtime health snapshot for a single knowledge source fed by circuit breakers
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    source: KnowledgeSource = Field(default=..., description="""The knowledge source""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier',
                       'ConceptMapping',
                       'SourceHealth',
                       'RetryInfo',
                       'SourceAnnotation']} })
    circuit_state: Optional[CircuitState] = Field(default=None, description="""Current circuit breaker state""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    failure_count: Optional[int] = Field(default=None, description="""Current consecutive failure count""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    threshold: Optional[int] = Field(default=None, description="""Failure threshold before circuit opens""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    cooldown: Optional[float] = Field(default=None, description="""Cooldown period in seconds before half-open probe""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    total_calls: Optional[int] = Field(default=None, description="""Total calls made to this source""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    total_failures: Optional[int] = Field(default=None, description="""Total failures recorded""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    total_successes: Optional[int] = Field(default=None, description="""Total successes recorded""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    health_score: Optional[float] = Field(default=None, description="""Health score 0..1 based on success/failure ratio""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    last_error: Optional[str] = Field(default=None, description="""Last error message recorded""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })
    is_open: Optional[bool] = Field(default=None, description="""Derived property — true if circuit_state is OPEN""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceHealth']} })


class RetryInfo(ConfiguredBaseModel):
    """
    Per-source retry statistics for a single operation
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    source: KnowledgeSource = Field(default=..., description="""The knowledge source""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier',
                       'ConceptMapping',
                       'SourceHealth',
                       'RetryInfo',
                       'SourceAnnotation']} })
    attempts: Optional[int] = Field(default=None, description="""Number of attempts made""", json_schema_extra = { "linkml_meta": {'domain_of': ['RetryInfo']} })
    max_attempts: Optional[int] = Field(default=None, description="""Maximum allowed attempts""", json_schema_extra = { "linkml_meta": {'domain_of': ['RetryInfo']} })
    last_delay: Optional[float] = Field(default=None, description="""Last delay applied between retries in seconds""", json_schema_extra = { "linkml_meta": {'domain_of': ['RetryInfo']} })
    strategy: Optional[str] = Field(default=None, description="""Retry strategy name used""", json_schema_extra = { "linkml_meta": {'domain_of': ['RetryInfo']} })
    success: Optional[bool] = Field(default=None, description="""Whether the operation ultimately succeeded""", json_schema_extra = { "linkml_meta": {'domain_of': ['RetryInfo']} })
    error_category: Optional[ErrorCategory] = Field(default=None, description="""Category of the error if the operation failed""", json_schema_extra = { "linkml_meta": {'domain_of': ['RetryInfo']} })


class LookupResult(ConfiguredBaseModel):
    """
    Result of a knowledge lookup operation
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    query: str = Field(default=..., description="""The original query string""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    concepts: Optional[list[UnifiedConcept]] = Field(default=None, description="""List of matching concepts""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult', 'SourceAnnotation']} })
    total_found: Optional[int] = Field(default=None, description="""Total number of concepts found""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    sources_queried: Optional[list[KnowledgeSource]] = Field(default=None, description="""List of sources that were queried""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    sources_succeeded: Optional[list[KnowledgeSource]] = Field(default=None, description="""List of sources that succeeded""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    sources_failed: Optional[list[KnowledgeSource]] = Field(default=None, description="""List of sources that failed""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    execution_time: Optional[float] = Field(default=None, description="""Execution time in seconds""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    errors: Optional[str] = Field(default=None, description="""Dictionary of errors per source (JSON-serialized dict)""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })
    source_health: Optional[str] = Field(default=None, description="""Health snapshot for all tracked sources (JSON-serialized dict of source->SourceHealth)""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult']} })


class LookupConfig(ConfiguredBaseModel):
    """
    Configuration for knowledge lookup operations
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    enabled_sources: Optional[list[KnowledgeSource]] = Field(default=None, description="""List of enabled knowledge sources""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    max_results_per_source: Optional[int] = Field(default=None, description="""Maximum results per source""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    timeout_per_source: Optional[float] = Field(default=None, description="""Timeout per source in seconds""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    parallel_queries: Optional[bool] = Field(default=None, description="""Whether to run queries in parallel""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    min_confidence_threshold: Optional[float] = Field(default=None, description="""Minimum confidence threshold""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    preferred_languages: Optional[list[str]] = Field(default=None, description="""List of preferred languages""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    concept_types: Optional[list[ConceptType]] = Field(default=None, description="""List of preferred concept types""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    rate_limits: Optional[str] = Field(default=None, description="""Rate limits per source (requests per second, JSON-serialized dict)""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    enable_deduplication: Optional[bool] = Field(default=None, description="""Whether to enable deduplication""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    similarity_threshold: Optional[float] = Field(default=None, description="""Similarity threshold for deduplication""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    merge_similar_concepts: Optional[bool] = Field(default=None, description="""Whether to merge similar concepts""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    enable_ontology_mapping: Optional[bool] = Field(default=None, description="""Whether to enable ontology mapping""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    api_keys: Optional[str] = Field(default=None, description="""API keys for external services (JSON-serialized dict)""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    circuit_breaker_threshold: Optional[int] = Field(default=None, description="""Failure threshold before circuit breaker opens (default: 5)""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    circuit_breaker_cooldown: Optional[float] = Field(default=None, description="""Cooldown period in seconds before half-open probe (default: 30.0)""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })
    enable_source_health_tracking: Optional[bool] = Field(default=None, description="""Whether to enable source health tracking via circuit breakers""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupConfig']} })


class SourceAnnotation(ConfiguredBaseModel):
    """
    Annotation from a single knowledge source
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    source: KnowledgeSource = Field(default=..., description="""The knowledge source""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptIdentifier',
                       'ConceptMapping',
                       'SourceHealth',
                       'RetryInfo',
                       'SourceAnnotation']} })
    concepts: Optional[list[UnifiedConcept]] = Field(default=None, description="""List of annotated concepts""", json_schema_extra = { "linkml_meta": {'domain_of': ['LookupResult', 'SourceAnnotation']} })
    surface_forms: Optional[list[str]] = Field(default=None, description="""List of surface forms found""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceAnnotation']} })
    positions: Optional[list[str]] = Field(default=None, description="""List of position dictionaries (JSON-serialized string)""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceAnnotation']} })
    processing_time: Optional[float] = Field(default=None, description="""Processing time in seconds""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceAnnotation', 'MultiSourceAnnotationResult']} })
    error: Optional[str] = Field(default=None, description="""Error message if any""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceAnnotation']} })


class ConceptAgreement(ConfiguredBaseModel):
    """
    Agreement analysis for a concept across sources
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    primary_concept: UnifiedConcept = Field(default=..., description="""The primary concept""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptAgreement']} })
    agreeing_sources: Optional[list[KnowledgeSource]] = Field(default=None, description="""Set of sources that agree""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptAgreement']} })
    disagreeing_sources: Optional[list[KnowledgeSource]] = Field(default=None, description="""Set of sources that disagree""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptAgreement']} })
    alternative_concepts: Optional[list[UnifiedConcept]] = Field(default=None, description="""List of alternative concepts""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptAgreement']} })
    confidence_level: Optional[ConfidenceLevel] = Field(default=None, description="""Confidence level based on source agreement""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptAgreement']} })
    consensus_score: Optional[float] = Field(default=None, description="""Consensus score""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConceptAgreement']} })


class MultiSourceAnnotationResult(ConfiguredBaseModel):
    """
    Complete annotation result from multiple sources
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup/linkml/schema'})

    sentence: str = Field(default=..., description="""The original sentence""", json_schema_extra = { "linkml_meta": {'domain_of': ['MultiSourceAnnotationResult']} })
    source_annotations: Optional[list[SourceAnnotation]] = Field(default=None, description="""Annotations from each source""", json_schema_extra = { "linkml_meta": {'domain_of': ['MultiSourceAnnotationResult']} })
    consensus_concepts: Optional[list[ConceptAgreement]] = Field(default=None, description="""Consensus concepts""", json_schema_extra = { "linkml_meta": {'domain_of': ['MultiSourceAnnotationResult']} })
    discrepancies: Optional[list[str]] = Field(default=None, description="""List of discrepancy dicts (JSON-serialized)""", json_schema_extra = { "linkml_meta": {'domain_of': ['MultiSourceAnnotationResult']} })
    overall_confidence: Optional[float] = Field(default=None, description="""Overall confidence score""", json_schema_extra = { "linkml_meta": {'domain_of': ['MultiSourceAnnotationResult']} })
    processing_time: Optional[float] = Field(default=None, description="""Total processing time in seconds""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceAnnotation', 'MultiSourceAnnotationResult']} })
    annotation_stats: Optional[str] = Field(default=None, description="""Annotation statistics dict (JSON-serialized)""", json_schema_extra = { "linkml_meta": {'domain_of': ['MultiSourceAnnotationResult']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ConceptIdentifier.model_rebuild()
ConceptMapping.model_rebuild()
UnifiedConcept.model_rebuild()
SourceHealth.model_rebuild()
RetryInfo.model_rebuild()
LookupResult.model_rebuild()
LookupConfig.model_rebuild()
SourceAnnotation.model_rebuild()
ConceptAgreement.model_rebuild()
MultiSourceAnnotationResult.model_rebuild()
