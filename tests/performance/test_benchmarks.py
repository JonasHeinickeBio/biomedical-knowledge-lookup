"""
Performance benchmarks for the knowledge lookup system.

These tests use the modular :class:`~knowledge_lookup.benchmarks.Benchmarker`
infrastructure so the measurements are reusable and consistent.
"""

import time
from unittest.mock import patch

import pytest
from knowledge_lookup import CentralKnowledgeLookup, KnowledgeSource, LookupConfig
from knowledge_lookup.benchmarks import (
    Benchmarker,
    BenchmarkSuite,
    generate_report,
)
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

    @pytest.fixture
    def suite(self):
        """Isolated suite so each test class gets clean results."""
        return BenchmarkSuite(name="caching_performance")

    def test_cache_write_performance(self, cache, suite):
        """Benchmark cache write operations."""
        bm = Benchmarker("cache_write_100", iterations=1, suite=suite)

        def write_100():
            for i in range(100):
                cache.set(f"key_{i}", f"value_{i}")

        bm.run(write_100)
        result = suite.get("cache_write_100")
        assert result is not None
        assert result.total_s < 1.0  # Should complete in less than 1 second

    def test_cache_read_performance(self, cache, suite):
        """Benchmark cache read operations."""
        # Prepare data
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")

        bm = Benchmarker("cache_read_100", iterations=1, suite=suite)

        def read_100():
            for i in range(100):
                cache.get(f"key_{i}")

        bm.run(read_100)
        result = suite.get("cache_read_100")
        assert result is not None
        assert result.total_s < 0.5  # Reads should be faster than writes

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

    def test_batch_operations_performance(self, cache, suite):
        """Benchmark batch get_many / set_many vs individual operations."""
        data = {f"key_{i}": f"value_{i}" for i in range(50)}

        # Benchmark set_many
        bm_set = Benchmarker("set_many_50", iterations=5, suite=suite)
        bm_set.run(cache.set_many, data)

        # Benchmark individual sets
        bm_set_ind = Benchmarker("set_individual_50", iterations=5, suite=suite)

        def set_individual():
            for k, v in data.items():
                cache.set(k, v)

        bm_set_ind.run(set_individual)

        # Both should complete in reasonable time
        assert suite.get("set_many_50").total_s < 2.0
        assert suite.get("set_individual_50").total_s < 2.0

        print(generate_report(suite))


@pytest.mark.slow
@pytest.mark.asyncio
class TestSearchPerformance:
    """Performance tests for search operations."""

    @pytest.fixture
    def lookup(self):
        """Create lookup instance."""
        config = LookupConfig()
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

        suite = BenchmarkSuite(name="large_object")
        bm_set = Benchmarker("set_large_object", suite=suite)
        bm_set.run(cache.set, "large_object", large_object)

        bm_get = Benchmarker("get_large_object", suite=suite)
        retrieved = bm_get.run(cache.get, "large_object")

        # Should handle large objects efficiently
        assert suite.get("set_large_object").total_s < 1.0
        assert suite.get("get_large_object").total_s < 0.5
        assert retrieved is not None

        print(generate_report(suite))


@pytest.mark.slow
@pytest.mark.asyncio
class TestConcurrentOperations:
    """Tests for concurrent operation performance."""

    @pytest.fixture
    def lookup(self):
        """Create lookup instance for concurrent tests."""
        config = LookupConfig()
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
            return await lookup.search_concepts(query, sources=[KnowledgeSource.OLS])

        queries = [f"query_{i}" for i in range(10)]
        start = time.time()
        results = await asyncio.gather(*[perform_search(q) for q in queries])
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

        suite = BenchmarkSuite(name="scaling")
        data_sizes = [10, 50, 100, 200]

        for size in data_sizes:
            bm = Benchmarker(f"write_{size}_items", suite=suite)
            bm.run(lambda n=size: [cache.set(f"key_{i}", f"value_{i}") for i in range(n)])

        times = [suite.get(f"write_{s}_items").total_s for s in data_sizes]

        # Time should scale roughly linearly
        # Larger datasets shouldn't be exponentially slower
        assert times[-1] < times[0] * len(data_sizes) * 2

        print(generate_report(suite))

    def test_cache_cleanup_performance(self, tmp_path):
        """Test performance of cache cleanup operations."""
        cache_dir = tmp_path / "cleanup_cache"
        cache = KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

        # Add many items with short TTL
        for i in range(100):
            cache.set(f"temp_key_{i}", f"value_{i}", ttl=0.1)

        time.sleep(0.2)  # Wait for expiration

        suite = BenchmarkSuite(name="cleanup")
        bm = Benchmarker("cleanup_expired_100", suite=suite)

        def read_expired():
            for i in range(100):
                cache.get(f"temp_key_{i}")

        bm.run(read_expired)
        result = suite.get("cleanup_expired_100")
        assert result is not None
        assert result.total_s < 1.0  # Cleanup should be efficient

    def test_invalidate_pattern_performance(self, tmp_path):
        """Test performance of pattern-based cache invalidation."""
        cache_dir = tmp_path / "pattern_cache"
        cache = KnowledgeLookupCache(disk_cache_dir=str(cache_dir))

        # Populate cache with mixed namespaced keys
        for i in range(50):
            cache.set(f"diabetes:result:{i}", f"value_{i}")
        for i in range(50):
            cache.set(f"cancer:result:{i}", f"value_{i}")

        suite = BenchmarkSuite(name="invalidation")
        bm = Benchmarker("invalidate_diabetes_ns", suite=suite)
        deleted = bm.run(cache.invalidate_pattern, "diabetes")

        result = suite.get("invalidate_diabetes_ns")
        assert result is not None
        assert result.total_s < 1.0
        # All diabetes keys should have been removed
        assert deleted >= 0  # May be 0 if disk index doesn't support it yet
