"""
Unit tests for knowledge lookup cache system.
"""

import tempfile
from pathlib import Path
import pytest
from knowledge_lookup.cache import (
    KnowledgeLookupCache, 
    MemoryCacheBackend, 
    DiskCacheBackend,
    get_cache, 
    init_cache
)


class TestCacheBackends:
    """Tests for individual cache backends."""

    def test_memory_backend(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("key1", "value1")
        assert backend.get("key1") == "value1"
        assert backend.get("key2") is None

    def test_disk_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            backend = DiskCacheBackend(cache_dir=cache_dir, max_size=10)
            backend.set("key1", "value1")
            assert backend.get("key1") == "value1"
            assert backend.get("key2") is None


class TestKnowledgeLookupCache:
    """Tests for KnowledgeLookupCache."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_initialization(self, cache_dir):
        """Test KnowledgeLookupCache initialization."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        assert cache is not None

    def test_get_and_set(self, cache_dir):
        """Test basic get and set."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_init_cache_function(self, cache_dir):
        """Test init_cache top-level function."""
        cache = init_cache(disk_cache_dir=cache_dir)
        assert isinstance(cache, KnowledgeLookupCache)
        assert get_cache() == cache
