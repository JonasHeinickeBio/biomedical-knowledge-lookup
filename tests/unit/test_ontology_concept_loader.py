"""
Unit tests for ontology concept loader.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from rdflib import Graph, Literal, URIRef

pytestmark = pytest.mark.unit
from knowledge_lookup.services.ontology_concept_loader import (
    OntologyConceptLoader,
    create_dynamic_concept_enum,
    get_dynamic_concept_handlers,
)


class TestOntologyConceptLoader:
    """Tests for OntologyConceptLoader."""

    @pytest.fixture
    def loader(self):
        return OntologyConceptLoader(ontology_dir="/tmp/fake_onto")

    def test_initialization(self):
        loader = OntologyConceptLoader(ontology_dir="/tmp/fake")
        assert os.path.normpath(str(loader.ontology_dir)) == os.path.normpath("/tmp/fake")

    @patch("rdflib.Graph.parse")
    def test_load_ontology_graph(self, mock_parse, loader):
        graph = loader.load_ontology_graph()
        assert isinstance(graph, Graph)

    def test_extract_concept_classes(self, loader):
        mock_graph = MagicMock(spec=Graph)
        mock_graph.query.return_value = []
        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            classes = loader.extract_concept_classes()
            assert isinstance(classes, dict)

    def test_get_concept_hierarchy(self, loader):
        mock_graph = MagicMock(spec=Graph)
        mock_graph.query.return_value = []
        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            hierarchy = loader.get_concept_hierarchy()
            assert isinstance(hierarchy, dict)

    def test_load_ontology_graph_cached(self, loader):
        cached_graph = Graph()
        loader._ontology_graph = cached_graph
        result = loader.load_ontology_graph()
        assert result is cached_graph

    def test_load_ontology_graph_no_ttl_files(self, tmp_path):
        loader = OntologyConceptLoader(ontology_dir=str(tmp_path))
        result = loader.load_ontology_graph()
        assert isinstance(result, Graph)
        assert len(result) == 0

    def test_load_ontology_graph_with_ttl_files(self, tmp_path):
        ttl_content = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://test.org/Disease> a owl:Class ;
    rdfs:label "Disease" .
"""
        ttl_file = tmp_path / "test_ontology.ttl"
        ttl_file.write_text(ttl_content)
        loader = OntologyConceptLoader(ontology_dir=str(tmp_path))
        graph = loader.load_ontology_graph()
        assert len(graph) > 0
        assert loader._ontology_graph is graph

    def test_load_ontology_graph_parse_error(self, tmp_path):
        bad_file = tmp_path / "bad.ttl"
        bad_file.write_text("NOT VALID TURTLE {{{{")
        loader = OntologyConceptLoader(ontology_dir=str(tmp_path))
        graph = loader.load_ontology_graph()
        assert isinstance(graph, Graph)

    def test_extract_concept_classes_with_triples(self, loader):
        mock_graph = MagicMock(spec=Graph)
        disease_uri = URIRef("http://test.org/Disease")
        mock_graph.subjects.return_value = [disease_uri]
        mock_graph.objects.return_value = [Literal("Disease")]
        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            classes = loader.extract_concept_classes()
            assert "Disease" in classes

    def test_extract_concept_classes_uri_with_hash(self, loader):
        mock_graph = MagicMock(spec=Graph)
        uri = URIRef("http://test.org/ontology#Gene")
        mock_graph.subjects.return_value = [uri]
        mock_graph.objects.return_value = []
        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            classes = loader.extract_concept_classes()
            assert "Gene" in classes

    def test_extract_concept_classes_uri_with_slash(self, loader):
        mock_graph = MagicMock(spec=Graph)
        uri = URIRef("http://test.org/ontology/Protein")
        mock_graph.subjects.return_value = [uri]
        mock_graph.objects.return_value = []
        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            classes = loader.extract_concept_classes()
            assert "Protein" in classes

    def test_get_concept_hierarchy_with_triples(self, loader):
        mock_graph = MagicMock(spec=Graph)
        child = URIRef("http://test.org/ChildClass")
        parent = URIRef("http://test.org/ParentClass")
        mock_graph.subject_objects.return_value = [(child, parent)]
        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            hierarchy = loader.get_concept_hierarchy()
            assert "ParentClass" in hierarchy
            assert "ChildClass" in hierarchy["ParentClass"]

    def test_extract_local_name_with_hash(self, loader):
        uri = URIRef("http://test.org/ont#Disease")
        name = loader._extract_local_name(uri)
        assert name == "Disease"

    def test_extract_local_name_with_slash(self, loader):
        uri = URIRef("http://test.org/ont/Disease")
        name = loader._extract_local_name(uri)
        assert name == "Disease"

    def test_create_dynamic_concept_types(self, loader):
        with patch.object(loader, "extract_concept_classes", return_value={"Disease": "Disease", "Gene": "Gene"}):
            mapping = loader.create_dynamic_concept_types()
            assert mapping["Disease"] == "DISEASE"
            assert mapping["Gene"] == "GENE"

    def test_create_dynamic_concept_types_with_hyphens(self, loader):
        with patch.object(loader, "extract_concept_classes", return_value={"My-Concept": "MC"}):
            mapping = loader.create_dynamic_concept_types()
            assert mapping["My-Concept"] == "MY_CONCEPT"


class TestCreateDynamicConceptEnum:
    def test_create_enum(self):
        with patch(
            "knowledge_lookup.services.ontology_concept_loader.OntologyConceptLoader"
        ) as MockLoader:
            instance = MockLoader.return_value
            instance.extract_concept_classes.return_value = {"Disease": "Disease", "Gene": "Gene"}
            DynamicEnum = create_dynamic_concept_enum()
            assert hasattr(DynamicEnum, "DISEASE")
            assert hasattr(DynamicEnum, "GENE")
            assert hasattr(DynamicEnum, "UNKNOWN")
            assert DynamicEnum.DISEASE.value == "disease"
            assert DynamicEnum.UNKNOWN.value == "unknown"


class TestGetDynamicConceptHandlersExtended:
    def test_specialized_and_default_handlers(self):
        with patch(
            "knowledge_lookup.services.ontology_concept_loader.OntologyConceptLoader"
        ) as MockLoader:
            instance = MockLoader.return_value
            instance.extract_concept_classes.return_value = {
                "Disease": "Disease",
                "Gene": "Gene",
                "Protein": "Protein",
                "Chemical": "Chemical",
                "Drug": "Drug",
                "SomeNewThing": "SomeNewThing",
            }
            handlers = get_dynamic_concept_handlers()
            from knowledge_lookup.services.rdf_converter import (
                ChemicalHandler,
                DefaultHandler,
                DiseaseHandler,
                DrugHandler,
                GeneHandler,
                ProteinHandler,
            )
            assert handlers["DISEASE"] is DiseaseHandler
            assert handlers["GENE"] is GeneHandler
            assert handlers["PROTEIN"] is ProteinHandler
            assert handlers["CHEMICAL"] is ChemicalHandler
            assert handlers["DRUG"] is DrugHandler
            assert handlers["UNKNOWN"] is DefaultHandler
