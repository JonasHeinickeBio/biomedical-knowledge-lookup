"""Unit tests for cache_demo.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from knowledge_lookup.cache.cache_demo import (
    adapter_integration_example,
    demonstrate_caching,
)

pytestmark = pytest.mark.unit


class TestCacheDemo:
    """Tests for cache_demo functions."""

    @pytest.mark.asyncio
    async def test_adapter_integration_example(self):
        """Test adapter_integration_example runs without error."""
        with patch("builtins.print") as mock_print:
            await adapter_integration_example()
            assert mock_print.call_count > 0

    @pytest.mark.asyncio
    async def test_demonstrate_caching_initializes_cache(self):
        """Test demonstrate_caching initializes cache."""
        mock_adapter = MagicMock()
        mock_adapter.is_available.return_value = True
        mock_adapter.get_cache_stats.return_value = {
            "sizes": {"memory": 1, "disk": 0},
            "memory": {"hit_rate": 0.0},
            "disk": {"hit_rate": 0.0},
        }
        mock_adapter.get_sources = AsyncMock(return_value=["CHEMBL"])
        mock_adapter.search_concepts = AsyncMock(return_value=["result1"])
        mock_adapter.get_cross_references = AsyncMock(return_value={"source1": "xref1"})
        mock_adapter._cache.cleanup.return_value = {"total_evicted": 0}

        with patch("knowledge_lookup.cache.cache_demo.init_cache") as mock_init, patch(
            "knowledge_lookup.cache.cache_demo.UniChemAdapter", return_value=mock_adapter
        ), patch("builtins.print"):
            await demonstrate_caching()

            mock_init.assert_called_once()
            mock_adapter.get_sources.assert_called()
            mock_adapter.search_concepts.assert_called()
            mock_adapter._cache.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_demonstrate_caching_handles_empty_results(self):
        """Test demonstrate_caching handles empty results."""
        mock_adapter = MagicMock()
        mock_adapter.is_available.return_value = True
        mock_adapter.get_cache_stats.return_value = {
            "sizes": {"memory": 0, "disk": 0},
            "memory": {"hit_rate": 0.0},
            "disk": {"hit_rate": 0.0},
        }
        mock_adapter.get_sources = AsyncMock(return_value=[])
        mock_adapter.search_concepts = AsyncMock(return_value=[])
        mock_adapter.get_cross_references = AsyncMock(return_value={})
        mock_adapter._cache.cleanup.return_value = {"total_evicted": 0}

        with patch("knowledge_lookup.cache.cache_demo.init_cache"), patch(
            "knowledge_lookup.cache.cache_demo.UniChemAdapter", return_value=mock_adapter
        ), patch("builtins.print"):
            await demonstrate_caching()

    @pytest.mark.asyncio
    async def test_demonstrate_caching_no_adapter(self):
        """Test demonstrate_caching handles adapter not available."""
        mock_adapter = MagicMock()
        mock_adapter.is_available.return_value = False
        mock_adapter.get_cache_stats.return_value = {
            "sizes": {"memory": 0, "disk": 0},
            "memory": {"hit_rate": 0.0},
            "disk": {"hit_rate": 0.0},
        }
        mock_adapter.get_sources = AsyncMock(return_value=[])
        mock_adapter.search_concepts = AsyncMock(return_value=[])
        mock_adapter.get_cross_references = AsyncMock(return_value={})
        mock_adapter._cache.cleanup.return_value = {"total_evicted": 0}

        with patch("knowledge_lookup.cache.cache_demo.init_cache") as mock_init, patch(
            "knowledge_lookup.cache.cache_demo.UniChemAdapter", return_value=mock_adapter
        ), patch("builtins.print"):
            await demonstrate_caching()

            mock_init.assert_called_once()
