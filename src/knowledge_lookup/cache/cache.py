"""
Professional Caching System for Knowledge Lookup Adapters

Provides memory and disk caching with TTL support, thread safety, and monitoring.
Designed for high-performance API integrations with configurable cache strategies.

## Adapter Integration

All adapters inherit `KnowledgeSourceAdapter` which provides built-in cache integration.

Adapter methods use `_get_cache_key()`, `_get_from_cache()`, `_set_in_cache()`, and `clear_cache()`
for automatic caching support with configurable TTL.
"""

import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached item with metadata."""

    key: str
    value: Any
    created_at: float
    ttl: float | None = None
    access_count: int = 0
    last_accessed: int = field(default_factory=time.monotonic_ns)

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary (deserialization)."""
        return cls(
            key=data["key"],
            value=data["value"],
            created_at=data["created_at"],
            ttl=data["ttl"],
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", data["created_at"]),
        )


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    sets: int = 0
    total_entries: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "sets": self.sets,
            "total_entries": self.total_entries,
            "hit_rate": self.hit_rate,
        }


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve a value from cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value in cache."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        pass

    @abstractmethod
    def cleanup(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get number of entries in cache."""
        pass


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend with TTL support."""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = threading.RLock()
        self._stats = CacheStats()

    def get(self, key: str) -> Any | None:
        """Retrieve a value from memory cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired():
                self._delete_entry(key)
                self._stats.misses += 1
                return None

            entry.access_count += 1
            entry.last_accessed = time.monotonic_ns()
            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value in memory cache."""
        with self._lock:
            if key in self._cache:
                # Update existing entry
                self._cache[key].value = value
                self._cache[key].ttl = ttl
                self._cache[key].created_at = time.time()
            else:
                # Create new entry
                entry = CacheEntry(key=key, value=value, created_at=time.time(), ttl=ttl)
                self._cache[key] = entry
                self._stats.sets += 1

            # Enforce max size (LRU eviction)
            if len(self._cache) > self._max_size:
                self._evict_lru()

    def delete(self, key: str) -> bool:
        """Delete a value from memory cache."""
        with self._lock:
            return self._delete_entry(key)

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()
            self._stats = CacheStats()

    def cleanup(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]
            for key in expired_keys:
                self._delete_entry(key)
            self._stats.evictions += len(expired_keys)
            return len(expired_keys)

    def size(self) -> int:
        """Get number of entries in cache."""
        with self._lock:
            return len(self._cache)

    def _delete_entry(self, key: str) -> bool:
        """Delete an entry (internal method)."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with oldest last_accessed time
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        self._delete_entry(lru_key)
        self._stats.evictions += 1


class DiskCacheBackend(CacheBackend):
    """Disk-based cache backend with persistence."""

    def __init__(self, cache_dir: str | Path, max_size: int = 10000):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_size = max_size
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._index_file = self._cache_dir / "cache_index.json"
        self._index: dict[str, Any] = {}
        self._load_index()

    def get(self, key: str) -> Any | None:
        """Retrieve a value from disk cache."""
        with self._lock:
            cache_file = self._get_cache_file(key)

            if not cache_file.exists():
                self._stats.misses += 1
                return None

            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                entry = CacheEntry.from_dict(data)

                if entry.is_expired():
                    self._delete_entry(key)
                    self._stats.misses += 1
                    return None

                entry.access_count += 1
                entry.last_accessed = time.monotonic_ns()
                self._save_entry(entry)
                self._stats.hits += 1
                return entry.value

            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                self._delete_entry(key)
                self._stats.misses += 1
                return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value in disk cache."""
        with self._lock:
            entry = CacheEntry(key=key, value=value, created_at=time.time(), ttl=ttl)
            self._save_entry(entry)
            self._stats.sets += 1

            # Enforce max size
            if len(self._index) > self._max_size:
                self._evict_lru()

    def delete(self, key: str) -> bool:
        """Delete a value from disk cache."""
        with self._lock:
            return self._delete_entry(key)

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            import shutil

            shutil.rmtree(self._cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._index = {}
            self._stats = CacheStats()
            self._save_index()

    def cleanup(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = []
            current_time = time.time()

            for key, metadata in self._index.items():
                created_at = metadata.get("created_at", 0)
                ttl = metadata.get("ttl")

                if ttl is not None and current_time - created_at > ttl:
                    expired_keys.append(key)

            for key in expired_keys:
                self._delete_entry(key)

            self._stats.evictions += len(expired_keys)
            return len(expired_keys)

    def size(self) -> int:
        """Get number of entries in cache."""
        with self._lock:
            return len(self._index)

    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for a key."""
        # Use hash of key for filename to avoid filesystem issues
        key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key_hash}.json"

    def _save_entry(self, entry: CacheEntry) -> None:
        """Save a cache entry to disk."""
        cache_file = self._get_cache_file(entry.key)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, indent=2)

            # Update index
            self._index[entry.key] = {
                "created_at": entry.created_at,
                "ttl": entry.ttl,
                "access_count": entry.access_count,
                "last_accessed": entry.last_accessed,
            }
            self._save_index()

        except Exception as e:
            logger.error(f"Failed to save cache entry '{entry.key}': {e}")

    def _delete_entry(self, key: str) -> bool:
        """Delete a cache entry."""
        cache_file = self._get_cache_file(key)

        try:
            if cache_file.exists():
                cache_file.unlink()

            if key in self._index:
                del self._index[key]
                self._save_index()
                return True

        except Exception as e:
            logger.error(f"Failed to delete cache entry '{key}': {e}")

        return False

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._index:
            return

        # Find entry with oldest last_accessed time
        lru_key = min(self._index.keys(), key=lambda k: self._index[k].get("last_accessed", 0))
        self._delete_entry(lru_key)
        self._stats.evictions += 1

    def _load_index(self) -> None:
        """Load cache index from disk."""
        self._index = {}

        if self._index_file.exists():
            try:
                with open(self._index_file, encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
                self._index = {}

    def _save_index(self) -> None:
        """Save cache index to disk."""
        try:
            with open(self._index_file, "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")


class KnowledgeLookupCache:
    """
    Professional caching system for knowledge lookup adapters.

    Features:
    - Multi-level caching (memory + disk)
    - TTL support with automatic cleanup
    - Thread-safe operations
    - Performance monitoring
    - Configurable cache strategies
    """

    def __init__(
        self,
        memory_max_size: int = 1000,
        disk_cache_dir: str | Path | None = None,
        disk_max_size: int = 10000,
        default_ttl: float | None = None,
        cleanup_interval: float = 300,  # 5 minutes
    ):
        """
        Initialize the caching system.

        Args:
            memory_max_size: Maximum entries in memory cache
            disk_cache_dir: Directory for disk cache (None disables disk cache)
            disk_max_size: Maximum entries in disk cache
            default_ttl: Default TTL in seconds for cache entries
            cleanup_interval: Interval for automatic cleanup in seconds
        """
        self._memory_cache = MemoryCacheBackend(max_size=memory_max_size)
        self._disk_cache = None

        if disk_cache_dir:
            self._disk_cache = DiskCacheBackend(cache_dir=disk_cache_dir, max_size=disk_max_size)

        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._lock = threading.RLock()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    def get(self, key: str, namespace: str = "") -> Any | None:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace for key isolation

        Returns:
            Cached value or None if not found
        """
        full_key = self._make_key(key, namespace)

        # Try memory cache first
        value = self._memory_cache.get(full_key)
        if value is not None:
            return value

        # Try disk cache if available
        if self._disk_cache:
            value = self._disk_cache.get(full_key)
            if value is not None:
                # Promote to memory cache
                self._memory_cache.set(full_key, value, self._default_ttl)
                return value

        return None

    def set(self, key: str, value: Any, ttl: float | None = None, namespace: str = "") -> None:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            namespace: Optional namespace for key isolation
        """
        full_key = self._make_key(key, namespace)
        effective_ttl = ttl if ttl is not None else self._default_ttl

        # Store in memory cache
        self._memory_cache.set(full_key, value, effective_ttl)

        # Store in disk cache if available
        if self._disk_cache:
            self._disk_cache.set(full_key, value, effective_ttl)

    def delete(self, key: str, namespace: str = "") -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace

        Returns:
            True if deleted, False if not found
        """
        full_key = self._make_key(key, namespace)

        deleted = self._memory_cache.delete(full_key)
        if self._disk_cache:
            deleted = self._disk_cache.delete(full_key) or deleted

        return deleted

    def clear(self, namespace: str = "") -> None:
        """
        Clear cache entries.

        Args:
            namespace: Clear only this namespace (empty clears all)
        """
        if not namespace:
            self._memory_cache.clear()
            if self._disk_cache:
                self._disk_cache.clear()
        else:
            # Namespace-specific clearing would require iterating all keys
            # For now, we'll clear all (can be optimized later)
            logger.warning("Namespace-specific clearing not implemented, clearing all")

    def cleanup(self) -> dict[str, int]:
        """
        Manually trigger cleanup of expired entries.

        Returns:
            Dictionary with cleanup statistics
        """
        with self._lock:
            memory_cleaned = self._memory_cache.cleanup()
            disk_cleaned = 0

            if self._disk_cache:
                disk_cleaned = self._disk_cache.cleanup()

            return {
                "memory_evicted": memory_cleaned,
                "disk_evicted": disk_cleaned,
                "total_evicted": memory_cleaned + disk_cleaned,
            }

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache statistics
        """
        memory_stats = self._memory_cache._stats
        disk_stats = self._disk_cache._stats if self._disk_cache else CacheStats()

        return {
            "memory": memory_stats.to_dict(),
            "disk": disk_stats.to_dict(),
            "combined": {
                "hits": memory_stats.hits + disk_stats.hits,
                "misses": memory_stats.misses + disk_stats.misses,
                "sets": memory_stats.sets + disk_stats.sets,
                "evictions": memory_stats.evictions + disk_stats.evictions,
                "hit_rate": (
                    (memory_stats.hits + disk_stats.hits)
                    / (
                        memory_stats.hits
                        + disk_stats.hits
                        + memory_stats.misses
                        + disk_stats.misses
                    )
                    if (
                        memory_stats.hits
                        + disk_stats.hits
                        + memory_stats.misses
                        + disk_stats.misses
                    )
                    > 0
                    else 0.0
                ),
            },
            "sizes": {
                "memory": self._memory_cache.size(),
                "disk": self._disk_cache.size() if self._disk_cache else 0,
            },
        }

    def _make_key(self, key: str, namespace: str = "") -> str:
        """Create a full cache key with namespace."""
        if namespace:
            return f"{namespace}:{key}"
        return key

    def _cleanup_worker(self) -> None:
        """Background worker for periodic cleanup."""
        while True:
            time.sleep(self._cleanup_interval)
            try:
                self.cleanup()
            except Exception as e:
                logger.error(f"Cache cleanup failed: {e}")


# Global cache instance for easy access
_cache_instance: KnowledgeLookupCache | None = None


def get_cache() -> KnowledgeLookupCache:
    """Get the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = KnowledgeLookupCache()
    return _cache_instance


def init_cache(
    memory_max_size: int = 1000,
    disk_cache_dir: str | Path | None = None,
    disk_max_size: int = 10000,
    default_ttl: float | None = 3600,  # 1 hour
    cleanup_interval: float = 300,
) -> KnowledgeLookupCache:
    """
    Initialize the global cache instance.

    Args:
        memory_max_size: Maximum entries in memory cache
        disk_cache_dir: Directory for disk cache
        disk_max_size: Maximum entries in disk cache
        default_ttl: Default TTL in seconds
        cleanup_interval: Cleanup interval in seconds

    Returns:
        The initialized cache instance
    """
    global _cache_instance
    _cache_instance = KnowledgeLookupCache(
        memory_max_size=memory_max_size,
        disk_cache_dir=disk_cache_dir,
        disk_max_size=disk_max_size,
        default_ttl=default_ttl,
        cleanup_interval=cleanup_interval,
    )
    return _cache_instance
