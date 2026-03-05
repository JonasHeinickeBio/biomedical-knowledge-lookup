"""
Unit tests for knowledge lookup cache system.
"""

import tempfile
from pathlib import Path

import pytest
from knowledge_lookup.cache import (
    CacheBackendType,
    DiskCacheBackend,
    KnowledgeLookupCache,
    MemoryCacheBackend,
    create_cache_backend,
    get_cache,
    init_cache,
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

    def test_memory_backend_invalidate_pattern(self):
        backend = MemoryCacheBackend(max_size=100)
        backend.set("diabetes:result:1", "v1")
        backend.set("diabetes:result:2", "v2")
        backend.set("cancer:result:1", "v3")
        deleted = backend.invalidate_pattern("diabetes")
        assert deleted == 2
        assert backend.get("diabetes:result:1") is None
        assert backend.get("diabetes:result:2") is None
        assert backend.get("cancer:result:1") == "v3"

    def test_disk_backend_invalidate_pattern(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            backend = DiskCacheBackend(cache_dir=cache_dir, max_size=100)
            backend.set("diabetes:result:1", "v1")
            backend.set("diabetes:result:2", "v2")
            backend.set("cancer:result:1", "v3")
            deleted = backend.invalidate_pattern("diabetes")
            assert deleted == 2
            assert backend.get("cancer:result:1") == "v3"

    def test_memory_backend_get_many(self):
        backend = MemoryCacheBackend(max_size=100)
        backend.set("a", 1)
        backend.set("b", 2)
        result = backend.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2}

    def test_memory_backend_set_many(self):
        backend = MemoryCacheBackend(max_size=100)
        backend.set_many({"x": 10, "y": 20})
        assert backend.get("x") == 10
        assert backend.get("y") == 20


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

    def test_get_many_and_set_many(self, cache_dir):
        """Test batch get_many and set_many."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set_many({"a": 1, "b": 2, "c": 3})
        result = cache.get_many(["a", "b", "c", "d"])
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["c"] == 3
        assert "d" not in result

    def test_invalidate_pattern(self, cache_dir):
        """Test pattern-based cache invalidation."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set_many(
            {
                "ns:diabetes:1": "v1",
                "ns:diabetes:2": "v2",
                "ns:cancer:1": "v3",
            }
        )
        deleted = cache.invalidate_pattern("diabetes")
        assert deleted >= 2
        assert cache.get("ns:diabetes:1") is None
        assert cache.get("ns:diabetes:2") is None
        assert cache.get("ns:cancer:1") == "v3"

    def test_namespace_isolation(self):
        """Test that namespaces isolate keys."""
        cache = KnowledgeLookupCache()
        cache.set("key", "ns1_value", namespace="ns1")
        cache.set("key", "ns2_value", namespace="ns2")
        assert cache.get("key", namespace="ns1") == "ns1_value"
        assert cache.get("key", namespace="ns2") == "ns2_value"

    def test_delete(self, cache_dir):
        """Test deletion."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        assert cache.delete("key1") is False

    def test_get_stats_includes_redis_and_backends_info(self, cache_dir):
        """Test that get_stats returns backend status."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        cache.set("k", "v")
        stats = cache.get_stats()
        assert "backends" in stats
        assert stats["backends"]["memory"] is True
        assert stats["backends"]["redis"] is False
        assert stats["backends"]["disk"] is True

    def test_get_stats_combined_hit_rate(self):
        """Test combined hit rate calculation in get_stats."""
        cache = KnowledgeLookupCache()
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.get_stats()
        assert stats["combined"]["hit_rate"] == pytest.approx(0.5)

    def test_cleanup_returns_redis_key(self, cache_dir):
        """Test that cleanup() result dict includes redis_evicted key."""
        cache = KnowledgeLookupCache(disk_cache_dir=cache_dir)
        result = cache.cleanup()
        assert "redis_evicted" in result

    @pytest.mark.asyncio
    async def test_async_get_set(self):
        """Test async_get and async_set."""
        cache = KnowledgeLookupCache()
        await cache.async_set("async_key", "async_value")
        val = await cache.async_get("async_key")
        assert val == "async_value"

    @pytest.mark.asyncio
    async def test_async_delete(self):
        """Test async_delete."""
        cache = KnowledgeLookupCache()
        await cache.async_set("del_key", "v")
        result = await cache.async_delete("del_key")
        assert result is True
        assert await cache.async_get("del_key") is None

    @pytest.mark.asyncio
    async def test_async_get_many_set_many(self):
        """Test async batch operations."""
        cache = KnowledgeLookupCache()
        await cache.async_set_many({"p": 1, "q": 2})
        result = await cache.async_get_many(["p", "q", "r"])
        assert result["p"] == 1
        assert result["q"] == 2
        assert "r" not in result

    def test_init_cache_function(self, cache_dir):
        """Test init_cache top-level function."""
        cache = init_cache(disk_cache_dir=cache_dir)
        assert isinstance(cache, KnowledgeLookupCache)
        assert get_cache() == cache


class TestCreateCacheBackend:
    """Tests for create_cache_backend factory."""

    def test_create_memory_backend(self):
        backend = create_cache_backend(CacheBackendType.MEMORY, max_size=50)
        assert isinstance(backend, MemoryCacheBackend)

    def test_create_disk_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = create_cache_backend(CacheBackendType.DISK, cache_dir=tmp)
            assert isinstance(backend, DiskCacheBackend)

    def test_create_redis_backend_raises_without_redis(self):
        """Without redis installed, should raise ImportError."""
        try:
            import redis  # noqa: F401

            pytest.skip("redis package is installed; cannot test ImportError path")
        except ImportError:
            pass
        with pytest.raises(ImportError, match="redis"):
            create_cache_backend(CacheBackendType.REDIS, host="localhost")

    def test_unknown_backend_type_raises(self):
        with pytest.raises((ValueError, AttributeError)):
            create_cache_backend("unknown_type")  # type: ignore[arg-type]
