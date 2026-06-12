"""
Timing utilities for performance measurement and benchmarking.

Provides high-precision timing functions and decorators for measuring
operation performance, especially useful for API calls and database operations.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimingStats:
    """Container for timing statistics."""

    def __init__(self):
        self.total_calls = 0
        self.total_time = 0.0
        self.min_time = float("inf")
        self.max_time = 0.0
        self.times = []

    def add_measurement(self, duration: float):
        """Add a timing measurement."""
        self.total_calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.times.append(duration)

    @property
    def average_time(self) -> float:
        """Get average execution time."""
        return self.total_time / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def median_time(self) -> float:
        """Get median execution time."""
        if not self.times:
            return 0.0
        sorted_times = sorted(self.times)
        n = len(sorted_times)
        if n % 2 == 0:
            return (sorted_times[n // 2 - 1] + sorted_times[n // 2]) / 2
        return sorted_times[n // 2]

    def reset(self):
        """Reset all statistics."""
        self.total_calls = 0
        self.total_time = 0.0
        self.min_time = float("inf")
        self.max_time = 0.0
        self.times.clear()

    def __str__(self) -> str:
        """String representation of timing statistics."""
        if self.total_calls == 0:
            return "No measurements recorded"

        return (
            f"Timing Statistics:\n"
            f"  Total calls: {self.total_calls}\n"
            f"  Total time: {self.total_time:.6f}s\n"
            f"  Average: {self.average_time:.6f}s\n"
            f"  Median: {self.median_time:.6f}s\n"
            f"  Min: {self.min_time:.6f}s\n"
            f"  Max: {self.max_time:.6f}s"
        )


class TimingContext:
    """Context manager for timing operations with automatic logging."""

    def __init__(self, description: str, log_level: int = logging.INFO, precision: int = 6):
        self.description = description
        self.log_level = log_level
        self.precision = precision
        self.start_time: float | None = None
        self.end_time: float | None = None

    async def __aenter__(self):
        self.start_time = time.perf_counter_ns()
        logger.log(self.log_level, f"Starting: {self.description}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter_ns()
        if self.start_time is not None:
            duration_ns = self.end_time - self.start_time
            duration_s = duration_ns / 1_000_000_000

            if exc_type is None:
                logger.log(
                    self.log_level,
                    f"Completed: {self.description} in {duration_s:.{self.precision}f}s "
                    f"({duration_ns:.0f}ns / {duration_ns / 1_000:.1f}μs)",
                )
            else:
                logger.log(
                    self.log_level,
                    f"Failed: {self.description} after {duration_s:.{self.precision}f}s "
                    f"({duration_ns:.0f}ns / {duration_ns / 1_000:.1f}μs)",
                )


async def time_async_operation(
    operation: Callable[[], Awaitable[Any]],
    description: str = "Operation",
    iterations: int = 1,
    log_results: bool = True,
    return_stats: bool = False,
) -> tuple[float, Any] | tuple[TimingStats, Any]:
    """
    Time an async operation with high precision timing.

    Args:
        operation: Async function to time (should be a lambda or partial)
        description: Description for logging
        iterations: Number of times to run for averaging
        log_results: Whether to log timing results
        return_stats: Whether to return TimingStats object instead of average

    Returns:
        If return_stats=False: Tuple of (average_time_seconds, last_result)
        If return_stats=True: Tuple of (TimingStats, last_result)
    """
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    stats = TimingStats()
    result = None

    for i in range(iterations):
        start_time = time.perf_counter_ns()  # Nanosecond precision
        try:
            result = await operation()
        except Exception as e:
            # Still record the timing even if operation failed
            end_time = time.perf_counter_ns()
            duration = (end_time - start_time) / 1_000_000_000
            stats.add_measurement(duration)
            raise e

        end_time = time.perf_counter_ns()
        duration = (end_time - start_time) / 1_000_000_000  # Convert to seconds
        stats.add_measurement(duration)

        if iterations > 1 and log_results:
            print(f"  Run {i + 1}: {duration:.6f} seconds")

    if log_results:
        if iterations == 1:
            duration = stats.times[0]
            print(f"{description}:")
            print(f"  Duration: {duration:.6f} seconds")
            print(f"  Performance: {1 / duration:.1f} ops/sec")
        else:
            print(f"{description}:")
            print(f"  Average: {stats.average_time:.6f} seconds")
            print(f"  Range: {stats.min_time:.6f} - {stats.max_time:.6f} seconds")
            print(f"  Median: {stats.median_time:.6f} seconds")

    if return_stats:
        return stats, result
    else:
        return stats.average_time, result


def time_sync_operation(
    operation: Callable[[], Any],
    description: str = "Operation",
    iterations: int = 1,
    log_results: bool = True,
    return_stats: bool = False,
) -> tuple[float, Any] | tuple[TimingStats, Any]:
    """
    Time a synchronous operation with high precision timing.

    Args:
        operation: Function to time
        description: Description for logging
        iterations: Number of times to run for averaging
        log_results: Whether to log timing results
        return_stats: Whether to return TimingStats object instead of average

    Returns:
        If return_stats=False: Tuple of (average_time_seconds, last_result)
        If return_stats=True: Tuple of (TimingStats, last_result)
    """

    async def async_wrapper():
        return operation()

    return asyncio.run(
        time_async_operation(async_wrapper, description, iterations, log_results, return_stats)
    )


def format_timing_comparison(
    time1: float,
    time2: float,
    label1: str = "First call",
    label2: str = "Second call",
    include_improvement: bool = True,
) -> str:
    """
    Format a timing comparison between two operations.

    Args:
        time1: Time for first operation (seconds)
        time2: Time for second operation (seconds)
        label1: Label for first operation
        label2: Label for second operation
        include_improvement: Whether to include improvement analysis

    Returns:
        Formatted comparison string
    """
    if time2 <= 0:
        return f"⚡ {label2} too fast to measure accurately (>1000x speedup)"

    speedup = time1 / time2

    comparison = (
        f"⏱️  Timing Comparison:\n"
        f"  {label1}: {time1:.6f}s\n"
        f"  {label2}: {time2:.6f}s\n"
        f"  Speedup: {speedup:.2f}x"
    )

    if not include_improvement:
        return comparison

    if speedup > 100:
        comparison += "\n   🚀 Exceptional performance improvement!"
    elif speedup > 10:
        comparison += "\n   ⚡ Significant performance improvement!"
    elif speedup > 2:
        comparison += "\n   ✅ Measurable performance improvement."
    else:
        comparison += "\n   📊 Minor performance improvement."

    return comparison


def timing_decorator(
    description: str | None = None,
    log_level: int = logging.INFO,
    precision: int = 6,
    include_args: bool = False,
    include_result: bool = False,
):
    """
    Decorator for timing async and sync functions.

    Args:
        description: Custom description (defaults to function name)
        log_level: Logging level for timing output
        precision: Decimal precision for timing display
        include_args: Whether to include function arguments in description
        include_result: Whether to include result in logging (be careful with large objects)

    Returns:
        Decorated function that logs timing information
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            desc = description or f"{func.__name__}"
            if include_args and (args or kwargs):
                arg_str = ", ".join([str(arg) for arg in args[:3]])  # Limit to first 3 args
                if kwargs:
                    kwarg_str = ", ".join([f"{k}={v}" for k, v in list(kwargs.items())[:2]])
                    arg_str += f", {kwarg_str}"
                desc += f"({arg_str})"

            start_time = time.perf_counter_ns()

            try:
                result = await func(*args, **kwargs)
                end_time = time.perf_counter_ns()

                duration_ns = end_time - start_time
                duration_s = duration_ns / 1_000_000_000

                log_msg = f"⏱️  {desc} completed in {duration_s:.{precision}f}s"
                if include_result and result is not None:
                    result_preview = (
                        str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    )
                    log_msg += f" → {result_preview}"

                logger.log(log_level, log_msg)
                return result

            except Exception as e:
                end_time = time.perf_counter_ns()
                duration_ns = end_time - start_time
                duration_s = duration_ns / 1_000_000_000

                logger.log(log_level, f"❌ {desc} failed after {duration_s:.{precision}f}s: {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            desc = description or f"{func.__name__}"
            if include_args and (args or kwargs):
                arg_str = ", ".join([str(arg) for arg in args[:3]])
                if kwargs:
                    kwarg_str = ", ".join([f"{k}={v}" for k, v in list(kwargs.items())[:2]])
                    arg_str += f", {kwarg_str}"
                desc += f"({arg_str})"

            start_time = time.perf_counter_ns()

            try:
                result = func(*args, **kwargs)
                end_time = time.perf_counter_ns()

                duration_ns = end_time - start_time
                duration_s = duration_ns / 1_000_000_000

                log_msg = f"⏱️  {desc} completed in {duration_s:.{precision}f}s"
                if include_result and result is not None:
                    result_preview = (
                        str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    )
                    log_msg += f" → {result_preview}"

                logger.log(log_level, log_msg)
                return result

            except Exception as e:
                end_time = time.perf_counter_ns()
                duration_ns = end_time - start_time
                duration_s = duration_ns / 1_000_000_000

                logger.log(log_level, f"❌ {desc} failed after {duration_s:.{precision}f}s: {e}")
                raise

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def benchmark_decorator(
    iterations: int = 5,
    description: str | None = None,
    log_level: int = logging.INFO,
    include_stats: bool = True,
):
    """
    Decorator for benchmarking functions with multiple iterations.

    Args:
        iterations: Number of times to run the function
        description: Custom description (defaults to function name)
        log_level: Logging level for benchmark output
        include_stats: Whether to include detailed statistics

    Returns:
        Decorated function that runs benchmarks
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            desc = description or f"Benchmark: {func.__name__}"

            async def operation():
                return await func(*args, **kwargs)

            stats, result = await time_async_operation(
                operation, desc, iterations, log_results=True, return_stats=True
            )

            # Type cast - we know stats is TimingStats when return_stats=True
            stats = cast(TimingStats, stats)

            if include_stats and iterations > 1:
                logger.log(log_level, f"📊 {desc} statistics:")
                logger.log(log_level, f"   Total calls: {stats.total_calls}")
                logger.log(log_level, f"   Average: {stats.average_time:.6f}s")
                logger.log(log_level, f"   Median: {stats.median_time:.6f}s")
                logger.log(log_level, f"   Range: {stats.min_time:.6f}s - {stats.max_time:.6f}s")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            desc = description or f"Benchmark: {func.__name__}"

            def operation():
                return func(*args, **kwargs)

            stats, result = time_sync_operation(
                operation, desc, iterations, log_results=True, return_stats=True
            )

            # Type cast - we know stats is TimingStats when return_stats=True
            stats = cast(TimingStats, stats)

            if include_stats and iterations > 1:
                logger.log(log_level, f"📊 {desc} statistics:")
                logger.log(log_level, f"   Total calls: {stats.total_calls}")
                logger.log(log_level, f"   Average: {stats.average_time:.6f}s")
                logger.log(log_level, f"   Median: {stats.median_time:.6f}s")
                logger.log(log_level, f"   Range: {stats.min_time:.6f}s - {stats.max_time:.6f}s")

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Convenience functions for common use cases
async def time_api_call(operation, description="API call"):
    """Convenience function for timing API calls."""
    return await time_async_operation(operation, description, iterations=1)


def time_function(func, *args, **kwargs):
    """Convenience function for timing synchronous functions."""
    start = time.perf_counter_ns()
    result = func(*args, **kwargs)
    end = time.perf_counter_ns()
    duration = (end - start) / 1_000_000_000
    return duration, result


async def time_async_function(func, *args, **kwargs):
    """Convenience function for timing async functions."""
    start = time.perf_counter_ns()
    result = await func(*args, **kwargs)
    end = time.perf_counter_ns()
    duration = (end - start) / 1_000_000_000
    return duration, result
