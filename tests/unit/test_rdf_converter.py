"""
Unit tests for RDF converter.
"""

import pytest
from rdflib import RDF, RDFS, Graph, Literal, URIRef
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit
from knowledge_lookup.rdf_converter import (
    AdapterHints,
    ChemicalHandler,
    ConceptType,
    ConceptTypeHandler,
    DefaultHandler,
    DiseaseHandler,
    DrugHandler,
    GeneHandler,
    KnowledgeSource,
    ProteinHandler,
    RDFNamespaces,
    UnifiedConcept,
    UnifiedRDFConverter,
)


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
            primary_id="CHEMBL123", primary_label="Aspirin", concept_type=ConceptType.CHEMICAL
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
        assert "CHEMBL123" in str(uri)

    def test_convert_concept(self, sample_concept, converter):
        """Test conversion of a single concept to RDF graph."""
        graph = converter.convert_concepts_to_graph([sample_concept])
        assert isinstance(graph, Graph)

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


class TestRDFConverterExtended:
    """Extended tests to improve coverage of add_common_properties and handlers."""

    @pytest.fixture
    def namespaces(self):
        return RDFNamespaces()

    @pytest.fixture
    def converter(self):
        return UnifiedRDFConverter()

    def _make_concept(self, concept_type=ConceptType.CHEMICAL, primary_id="C1", **kwargs):
        concept = UnifiedConcept(
            primary_id=primary_id, primary_label="Label", concept_type=concept_type, **kwargs
        )
        return concept

    def test_common_properties_confidence_score_positive(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept(confidence_score=0.95)
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.confidenceScore, None)))
        assert len(triples) == 1

    def test_common_properties_categories(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.categories = ["cat1", "cat2"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.hasCategory, None)))
        assert len(triples) == 2

    def test_common_properties_synonyms(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.synonyms = ["synA", "synB"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.hasSynonym, None)))
        assert len(triples) == 2

    def test_common_properties_definitions(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.definitions = ["def1"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.hasDefinition, None)))
        assert len(triples) == 1

    def test_common_properties_semantic_types(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.semantic_types = ["typeA"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.hasSemanticType, None)))
        assert len(triples) == 1

    def test_common_properties_labels_multilang(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.labels = {"en": "English", "de": "Deutsch"}
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, RDFS.label, None)))
        assert len(triples) >= 3

    def test_common_properties_parents(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.parents = ["http://parent/1"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.hasParent, None)))
        assert len(triples) == 1

    def test_common_properties_children(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.children = ["http://child/1"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.hasChild, None)))
        assert len(triples) == 1

    def test_common_properties_related(self, namespaces):
        handler = DefaultHandler(namespaces)
        concept = self._make_concept()
        concept.related = ["http://related/1"]
        graph = Graph()
        concept_uri = URIRef("http://test/concept/1")
        handler.add_common_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, namespaces.VOCAB.relatedTo, None)))
        assert len(triples) == 1


class TestChemicalHandlerExtended:
    @pytest.fixture
    def ns(self):
        return RDFNamespaces()

    def test_get_concept_class_uri(self, ns):
        handler = ChemicalHandler(ns)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.CHEMICAL)
        uri = handler.get_concept_class_uri(concept)
        assert "Compound" in str(uri)

    def test_primary_uri_with_unichem(self, ns):
        handler = ChemicalHandler(ns)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.CHEMICAL)
        concept.add_identifier(KnowledgeSource.UNICHEM, "UC123")
        uri = handler.get_primary_uri(concept)
        assert "UC123" in str(uri)

    def test_primary_uri_without_unichem(self, ns):
        handler = ChemicalHandler(ns)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.CHEMICAL)
        uri = handler.get_primary_uri(concept)
        assert "compound/C1" in str(uri)

    def test_add_type_specific_pubchem(self, ns):
        handler = ChemicalHandler(ns)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.CHEMICAL)
        concept.add_identifier(KnowledgeSource.PUBCHEM, "PUB123", "PubChemLabel")
        graph = Graph()
        concept_uri = URIRef("http://test/c1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasPubChemId, None)))
        assert len(triples) == 1

    def test_add_type_specific_drugbank(self, ns):
        handler = ChemicalHandler(ns)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.CHEMICAL)
        concept.add_identifier(KnowledgeSource.DRUGBANK, "DB123", "DrugBankLabel")
        graph = Graph()
        concept_uri = URIRef("http://test/c1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasDrugBankId, None)))
        assert len(triples) == 1

    def test_add_type_specific_generic_identifier(self, ns):
        handler = ChemicalHandler(ns)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.CHEMICAL)
        concept.add_identifier(KnowledgeSource.OLS, "OLS:123")
        graph = Graph()
        concept_uri = URIRef("http://test/c1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasIdentifier, None)))
        assert len(triples) == 1


class TestDiseaseHandlerExtended:
    @pytest.fixture
    def ns(self):
        return RDFNamespaces()

    def test_get_concept_class_uri(self, ns):
        handler = DiseaseHandler(ns)
        concept = UnifiedConcept(primary_id="D1", primary_label="X", concept_type=ConceptType.DISEASE)
        uri = handler.get_concept_class_uri(concept)
        assert "Disease" in str(uri)

    def test_primary_uri_with_mondo(self, ns):
        handler = DiseaseHandler(ns)
        concept = UnifiedConcept(primary_id="D1", primary_label="X", concept_type=ConceptType.DISEASE)
        concept.add_identifier(KnowledgeSource.MONDO, "MONDO:123")
        uri = handler.get_primary_uri(concept)
        assert "mondo" in str(uri)

    def test_primary_uri_without_mondo(self, ns):
        handler = DiseaseHandler(ns)
        concept = UnifiedConcept(primary_id="D1", primary_label="X", concept_type=ConceptType.DISEASE)
        uri = handler.get_primary_uri(concept)
        assert "disease/D1" in str(uri)

    def test_add_type_specific_mondo(self, ns):
        handler = DiseaseHandler(ns)
        concept = UnifiedConcept(primary_id="D1", primary_label="X", concept_type=ConceptType.DISEASE)
        concept.add_identifier(KnowledgeSource.MONDO, "MONDO:123")
        graph = Graph()
        concept_uri = URIRef("http://test/d1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasMondoId, None)))
        assert len(triples) == 1

    def test_add_type_specific_oxo(self, ns):
        handler = DiseaseHandler(ns)
        concept = UnifiedConcept(primary_id="D1", primary_label="X", concept_type=ConceptType.DISEASE)
        concept.add_identifier(KnowledgeSource.OXO, "OXO:456")
        graph = Graph()
        concept_uri = URIRef("http://test/d1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasOxoId, None)))
        assert len(triples) == 1

    def test_add_type_specific_generic(self, ns):
        handler = DiseaseHandler(ns)
        concept = UnifiedConcept(primary_id="D1", primary_label="X", concept_type=ConceptType.DISEASE)
        concept.add_identifier(KnowledgeSource.OLS, "OLS:999")
        graph = Graph()
        concept_uri = URIRef("http://test/d1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasIdentifier, None)))
        assert len(triples) == 1


class TestGeneHandlerExtended:
    @pytest.fixture
    def ns(self):
        return RDFNamespaces()

    def test_get_concept_class_uri(self, ns):
        handler = GeneHandler(ns)
        concept = UnifiedConcept(primary_id="G1", primary_label="X", concept_type=ConceptType.GENE)
        uri = handler.get_concept_class_uri(concept)
        assert "Gene" in str(uri)

    def test_primary_uri_with_ensembl(self, ns):
        handler = GeneHandler(ns)
        concept = UnifiedConcept(primary_id="G1", primary_label="X", concept_type=ConceptType.GENE)
        concept.add_identifier(KnowledgeSource.ENSEMBL, "ENSG00001")
        uri = handler.get_primary_uri(concept)
        assert "ENSG00001" in str(uri)

    def test_primary_uri_without_ensembl(self, ns):
        handler = GeneHandler(ns)
        concept = UnifiedConcept(primary_id="G1", primary_label="X", concept_type=ConceptType.GENE)
        uri = handler.get_primary_uri(concept)
        assert "gene/G1" in str(uri)

    def test_add_type_specific_ensembl(self, ns):
        handler = GeneHandler(ns)
        concept = UnifiedConcept(primary_id="G1", primary_label="X", concept_type=ConceptType.GENE)
        concept.add_identifier(KnowledgeSource.ENSEMBL, "ENSG00001")
        graph = Graph()
        concept_uri = URIRef("http://test/g1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasEnsemblId, None)))
        assert len(triples) == 1

    def test_add_type_specific_uniprot(self, ns):
        handler = GeneHandler(ns)
        concept = UnifiedConcept(primary_id="G1", primary_label="X", concept_type=ConceptType.GENE)
        concept.add_identifier(KnowledgeSource.UNIPROT, "P12345")
        graph = Graph()
        concept_uri = URIRef("http://test/g1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasUniProtId, None)))
        assert len(triples) == 1

    def test_add_type_specific_generic(self, ns):
        handler = GeneHandler(ns)
        concept = UnifiedConcept(primary_id="G1", primary_label="X", concept_type=ConceptType.GENE)
        concept.add_identifier(KnowledgeSource.NCBI, "NCBI:999")
        graph = Graph()
        concept_uri = URIRef("http://test/g1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasIdentifier, None)))
        assert len(triples) == 1


class TestProteinHandlerExtended:
    @pytest.fixture
    def ns(self):
        return RDFNamespaces()

    def test_get_concept_class_uri(self, ns):
        handler = ProteinHandler(ns)
        concept = UnifiedConcept(primary_id="P1", primary_label="X", concept_type=ConceptType.PROTEIN)
        uri = handler.get_concept_class_uri(concept)
        assert "Protein" in str(uri)

    def test_primary_uri_with_uniprot(self, ns):
        handler = ProteinHandler(ns)
        concept = UnifiedConcept(primary_id="P1", primary_label="X", concept_type=ConceptType.PROTEIN)
        concept.add_identifier(KnowledgeSource.UNIPROT, "P12345")
        uri = handler.get_primary_uri(concept)
        assert "P12345" in str(uri)

    def test_primary_uri_without_uniprot(self, ns):
        handler = ProteinHandler(ns)
        concept = UnifiedConcept(primary_id="P1", primary_label="X", concept_type=ConceptType.PROTEIN)
        uri = handler.get_primary_uri(concept)
        assert "protein/P1" in str(uri)

    def test_add_type_specific_uniprot(self, ns):
        handler = ProteinHandler(ns)
        concept = UnifiedConcept(primary_id="P1", primary_label="X", concept_type=ConceptType.PROTEIN)
        concept.add_identifier(KnowledgeSource.UNIPROT, "P12345")
        graph = Graph()
        concept_uri = URIRef("http://test/p1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasUniProtId, None)))
        assert len(triples) == 1

    def test_add_type_specific_ensembl(self, ns):
        handler = ProteinHandler(ns)
        concept = UnifiedConcept(primary_id="P1", primary_label="X", concept_type=ConceptType.PROTEIN)
        concept.add_identifier(KnowledgeSource.ENSEMBL, "ENSP00001")
        graph = Graph()
        concept_uri = URIRef("http://test/p1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasEnsemblId, None)))
        assert len(triples) == 1

    def test_add_type_specific_generic(self, ns):
        handler = ProteinHandler(ns)
        concept = UnifiedConcept(primary_id="P1", primary_label="X", concept_type=ConceptType.PROTEIN)
        concept.add_identifier(KnowledgeSource.OLS, "OLS:777")
        graph = Graph()
        concept_uri = URIRef("http://test/p1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasIdentifier, None)))
        assert len(triples) == 1


class TestDrugHandlerExtended:
    @pytest.fixture
    def ns(self):
        return RDFNamespaces()

    def test_get_concept_class_uri(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        uri = handler.get_concept_class_uri(concept)
        assert "Drug" in str(uri)

    def test_primary_uri_with_drugbank(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        concept.add_identifier(KnowledgeSource.DRUGBANK, "DB123")
        uri = handler.get_primary_uri(concept)
        assert "DB123" in str(uri)

    def test_primary_uri_with_chembl_no_drugbank(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        concept.add_identifier(KnowledgeSource.CHEMBL, "CHEMBL456")
        uri = handler.get_primary_uri(concept)
        assert "CHEMBL456" in str(uri)

    def test_primary_uri_fallback(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        uri = handler.get_primary_uri(concept)
        assert "drug/DR1" in str(uri)

    def test_add_type_specific_drugbank(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        concept.add_identifier(KnowledgeSource.DRUGBANK, "DB123")
        graph = Graph()
        concept_uri = URIRef("http://test/dr1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasDrugBankId, None)))
        assert len(triples) == 1

    def test_add_type_specific_chembl(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        concept.add_identifier(KnowledgeSource.CHEMBL, "CHEMBL456")
        graph = Graph()
        concept_uri = URIRef("http://test/dr1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasChEMBLId, None)))
        assert len(triples) == 1

    def test_add_type_specific_pubchem(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        concept.add_identifier(KnowledgeSource.PUBCHEM, "PUB789")
        graph = Graph()
        concept_uri = URIRef("http://test/dr1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasPubChemId, None)))
        assert len(triples) == 1

    def test_add_type_specific_generic(self, ns):
        handler = DrugHandler(ns)
        concept = UnifiedConcept(primary_id="DR1", primary_label="X", concept_type=ConceptType.DRUG)
        concept.add_identifier(KnowledgeSource.OLS, "OLS:333")
        graph = Graph()
        concept_uri = URIRef("http://test/dr1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasIdentifier, None)))
        assert len(triples) == 1


class TestDefaultHandlerExtended:
    @pytest.fixture
    def ns(self):
        return RDFNamespaces()

    def test_get_concept_class_uri(self, ns):
        handler = DefaultHandler(ns)
        concept = UnifiedConcept(primary_id="X1", primary_label="X", concept_type=ConceptType.SYMPTOM)
        uri = handler.get_concept_class_uri(concept)
        assert "Concept" in str(uri)

    def test_get_primary_uri(self, ns):
        handler = DefaultHandler(ns)
        concept = UnifiedConcept(primary_id="X1", primary_label="X", concept_type=ConceptType.SYMPTOM)
        uri = handler.get_primary_uri(concept)
        assert "concept/X1" in str(uri)

    def test_add_type_specific_properties(self, ns):
        handler = DefaultHandler(ns)
        concept = UnifiedConcept(primary_id="X1", primary_label="X", concept_type=ConceptType.SYMPTOM)
        concept.add_identifier(KnowledgeSource.OLS, "OLS:111")
        concept.add_identifier(KnowledgeSource.GO, "GO:222")
        graph = Graph()
        concept_uri = URIRef("http://test/x1")
        handler.add_type_specific_properties(graph, concept, concept_uri)
        triples = list(graph.triples((concept_uri, ns.VOCAB.hasIdentifier, None)))
        assert len(triples) == 2


class TestAdapterHintsExtended:
    def test_add_all_methods(self):
        hints = AdapterHints()
        ns = RDFNamespaces()
        hints.add_namespace("custom", ns.AIDPAIS)
        hints.add_predicate("test_pred", URIRef("http://pred"))
        hints.add_type_mapping(ConceptType.DISEASE, URIRef("http://disease"))
        hints.add_identifier_mapping(KnowledgeSource.CHEMBL, {"prefix": "chembl"})
        assert "custom" in hints.custom_namespaces
        assert "test_pred" in hints.custom_predicates
        assert ConceptType.DISEASE in hints.type_mappings
        assert KnowledgeSource.CHEMBL in hints.identifier_mappings


class TestUnifiedRDFConverterExtended:
    @pytest.fixture
    def converter(self):
        return UnifiedRDFConverter()

    def test_convert_with_adapter_hints_namespaces(self):
        hints = AdapterHints()
        ns = RDFNamespaces()
        hints.add_namespace("myns", ns.AIDPAIS)
        conv = UnifiedRDFConverter(adapter_hints=hints)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.SYMPTOM)
        graph = conv.convert_concepts_to_graph([concept])
        assert isinstance(graph, Graph)

    def test_convert_single_concept_error_handling(self):
        conv = UnifiedRDFConverter()
        concept = UnifiedConcept(primary_id="ERR", primary_label="X", concept_type=ConceptType.DISEASE)
        with patch.object(conv.handlers[ConceptType.DISEASE], "add_common_properties", side_effect=RuntimeError("fail")):
            graph = Graph()
            conv._convert_single_concept(graph, concept)

    def test_add_concept_mappings_with_confidence(self):
        conv = UnifiedRDFConverter()
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.DISEASE)
        from knowledge_lookup.models import ConceptIdentifier, ConceptMapping
        concept.mappings = [
            ConceptMapping(
                from_concept=ConceptIdentifier(KnowledgeSource.UMLS, "C1"),
                to_concept=ConceptIdentifier(KnowledgeSource.CHEMBL, "CHEMBL1"),
                mapping_type="exact",
                confidence=0.95,
                source="test_src",
            )
        ]
        graph = Graph()
        concept_uri = URIRef("http://test/c1")
        conv._add_concept_mappings(graph, concept, concept_uri)
        mapping_triples = list(graph.triples((None, conv.namespaces.RDF.type, conv.namespaces.VOCAB.Mapping)))
        assert len(mapping_triples) == 1

    def test_add_concept_mappings_no_confidence_no_source(self):
        conv = UnifiedRDFConverter()
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.DISEASE)
        from knowledge_lookup.models import ConceptIdentifier, ConceptMapping
        concept.mappings = [
            ConceptMapping(
                from_concept=ConceptIdentifier(KnowledgeSource.UMLS, "C1"),
                to_concept=ConceptIdentifier(KnowledgeSource.CHEMBL, "CHEMBL1"),
                mapping_type="exact",
                confidence=None,
                source=None,
            )
        ]
        graph = Graph()
        concept_uri = URIRef("http://test/c1")
        conv._add_concept_mappings(graph, concept, concept_uri)
        mapping_triples = list(graph.triples((None, conv.namespaces.RDF.type, conv.namespaces.VOCAB.Mapping)))
        assert len(mapping_triples) == 1

    def test_get_concept_uri_from_identifier_all_sources(self):
        conv = UnifiedRDFConverter()
        from knowledge_lookup.models import ConceptIdentifier
        id_chembl = ConceptIdentifier(KnowledgeSource.CHEMBL, "C1")
        id_pubchem = ConceptIdentifier(KnowledgeSource.PUBCHEM, "P1")
        id_drugbank = ConceptIdentifier(KnowledgeSource.DRUGBANK, "D1")
        id_uniprot = ConceptIdentifier(KnowledgeSource.UNIPROT, "U1")
        id_ensembl = ConceptIdentifier(KnowledgeSource.ENSEMBL, "E1")
        id_other = ConceptIdentifier(KnowledgeSource.OLS, "O1")
        assert "C1" in str(conv._get_concept_uri_from_identifier(id_chembl))
        assert "P1" in str(conv._get_concept_uri_from_identifier(id_pubchem))
        assert "D1" in str(conv._get_concept_uri_from_identifier(id_drugbank))
        assert "U1" in str(conv._get_concept_uri_from_identifier(id_uniprot))
        assert "E1" in str(conv._get_concept_uri_from_identifier(id_ensembl))
        assert "ols/O1" in str(conv._get_concept_uri_from_identifier(id_other))

    def test_add_concept_type_handler(self):
        conv = UnifiedRDFConverter()
        ns = RDFNamespaces()
        handler = DefaultHandler(ns)
        conv.add_concept_type_handler(ConceptType.PERSON, handler)
        assert ConceptType.PERSON in conv.handlers

    def test_get_supported_concept_types(self):
        conv = UnifiedRDFConverter()
        types = conv.get_supported_concept_types()
        assert ConceptType.DISEASE in types
        assert ConceptType.GENE in types

    def test_convert_and_save_formats(self, tmp_path):
        conv = UnifiedRDFConverter()
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.DISEASE)
        for fmt in ["turtle", "xml", "json-ld", "nt", "n3"]:
            out = tmp_path / f"out_{fmt.replace('-', '_')}.ttl"
            conv.convert_and_save([concept], str(out), format=fmt)
            assert out.exists()

    def test_convert_and_save_unknown_format(self, tmp_path):
        conv = UnifiedRDFConverter()
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.DISEASE)
        out = tmp_path / "out_unknown.ttl"
        conv.convert_and_save([concept], str(out), format="bogus")
        assert out.exists()

    def test_from_ontology_no_dir(self):
        conv = UnifiedRDFConverter.from_ontology(ontology_dir=None, adapter_hints=None)
        assert isinstance(conv, UnifiedRDFConverter)

    def test_from_ontology_with_dir(self, tmp_path):
        conv = UnifiedRDFConverter.from_ontology(ontology_dir=str(tmp_path), adapter_hints=None)
        assert isinstance(conv, UnifiedRDFConverter)

    def test_load_dynamic_handlers_exception_fallback(self):
        conv = UnifiedRDFConverter()
        with patch("knowledge_lookup.ontology_concept_loader.get_dynamic_concept_handlers", side_effect=RuntimeError("boom")):
            result = conv._load_dynamic_handlers()
            assert ConceptType.UNKNOWN in result

    def test_dynamic_handler_matching(self):
        conv = UnifiedRDFConverter()
        with patch("knowledge_lookup.ontology_concept_loader.get_dynamic_concept_handlers", return_value={"DISEASE": DefaultHandler, "NONENUMKEY": DefaultHandler}):
            result = conv._load_dynamic_handlers()
            assert ConceptType.DISEASE in result

    def test_convert_concepts_with_adapter_type_mapping(self):
        hints = AdapterHints()
        hints.add_type_mapping(ConceptType.DISEASE, URIRef("http://custom/Disease"))
        conv = UnifiedRDFConverter(adapter_hints=hints)
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.DISEASE)
        graph = conv.convert_concepts_to_graph([concept])
        assert isinstance(graph, Graph)

    def test_merge_with_existing_graph(self, tmp_path):
        conv = UnifiedRDFConverter()
        concept = UnifiedConcept(primary_id="C1", primary_label="X", concept_type=ConceptType.DISEASE)
        new_graph = conv.convert_concepts_to_graph([concept])

        existing = Graph()
        existing.add((URIRef("http://existing"), RDFS.label, Literal("Old")))
        existing_path = tmp_path / "existing.ttl"
        existing.serialize(str(existing_path), format="turtle")

        output_path = tmp_path / "merged.ttl"
        merged = conv.merge_with_existing_graph(new_graph, str(existing_path), str(output_path))
        assert isinstance(merged, Graph)
        assert len(merged) > 0
        assert output_path.exists()
