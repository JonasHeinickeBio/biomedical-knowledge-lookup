"""
Unit tests for TytoAdapter.

The tyto module is replaced by a mock limited to the per-ontology objects the
installed tyto package provides (``SO``, ``SBO``, ``NCIT``), each with
``get_term_by_uri`` and ``get_uri_by_term``. No network access.
"""

import logging
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit
import knowledge_lookup.adapters.tyto_adapter as mod
from knowledge_lookup.adapters.tyto_adapter import TytoAdapter
from knowledge_lookup.models import KnowledgeSource, LookupConfig


@pytest.fixture
def mock_tyto(monkeypatch):
    """A tyto stand-in with only the real per-ontology API (no module-level get_label)."""
    fake = MagicMock(spec=["SO", "SBO", "NCIT"])
    for name in ("SO", "SBO", "NCIT"):
        ontology = MagicMock(spec=["get_term_by_uri", "get_uri_by_term"])
        ontology.get_term_by_uri.side_effect = LookupError("No matching term found")
        ontology.get_uri_by_term.side_effect = LookupError("not a valid ontology term")
        setattr(fake, name, ontology)
    monkeypatch.setattr(mod, "tyto", fake)
    return fake


class TestTytoAdapter:
    """Tests for TytoAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create TytoAdapter instance."""
        return TytoAdapter(lookup_config)

    def test_adapter_initialization(self, lookup_config):
        """Test TytoAdapter initialization."""
        adapter = TytoAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.TYTO
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.TYTO

    def test_is_available_with_tyto(self, adapter, mock_tyto):
        """Test is_available when tyto is available."""
        assert adapter.is_available() is True

    def test_is_available_without_tyto(self, monkeypatch):
        """Test is_available when tyto is not available."""
        monkeypatch.setattr(mod, "tyto", None)
        assert TytoAdapter(LookupConfig()).is_available() is False

    def test_installed_tyto_provides_used_api(self):
        """Regression: the adapter only uses API the installed tyto package has."""
        tyto = pytest.importorskip("tyto")
        assert not hasattr(tyto, "get_label")
        for name in mod._ONTOLOGY_URI_PREFIXES:
            ontology_class = type(getattr(tyto, name))
            assert callable(ontology_class.get_term_by_uri)
            assert callable(ontology_class.get_uri_by_term)

    # --- get_concept_details ---

    @pytest.mark.asyncio
    async def test_get_concept_details_no_tyto(self, monkeypatch):
        """Test get_concept_details when tyto is None."""
        monkeypatch.setattr(mod, "tyto", None)
        result = await TytoAdapter(LookupConfig()).get_concept_details(
            "http://purl.obolibrary.org/obo/SO_0000167"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_non_uri(self, adapter, mock_tyto):
        """Test get_concept_details with non-URI concept_id (returns None)."""
        assert await adapter.get_concept_details("SO:0000167") is None
        mock_tyto.SO.get_term_by_uri.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_concept_details_so_term(self, adapter, mock_tyto):
        """Regression: SO URIs are resolved with tyto.SO.get_term_by_uri."""
        mock_tyto.SO.get_term_by_uri.side_effect = None
        mock_tyto.SO.get_term_by_uri.return_value = "promoter"

        uri = "http://purl.obolibrary.org/obo/SO_0000167"
        result = await adapter.get_concept_details(uri)

        mock_tyto.SO.get_term_by_uri.assert_called_once_with(uri)
        assert result is not None
        assert result.primary_id == uri
        assert result.primary_label == "promoter"
        assert result.categories == ["SO"]
        assert result.confidence_score == 1.0
        assert [(i.source, i.identifier, i.url) for i in result.identifiers] == [
            (KnowledgeSource.TYTO, uri, uri)
        ]
        assert result.source_data[KnowledgeSource.TYTO]["ontology"] == "SO"

    @pytest.mark.asyncio
    async def test_get_concept_details_http_identifiers_org_sbo(self, adapter, mock_tyto):
        """http://identifiers.org URIs are passed to tyto in the https form it recognises."""
        mock_tyto.SBO.get_term_by_uri.side_effect = None
        mock_tyto.SBO.get_term_by_uri.return_value = "functional entity"

        result = await adapter.get_concept_details("http://identifiers.org/SBO:0000241")

        mock_tyto.SBO.get_term_by_uri.assert_called_once_with(
            "https://identifiers.org/SBO:0000241"
        )
        assert result.primary_id == "http://identifiers.org/SBO:0000241"
        assert result.primary_label == "functional entity"

    @pytest.mark.asyncio
    async def test_get_concept_details_ncit_term(self, adapter, mock_tyto):
        mock_tyto.NCIT.get_term_by_uri.side_effect = None
        mock_tyto.NCIT.get_term_by_uri.return_value = "Diabetes Mellitus"
        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/NCIT_C2985")
        assert result.primary_label == "Diabetes Mellitus"
        assert result.categories == ["NCIT"]

    @pytest.mark.asyncio
    async def test_get_concept_details_unsupported_ontology(self, adapter, mock_tyto):
        """URIs outside SO/SBO/NCIT return None without a lookup."""
        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/DOID_162")
        assert result is None
        for name in ("SO", "SBO", "NCIT"):
            getattr(mock_tyto, name).get_term_by_uri.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_concept_details_rejects_malformed_uri(self, adapter, mock_tyto):
        """URIs with characters that would break tyto's SPARQL are not passed on."""
        result = await adapter.get_concept_details(
            "http://purl.obolibrary.org/obo/SO_0000167> ?p ?o } #"
        )
        assert result is None
        mock_tyto.SO.get_term_by_uri.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_concept_details_term_not_found(self, adapter, mock_tyto):
        """tyto raises LookupError for unknown URIs; the adapter returns None."""
        result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/SO_9999999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_empty_label(self, adapter, mock_tyto):
        mock_tyto.SO.get_term_by_uri.side_effect = None
        mock_tyto.SO.get_term_by_uri.return_value = ""
        assert (
            await adapter.get_concept_details("http://purl.obolibrary.org/obo/SO_0000167") is None
        )

    @pytest.mark.asyncio
    async def test_get_concept_details_with_tyto_exception(self, adapter, mock_tyto, caplog):
        """Other tyto errors are logged and return None."""
        mock_tyto.SO.get_term_by_uri.side_effect = Exception("Ontology error")
        with caplog.at_level(logging.ERROR):
            result = await adapter.get_concept_details("http://purl.obolibrary.org/obo/SO_0000167")
        assert result is None
        assert "Tyto lookup failed" in caplog.text

    # --- search_concepts ---

    @pytest.mark.asyncio
    async def test_search_concepts_no_tyto(self, monkeypatch):
        monkeypatch.setattr(mod, "tyto", None)
        assert await TytoAdapter(LookupConfig()).search_concepts("promoter") == []

    @pytest.mark.asyncio
    async def test_search_concepts_exact_label(self, adapter, mock_tyto):
        """Regression: search is implemented with get_uri_by_term across SO, SBO and NCIT."""
        mock_tyto.SO.get_uri_by_term.side_effect = None
        mock_tyto.SO.get_uri_by_term.return_value = "https://identifiers.org/SO:0000167"
        mock_tyto.SO.get_term_by_uri.side_effect = None
        mock_tyto.SO.get_term_by_uri.return_value = "promoter"
        # SBO has two terms labelled "promoter"; tyto raises a plain Exception
        mock_tyto.SBO.get_uri_by_term.side_effect = Exception(
            "Ambiguous term promoter--found multiple URIs ['http://biomodels.net/SBO/SBO_0000598']"
        )
        mock_tyto.NCIT.get_uri_by_term.side_effect = None
        mock_tyto.NCIT.get_uri_by_term.return_value = "https://identifiers.org/ncit:C13297"
        mock_tyto.NCIT.get_term_by_uri.side_effect = Exception("label lookup failed")

        results = await adapter.search_concepts("Promoter", limit=10)

        assert [(c.primary_id, c.primary_label, c.categories) for c in results] == [
            ("https://identifiers.org/SO:0000167", "promoter", ["SO"]),
            ("https://identifiers.org/ncit:C13297", "Promoter", ["NCIT"]),
        ]
        mock_tyto.SO.get_uri_by_term.assert_called_once_with("Promoter")

    @pytest.mark.asyncio
    async def test_search_concepts_not_found(self, adapter, mock_tyto):
        """A label found in no ontology returns []."""
        assert await adapter.search_concepts("nonexistent term") == []

    @pytest.mark.asyncio
    async def test_search_concepts_limit(self, adapter, mock_tyto):
        for name in ("SO", "NCIT"):
            ontology = getattr(mock_tyto, name)
            ontology.get_uri_by_term.side_effect = None
            ontology.get_uri_by_term.return_value = f"https://identifiers.org/{name}:1"
            ontology.get_term_by_uri.side_effect = None
            ontology.get_term_by_uri.return_value = "promoter"
        assert len(await adapter.search_concepts("promoter", limit=1)) == 1
        assert await adapter.search_concepts("promoter", limit=0) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", ["promoter' . }", "prom.*", "5' UTR", "", "   "])
    async def test_search_concepts_rejects_unsafe_terms(self, adapter, mock_tyto, query):
        """tyto puts the term into a SPARQL regex unescaped, so unsafe terms are skipped."""
        assert await adapter.search_concepts(query) == []
        for name in ("SO", "SBO", "NCIT"):
            getattr(mock_tyto, name).get_uri_by_term.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_concepts_all_ontologies_fail(self, adapter, mock_tyto, caplog):
        """When every ontology errors, the failure is logged and reaches the circuit breaker."""
        for name in ("SO", "SBO", "NCIT"):
            getattr(mock_tyto, name).get_uri_by_term.side_effect = Exception("endpoint down")
        breaker = MagicMock()
        breaker.allow_request.return_value = True
        adapter.set_circuit_breaker(breaker)
        with caplog.at_level(logging.WARNING):
            results = await adapter.search_concepts("promoter")
        assert results == []
        breaker.record_failure.assert_called()
        assert "Tyto search failed" in caplog.text

    # --- defaults ---

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.TYTO: 5.0})
        adapter = TytoAdapter(config)
        assert adapter.get_rate_limit() == 5.0

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("TEST:001")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_get_relationships_default(self, adapter):
        """Test get_relationships returns empty list by default."""
        relationships = await adapter.get_relationships("TEST:001")
        assert isinstance(relationships, list)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass
