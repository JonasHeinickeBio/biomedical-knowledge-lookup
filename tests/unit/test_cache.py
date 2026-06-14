"""
Unit tests for knowledge lookup cache system.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.cache import (
    CacheEntry,
    CacheStats,
    DiskCacheBackend,
    KnowledgeLookupCache,
    MemoryCacheBackend,
    get_cache,
    init_cache,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_is_expired_no_ttl(self):
        entry = CacheEntry(key="k", value="v", created_at=time.time() - 100, ttl=None)
        assert entry.is_expired() is False

    def test_is_expired_with_ttl_not_expired(self):
        entry = CacheEntry(key="k", value="v", created_at=time.time(), ttl=60)
        assert entry.is_expired() is False

    def test_is_expired_with_ttl_expired(self):
        entry = CacheEntry(key="k", value="v", created_at=time.time() - 100, ttl=10)
        assert entry.is_expired() is True

    def test_to_dict(self):
        entry = CacheEntry(key="k", value="v", created_at=1.0, ttl=60, access_count=3, last_accessed=2.0)
        d = entry.to_dict()
        assert d["key"] == "k"
        assert d["value"] == "v"
        assert d["ttl"] == 60
        assert d["access_count"] == 3

    def test_from_dict(self):
        data = {"key": "k", "value": "v", "created_at": 1.0, "ttl": 60, "access_count": 2, "last_accessed": 3.0}
        entry = CacheEntry.from_dict(data)
        assert entry.key == "k"
        assert entry.access_count == 2

    def test_from_dict_defaults(self):
        data = {"key": "k", "value": "v", "created_at": 1.0, "ttl": None}
        entry = CacheEntry.from_dict(data)
        assert entry.access_count == 0


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_hit_rate_empty(self):
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_with_data(self):
        stats = CacheStats(hits=8, misses=2)
        assert stats.hit_rate == 0.8

    def test_to_dict(self):
        stats = CacheStats(hits=5, misses=3, evictions=1, sets=8, total_entries=10)
        d = stats.to_dict()
        assert d["hits"] == 5
        assert d["misses"] == 3
        assert d["evictions"] == 1
        assert d["hit_rate"] == 5 / 8


class TestMemoryCacheBackend:
    """Tests for MemoryCacheBackend."""

    def test_basic_get_set(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("key1", "value1")
        assert backend.get("key1") == "value1"
        assert backend.get("missing") is None

    def test_get_expired_entry(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("key1", "value1", ttl=0.001)
        time.sleep(0.01)
        assert backend.get("key1") is None

    def test_set_updates_existing(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("key1", "value1")
        backend.set("key1", "value2")
        assert backend.get("key1") == "value2"

    def test_delete_existing(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("key1", "value1")
        assert backend.delete("key1") is True
        assert backend.get("key1") is None

    def test_delete_missing(self):
        backend = MemoryCacheBackend(max_size=10)
        assert backend.delete("nonexistent") is False

    def test_clear(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("k1", "v1")
        backend.set("k2", "v2")
        backend.clear()
        assert backend.size() == 0
        assert backend.get("k1") is None

    def test_cleanup_expired(self):
        backend = MemoryCacheBackend(max_size=10)
        backend.set("expires", "v", ttl=0.001)
        backend.set("stays", "v", ttl=60)
        time.sleep(0.01)
        removed = backend.cleanup()
        assert removed == 1
        assert backend.size() == 1

    def test_size(self):
        backend = MemoryCacheBackend(max_size=10)
        assert backend.size() == 0
        backend.set("k1", "v1")
        assert backend.size() == 1

    def test_evict_lru(self):
        backend = MemoryCacheBackend(max_size=2)
        backend.set("k1", "v1")
        backend.set("k2", "v2")
        backend.get("k1")
        backend.set("k3", "v3")
        assert backend.size() == 2
        assert backend.get("k2") is None

    def test_evict_lru_empty_cache(self):
        backend = MemoryCacheBackend(max_size=2)
        backend._evict_lru()
        assert backend.size() == 0


class TestDiskCacheBackend:
    """Tests for DiskCacheBackend."""

    def test_basic_get_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            backend.set("k1", "v1")
            assert backend.get("k1") == "v1"
            assert backend.get("missing") is None

    def test_get_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            backend.set("k1", "v1", ttl=0.001)
            time.sleep(0.01)
            assert backend.get("k1") is None

    def test_get_corrupted_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            key_hash_path = backend._get_cache_file("k1")
            key_hash_path.write_text("not valid json {{{")
            assert backend.get("k1") is None

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            backend.set("k1", "v1")
            assert backend.delete("k1") is True
            assert backend.get("k1") is None

    def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            assert backend.delete("nope") is False

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            backend.set("k1", "v1")
            backend.set("k2", "v2")
            backend.clear()
            assert backend.size() == 0

    def test_cleanup_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            backend.set("expires", "v", ttl=0.001)
            backend.set("stays", "v", ttl=60)
            time.sleep(0.01)
            removed = backend.cleanup()
            assert removed == 1
            assert backend.size() == 1

    def test_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=100)
            assert backend.size() == 0
            backend.set("k1", "v1")
            assert backend.size() == 1

    def test_evict_lru(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=2)
            backend.set("k1", "v1")
            time.sleep(0.01)
            backend.set("k2", "v2")
            backend.set("k3", "v3")
            assert backend.size() <= 2

    def test_evict_lru_empty_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp, max_size=2)
            backend._evict_lru()

    def test_load_index_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            index_file = cache_dir / "cache_index.json"
            index_file.write_text("corrupt {{{")
            backend = DiskCacheBackend(cache_dir=tmp)
            assert backend._index == {}

    def test_save_index_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp)
            backend._index_file = Path("/nonexistent/dir/index.json")
            backend._save_index()

    def test_save_entry_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = DiskCacheBackend(cache_dir=tmp)
            entry = CacheEntry(key="k", value="v", created_at=time.time())
            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                backend._save_entry(entry)


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

    def test_initialization_no_disk(self):
        cache = KnowledgeLookupCache()
        assert cache._disk_cache is None

    def test_get_and_set(self, cache_dir):
        """Test basic get and set."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_from_disk_promotes_to_memory(self, cache_dir):
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir, default_ttl=60)
        cache._disk_cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_set_with_default_ttl(self, cache_dir):
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir, default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_delete_with_disk(self, cache_dir):
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_no_disk(self):
        cache = KnowledgeLookupCache()
        cache.set("key1", "value1")
        assert cache.delete("key1") is True

    def test_clear_all(self, cache_dir):
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None

    def test_clear_namespace(self):
        cache = KnowledgeLookupCache()
        cache.set("k1", "v1")
        cache.clear(namespace="ns1")

    def test_cleanup(self, cache_dir):
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("k1", "v1")
        result = cache.cleanup()
        assert "memory_evicted" in result
        assert "disk_evicted" in result

    def test_cleanup_no_disk(self):
        cache = KnowledgeLookupCache()
        cache.set("k1", "v1")
        result = cache.cleanup()
        assert result["disk_evicted"] == 0

    def test_get_stats(self, cache_dir):
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("k1", "v1")
        cache.get("k1")
        cache.get("missing")
        stats = cache.get_stats()
        assert "memory" in stats
        assert "disk" in stats
        assert "combined" in stats
        assert stats["sizes"]["memory"] == 1

    def test_get_stats_no_disk(self):
        cache = KnowledgeLookupCache()
        stats = cache.get_stats()
        assert stats["sizes"]["disk"] == 0

    def test_make_key_with_namespace(self):
        cache = KnowledgeLookupCache()
        assert cache._make_key("k", "ns") == "ns:k"

    def test_make_key_no_namespace(self):
        cache = KnowledgeLookupCache()
        assert cache._make_key("k", "") == "k"


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_cache_singleton(self):
        cache = get_cache()
        assert isinstance(cache, KnowledgeLookupCache)

    def test_init_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = init_cache(disk_cache_dir=tmp, default_ttl=3600)
            assert isinstance(cache, KnowledgeLookupCache)
            assert get_cache() is cache
