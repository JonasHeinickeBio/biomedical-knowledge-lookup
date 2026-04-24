"""
Unit tests for ontology concept loader.
"""

from unittest.mock import MagicMock, patch

import pytest
from rdflib import Graph

pytestmark = pytest.mark.unit
from knowledge_lookup.ontology_concept_loader import (
    OntologyConceptLoader,
    get_dynamic_concept_handlers,
)


class TestOntologyConceptLoader:
    """Tests for OntologyConceptLoader."""

    @pytest.fixture
    def loader(self):
        """Create OntologyConceptLoader instance."""
        return OntologyConceptLoader()

    def test_initialization(self):
        """Test OntologyConceptLoader initialization."""
        loader = OntologyConceptLoader(ontology_dir="/tmp/fake")
        assert str(loader.ontology_dir) == "/tmp/fake"

    def test_get_dynamic_concept_handlers(self):
        """Test get_dynamic_concept_handlers returns a dict."""
        with patch(
            "knowledge_lookup.ontology_concept_loader.get_dynamic_concept_handlers"
        ) as mock_get:
            mock_get.return_value = {}
            handlers = get_dynamic_concept_handlers()
            assert isinstance(handlers, dict)

    @patch("rdflib.Graph.parse")
    def test_load_ontology_graph(self, mock_parse, loader):
        """Test loading ontology graph."""
        graph = loader.load_ontology_graph()
        assert isinstance(graph, Graph)

    def test_extract_concept_classes(self, loader):
        """Test extracting concept classes."""
        mock_graph = MagicMock(spec=Graph)
        # Mock some triples for concept classes
        mock_graph.query.return_value = []

        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            classes = loader.extract_concept_classes()
            assert isinstance(classes, dict)

    def test_get_concept_hierarchy(self, loader):
        """Test getting concept hierarchy."""
        mock_graph = MagicMock(spec=Graph)
        mock_graph.query.return_value = []

        with patch.object(loader, "load_ontology_graph", return_value=mock_graph):
            hierarchy = loader.get_concept_hierarchy()
            assert isinstance(hierarchy, dict)
