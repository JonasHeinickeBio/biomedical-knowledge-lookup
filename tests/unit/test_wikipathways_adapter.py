"""
Unit tests for WikiPathwaysAdapter.
"""

from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters.wikipathways_adapter import WikiPathwaysAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource, LookupConfig

pytestmark = pytest.mark.unit


def _text_entry(**overrides):
    entry = {
        "id": "WP3159",
        "url": "https://www.wikipathways.org/instance/WP3159",
        "name": "Interleukin-11 signaling pathway",
        "species": "Homo sapiens",
        "revision": "2024-01-01",
        "description": "IL-11 signals through gp130.",
        "datanodes": "IL11, IL11RA, STAT3",
        "annotations": "interleukin signaling",
    }
    entry.update(overrides)
    return entry


def _info_entry(**overrides):
    entry = {
        "id": "WP3159",
        "url": "https://www.wikipathways.org/instance/WP3159",
        "name": "Interleukin-11 signaling pathway",
        "species": "Homo sapiens",
        "revision": "2024-01-01",
        "description": "IL-11 signals through gp130.",
        "citedIn": "",
    }
    entry.update(overrides)
    return entry


def _xref_entry(**overrides):
    entry = {
        "id": "WP3159",
        "url": "https://www.wikipathways.org/instance/WP3159",
        "name": "Interleukin-11 signaling pathway",
        "species": "Homo sapiens",
        "hgnc": "hgnc.symbol:IL11, hgnc.symbol:IL11RA, hgnc.symbol:STAT3",
    }
    entry.update(overrides)
    return entry


class TestWikiPathwaysAdapter:
    """Tests for WikiPathwaysAdapter."""

    @pytest.fixture
    def adapter(self, lookup_config):
        """Create WikiPathwaysAdapter instance.

        Clears the shared adapter cache before and after each test: the bulk
        JSON index is deliberately cached by ``KnowledgeSource`` (not by adapter
        instance) so a process reuses one download across lookups, but that
        means the cache is a process-global singleton that would otherwise leak
        a mocked response from one test into the next.
        """
        a = WikiPathwaysAdapter(lookup_config)
        a.clear_cache()
        yield a
        a.clear_cache()

    def test_adapter_initialization(self, lookup_config):
        """Test WikiPathwaysAdapter initialization."""
        adapter = WikiPathwaysAdapter(lookup_config)
        assert adapter.source == KnowledgeSource.WIKIPATHWAYS
        assert adapter.config == lookup_config

    def test_get_source(self, adapter):
        """Test get_source returns correct source."""
        assert adapter.get_source() == KnowledgeSource.WIKIPATHWAYS

    def test_is_available(self, adapter):
        """Test is_available returns True."""
        assert adapter.is_available() is True

    def test_get_rate_limit_default(self, adapter):
        """Test get_rate_limit returns default value."""
        rate_limit = adapter.get_rate_limit()
        assert isinstance(rate_limit, int | float)
        assert rate_limit > 0

    def test_get_rate_limit_custom(self):
        """Test get_rate_limit with custom config."""
        config = LookupConfig(rate_limits={KnowledgeSource.WIKIPATHWAYS: 2.0})
        adapter = WikiPathwaysAdapter(config)
        assert adapter.get_rate_limit() == 2.0

    @pytest.mark.asyncio
    async def test_search_concepts_matches_name(self, adapter):
        """A query matching the pathway name ranks above a description-only match."""
        name_hit = _text_entry(id="WP3159", name="Interleukin-11 signaling pathway")
        desc_hit = _text_entry(
            id="WP99",
            name="Unrelated pathway",
            description="mentions interleukin only here",
            datanodes="",
            annotations="",
        )
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [desc_hit, name_hit]}
            results = await adapter.search_concepts("interleukin", limit=10)

        url = mock_req.call_args.args[0]
        assert url.endswith("/findPathwaysByText.json")
        assert [r.primary_id for r in results] == ["WP3159", "WP99"]
        assert results[0].concept_type == ConceptType.PATHWAY
        assert results[0].confidence_score > results[1].confidence_score

    @pytest.mark.asyncio
    async def test_search_concepts_respects_limit(self, adapter):
        entries = [_text_entry(id=f"WP{i}", name=f"Interleukin pathway {i}") for i in range(5)]
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": entries}
            results = await adapter.search_concepts("interleukin", limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_concepts_empty_response(self, adapter):
        """Test search concepts with empty response."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": []}
            results = await adapter.search_concepts("nonexistent", limit=10)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_no_matches(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_text_entry()]}
            results = await adapter.search_concepts("completely-unrelated-term", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_concepts_network_error(self, adapter):
        """Test search concepts with network error."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Network error")
            results = await adapter.search_concepts("test")
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_concepts_caches_bulk_file(self, adapter):
        """The bulk file is downloaded once and reused across calls."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_text_entry()]}
            await adapter.search_concepts("interleukin")
            await adapter.search_concepts("interleukin")
        assert mock_req.await_count == 1

    @pytest.mark.asyncio
    async def test_get_concept_details_success(self, adapter):
        """Test get_concept_details with valid ID."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_info_entry()]}
            result = await adapter.get_concept_details("WIKIPATHWAYS:WP3159")

        assert result is not None
        assert result.primary_id == "WP3159"
        assert result.confidence_score == 1.0
        url = mock_req.call_args.args[0]
        assert url.endswith("/getPathwayInfo.json")

    @pytest.mark.asyncio
    async def test_get_concept_details_not_found(self, adapter):
        """Test get_concept_details when the ID is absent from the bulk index."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_info_entry()]}
            result = await adapter.get_concept_details("WP_UNKNOWN")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_details_failure_returns_none(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("boom")
            result = await adapter.get_concept_details("WP3159")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_relationships_returns_gene_edges(self, adapter):
        """get_relationships exposes participating HGNC genes as edge dicts
        (same shape as KEGG/STRING) sourced from the findPathwaysByXref index."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_xref_entry()]}
            rels = await adapter.get_relationships("WIKIPATHWAYS:WP3159", limit=2)

        url = mock_req.call_args.args[0]
        assert url.endswith("/findPathwaysByXref.json")
        assert [r["related_name"] for r in rels] == ["IL11", "IL11RA"]
        assert all(r["relation_label"] == "has_gene" for r in rels)
        assert all(r["source"] == "WIKIPATHWAYS_GENE" for r in rels)

    @pytest.mark.asyncio
    async def test_get_relationships_unknown_id_returns_empty(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_xref_entry()]}
            assert await adapter.get_relationships("WP_UNKNOWN") == []

    @pytest.mark.asyncio
    async def test_get_relationships_no_hgnc_field_returns_empty(self, adapter):
        """Non-human pathways carry an empty ``hgnc`` field."""
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"pathwayInfo": [_xref_entry(hgnc="")]}
            assert await adapter.get_relationships("WP3159") == []

    @pytest.mark.asyncio
    async def test_get_relationships_degrades_on_error(self, adapter):
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("network down")
            assert await adapter.get_relationships("WP3159") == []

    @pytest.mark.asyncio
    async def test_get_relationships_blank_id_returns_empty(self, adapter):
        assert await adapter.get_relationships("WIKIPATHWAYS:") == []

    @pytest.mark.asyncio
    async def test_get_mappings_default(self, adapter):
        """Test get_mappings returns empty list by default."""
        mappings = await adapter.get_mappings("WP3159")
        assert isinstance(mappings, list)
        assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager."""
        async with adapter:
            pass  # Should not raise any exceptions


class TestParseXrefField:
    """Tests for the module-level xref field parser."""

    def test_parses_comma_separated_values(self):
        from knowledge_lookup.adapters.wikipathways_adapter import _parse_xref_field

        assert _parse_xref_field("hgnc.symbol:A, hgnc.symbol:B", prefix="hgnc.symbol:") == [
            "A",
            "B",
        ]

    def test_parses_semicolon_chained_values(self):
        from knowledge_lookup.adapters.wikipathways_adapter import _parse_xref_field

        assert _parse_xref_field("hgnc.symbol:A;hgnc.symbol:B", prefix="hgnc.symbol:") == [
            "A",
            "B",
        ]

    def test_deduplicates_preserving_order(self):
        from knowledge_lookup.adapters.wikipathways_adapter import _parse_xref_field

        result = _parse_xref_field(
            "hgnc.symbol:A, hgnc.symbol:B, hgnc.symbol:A", prefix="hgnc.symbol:"
        )
        assert result == ["A", "B"]

    def test_blank_or_non_string_returns_empty(self):
        from knowledge_lookup.adapters.wikipathways_adapter import _parse_xref_field

        assert _parse_xref_field("", prefix="hgnc.symbol:") == []
        assert _parse_xref_field(None, prefix="hgnc.symbol:") == []
