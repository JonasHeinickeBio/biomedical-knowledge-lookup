"""
Unit tests for caching system.
"""

import time
from pathlib import Path

import pytest

from knowledge_lookup.cache import (
    CacheEntry,
    CacheStats,
    KnowledgeLookupCache,
    get_cache,
    init_cache,
)


class TestCacheEntry:
    """Tests for CacheEntry model."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test"},
            created_at=time.time(),
            ttl=3600,
        )
        assert entry.key == "test_key"
        assert entry.value == {"data": "test"}
        assert entry.ttl == 3600

    def test_cache_entry_not_expired(self):
        """Test cache entry that hasn't expired."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            ttl=3600,
        )
        assert not entry.is_expired()

    def test_cache_entry_expired(self):
        """Test cache entry that has expired."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time() - 7200,  # 2 hours ago
            ttl=3600,  # 1 hour TTL
        )
        assert entry.is_expired()

    def test_cache_entry_no_expiration(self):
        """Test cache entry with no TTL (never expires)."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time() - 86400,  # 1 day ago
            ttl=None,
        )
        assert not entry.is_expired()

    def test_cache_entry_to_dict(self):
        """Test converting cache entry to dictionary."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            ttl=3600,
        )
        data = entry.to_dict()
        assert data["key"] == "test_key"
        assert data["value"] == "test_value"
        assert "created_at" in data
        assert data["ttl"] == 3600

    def test_cache_entry_from_dict(self):
        """Test creating cache entry from dictionary."""
        data = {
            "key": "test_key",
            "value": "test_value",
            "created_at": time.time(),
            "ttl": 3600,
            "access_count": 5,
            "last_accessed": time.time(),
        }
        entry = CacheEntry.from_dict(data)
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.access_count == 5


class TestCacheStats:
    """Tests for CacheStats model."""

    def test_cache_stats_initialization(self):
        """Test cache stats initialization."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.sets == 0

    def test_cache_stats_hit_rate_zero(self):
        """Test hit rate calculation with no data."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_cache_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = CacheStats(hits=10, misses=5, sets=15)
        data = stats.to_dict()
        assert data["hits"] == 10
        assert data["misses"] == 5
        assert data["sets"] == 15
        assert "hit_rate" in data


class TestKnowledgeLookupCache:
    """Tests for KnowledgeLookupCache."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create a cache instance for testing."""
        cache_dir = tmp_path / "test_cache"
        return KnowledgeLookupCache(
            memory_max_size=100,
            disk_cache_dir=str(cache_dir),
            default_ttl=3600,
        )

    def test_cache_initialization(self, tmp_path):
        """Test cache initialization."""
        cache_dir = tmp_path / "test_cache"
        cache = KnowledgeLookupCache(disk_cache_dir=str(cache_dir))
        assert cache is not None
        assert cache_dir.exists()

    def test_cache_set_and_get(self, cache):
        """Test setting and getting cache values."""
        cache.set("test_key", "test_value")
        value = cache.get("test_key")
        assert value == "test_value"

    def test_cache_get_nonexistent_key(self, cache):
        """Test getting a nonexistent key returns None."""
        value = cache.get("nonexistent_key")
        assert value is None

    def test_cache_set_with_ttl(self, cache):
        """Test setting a value with TTL."""
        cache.set("test_key", "test_value", ttl=1)
        value = cache.get("test_key")
        assert value == "test_value"
        # Wait for expiration
        time.sleep(1.1)
        value = cache.get("test_key")
        assert value is None

    def test_cache_delete(self, cache):
        """Test deleting a cache entry."""
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        cache.delete("test_key")
        assert cache.get("test_key") is None

    def test_cache_clear(self, cache):
        """Test clearing the cache."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_stats_tracking(self, cache):
        """Test that cache tracks statistics."""
        # Set some values
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Get some values (hits)
        cache.get("key1")
        cache.get("key2")

        # Get nonexistent key (miss)
        cache.get("key3")

        stats = cache.get_stats()
        assert "combined" in stats
        assert stats["combined"]["hits"] >= 2
        assert stats["combined"]["misses"] >= 1
        assert stats["combined"]["sets"] >= 2

    def test_cache_contains(self, cache):
        """Test checking if key exists in cache."""
        cache.set("test_key", "test_value")
        # Check if value exists by getting it
        assert cache.get("test_key") is not None
        assert cache.get("nonexistent_key") is None

    def test_cache_size(self, cache):
        """Test getting cache size."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        stats = cache.get_stats()
        assert stats["sizes"]["memory"] >= 3 or stats["sizes"]["disk"] >= 3


class TestCacheSingleton:
    """Tests for cache singleton functions."""

    def test_init_cache(self, tmp_path):
        """Test initializing the global cache."""
        cache_dir = tmp_path / "global_cache"
        cache = init_cache(disk_cache_dir=str(cache_dir))
        assert cache is not None

    def test_get_cache(self):
        """Test getting the global cache instance."""
        cache = get_cache()
        assert cache is not None

    def test_get_cache_without_init(self):
        """Test getting cache returns a default instance."""
        # This should not raise an error
        cache = get_cache()
        assert cache is not None


class TestCacheIntegration:
    """Integration tests for cache functionality."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create a cache instance for integration testing."""
        cache_dir = tmp_path / "integration_cache"
        return KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

    def test_cache_with_complex_objects(self, cache):
        """Test caching complex objects."""
        complex_obj = {
            "id": "DOID:9351",
            "label": "diabetes mellitus",
            "synonyms": ["diabetes", "DM"],
            "metadata": {"source": "OLS", "version": "1.0"},
        }
        cache.set("complex_key", complex_obj)
        retrieved = cache.get("complex_key")
        assert retrieved == complex_obj
        assert retrieved["id"] == "DOID:9351"

    def test_cache_performance(self, cache):
        """Test cache performance with multiple operations."""
        # Set many values
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        # Retrieve them
        for i in range(100):
            value = cache.get(f"key_{i}")
            assert value == f"value_{i}"

        stats = cache.get_stats()
        assert stats["combined"]["sets"] >= 100
        assert stats["combined"]["hits"] >= 100

    def test_cache_expiration_cleanup(self, cache):
        """Test that expired entries are cleaned up."""
        # Set entries with short TTL
        for i in range(10):
            cache.set(f"temp_key_{i}", f"temp_value_{i}", ttl=0.5)

        # Wait for expiration
        time.sleep(0.6)

        # Accessing expired entries should return None
        for i in range(10):
            value = cache.get(f"temp_key_{i}")
            assert value is None
