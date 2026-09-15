"""
Cache package - caching system for knowledge lookup results.
"""

from .cache import (
    CacheBackend,
    CacheEntry,
    CacheStats,
    DiskCacheBackend,
    KnowledgeLookupCache,
    MemoryCacheBackend,
    ensure_cache,
    get_cache,
    init_cache,
)

__all__ = [
    "CacheEntry",
    "CacheStats",
    "CacheBackend",
    "DiskCacheBackend",
    "KnowledgeLookupCache",
    "MemoryCacheBackend",
    "ensure_cache",
    "get_cache",
    "init_cache",
]
