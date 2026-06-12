"""
Unified RDF Converter for Knowledge Graph Integration

Converts UnifiedConcept objects from knowledge lookup adapters into RDF triples
that integrate with the AID-PAIS biomedical knowledge graph.

Supports all ConceptType enums and provides extensible architecture for
25+ adapters with adapter-specific customization hints.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from .models import ConceptIdentifier, ConceptType, KnowledgeSource, UnifiedConcept

logger = logging.getLogger(__name__)


class RDFNamespaces:
    """Centralized namespace management for AID-PAIS knowledge graph."""

    # Core AID-PAIS namespaces (aligned with existing ontology)
    AIDPAIS = Namespace("http://www.aid-pais-kg.org/")
    VOCAB = Namespace("http://www.aid-pais-kg.org/vocab/")
    SYMPTOM = Namespace("http://www.aid-pais-kg.org/Symptom/")

    # External biomedical namespaces
    CHEMBL = Namespace("https://www.ebi.ac.uk/chembl/compound/")
    PUBCHEM = Namespace("https://pubchem.ncbi.nlm.nih.gov/compound/")
    DRUGBANK = Namespace("https://www.drugbank.ca/drugs/")
    UNICHEM = Namespace("https://www.ebi.ac.uk/unichem/compoundsources/")
    UNIPROT = Namespace("https://www.uniprot.org/uniprotkb/")
    ENSEMBL = Namespace("https://www.ensembl.org/id/")
    NCBI = Namespace("https://www.ncbi.nlm.nih.gov/")
    OLS = Namespace("https://www.ebi.ac.uk/ols4/api/ontologies/")

    # Standard RDF namespaces
    RDF = RDF
    RDFS = RDFS
    OWL = Namespace("http://www.w3.org/2002/07/owl#")
    XSD = XSD

    @classmethod
    def get_namespace_bindings(cls) -> dict[str, Namespace | Any]:
        """Get all namespace bindings for RDF graph initialization."""
        return {
            "aidpais": cls.AIDPAIS,
            "vocab": cls.VOCAB,
            "symptom": cls.SYMPTOM,
            "chembl": cls.CHEMBL,
            "pubchem": cls.PUBCHEM,
            "drugbank": cls.DRUGBANK,
            "unichem": cls.UNICHEM,
            "uniprot": cls.UNIPROT,
            "ensembl": cls.ENSEMBL,
            "ncbi": cls.NCBI,
            "ols": cls.OLS,
            "rdf": cls.RDF,
            "rdfs": cls.RDFS,
            "owl": cls.OWL,
            "xsd": cls.XSD,
        }


class ConceptTypeHandler(ABC):
    """Abstract base class for concept-type specific RDF conversion handlers."""

    def __init__(self, namespaces: RDFNamespaces):
        self.namespaces = namespaces

    @abstractmethod
    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        """Get the RDF class URI for this concept type."""
        pass

    @abstractmethod
    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        """Get the primary URI for this concept."""
        pass

    @abstractmethod
    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add concept-type specific RDF properties."""
        pass

    def add_common_properties(self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef):
        """Add common properties shared across all concept types."""
        # Basic properties
        graph.add((concept_uri, self.namespaces.RDF.type, self.get_concept_class_uri(concept)))
        graph.add((concept_uri, self.namespaces.RDFS.label, Literal(concept.primary_label)))

        # Concept type
        graph.add(
            (concept_uri, self.namespaces.VOCAB.conceptType, Literal(concept.concept_type.value))
        )

        # Confidence score
        if concept.confidence_score > 0:
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.confidenceScore,
                    Literal(concept.confidence_score, datatype=self.namespaces.XSD.float),
                )
            )

        # Categories
        for category in concept.categories:
            graph.add((concept_uri, self.namespaces.VOCAB.hasCategory, Literal(category)))

        # Synonyms
        for synonym in concept.synonyms:
            graph.add((concept_uri, self.namespaces.VOCAB.hasSynonym, Literal(synonym)))

        # Definitions
        for definition in concept.definitions:
            graph.add((concept_uri, self.namespaces.VOCAB.hasDefinition, Literal(definition)))

        # Semantic types
        for sem_type in concept.semantic_types:
            graph.add((concept_uri, self.namespaces.VOCAB.hasSemanticType, Literal(sem_type)))

        # Labels in different languages
        for lang, label in concept.labels.items():
            graph.add((concept_uri, self.namespaces.RDFS.label, Literal(label, lang=lang)))

        # Relationships
        for parent in concept.parents:
            parent_uri = URIRef(parent)  # Could be enhanced to resolve to proper URIs
            graph.add((concept_uri, self.namespaces.VOCAB.hasParent, parent_uri))

        for child in concept.children:
            child_uri = URIRef(child)
            graph.add((concept_uri, self.namespaces.VOCAB.hasChild, child_uri))

        for related in concept.related:
            related_uri = URIRef(related)
            graph.add((concept_uri, self.namespaces.VOCAB.relatedTo, related_uri))


class ChemicalHandler(ConceptTypeHandler):
    """RDF handler for chemical compounds."""

    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS.Compound

    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        # Use UniChem ID as primary URI if available, otherwise use primary_id
        unichem_id = None
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.UNICHEM:
                unichem_id = identifier.identifier
                break

        if unichem_id:
            return self.namespaces.UNICHEM[unichem_id]
        else:
            return self.namespaces.AIDPAIS[f"compound/{concept.primary_id}"]

    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add chemical-specific properties and cross-references."""
        # Add cross-references with proper namespaces
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.CHEMBL:
                chembl_uri = self.namespaces.CHEMBL[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasChEMBLId, chembl_uri))
                graph.add(
                    (chembl_uri, self.namespaces.RDFS.label, Literal(identifier.label or ""))
                )
                graph.add((chembl_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.PUBCHEM:
                pubchem_uri = self.namespaces.PUBCHEM[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasPubChemId, pubchem_uri))
                graph.add(
                    (pubchem_uri, self.namespaces.RDFS.label, Literal(identifier.label or ""))
                )
                graph.add((pubchem_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.DRUGBANK:
                drugbank_uri = self.namespaces.DRUGBANK[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasDrugBankId, drugbank_uri))
                graph.add(
                    (drugbank_uri, self.namespaces.RDFS.label, Literal(identifier.label or ""))
                )
                graph.add((drugbank_uri, self.namespaces.OWL.sameAs, concept_uri))

            # Add generic cross-reference
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.hasIdentifier,
                    Literal(f"{identifier.source.value}:{identifier.identifier}"),
                )
            )


class DiseaseHandler(ConceptTypeHandler):
    """RDF handler for diseases."""

    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS.Disease

    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        # Use MONDO ID if available, otherwise use primary_id
        mondo_id = None
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.MONDO:
                mondo_id = identifier.identifier
                break

        if mondo_id:
            return self.namespaces.OLS[f"mondo/{mondo_id}"]
        else:
            return self.namespaces.AIDPAIS[f"disease/{concept.primary_id}"]

    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add disease-specific properties."""
        # Disease-specific cross-references
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.MONDO:
                mondo_uri = self.namespaces.OLS[f"mondo/{identifier.identifier}"]
                graph.add((concept_uri, self.namespaces.VOCAB.hasMondoId, mondo_uri))
                graph.add((mondo_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.OXO:
                oxo_uri = self.namespaces.OLS[f"oxo/{identifier.identifier}"]
                graph.add((concept_uri, self.namespaces.VOCAB.hasOxoId, oxo_uri))
                graph.add((oxo_uri, self.namespaces.OWL.sameAs, concept_uri))

            # Add generic cross-reference
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.hasIdentifier,
                    Literal(f"{identifier.source.value}:{identifier.identifier}"),
                )
            )


class GeneHandler(ConceptTypeHandler):
    """RDF handler for genes."""

    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS.Gene

    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        # Use Ensembl ID if available, otherwise use primary_id
        ensembl_id = None
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.ENSEMBL:
                ensembl_id = identifier.identifier
                break

        if ensembl_id:
            return self.namespaces.ENSEMBL[ensembl_id]
        else:
            return self.namespaces.AIDPAIS[f"gene/{concept.primary_id}"]

    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add gene-specific properties."""
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.ENSEMBL:
                ensembl_uri = self.namespaces.ENSEMBL[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasEnsemblId, ensembl_uri))
                graph.add((ensembl_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.UNIPROT:
                uniprot_uri = self.namespaces.UNIPROT[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasUniProtId, uniprot_uri))
                graph.add((uniprot_uri, self.namespaces.OWL.sameAs, concept_uri))

            # Add generic cross-reference
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.hasIdentifier,
                    Literal(f"{identifier.source.value}:{identifier.identifier}"),
                )
            )


class ProteinHandler(ConceptTypeHandler):
    """RDF handler for proteins."""

    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS.Protein

    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        # Use UniProt ID if available, otherwise use primary_id
        uniprot_id = None
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.UNIPROT:
                uniprot_id = identifier.identifier
                break

        if uniprot_id:
            return self.namespaces.UNIPROT[uniprot_id]
        else:
            return self.namespaces.AIDPAIS[f"protein/{concept.primary_id}"]

    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add protein-specific properties."""
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.UNIPROT:
                uniprot_uri = self.namespaces.UNIPROT[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasUniProtId, uniprot_uri))
                graph.add((uniprot_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.ENSEMBL:
                ensembl_uri = self.namespaces.ENSEMBL[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasEnsemblId, ensembl_uri))
                graph.add((ensembl_uri, self.namespaces.OWL.sameAs, concept_uri))

            # Add generic cross-reference
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.hasIdentifier,
                    Literal(f"{identifier.source.value}:{identifier.identifier}"),
                )
            )


class DrugHandler(ConceptTypeHandler):
    """RDF handler for drugs."""

    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS.Drug

    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        # Use DrugBank ID if available, otherwise ChEMBL, otherwise primary_id
        drugbank_id = None
        chembl_id = None

        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.DRUGBANK:
                drugbank_id = identifier.identifier
            elif identifier.source == KnowledgeSource.CHEMBL:
                chembl_id = identifier.identifier

        if drugbank_id:
            return self.namespaces.DRUGBANK[drugbank_id]
        elif chembl_id:
            return self.namespaces.CHEMBL[chembl_id]
        else:
            return self.namespaces.AIDPAIS[f"drug/{concept.primary_id}"]

    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add drug-specific properties."""
        for identifier in concept.identifiers:
            if identifier.source == KnowledgeSource.DRUGBANK:
                drugbank_uri = self.namespaces.DRUGBANK[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasDrugBankId, drugbank_uri))
                graph.add((drugbank_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.CHEMBL:
                chembl_uri = self.namespaces.CHEMBL[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasChEMBLId, chembl_uri))
                graph.add((chembl_uri, self.namespaces.OWL.sameAs, concept_uri))

            elif identifier.source == KnowledgeSource.PUBCHEM:
                pubchem_uri = self.namespaces.PUBCHEM[identifier.identifier]
                graph.add((concept_uri, self.namespaces.VOCAB.hasPubChemId, pubchem_uri))
                graph.add((pubchem_uri, self.namespaces.OWL.sameAs, concept_uri))

            # Add generic cross-reference
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.hasIdentifier,
                    Literal(f"{identifier.source.value}:{identifier.identifier}"),
                )
            )


class DefaultHandler(ConceptTypeHandler):
    """Default handler for unknown or unspecified concept types."""

    def get_concept_class_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS.Concept

    def get_primary_uri(self, concept: UnifiedConcept) -> URIRef:
        return self.namespaces.AIDPAIS[f"concept/{concept.primary_id}"]

    def add_type_specific_properties(
        self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef
    ):
        """Add generic cross-references for unknown concept types."""
        for identifier in concept.identifiers:
            graph.add(
                (
                    concept_uri,
                    self.namespaces.VOCAB.hasIdentifier,
                    Literal(f"{identifier.source.value}:{identifier.identifier}"),
                )
            )


class AdapterHints:
    """Container for adapter-specific RDF conversion hints and customizations."""

    def __init__(self):
        self.custom_namespaces: dict[str, Namespace] = {}
        self.custom_predicates: dict[str, URIRef] = {}
        self.type_mappings: dict[ConceptType, URIRef] = {}
        self.identifier_mappings: dict[KnowledgeSource, dict[str, Any]] = {}

    def add_namespace(self, prefix: str, namespace: Namespace):
        """Add a custom namespace."""
        self.custom_namespaces[prefix] = namespace

    def add_predicate(self, name: str, predicate_uri: URIRef):
        """Add a custom predicate."""
        self.custom_predicates[name] = predicate_uri

    def add_type_mapping(self, concept_type: ConceptType, rdf_class: URIRef):
        """Map a concept type to a specific RDF class."""
        self.type_mappings[concept_type] = rdf_class

    def add_identifier_mapping(self, source: KnowledgeSource, mapping_config: dict[str, Any]):
        """Add identifier mapping configuration for a knowledge source."""
        self.identifier_mappings[source] = mapping_config


class UnifiedRDFConverter:
    """
    Unified RDF converter for biomedical knowledge graph integration.

    Converts UnifiedConcept objects from any knowledge lookup adapter into
    RDF triples that integrate seamlessly with the AID-PAIS knowledge graph.

    Features:
    - Support for all ConceptType enums (Disease, Drug, Gene, Protein, etc.)
    - Modular handler system for concept-type specific conversions
    - Adapter hints system for source-specific customizations
    - Extensible architecture for 25+ adapters
    - Integration with existing AID-PAIS ontology structure
    - Dynamic loading from ontology files
    """

    def __init__(
        self, adapter_hints: AdapterHints | None = None, use_dynamic_loading: bool = False
    ):
        """
        Initialize the RDF converter.

        Args:
            adapter_hints: Optional adapter-specific customization hints
            use_dynamic_loading: If True, load concept types dynamically from ontology
        """
        self.namespaces = RDFNamespaces()
        self.adapter_hints = adapter_hints or AdapterHints()
        self.ontology_loader: Any = None  # For dynamic loading

        if use_dynamic_loading:
            self.handlers = self._load_dynamic_handlers()
        else:
            self.handlers = self._load_static_handlers()

    @classmethod
    def from_ontology(
        cls, ontology_dir: str | None = None, adapter_hints: AdapterHints | None = None
    ) -> "UnifiedRDFConverter":
        """
        Create a UnifiedRDFConverter with dynamically loaded concept types from ontology.

        Args:
            ontology_dir: Directory containing ontology TTL files
            adapter_hints: Optional adapter-specific customization hints

        Returns:
            UnifiedRDFConverter with dynamic concept type handlers
        """
        instance = cls(adapter_hints=adapter_hints, use_dynamic_loading=True)
        if ontology_dir:
            # Override the default ontology directory
            from .ontology_concept_loader import OntologyConceptLoader

            instance.ontology_loader = OntologyConceptLoader(ontology_dir)
            instance.handlers = instance._load_dynamic_handlers()
        return instance

    def _load_static_handlers(self) -> dict[ConceptType, ConceptTypeHandler]:
        """Load the static (manually defined) concept type handlers."""
        return {
            # Clinical entities
            ConceptType.DISEASE: DiseaseHandler(self.namespaces),
            ConceptType.SYMPTOM: DefaultHandler(self.namespaces),
            ConceptType.PHENOTYPE: DefaultHandler(self.namespaces),
            ConceptType.TREATMENT: DefaultHandler(self.namespaces),
            ConceptType.DEMOGRAPHIC: DefaultHandler(self.namespaces),
            ConceptType.CASE_DEFINITION: DefaultHandler(self.namespaces),
            ConceptType.PROGNOSIS: DefaultHandler(self.namespaces),
            # Molecular entities
            ConceptType.MOLECULAR_ENTITY: DefaultHandler(self.namespaces),
            ConceptType.GENE: GeneHandler(self.namespaces),
            ConceptType.PROTEIN: ProteinHandler(self.namespaces),
            ConceptType.CYTOKINE: ProteinHandler(
                self.namespaces
            ),  # Use protein handler for cytokines
            ConceptType.METABOLITE: ChemicalHandler(
                self.namespaces
            ),  # Use chemical handler for metabolites
            ConceptType.BIOMARKER: DefaultHandler(self.namespaces),
            ConceptType.GENE_DISEASE_ASSOCIATION: DefaultHandler(self.namespaces),
            # Chemical entities
            ConceptType.CHEMICAL: ChemicalHandler(self.namespaces),
            ConceptType.DRUG: DrugHandler(self.namespaces),
            # Anatomical entities
            ConceptType.ANATOMICAL_ENTITY: DefaultHandler(self.namespaces),
            ConceptType.ORGAN_SYSTEM: DefaultHandler(self.namespaces),
            ConceptType.ORGAN: DefaultHandler(self.namespaces),
            ConceptType.TISSUE: DefaultHandler(self.namespaces),
            ConceptType.CELL_TYPE: DefaultHandler(self.namespaces),
            ConceptType.CELLULAR_COMPONENT: DefaultHandler(self.namespaces),
            # Biological processes
            ConceptType.BIOLOGICAL_PROCESS: DefaultHandler(self.namespaces),
            ConceptType.PHYSIOLOGICAL_PROCESS: DefaultHandler(self.namespaces),
            ConceptType.PATHOPHYSIOLOGICAL_PROCESS: DefaultHandler(self.namespaces),
            ConceptType.MOLECULAR_FUNCTION: DefaultHandler(self.namespaces),
            # Measurement and observation
            ConceptType.OBSERVATION: DefaultHandler(self.namespaces),
            ConceptType.ASSAY: DefaultHandler(self.namespaces),
            # Evidence and study types
            ConceptType.EVIDENCE: DefaultHandler(self.namespaces),
            ConceptType.REFERENCE: DefaultHandler(self.namespaces),
            ConceptType.CITATION: DefaultHandler(self.namespaces),
            ConceptType.STUDY: DefaultHandler(self.namespaces),
            ConceptType.CLINICAL_STUDY: DefaultHandler(self.namespaces),
            ConceptType.LABORATORY_STUDY: DefaultHandler(self.namespaces),
            ConceptType.OBSERVATIONAL_STUDY: DefaultHandler(self.namespaces),
            ConceptType.COHORT_STUDY: DefaultHandler(self.namespaces),
            ConceptType.CASE_STUDY: DefaultHandler(self.namespaces),
            ConceptType.CASE_CONTROL_STUDY: DefaultHandler(self.namespaces),
            ConceptType.RANDOMIZED_CONTROLLED_TRIAL: DefaultHandler(self.namespaces),
            ConceptType.CLINICAL_TRIAL: DefaultHandler(self.namespaces),
            ConceptType.META_ANALYSIS: DefaultHandler(self.namespaces),
            ConceptType.SYSTEMATIC_REVIEW: DefaultHandler(self.namespaces),
            ConceptType.INTERVENTIONAL_STUDY: DefaultHandler(self.namespaces),
            ConceptType.DIAGNOSTIC_TRIAL: DefaultHandler(self.namespaces),
            ConceptType.COMMUNITY_TRIAL: DefaultHandler(self.namespaces),
            ConceptType.RETROSPECTIVE_COHORT_STUDY: DefaultHandler(self.namespaces),
            ConceptType.PROSPECTIVE_COHORT_STUDY: DefaultHandler(self.namespaces),
            # Other entities
            ConceptType.PERSON: DefaultHandler(self.namespaces),
            ConceptType.ORGANISM: DefaultHandler(self.namespaces),
            ConceptType.PROCEDURE: DefaultHandler(self.namespaces),
            # Backward compatibility
            ConceptType.PATHWAY: DefaultHandler(self.namespaces),
            ConceptType.ANATOMY: DefaultHandler(self.namespaces),
            ConceptType.UNKNOWN: DefaultHandler(self.namespaces),
        }

    def _load_dynamic_handlers(self) -> dict[ConceptType, ConceptTypeHandler]:
        """Load concept type handlers dynamically from ontology."""
        from .ontology_concept_loader import get_dynamic_concept_handlers

        try:
            dynamic_handlers = get_dynamic_concept_handlers()

            # Convert string keys to ConceptType enum values with flexible matching
            handlers = {}
            for concept_key, handler_class in dynamic_handlers.items():
                # Try multiple variations of the concept key
                concept_type = None

                # Try exact match first
                concept_type = getattr(ConceptType, concept_key.upper(), None)

                # Try with underscores
                if not concept_type:
                    underscored = concept_key.upper().replace(" ", "_").replace("-", "_")
                    concept_type = getattr(ConceptType, underscored, None)

                # Try removing spaces and converting to upper
                if not concept_type:
                    normalized = "".join(word.capitalize() for word in concept_key.split())
                    concept_type = getattr(ConceptType, normalized.upper(), None)

                if concept_type:
                    handlers[concept_type] = handler_class(self.namespaces)
                else:
                    logger.debug(f"No ConceptType enum found for ontology concept: {concept_key}")

            # Ensure UNKNOWN is always available
            if ConceptType.UNKNOWN not in handlers:
                handlers[ConceptType.UNKNOWN] = DefaultHandler(self.namespaces)

            logger.info(f"Loaded {len(handlers)} dynamic concept type handlers from ontology")
            return handlers

        except Exception as e:
            logger.error(f"Failed to load dynamic handlers: {e}. Falling back to static handlers.")
            return self._load_static_handlers()

    def convert_concepts_to_graph(self, concepts: list[UnifiedConcept]) -> Graph:
        """
        Convert a list of UnifiedConcept objects to an RDF graph.

        Args:
            concepts: List of concepts to convert

        Returns:
            RDFLib Graph containing the converted concepts
        """
        graph = Graph()

        # Bind all namespaces
        for prefix, namespace in self.namespaces.get_namespace_bindings().items():
            graph.bind(prefix, namespace)

        # Bind custom namespaces from adapter hints
        for prefix, namespace in self.adapter_hints.custom_namespaces.items():
            graph.bind(prefix, namespace)

        # Convert each concept
        for concept in concepts:
            self._convert_single_concept(graph, concept)

        logger.info(f"Converted {len(concepts)} concepts to RDF graph with {len(graph)} triples")
        return graph

    def _convert_single_concept(self, graph: Graph, concept: UnifiedConcept):
        """
        Convert a single UnifiedConcept to RDF triples.

        Args:
            graph: RDF graph to add triples to
            concept: Concept to convert
        """
        try:
            # Get the appropriate handler
            handler = self.handlers.get(concept.concept_type, self.handlers[ConceptType.UNKNOWN])

            # Apply adapter hints for type mapping if available
            if concept.concept_type in self.adapter_hints.type_mappings:
                # Custom type mapping would override handler
                pass  # For now, handlers take precedence

            # Get primary URI
            concept_uri = handler.get_primary_uri(concept)

            # Add common properties
            handler.add_common_properties(graph, concept, concept_uri)

            # Add type-specific properties
            handler.add_type_specific_properties(graph, concept, concept_uri)

            # Add mappings between concepts
            self._add_concept_mappings(graph, concept, concept_uri)

        except Exception as e:
            logger.error(f"Error converting concept {concept.primary_id}: {e}")
            # Continue with other concepts rather than failing completely

    def _add_concept_mappings(self, graph: Graph, concept: UnifiedConcept, concept_uri: URIRef):
        """Add RDF triples for concept mappings."""
        for mapping in concept.mappings:
            # Create URIs for source and target concepts
            to_uri = self._get_concept_uri_from_identifier(mapping.to_concept)

            # Add mapping relationship
            mapping_predicate = self.namespaces.VOCAB.hasMapping
            graph.add((concept_uri, mapping_predicate, to_uri))

            # Add mapping metadata
            mapping_uri = self.namespaces.AIDPAIS[
                f"mapping/{concept.primary_id}_{mapping.from_concept.identifier}_{mapping.to_concept.identifier}"
            ]
            graph.add((mapping_uri, self.namespaces.RDF.type, self.namespaces.VOCAB.Mapping))
            graph.add(
                (mapping_uri, self.namespaces.VOCAB.mappingType, Literal(mapping.mapping_type))
            )
            if mapping.confidence:
                graph.add(
                    (
                        mapping_uri,
                        self.namespaces.VOCAB.confidenceScore,
                        Literal(mapping.confidence, datatype=self.namespaces.XSD.float),
                    )
                )
            if mapping.source:
                graph.add(
                    (mapping_uri, self.namespaces.VOCAB.mappingSource, Literal(mapping.source))
                )

    def _get_concept_uri_from_identifier(self, identifier: ConceptIdentifier) -> URIRef:
        """Get URI for a concept based on its identifier."""
        # This is a simplified version - could be enhanced with more sophisticated URI resolution
        if identifier.source == KnowledgeSource.CHEMBL:
            return self.namespaces.CHEMBL[identifier.identifier]
        elif identifier.source == KnowledgeSource.PUBCHEM:
            return self.namespaces.PUBCHEM[identifier.identifier]
        elif identifier.source == KnowledgeSource.DRUGBANK:
            return self.namespaces.DRUGBANK[identifier.identifier]
        elif identifier.source == KnowledgeSource.UNIPROT:
            return self.namespaces.UNIPROT[identifier.identifier]
        elif identifier.source == KnowledgeSource.ENSEMBL:
            return self.namespaces.ENSEMBL[identifier.identifier]
        else:
            return self.namespaces.AIDPAIS[f"{identifier.source.value}/{identifier.identifier}"]

    def save_graph(self, graph: Graph, output_path: str | Path, format: str = "turtle") -> None:
        """
        Save an RDF graph to a file.

        Args:
            graph: RDF graph to save
            output_path: Path to save the file
            format: Serialization format ('turtle', 'xml', 'json-ld', 'nt')
        """
        output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Map format names
        format_mapping = {
            "turtle": "ttl",
            "ttl": "ttl",
            "xml": "xml",
            "rdf": "xml",
            "json-ld": "json-ld",
            "nt": "nt",
            "n3": "n3",
        }

        output_format = format_mapping.get(format.lower(), "ttl")

        # Serialize and save
        graph.serialize(output_path, format=output_format)
        logger.info(
            f"Saved RDF graph with {len(graph)} triples to {output_path} in {format} format"
        )

    def merge_with_existing_graph(
        self,
        new_graph: Graph,
        existing_graph_path: str | Path,
        output_path: str | Path,
    ) -> Graph:
        """
        Merge new concept data with an existing knowledge graph.

        Args:
            new_graph: RDF graph with new concept data
            existing_graph_path: Path to existing KG file
            output_path: Path to save merged graph

        Returns:
            Merged RDF graph
        """
        existing_graph_path = Path(existing_graph_path)
        output_path = Path(output_path)

        # Load existing graph
        existing_graph = Graph()
        existing_graph.parse(existing_graph_path, format="turtle")

        logger.info(f"Existing graph: {len(existing_graph)} triples")
        logger.info(f"New graph: {len(new_graph)} triples")

        # Merge graphs
        merged_graph = existing_graph + new_graph

        logger.info(f"Merged graph: {len(merged_graph)} triples")

        # Save merged graph
        self.save_graph(merged_graph, output_path, format="turtle")

        return merged_graph

    def convert_and_save(
        self, concepts: list[UnifiedConcept], output_path: str | Path, format: str = "turtle"
    ) -> Graph:
        """
        Convert concepts to RDF and save to file in one step.

        Args:
            concepts: List of concepts to convert
            output_path: Path to save the RDF file
            format: Serialization format

        Returns:
            The created RDF graph
        """
        graph = self.convert_concepts_to_graph(concepts)
        self.save_graph(graph, output_path, format)
        return graph

    def add_concept_type_handler(self, concept_type: ConceptType, handler: ConceptTypeHandler):
        """
        Add or override a concept type handler.

        This allows for extensibility - new handlers can be registered for
        new concept types or to override existing ones.

        Args:
            concept_type: The concept type this handler handles
            handler: The handler instance
        """
        self.handlers[concept_type] = handler
        logger.info(f"Registered custom handler for concept type: {concept_type.value}")

    def get_supported_concept_types(self) -> set[ConceptType]:
        """Get all supported concept types."""
        return set(self.handlers.keys())
