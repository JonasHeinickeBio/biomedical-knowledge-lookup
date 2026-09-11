"""
Unit tests for timing utilities.
"""

import sys
import pytest

pytestmark = pytest.mark.unit
import asyncio
import time

from src.knowledge_lookup.utils.timing_utils import (
    TimingStats,
    benchmark_decorator,
    format_timing_comparison,
    time_async_operation,
    time_sync_operation,
    timing_decorator,
)


class TestTimingStats:
    """Test suite for TimingStats class."""

    def test_timing_stats_initialization(self):
        """Test TimingStats initialization."""
        stats = TimingStats()
        assert stats.total_calls == 0
        assert stats.total_time == 0.0
        assert stats.min_time == float("inf")
        assert stats.max_time == 0.0
        assert stats.times == []

    def test_add_measurement(self):
        """Test adding measurements to TimingStats."""
        stats = TimingStats()
        stats.add_measurement(0.1)
        stats.add_measurement(0.3)
        stats.add_measurement(0.2)

        assert stats.total_calls == 3
        assert stats.total_time == pytest.approx(0.6)
        assert stats.min_time == 0.1
        assert stats.max_time == 0.3
        assert len(stats.times) == 3

    def test_average_time(self):
        """Test average time calculation."""
        stats = TimingStats()
        assert stats.average_time == 0.0

        stats.add_measurement(0.1)
        stats.add_measurement(0.3)
        assert stats.average_time == pytest.approx(0.2)

    def test_median_time(self):
        """Test median time calculation."""
        stats = TimingStats()
        assert stats.median_time == 0.0

        stats.add_measurement(0.1)
        stats.add_measurement(0.5)
        stats.add_measurement(0.3)
        # Sorted: 0.1, 0.3, 0.5 -> Median 0.3
        assert stats.median_time == 0.3

        stats.add_measurement(0.7)
        # Sorted: 0.1, 0.3, 0.5, 0.7 -> Median (0.3+0.5)/2 = 0.4
        assert stats.median_time == 0.4

    def test_reset(self):
        """Test resetting TimingStats."""
        stats = TimingStats()
        stats.add_measurement(0.1)
        stats.reset()

        assert stats.total_calls == 0
        assert stats.total_time == 0.0
        assert stats.min_time == float("inf")
        assert stats.max_time == 0.0
        assert stats.times == []


class TestTimingFunctions:
    """Test suite for timing functions and decorators."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows timer resolution too low for precise timing assertions",
    )
    async def test_time_async_operation(self):
        """Test timing an async operation."""

        async def mock_op():
            await asyncio.sleep(0.01)
            return "success"

        duration, result = await time_async_operation(mock_op, iterations=1, log_results=False)

        assert result == "success"
        assert duration >= 0.01

    def test_time_sync_operation(self):
        """Test timing a synchronous operation."""

        def mock_op():
            time.sleep(0.01)
            return "sync success"

        duration, result = time_sync_operation(mock_op, iterations=1, log_results=False)

        assert result == "sync success"
        assert duration >= 0.01

    def test_format_timing_comparison(self):
        """Test timing comparison formatting."""
        comparison = format_timing_comparison(1.1, 0.1, label1="Slow", label2="Fast")
        assert "Slow: 1.100000s" in comparison
        assert "Fast: 0.100000s" in comparison
        assert "Speedup: 11.00x" in comparison
        assert "⚡ Significant performance improvement!" in comparison

    @pytest.mark.asyncio
    async def test_timing_decorator_async(self):
        """Test timing decorator with async function."""

        @timing_decorator(description="Async test")
        async def decorated_async_func():
            await asyncio.sleep(0.01)
            return "decorated success"

        result = await decorated_async_func()
        assert result == "decorated success"

    def test_timing_decorator_sync(self):
        """Test timing decorator with sync function."""

        @timing_decorator(description="Sync test")
        def decorated_sync_func():
            time.sleep(0.01)
            return "sync decorated success"

        result = decorated_sync_func()
        assert result == "sync decorated success"

    @pytest.mark.asyncio
    async def test_benchmark_decorator(self):
        """Test benchmark decorator."""

        @benchmark_decorator(iterations=3)
        async def benchmarked_func():
            await asyncio.sleep(0.01)
            return "benchmarked success"

        result = await benchmarked_func()
        assert result == "benchmarked success"
