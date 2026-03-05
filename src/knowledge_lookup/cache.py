"""
Professional Caching System for Knowledge Lookup Adapters

Provides memory and disk caching with TTL support, thread safety, and monitoring.
Designed for high-performance API integrations with configurable cache strategies.

Features:
- Multi-level caching (memory + disk)
- Optional Redis backend for distributed deployments
- Compression support for large objects (zlib)
- Async cache operations
- Batch get/set operations
- Pattern-based cache invalidation
- Enhanced analytics and monitoring
"""

import asyncio
import hashlib
import json
import logging
import threading
import time
import zlib
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Optional Redis support
try:
    import redis  # type: ignore[import-untyped]

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = logging.getLogger(__name__)


class CacheBackendType(Enum):
    """Supported cache backend types."""

    MEMORY = "memory"
    DISK = "disk"
    REDIS = "redis"


@dataclass
class CacheEntry:
    """Represents a cached item with metadata."""

    key: str
    value: Any
    created_at: float
    ttl: float | None = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

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
    compressed_entries: int = 0
    bytes_saved_by_compression: int = 0
    batch_operations: int = 0

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
            "compressed_entries": self.compressed_entries,
            "bytes_saved_by_compression": self.bytes_saved_by_compression,
            "batch_operations": self.batch_operations,
        }


# ---------------------------------------------------------------------------
# Compression helpers
# ---------------------------------------------------------------------------

_COMPRESSION_THRESHOLD = 1024  # bytes — only compress values larger than this


def _compress_value(value: Any) -> tuple[bytes, int]:
    """Serialize and compress *value* with zlib.

    Returns ``(compressed_bytes, original_size)`` so callers can track savings.
    """
    raw = json.dumps(value, default=str).encode("utf-8")
    compressed = zlib.compress(raw, level=6)
    return compressed, len(raw)


def _decompress_value(data: bytes) -> Any:
    """Decompress and deserialize a value previously compressed by :func:`_compress_value`."""
    raw = zlib.decompress(data)
    return json.loads(raw.decode("utf-8"))


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

    # ------------------------------------------------------------------
    # Optional batch / pattern operations (default implementations)
    # ------------------------------------------------------------------

    def get_many(self, keys: Iterable[str]) -> dict[str, Any]:
        """Retrieve multiple values at once.  Returns a dict of key→value for hits."""
        result: dict[str, Any] = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(self, mapping: dict[str, Any], ttl: float | None = None) -> None:
        """Store multiple key/value pairs at once."""
        for key, value in mapping.items():
            self.set(key, value, ttl)

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys that contain *pattern* as a substring.

        Returns the number of deleted entries.  Backends may override this
        with a more efficient implementation.
        """
        return 0


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
            entry.last_accessed = time.time()
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

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys containing *pattern* as a substring."""
        with self._lock:
            matching = [k for k in self._cache if pattern in k]
            for key in matching:
                self._delete_entry(key)
            self._stats.evictions += len(matching)
            return len(matching)


class DiskCacheBackend(CacheBackend):
    """Disk-based cache backend with persistence."""

    def __init__(self, cache_dir: str | Path, max_size: int = 10000):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_size = max_size
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._index_file = self._cache_dir / "cache_index.json"
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
                entry.last_accessed = time.time()
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

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys containing *pattern* as a substring."""
        with self._lock:
            matching = [k for k in list(self._index.keys()) if pattern in k]
            for key in matching:
                self._delete_entry(key)
            self._stats.evictions += len(matching)
            return len(matching)


class RedisCacheBackend(CacheBackend):
    """Redis-based cache backend for distributed deployments.

    Requires the ``redis`` package (``pip install redis``).
    Values are JSON-serialised before storage so they survive across processes.
    Large values above *compression_threshold* bytes are automatically
    compressed with zlib before being stored in Redis.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        key_prefix: str = "klookup:",
        compression_threshold: int = _COMPRESSION_THRESHOLD,
        **kwargs: Any,
    ):
        if not HAS_REDIS:
            raise ImportError(
                "The 'redis' package is required for RedisCacheBackend. "
                "Install it with: pip install redis"
            )
        self._prefix = key_prefix
        self._compression_threshold = compression_threshold
        self._stats = CacheStats()
        self._client = redis.Redis(
            host=host, port=port, db=db, password=password, decode_responses=False, **kwargs
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _encode(self, value: Any) -> bytes:
        raw = json.dumps(value, default=str).encode("utf-8")
        if len(raw) >= self._compression_threshold:
            compressed = zlib.compress(raw, level=6)
            # Mark as compressed with a 1-byte flag
            payload = b"\x01" + compressed
            self._stats.compressed_entries += 1
            self._stats.bytes_saved_by_compression += len(raw) - len(compressed)
        else:
            payload = b"\x00" + raw
        return payload

    def _decode(self, data: bytes) -> Any:
        flag, body = data[0:1], data[1:]
        if flag == b"\x01":
            body = zlib.decompress(body)
        return json.loads(body.decode("utf-8"))

    # ------------------------------------------------------------------
    # CacheBackend interface
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        try:
            data = self._client.get(self._full_key(key))
            if data is None:
                self._stats.misses += 1
                return None
            self._stats.hits += 1
            return self._decode(data)
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            self._stats.misses += 1
            return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        try:
            payload = self._encode(value)
            fkey = self._full_key(key)
            if ttl is not None:
                self._client.setex(fkey, int(ttl), payload)
            else:
                self._client.set(fkey, payload)
            self._stats.sets += 1
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")

    def delete(self, key: str) -> bool:
        try:
            result = self._client.delete(self._full_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
            return False

    def clear(self) -> None:
        try:
            pattern = f"{self._prefix}*"
            keys = self._client.keys(pattern)
            if keys:
                self._client.delete(*keys)
            self._stats = CacheStats()
        except Exception as e:
            logger.error(f"Redis CLEAR error: {e}")

    def cleanup(self) -> int:
        """Redis manages TTL expiry natively; nothing to do here."""
        return 0

    def size(self) -> int:
        try:
            return len(self._client.keys(f"{self._prefix}*"))
        except Exception as e:
            logger.error(f"Redis SIZE error: {e}")
            return 0

    def get_many(self, keys: Iterable[str]) -> dict[str, Any]:
        keys_list = list(keys)
        if not keys_list:
            return {}
        try:
            full_keys = [self._full_key(k) for k in keys_list]
            values = self._client.mget(full_keys)
            result: dict[str, Any] = {}
            for orig_key, data in zip(keys_list, values, strict=True):
                if data is not None:
                    result[orig_key] = self._decode(data)
                    self._stats.hits += 1
                else:
                    self._stats.misses += 1
            return result
        except Exception as e:
            logger.error(f"Redis MGET error: {e}")
            return {}

    def set_many(self, mapping: dict[str, Any], ttl: float | None = None) -> None:
        try:
            pipe = self._client.pipeline()
            for key, value in mapping.items():
                payload = self._encode(value)
                fkey = self._full_key(key)
                if ttl is not None:
                    pipe.setex(fkey, int(ttl), payload)
                else:
                    pipe.set(fkey, payload)
                self._stats.sets += 1
            pipe.execute()
            self._stats.batch_operations += 1
        except Exception as e:
            logger.error(f"Redis MSET error: {e}")
            # Fall back to individual sets
            for key, value in mapping.items():
                self.set(key, value, ttl)

    def invalidate_pattern(self, pattern: str) -> int:
        try:
            full_pattern = f"{self._prefix}*{pattern}*"
            keys = self._client.keys(full_pattern)
            if keys:
                self._client.delete(*keys)
                self._stats.evictions += len(keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Redis INVALIDATE_PATTERN error: {e}")
            return 0


class KnowledgeLookupCache:
    """
    Professional caching system for knowledge lookup adapters.

    Features:
    - Multi-level caching (memory + disk)
    - Optional Redis backend for distributed deployments
    - Compression support for large objects
    - TTL support with automatic cleanup
    - Thread-safe synchronous operations
    - Async wrappers for non-blocking usage
    - Batch get/set operations
    - Pattern-based cache invalidation
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
        redis_backend: Optional["RedisCacheBackend"] = None,
        compression_threshold: int = _COMPRESSION_THRESHOLD,
    ):
        """
        Initialize the caching system.

        Args:
            memory_max_size: Maximum entries in memory cache
            disk_cache_dir: Directory for disk cache (None disables disk cache)
            disk_max_size: Maximum entries in disk cache
            default_ttl: Default TTL in seconds for cache entries
            cleanup_interval: Interval for automatic cleanup in seconds
            redis_backend: Pre-configured :class:`RedisCacheBackend` instance.
                When provided, Redis is used as the primary persistent store
                instead of the disk cache.
            compression_threshold: Byte size above which values are compressed
                before storage (applies to memory backend only; Redis has its own
                threshold set on the backend itself).
        """
        self._memory_cache = MemoryCacheBackend(max_size=memory_max_size)
        self._disk_cache: DiskCacheBackend | None = None
        self._redis_cache: RedisCacheBackend | None = redis_backend
        self._compression_threshold = compression_threshold

        if disk_cache_dir and redis_backend is None:
            self._disk_cache = DiskCacheBackend(cache_dir=disk_cache_dir, max_size=disk_max_size)

        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._lock = threading.RLock()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    # ------------------------------------------------------------------
    # Synchronous API
    # ------------------------------------------------------------------

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

        # Try memory cache first (fastest)
        value = self._memory_cache.get(full_key)
        if value is not None:
            return value

        # Try Redis if configured
        if self._redis_cache is not None:
            value = self._redis_cache.get(full_key)
            if value is not None:
                # Promote to memory cache
                self._memory_cache.set(full_key, value, self._default_ttl)
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

        # Store in Redis if configured
        if self._redis_cache is not None:
            self._redis_cache.set(full_key, value, effective_ttl)

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
        if self._redis_cache is not None:
            deleted = self._redis_cache.delete(full_key) or deleted
        if self._disk_cache:
            deleted = self._disk_cache.delete(full_key) or deleted

        return deleted

    def get_many(self, keys: list[str], namespace: str = "") -> dict[str, Any]:
        """Retrieve multiple values at once.

        Returns a mapping of key → value for all cache hits.

        Args:
            keys: List of cache keys to retrieve
            namespace: Optional namespace for key isolation
        """
        full_keys = [self._make_key(k, namespace) for k in keys]
        result: dict[str, Any] = {}
        missing_full: list[str] = []

        # Memory pass
        for fk in full_keys:
            val = self._memory_cache.get(fk)
            if val is not None:
                result[fk] = val
            else:
                missing_full.append(fk)

        # Redis pass for remaining misses
        if missing_full and self._redis_cache is not None:
            redis_hits = self._redis_cache.get_many(missing_full)
            for fk, val in redis_hits.items():
                result[fk] = val
                self._memory_cache.set(fk, val, self._default_ttl)
            missing_full = [fk for fk in missing_full if fk not in redis_hits]

        # Disk pass for remaining misses
        if missing_full and self._disk_cache:
            for fk in missing_full:
                val = self._disk_cache.get(fk)
                if val is not None:
                    result[fk] = val
                    self._memory_cache.set(fk, val, self._default_ttl)

        # Re-map full keys back to original keys
        orig_key_map = {self._make_key(k, namespace): k for k in keys}
        return {orig_key_map[fk]: v for fk, v in result.items() if fk in orig_key_map}

    def set_many(
        self,
        mapping: dict[str, Any],
        ttl: float | None = None,
        namespace: str = "",
    ) -> None:
        """Store multiple key/value pairs at once.

        Args:
            mapping: Dictionary of key → value pairs
            ttl: Time to live in seconds (uses default if None)
            namespace: Optional namespace for key isolation
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        full_mapping = {self._make_key(k, namespace): v for k, v in mapping.items()}

        self._memory_cache.set_many(full_mapping, effective_ttl)
        if self._redis_cache is not None:
            self._redis_cache.set_many(full_mapping, effective_ttl)
        if self._disk_cache:
            self._disk_cache.set_many(full_mapping, effective_ttl)

    def invalidate_pattern(self, pattern: str, namespace: str = "") -> int:
        """Invalidate all cache entries whose key contains *pattern*.

        Args:
            pattern: Substring to match against cache keys
            namespace: Optional namespace prefix (prepended to pattern)

        Returns:
            Total number of entries deleted across all backends
        """
        full_pattern = self._make_key(pattern, namespace)
        total = self._memory_cache.invalidate_pattern(full_pattern)
        if self._redis_cache is not None:
            total += self._redis_cache.invalidate_pattern(full_pattern)
        if self._disk_cache:
            total += self._disk_cache.invalidate_pattern(full_pattern)
        return total

    def clear(self, namespace: str = "") -> None:
        """
        Clear cache entries.

        Args:
            namespace: Clear only this namespace (empty clears all)
        """
        if not namespace:
            self._memory_cache.clear()
            if self._redis_cache is not None:
                self._redis_cache.clear()
            if self._disk_cache:
                self._disk_cache.clear()
        else:
            # Delegate to pattern-based invalidation for namespaced clears
            self.invalidate_pattern("", namespace=namespace)

    def cleanup(self) -> dict[str, int]:
        """
        Manually trigger cleanup of expired entries.

        Returns:
            Dictionary with cleanup statistics
        """
        with self._lock:
            memory_cleaned = self._memory_cache.cleanup()
            redis_cleaned = 0
            disk_cleaned = 0

            if self._redis_cache is not None:
                redis_cleaned = self._redis_cache.cleanup()
            if self._disk_cache:
                disk_cleaned = self._disk_cache.cleanup()

            return {
                "memory_evicted": memory_cleaned,
                "redis_evicted": redis_cleaned,
                "disk_evicted": disk_cleaned,
                "total_evicted": memory_cleaned + redis_cleaned + disk_cleaned,
            }

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache statistics
        """
        memory_stats = self._memory_cache._stats
        redis_stats = self._redis_cache._stats if self._redis_cache else CacheStats()
        disk_stats = self._disk_cache._stats if self._disk_cache else CacheStats()

        total_hits = memory_stats.hits + redis_stats.hits + disk_stats.hits
        total_misses = memory_stats.misses + redis_stats.misses + disk_stats.misses

        return {
            "memory": memory_stats.to_dict(),
            "redis": redis_stats.to_dict(),
            "disk": disk_stats.to_dict(),
            "combined": {
                "hits": total_hits,
                "misses": total_misses,
                "sets": memory_stats.sets + redis_stats.sets + disk_stats.sets,
                "evictions": (
                    memory_stats.evictions + redis_stats.evictions + disk_stats.evictions
                ),
                "hit_rate": (
                    total_hits / (total_hits + total_misses)
                    if (total_hits + total_misses) > 0
                    else 0.0
                ),
                "compressed_entries": (
                    memory_stats.compressed_entries
                    + redis_stats.compressed_entries
                    + disk_stats.compressed_entries
                ),
                "bytes_saved_by_compression": (
                    memory_stats.bytes_saved_by_compression
                    + redis_stats.bytes_saved_by_compression
                    + disk_stats.bytes_saved_by_compression
                ),
            },
            "sizes": {
                "memory": self._memory_cache.size(),
                "redis": self._redis_cache.size() if self._redis_cache else 0,
                "disk": self._disk_cache.size() if self._disk_cache else 0,
            },
            "backends": {
                "memory": True,
                "redis": self._redis_cache is not None,
                "disk": self._disk_cache is not None,
            },
        }

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------

    async def async_get(self, key: str, namespace: str = "") -> Any | None:
        """Async wrapper for :meth:`get`.

        Runs the blocking I/O in a thread-pool executor so it doesn't block
        the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get, key, namespace)

    async def async_set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        namespace: str = "",
    ) -> None:
        """Async wrapper for :meth:`set`."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.set(key, value, ttl, namespace))

    async def async_delete(self, key: str, namespace: str = "") -> bool:
        """Async wrapper for :meth:`delete`."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.delete, key, namespace)

    async def async_get_many(self, keys: list[str], namespace: str = "") -> dict[str, Any]:
        """Async wrapper for :meth:`get_many`."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_many, keys, namespace)

    async def async_set_many(
        self,
        mapping: dict[str, Any],
        ttl: float | None = None,
        namespace: str = "",
    ) -> None:
        """Async wrapper for :meth:`set_many`."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.set_many(mapping, ttl, namespace))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
    redis_backend: Optional["RedisCacheBackend"] = None,
) -> KnowledgeLookupCache:
    """
    Initialize the global cache instance.

    Args:
        memory_max_size: Maximum entries in memory cache
        disk_cache_dir: Directory for disk cache
        disk_max_size: Maximum entries in disk cache
        default_ttl: Default TTL in seconds
        cleanup_interval: Cleanup interval in seconds
        redis_backend: Optional pre-configured :class:`RedisCacheBackend`.
            When provided, Redis replaces the disk cache as the secondary tier.

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
        redis_backend=redis_backend,
    )
    return _cache_instance


def create_cache_backend(
    backend_type: CacheBackendType,
    **kwargs: Any,
) -> CacheBackend:
    """Factory function that creates a :class:`CacheBackend` instance.

    Args:
        backend_type: Which backend to create.
        **kwargs: Arguments forwarded to the backend constructor.

    Returns:
        A configured :class:`CacheBackend` instance.

    Raises:
        ImportError: If ``backend_type`` is :attr:`CacheBackendType.REDIS` and
            the ``redis`` package is not installed.
        ValueError: If ``backend_type`` is unknown.
    """
    if backend_type == CacheBackendType.MEMORY:
        return MemoryCacheBackend(**kwargs)
    if backend_type == CacheBackendType.DISK:
        return DiskCacheBackend(**kwargs)
    if backend_type == CacheBackendType.REDIS:
        return RedisCacheBackend(**kwargs)
    raise ValueError(f"Unknown cache backend type: {backend_type}")
