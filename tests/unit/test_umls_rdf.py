"""
Unit tests for UMLS → RDF / SPARQL module.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from knowledge_lookup.models import ConceptType, KnowledgeSource, UnifiedConcept
from knowledge_lookup.umls.rdf import (
    SparqlEndpoint,
    concept_to_graph,
    concept_to_turtle,
    concepts_to_graph,
    concepts_to_jsonld,
    concepts_to_turtle,
    save_concepts_to_file,
)


@pytest.fixture
def sample_concept():
    c = UnifiedConcept(
        primary_id="C0011849",
        primary_label="Diabetes Mellitus",
        concept_type=ConceptType.DISEASE,
        synonyms=["Diabetes", "DM"],
        definitions=["A metabolic disease characterized by high blood sugar."],
        semantic_types=["Disease or Syndrome"],
        categories=["SNOMEDCT_US", "ICD10CM"],
        parents=["C0011860"],
        children=["C0011860"],
        related=["C0027051"],
        confidence_score=0.95,
    )
    c.sources = {KnowledgeSource.UMLS}
    return c


@pytest.fixture
def multiple_concepts(sample_concept):
    c2 = UnifiedConcept(
        primary_id="C0027051",
        primary_label="Myocardial Infarction",
        concept_type=ConceptType.DISEASE,
        synonyms=["Heart attack", "MI"],
    )
    c2.sources = {KnowledgeSource.UMLS}
    return [sample_concept, c2]


class TestConceptToRDF:
    def test_concept_to_graph_returns_graph(self, sample_concept):
        g = concept_to_graph(sample_concept)
        assert g is not None
        triples = list(g)
        assert len(triples) > 0

    def test_concept_to_graph_type_triple(self, sample_concept):
        g = concept_to_graph(sample_concept)
        # Check rdf:type assertion
        from rdflib import RDF

        for _s, p, o in g:
            if p == RDF.type:
                assert "Disease" in str(o) or "Concept" in str(o)
                return
        pytest.fail("No rdf:type triple found")

    def test_concept_to_graph_label(self, sample_concept):
        g = concept_to_graph(sample_concept)
        from rdflib import RDFS

        labels = [str(o) for s, p, o in g if p == RDFS.label]
        assert "Diabetes Mellitus" in labels

    def test_concept_to_turtle_returns_ttl_string(self, sample_concept):
        ttl = concept_to_turtle(sample_concept)
        assert isinstance(ttl, str)
        assert len(ttl) > 0
        assert "@prefix" in ttl or "C0011849" in ttl

    def test_concepts_to_graph_combines(self, multiple_concepts):
        g = concepts_to_graph(multiple_concepts)
        from rdflib import RDFS

        labels = {str(o) for s, p, o in g if p == RDFS.label}
        assert "Diabetes Mellitus" in labels
        assert "Myocardial Infarction" in labels

    def test_concepts_to_turtle(self, multiple_concepts):
        ttl = concepts_to_turtle(multiple_concepts)
        assert "Diabetes" in ttl
        assert "Myocardial" in ttl

    def test_concepts_to_jsonld(self, multiple_concepts):
        jld = concepts_to_jsonld(multiple_concepts)
        # JSON-LD can be a dict (single node) or list (multiple nodes)
        assert isinstance(jld, dict | list)
        if isinstance(jld, dict):
            assert "@graph" in jld or "@id" in jld
        else:
            assert len(jld) > 0

    def test_save_concepts_to_file(self, multiple_concepts, tmp_path):
        out = tmp_path / "test_concepts.ttl"
        result = save_concepts_to_file(multiple_concepts, out)
        assert result == out
        assert out.exists()
        content = out.read_text()
        assert "Diabetes" in content

    def test_save_concepts_to_file_jsonld(self, multiple_concepts, tmp_path):
        out = tmp_path / "test_concepts.json"
        result = save_concepts_to_file(multiple_concepts, out, fmt="json-ld")
        assert result.exists()

    def test_concept_without_type_defaults_to_concept(self):
        c = UnifiedConcept(
            primary_id="C9999999",
            primary_label="Unknown",
            concept_type=ConceptType.UNKNOWN,
        )
        ttl = concept_to_turtle(c)
        assert "C9999999" in ttl

    def test_concept_with_synonyms(self):
        c = UnifiedConcept(
            primary_id="C001",
            primary_label="Test",
            concept_type=ConceptType.CHEMICAL,
            synonyms=["syn1", "syn2"],
        )
        ttl = concept_to_turtle(c)
        assert "syn1" in ttl
        assert "syn2" in ttl

    def test_concept_with_definitions(self):
        c = UnifiedConcept(
            primary_id="C001",
            primary_label="Test",
            concept_type=ConceptType.DRUG,
            definitions=["A drug definition."],
        )
        ttl = concept_to_turtle(c)
        assert "A drug definition" in ttl


class TestSparqlEndpoint:
    def _mock_resp(self, data=None, side_effect=None):
        """Create a mock aiohttp response."""
        from unittest.mock import AsyncMock, MagicMock

        mock_resp = MagicMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.json = (
            AsyncMock(return_value=data or {}) if data is not None else AsyncMock(return_value={})
        )
        mock_resp.raise_for_status = MagicMock(side_effect=side_effect)
        return mock_resp

    @pytest.mark.asyncio
    async def test_query_returns_list(self):
        mock_data = {
            "results": {
                "bindings": [
                    {"item": {"type": "uri", "value": "http://example.org/Q1"}},
                    {"item": {"type": "uri", "value": "http://example.org/Q2"}},
                ]
            }
        }
        mock_resp = self._mock_resp(data=mock_data)

        with patch("aiohttp.ClientSession.get", return_value=mock_resp):
            client = SparqlEndpoint("https://query.wikidata.org/sparql")
            results = await client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 5")
            assert len(results) == 2
            assert results[0]["item"] == "http://example.org/Q1"
            await client.close()

    @pytest.mark.asyncio
    async def test_query_empty_results(self):
        mock_resp = self._mock_resp(data={"results": {"bindings": []}})

        with patch("aiohttp.ClientSession.get", return_value=mock_resp):
            client = SparqlEndpoint("https://query.wikidata.org/sparql")
            results = await client.query("SELECT * WHERE { ?s ?p ?o } LIMIT 0")
            assert results == []
            await client.close()

    @pytest.mark.asyncio
    async def test_query_error_returns_empty(self):
        mock_resp = self._mock_resp(side_effect=Exception("HTTP error"))

        with patch("aiohttp.ClientSession.get", return_value=mock_resp):
            client = SparqlEndpoint("https://query.wikidata.org/sparql")
            results = await client.query("SELECT * WHERE { BAD }")
            assert results == []
            await client.close()

    def test_parse_sparql_json(self):
        data = {
            "results": {
                "bindings": [
                    {
                        "s": {"type": "uri", "value": "http://example.org/s1"},
                        "p": {"type": "uri", "value": "http://example.org/p1"},
                    },
                ]
            }
        }
        parsed = SparqlEndpoint._parse_sparql_json(data)
        assert len(parsed) == 1
        assert parsed[0]["s"] == "http://example.org/s1"
        assert parsed[0]["p"] == "http://example.org/p1"

    def test_sparql_endpoints_dict(self):
        from knowledge_lookup.umls.rdf import SPARQL_ENDPOINTS

        assert "wikidata" in SPARQL_ENDPOINTS
        assert "bioportal" in SPARQL_ENDPOINTS
        assert SPARQL_ENDPOINTS["wikidata"] == "https://query.wikidata.org/sparql"
