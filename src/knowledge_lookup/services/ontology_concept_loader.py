"""
Dynamic Ontology Concept Type Loader

Automatically extracts owl:Class concepts from AID-PAIS ontology modules
and dynamically generates concept type handlers for the RDF converter.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any

from rdflib import OWL, RDF, RDFS, Graph, URIRef

logger = logging.getLogger(__name__)


class OntologyConceptLoader:
    """Loads concept types dynamically from ontology files."""

    def __init__(self, ontology_dir: str | None = None):
        """
        Initialize the ontology loader.

        Args:
            ontology_dir: Directory containing ontology TTL files. If None,
                         uses default AID-PAIS ontology modules directory.
        """
        if ontology_dir is None:
            # Default to the ontology modules directory
            # Use absolute path from this file location
            current_file = Path(__file__).absolute()
            project_root = current_file.parent.parent.parent  # AID-PAIS-KnowledgeGraph/
            ontology_dir = str(
                project_root
                / "hybrid_kg_prototype"
                / "ontology_mapping"
                / "aid-pais-ontology-modules"
                / "modules"
            )

        self.ontology_dir = Path(ontology_dir)
        self._ontology_graph: Any = None

    def load_ontology_graph(self) -> Graph:
        """Load and merge all ontology TTL files into a single graph."""
        if self._ontology_graph is not None:
            return self._ontology_graph

        graph = Graph()

        # Find all TTL files in the ontology directory
        ttl_files = list(self.ontology_dir.glob("*.ttl"))

        if not ttl_files:
            logger.warning(f"No TTL files found in {self.ontology_dir}")
            return graph

        logger.info(f"Loading {len(ttl_files)} ontology files from {self.ontology_dir}")

        for ttl_file in ttl_files:
            try:
                logger.debug(f"Loading ontology file: {ttl_file}")
                graph.parse(str(ttl_file), format="turtle")
            except Exception as e:
                logger.error(f"Error loading ontology file {ttl_file}: {e}")
                continue

        self._ontology_graph = graph
        logger.info(f"Loaded ontology graph with {len(graph)} triples")
        return graph

    def extract_concept_classes(self) -> dict[str, str]:
        """
        Extract all owl:Class concepts from the ontology.

        Returns:
            Dictionary mapping concept names to their labels/descriptions
        """
        graph = self.load_ontology_graph()
        concepts = {}

        # Query for all owl:Class instances
        for class_uri in graph.subjects(RDF.type, OWL.Class):
            # Get the local name (after the # or /)
            if isinstance(class_uri, URIRef):
                # Extract local name from URI
                uri_str = str(class_uri)
                if "#" in uri_str:
                    local_name = uri_str.split("#")[-1]
                else:
                    local_name = uri_str.split("/")[-1]

                # Get label if available
                label = None
                for label_obj in graph.objects(class_uri, RDFS.label):
                    label = str(label_obj)
                    break

                # Use local name as key, label as value
                concepts[local_name] = label or local_name

        logger.info(f"Extracted {len(concepts)} concept classes from ontology")
        return concepts

    def get_concept_hierarchy(self) -> dict[str, list[str]]:
        """
        Extract concept hierarchy (subclass relationships).

        Returns:
            Dictionary mapping parent concepts to their children
        """
        graph = self.load_ontology_graph()
        hierarchy: dict[str, list[str]] = {}

        # Query for rdfs:subClassOf relationships
        for subj, obj in graph.subject_objects(RDFS.subClassOf):
            if isinstance(subj, URIRef) and isinstance(obj, URIRef):
                # Extract local names
                subj_name = self._extract_local_name(subj)
                obj_name = self._extract_local_name(obj)

                if obj_name not in hierarchy:
                    hierarchy[obj_name] = []
                hierarchy[obj_name].append(subj_name)

        return hierarchy

    def _extract_local_name(self, uri: URIRef) -> str:
        """Extract local name from URI."""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        else:
            return uri_str.split("/")[-1]

    def create_dynamic_concept_types(self) -> dict[str, str]:
        """
        Create a mapping of concept names to their normalized enum-style names.

        Returns:
            Dictionary mapping original concept names to normalized names
        """
        concepts = self.extract_concept_classes()

        # Normalize concept names to enum-style (UPPER_CASE)
        normalized_mapping = {}
        for concept_name, _label in concepts.items():
            # Convert to UPPER_CASE with underscores
            normalized = concept_name.upper().replace("-", "_").replace(" ", "_")
            normalized_mapping[concept_name] = normalized

        return normalized_mapping


def create_dynamic_concept_enum():
    """
    Dynamically create a ConceptType enum from ontology classes.

    Returns:
        A dynamically created Enum class
    """
    loader = OntologyConceptLoader()
    concepts = loader.extract_concept_classes()

    # Create enum members
    enum_members = {}
    for concept_name, _label in concepts.items():
        # Normalize to UPPER_CASE
        enum_name = concept_name.upper().replace("-", "_").replace(" ", "_")
        # Use the original name as the value for backward compatibility
        enum_members[enum_name] = concept_name.lower().replace(" ", "_").replace("-", "_")

    # Add UNKNOWN for backward compatibility
    enum_members["UNKNOWN"] = "unknown"

    # Create the enum class
    DynamicConceptType = Enum("ConceptType", enum_members)  # type: ignore

    return DynamicConceptType


# Utility functions for integration with RDF converter
def get_dynamic_concept_handlers():
    """
    Get a mapping of concept types to handler classes for dynamic loading.

    Returns:
        Dictionary mapping concept names to handler classes (not instances)
    """
    # Import here to avoid circular imports
    from .rdf_converter import (
        ChemicalHandler,
        DefaultHandler,
        DiseaseHandler,
        DrugHandler,
        GeneHandler,
        ProteinHandler,
    )

    loader = OntologyConceptLoader()
    concepts = loader.extract_concept_classes()

    handlers = {}

    # Map specific high-priority concepts to specialized handlers
    specialized_mappings = {
        "Disease": DiseaseHandler,
        "Gene": GeneHandler,
        "Protein": ProteinHandler,
        "Chemical": ChemicalHandler,
        "Drug": DrugHandler,
    }

    # Create handlers for all concepts
    for concept_name in concepts.keys():
        if concept_name in specialized_mappings:
            handler_class = specialized_mappings[concept_name]
        else:
            handler_class = DefaultHandler

        # Use normalized name that matches ConceptType enum values
        # Convert CamelCase to UPPER_CASE_WITH_UNDERSCORES
        import re

        key = re.sub(r"(?<!^)(?=[A-Z])", "_", concept_name).upper()
        handlers[key] = handler_class

    # Add unknown handler
    handlers["UNKNOWN"] = DefaultHandler

    return handlers


if __name__ == "__main__":
    # Test the dynamic loading
    loader = OntologyConceptLoader()

    print("=== Ontology Concept Loader Test ===")

    concepts = loader.extract_concept_classes()
    print(f"Found {len(concepts)} concept classes:")
    for name, label in sorted(concepts.items())[:10]:  # Show first 10
        print(f"  - {name}: {label}")
    if len(concepts) > 10:
        print(f"  ... and {len(concepts) - 10} more")

    hierarchy = loader.get_concept_hierarchy()
    print(f"\nHierarchy with {len(hierarchy)} parent concepts")

    # Test dynamic enum creation
    try:
        DynamicConceptType = create_dynamic_concept_enum()
        print(f"\nDynamic ConceptType enum created with {len(DynamicConceptType)} members")
        print("Sample members:")
        for _i, member in enumerate(list(DynamicConceptType)[:5]):
            print(f"  - {member.name}: {member.value}")
        if len(DynamicConceptType) > 5:
            print(f"  ... and {len(DynamicConceptType) - 5} more")
    except Exception as e:
        print(f"Error creating dynamic enum: {e}")
