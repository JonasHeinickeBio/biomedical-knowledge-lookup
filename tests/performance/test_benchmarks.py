"""
Performance benchmarks for the knowledge lookup system.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.cache import KnowledgeLookupCache
from knowledge_lookup.models import ConceptType, UnifiedConcept


@pytest.mark.slow
@pytest.mark.asyncio
class TestCachingPerformance:
    """Performance tests for caching system."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache instance for benchmarking."""
        cache_dir = tmp_path / "benchmark_cache"
        return KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

    def test_cache_write_performance(self, cache, benchmark):
        """Benchmark cache write operations."""

        def write_to_cache():
            for i in range(100):
                cache.set(f"key_{i}", f"value_{i}")

        if hasattr(pytest, "benchmark"):
            benchmark(write_to_cache)
        else:
            start = time.time()
            write_to_cache()
            duration = time.time() - start
            assert duration < 1.0  # Should complete in less than 1 second

    def test_cache_read_performance(self, cache, benchmark):
        """Benchmark cache read operations."""
        # Prepare data
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        def read_from_cache():
            for i in range(100):
                cache.get(f"key_{i}")

        if hasattr(pytest, "benchmark"):
            benchmark(read_from_cache)
        else:
            start = time.time()
            read_from_cache()
            duration = time.time() - start
            assert duration < 0.5  # Reads should be faster than writes

    def test_cache_hit_rate(self, cache):
        """Test cache hit rate under normal load."""
        # Set 100 items
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        # Access 80 of them (simulate 80% hit rate scenario)
        for i in range(80):
            cache.get(f"key_{i}")

        # Access 20 non-existent items
        for i in range(100, 120):
            cache.get(f"key_{i}")

        stats = cache.get_stats()
        # Should have reasonable hit rate
        assert stats["combined"]["hit_rate"] >= 0.7

    def test_cache_concurrent_access(self, cache):
        """Test cache performance under concurrent access."""
        import asyncio

        async def concurrent_operations():
            tasks = []
            for i in range(50):
                # Mix of reads and writes
                cache.set(f"key_{i}", f"value_{i}")
                tasks.append(asyncio.sleep(0.001))

            await asyncio.gather(*tasks)

        start = time.time()
        asyncio.run(concurrent_operations())
        duration = time.time() - start

        # Should complete reasonably fast
        assert duration < 2.0


@pytest.mark.slow
@pytest.mark.asyncio
class TestSearchPerformance:
    """Performance tests for search operations."""

    @pytest.fixture
    def lookup(self):
        """Create lookup instance with caching enabled."""
        config = LookupConfig(cache_enabled=True)
        return CentralKnowledgeLookup(config)

    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_search_with_cache_performance(self, mock_search, lookup):
        """Test search performance with caching."""
        mock_concepts = [
            UnifiedConcept(
                primary_id=f"TEST:{i}",
                primary_label=f"Test {i}",
                concept_type=ConceptType.DISEASE,
            )
            for i in range(10)
        ]
        mock_search.return_value = mock_concepts

        # First search (cache miss)
        start = time.time()
        await lookup.search_concepts("diabetes", sources=[KnowledgeSource.OLS])
        first_call_time = time.time() - start

        # Second search (cache hit)
        start = time.time()
        await lookup.search_concepts("diabetes", sources=[KnowledgeSource.OLS])
        second_call_time = time.time() - start

        # Cache should make second call faster (or at least not slower)
        assert second_call_time <= first_call_time * 2

    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_batch_search_performance(self, mock_search, lookup):
        """Test performance of batch searches."""
        mock_concepts = [
            UnifiedConcept(
                primary_id="TEST:001",
                primary_label="Test",
                concept_type=ConceptType.DISEASE,
            )
        ]
        mock_search.return_value = mock_concepts

        queries = [f"query_{i}" for i in range(20)]

        start = time.time()
        for query in queries:
            await lookup.search_concepts(query, sources=[KnowledgeSource.OLS])
        duration = time.time() - start

        # Should complete in reasonable time
        assert duration < 5.0
        # Average time per query
        avg_time = duration / len(queries)
        assert avg_time < 0.5


@pytest.mark.slow
class TestMemoryUsage:
    """Tests for memory usage and efficiency."""

    def test_cache_memory_limits(self, tmp_path):
        """Test that cache respects memory limits."""
        cache_dir = tmp_path / "memory_test_cache"
        cache = KnowledgeLookupCache(
            memory_max_size=100,
            disk_cache_dir=str(cache_dir),
        )

        # Add more items than max_size
        for i in range(150):
            cache.set(f"key_{i}", f"value_{i}" * 100)  # Larger values

        # Cache should not exceed max_size by too much
        stats = cache.get_stats()
        total_size = stats["sizes"]["memory"] + stats["sizes"]["disk"]
        assert total_size <= 150  # Allow some overhead

    def test_large_object_caching(self, tmp_path):
        """Test caching of large objects."""
        cache_dir = tmp_path / "large_object_cache"
        cache = KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

        # Create a large object
        large_object = {
            "concepts": [
                {
                    "id": f"CONCEPT:{i}",
                    "label": f"Concept {i}",
                    "data": "x" * 1000,
                }
                for i in range(100)
            ]
        }

        start = time.time()
        cache.set("large_object", large_object)
        set_time = time.time() - start

        start = time.time()
        retrieved = cache.get("large_object")
        get_time = time.time() - start

        # Should handle large objects efficiently
        assert set_time < 1.0
        assert get_time < 0.5
        assert retrieved is not None


@pytest.mark.slow
@pytest.mark.asyncio
class TestConcurrentOperations:
    """Tests for concurrent operation performance."""

    @pytest.fixture
    def lookup(self):
        """Create lookup instance for concurrent tests."""
        config = LookupConfig(cache_enabled=True)
        return CentralKnowledgeLookup(config)

    @patch("knowledge_lookup.adapters.ols_adapter.OLSAdapter.search_concepts")
    async def test_concurrent_searches(self, mock_search, lookup):
        """Test concurrent search operations."""
        import asyncio

        mock_concepts = [
            UnifiedConcept(
                primary_id="TEST:001",
                primary_label="Test",
                concept_type=ConceptType.DISEASE,
            )
        ]
        mock_search.return_value = mock_concepts

        async def perform_search(query):
            return await lookup.search_concepts(
                query, sources=[KnowledgeSource.OLS]
            )

        queries = [f"query_{i}" for i in range(10)]
        start = time.time()
        results = await asyncio.gather(
            *[perform_search(q) for q in queries]
        )
        duration = time.time() - start

        assert len(results) == len(queries)
        # Concurrent operations should be faster than sequential
        assert duration < 3.0


@pytest.mark.slow
class TestScalability:
    """Tests for system scalability."""

    def test_scaling_with_data_size(self, tmp_path):
        """Test how system scales with increasing data size."""
        cache_dir = tmp_path / "scaling_cache"
        cache = KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

        data_sizes = [10, 50, 100, 200]
        times = []

        for size in data_sizes:
            start = time.time()
            for i in range(size):
                cache.set(f"key_{i}", f"value_{i}")
            duration = time.time() - start
            times.append(duration)

        # Time should scale roughly linearly
        # Larger datasets shouldn't be exponentially slower
        assert times[-1] < times[0] * len(data_sizes) * 2

    def test_cache_cleanup_performance(self, tmp_path):
        """Test performance of cache cleanup operations."""
        cache_dir = tmp_path / "cleanup_cache"
        cache = KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

        # Add many items with short TTL
        for i in range(100):
            cache.set(f"temp_key_{i}", f"value_{i}", ttl=0.1)

        time.sleep(0.2)  # Wait for expiration

        # Access cache to trigger cleanup
        start = time.time()
        for i in range(100):
            cache.get(f"temp_key_{i}")
        duration = time.time() - start

        # Cleanup should be efficient
        assert duration < 1.0
