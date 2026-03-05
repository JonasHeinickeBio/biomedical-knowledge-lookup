"""
Unit tests for RDF converter.
"""

from rdflib import Graph, URIRef, RDF, RDFS, Literal
import pytest
from knowledge_lookup.rdf_converter import RDFNamespaces, UnifiedRDFConverter, ChemicalHandler, UnifiedConcept, ConceptType, KnowledgeSource


class TestRDFConverter:
    """Tests for RDF conversion logic."""

    @pytest.fixture
    def namespaces(self):
        """Create RDFNamespaces instance."""
        return RDFNamespaces()

    @pytest.fixture
    def converter(self):
        """Create UnifiedRDFConverter instance."""
        return UnifiedRDFConverter()

    @pytest.fixture
    def sample_concept(self):
        """Create sample concept for RDF testing."""
        concept = UnifiedConcept(
            primary_id="CHEMBL123",
            primary_label="Aspirin",
            concept_type=ConceptType.CHEMICAL
        )
        concept.add_identifier(KnowledgeSource.CHEMBL, "CHEMBL123", "Aspirin")
        concept.definitions = ["A common pain reliever"]
        return concept

    def test_namespaces_initialization(self):
        """Test RDF namespaces and bindings."""
        bindings = RDFNamespaces.get_namespace_bindings()
        assert "aidpais" in bindings
        assert "chembl" in bindings
        assert bindings["rdf"] == RDF
        assert bindings["rdfs"] == RDFS

    def test_chemical_handler_uri(self, sample_concept, namespaces):
        """Test URI generation for chemical concepts."""
        handler = ChemicalHandler(namespaces)
        uri = handler.get_primary_uri(sample_concept)
        # It seems the handler uses AIDPAIS namespace by default or has a specific logic
        assert "CHEMBL123" in str(uri)

    def test_convert_concept(self, sample_concept, converter):
        """Test conversion of a single concept to RDF graph."""
        graph = converter.convert_concepts_to_graph([sample_concept])
        assert isinstance(graph, Graph)
        
        # Verify basic triples
        found_label = False
        for _, p, o in graph.triples((None, RDFS.label, None)):
            if str(o) == "Aspirin":
                found_label = True
        assert found_label

    def test_export_to_file(self, sample_concept, converter, tmp_path):
        """Test exporting RDF to file."""
        output_file = tmp_path / "test_export.ttl"
        converter.convert_and_save([sample_concept], str(output_file), format="turtle")
        assert output_file.exists()
        assert output_file.stat().st_size > 0
